r"""The controller buttons in the model's hands.

    ..\.venv\Scripts\python.exe game\test_step.py

`step` drives one cell by compass word, `press` presses the button under the
rover. Both run through skills.call, so this checks the model's exact path --
validation, result strings, step charging -- not a side door.
"""

import console
import nav
import skills
from world import World


def test_step_drives_one_cell():
    w = World()
    c = skills.call(w, "step", {"direction": "north"})
    assert c.result.startswith("MOVED"), c.result
    assert w.pos == (25, 24), w.pos
    assert c.steps == 1 and w.steps == 1


def test_step_reads_generously():
    w = World()
    assert skills.call(w, "step", {"direction": "N"}).result.startswith("MOVED")
    assert skills.call(w, "step", {"direction": "  South "}).result.startswith("MOVED")
    assert w.pos == (25, 25), w.pos  # north then back south


def test_step_refusal_is_loud_and_free():
    w = World()
    w.pos = (25, 25)
    # South of spawn is the base pad: solid, so stopping is the only arrival.
    c = skills.call(w, "step", {"direction": "south"})
    assert c.result.startswith("BUMPED"), c.result
    assert w.pos == (25, 25) and c.steps == 0 and w.steps == 0


def test_step_junk_direction_is_bad_args():
    w = World()
    for junk in ("forward", "up", "", None, True, 7):
        c = skills.call(w, "step", {"direction": junk})
        assert c.result.startswith("BAD_ARGS"), (junk, c.result)
    assert w.steps == 0 and w.pos == (25, 25)


def test_press():
    w = World()
    c = skills.call(w, "press", {})
    assert c.result.startswith("NOTHING_TO_PRESS"), c.result
    assert c.steps == 1, "even thin air costs the step"
    b = next(iter(w.buttons))
    w.pos = b
    c = skills.call(w, "press", {})
    assert c.result.startswith("PRESSED"), c.result
    assert b in w.pressed


def test_step_and_press_obey_the_day():
    w = World()
    w.steps = 1000
    w.day_over = True
    assert skills.call(w, "step", {"direction": "north"}).result.startswith("OUT_OF_STEPS")
    assert skills.call(w, "press", {}).result.startswith("OUT_OF_STEPS")
    assert w.pos == (25, 25)


def test_console_buttons():
    w = World()
    out = console.run(w, "step north")
    assert any("MOVED" in t for t, _ in out), out
    assert w.pos == (25, 24)
    out = console.run(w, "press")
    assert any("NOTHING_TO_PRESS" in t for t, _ in out), out
    out = console.run(w, "step up")
    assert any("BAD_ARGS" in t for t, _ in out), out


def test_typed_buttons_are_recovered():
    assert skills.written_call('step("north")') == ("step", {"direction": "north"})
    assert skills.written_call("press()") == ("press", {})
    assert skills.looks_like_a_call("I will step(north) now")
    assert skills.looks_like_a_call("I will press() now")
    # ...but prose without a paren is still prose.
    assert not skills.looks_like_a_call("step is the right tool here")
    assert not skills.looks_like_a_call("Nothing to report.")


def test_schema_stays_honest():
    names = {t["function"]["name"] for t in skills.TOOLS}
    assert names == {"goto", "distance", "step", "press"}, names
    # No relative controls on offer anywhere -- the prose may forbid "forward",
    # but no parameter may accept it.
    params = {k for t in skills.TOOLS
              for k in t["function"]["parameters"]["properties"]}
    assert params <= {"x", "y", "why", "avoid", "direction"}, params


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("all step checks passed")
