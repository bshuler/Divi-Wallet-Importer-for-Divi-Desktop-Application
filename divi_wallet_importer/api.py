"""Business logic for Divi Wallet Importer."""

import os
import json
import shutil
import datetime
import subprocess
import threading
import time
import logging
from divi_wallet_importer import platform_utils
from divi_wallet_importer.bip39 import validate_mnemonic

# Thread-safe recovery state
_recovery_lock = threading.Lock()
_recovery_status = {"state": "idle", "message": "", "progress": ""}

def get_platform_info():
    """Return platform info dict: platform, divi_data_dir, wallet_exists, divi_desktop_data_dir"""
    plat = platform_utils.get_platform()
    divi_dir = platform_utils.get_divi_data_dir()
    wallet_path = os.path.join(divi_dir, 'wallet.dat')
    return {
        "platform": plat,
        "divi_data_dir": divi_dir,
        "divi_desktop_data_dir": platform_utils.get_divi_desktop_data_dir(),
        "wallet_exists": os.path.exists(wallet_path),
    }

def check_wallet():
    """Check if wallet.dat exists. Returns dict with exists, path."""
    divi_dir = platform_utils.get_divi_data_dir()
    wallet_path = os.path.join(divi_dir, 'wallet.dat')
    return {
        "exists": os.path.exists(wallet_path),
        "path": wallet_path,
    }

def backup_wallet():
    """Rename wallet.dat with timestamp, delete divitxs.db. Returns dict with success, message, backup_name."""
    # Based on rename_wallet() and remove_divitxs_db() from main.py
    divi_dir = platform_utils.get_divi_data_dir()
    wallet_path = os.path.join(divi_dir, 'wallet.dat')

    now = datetime.datetime.now()
    backup_name = "wallet_backup_{}.dat".format(now.strftime('%Y-%m-%d-%H-%M-%S'))
    backup_path = os.path.join(divi_dir, backup_name)

    if not os.path.exists(wallet_path):
        return {"success": False, "message": "wallet.dat not found", "backup_name": ""}

    try:
        shutil.move(wallet_path, backup_path)
    except Exception as e:
        return {"success": False, "message": "Failed to backup wallet.dat: {}".format(e), "backup_name": ""}

    # Delete divitxs.db
    desktop_dir = platform_utils.get_divi_desktop_data_dir()
    divitxs_path = os.path.join(desktop_dir, "divitxs.db")
    divitxs_msg = ""
    if os.path.exists(divitxs_path):
        try:
            os.remove(divitxs_path)
            divitxs_msg = " Deleted divitxs.db."
        except Exception as e:
            divitxs_msg = " Warning: could not delete divitxs.db: {}".format(e)

    return {
        "success": True,
        "message": "wallet.dat renamed to {}.{}".format(backup_name, divitxs_msg),
        "backup_name": backup_name,
    }

def validate_seed(mnemonic_str):
    """Validate mnemonic string. Returns dict with valid, message."""
    valid, message = validate_mnemonic(mnemonic_str)
    return {"valid": valid, "message": message}

def start_recovery(mnemonic_str):
    """Start divid daemon with mnemonic, launch monitor thread. Returns dict with success, message."""
    global _recovery_status

    try:
        daemon_path = platform_utils.get_daemon_path()
    except FileNotFoundError as e:
        return {"success": False, "message": str(e)}

    command = [daemon_path, '-mnemonic={}'.format(mnemonic_str), '-force_rescan=1']

    try:
        subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception as e:
        return {"success": False, "message": "Failed to start daemon: {}".format(e)}

    with _recovery_lock:
        _recovery_status = {"state": "running", "message": "Daemon started. Monitoring recovery...", "progress": ""}

    thread = threading.Thread(target=_monitor_recovery, daemon=True)
    thread.start()

    return {"success": True, "message": "Recovery started. Daemon launched."}

def get_recovery_status():
    """Return current recovery status dict (thread-safe)."""
    with _recovery_lock:
        return dict(_recovery_status)

def _monitor_recovery():
    """Background thread: poll divi-cli getinfo for progress."""
    global _recovery_status

    try:
        cli_path = platform_utils.get_cli_path()
    except FileNotFoundError as e:
        with _recovery_lock:
            _recovery_status = {"state": "error", "message": str(e), "progress": ""}
        return

    while True:
        try:
            result = subprocess.run(
                [cli_path, "getinfo"],
                capture_output=True, text=True, check=False
            )
            output = result.stderr.strip() if result.stderr else result.stdout.strip()

            if output.startswith("error:"):
                try:
                    error_msg = json.loads(output.replace("error: ", ""))
                    message = error_msg.get("message", "")
                except (json.JSONDecodeError, ValueError):
                    message = output

                if "Loading block index" in message:
                    with _recovery_lock:
                        _recovery_status = {"state": "running", "message": "Loading blockchain data...", "progress": "loading_blocks"}
                elif "Loading wallet" in message:
                    percent = ""
                    try:
                        percent = message.split("(")[1].split("%")[0].strip() + "%"
                    except (IndexError, ValueError):
                        percent = ""
                    with _recovery_lock:
                        _recovery_status = {"state": "running", "message": "Wallet recovery in progress... {}".format(percent), "progress": percent}
                elif "Scanning chain for wallet updates" in message:
                    with _recovery_lock:
                        _recovery_status = {"state": "complete", "message": "Recovery complete. Ready to launch Divi Desktop.", "progress": "100%"}
                    return
                else:
                    with _recovery_lock:
                        _recovery_status = {"state": "running", "message": message, "progress": ""}
            else:
                with _recovery_lock:
                    _recovery_status = {"state": "complete", "message": "Recovery complete. Ready to launch Divi Desktop.", "progress": "100%"}
                return
        except Exception as e:
            with _recovery_lock:
                _recovery_status = {"state": "error", "message": "Monitor error: {}".format(e), "progress": ""}
            return

        time.sleep(5)

def launch_desktop():
    """Launch Divi Desktop application. Returns dict with success, message."""
    try:
        desktop_path = platform_utils.get_divi_desktop_executable()
        platform_utils.launch_application(desktop_path)
        return {"success": True, "message": "Divi Desktop launched."}
    except Exception as e:
        return {"success": False, "message": "Could not launch Divi Desktop: {}".format(e)}
