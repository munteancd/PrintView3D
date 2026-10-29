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
REPLY_TIMEOUT_MS = 3000         # no "ok" in this time: the open window is stuck, open a new one
ACK = b"ok\n"


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


DELIVERED = "delivered"
NO_WINDOW = "no window"         # nothing listens: no PrintView3D is open
NO_REPLY = "no reply"           # something listens but did not answer "ok" in time


def send_to_running(path: str, name: str | None = None) -> bool:
    """Hand the file to a PrintView3D that is already running. True if it took it."""
    return hand_over(path, name) == DELIVERED


def hand_over(path: str, name: str | None = None) -> str:
    """Like send_to_running(), but says what happened: DELIVERED, NO_WINDOW or NO_REPLY."""
    import time

    from PySide6.QtNetwork import QLocalSocket

    sock = QLocalSocket()
    sock.connectToServer(name or server_name())
    if not sock.waitForConnected(CONNECT_TIMEOUT_MS):
        return NO_WINDOW
    if sys.platform == "win32":
        # Windows only lets the program the user is working with bring a window to the front;
        # this start is that program, so allow the running one to come forward.
        try:
            import ctypes
            ctypes.windll.user32.AllowSetForegroundWindow(-1)  # type: ignore[attr-defined]  # ASFW_ANY
        except Exception:  # noqa: BLE001
            pass
    sock.write(encode(path))
    sock.flush()
    # On Windows Qt writes to the pipe in the background; wait until the message has really
    # left. Its answer is not used: it can be False when the pipe took the bytes at once.
    sock.waitForBytesWritten(REPLY_TIMEOUT_MS)
    # Delivered only when the open window answers "ok".
    reply = bytearray()
    deadline = time.monotonic() + REPLY_TIMEOUT_MS / 1000
    while ACK not in reply:
        left = int((deadline - time.monotonic()) * 1000)
        if left <= 0 or not sock.waitForReadyRead(left):
            break
        reply.extend(bytes(sock.readAll()))
    # The window answers and then hangs up; the "ok" can arrive together with the hang-up, when
    # waitForReadyRead() already says False. It is then still waiting here to be read.
    reply.extend(bytes(sock.readAll()))
    sock.abort()
    return DELIVERED if ACK in reply else NO_REPLY


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
        from PySide6.QtCore import QTimer

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
                        sock.write(ACK)            # answer first, so the other start can exit
                        sock.flush()
                        # Load once this connection is done; on_file may open dialogs.
                        QTimer.singleShot(0, lambda p=path: self.on_file(p))
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
