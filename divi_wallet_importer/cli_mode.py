"""Terminal-only fallback mode for Divi Wallet Importer."""

import getpass
import time

from divi_wallet_importer import api


def _ask_yes_no(prompt):
    """Ask a yes/no question, return True for yes."""
    while True:
        answer = input("{} [y/n]: ".format(prompt)).strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Please enter 'y' or 'n'.")


def run_cli():
    """Run the wallet importer in terminal mode."""
    print("=" * 60)
    print("  Divi Wallet Importer for Divi Desktop")
    print("  Terminal Mode")
    print("=" * 60)
    print()

    # Check for in-progress recovery
    recovery = api.check_recovery_in_progress()
    if recovery["in_progress"]:
        elapsed = recovery["elapsed"]
        m = elapsed // 60
        s = elapsed % 60
        print("  A recovery is already in progress.")
        print("  Phase: {}".format(recovery["phase"]))
        print("  Elapsed: {}m {}s".format(m, s))
        print("  Status: {}".format(recovery["message"]))
        print()
        choice = input("  [R]esume monitoring, [L]aunch Divi Desktop, or [C]lear and start over? ").strip().lower()
        if choice in ("r", "resume"):
            result = api.resume_monitoring()
            if result["success"]:
                print("\n  Resumed. Monitoring recovery progress (Ctrl+C to stop)...\n")
                try:
                    while True:
                        status = api.get_recovery_status()
                        line = "  [{}] {}".format(status["phase"] or status["state"], status["message"])
                        if status["progress"]:
                            line += " ({})".format(status["progress"])
                        print("\r" + line.ljust(80), end="", flush=True)
                        if status["state"] in ("complete", "launched", "error"):
                            print()
                            break
                        time.sleep(5)
                except KeyboardInterrupt:
                    print("\n\n  Monitoring stopped. Recovery continues in background.")
                if status["state"] == "launched":
                    print("\n  Divi Desktop has been launched. It will finish syncing automatically.")
                return
            else:
                print("  {}".format(result["message"]))
        elif choice in ("l", "launch"):
            result = api.launch_desktop()
            print("  {}".format(result["message"]))
            print("  Divi Desktop will synchronize and complete the wallet conversion.")
            return
        elif choice in ("c", "clear"):
            result = api.clear_recovery()
            print("  {}".format(result["message"]))
            print()
        else:
            print("  Unrecognized choice. Starting fresh.\n")
            api.clear_recovery()

    # Platform info
    info = api.get_platform_info()
    print("Platform: {}".format(info["platform"]))
    print("Divi data dir: {}".format(info["divi_data_dir"]))
    print()

    # Auto-detect prerequisites
    print("Checking prerequisites...")
    prereqs = api.check_prerequisites()
    print()

    if prereqs["desktop_installed"]:
        print("  [OK] Divi Desktop found: {}".format(prereqs["desktop_path"]))
    else:
        print("  [!!] Divi Desktop not found at: {}".format(prereqs["desktop_path"]))
        print("\nPlease install Divi Desktop first:")
        print("  https://diviproject.org/downloads")
        return

    if prereqs["daemon_found"]:
        print("  [OK] Divi daemon found: {}".format(prereqs["daemon_path"]))
    else:
        print("  [!!] Divi daemon not found: {}".format(prereqs["daemon_path"]))
        print("\nSet DIVI_DAEMON_PATH environment variable to the full path of your divid binary.")
        return

    if prereqs["daemon_running"]:
        msg = "  [**] Divi daemon is currently running"
        if prereqs["daemon_pid"]:
            msg += " (PID {})".format(prereqs["daemon_pid"])
        if prereqs["rpc_port_open"]:
            msg += " - RPC port 51473 open"
        print(msg)
        if _ask_yes_no("       Stop the daemon before continuing?"):
            print("       Stopping daemon via RPC...")
            result = api.stop_daemon()
            if result["success"]:
                print("       {}".format(result["message"]))
            else:
                print("       Warning: {}".format(result["message"]))
        else:
            print("       Continuing with daemon running.")

    if prereqs["blockchain_synced"]:
        print("  [OK] Blockchain data found (synced)")
    else:
        if prereqs["data_dir_exists"]:
            print("  [!!] Blockchain not fully synced (missing blocks or chainstate)")
        else:
            print("  [!!] Divi data directory not found: {}".format(prereqs["divi_data_dir"]))
        print("\nPlease sync Divi Desktop fully before attempting recovery.")
        if not _ask_yes_no("Continue anyway?"):
            return

    print()

    # Check wallet
    wallet = api.check_wallet()
    if wallet["exists"]:
        print("\nExisting wallet.dat found at: {}".format(wallet["path"]))
        if _ask_yes_no("Back up and rename wallet.dat?"):
            result = api.backup_wallet()
            if result["success"]:
                print("  {}".format(result["message"]))
            else:
                print("  ERROR: {}".format(result["message"]))
                return
        else:
            print("Backup cancelled. Exiting.")
            return
    else:
        print("\nNo existing wallet.dat found. Proceeding to seed entry.")

    # Mnemonic entry
    print("\n" + "-" * 60)
    print("Enter your 12-word mnemonic seed phrase.")
    print("Words must be lowercase, separated by spaces.")
    print("Your input will be hidden for security.")
    print("-" * 60)

    mnemonic = getpass.getpass("Mnemonic (hidden): ").strip()

    # Validate
    result = api.validate_seed(mnemonic)
    if not result["valid"]:
        print("\nERROR: {}".format(result["message"]))
        return

    print("\nMnemonic is valid! Starting recovery...")

    # Start recovery
    result = api.start_recovery(mnemonic)
    mnemonic = ""  # Clear from memory

    if not result["success"]:
        print("ERROR: {}".format(result["message"]))
        return

    print(result["message"])
    print("\nMonitoring recovery progress (Ctrl+C to stop)...")
    print()

    try:
        while True:
            status = api.get_recovery_status()
            line = "  [{}] {}".format(status["phase"] or status["state"], status["message"])
            if status["progress"]:
                line += " ({})".format(status["progress"])
            print("\r" + line.ljust(80), end="", flush=True)

            if status["state"] in ("complete", "error"):
                print()
                break
            if status["state"] == "launched":
                print()
                print("\n  Divi Desktop has been launched.")
                print("  It will synchronize and complete the wallet conversion automatically.")
                print("  You can close this tool now.")
                break

            time.sleep(5)
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped. Recovery continues in background.")
        print("Run this tool again to resume monitoring or launch Divi Desktop.")
        return

    if status["state"] == "complete":
        if _ask_yes_no("\nLaunch Divi Desktop?"):
            result = api.launch_desktop()
            print(result["message"])
            print("Divi Desktop will synchronize and complete the wallet conversion.")

    print("\nDone.")
