"""Settings changed inside the app, and when each change lands. Every test writes to a
temporary file."""

import json
import tempfile
from pathlib import Path

import pygame

import chat
import config
import prompts
import registry
import dashboard
import render
import replay
import settings
from world import World


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
            registry.BY_NAME[name].set(v)
        self.dir.cleanup()


def test_defaults_are_the_code():
    # STORM_ON is the one this file turns off itself, after the registry has read it.
    off = [s.name for s in registry.SETTINGS
           if s.default != s.get() and s.name != "STORM_ON"]
    assert not off, "every default is the module's own value"
    bad = []
    for s in registry.SETTINGS:
        try:
            s.coerce(s.default)
        except ValueError as e:
            bad.append(f"{s.name}: {e}")
    assert not bad, "every default passes its own validation"
    assert all(s.tier in registry.TIERS for s in registry.SETTINGS), "every setting has a known tier"
    assert len(registry.BY_NAME) == len(registry.SETTINGS), "names are unique"
    # 10c ships the recording's numbers, so the preset must describe what is shipped.
    rec = registry.PRESETS["29 Sept recording"]
    assert all(registry.BY_NAME[k].default == v for k, v in rec.items()), "the shipped values are the 29 Sept recording"
    assert set(rec) == set(registry.PRESETS["design"]), "both presets name the same settings"


def test_only_changes_are_saved():
    with Sandbox() as sb:
        p = sb.prefs()
        p.set("BATTERY", 150)
        assert sb.saved() == {"BATTERY": 150}, "a change is written"
        p.set("BATTERY", registry.BY_NAME["BATTERY"].default)
        assert sb.saved() == {}, "setting it back to the default removes it"
        p.set("ANIM_SPEED", 2)
        assert isinstance(sb.saved()["ANIM_SPEED"], float), "typed numbers keep the setting's type"
        assert registry.Prefs(sb.path).user == {"ANIM_SPEED": 2.0}, "a new Prefs reads it back"


def test_each_tier_lands_when_it_says():
    with Sandbox() as sb:
        p = sb.prefs()
        p.set("ANIM_SPEED", 2.0)
        assert settings.ANIM_SPEED == 2.0, "now: in force straight away"

        before = settings.BATTERY
        p.set("BATTERY", 150)
        assert settings.BATTERY == before, "next sol: not in force mid-sol"
        assert p.shown(registry.BY_NAME["BATTERY"]) == 150, "...but shown as the value"
        done = p.nightfall()
        assert settings.BATTERY == 150, "...and in force after nightfall"
        assert p.pending == {}, "...once"

        p.set("MODEL", "gemma4:e4b")
        assert (settings.MODEL != "gemma4:e4b"
                    or registry.BY_NAME["MODEL"].default == "gemma4:e4b"), "the model waits for the sol too"
        p.set("MODEL", settings.MODEL)
        assert "MODEL" not in p.pending, "changing it back cancels the wait"

        hud = config.HUD_H
        p.set("HUD_H", 200)
        p.nightfall()
        assert config.HUD_H == hud, "relaunch: not applied by nightfall either"
        registry.Prefs(sb.path).apply_all()
        assert config.HUD_H == 200, "...only at the next start"


def test_bad_values_are_refused():
    with Sandbox() as sb:
        p = sb.prefs()
        for name, v in (("BATTERY", 5), ("BATTERY", "lots"),
                        ("STORM_ON", 1), ("MODEL", "  ")):
            try:
                p.set(name, v)
                refused = False
            except ValueError:
                refused = True
            assert refused, f"{name}={v!r} refused"
        assert sb.saved() == {}, "and nothing was saved"
        sb.path.write_text('{"BATTERY": 99999, "NOT_A_SETTING": 1, "VISION_RADIUS": 3}')
        q = sb.prefs()
        assert q.user == {"VISION_RADIUS": 3}, "a hand-edited file keeps what is valid"
        assert len(q.warnings) == 2, "...and says what it dropped"
        sb.path.write_text("{not json")
        assert sb.prefs().user == {}, "a broken file is ignored, not fatal"


def test_the_prompt_states_the_settings():
    with Sandbox():
        settings.MOVE_HOPS, settings.FREE_HOPS = 7, 3
        text = prompts.use()
        assert "7 drives a turn" in text, "drives"
        assert "3 looks" in text, "looks"
        assert "Ten drives" not in text, "no number written in by hand"
    prompts.use()


def test_replay_uses_the_logs_settings():
    rows = [{"kind": "settings", "sol": 1, "values": {"BATTERY": 150, "HUD_H": 190,
                                                      "MODEL": "elsewhere"}},
            {"kind": "settings", "sol": 2, "values": {"BATTERY": 300}}]
    with Sandbox() as sb, tempfile.TemporaryDirectory() as d:
        run = Path(d)
        (run / "game.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
        (run / "chat.jsonl").write_text("")
        script = replay.Script(run)
        hud, model = config.HUD_H, settings.MODEL
        script.use_settings(1)
        assert settings.BATTERY == 150, "sol 1's world settings"
        assert config.HUD_H == hud, "the viewer keeps their own window"
        assert settings.MODEL == model, "...and nothing about the model is taken"
        script.use_settings(2)
        assert settings.BATTERY == 300, "sol 2's own"
        assert not sb.path.exists(), "nothing was saved as the viewer's"


def test_the_screens_draw():
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
    for memory in (False, True):
        render.draw_chat(pane, conv, w, f, "", False, 0, memory=memory)
    rows = dashboard.list_rows(w)
    assert ("drive to objective 2", "struck") in rows, "struck items are ticked"
    assert ("a long item " * 12, "open") in rows, "open ones are not"
    lines = [t for t, _ in dashboard.memory_rows(w, 60)]
    assert (lines.index("the C: east of the pad")
                < lines.index("STANDING ORDERS") < lines.index("1. finish objective 2")), "the memory, then the orders"
    assert "drive to objective 2" not in lines, "the list is not in the memory view"
    with Sandbox() as sb:
        items = [("preset", k) for k in registry.PRESETS] + \
                [("setting", s) for s in registry.SETTINGS]
        p = sb.prefs()
        p.set("BATTERY", 150)
        screen = pygame.Surface((1200, 500))
        for i in range(len(items)):
            render.draw_settings(screen, f, items, i, p, None, "", None, False)
        render.draw_settings(screen, f, items, 5, p, "12", "a notice", ["a", "b"], True)
        assert True, "every row draws, editing and replaying included"
