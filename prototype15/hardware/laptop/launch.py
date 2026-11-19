"""What the three level programs share: finding the rover, and keeping a double-clicked
window open long enough to read an error.

run(main) adds `--rover <address>` unless one was given, from the name in
hardware/rover_address.txt (rpi5.local unless changed), looked up as an IPv4 address
since the rover server listens on IPv4. On a failure it prints why and waits for Enter."""

import os
import socket
import sys
import traceback

HARDWARE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDRESS_FILE = os.path.join(HARDWARE, "rover_address.txt")


def rover_name():
    """The first line of rover_address.txt that is not a comment."""
    if os.path.exists(ADDRESS_FILE):
        with open(ADDRESS_FILE, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#"):
                    return line
    return "rpi5.local"


def rover_ip(name):
    try:
        return socket.gethostbyname(name)
    except OSError:
        raise SystemExit(f"cannot find the rover by the name {name!r}.\n"
                         f"Is the Pi on and on the same hotspot? If its name or IP is "
                         f"different, put it in {ADDRESS_FILE}")


def run(main):
    """Run a program's main() with the rover's address filled in."""
    try:
        if "--rover" not in sys.argv:
            name = rover_name()
            ip = rover_ip(name)
            print(f"rover: {name} -> {ip}")
            sys.argv[1:1] = ["--rover", ip]
        main()
    except SystemExit as e:
        if e.code in (None, 0):
            return
        if not isinstance(e.code, int):
            print(e.code)
        _hold()
    except KeyboardInterrupt:
        pass
    except Exception:
        traceback.print_exc()
        _hold()


def _hold():
    try:
        input("\nPress Enter to close.")
    except EOFError:
        pass
