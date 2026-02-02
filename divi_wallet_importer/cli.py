"""Command-line entry point for Divi Wallet Importer."""

import argparse


def main():
    parser = argparse.ArgumentParser(
        description="Divi Wallet Importer for Divi Desktop Application"
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run in terminal-only mode (no browser GUI)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Port for the web server (default: auto-select)",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Don't auto-open the browser",
    )
    args = parser.parse_args()

    if args.cli:
        from divi_wallet_importer.cli_mode import run_cli
        run_cli()
    else:
        from divi_wallet_importer.server import run_server
        run_server(port=args.port, no_open=args.no_open)
