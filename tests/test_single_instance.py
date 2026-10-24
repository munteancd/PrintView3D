"""One window: a second start hands its file to the PrintView3D already open; restart command."""

import os
import sys
import time
import uuid

import pytest

from printview3d import restart, single_instance as si


def test_message_round_trip(tmp_path):
    path = str(tmp_path / "part one.stl")
    assert si.decode(si.encode(path)) == os.path.abspath(path)


@pytest.mark.parametrize("data", [b"", b"not json\n", b'["a"]\n', b'{"file": 3}\n', b"\xff\xfe\n"])
def test_decode_ignores_garbage(data):
    assert si.decode(data) == ""


def test_server_name_is_safe():
    name = si.server_name()
    assert name.startswith("PrintView3D-")
    assert all(c.isalnum() or c in "_.-" for c in name)


@pytest.fixture
def qapp():
    from PySide6.QtCore import QCoreApplication
    return QCoreApplication.instance() or QCoreApplication([])


def _wait(app, cond, seconds=3.0):
    end = time.monotonic() + seconds
    while not cond() and time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def test_second_start_hands_file_to_first(qapp, tmp_path):
    name = "PrintView3D-test-" + uuid.uuid4().hex[:8]
    got = []
    server = si.FileServer(got.append, name=name)
    assert server.listen()
    try:
        path = str(tmp_path / "cube.3mf")
        assert si.send_to_running(path, name=name)
        _wait(qapp, lambda: got)
        assert got == [os.path.abspath(path)]
        # Only one window may listen: a second server does not take the name over.
        other = si.FileServer(lambda p: None, name=name)
        assert not other.listen()
    finally:
        server.close()


def test_nobody_running(qapp, tmp_path):
    name = "PrintView3D-test-" + uuid.uuid4().hex[:8]
    assert not si.send_to_running(str(tmp_path / "a.stl"), name=name)


@pytest.mark.skipif(sys.platform == "win32", reason="Windows pipes go away with their program")
def test_stale_socket_file_is_replaced(qapp):
    """A PrintView3D that crashed leaves its socket file behind; the next one still listens."""
    from PySide6.QtNetwork import QLocalServer
    name = "PrintView3D-test-" + uuid.uuid4().hex[:8]
    crashed = QLocalServer()
    assert crashed.listen(name)
    sock_file = crashed.fullServerName()
    crashed.close()
    open(sock_file, "w").close()                    # what a crash leaves: the file, nobody listening
    try:
        server = si.FileServer(lambda p: None, name=name)
        assert server.listen()
        server.close()
    finally:
        QLocalServer.removeServer(name)


def test_restart_command_from_source(tmp_path):
    prog, args = restart.command(str(tmp_path / "m.stl"), frozen=False, environ={})
    assert prog == sys.executable
    assert args == ["-m", "printview3d", os.path.abspath(str(tmp_path / "m.stl")), "--new-window"]


def test_restart_command_installed_without_file():
    prog, args = restart.command(None, frozen=True, environ={})
    assert prog == sys.executable and args == ["--new-window"]


def test_restart_command_appimage():
    prog, args = restart.command(None, frozen=True, environ={"APPIMAGE": "/home/u/PrintView3D.AppImage"})
    assert prog == "/home/u/PrintView3D.AppImage"
