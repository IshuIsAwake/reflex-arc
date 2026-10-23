"""Level 2 -- talk to the rover in plain words; a language model turns them into moves.

    python level2.py --rover 10.7.12.41
    python level2.py --rover 127.0.0.1                  against server.py --fake
    python level2.py --rover 127.0.0.1 --model gemma4:e4b

    > go forward two cells, then turn right and go one more
      model: F F R F   "Two forward, a right, one more."
      drive? [Enter = yes, n = no]

Typing moves yourself ("F R L F F") skips the model. /stop, /reset, /quit.

The IoT level: no map, no simulation, no planner. The model hears what you said and
where the rover believes it is, and answers with commands from a fixed alphabet.
Anything outside it is refused before it reaches the wheels.

The model is reached through Ollama's HTTP API with the standard library, as 10d does.
`gemma4:31b-cloud` runs on Ollama's cloud through this machine's sign-in; if it does
not answer, the request goes to the local `gemma4:e4b`.
"""

import argparse
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pi"))
import grid                       # noqa: E402
from link import LinkError, RoverLink  # noqa: E402

OLLAMA = "http://localhost:11434/api/chat"

SYSTEM = """You drive a small six-wheeled rover on a floor marked out in square cells.
It understands exactly these commands, one cell or one quarter turn each:
  F  forward one cell        B  back one cell
  L  turn left 90 degrees    R  turn right 90 degrees  (turns stay in the same cell)
Every command is relative to the way the rover is facing right now.
"Forward two cells" is F F. "Turn around" is R R. "Go back where you started" means
undoing the moves so far, which you can work out from the conversation.

Answer with JSON only:
  {"commands": ["F", "F", "R"], "reply": "one short sentence to the operator"}
Use as few turns as you can: turns are the rover's least accurate move.
If the request is unclear, unsafe or not about driving, send "commands": [] and
ask in "reply". Never invent other commands."""


def ask_model(model, history, text, pose):
    said = {"role": "user", "content": f"The rover is at {pose}. {text}"}
    body = {"model": model, "messages": [{"role": "system", "content": SYSTEM}] + history[-12:] + [said],
            "stream": False, "format": "json", "think": False,
            "options": {"temperature": 0, "seed": 0}, "keep_alive": "30m"}
    req = urllib.request.Request(OLLAMA, json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        content = json.loads(r.read())["message"]["content"]
    data = json.loads(content)
    cmds = grid.parse(" ".join(data.get("commands", [])))
    if any(c not in grid.RELATIVE for c in cmds):
        raise ValueError(f"model used a command it was not given: {' '.join(cmds)}")
    history += [said, {"role": "assistant", "content": content}]   # only once it was usable
    return cmds, data.get("reply", "")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rover", required=True, help="the Pi's address, or 127.0.0.1 for a fake")
    ap.add_argument("--model", default="gemma4:31b-cloud")
    ap.add_argument("--fallback", default="gemma4:e4b")
    ap.add_argument("--yes", action="store_true", help="drive without asking each time")
    args = ap.parse_args()

    rover = RoverLink(args.rover)
    try:
        hi = rover.hello()
    except OSError as e:
        sys.exit(f"cannot reach the rover at {args.rover}:5005 ({e}). Is server.py running?")
    print(f"connected ({'fake' if hi['fake'] else 'REAL'} motors). "
          f"Rover at {hi['pose']}. Type what it should do.\n")
    pose = grid.Pose(hi["pose"]["x"], hi["pose"]["y"],
                     grid.HEADING_NAMES.index(hi["pose"]["heading"]))
    history = []

    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            continue
        if text in ("/quit", "/q"):
            break
        if text == "/stop":
            rover.stop()
            continue
        if text == "/reset":
            p = rover.reset("N")["pose"]
            pose = grid.Pose(p["x"], p["y"], 0)
            print("  reset: this cell is (0,0), facing N")
            continue

        try:
            cmds, reply = grid.parse(text), "(typed directly)"
        except ValueError:
            try:
                cmds, reply = ask_model(args.model, history, text, pose)
            except Exception as e:  # cloud down, rate-limited, bad JSON: try the local one
                print(f"  {args.model} failed ({e}); asking {args.fallback}")
                try:
                    cmds, reply = ask_model(args.fallback, history, text, pose)
                except Exception as e2:
                    print(f"  no usable answer: {e2}")
                    continue
        print(f"  model: {' '.join(cmds) or '(nothing)'}   \"{reply}\"")
        if not cmds:
            continue
        end = pose
        for c in cmds:
            end = grid.apply(end, c)
        print(f"  ends at {end}")
        if not args.yes and input("  drive? [Enter = yes, n = no] ").strip().lower() == "n":
            continue
        try:
            p = rover.drive(cmds, on_step=lambda m: print(f"    {m['i']}. {m['cmd']}  -> {m['pose']}"))
            pose = grid.Pose(p["x"], p["y"], grid.HEADING_NAMES.index(p["heading"]))
        except (LinkError, OSError) as e:
            print(f"  ROVER: {e}")
    rover.stop()
    rover.close()


if __name__ == "__main__":
    main()
