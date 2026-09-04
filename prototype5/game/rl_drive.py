"""Driving the world with the trained one-cell policy.

The seam between the RL half and the game: A* in `nav.py` still plans the route
cell by cell, but with executor="policy" each leg is driven by the DQN from
`rl_cell.py` (FWD / LEFT90 / RIGHT90 / PRESS) instead of teleporting via
`world.move`. The policy was trained in `CellEnv`; this file translates the
live `World` into the same 8-float "clean state" it expects, so sim and floor
see identical vectors (rover_ideas.md, Sim and reality).

No torch at import time: `load_policy` imports it lazily, so the game, the
console and every test keep working on a machine without torch. Only a policy
drive pays for the import.
"""

import math
import os

import numpy as np

from world import DIRS

NAMES = ["FWD", "LEFT90", "RIGHT90", "PRESS"]

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_POLICY = os.path.join(HERE, "rl_policy.pt")


def policy_obs(world, tx, ty):
    """The 8-float clean state for target (tx, ty), field-for-field identical
    to CellEnv._obs in rl_cell.py: dx, dy, sin/cos of heading+herr,
    herr/45, front_blocked, on_button, dist/10."""
    dx = tx - world.pos[0]
    dy = ty - world.pos[1]
    rad = math.radians(world.heading * 90.0 + world.herr)
    fx, fy = DIRS[world.heading]
    front = world.here.blocked(world.pos[0] + fx, world.pos[1] + fy)
    return np.array([
        dx, dy,
        math.sin(rad), math.cos(rad),
        world.herr / 45.0,
        1.0 if front else 0.0,
        1.0 if world.pos in world.buttons else 0.0,
        math.hypot(dx, dy) / 10.0,
    ], dtype=np.float32)


def load_policy(path=None):
    """Greedy action function for the trained weights. Raises RuntimeError
    with the fix (not a traceback to debug) when weights or torch are missing."""
    path = path or DEFAULT_POLICY
    if not os.path.exists(path):
        raise RuntimeError(
            f"no policy at {path} -- train one: "
            f"cd prototype3 && python game\\rl_cell.py --train --episodes 2000")
    try:
        import torch
        from rl_cell import QNet
    except ImportError as e:
        # Name the module that is actually missing. This used to blame torch for
        # whatever failed, and `rl_cell` imports gymnasium too -- so a working torch
        # and no gymnasium sent you off installing the thing you already had.
        raise RuntimeError(
            f"need {e.name} to drive the policy: pip install torch numpy gymnasium "
            f"--extra-index-url https://download.pytorch.org/whl/cpu")
    q = QNet()
    q.load_state_dict(torch.load(path, map_location="cpu"))
    q.eval()

    def act(obs):
        import torch as _t
        with _t.no_grad():
            return int(q(_t.from_numpy(obs).unsqueeze(0)).argmax())

    return act


def drive_leg(world, tx, ty, act, cap=12):
    """Drive toward adjacent cell (tx, ty) with the policy, at most `cap`
    micro-actions. Returns {"arrived", "actions", "charged", "trail"} where
    charged is the day-steps spent (bumps are free, like move() refusing a
    wall) and trail is [(cell, revealed)] per actual move, so the caller can
    replay and log exactly where the rover went -- including wandering."""
    actions, trail = [], []
    charged = 0
    for _ in range(cap):
        if world.day_over or world.pos == (tx, ty):
            break
        a = act(policy_obs(world, tx, ty))
        before = world.steps
        kind = world.step_action(a)
        actions.append(NAMES[a])
        charged += world.steps - before
        if kind == "moved":
            trail.append((world.pos, sorted(world.revealed)))
        elif kind == "pressed":
            break
    return {"arrived": world.pos == (tx, ty), "actions": actions,
            "charged": charged, "trail": trail}


def press_here(world, act, cap=6):
    """PRESS the button under the rover. Returns (pressed, actions)."""
    actions = []
    for _ in range(cap):
        if world.day_over:
            break
        a = act(policy_obs(world, *world.pos))
        kind = world.step_action(a)
        actions.append(NAMES[a])
        if kind == "pressed":
            return True, actions
    return world.pos in world.pressed, actions
