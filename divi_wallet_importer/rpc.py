"""Pure-Python JSON-RPC client for divid daemon."""

import base64
import json
import os
import urllib.request
import urllib.error


class RPCError(Exception):
    """Error returned by the divid JSON-RPC interface."""
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__('RPC error {}: {}'.format(code, message))


class RPCConnectionError(Exception):
    """Cannot connect to divid daemon."""
    pass


class DiviRPC:
    """JSON-RPC client for divid daemon."""

    def __init__(self, host='127.0.0.1', port=51473, user=None, password=None):
        self.url = 'http://{}:{}'.format(host, port)
        self.user = user
        self.password = password
        self._id = 0

    @classmethod
    def from_conf(cls, conf_path=None):
        """Create client by reading rpcuser/rpcpassword from divi.conf.

        If no conf_path given, uses platform default from platform_utils.
        """
        if conf_path is None:
            from divi_wallet_importer.platform_utils import get_divi_conf_path
            conf_path = get_divi_conf_path()

        config = {}
        try:
            with open(conf_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        key, value = line.split('=', 1)
                        config[key.strip()] = value.strip()
        except (OSError, IOError) as e:
            raise RPCConnectionError('Cannot read divi.conf at {}: {}'.format(conf_path, e))

        user = config.get('rpcuser')
        password = config.get('rpcpassword')
        port = int(config.get('rpcport', 51473))

        if not user or not password:
            raise RPCConnectionError(
                'rpcuser/rpcpassword not found in {}'.format(conf_path)
            )

        return cls(host='127.0.0.1', port=port, user=user, password=password)

    def call(self, method, *params, timeout=10):
        """Make a JSON-RPC call. Returns result or raises RPCError/RPCConnectionError."""
        self._id += 1
        payload = json.dumps({
            'jsonrpc': '1.0',
            'id': self._id,
            'method': method,
            'params': list(params),
        }).encode('utf-8')

        auth_str = '{}:{}'.format(self.user or '', self.password or '')
        auth_b64 = base64.b64encode(auth_str.encode('utf-8')).decode('ascii')

        req = urllib.request.Request(
            self.url,
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Basic {}'.format(auth_b64),
            },
        )

        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
            body = json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            # divid returns HTTP 500 for JSON-RPC errors (e.g. "Loading wallet...")
            try:
                body = json.loads(e.read().decode('utf-8'))
            except (json.JSONDecodeError, ValueError):
                raise RPCError(e.code, 'HTTP {}'.format(e.code))
        except urllib.error.URLError as e:
            raise RPCConnectionError('Cannot connect to divid at {}: {}'.format(self.url, e.reason))
        except Exception as e:
            raise RPCConnectionError('RPC request failed: {}'.format(e))

        if body.get('error'):
            err = body['error']
            raise RPCError(err.get('code', -1), err.get('message', str(err)))

        return body.get('result')

    # Convenience methods
    def getinfo(self):
        return self.call('getinfo')

    def getblockchaininfo(self):
        return self.call('getblockchaininfo')

    def getwalletinfo(self):
        return self.call('getwalletinfo')

    def stop(self):
        return self.call('stop')

    def is_responsive(self):
        """Check if daemon is responding to RPC. Returns bool."""
        try:
            self.getinfo()
            return True
        except (RPCError, RPCConnectionError):
            return False
