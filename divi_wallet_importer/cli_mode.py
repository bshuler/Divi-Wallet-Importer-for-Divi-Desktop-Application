"""Terminal-only fallback mode for Divi Wallet Importer."""

import getpass
import re
import sys
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


def _format_elapsed(seconds):
    """Format elapsed seconds as e.g. '1m 30s' or '45s'."""
    if seconds < 60:
        return "{}s".format(seconds)
    m = seconds // 60
    s = seconds % 60
    return "{}m {}s".format(m, s)


def _read_mnemonic_hidden():
    """Read a 12 or 24-word mnemonic with echo disabled, accepting multi-line paste.

    getpass.getpass() only reads a single line, so pasting words separated by
    newlines loses everything after the first line.  This function uses raw
    terminal mode and reads character-by-character.  After each newline it uses
    select() with a short timeout to distinguish "more paste data arriving"
    from "user pressed Enter and is waiting."  This handles any combination of
    spaces, newlines, commas, or tabs between words.
    """
    words = []

    try:
        # Unix: disable echo via termios, use select for paste detection
        import termios
        import tty
        import select as _select
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd, termios.TCSADRAIN)
            buf = []
            while True:
                ch = sys.stdin.read(1)
                if ch in ('\r', '\n'):
                    line = ''.join(buf).strip()
                    buf = []
                    sys.stderr.write('\r\n')
                    if line:
                        words.extend(re.split(r'[\s,]+', line))
                    if len(words) >= 24:
                        break
                    # Check if more data is arriving (paste in progress)
                    if _select.select([fd], [], [], 0.15)[0]:
                        continue  # more paste data coming, keep reading
                    # No more data — user pressed Enter manually
                    if words:
                        break  # accept what we have
                elif ch in ('\x7f', '\x08'):  # backspace
                    if buf:
                        buf.pop()
                        sys.stderr.write('\b \b')
                        sys.stderr.flush()
                elif ch == '\x03':  # Ctrl+C
                    raise KeyboardInterrupt
                elif ch == '\x04':  # Ctrl+D
                    break
                else:
                    buf.append(ch)
                    sys.stderr.write('*')
                    sys.stderr.flush()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except (ImportError, OSError):
        # Windows or non-tty: fall back to getpass line-by-line
        while len(words) < 24:
            prompt = "Mnemonic (hidden): " if not words else "  ...continue: "
            line = getpass.getpass(prompt).strip()
            if not line:
                break
            words.extend(re.split(r'[\s,]+', line))

    return " ".join(w.lower() for w in words if w)


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

    if prereqs["desktop_app_running"]:
        msg = "  [**] Divi Desktop is currently running"
        if prereqs["desktop_app_pid"]:
            msg += " (PID {})".format(prereqs["desktop_app_pid"])
        print(msg)
        print("       Divi Desktop must be closed before the wallet can be imported.")
        if not _ask_yes_no("       Close Divi Desktop and continue?"):
            print("       Cannot proceed while Divi Desktop is running. Exiting.")
            return
        print("       Closing Divi Desktop...")
        api.stop_desktop()
        elapsed = 0
        while True:
            time.sleep(3)
            elapsed += 3
            info = api.check_desktop_running()
            if not info["running"]:
                print("\r       Divi Desktop closed. ({} elapsed)".format(
                    _format_elapsed(elapsed)).ljust(60))
                break
            print("\r       Waiting for Divi Desktop to close... ({})".format(
                _format_elapsed(elapsed)), end="", flush=True)
            # Every 60 seconds, offer the option to stop waiting
            if elapsed % 60 == 0:
                print()
                if not _ask_yes_no("       Still waiting. Keep waiting?"):
                    print("       Exiting.")
                    return

    # Re-check daemon status (closing Desktop may have stopped it)
    if prereqs["daemon_running"] and prereqs["desktop_app_running"]:
        daemon_check = api.check_desktop_running()
        if not daemon_check["running"]:
            # Desktop closed, give daemon a moment to shut down too
            time.sleep(3)
        from divi_wallet_importer.platform_utils import find_running_daemon
        prereqs["daemon_running"] = find_running_daemon()["running"]

    if prereqs["daemon_running"]:
        msg = "  [**] Divi daemon is currently running"
        if prereqs["daemon_pid"]:
            msg += " (PID {})".format(prereqs["daemon_pid"])
        if prereqs["rpc_port_open"]:
            msg += " - RPC port 51473 open"
        print(msg)
        print("       The daemon must be stopped before recovery can begin.")
        if not _ask_yes_no("       Stop the daemon and continue?"):
            print("       Cannot proceed while the daemon is running. Exiting.")
            return
        print("       Stopping daemon via RPC...")
        result = api.stop_daemon()
        if result["success"]:
            print("       {}".format(result["message"]))
        else:
            print("       ERROR: {}".format(result["message"]))
            return

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
    print("Enter your 12 or 24-word mnemonic seed phrase.")
    print("You can paste all words at once (even across multiple lines).")
    print("Your input will be hidden for security.")
    print("-" * 60)

    mnemonic = _read_mnemonic_hidden()

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

    # Suppress console logger during \r progress updates to avoid interleaved output
    import logging
    _cli_logger = logging.getLogger('divi_importer')
    _console_handlers = [h for h in _cli_logger.handlers if isinstance(h, logging.StreamHandler)
                         and not isinstance(h, logging.FileHandler)]
    for h in _console_handlers:
        _cli_logger.removeHandler(h)

    last_line = ""
    try:
        while True:
            status = api.get_recovery_status()
            line = "  [{}] {}".format(status["phase"] or status["state"], status["message"])
            if status["progress"]:
                line += " ({})".format(status["progress"])

            if status["state"] in ("complete", "error"):
                if last_line:
                    print()  # newline after previous \r line
                print(line)
                break
            if status["state"] == "launched":
                if last_line:
                    print()  # newline after previous \r line
                print(line)
                print()
                print("  Divi Desktop has been launched.")
                print("  It will synchronize and complete the wallet conversion automatically.")
                print("  You can close this tool now.")
                break

            # Overwrite in-place for progress updates
            print("\r" + line.ljust(80), end="", flush=True)
            last_line = line
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped. Recovery continues in background.")
        print("Run this tool again to resume monitoring or launch Divi Desktop.")
        return
    finally:
        for h in _console_handlers:
            _cli_logger.addHandler(h)

    if status["state"] == "complete":
        if _ask_yes_no("\nLaunch Divi Desktop?"):
            result = api.launch_desktop()
            print(result["message"])
            print("Divi Desktop will synchronize and complete the wallet conversion.")

    print("\nDone.")
