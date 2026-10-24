"""One window: a file opened while PrintView3D is already running goes to that window.

The first PrintView3D started listens on a local socket (a named pipe on Windows, a socket file
on Linux and macOS), one per user. A later start with a file first tries to hand the file to it;
when that works it exits at once, so a double-click shows the file in the window that is already
open. Settings -> Files -> "Open each file in a new window" turns this off.

Starting PrintView3D without a file always opens a new window (to compare two models side by
side). macOS hands files to the running app by itself (FileOpen events), so nothing changes there.
"""

from __future__ import annotations

import getpass
import json
import os
import re
import sys

CONNECT_TIMEOUT_MS = 500
SEND_TIMEOUT_MS = 1000


def server_name() -> str:
    """One name per user, so two people signed in on one PC each get their own window."""
    try:
        user = getpass.getuser()
    except Exception:  # noqa: BLE001 - no user name: share one name
        user = "user"
    return "PrintView3D-" + (re.sub(r"[^A-Za-z0-9_.-]", "_", user) or "user")


def encode(path: str) -> bytes:
    """The message a second start sends: one line of JSON."""
    return (json.dumps({"file": os.path.abspath(path)}) + "\n").encode("utf-8")


def decode(data: bytes) -> str:
    """The file in a message from encode(), or "" if it is not one."""
    try:
        msg = json.loads(data.decode("utf-8").strip() or "{}")
    except (UnicodeDecodeError, ValueError):
        return ""
    path = msg.get("file") if isinstance(msg, dict) else None
    return path if isinstance(path, str) else ""


def send_to_running(path: str, name: str | None = None) -> bool:
    """Hand the file to a PrintView3D that is already running. True if it took it."""
    from PySide6.QtNetwork import QLocalSocket

    sock = QLocalSocket()
    sock.connectToServer(name or server_name())
    if not sock.waitForConnected(CONNECT_TIMEOUT_MS):
        return False
    if sys.platform == "win32":
        # Windows only lets the program the user is working with bring a window to the front;
        # this start is that program, so allow the running one to come forward.
        try:
            import ctypes
            ctypes.windll.user32.AllowSetForegroundWindow(-1)  # type: ignore[attr-defined]  # ASFW_ANY
        except Exception:  # noqa: BLE001
            pass
    sock.write(encode(path))
    ok = sock.waitForBytesWritten(SEND_TIMEOUT_MS)
    sock.disconnectFromServer()
    if sock.state() != QLocalSocket.UnconnectedState:
        sock.waitForDisconnected(SEND_TIMEOUT_MS)
    return ok


class FileServer:
    """Listens for files from later starts and calls on_file(path) for each one."""

    def __init__(self, on_file, name: str | None = None, parent=None):
        from PySide6.QtNetwork import QLocalServer

        self.name = name or server_name()
        self.on_file = on_file
        self.server = QLocalServer(parent)
        self.server.setSocketOptions(QLocalServer.UserAccessOption)   # only this user can send
        self.server.newConnection.connect(self._accept)

    def listen(self) -> bool:
        """Start listening. False if another PrintView3D already listens (then nothing changes)."""
        from PySide6.QtNetwork import QLocalServer

        if self.server.isListening():
            return True
        # Ask first: with UserAccessOption, Qt on Linux/macOS replaces an existing socket file
        # without complaint, which would take the name from a window that is still open.
        if send_probe(self.name):
            return False
        # Nobody answers. On Linux/macOS a socket file may be left behind by a PrintView3D that
        # crashed; remove it. (On Windows a pipe goes away with its program; this does nothing.)
        QLocalServer.removeServer(self.name)
        return self.server.listen(self.name)

    def close(self):
        self.server.close()

    def _accept(self):
        while self.server.hasPendingConnections():
            sock = self.server.nextPendingConnection()
            buf = bytearray()

            def read(sock=sock, buf=buf):
                buf.extend(bytes(sock.readAll()))
                if b"\n" in buf:
                    line, _, _rest = bytes(buf).partition(b"\n")
                    buf.clear()
                    path = decode(line)
                    if path:
                        self.on_file(path)
                    sock.disconnectFromServer()

            sock.readyRead.connect(read)
            sock.disconnected.connect(sock.deleteLater)
            if sock.bytesAvailable():
                read()


def send_probe(name: str) -> bool:
    """True if something answers on the name (a live PrintView3D)."""
    from PySide6.QtNetwork import QLocalSocket

    sock = QLocalSocket()
    sock.connectToServer(name)
    alive = sock.waitForConnected(CONNECT_TIMEOUT_MS)
    if alive:
        sock.disconnectFromServer()
    return alive
