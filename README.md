## Divi Wallet Importer for Divi Desktop

The **Divi Wallet Importer** helps you securely import your 12-word mnemonic seed phrase from Divi Wallet Mobile into the Divi Desktop Application.

### Features

- **Browser-based GUI**: Opens in your default browser with a guided wizard
- **Terminal mode**: Full CLI fallback with `--cli` flag
- **Zero dependencies**: Uses only Python standard library (no pip packages required)
- **Cross-platform**: Works on Windows, macOS, and Linux
- **Secure**: Server binds to `127.0.0.1` only, session token on all API calls, mnemonic cleared from memory after use

### Installation

#### Windows

Download **`divi-wallet-importer.exe`** from the [latest release](https://github.com/AustinCGomez/Divi-Wallet-Importer-for-Divi-Desktop-Application/releases/latest) and double-click to run. No Python required.

<details>
<summary>Alternative: install with pip</summary>

1. Install Python from [python.org/downloads](https://www.python.org/downloads/) (check **"Add Python to PATH"** during install)
2. Open **Command Prompt** or **PowerShell** and run:

```bash
pip install git+https://github.com/AustinCGomez/Divi-Wallet-Importer-for-Divi-Desktop-Application.git
```

If `pip` is not recognized, try `py -m pip` instead:

```bash
py -m pip install git+https://github.com/AustinCGomez/Divi-Wallet-Importer-for-Divi-Desktop-Application.git
```
</details>

#### macOS

macOS ships with Python 3 on recent versions. Open **Terminal** and run:

```bash
pip3 install git+https://github.com/AustinCGomez/Divi-Wallet-Importer-for-Divi-Desktop-Application.git
```

If you get a "command not found" error, install Python from [python.org/downloads](https://www.python.org/downloads/) and try again.

<details>
<summary>Alternative: standalone binary</summary>

Download **`divi-wallet-importer-macos`** from the [latest release](https://github.com/AustinCGomez/Divi-Wallet-Importer-for-Divi-Desktop-Application/releases/latest), then:

```bash
chmod +x divi-wallet-importer-macos
./divi-wallet-importer-macos
```
</details>

#### Linux

Most distributions include Python 3. You may need to install `pip` first:

```bash
# Debian/Ubuntu
sudo apt install python3-pip

# Fedora
sudo dnf install python3-pip
```

Then install:

```bash
pip3 install git+https://github.com/AustinCGomez/Divi-Wallet-Importer-for-Divi-Desktop-Application.git
```

<details>
<summary>Alternative: standalone binary</summary>

Download **`divi-wallet-importer-linux`** from the [latest release](https://github.com/AustinCGomez/Divi-Wallet-Importer-for-Divi-Desktop-Application/releases/latest), then:

```bash
chmod +x divi-wallet-importer-linux
./divi-wallet-importer-linux
```
</details>

#### Install from source

```bash
git clone https://github.com/AustinCGomez/Divi-Wallet-Importer-for-Divi-Desktop-Application.git
cd Divi-Wallet-Importer-for-Divi-Desktop-Application
pip install .
```

### Usage

**Browser mode** (default):

```bash
divi-wallet-importer
```

This starts a local web server and opens the wizard in your default browser.

**Terminal mode**:

```bash
divi-wallet-importer --cli
```

Runs entirely in the terminal with text prompts.

**Options**:

| Flag | Description |
|------|-------------|
| `--cli` | Run in terminal-only mode (no browser) |
| `--port PORT` | Use a specific port (default: auto-select) |
| `--no-open` | Start server without opening browser |
| `--clear` | Clear any in-progress recovery state and start fresh |

You can also run as a module:

```bash
python -m divi_wallet_importer
```

### Recovery Steps

1. **Install Divi Desktop**: Download from [diviproject.org/downloads](https://diviproject.org/downloads)
2. **Sync Divi Desktop**: Allow it to fully sync with the blockchain
3. **Close Divi Desktop**: Shut it down before running the importer
4. **Run Divi Wallet Importer**: Follow the wizard to enter your 12-word seed phrase
5. **Wait for wallet recovery**: The importer starts the Divi daemon and recreates your wallet from the seed phrase
6. **Divi Desktop launches automatically**: Once your wallet is recovered, Divi Desktop opens and finishes syncing on its own
7. **Close encrypt popup**: When the "Encrypt Wallet" popup appears, dismiss it for now
8. **Check your balance**: Confirm funds have migrated
9. **Restart and encrypt**: Close Divi Desktop, reopen it, then set a password to encrypt your wallet

If you close the importer during recovery, run it again and it will detect the in-progress recovery and offer to resume.

### Cross-Platform Support

| Platform | Data Directory | Desktop App Location |
|----------|---------------|---------------------|
| Windows | `%APPDATA%\DIVI` | `C:\Program Files\Divi Desktop\Divi Desktop.exe` |
| macOS | `~/Library/Application Support/DIVI` | `/Applications/Divi Desktop.app` |
| Linux | `~/.divi` | `/usr/bin/divi-desktop` |

### Environment Variable Overrides

| Variable | Purpose |
|----------|---------|
| `DIVI_DAEMON_PATH` | Full path to the `divid` binary |

### Troubleshooting

- **Error logs**: Check `~/Desktop/DWtoDD_logs/` for error details
- **Daemon not found**: Set `DIVI_DAEMON_PATH` environment variable to the full path of your `divid` binary
- **Need help?**: Join the [Divi Discord](https://discord.gg/diviproject)

### Contributing

We welcome contributions! Please fork this repository and submit pull requests for bug fixes or enhancements.

---

Thank you for using the **Divi Wallet Importer for Divi Desktop**!
