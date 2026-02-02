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
            Path.home() / '.config' / 'Divi Desktop',
            Path.home() / '.local' / 'share' / 'Divi Desktop',
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return str(candidates[0])


def get_daemon_path() -> str:
    """
    Returns the divid daemon path with discovery sequence:
    1. Check DIVI_DAEMON_PATH env var
    2. Probe platform-specific locations
    3. Raise FileNotFoundError if not found
    """
    # Step 1: Check env var override
    env_path = os.getenv('DIVI_DAEMON_PATH')
    if env_path and os.path.isfile(env_path):
        return env_path

    # Step 2: Build platform-specific candidates
    desktop_data = get_divi_desktop_data_dir()
    plat = get_platform()
    candidates = []

    if plat == 'windows':
        binary = 'divid.exe'
        subdirs = ['divi_win_64']
    elif plat == 'macos':
        binary = 'divid'
        subdirs = ['divi_osx_64', 'divi_mac_64', 'divi_darwin_64']
    else:  # linux
        binary = 'divid'
        subdirs = ['divi_linux_64', 'divi_ubuntu_64']

    for subdir in subdirs:
        path = os.path.join(desktop_data, 'divid', 'unpacked', subdir, binary)
        candidates.append(path)

    # Step 3: Return first existing path
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    # Step 4: Not found - raise with helpful message
    searched = '\n  '.join(candidates)
    raise FileNotFoundError(
        f"Could not find divid daemon. Searched:\n  {searched}\n"
        f"Hint: Set DIVI_DAEMON_PATH environment variable to override."
    )


def get_cli_path() -> str:
    """
    Returns the divi-cli path with discovery sequence:
    1. Check DIVI_CLI_PATH env var
    2. Probe platform-specific locations
    3. Raise FileNotFoundError if not found
    """
    # Step 1: Check env var override
    env_path = os.getenv('DIVI_CLI_PATH')
    if env_path and os.path.isfile(env_path):
        return env_path

    # Step 2: Build platform-specific candidates
    desktop_data = get_divi_desktop_data_dir()
    plat = get_platform()
    candidates = []

    if plat == 'windows':
        binary = 'divi-cli.exe'
        subdirs = ['divi_win_64']
    elif plat == 'macos':
        binary = 'divi-cli'
        subdirs = ['divi_osx_64', 'divi_mac_64', 'divi_darwin_64']
    else:  # linux
        binary = 'divi-cli'
        subdirs = ['divi_linux_64', 'divi_ubuntu_64']

    for subdir in subdirs:
        path = os.path.join(desktop_data, 'divid', 'unpacked', subdir, binary)
        candidates.append(path)

    # Step 3: Return first existing path
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    # Step 4: Not found - raise with helpful message
    searched = '\n  '.join(candidates)
    raise FileNotFoundError(
        f"Could not find divi-cli. Searched:\n  {searched}\n"
        f"Hint: Set DIVI_CLI_PATH environment variable to override."
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
