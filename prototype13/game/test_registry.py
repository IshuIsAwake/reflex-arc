"""Settings changed inside the app, and when each change lands.

    .venv/bin/python game/test_registry.py

Every test writes to a temporary file and puts the modules back, because a registry
change is a global one and would otherwise resize or retime the next suite.
"""

import json
import tempfile
from pathlib import Path

import pygame

import chat
import config as C
import prompts
import registry
import render
import replay
import settings as S
from world import World

S.STORM_ON = False


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'}  {name}{'   ' + detail if detail else ''}")
    return bool(cond)


class Sandbox:
    """A Prefs on a temporary file, with every setting put back on the way out."""

    def __enter__(self):
        self.keep = registry.snapshot()
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "user_settings.json"
        return self

    def prefs(self):
        return registry.Prefs(self.path)

    def saved(self):
        return json.loads(self.path.read_text()) if self.path.exists() else {}

    def __exit__(self, *exc):
        for name, v in self.keep.items():
            setattr(registry.BY_NAME[name].mod, name, v)
        self.dir.cleanup()


def test_defaults_are_the_code():
    print("defaults stay in code")
    # STORM_ON is the one this file turns off itself, after the registry has read it.
    off = [s.name for s in registry.SETTINGS
           if s.default != getattr(s.mod, s.name) and s.name != "STORM_ON"]
    ok = check("every default is the module's own value", not off, str(off))
    bad = []
    for s in registry.SETTINGS:
        try:
            s.coerce(s.default)
        except ValueError as e:
            bad.append(f"{s.name}: {e}")
    ok &= check("every default passes its own validation", not bad, str(bad))
    ok &= check("every setting has a known tier",
                all(s.tier in registry.TIERS for s in registry.SETTINGS))
    ok &= check("names are unique", len(registry.BY_NAME) == len(registry.SETTINGS))
    # 10c ships the recording's numbers, so the preset must describe what is shipped.
    rec = registry.PRESETS["29 Sept recording"]
    ok &= check("the shipped values are the 29 Sept recording",
                all(registry.BY_NAME[k].default == v for k, v in rec.items()),
                str({k: registry.BY_NAME[k].default for k in rec}))
    ok &= check("both presets name the same settings",
                set(rec) == set(registry.PRESETS["design"]))
    return ok


def test_only_changes_are_saved():
    print("the user file holds only what differs")
    with Sandbox() as sb:
        p = sb.prefs()
        p.set("BATTERY", 150)
        ok = check("a change is written", sb.saved() == {"BATTERY": 150}, str(sb.saved()))
        p.set("BATTERY", registry.BY_NAME["BATTERY"].default)
        ok &= check("setting it back to the default removes it", sb.saved() == {},
                    str(sb.saved()))
        p.set("ANIM_SPEED", 2)
        ok &= check("typed numbers keep the setting's type",
                    isinstance(sb.saved()["ANIM_SPEED"], float))
        ok &= check("a new Prefs reads it back",
                    registry.Prefs(sb.path).user == {"ANIM_SPEED": 2.0})
    return ok


def test_each_tier_lands_when_it_says():
    print("now, next sol, relaunch")
    with Sandbox() as sb:
        p = sb.prefs()
        p.set("ANIM_SPEED", 2.0)
        ok = check("now: in force straight away", S.ANIM_SPEED == 2.0)

        before = S.BATTERY
        p.set("BATTERY", 150)
        ok &= check("next sol: not in force mid-sol", S.BATTERY == before)
        ok &= check("...but shown as the value", p.shown(registry.BY_NAME["BATTERY"]) == 150)
        done = p.nightfall()
        ok &= check("...and in force after nightfall", S.BATTERY == 150, str(done))
        ok &= check("...once", p.pending == {})

        p.set("MODEL", "gemma4:e4b")
        ok &= check("the model waits for the sol too", S.MODEL != "gemma4:e4b"
                    or registry.BY_NAME["MODEL"].default == "gemma4:e4b")
        p.set("MODEL", S.MODEL)
        ok &= check("changing it back cancels the wait", "MODEL" not in p.pending)

        hud = C.HUD_H
        p.set("HUD_H", 200)
        p.nightfall()
        ok &= check("relaunch: not applied by nightfall either", C.HUD_H == hud)
        registry.Prefs(sb.path).apply_all()
        ok &= check("...only at the next start", C.HUD_H == 200)
    return ok


def test_bad_values_are_refused():
    print("bad values")
    with Sandbox() as sb:
        p = sb.prefs()
        for name, v in (("BATTERY", 5), ("BATTERY", "lots"), ("MAP_FORMAT", "png"),
                        ("STORM_ON", 1), ("MODEL", "  ")):
            try:
                p.set(name, v)
                refused = False
            except ValueError:
                refused = True
            if not check(f"{name}={v!r} refused", refused):
                return False
        ok = check("and nothing was saved", sb.saved() == {})
        sb.path.write_text('{"BATTERY": 99999, "NOT_A_SETTING": 1, "VISION_RADIUS": 3}')
        q = sb.prefs()
        ok &= check("a hand-edited file keeps what is valid", q.user == {"VISION_RADIUS": 3},
                    str(q.user))
        ok &= check("...and says what it dropped", len(q.warnings) == 2, str(q.warnings))
        sb.path.write_text("{not json")
        ok &= check("a broken file is ignored, not fatal", sb.prefs().user == {})
    return ok


def test_the_prompt_states_the_settings():
    print("the prompt says the caps the game enforces")
    with Sandbox():
        S.MOVE_HOPS, S.FREE_HOPS = 7, 3
        text = prompts.use(prompts.DEFAULT)
        ok = check("drives", "7 drives a turn" in text)
        ok &= check("looks", "3 looks" in text)
        ok &= check("no number written in by hand", "Ten drives" not in text)
    prompts.use(prompts.DEFAULT)
    return ok


def test_replay_uses_the_logs_settings():
    print("replay takes the kept run's values")
    rows = [{"kind": "settings", "sol": 1, "values": {"BATTERY": 150, "HUD_H": 190,
                                                      "MODEL": "elsewhere"}},
            {"kind": "settings", "sol": 2, "values": {"BATTERY": 300}}]
    with Sandbox() as sb, tempfile.TemporaryDirectory() as d:
        run = Path(d)
        (run / "game.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
        (run / "chat.jsonl").write_text("")
        script = replay.Script(run)
        hud, model = C.HUD_H, S.MODEL
        script.use_settings(1)
        ok = check("sol 1's world settings", S.BATTERY == 150)
        ok &= check("the viewer keeps their own window", C.HUD_H == hud)
        ok &= check("...and nothing about the model is taken", S.MODEL == model)
        script.use_settings(2)
        ok &= check("sol 2's own", S.BATTERY == 300)
        ok &= check("nothing was saved as the viewer's", not sb.path.exists())
        legacy = registry.from_log([{"kind": "run", "day_steps": 150, "vision": 2,
                                     "arena": "50x50", "model": "x"}])
        ok &= check("tapes from before the registry are read too",
                    legacy == {1: {"BATTERY": 150, "VISION_RADIUS": 2,
                                   "APP_ARENA": "50"}}, str(legacy))
    return ok


def test_the_screens_draw():
    print("drawing, headless")
    pygame.font.init()
    f = render.Fonts()
    w = World()
    w.notes.add("drive to objective 2")
    w.notes.add("a long item " * 12)
    w.notes.strike(1)
    w.notes.memory = {"the C": "east of the pad"}
    w.notes.order("finish objective 2")
    conv = chat.Conversation(w)
    pane = pygame.Surface((600, 700))
    ok = True
    for memory in (False, True):
        render.draw_chat(pane, conv, w, f, "", False, 0, memory=memory)
    rows = render.D.list_rows(w)
    ok &= check("struck items are ticked", ("drive to objective 2", "struck") in rows)
    ok &= check("open ones are not", ("a long item " * 12, "open") in rows)
    lines = [t for t, _ in render.D.memory_rows(w, 60)]
    ok &= check("the memory, then the orders", lines.index("the C: east of the pad")
                < lines.index("STANDING ORDERS") < lines.index("1. finish objective 2"),
                str(lines))
    ok &= check("the list is not in the memory view", "drive to objective 2" not in lines)
    with Sandbox() as sb:
        items = [("preset", k) for k in registry.PRESETS] + \
                [("setting", s) for s in registry.SETTINGS]
        p = sb.prefs()
        p.set("BATTERY", 150)
        screen = pygame.Surface((1200, 500))
        for i in range(len(items)):
            render.draw_settings(screen, f, items, i, p, None, "", None, False)
        render.draw_settings(screen, f, items, 5, p, "12", "a notice", ["a", "b"], True)
        ok &= check("every row draws, editing and replaying included", True)
    return ok


if __name__ == "__main__":
    import sys
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    results = [t() for t in tests]
    print(f"\n{sum(results)}/{len(results)} groups passed")
    sys.exit(0 if all(results) else 1)
