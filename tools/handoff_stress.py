"""TEMPORARY (removed before merging): run the one-window hand-off many times, old vs new code.

python tools/handoff_stress.py [rounds]
"""

import os
import subprocess
import sys
import time
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

OLD = r'''
import sys
from PySide6.QtNetwork import QLocalSocket
from printview3d import single_instance as si
def old_send(path, name):
    sock = QLocalSocket()
    sock.connectToServer(name)
    if not sock.waitForConnected(si.CONNECT_TIMEOUT_MS):
        return "no window"
    sock.write(si.encode(path)); sock.flush()
    reply = bytearray()
    while si.ACK not in reply and sock.waitForReadyRead(si.REPLY_TIMEOUT_MS):
        reply.extend(bytes(sock.readAll()))
    sock.abort()
    return "delivered" if si.ACK in reply else "no reply"
'''

VARIANTS = {
    "old code, no Qt app (the old test)": OLD + "r = old_send(sys.argv[1], sys.argv[2])\n",
    "old code, with Qt app (the real app before)": OLD + "from PySide6.QtCore import QCoreApplication\n"
        "app = QCoreApplication([])\nr = old_send(sys.argv[1], sys.argv[2])\n",
    "new code, no Qt app": "import sys\nfrom printview3d import single_instance as si\n"
        "r = si.hand_over(sys.argv[1], name=sys.argv[2])\n",
    "new code, with Qt app (new test and the app)": "import sys\nfrom PySide6.QtCore import QCoreApplication\n"
        "from printview3d import single_instance as si\napp = QCoreApplication([])\n"
        "r = si.hand_over(sys.argv[1], name=sys.argv[2])\n",
}
TAIL = "print(r)\n"


def main():
    from PySide6.QtCore import QCoreApplication
    from printview3d import single_instance as si

    app = QCoreApplication.instance() or QCoreApplication([])
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"), QT_QPA_PLATFORM="offscreen")
    bad = 0
    for label, code in VARIANTS.items():
        results, arrived_missing = {}, 0
        for i in range(rounds):
            name = "PV3D-stress-" + uuid.uuid4().hex[:8]
            got = []
            server = si.FileServer(got.append, name=name)
            assert server.listen()
            p = subprocess.Popen([sys.executable, "-c", code + TAIL, f"C:/x/{i}.stl", name],
                                 env=env, stdout=subprocess.PIPE, text=True)
            end = time.monotonic() + 15
            while (p.poll() is None or not got) and time.monotonic() < end:
                app.processEvents()
                time.sleep(0.005)
            out = (p.communicate(timeout=10)[0] or "?").strip()
            for _ in range(20):
                app.processEvents()
            key = out + ("" if got else " (file never arrived)")
            results[key] = results.get(key, 0) + 1
            server.close()
        ok = results.get("delivered", 0)
        print(f"::notice title={label}::{ok}/{rounds} delivered; {results}")
        if label.startswith("new") and "with Qt app" in label and ok != rounds:
            bad = 1
    sys.exit(bad)


if __name__ == "__main__":
    main()
