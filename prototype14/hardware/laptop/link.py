"""The laptop's end of the link to the rover (hardware/pi/server.py). The messages are in
../LINK.md.

    rover = RoverLink("10.7.12.41")          # or "127.0.0.1" with server.py --fake
    rover.hello()
    rover.drive(["N", "N", "E"], on_step=print)

`drive` blocks until the rover has finished, and finishes the whole list even if the wifi
drops: it reconnects and sends again whatever had not been driven. The command that was
moving when the link dropped is driven again in full, since the rover stopped part-way
and can't say how far it got. A stop from any window ends the drive, and nothing is resent."""

import json
import socket
import threading
import time

PORT = 5005
# Drive ids. They start from the clock, so a new run never reuses an old run's ids.
last_id = int(time.time()) % 100000 * 1000


def new_id():
    global last_id
    last_id += 1
    return last_id


class LinkError(Exception):
    pass


class RoverStopped(LinkError):
    """A stop came in mid-drive: from the pad, /stop, or any window. Not retried: a person
    has taken over, and the rest of the list is theirs to finish or drop."""

    def __init__(self, msg):
        self.result = msg["result"]
        self.pose = msg.get("pose")
        note = ""
        if msg.get("note"):
            note = f": {msg['note']}"
        super().__init__(f"{msg['result']} at {self.pose}{note}")


class RoverLink:
    def __init__(self, host, port=PORT, timeout=120, retries=5):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.retries = retries
        self.sock = None
        self.buf = b""
        # Level 3 drives on its worker thread while the game's thread may send a stop.
        self.send_lock = threading.Lock()

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

    def send(self, obj):
        if self.sock is None:
            self.connect()
        with self.send_lock:
            self.sock.sendall((json.dumps(obj) + "\n").encode())

    def receive(self):
        """The next message from the rover."""
        while b"\n" not in self.buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("rover closed the connection")
            self.buf += chunk
        line, self.buf = self.buf.split(b"\n", 1)
        return json.loads(line)

    def ask(self, obj):
        """Send a message and return the rover's answer: the next message with "ok" in it."""
        self.send(obj)
        while True:
            msg = self.receive()
            if "ok" in msg:
                return msg

    def hello(self):
        return self.ask({"op": "hello"})

    def reset(self, heading="N"):
        return self.ask({"op": "reset", "heading": heading})

    def set_pose(self, x, y, heading):
        """Tell the rover which cell it is on, after a person has put it there."""
        return self.ask({"op": "set_pose", "x": x, "y": y, "heading": heading})

    def manual(self, left, right):
        """Wheel power, -1..1 each side. Send it again within 0.4 s or the rover stops."""
        self.send({"op": "manual", "left": round(left, 3), "right": round(right, 3)})

    def stop(self, wait=True):
        """Stop the rover. With `wait`, read its answer too, or the next ask() would read
        this one instead. Level 3 doesn't wait: its worker thread may be reading a drive."""
        try:
            if wait:
                self.ask({"op": "stop"})
            else:
                self.send({"op": "stop"})
        except (OSError, ValueError):
            pass

    def drive(self, cmds, on_step=None):
        """Drive every command in `cmds`. Returns the rover's last pose. Raises RoverStopped
        if a stop ends it part-way, and LinkError if it gives up."""
        todo = list(cmds)
        for attempt in range(self.retries + 1):
            if not todo:
                break
            did = new_id()
            got = 0  # commands the rover has reported done
            try:
                self.send({"op": "drive", "id": did, "cmds": todo})
                while True:
                    msg = self.receive()
                    if msg.get("id") != did:
                        continue
                    if msg.get("event") == "step":
                        got = msg["i"]
                        if on_step:
                            on_step(msg)
                    elif msg.get("event") == "done":
                        if msg["result"] == "DONE":
                            return msg["pose"]
                        if msg["result"] == "STOPPED":
                            raise RoverStopped(msg)
                        raise LinkError(f"rover said {msg['result']}: {msg.get('note', '')}")
            except (OSError, ValueError) as e:
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
