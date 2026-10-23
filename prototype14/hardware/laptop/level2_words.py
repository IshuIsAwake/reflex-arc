"""Level 2: tell the rover what to do in plain words; a language model turns them into
moves. No map, no simulation. Double-click to run, or:

    python level2_words.py                       finds the Pi by hardware/rover_address.txt
    python level2_words.py --rover 127.0.0.1     against server.py --fake

    > go forward two cells, then turn right and go one more
      model: F F R F   "Two forward, a right, one more."
      drive? [Enter = yes, n = no]

Typing the moves yourself ("F R L F F") skips the model. /stop, /reset, /quit.
The model may only answer with F B L R; anything else is refused before the wheels. It is
reached through Ollama; if the cloud model doesn't answer, the local gemma4:e4b does.
"""

import argparse
import json
import os
import sys
import urllib.request

import launch
from link import LinkError, RoverLink, RoverStopped

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pi"))
import grid  # noqa: E402  the Pi's grid, for the commands and the pose

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
    """The model's moves for `text`, as (commands, reply). Raises if it can't give usable ones."""
    said = {"role": "user", "content": f"The rover is at {pose}. {text}"}
    messages = [{"role": "system", "content": SYSTEM}] + history[-12:] + [said]
    body = {"model": model, "messages": messages, "stream": False, "format": "json",
            "think": False, "options": {"temperature": 0, "seed": 0}, "keep_alive": "30m"}
    req = urllib.request.Request(OLLAMA, json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        content = json.loads(r.read())["message"]["content"]
    data = json.loads(content)
    cmds = grid.parse(" ".join(data.get("commands", [])))
    for c in cmds:
        if c not in grid.RELATIVE:
            raise ValueError(f"model used a command it was not given: {' '.join(cmds)}")
    history += [said, {"role": "assistant", "content": content}]  # only once it was usable
    return cmds, data.get("reply", "")


def moves_for(args, history, text, pose):
    """(commands, reply) for a line typed at the prompt, or None if there are none."""
    try:
        return grid.parse(text), "(typed directly)"
    except ValueError:
        pass
    try:
        return ask_model(args.model, history, text, pose)
    except Exception as e:  # cloud down, rate-limited, bad JSON: try the local one
        print(f"  {args.model} failed ({e}); asking {args.fallback}")
    try:
        return ask_model(args.fallback, history, text, pose)
    except Exception as e:
        print(f"  no usable answer: {e}")
        return None


def show_step(m):
    print(f"    {m['i']}. {m['cmd']}  -> {m['pose']}")


def main():
    ap = argparse.ArgumentParser(description="Level 2: plain words drive the rover")
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
    motors = "fake" if hi["fake"] else "REAL"
    print(f"connected ({motors} motors). Rover at {hi['pose']}. Type what it should do.\n")
    pose = grid.from_json(hi["pose"])
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
            pose = grid.from_json(rover.reset("N")["pose"])
            print("  reset: this cell is (0,0), facing N")
            continue

        answer = moves_for(args, history, text, pose)
        if answer is None:
            continue
        cmds, reply = answer
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
            pose = grid.from_json(rover.drive(cmds, on_step=show_step))
        except RoverStopped as e:  # stopped part-way: carry on from where it stopped
            print(f"  ROVER: {e}")
            pose = grid.from_json(e.pose)
        except (LinkError, OSError) as e:
            print(f"  ROVER: {e}")
    rover.stop()
    rover.close()


if __name__ == "__main__":
    launch.run(main)
