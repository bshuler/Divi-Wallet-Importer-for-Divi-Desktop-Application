"""Local HTTP server with JSON API for the Divi Wallet Importer."""

import json
import os
import secrets
import socket
import sys
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler

from divi_wallet_importer import api


_session_token = None
_server_instance = None


def _find_free_port():
    """Find a free port by binding to port 0."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _load_index_html(port, token):
    """Load index.html from package and inject API_BASE and TOKEN."""
    if getattr(sys, 'frozen', False):
        # Running inside a PyInstaller bundle
        base = sys._MEIPASS
        path = os.path.join(base, 'divi_wallet_importer', 'web', 'index.html')
        with open(path, 'r', encoding='utf-8') as f:
            html = f.read()
    elif sys.version_info >= (3, 9):
        from importlib.resources import files
        html = files("divi_wallet_importer.web").joinpath("index.html").read_text(encoding="utf-8")
    else:
        import importlib.resources as pkg_resources
        html = pkg_resources.read_text("divi_wallet_importer.web", "index.html", encoding="utf-8")

    html = html.replace("{{API_BASE}}", "http://127.0.0.1:{}".format(port))
    html = html.replace("{{SESSION_TOKEN}}", token)
    return html


class _RequestHandler(BaseHTTPRequestHandler):
    """Handle HTTP requests for the wallet importer."""

    _cached_html = None

    def log_message(self, format, *args):
        """Suppress default access logs."""
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "null")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _check_token(self):
        token = self.headers.get("X-Session-Token", "")
        if token != _session_token:
            self._send_json({"error": "Unauthorized"}, 403)
            return False
        return True

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "null")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Session-Token")
        self.end_headers()

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            if _RequestHandler._cached_html is None:
                return self._send_json({"error": "Not ready"}, 503)
            self._send_html(_RequestHandler._cached_html)
            return

        if not self._check_token():
            return

        if self.path == "/api/platform":
            self._send_json(api.get_platform_info())
        elif self.path == "/api/prerequisites":
            self._send_json(api.check_prerequisites())
        elif self.path == "/api/wallet/check":
            self._send_json(api.check_wallet())
        elif self.path == "/api/recovery/status":
            self._send_json(api.get_recovery_status())
        elif self.path == "/api/recovery/check":
            self._send_json(api.check_recovery_in_progress())
        elif self.path == "/api/desktop/check":
            self._send_json(api.check_desktop_running())
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        # Allow shutdown and beacon without full CORS
        if self.path == "/api/shutdown":
            if not self._check_token():
                return
            self._send_json({"success": True, "message": "Shutting down."})
            threading.Thread(target=self._shutdown_server, daemon=True).start()
            return

        if not self._check_token():
            return

        if self.path == "/api/desktop/stop":
            self._send_json(api.stop_desktop())
            return

        if self.path == "/api/daemon/stop":
            self._send_json(api.stop_daemon())
            return

        if self.path == "/api/recovery/resume":
            self._send_json(api.resume_monitoring())
            return

        if self.path == "/api/recovery/clear":
            self._send_json(api.clear_recovery())
            return

        if self.path == "/api/wallet/backup":
            self._send_json(api.backup_wallet())
        elif self.path == "/api/recovery/start":
            body = self._read_body()
            mnemonic = body.get("mnemonic", "")
            if not mnemonic:
                self._send_json({"success": False, "message": "No mnemonic provided."}, 400)
                return
            result = api.start_recovery(mnemonic)
            self._send_json(result)
        elif self.path == "/api/launch-desktop":
            self._send_json(api.launch_desktop())
        else:
            self._send_json({"error": "Not found"}, 404)

    @staticmethod
    def _shutdown_server():
        """Shutdown the server from a background thread."""
        import time
        time.sleep(0.5)
        if _server_instance:
            _server_instance.shutdown()


def run_server(port=0, no_open=False):
    """Start the HTTP server and optionally open a browser."""
    global _session_token, _server_instance

    _session_token = secrets.token_urlsafe(32)

    if port == 0:
        port = _find_free_port()

    _RequestHandler._cached_html = _load_index_html(port, _session_token)

    server = HTTPServer(("127.0.0.1", port), _RequestHandler)
    _server_instance = server

    url = "http://127.0.0.1:{}".format(port)
    print("Divi Wallet Importer running at {}".format(url))
    print("Press Ctrl+C to stop.")

    if not no_open:
        # Open browser after a short delay to let server start
        def open_browser():
            import time
            time.sleep(0.3)
            webbrowser.open(url)
        threading.Thread(target=open_browser, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("\nServer stopped.")
