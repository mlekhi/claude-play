import socket
import json
import subprocess
import os
import time


class MpvController:
    SOCKET_PATH = "/tmp/claude-piece-mpv.sock"

    def __init__(self):
        self.sock = None
        self.process = None
        self._buf = b""

    def launch(self, filepath):
        """Launch mpv with IPC enabled, playing the given file."""
        if self.process and self.process.poll() is None:
            return  # already running

        # Clean up stale socket
        if os.path.exists(self.SOCKET_PATH):
            os.unlink(self.SOCKET_PATH)

        self.process = subprocess.Popen([
            "mpv",
            f"--input-ipc-server={self.SOCKET_PATH}",
            "--no-terminal",
            "--force-window=yes",
            "--keep-open=yes",
            "--pause",
            filepath,
        ])

        # Wait for socket to appear
        for _ in range(50):
            if os.path.exists(self.SOCKET_PATH):
                break
            time.sleep(0.1)

        self._connect()

    def _connect(self):
        """Connect to the mpv IPC socket."""
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.SOCKET_PATH)
        self.sock.settimeout(1.0)
        self._buf = b""

    def _send(self, command):
        """Send a command to mpv and return the response."""
        if not self.sock:
            return None
        payload = json.dumps({"command": command}) + "\n"
        try:
            self.sock.sendall(payload.encode("utf-8"))
            return self._read_response()
        except (BrokenPipeError, ConnectionError, OSError):
            return None

    def _read_response(self):
        """Read a command response, skipping event messages."""
        while True:
            if b"\n" in self._buf:
                line, self._buf = self._buf.split(b"\n", 1)
                try:
                    msg = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    continue
                if "event" not in msg and "error" in msg:
                    return msg
                continue
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                return None
            if not chunk:
                return None
            self._buf += chunk

    def pause(self):
        self._send(["set_property", "pause", True])

    def resume(self):
        self._send(["set_property", "pause", False])

    def get_position(self):
        resp = self._send(["get_property", "playback-time"])
        if resp and resp.get("error") == "success":
            return resp.get("data", 0)
        return 0

    def seek(self, position):
        self._send(["seek", position, "absolute"])

    def load_file(self, filepath):
        self._send(["loadfile", filepath, "replace"])

    def is_eof(self):
        resp = self._send(["get_property", "eof-reached"])
        if resp and resp.get("error") == "success":
            return resp.get("data", False)
        return False

    def is_running(self):
        return self.process is not None and self.process.poll() is None

    def minimize(self):
        subprocess.run([
            "osascript", "-e",
            'tell application "System Events" to tell process "mpv" '
            'to set value of attribute "AXMinimized" of every window to true'
        ], capture_output=True)

    def unminimize(self):
        subprocess.run([
            "osascript", "-e",
            'tell application "System Events" to tell process "mpv" '
            'to set value of attribute "AXMinimized" of every window to false'
        ], capture_output=True)

    def quit(self):
        self._send(["quit"])
        if self.process:
            self.process.wait(timeout=5)
        if self.sock:
            self.sock.close()
            self.sock = None
