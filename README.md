## Divi Wallet Importer for Divi Desktop

The **Divi Wallet Importer** helps you securely import your 12-word mnemonic seed phrase from Divi Wallet Mobile into the Divi Desktop Application.

### Features

- **Browser-based GUI**: Opens in your default browser with a guided wizard
- **Terminal mode**: Full CLI fallback with `--cli` flag
- **Zero dependencies**: Uses only Python standard library (no pip packages required)
- **Cross-platform**: Works on Windows, macOS, and Linux
- **Secure**: Server binds to `127.0.0.1` only, session token on all API calls, mnemonic cleared from memory after use

### Installation

Install directly from GitHub:

```bash
pip install git+https://github.com/AustinCGomez/Divi-Wallet-Importer-for-Divi-Desktop-Application.git
```

Or clone and install locally:

```bash
git clone https://github.com/AustinCGomez/Divi-Wallet-Importer-for-Divi-Desktop-Application.git
cd Divi-Wallet-Importer-for-Divi-Desktop-Application
pip install .
```

For development:

```bash
pip install -e .
```

**Requirements**: Python 3.8 or later. No additional packages needed.

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

You can also run as a module:

```bash
python -m divi_wallet_importer
```

### Recovery Steps

1. **Install Divi Desktop**: Download from [diviproject.org/downloads](https://diviproject.org/downloads)
2. **Sync Divi Desktop**: Allow it to fully sync with the blockchain
3. **Close Divi Desktop**: Shut it down before running the importer
4. **Run Divi Wallet Importer**: Follow the wizard to enter your 12-word seed phrase (lowercase)
5. **Wait for recovery**: The importer will start the Divi daemon and monitor progress
6. **Divi Desktop opens**: When recovery is ready, launch Divi Desktop from the wizard
7. **Close encrypt popup**: When the "Encrypt Wallet" popup appears, dismiss it for now
8. **Check your balance**: Confirm funds have migrated
9. **Restart and encrypt**: Close Divi Desktop, reopen it, then set a password to encrypt your wallet

> **Note:** Seed words from Divi Wallet are displayed in UPPERCASE, but must be entered in **lowercase** for the recovery to work.

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
| `DIVI_CLI_PATH` | Full path to the `divi-cli` binary |

### Troubleshooting

- **Error logs**: Check `~/Desktop/DWtoDD_logs/` for error details
- **Daemon not found**: Set `DIVI_DAEMON_PATH` environment variable to the full path of your `divid` binary
- **Need help?**: Join the [Divi Discord](https://discord.gg/diviproject)

### Contributing

We welcome contributions! Please fork this repository and submit pull requests for bug fixes or enhancements.

---

Thank you for using the **Divi Wallet Importer for Divi Desktop**!
