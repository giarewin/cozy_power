"""CozyLife device control class."""
import socket
import json
import time
import logging
from .const import CMD_QUERY, CMD_SET, CMD_INFO

_LOGGER = logging.getLogger(__name__)

class CozyLifeDevice:
    def __init__(self, ip, port=5555):
        self.ip = ip
        self.port = port
        self._socket = None
        self._connect_timeout = 3
        self._read_timeout = 2
        self._last_connect_attempt = 0
        self._connect_retry_delay = 30

    def _ensure_connection(self):
        current_time = time.time()
        if self._socket:
            return True
        if (current_time - self._last_connect_attempt) < self._connect_retry_delay:
            return False
        self._last_connect_attempt = current_time
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(self._connect_timeout)
            self._socket.connect((self.ip, self.port))
            return True
        except Exception as e:
            _LOGGER.debug(f"Connection failed to {self.ip}: {e}")
            self._close_connection()
            return False

    def _close_connection(self):
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

    def _get_sn(self):
        return str(int(round(time.time() * 1000)))

    def _read_response(self):
        if not self._socket:
            return None
        try:
            self._socket.settimeout(self._read_timeout)
            data = ""
            while True:
                chunk = self._socket.recv(1024).decode("utf-8")
                if not chunk:
                    break
                data += chunk
                if '\n' in data:
                    json_data = data.split('\n')[0].strip()
                    try:
                        return json.loads(json_data)
                    except json.JSONDecodeError:
                        data = data.split('\n', 1)[1] if '\n' in data else ""
                        continue
        except Exception as e:
            _LOGGER.debug(f"Error reading from {self.ip}: {e}")
            self._close_connection()
        return None

    def _send_message(self, command):
        if not self._ensure_connection():
            return None
        try:
            payload = json.dumps(command) + "\r\n"
            self._socket.send(payload.encode("utf-8"))
            return self._read_response()
        except Exception as e:
            _LOGGER.debug(f"Failed to communicate with {self.ip}: {e}")
            self._close_connection()
            return None

    def query_state(self):
        command = {
            "cmd": CMD_QUERY,
            "pv": 0,
            "sn": self._get_sn(),
            "msg": {"attr": [0]},
        }
        response = self._send_message(command)
        if response and response.get("msg"):
            return response["msg"].get("data", {})
        return None
