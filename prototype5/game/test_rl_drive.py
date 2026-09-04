r"""The RL buttons drive the real game.

    ..\.venv\Scripts\python.exe game\test_rl_drive.py

world.step_action speaks the four buttons rl_cell.py trained (FWD / LEFT90 /
RIGHT90 / PRESS), and nav.goto executor="policy" drives each A* leg with them
instead of teleporting. The oracle below stands in for the weights so every
check here runs without torch; the real policy gets its turn in the last test,
which skips loudly when weights or torch are missing.
"""

import math

import nav
import rl_drive
from world import DIRS, World


def oracle(obs):
    """A greedy stand-in for the trained net: face the target cell, drive,
    PRESS on the button. Reads only the 8-float obs, never the world."""
    dx, dy, sin_h, cos_h, _herr, front, on_button, _dist = (float(v) for v in obs)
    if on_button > 0.5:
        return 3
    want = (1 if dx > 0 else 3) if abs(dx) >= abs(dy) else (2 if dy > 0 else 0)
    got = int(round(math.degrees(math.atan2(sin_h, cos_h)) / 90.0)) % 4
    if got != want:
        return 2
    if front > 0.5:
        return 1
    return 0


def button(w):
    assert len(w.buttons) == 1, w.buttons
    return next(iter(w.buttons))


def test_world_has_heading_and_buttons():
    w = World()
    assert w.heading == 0 and w.herr == 0.0
    b = button(w)
    assert w.here.at(*b) == ".", "a button must sit on clear ground, not rock"
    assert b != w.pos, "the rover must drive to reach it"


def test_step_action_turns():
    w = World()
    assert w.step_action(1) == "turned" and w.heading == 3
    assert w.step_action(2) == "turned" and w.heading == 0
    assert w.steps == 2, "turns are actions and cost steps"


def test_step_action_fwd_or_bump():
    w = World()
    fx, fy = DIRS[w.heading]
    front = (w.pos[0] + fx, w.pos[1] + fy)
    if w.here.blocked(*front):
        assert w.step_action(0) == "bump"
        assert w.pos == (25, 25) and w.steps == 0, "a refused move costs nothing"
    else:
        assert w.step_action(0) == "moved"
        assert w.pos == front and w.steps == 1


def test_press():
    w = World()
    assert w.step_action(3) == "noop", "pressing thin air presses nothing"
    assert not w.pressed
    w.pos = button(w)
    assert w.step_action(3) == "pressed"
    assert w.pos in w.pressed


def test_next_day_squares_up():
    w = World()
    w.heading, w.herr = 2, 12.5
    w.next_day()
    assert (w.heading, w.herr) == (0, 0.0)


def test_policy_obs_matches_training():
    w = World()
    obs = rl_drive.policy_obs(w, *button(w))
    assert obs.shape == (8,), obs.shape
    assert obs[6] == 0.0, "not standing on the button yet"
    w.pos = button(w)
    assert rl_drive.policy_obs(w, *w.pos)[6] == 1.0


def test_policy_goto_adjacent():
    w = World()
    target = next((w.pos[0] + dx, w.pos[1] + dy) for dx, dy in DIRS
                  if not w.here.blocked(w.pos[0] + dx, w.pos[1] + dy))
    r = nav.goto(w, *target, executor="policy", act=oracle)
    assert r.code == "DONE", r
    assert r.at == target, r
    assert not r.pressed


def test_policy_goto_button_presses():
    w = World()
    r = nav.goto(w, *button(w), executor="policy", act=oracle)
    assert r.code == "DONE", r
    assert w.pos == button(w) and r.pressed, r
    assert "Pressed the button" in (r.advice or ""), r.advice


def test_teleport_default_unchanged():
    w = World()
    r = nav.goto(w, 25, 20)
    assert r.code == "DONE" and not r.pressed, r


def test_console_policy_word():
    import console
    w = World()
    out = console.run(w, "goto 25 20 policy")
    text = " ".join(t for t, _ in out)
    assert "DONE" in text or "no policy" in text, out


def test_real_policy_if_available():
    try:
        act = rl_drive.load_policy()
    except (RuntimeError, ImportError) as e:
        print(f"SKIP real policy: {e}")
        return
    w = World()
    r = nav.goto(w, *button(w), executor="policy", act=act)
    assert r.code == "DONE" and r.pressed, (
        f"the trained weights should press: {r} at={w.pos}")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("all rl_drive checks passed")
