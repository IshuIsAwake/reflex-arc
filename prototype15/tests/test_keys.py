"""The game's keys, pressed for real through Game.frame() with no window: her chat, the
terminal, the settings screen, the map, the view, driving by hand and the quit question."""
import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame  # noqa: E402

import main  # noqa: E402
import registry  # noqa: E402
import render  # noqa: E402
import settings  # noqa: E402



def key(k, ch=""):
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=k, unicode=ch, mod=0))


def typed(text):
    for ch in text:
        key(pygame.key.key_code(ch) if ch != " " else pygame.K_SPACE, ch)


def frames(game, n=3):
    for _ in range(n):
        game.frame()


def quiet_model(conv):
    """The model answers at once with a line and no call."""
    def stream(messages, allowed=None):
        conv.q.put(("say", "Ready."))
        conv.q.put(("done", ({"prompt_eval_count": 1, "eval_count": 1}, [])))
    conv._stream = stream


def test_every_mode_answers_its_keys(tmp_path, monkeypatch, inline_threads):
    monkeypatch.setattr(main, "RUNS", tmp_path / "runs")
    prefs = registry.Prefs(tmp_path / "user_settings.json")
    args, script, carried = main.read_flags(["--arena", "30", "--comms", "on"], prefs)
    pygame.init()
    game = main.Game(args, script, carried, prefs)
    quiet_model(game.conv)
    frames(game)
    # Her chat: /help, then an order.
    key(pygame.K_TAB)
    frames(game, 1)
    assert game.typing
    typed("/help")
    key(pygame.K_RETURN)
    frames(game)
    assert any("/next" in t for w, t in game.conv.lines), game.conv.lines[-3:]
    typed("/order survey north")
    key(pygame.K_RETURN)
    frames(game)
    assert game.world.notes.orders == ["survey north"], game.conv.lines[-3:]
    key(pygame.K_ESCAPE)
    frames(game, 1)
    assert not game.typing
    # The terminal: help, comms, a drive.
    key(pygame.K_t)
    frames(game, 1)
    assert game.mode == "console"
    typed("help")
    key(pygame.K_RETURN)
    frames(game)
    assert any("place X Y" in t for t, tone in game.history)
    typed("comms off")
    key(pygame.K_RETURN)
    frames(game)
    assert settings.COMMS is False
    typed("goto 15 10")
    key(pygame.K_RETURN)
    frames(game)
    assert any(t.startswith("DONE") or "steps" in t for t, tone in game.history), game.history[-3:]
    key(pygame.K_ESCAPE)
    frames(game, 1)
    assert game.mode == "world"
    # The settings screen: down twice, nudge one, close.
    key(pygame.K_o)
    frames(game, 1)
    assert game.mode == "settings"
    key(pygame.K_DOWN)
    key(pygame.K_DOWN)
    key(pygame.K_RIGHT)
    frames(game)
    assert game.notice, game.notice
    key(pygame.K_ESCAPE)
    frames(game, 1)
    assert game.mode == "world"
    # The map and a mark, the view, and a step by hand.
    key(pygame.K_m)
    frames(game, 1)
    assert game.mode == "map"
    key(pygame.K_x)
    frames(game, 1)
    assert game.cursor in game.world.here.marks
    key(pygame.K_ESCAPE)
    frames(game, 1)
    assert game.mode == "world"
    key(pygame.K_v)
    frames(game, 1)
    assert game.mode == "view"
    key(pygame.K_v)
    frames(game, 1)
    assert game.mode == "world"
    before = game.world.pos
    key(pygame.K_d)
    frames(game, 1)
    assert game.world.pos != before or game.world.here.blocked(before[0] + 1, before[1])
    # The quit question, and back.
    key(pygame.K_ESCAPE)
    frames(game, 1)
    assert game.mode == "quit"
    key(pygame.K_ESCAPE)
    frames(game, 1)
    assert game.mode == "world"
    # K keeps the run and exits.
    key(pygame.K_ESCAPE)
    key(pygame.K_k)
    try:
        frames(game, 1)
        assert False, "K should have exited"
    except SystemExit:
        pass
    finally:
        pygame.init()  # leaving quits pygame; the tests after this one still need it
        render.DISPLAY_SIZE = None  # the window's size, which the render tests must not see
    kept = [d for d in (tmp_path / "runs").iterdir() if not d.name.startswith("pending")]
    assert kept and (kept[0] / "night.json").exists()
