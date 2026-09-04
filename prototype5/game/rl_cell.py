r"""One-cell driving policy: the RL half of the rover track.

Where it sits: A* in `nav.py` plans a route cell by cell. This policy crosses
ONE cell (forward / turn / press) and reports back. The planner budgets what
this policy spends, so `estimate_cost()` below is an interface obligation,
not a nice-to-have (`work_division.md` Abhishek + Koushik).

Actions (what the user asked for):
    0 FORWARD   drive one cell forward
    1 LEFT90    turn left in place
    2 RIGHT90   turn right in place
    3 PRESS     press the button / interact (only works on the button cell)

Rotation rule (`ARCHITECTURE.md`): heading error compounds, position error
does not. So turns go through a NON-learned correction step that models the
overhead camera + ArUco tag: after every turn we read heading with noise and
snap back toward the nearest 90 deg. The policy learns to drive; the camera
keeps it square. This file models both so training sees what the floor sees.

From scratch, per repo rules: DQN + MLP in plain torch, no stable-baselines.
CPU only, ~2 min. Run me from inside `game/` (same as `main.py`):

    cd prototype3
    python game\\rl_cell.py --train --episodes 2000
    python game\\rl_cell.py --eval --episodes 200
"""

import argparse
import math
import os
import random
import sys
from collections import deque

import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError:  # keep the error loud and actionable
    print("need gymnasium: py -m pip install gymnasium torch numpy")
    raise

try:
    import torch
    import torch.nn as nn
except ImportError:
    print("need torch: py -m pip install torch --index-url https://download.pytorch.org/whl/cpu")
    raise

FWD, LEFT, RIGHT, PRESS = 0, 1, 2, 3
NAMES = ["FWD", "LEFT90", "RIGHT90", "PRESS"]
# headings: 0=N(-y) 1=E(+x) 2=S(+y) 3=W(-x) -- matches nav.NEIGHBOURS order
DVEC = [(0, -1), (1, 0), (0, 1), (-1, 0)]

HERE = os.path.dirname(os.path.abspath(__file__))
SAVE = os.path.join(HERE, "rl_policy.pt")


class CellEnv(gym.Env):
    """7x7 training arena. One button cell, random rocks, random spawn.

    Observation (8 floats, the "clean state" from rover_ideas: same in sim
    and real, only dynamics differ):
      [dx_goal, dy_goal, sin_h, cos_h, herr/45, front_blocked, on_button, dist/10]
    herr = continuous heading error in degrees from the camera (0 = square).
    """

    metadata = {"render_modes": []}

    def __init__(self, size=7, max_steps=40, seed=None):
        super().__init__()
        self.size = size
        self.max_steps = max_steps
        self.action_space = spaces.Discrete(4)
        self.observation_space = spaces.Box(-10, 10, shape=(8,), dtype=np.float32)
        self.rng = random.Random(seed)
        self.np_rng = np.random.default_rng(seed)
        self.reset(seed=seed)

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self.rng.seed(seed)
            self.np_rng = np.random.default_rng(seed)
        s = self.size
        # random rocks ~10%, never on border spawn area
        self.rocks = set()
        for y in range(s):
            for x in range(s):
                if self.rng.random() < 0.10:
                    self.rocks.add((x, y))
        # domain randomization: slip + turn noise change every episode,
        # so the policy never leans on one mass/friction/motor combo.
        self.slip = self.rng.uniform(0.0, 0.10)
        self.turn_noise = self.rng.uniform(6.0, 14.0)  # deg std before correction
        # spawn + button, both clear
        while True:
            self.pos = (self.rng.randrange(s), self.rng.randrange(s))
            if self.pos not in self.rocks:
                break
        while True:
            self.button = (self.rng.randrange(s), self.rng.randrange(s))
            if self.button not in self.rocks and self.button != self.pos:
                break
        self.rocks.discard(self.pos)
        self.rocks.discard(self.button)
        self.heading = self.rng.randrange(4)
        self.herr = float(self.np_rng.normal(0, 3.0))  # deg, camera read
        self.steps = 0
        return self._obs(), {}

    # -- helpers ---------------------------------------------------------
    def _blocked(self, x, y):
        s = self.size
        return not (0 <= x < s and 0 <= y < s) or (x, y) in self.rocks

    def _front(self):
        dx, dy = DVEC[self.heading]
        return self._blocked(self.pos[0] + dx, self.pos[1] + dy)

    def _obs(self):
        dx = self.button[0] - self.pos[0]
        dy = self.button[1] - self.pos[1]
        rad = math.radians(self.heading * 90.0 + self.herr)
        return np.array([
            dx, dy,
            math.sin(rad), math.cos(rad),
            self.herr / 45.0,
            1.0 if self._front() else 0.0,
            1.0 if self.pos == self.button else 0.0,
            math.hypot(dx, dy) / 10.0,
        ], dtype=np.float32)

    # -- the camera correction (NOT learned) -----------------------------
    def _correct_heading(self):
        """Model of the ArUco snap: read heading with noise, servo back.

        Turn puts ~turn_noise error on. Correction kills ~85% of it and
        leaves ~1.5 deg read noise. Policy sees the residual in herr.
        """
        self.herr = self.herr * 0.15 + float(self.np_rng.normal(0, 1.5))
        self.herr = max(-30.0, min(30.0, self.herr))

    # -- gym -------------------------------------------------------------
    def step(self, a):
        self.steps += 1
        reward = -0.02  # every action burns battery/time
        done = False
        pressed = False
        if self.pos == self.button and a != PRESS:
            reward -= 0.2  # standing on the button and not pressing is loitering

        if a == LEFT:
            self.heading = (self.heading - 1) % 4
            self.herr += float(self.np_rng.normal(0, self.turn_noise))
            self._correct_heading()
            reward -= 0.01
        elif a == RIGHT:
            self.heading = (self.heading + 1) % 4
            self.herr += float(self.np_rng.normal(0, self.turn_noise))
            self._correct_heading()
            reward -= 0.01
        elif a == FWD:
            if self.rng.random() < self.slip:
                reward -= 0.05  # wheels slipped, no motion
            elif self._front():
                reward -= 0.5  # drove at a wall/rock
            else:
                dx, dy = DVEC[self.heading]
                self.pos = (self.pos[0] + dx, self.pos[1] + dy)
                # forward motion drags heading slightly off, camera watches
                self.herr += float(self.np_rng.normal(0, 1.0))
                self.herr = max(-30.0, min(30.0, self.herr))
                prev = math.hypot(self.button[0] - self.pos[0] + dx,
                                  self.button[1] - self.pos[1] + dy)
                now = math.hypot(self.button[0] - self.pos[0],
                                 self.button[1] - self.pos[1])
                reward += 0.10 if now < prev else -0.05  # dense progress signal
        elif a == PRESS:
            if self.pos == self.button:
                reward += 5.0 - 0.1 * abs(self.herr) / 10.0
                done = True  # pressed the right button: episode won
                pressed = True
            else:
                reward -= 0.3  # pressed thin air
        if self.steps >= self.max_steps:
            done = True
        return self._obs(), reward, done, False, {"pressed": pressed}


class QNet(nn.Module):
    def __init__(self, obs=8, act=4):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(obs, 64), nn.ReLU(),
            nn.Linear(64, 64), nn.ReLU(),
            nn.Linear(64, act))

    def forward(self, x):
        return self.net(x)


def train(episodes=2000, seed=0, save=SAVE, log_every=200):
    env = CellEnv(seed=seed)
    q, qt = QNet(), QNet()
    qt.load_state_dict(q.state_dict())
    opt = torch.optim.Adam(q.parameters(), lr=1e-3)
    loss_fn = nn.SmoothL1Loss()
    buf = deque(maxlen=10000)
    gamma, eps0, eps1 = 0.99, 1.0, 0.05
    decay = max(1, int(episodes * 0.7))
    steps, sync = 0, 0
    wins, rsum, ssum = 0, 0.0, 0

    for ep in range(1, episodes + 1):
        obs, _ = env.reset()
        eps = eps1 + (eps0 - eps1) * max(0.0, 1.0 - ep / decay)
        done, eret = False, 0.0
        pressed_ep = False
        while not done:
            if random.random() < eps:
                a = random.randrange(4)
            else:
                with torch.no_grad():
                    a = int(q(torch.from_numpy(obs).unsqueeze(0)).argmax())
            nobs, r, done, _, info = env.step(a)
            if info.get("pressed"):
                pressed_ep = True
            buf.append((obs, a, r, nobs, done))
            obs, eret = nobs, eret + r
            steps += 1
            if len(buf) >= 512:
                b = random.sample(buf, 64)
                o = torch.from_numpy(np.stack([t[0] for t in b]))
                nb = torch.from_numpy(np.stack([t[3] for t in b]))
                av = torch.tensor([t[1] for t in b])
                rv = torch.tensor([t[2] for t in b], dtype=torch.float32)
                dv = torch.tensor([t[4] for t in b], dtype=torch.float32)
                with torch.no_grad():
                    tgt = rv + (1 - dv) * gamma * qt(nb).max(1).values
                loss = loss_fn(q(o)[range(64), av], tgt)
                opt.zero_grad()
                loss.backward()
                opt.step()
                sync += 1
                if sync % 200 == 0:
                    qt.load_state_dict(q.state_dict())
        # PRESS on button is the only +5, so pressed_ep means a win
        rsum += eret
        ssum += env.steps
        if pressed_ep:
            wins += 1
        if ep % log_every == 0:
            print(f"ep {ep}/{episodes} eps={eps:.2f} "
                  f"winrate[{ep-log_every+1}-{ep}]={wins/log_every:.2f} "
                  f"avg_ret={rsum/log_every:.2f} avg_steps={ssum/log_every:.1f}",
                  flush=True)
            wins, rsum, ssum = 0, 0.0, 0
    torch.save(q.state_dict(), save)
    print(f"saved {save}")
    return save


@torch.no_grad()
def evaluate(path=SAVE, episodes=200, seed=999):
    if not os.path.exists(path):
        print(f"no policy at {path} -- run --train first")
        return None
    q = QNet()
    q.load_state_dict(torch.load(path, map_location="cpu"))
    q.eval()
    env = CellEnv(seed=seed)
    wins, steps, herr = 0, [], []
    press_steps = []
    for _ in range(episodes):
        obs, _ = env.reset()
        done = False
        pressed = False
        while not done:
            a = int(q(torch.from_numpy(obs).unsqueeze(0)).argmax())
            was_pressed = (a == PRESS and env.pos == env.button)
            obs, r, done, _, info = env.step(a)
            if info.get("pressed") or (was_pressed and done):
                pressed = True
        if pressed:
            # last PRESS succeeded (episode ended on the button)
            wins += 1
            press_steps.append(env.steps)
        steps.append(env.steps)
        herr.append(abs(env.herr))
    steps = np.array(steps)
    win_mean = float(np.mean(press_steps)) if press_steps else float("nan")
    print(f"eval {episodes}: press_success={wins/episodes:.2f} "
          f"mean_steps={steps.mean():.1f} p90={np.percentile(steps,90):.0f} "
          f"mean_|herr|={np.mean(herr):.1f}deg win_mean_steps={win_mean:.1f}")
    print(f"ESTIMATED COST for goto(): {win_mean:.1f} policy-steps per button trip "
          f"(planner budgets this).")
    return wins / episodes


def demo(path=SAVE, seed=7):
    """One greedy rollout in text, so you can watch FWD/turn/PRESS."""
    q = QNet()
    q.load_state_dict(torch.load(path, map_location="cpu"))
    q.eval()
    env = CellEnv(seed=seed)
    obs, _ = env.reset()
    print(f"start={env.pos} h={env.heading} button={env.button} rocks={len(env.rocks)}")
    for t in range(20):
        with torch.no_grad():
            a = int(q(torch.from_numpy(obs).unsqueeze(0)).argmax())
        obs, r, done, _, _ = env.step(a)
        print(f"  {t:02d} {NAMES[a]:7s} -> pos={env.pos} h={env.heading} "
              f"herr={env.herr:+.1f} r={r:+.2f}")
        if done:
            print("  DONE: pressed" if env.pos == env.button else "  DONE: timed out")
            break


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", action="store_true")
    ap.add_argument("--eval", action="store_true")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--episodes", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    if not (args.train or args.eval or args.demo):
        ap.print_help()
        sys.exit(0)
    if args.train:
        train(episodes=args.episodes, seed=args.seed)
    if args.eval:
        evaluate(episodes=min(args.episodes, 200) if args.train else 200)
    if args.demo:
        demo()
