import os
import sys
import subprocess
import webbrowser
import platform
from pathlib import Path


def get_platform() -> str:
    """Returns 'windows', 'macos', or 'linux' based on sys.platform."""
    if sys.platform == 'win32':
        return 'windows'
    elif sys.platform == 'darwin':
        return 'macos'
    else:
        return 'linux'


def get_divi_data_dir() -> str:
    """Returns the Divi Core data directory path for the current platform."""
    plat = get_platform()
    if plat == 'windows':
        return os.path.join(os.getenv('APPDATA'), 'DIVI')
    elif plat == 'macos':
        return str(Path.home() / 'Library' / 'Application Support' / 'DIVI')
    else:  # linux
        return str(Path.home() / '.divi')


def get_divi_conf_path() -> str:
    """Returns the path to divi.conf in the Divi data directory."""
    return os.path.join(get_divi_data_dir(), 'divi.conf')


def get_divi_desktop_data_dir() -> str:
    """Returns the Divi Desktop data directory, probing multiple locations."""
    plat = get_platform()

    if plat == 'windows':
        return os.path.join(os.getenv('APPDATA'), 'Divi Desktop')

    elif plat == 'macos':
        # Try multiple locations in order
        candidates = [
            Path.home() / 'Library' / 'Application Support' / 'Divi Desktop',
            Path.home() / 'Library' / 'Application Support' / 'divi-desktop',
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        # Return first candidate as best guess
        return str(candidates[0])

    else:  # linux
        candidates = [
            Path.home() / '.config' / 'divi-desktop',
            Path.home() / '.config' / 'Divi Desktop',
            Path.home() / '.local' / 'share' / 'Divi Desktop',
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return str(candidates[0])


def find_running_daemon():
    """Check if divid is already running by examining default ports.

    Returns dict with:
        running: bool - whether divid appears to be running
        pid: int or None - process ID if found
        binary_path: str or None - path to the running binary if determinable
        rpc_port: bool - whether RPC port 51473 is open
        p2p_port: bool - whether P2P port 51472 is open
    """
    result = {
        "running": False,
        "pid": None,
        "binary_path": None,
        "rpc_port": False,
        "p2p_port": False,
    }

    plat = get_platform()

    # Check ports
    for port, key in [(51473, "rpc_port"), (51472, "p2p_port")]:
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            conn = s.connect_ex(('127.0.0.1', port))
            s.close()
            if conn == 0:
                result[key] = True
        except Exception:
            pass

    if not result["rpc_port"] and not result["p2p_port"]:
        return result

    # Something is listening - try to find the process
    result["running"] = True

    try:
        if plat in ('macos', 'linux'):
            # Use lsof to find what's listening on the RPC port
            port_to_check = 51473 if result["rpc_port"] else 51472
            proc = subprocess.run(
                ['lsof', '-i', ':{}'.format(port_to_check), '-t'],
                capture_output=True, text=True, check=False, timeout=5
            )
            if proc.returncode == 0 and proc.stdout.strip():
                pid = int(proc.stdout.strip().split('\n')[0])
                result["pid"] = pid
                # Get binary path from pid
                if plat == 'macos':
                    proc2 = subprocess.run(
                        ['ps', '-p', str(pid), '-o', 'comm='],
                        capture_output=True, text=True, check=False, timeout=5
                    )
                else:
                    # Linux: read /proc/pid/exe symlink
                    try:
                        result["binary_path"] = os.readlink('/proc/{}/exe'.format(pid))
                    except (OSError, PermissionError):
                        pass
                if plat == 'macos' and proc2.returncode == 0:
                    result["binary_path"] = proc2.stdout.strip()
        elif plat == 'windows':
            # Use netstat to find PID listening on the port
            port_to_check = 51473 if result["rpc_port"] else 51472
            proc = subprocess.run(
                ['netstat', '-ano'],
                capture_output=True, text=True, check=False, timeout=5
            )
            if proc.returncode == 0:
                for line in proc.stdout.split('\n'):
                    if ':{}'.format(port_to_check) in line and 'LISTENING' in line:
                        parts = line.split()
                        if len(parts) >= 5:
                            try:
                                pid = int(parts[-1])
                                result["pid"] = pid
                                # Get binary from PID via tasklist
                                proc2 = subprocess.run(
                                    ['tasklist', '/FI', 'PID eq {}'.format(pid), '/FO', 'CSV', '/NH'],
                                    capture_output=True, text=True, check=False, timeout=5
                                )
                                if proc2.returncode == 0 and proc2.stdout.strip():
                                    # CSV format: "name.exe","pid",...
                                    name = proc2.stdout.strip().split(',')[0].strip('"')
                                    if 'divid' in name.lower():
                                        result["binary_path"] = name
                            except (ValueError, IndexError):
                                pass
                        break
    except Exception:
        pass

    return result


def get_daemon_path() -> str:
    """
    Returns the divid daemon path with discovery sequence:
    1. Check DIVI_DAEMON_PATH env var
    2. Probe platform-specific locations
    3. Check if daemon is running (may reveal path)
    4. Raise FileNotFoundError if not found
    """
    # Step 1: Check env var override
    env_path = os.getenv('DIVI_DAEMON_PATH')
    if env_path and os.path.isfile(env_path):
        return env_path

    # Step 2: Build platform-specific candidates
    desktop_data = get_divi_desktop_data_dir()
    plat = get_platform()

    if plat == 'windows':
        binary = 'divid.exe'
        # Direct path first (from Divi Desktop source), then platform subfolders
        candidates = [
            os.path.join(desktop_data, 'divid', 'unpacked', binary),
            os.path.join(desktop_data, 'divid', 'unpacked', 'divi_win', binary),
            os.path.join(desktop_data, 'divid', 'unpacked', 'divi_win_64', binary),
        ]
    elif plat == 'macos':
        binary = 'divid'
        candidates = [
            os.path.join(desktop_data, 'divid', 'unpacked', binary),
            os.path.join(desktop_data, 'divid', 'unpacked', 'divi_osx', binary),
            os.path.join(desktop_data, 'divid', 'unpacked', 'divi_osx_64', binary),
            os.path.join(desktop_data, 'divid', 'unpacked', 'divi_mac_64', binary),
            os.path.join(desktop_data, 'divid', 'unpacked', 'divi_darwin_64', binary),
        ]
    else:  # linux
        binary = 'divid'
        candidates = [
            os.path.join(desktop_data, 'divid', 'unpacked', binary),
            os.path.join(desktop_data, 'divid', 'unpacked', 'divi_linux', binary),
            os.path.join(desktop_data, 'divid', 'unpacked', 'divi_linux_64', binary),
            os.path.join(desktop_data, 'divid', 'unpacked', 'divi_ubuntu', binary),
            os.path.join(desktop_data, 'divid', 'unpacked', 'divi_ubuntu_64', binary),
        ]

    # Step 3: Return first existing path
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    # Step 4: Check if daemon is already running (may reveal its path)
    running_info = find_running_daemon()
    if running_info["binary_path"] and os.path.isfile(running_info["binary_path"]):
        return running_info["binary_path"]

    # Step 5: Not found - raise with helpful message
    searched = '\n  '.join(candidates)
    raise FileNotFoundError(
        f"Could not find divid daemon. Searched:\n  {searched}\n"
        f"Hint: Set DIVI_DAEMON_PATH environment variable to override."
    )


def get_divi_desktop_executable() -> str:
    """Returns the Divi Desktop executable path."""
    plat = get_platform()

    if plat == 'windows':
        return 'C:/Program Files/Divi Desktop/Divi Desktop.exe'

    elif plat == 'macos':
        return '/Applications/Divi Desktop.app'

    else:  # linux
        candidates = [
            '/usr/bin/divi-desktop',
            '/opt/Divi Desktop/divi-desktop',
        ]
        for candidate in candidates:
            if os.path.isfile(candidate):
                return candidate
        # Return first candidate as best guess
        return candidates[0]


def get_log_directory() -> str:
    """Returns the log directory path, creating it if needed."""
    plat = get_platform()

    if plat == 'linux':
        desktop = Path.home() / 'Desktop'
        if not desktop.exists():
            # Fallback for Linux systems without Desktop
            return str(Path.home() / '.local' / 'share' / 'DWtoDD_logs')

    # All platforms (including Linux with Desktop)
    return str(Path.home() / 'Desktop' / 'DWtoDD_logs')


def open_url(url: str) -> None:
    """Opens a URL in the default browser."""
    webbrowser.open(url)


def launch_application(path: str) -> None:
    """Launches an application at the given path."""
    plat = get_platform()

    if plat == 'windows':
        os.startfile(path)
    elif plat == 'macos':
        subprocess.Popen(['open', path])
    else:  # linux
        subprocess.Popen(['xdg-open', path])


def get_base_dir() -> str:
    """Returns the base directory, supporting PyInstaller frozen mode."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return os.path.dirname(sys.executable)
    else:
        # Running as script
        return os.path.dirname(os.path.abspath(__file__))
