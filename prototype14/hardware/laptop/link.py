"""link -- the laptop's end of the connection to hardware/pi/server.py.

    rover = RoverLink("10.7.12.41")          # or "127.0.0.1" with server.py --fake
    rover.hello()
    rover.drive(["N", "N", "E"], on_step=print)

`drive` blocks until the rover has finished, and it finishes the whole list even if
the wifi drops: it reconnects, asks again under the same id (the rover answers a
finished id from memory, so nothing drives twice), and sends whatever had not been
driven yet. The command that was moving when the link dropped is driven again in
full, because the rover stopped part-way through it and cannot say how far it got.
A stop from any window is the exception: it ends the drive, and nothing is resent.
"""

import itertools
import json
import socket
import threading
import time

PORT = 5005
_ids = itertools.count(int(time.time()) % 100000 * 1000)


class LinkError(Exception):
    pass


class RoverStopped(LinkError):
    """A stop came in mid-drive -- the pad, /stop, any window. Not retried: a person has
    taken over, and the rest of the list is theirs to finish or drop."""

    def __init__(self, msg):
        self.result, self.pose = msg["result"], msg.get("pose")
        note = f": {msg['note']}" if msg.get("note") else ""
        super().__init__(f"{msg['result']} at {self.pose}{note}")


class RoverLink:
    def __init__(self, host, port=PORT, timeout=120, retries=5):
        self.host, self.port = host, port
        self.timeout, self.retries = timeout, retries
        self.sock = None
        self.buf = b""
        self._send_lock = threading.Lock()

    # --- the connection ----------------------------------------------------
    def connect(self):
        self.close()
        self.sock = socket.create_connection((self.host, self.port), timeout=5)
        self.sock.settimeout(self.timeout)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.buf = b""

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None

    def _send(self, obj):
        if self.sock is None:
            self.connect()
        with self._send_lock:            # whole lines only, if two threads ever share a link
            self.sock.sendall((json.dumps(obj) + "\n").encode())

    def _recv(self):
        while b"\n" not in self.buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("rover closed the connection")
            self.buf += chunk
        line, self.buf = self.buf.split(b"\n", 1)
        return json.loads(line)

    def _ask(self, obj):
        self._send(obj)
        while True:
            msg = self._recv()
            if "ok" in msg:
                return msg

    # --- what the rover can be asked ----------------------------------------
    def hello(self):
        return self._ask({"op": "hello"})

    def reset(self, heading="N"):
        return self._ask({"op": "reset", "heading": heading})

    def set_pose(self, x, y, heading):
        """Tell the rover which cell it is on, after a person has put it there."""
        return self._ask({"op": "set_pose", "x": x, "y": y, "heading": heading})

    def manual(self, left, right):
        """Wheel power, -1..1 each side. Send it again within 0.4 s or the rover stops."""
        self._send({"op": "manual", "left": round(left, 3), "right": round(right, 3)})

    def stop(self):
        try:
            self._send({"op": "stop"})
        except OSError:
            pass

    def drive(self, cmds, on_step=None):
        """Drive every command in `cmds`. Returns the rover's last pose. Raises
        RoverStopped if a stop ends it part-way."""
        todo = list(cmds)
        for attempt in range(self.retries + 1):
            if not todo:
                break
            did = next(_ids)
            got = 0
            try:
                self._send({"op": "drive", "id": did, "cmds": todo})
                while True:
                    msg = self._recv()
                    if msg.get("id") != did:
                        continue
                    if msg.get("event") == "step":
                        got = msg["i"]
                        on_step and on_step(msg)
                    elif msg.get("event") == "done":
                        if msg["result"] == "DONE":
                            return msg["pose"]
                        if msg["result"] == "STOPPED":
                            raise RoverStopped(msg)
                        raise LinkError(f"rover said {msg['result']}: {msg.get('note', '')}")
            except (OSError, ConnectionError, ValueError) as e:
                todo = todo[got:]
                print(f"  link dropped ({e}); {len(todo)} command(s) left, reconnecting...")
                time.sleep(min(2 * (attempt + 1), 8))
                try:
                    self.connect()
                except OSError:
                    continue
        if todo:
            raise LinkError(f"gave up with {len(todo)} command(s) not driven: {' '.join(todo)}")
        return self.hello()["pose"]
