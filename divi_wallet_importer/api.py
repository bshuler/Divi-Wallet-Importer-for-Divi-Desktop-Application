"""Business logic for Divi Wallet Importer."""

import os
import re
import json
import shutil
import datetime
import subprocess
import threading
import time
import logging
import logging.handlers
from divi_wallet_importer import platform_utils
from divi_wallet_importer.bip39 import validate_mnemonic
from divi_wallet_importer.rpc import DiviRPC, RPCError, RPCConnectionError

logger = logging.getLogger('divi_importer')

# ---------------------------------------------------------------------------
# Mnemonic redaction
# ---------------------------------------------------------------------------

class MnemonicRedactionFilter(logging.Filter):
    """Scrub mnemonic seed phrases from all log output."""
    def filter(self, record):
        record.msg = re.sub(r'-mnemonic=[^\s\]]+', '-mnemonic=[REDACTED]', str(record.msg))
        if hasattr(record, 'args') and record.args:
            record.args = tuple(
                re.sub(r'-mnemonic=[^\s\]]+', '-mnemonic=[REDACTED]', str(a))
                if isinstance(a, str) else a
                for a in record.args
            )
        return True


def _setup_logging():
    """Configure logging with mnemonic redaction and file output."""
    if logger.handlers:
        return  # already configured

    logger.setLevel(logging.DEBUG)
    redaction = MnemonicRedactionFilter()

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.addFilter(redaction)
    console.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
    logger.addHandler(console)

    # File handler
    log_dir = platform_utils.get_log_directory()
    try:
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, 'importer.log')
        file_handler = logging.handlers.RotatingFileHandler(
            log_path, maxBytes=2 * 1024 * 1024, backupCount=3
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.addFilter(redaction)
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        )
        logger.addHandler(file_handler)
    except OSError:
        pass  # non-critical if log dir can't be created


_setup_logging()

# ---------------------------------------------------------------------------
# Thread-safe recovery state
# ---------------------------------------------------------------------------

_recovery_lock = threading.Lock()
_recovery_status = {"state": "idle", "phase": "", "message": "", "progress": ""}
_recovery_start_time = None
_auto_launched = False


def _set_status(state, message, progress="", phase=""):
    global _recovery_status
    with _recovery_lock:
        _recovery_status = {
            "state": state,
            "phase": phase,
            "message": message,
            "progress": progress,
        }
    if phase:
        _save_state(phase)


def _get_state_path():
    """Path to persistent recovery state file."""
    divi_dir = platform_utils.get_divi_data_dir()
    return os.path.join(divi_dir, 'importer_state.json')


def _save_state(phase, extra=None):
    """Persist recovery state to disk for resume detection."""
    state = {
        "start_time": _recovery_start_time,
        "phase": phase,
        "timestamp": time.time(),
    }
    if extra:
        state.update(extra)
    try:
        path = _get_state_path()
        with open(path, 'w') as f:
            json.dump(state, f)
    except OSError:
        pass


def _load_state():
    """Load persisted recovery state. Returns dict or None."""
    try:
        path = _get_state_path()
        with open(path, 'r') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _clear_state():
    """Delete persisted recovery state."""
    try:
        path = _get_state_path()
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _auto_launch_desktop():
    """Auto-launch Divi Desktop when wallet recovery enters scanning phase."""
    global _auto_launched
    _auto_launched = True
    logger.info("Wallet recovered. Auto-launching Divi Desktop to handle remaining sync.")
    try:
        desktop_path = platform_utils.get_divi_desktop_executable()
        platform_utils.launch_application(desktop_path)
        _set_status("launched", "Divi Desktop launched. It will finish syncing your wallet automatically.", "", "launched")
        _clear_state()
    except Exception as e:
        logger.warning("Could not auto-launch Desktop: %s", e)
        # Don't change status — user can still launch manually


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

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


def check_prerequisites():
    """Auto-detect Divi Desktop installation and sync status."""
    plat = platform_utils.get_platform()
    divi_dir = platform_utils.get_divi_data_dir()

    # Check Divi Desktop executable
    desktop_path = platform_utils.get_divi_desktop_executable()
    if plat == "macos" and desktop_path.endswith(".app"):
        desktop_installed = os.path.isdir(desktop_path)
    else:
        desktop_installed = os.path.isfile(desktop_path)

    # Check daemon binary
    daemon_found = False
    daemon_path = ""
    try:
        daemon_path = platform_utils.get_daemon_path()
        daemon_found = True
    except FileNotFoundError as e:
        daemon_path = str(e)

    # Check if daemon is running on default ports
    running_info = platform_utils.find_running_daemon()

    # Check data directory
    data_dir_exists = os.path.isdir(divi_dir)

    # Check blockchain sync by looking for chain data
    blockchain_synced = False
    if data_dir_exists:
        blocks_dir = os.path.join(divi_dir, "blocks")
        chainstate_dir = os.path.join(divi_dir, "chainstate")
        blockchain_synced = os.path.isdir(blocks_dir) and os.path.isdir(chainstate_dir)

    return {
        "platform": plat,
        "desktop_installed": desktop_installed,
        "desktop_path": desktop_path,
        "daemon_found": daemon_found,
        "daemon_path": daemon_path,
        "data_dir_exists": data_dir_exists,
        "blockchain_synced": blockchain_synced,
        "divi_data_dir": divi_dir,
        "daemon_running": running_info["running"],
        "daemon_pid": running_info["pid"],
        "rpc_port_open": running_info["rpc_port"],
        "p2p_port_open": running_info["p2p_port"],
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


def check_recovery_in_progress():
    """Check if a recovery is currently in progress (daemon running in recovery mode).

    Returns dict with:
        in_progress: bool
        phase: str - current phase if in progress
        elapsed: int - seconds since recovery started
        message: str - human-readable status
    """
    # First check if we're actively monitoring (same process)
    with _recovery_lock:
        if _recovery_status["state"] == "running":
            elapsed = int(time.time() - _recovery_start_time) if _recovery_start_time else 0
            return {
                "in_progress": True,
                "phase": _recovery_status["phase"],
                "elapsed": elapsed,
                "message": _recovery_status["message"],
            }

    # Check persisted state from a previous run
    saved = _load_state()
    if not saved:
        return {"in_progress": False, "phase": "", "elapsed": 0, "message": ""}

    # State file exists — check if daemon is actually still running
    try:
        rpc = DiviRPC.from_conf()
        rpc.getinfo()
        # Daemon is up and responding normally — may be done
        phase = saved.get("phase", "")
        if phase in ("complete", "error", ""):
            _clear_state()
            return {"in_progress": False, "phase": "", "elapsed": 0, "message": ""}
        # Still in a recovery phase
        start = saved.get("start_time", time.time())
        return {
            "in_progress": True,
            "phase": phase,
            "elapsed": int(time.time() - start),
            "message": "Recovery in progress (resumed).",
        }
    except RPCError as e:
        # Daemon is responding with error — still loading/scanning
        message = e.message
        phase = ""
        if "Loading block index" in message:
            phase = "loading_blocks"
        elif "Loading wallet" in message:
            phase = "recovering_wallet"
        elif "Rescanning" in message or "Scanning" in message:
            phase = "scanning"
        elif "Verifying" in message:
            phase = "verifying"
        else:
            phase = saved.get("phase", "")
        start = saved.get("start_time", time.time())
        return {
            "in_progress": True,
            "phase": phase,
            "elapsed": int(time.time() - start),
            "message": message,
        }
    except RPCConnectionError:
        # Daemon not running — recovery ended (crashed or completed)
        _clear_state()
        return {"in_progress": False, "phase": "", "elapsed": 0, "message": ""}


def resume_monitoring():
    """Resume monitoring an in-progress recovery (e.g. after tool restart).

    Returns dict with success, message.
    """
    global _recovery_start_time

    status = check_recovery_in_progress()
    if not status["in_progress"]:
        return {"success": False, "message": "No recovery in progress."}

    # Restore start time from saved state
    saved = _load_state()
    if saved and saved.get("start_time"):
        _recovery_start_time = saved["start_time"]
    else:
        _recovery_start_time = time.time()

    _set_status("running", status["message"], "", status["phase"])

    thread = threading.Thread(target=_monitor_recovery, daemon=True)
    thread.start()

    return {"success": True, "message": "Resumed monitoring recovery."}


def clear_recovery():
    """Clear recovery state and optionally stop daemon. For starting over."""
    _clear_state()
    global _recovery_status, _recovery_start_time
    with _recovery_lock:
        _recovery_status = {"state": "idle", "phase": "", "message": "", "progress": ""}
    _recovery_start_time = None
    return {"success": True, "message": "Recovery state cleared."}


def stop_daemon():
    """Stop the running divid daemon via RPC."""
    try:
        rpc = DiviRPC.from_conf()
    except RPCConnectionError as e:
        return {"success": False, "message": str(e)}

    try:
        rpc.stop()
        logger.info("Sent RPC stop command to daemon.")
    except RPCConnectionError:
        return {"success": True, "message": "Daemon is not running."}
    except RPCError as e:
        return {"success": False, "message": "RPC error: {}".format(e.message)}

    # Wait for daemon to shut down
    for _ in range(15):
        time.sleep(2)
        if not rpc.is_responsive():
            logger.info("Daemon stopped successfully.")
            return {"success": True, "message": "Daemon stopped."}

    return {"success": False, "message": "Daemon did not stop within 30 seconds."}


def start_recovery(mnemonic_str):
    """Start divid daemon with mnemonic, launch monitor thread. Returns dict with success, message."""
    global _recovery_status
    global _auto_launched
    _auto_launched = False

    try:
        daemon_path = platform_utils.get_daemon_path()
    except FileNotFoundError as e:
        return {"success": False, "message": str(e)}

    # Step 1: Check for running daemon via RPC and stop it
    try:
        rpc = DiviRPC.from_conf()
        if rpc.is_responsive():
            logger.info("Daemon is running. Sending stop command before recovery...")
            _set_status("running", "Stopping existing daemon...", "", "stopping")
            try:
                rpc.stop()
            except (RPCError, RPCConnectionError):
                pass
            # Wait for daemon to shut down
            for i in range(15):
                time.sleep(2)
                if not rpc.is_responsive():
                    break
            else:
                return {"success": False, "message": "Could not stop existing daemon within 30 seconds."}
            logger.info("Existing daemon stopped.")
    except RPCConnectionError:
        pass  # No conf or daemon not running — fine

    # Step 2: Launch daemon with mnemonic
    command = [daemon_path, '-mnemonic={}'.format(mnemonic_str), '-force_rescan=1']
    logger.info("Launching daemon: %s", [daemon_path, '-mnemonic=[REDACTED]', '-force_rescan=1'])

    try:
        subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception as e:
        return {"success": False, "message": "Failed to start daemon: {}".format(e)}

    global _recovery_start_time
    _recovery_start_time = time.time()
    _set_status("running", "Daemon started. Waiting for RPC to become available...", "", "starting")

    # Step 3: Wait for RPC to become available (daemon needs time to start)
    logger.info("Waiting for daemon RPC to become available...")
    rpc_ready = False
    for _ in range(30):
        time.sleep(2)
        try:
            rpc = DiviRPC.from_conf()
            rpc.getinfo()
            rpc_ready = True
            break
        except RPCError:
            # RPC responded with an error (e.g. "Loading...") — daemon IS up
            rpc_ready = True
            break
        except RPCConnectionError:
            pass  # Not ready yet

    if not rpc_ready:
        logger.warning("Daemon RPC did not become available within 60 seconds.")
        # Don't fail — it might just be slow. Monitor thread will handle it.

    # Step 4: Check wallet.dat exists within 15s
    divi_dir = platform_utils.get_divi_data_dir()
    wallet_path = os.path.join(divi_dir, 'wallet.dat')
    wallet_found = False
    for _ in range(5):
        if os.path.exists(wallet_path):
            wallet_found = True
            break
        time.sleep(3)
    if wallet_found:
        logger.info("wallet.dat created at %s", wallet_path)
    else:
        logger.warning("wallet.dat not found after daemon start (may appear later).")

    _set_status("running", "Daemon started. Monitoring recovery...", "", "starting")

    thread = threading.Thread(target=_monitor_recovery, daemon=True)
    thread.start()

    return {"success": True, "message": "Recovery started. Daemon launched."}


def get_recovery_status():
    """Return current recovery status dict (thread-safe)."""
    with _recovery_lock:
        status = dict(_recovery_status)
    if _recovery_start_time and status["state"] in ("running", "launched"):
        status["elapsed"] = int(time.time() - _recovery_start_time)
    else:
        status["elapsed"] = 0
    return status


def _monitor_recovery():
    """Background thread: poll divid RPC for recovery progress."""
    # Give daemon a moment to settle
    time.sleep(5)

    try:
        rpc = DiviRPC.from_conf()
    except RPCConnectionError as e:
        _set_status("error", "Cannot read RPC config: {}".format(e), "")
        return

    consecutive_failures = 0
    max_failures = 6  # 30 seconds of no response

    while True:
        try:
            info = rpc.getinfo()
            consecutive_failures = 0

            # Success — daemon is responding with JSON
            blocks = info.get("blocks", 0)
            headers = info.get("headers", 0)

            if headers > 0 and blocks >= headers:
                # Fully synced
                logger.info("Recovery complete. Blocks: %d/%d", blocks, headers)
                _set_status("complete", "Recovery complete. Ready to launch Divi Desktop.", "100%", "complete")
                _clear_state()
                return
            elif headers > 0:
                pct = "{}%".format(int(blocks / max(headers, 1) * 100))
                _set_status("running", "Block {}/{}".format(blocks, headers), pct, "syncing")
            else:
                _set_status("running", "Waiting for block headers...", "", "syncing")

        except RPCError as e:
            consecutive_failures = 0  # daemon IS responding, just with an error
            message = e.message

            if "Loading block index" in message:
                _set_status("running", "Loading blockchain index...", "", "loading_blocks")
            elif "Loading wallet" in message:
                percent = ""
                try:
                    percent = message.split("(")[1].split("%")[0].strip() + "%"
                except (IndexError, ValueError):
                    percent = ""
                _set_status("running", "Recreating wallet from seed phrase... {}".format(percent), percent, "recovering_wallet")
            elif "Rescanning" in message or "Scanning" in message:
                _set_status("running", "Scanning blockchain for your transactions...", "", "scanning")
                if not _auto_launched:
                    _auto_launch_desktop()
            elif "Verifying" in message:
                _set_status("running", "Verifying blockchain data...", "", "verifying")
            elif "Activating best chain" in message:
                _set_status("running", "Activating best chain...", "", "loading_blocks")
            else:
                _set_status("running", message, "", "")

        except RPCConnectionError:
            consecutive_failures += 1
            if consecutive_failures >= max_failures:
                logger.error("Daemon stopped responding after %d attempts.", max_failures)
                _set_status("error", "Daemon stopped responding.", "", "error")
                return
            # Might be temporarily busy — keep trying
            _set_status("running", "Waiting for daemon response...", "", "starting")

        time.sleep(5)


def launch_desktop():
    """Launch Divi Desktop application."""
    try:
        desktop_path = platform_utils.get_divi_desktop_executable()
        platform_utils.launch_application(desktop_path)
        _clear_state()
        logger.info("Divi Desktop launched.")
        return {"success": True, "message": "Divi Desktop launched."}
    except Exception as e:
        return {"success": False, "message": "Could not launch Divi Desktop: {}".format(e)}
