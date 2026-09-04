r"""Train the one-cell policy on the real arena, not the 7x7 box.

`rl_cell.py` teaches FWD / LEFT90 / RIGHT90 / PRESS in a random 7x7 CellEnv.
This file fine-tunes the same net (same QNet, same 8-float obs via
rl_drive.policy_obs) on the real 50x50 world: real boulders, the real button
at (23,23), random walkable spawn and heading every episode. Rewards mirror
CellEnv (+5 press, -0.2 loiter, progress shaping) so only the ground changes.

Run from inside `game/` (same as `main.py`):

    cd prototype3
    python game\\rl_arena.py --eval --episodes 200          # zero-shot transfer check
    python game\\rl_arena.py --train --episodes 3000        # fine-tune from rl_policy.pt
    python game\\rl_arena.py --eval --episodes 200 --load game\\rl_arena.pt

Measured 2026-09-04, and why rl_policy.pt stays the game default: box weights
trek the arena zero-shot at 0.05 press rate, fine-tuning lifts treks to 0.65 --
but the game never asks for treks. nav.goto asks for ONE-cell legs under A*,
and there box weights press 10/10 at ~7 steps while arena weights press 0/10
at ~72 (the 120-step trek episodes teach loopy search that blows the 12-step
leg cap). Train the unit the architecture actually uses: single-cell crossing.
"""

import argparse
import math
import os
import random
import sys
from collections import deque

import numpy as np

try:
    import torch
    import torch.nn as nn
except ImportError:
    print("need torch: py -m pip install torch --index-url https://download.pytorch.org/whl/cpu")
    raise

from world import World
import rl_drive
from rl_cell import QNet

HERE = os.path.dirname(os.path.abspath(__file__))
BOX_POLICY = os.path.join(HERE, "rl_policy.pt")     # 7x7 starting point
ARENA_POLICY = os.path.join(HERE, "rl_arena.pt")    # fine-tuned on the arena

MAX_STEPS = 120  # far corner to the button is ~52 Manhattan; detours cost extra


def make_world(ep):
    """Fresh arena, random walkable spawn (never the button), random heading."""
    random.seed(ep)
    w = World(recorder=None)
    while True:
        x = random.randrange(w.here.w)
        y = random.randrange(w.here.h)
        if w.here.at(x, y) == "." and (x, y) != w.pos and (x, y) not in w.buttons:
            break
    w.pos = (x, y)
    w.heading = random.randrange(4)
    w.herr = random.gauss(0, 3.0)
    w._arrive()
    return w


def button_of(w):
    return next(iter(w.buttons))


def arena_step(w, a):
    """One policy action on the real world. Rewards mirror CellEnv exactly.

    Returns (obs, reward, truncated_or_pressed, pressed)."""
    b = button_of(w)
    pre = math.hypot(b[0] - w.pos[0], b[1] - w.pos[1])
    on = (w.pos == b)
    kind = w.step_action(a)
    now = math.hypot(b[0] - w.pos[0], b[1] - w.pos[1])
    r = -0.02  # every action burns battery/time
    pressed = False
    if on and a != 3:
        r -= 0.2  # standing on the button and not pressing is loitering
    if kind == "turned":
        r -= 0.01
    elif kind == "bump":
        r -= 0.5  # drove at a wall/rock
    elif kind == "moved":
        r += 0.10 if now < pre else -0.05  # dense progress signal
    elif kind == "pressed":
        r += 5.0 - 0.1 * abs(w.herr) / 10.0
        pressed = True
    else:  # noop: pressed thin air
        r -= 0.3
    return rl_drive.policy_obs(w, *b), r, pressed


def train_arena(episodes=3000, init=BOX_POLICY, save=ARENA_POLICY,
                seed=0, log_every=200):
    import torch as _t  # already imported above; kept local for symmetry
    q, qt = QNet(), QNet()
    if init and os.path.exists(init):
        q.load_state_dict(_t.load(init, map_location="cpu"))
        print(f"fine-tuning from {init}")
    else:
        print("training from scratch")
    qt.load_state_dict(q.state_dict())
    opt = _t.optim.Adam(q.parameters(), lr=1e-3)
    loss_fn = nn.SmoothL1Loss()
    buf = deque(maxlen=20000)
    gamma, eps0, eps1 = 0.99, 1.0, 0.05
    decay = max(1, int(episodes * 0.7))
    sync = 0
    wins, rsum, ssum = 0, 0.0, 0

    for ep in range(1, episodes + 1):
        w = make_world(seed * 100000 + ep)
        b = button_of(w)
        obs = rl_drive.policy_obs(w, *b)
        eps = eps1 + (eps0 - eps1) * max(0.0, 1.0 - ep / decay)
        done, eret, pressed_ep, t = False, 0.0, False, 0
        while not done:
            if random.random() < eps:
                a = random.randrange(4)
            else:
                with _t.no_grad():
                    a = int(q(_t.from_numpy(obs).unsqueeze(0)).argmax())
            nobs, r, pressed = arena_step(w, a)
            done = pressed or t + 1 >= MAX_STEPS
            if pressed:
                pressed_ep = True
            buf.append((obs, a, r, nobs, done))
            obs, eret, t = nobs, eret + r, t + 1
            if len(buf) >= 512:
                batch = random.sample(buf, 64)
                o = _t.from_numpy(np.stack([x[0] for x in batch]))
                nb = _t.from_numpy(np.stack([x[3] for x in batch]))
                av = _t.tensor([x[1] for x in batch])
                rv = _t.tensor([x[2] for x in batch], dtype=_t.float32)
                dv = _t.tensor([x[4] for x in batch], dtype=_t.float32)
                with _t.no_grad():
                    tgt = rv + (1 - dv) * gamma * qt(nb).max(1).values
                loss = loss_fn(q(o)[range(64), av], tgt)
                opt.zero_grad()
                loss.backward()
                opt.step()
                sync += 1
                if sync % 200 == 0:
                    qt.load_state_dict(q.state_dict())
        rsum += eret
        ssum += t
        if pressed_ep:
            wins += 1
        if ep % log_every == 0:
            print(f"ep {ep}/{episodes} eps={eps:.2f} "
                  f"winrate[{ep-log_every+1}-{ep}]={wins/log_every:.2f} "
                  f"avg_ret={rsum/log_every:.2f} avg_steps={ssum/log_every:.1f}",
                  flush=True)
            wins, rsum, ssum = 0, 0.0, 0
    _t.save(q.state_dict(), save)
    print(f"saved {save}")
    return save


@torch.no_grad()
def evaluate_arena(path=BOX_POLICY, episodes=200, seed=999):
    if not os.path.exists(path):
        print(f"no policy at {path}")
        return None
    q = QNet()
    q.load_state_dict(torch.load(path, map_location="cpu"))
    q.eval()
    wins, steps, win_steps = 0, [], []
    for i in range(episodes):
        w = make_world(seed * 1000 + i)
        b = button_of(w)
        obs = rl_drive.policy_obs(w, *b)
        pressed, t = False, 0
        while True:
            a = int(q(torch.from_numpy(obs).unsqueeze(0)).argmax())
            obs, _r, pressed = arena_step(w, a)
            t += 1
            if pressed or t >= MAX_STEPS:
                break
        if pressed:
            wins += 1
            win_steps.append(t)
        steps.append(t)
    steps = np.array(steps)
    win_mean = float(np.mean(win_steps)) if win_steps else float("nan")
    print(f"arena eval {episodes} [{os.path.basename(path)}]: "
          f"press_success={wins/episodes:.2f} mean_steps={steps.mean():.1f} "
          f"p90={np.percentile(steps,90):.0f} win_mean_steps={win_mean:.1f}")
    return wins / episodes


def demo_arena(path=BOX_POLICY, ep=7):
    q = QNet()
    q.load_state_dict(torch.load(path, map_location="cpu"))
    q.eval()
    w = make_world(ep)
    b = button_of(w)
    obs = rl_drive.policy_obs(w, *b)
    print(f"start={w.pos} h={w.heading} button={b}")
    for t in range(30):
        a = int(q(torch.from_numpy(obs).unsqueeze(0)).argmax())
        obs, r, pressed = arena_step(w, a)
        print(f"  {t:02d} {rl_drive.NAMES[a]:7s} -> pos={w.pos} h={w.heading} "
              f"herr={w.herr:+.1f} r={r:+.2f}")
        if pressed:
            print("  DONE: pressed")
            return
    print("  DONE: timed out")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", action="store_true")
    ap.add_argument("--eval", action="store_true")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--episodes", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--init", default=BOX_POLICY)
    ap.add_argument("--load", default=BOX_POLICY)
    ap.add_argument("--save", default=ARENA_POLICY)
    args = ap.parse_args()
    if not (args.train or args.eval or args.demo):
        ap.print_help()
        sys.exit(0)
    if args.train:
        train_arena(episodes=args.episodes, init=args.init, save=args.save,
                    seed=args.seed)
    if args.eval:
        evaluate_arena(path=args.load,
                       episodes=args.episodes if args.episodes <= 500 else 200)
    if args.demo:
        demo_arena(path=args.load)
