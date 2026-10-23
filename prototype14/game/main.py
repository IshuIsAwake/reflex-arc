"""The game: the window, the keys, and the loop that runs the mission.

    .venv/bin/python game/main.py [--arena 30|50] [--sols N] [--model TAG] [--think]
                                  [--comms on|off] [--objectives manual|auto] [--preset design]
                                  [--outage N] [--resume runs/<stamp>] [--replay runs/<stamp>]

Every key, command and flag is in MANUAL.md. Settings come from the code's defaults, then
user_settings.json, then the flags for this launch."""

import argparse
import hashlib
import os
import pathlib
import signal
import sys
import time

import pygame

import anim
import autopilot
import chat
import prompts
import config
import console
import logs
import nav
import ollama
import registry
import dashboard
import render
import replay
import report
import settings
import sight
from world import World

def headless():
    """No window: nobody is watching, so nobody is at the desk."""
    return os.environ.get("SDL_VIDEODRIVER") == "dummy"


DIRS = {pygame.K_w: (0, -1), pygame.K_s: (0, 1), pygame.K_a: (-1, 0), pygame.K_d: (1, 0),
        pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1), pygame.K_LEFT: (-1, 0),
        pygame.K_RIGHT: (1, 0)}


def edit(text, caret, e):
    """One key on a line being typed. Returns the line and where the caret is now."""
    if e.key == pygame.K_BACKSPACE:
        if caret == 0:
            return text, 0
        return text[:caret - 1] + text[caret:], caret - 1
    if e.key == pygame.K_DELETE:
        return text[:caret] + text[caret + 1:], caret
    if e.key == pygame.K_LEFT:
        return text, max(0, caret - 1)
    if e.key == pygame.K_RIGHT:
        return text, min(len(text), caret + 1)
    if e.key == pygame.K_HOME:
        return text, 0
    if e.key == pygame.K_END:
        return text, len(text)
    if e.unicode and e.unicode.isprintable():
        return text[:caret] + e.unicode + text[caret:], caret + len(e.unicode)
    return text, caret


def read_flags(argv, prefs):
    """Put every setting in force before anything reads one: the defaults, the saved
    settings, this launch's flags, and on a replay the kept run's own values, which win.
    Returns (args, script, carried); `carried` is the night a resumed run wakes from."""
    p = argparse.ArgumentParser(prog="game/main.py")
    p.add_argument("--arena", choices=tuple(config.ARENAS), help="which arena to land on")
    p.add_argument("--model", help="any tag `ollama list` shows, or a `-cloud` one")
    p.add_argument("--think", action="store_true",
                   help="reasoning trace on, and the sampler left to the model")
    p.add_argument("--pause", choices=("key", "none"),
                   help="who says the rover finished a leg; 'key' is SPACE at every pause")
    p.add_argument("--sols", type=int, help="sols in the mission; 0 is no limit")
    p.add_argument("--comms", choices=("on", "off"),
                   help="whether anyone is at the desk to talk to her; a run with no "
                        "window starts with it off")
    p.add_argument("--objectives", choices=("manual", "auto"),
                   help="auto: three objectives from sol 2, a new set once the last is "
                        "done")
    p.add_argument("--preset", choices=tuple(registry.PRESETS),
                   help="load a preset for this launch only; nothing is saved")
    p.add_argument("--outage", type=int, action="append", metavar="SOL",
                   help="cut the planner's model off for sol SOL, to watch the fallback "
                        "take over and hand back; repeatable")
    p.add_argument("--replay", metavar="RUN_DIR",
                   help="re-issue a kept run's calls with no model in the loop")
    p.add_argument("--resume", metavar="RUN_DIR",
                   help="carry on a kept run's expedition from the sol after it stopped")
    args = p.parse_args(argv)
    if args.replay and args.resume:
        p.error("--replay and --resume are two different runs; pick one")

    prefs.apply_all()
    for warning in prefs.warnings:
        print("settings:", warning)
    if args.preset:
        registry.apply(registry.PRESETS[args.preset])
    settings.OUTAGE_SOLS = tuple(args.outage or ())
    # With no window, nobody is at the desk unless the flag says so.
    comms = args.comms == "on" if args.comms else False if headless() else None
    flags = {"APP_ARENA": args.arena, "MODEL": args.model, "ROVER_PAUSE": args.pause,
             "MISSION_SOLS": args.sols, "COMMS": comms, "OBJECTIVES": args.objectives}
    bad = registry.apply({k: v for k, v in flags.items() if v is not None})
    if bad:
        p.error(f"out of range: {', '.join(bad)}")
    if args.think:
        settings.MODEL_THINK = True
        settings.MODEL_TEMP = None

    # Loaded before the window opens, so a bad run directory is reported at the prompt.
    script = replay.load(pathlib.Path(args.replay)) if args.replay else None
    if script:
        script.use_settings(script.first_sol)
    carried = script.start if script else None
    if args.resume:
        try:
            carried = logs.load_night(pathlib.Path(args.resume))
        except ValueError as e:
            p.error(str(e))
    if carried:
        # The map belongs to the arena it was drawn on, whatever is saved or flagged.
        registry.apply({"APP_ARENA": carried["arena"]})

    # Before anything reads config: the window and the world are sized off it.
    config.use(config.APP_ARENA)
    # Last: the prompt is built from the arena and the turn caps.
    prompts.use()
    return args, script, carried


def main():
    prefs = registry.Prefs()
    args, script, carried = read_flags(sys.argv[1:], prefs)
    pygame.init()

    def title():
        """Rewritten at nightfall, when the model may change."""
        pygame.display.set_caption(
            f"ANGARAKA -- prototype 14  ·  {config.VIEW_W}x{config.VIEW_H}"
            + (f"  ·  replay of {pathlib.Path(args.replay).name}" if args.replay else
               f"  ·  {settings.MODEL}")
            + ("  ·  thinking" if settings.MODEL_THINK else "")
            + ("  ·  comms on" if settings.COMMS else "  ·  comms off"))

    title()
    clock = pygame.time.Clock()
    fonts = render.Fonts()

    def layout_surfaces(display):
        """The window, and the arena's and the pane's parts of it."""
        game_rect, pane_rect = render.layout(*display.get_size())
        return display, display.subsurface(game_rect), display.subsurface(pane_rect)

    # The window fills the desktop, less its border and the taskbar.
    desktop = pygame.display.get_desktop_sizes()[0]
    screen, game, pane = layout_surfaces(pygame.display.set_mode(
        (max(960, desktop[0] - settings.SCREEN_RESERVE_W), max(640, desktop[1] - settings.SCREEN_RESERVE_H)),
        pygame.RESIZABLE))

    # The run is recorded from the start; whether it is kept is asked at the end.
    runs = pathlib.Path(__file__).resolve().parent.parent / "runs"
    run = logs.Run(runs, headless=headless())

    # SIGTERM keeps the run and exits. SDL would turn it into the K/D/ESC question, which a
    # headless run has nobody to answer.
    term = []
    signal.signal(signal.SIGTERM, lambda *_: term.append(True))

    def log_settings(sol):
        """Every setting in force, and a hash of the prompt they built, once a sol."""
        run.record("settings", sol=sol, values=registry.snapshot(),
                   prompt=hashlib.sha256(prompts.SYSTEM.encode()).hexdigest()[:12])

    w = World(recorder=run.record, carried=carried)
    if settings.OUTAGE_SOLS:
        # A staged outage goes on the tape, so it is never mistaken for a real one.
        run.record("outage", sols=list(settings.OUTAGE_SOLS), model=settings.MODEL,
                   fallback=settings.MODEL_FALLBACK)
    if args.resume:
        run.save_start(carried, pathlib.Path(args.resume).resolve().name)
    elif script and script.start:
        run.save_start(script.start, pathlib.Path(args.replay).resolve().name)
    log_settings(w.day)
    nav.clear_plan(w)  # the route file starts empty, never with yesterday's leg
    tape = chat.Tape(run.chat_path)
    # Which model answers. One for the run: an outage does not end at nightfall.
    link = ollama.Link()

    def talker():
        """The other end of the chat: Ollama, or a kept run."""
        if script:
            return replay.Replay(w, script, tape)
        return chat.Conversation(w, tape, link)

    conv = talker()
    conv.open_day(w)

    reel = anim.Reel(w)
    # The planner waits for the rover: no request goes out while a drive is still being
    # drawn, and for SETTLE_SECONDS after, so each drive can be seen. `settle` holds the
    # earliest time the next request may go out.
    settle = [0.0]

    def ready():
        now = time.monotonic()
        if reel.busy:
            settle[0] = now + settings.SETTLE_SECONDS
            return False
        return now >= settle[0]

    conv.ready = ready
    # The clock and the desk's windows, new every sol. A replay or a headless run never waits.
    pilot = autopilot.Autopilot(live=not script, attended=not headless())
    # Whether anyone was at the desk last frame, so a change from C or the settings screen is noticed.
    at_desk = [settings.COMMS]
    mode = "world"
    cursor = w.pos
    held = None
    next_step = 0
    line, history = "", []
    said, typing, scroll, scroll_max = "", False, 0, 0
    memory_shown = False  # P: the scratchpad shows her memory and the board, not the list
    picked, editing, notice, models = 0, None, "", None
    # Only one line is typed at a time (her chat, the terminal or a setting), so one caret serves all three.
    caret = 0
    repeating = False
    items = [("preset", label) for label in registry.PRESETS] + \
            [("setting", st) for st in registry.SETTINGS]

    def leave(keep):
        run.record("quit", kept=keep, day=w.day, steps=w.steps,
                   seconds=round(w.elapsed, 1))
        if keep:
            run.save_night(w)
            run.save_report(report.build(w))
        tape.close()
        if keep:
            print(f"kept {run.keep()}", flush=True)
        else:
            run.discard()
        pygame.quit()
        sys.exit()

    def place(text):
        """`place X Y [high|medium|low] [cost]` puts an objective on mapped ground.
        `place X Y interest COST TEXT` hides an interest. Returns (refusal, None) or (None, done)."""
        words = text.split()
        if len(words) >= 3 and words[2].lower() == "interest":
            if (len(words) < 5 or not all(t.lstrip("-").isdigit() for t in words[:2])
                    or not words[3].isdigit()):
                return "try  place 12 8 interest 30 a ring of dark glassy stones", None
            i, why = w.place_interest((int(words[0]), int(words[1])), " ".join(words[4:]),
                                      int(words[3]))
            return (why, None) if not i else (None, f"interest hidden at ({i.cell[0]},"
                                                    f"{i.cell[1]}), {i.cost} steps")
        nums = [t for t in words if t.lstrip("-").isdigit()]
        if len(nums) < 2:
            return "place needs a cell -- try  place 21 8 high 40", None
        cell = (int(nums[0]), int(nums[1]))
        priority = next((t for t in words if t.lower() in ("high", "medium", "low")),
                        "medium")
        cost = int(nums[2]) if len(nums) > 2 else 30
        if cost <= 0:
            return f"{cost} steps of work is not work", None
        o, why = w.place_objective(cell, priority.lower(), cost)
        if not o:
            return why, None
        return None, (f"placed objective {o.glyph} at ({cell[0]},{cell[1]}), {o.priority} "
                      f"priority, {o.cost} steps of work -- it is in her view")

    def by_day():
        """Whether what the desk types goes to her as the day's one urgent message."""
        return pilot.live and pilot.phase == "day" and pilot.wait != "radio"

    def board(verb, rest):
        """The orders board, from her chat. Returns the line for the pane. Every change is told
        to her (by day as the urgent message) and recorded, so a replay can post it again."""
        n = w.notes
        rest = rest.strip()
        if verb == "orders" and not rest:
            return ("the board is empty" if not n.orders else
                    "the board -- " + "   ".join(f"{i}. {t}" for i, t in
                                                 enumerate(n.orders, 1)))
        why = pilot.urgent_why_not(w) if by_day() else pilot.why_not()
        if why:
            return why
        if not by_day() and conv.busy:
            return "she is still talking -- wait until she has finished"
        if verb == "orders" and rest.lower() != "clear":
            return "/order <text> posts one order; /orders shows the board"
        if verb == "order" and not rest:
            return "/order needs the order -- e.g.  /order survey the north-west first"
        if verb == "order" and len(rest) > settings.ORDERS_CHARS:
            return (f"order refused -- {len(rest)} characters, and the cap is "
                    f"{settings.ORDERS_CHARS}. Say it shorter.")
        if verb == "orders":
            n.clear_orders()
            w.record("orders_cleared")
            told, said = "mission control has cleared the board", "the board is cleared"
        elif verb == "order":
            k = n.order(rest)
            w.record("order", n=k, text=rest)
            told, said = f"mission control posted order {k}: {rest}", f"order {k} posted"
        else:
            k = int(rest) if rest.isdigit() else 0
            text = n.retract(k)
            if text is None:
                return f"there is no order {rest or '?'} -- the board has {len(n.orders)}"
            w.record("retract", n=k, text=text)
            told, said = (f"mission control took down order {k}: {text}",
                          f"order {k} retracted: {text}")
        told = told[0].upper() + told[1:] + ". The board in your view is current."
        if by_day():
            pilot.send_urgent(conv, w, told)
            return f"{said} -- sent to her as the urgent message"
        pilot.say(conv, w, told)
        return f"{said} -- she is told"

    CHAT_HELP = [
        "words            at dawn and night, talk to her. By day, one urgent message",
        "/next [WORDS]    move on: dawn to day, dusk to night, night to the next sol, or "
        "close a radio line. WORDS go to her with whatever comes next",
        "/order TEXT      post an order on her board. /orders shows it",
        "/retract N       take order N down. /orders clear takes them all",
        "/status          the status line, as she reads it",
        "Your terminal (T) has the rest: comms, sols, place -- type help there."]

    def chat_line(text):
        """One line typed in her chat. Returns the pane's lines: why it did not go, or what it did."""
        if not text.startswith("/"):
            if by_day():
                why = pilot.send_urgent(conv, w, text)
                return [why or "urgent sent -- she reads it after the call in hand"]
            why = pilot.say(conv, w, text)
            return [why] if why else []
        word, _, rest = text.partition(" ")
        verb = word[1:].lower()
        if verb == "help":
            return CHAT_HELP
        if verb == "status":
            return [sight.status_line(w)]
        if verb in ("order", "orders", "retract"):
            return [board(verb, rest)]
        if verb == "next":
            why = pilot.next(rest)
            return [why] if why else []
        return [f"no such command: {word} -- /help lists them"]

    def await_rover(world, dirs):
        """Wait until the rover has driven the leg: the SPACE pause. goto runs on this thread, so
        this runs its own loop, drawing and reading keys, and takes only SPACE (or the quit question)."""
        if settings.ROVER_PAUSE != "key":
            return
        world.awaiting_rover = list(dirs)
        asking = False  # ESC asks the same keep-or-discard question as anywhere else
        try:
            while True:
                if term:
                    leave(True)
                for e in pygame.event.get():
                    if e.type == pygame.QUIT:
                        asking = True
                    if e.type != pygame.KEYDOWN:
                        continue
                    if asking:
                        asking = answer_quit(e)
                    elif e.key == pygame.K_SPACE:
                        return
                    elif e.key == pygame.K_ESCAPE:
                        asking = True
                clock.tick(config.FPS)
                render.draw_world(game, w, fonts, reel)
                if asking:
                    render.draw_quit(game, w, fonts, run, mission_over())
                render.draw_chat(pane, conv, w, fonts, said, typing, scroll,
                                 settings.SHOW_THINKING, reel, None, memory_shown, pilot, caret)
                pygame.display.flip()
        finally:
            world.awaiting_rover = None

    nav._await_rover = await_rover

    def mission_over():
        """The last sol is done, or the rover is lost. A length changed on the settings screen counts already."""
        sols = prefs.pending.get("MISSION_SOLS", settings.MISSION_SOLS)
        return w.day_over and (w.lost or bool(sols) and w.day >= sols)

    # With a window the end of the mission waits (`sols N` plays on, ESC finishes); headless, it is kept and ends.
    at_end = [False]

    def add_sols(rest):
        """The terminal's `sols N`: N more sols, this run only."""
        if not rest.strip().isdigit() or int(rest) < 1:
            return "sols needs a number of sols to add -- e.g.  sols 3", None
        if not settings.MISSION_SOLS and not prefs.pending.get("MISSION_SOLS"):
            return "this mission has no limit (--sols 0), so there is nothing to add to", None
        n = int(rest)
        settings.MISSION_SOLS = max(prefs.pending.pop("MISSION_SOLS", settings.MISSION_SOLS), w.day) + n
        at_end[0] = False
        run.record("mission_extended", sols=settings.MISSION_SOLS, added=n)
        return None, f"{n} more sol{'s' if n > 1 else ''} -- the mission now runs to sol " \
                     f"{settings.MISSION_SOLS}"

    def set_comms(rest):
        """The terminal's `comms on|off`, the same switch as C."""
        if rest.strip().lower() not in ("on", "off"):
            return f"comms are {'on' if settings.COMMS else 'off'} -- comms on, or comms off", None
        settings.COMMS = rest.strip().lower() == "on"
        return None, f"comms {'on: someone is at the desk' if settings.COMMS else 'off: nobody is'}"

    desk = {"comms": set_comms, "sols": add_sols, "place": place}

    def answer_quit(e):
        """K keeps the run, D discards it, ESC goes back. Returns whether still asking."""
        if e.key == pygame.K_k:
            leave(True)
        elif e.key == pygame.K_d:
            leave(False)
        return e.key != pygame.K_ESCAPE

    def nightfall():
        """The sol rolls over. Settings waiting for it go in force first, then the prompt is rebuilt.
        A replay does the operator's actions itself, before the rollover."""
        nonlocal conv, pilot
        notes = []
        if script:
            for done in script.operator(w, w.day):
                conv.write("status", f"operator, sol {w.day} -- {done}")
            script.use_settings(w.day + 1)
        else:
            changed = prefs.nightfall()
            notes = [f"{k} {registry.show(v)}" for k, v in changed.items()]
        prompts.use()
        run.save_night(w)  # a crash tomorrow still resumes from tonight
        run.save_report(report.build(w))
        w.next_day()
        log_settings(w.day)
        title()
        conv = talker()
        conv.ready = ready
        conv.open_day(w)
        pilot = autopilot.Autopilot(live=not script, attended=not headless(),
                                    words=pilot.words)
        if notes:
            conv.write("note", "settings from this sol: " + ", ".join(notes))

    def shift():
        """Someone sat down at the desk, or left it, mid-sol. The prompt is rebuilt and she is told."""
        at_desk[0] = settings.COMMS
        prompts.use()
        run.record("comms", sol=w.day, on=settings.COMMS, steps=w.steps,
                   prompt=hashlib.sha256(prompts.SYSTEM.encode()).hexdigest()[:12])
        conv.write("note", "comms on -- someone is at the desk, and she is told so"
                   if settings.COMMS else "comms off -- nobody is at the desk, and she is told so")
        title()

    def settings_key(e):
        """One key on the settings screen. Returns False when the screen closes."""
        nonlocal picked, editing, notice, caret
        kind, it = items[picked]
        locked = bool(script) and (kind == "preset" or it.tier != "now")
        if editing is not None:
            if e.key == pygame.K_ESCAPE:
                editing = None
            elif e.key == pygame.K_RETURN:
                notice = change(it, editing)
                editing = None
            else:
                editing, caret = edit(editing, caret, e)
            return True
        if e.key in (pygame.K_ESCAPE, pygame.K_o):
            return False
        if e.key in (pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s):
            d = -1 if e.key in (pygame.K_UP, pygame.K_w) else 1
            picked, notice = (picked + d) % len(items), ""
        elif locked and e.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d,
                                  pygame.K_RETURN, pygame.K_r):
            notice = "a replay runs on the kept run's settings; only 'now' ones change"
        elif kind == "preset" and e.key == pygame.K_RETURN:
            prefs.preset(it)
            notice = f"loaded {it}; each value lands on its own tier"
        elif kind == "setting" and e.key in (pygame.K_LEFT, pygame.K_a,
                                             pygame.K_RIGHT, pygame.K_d):
            d = -1 if e.key in (pygame.K_LEFT, pygame.K_a) else 1
            notice = change(it, it.nudge(prefs.shown(it), d))
        elif kind == "setting" and e.key == pygame.K_RETURN:
            editing = "" if prefs.shown(it) is None else str(prefs.shown(it))
            caret = len(editing)
        elif kind == "setting" and e.key == pygame.K_r:
            notice = change(it, it.default)
        return True

    def change(st, v):
        try:
            v = prefs.set(st.name, v)
        except ValueError as err:
            return f"{st.name} not changed: {err}"
        if st.name == "MODEL" and models is not None and v not in models:
            return f"{v} is not in `ollama list`; pull it before the next sol"
        return f"{st.name} {registry.show(v)} -- {registry.TIER_NAMES[st.tier]}"

    while True:
        if term:
            leave(True)
        dt = clock.tick(config.FPS) / 1000.0
        now = pygame.time.get_ticks()

        # Held keys repeat while a line is typed; otherwise WASD has its own repeat.
        wants = typing or mode == "console" or editing is not None
        if wants != repeating:
            if wants:
                pygame.key.set_repeat(settings.TYPE_REPEAT_DELAY_MS, settings.TYPE_REPEAT_MS)
            else:
                pygame.key.set_repeat()
            repeating = wants

        for e in pygame.event.get():
            if e.type == pygame.VIDEORESIZE:
                screen, game, pane = layout_surfaces(pygame.display.set_mode(
                    (max(960, e.w), max(640, e.h)), pygame.RESIZABLE))
                continue
            if mode == "world" and not typing:
                if dashboard.pad_event(e, game.get_width()):
                    continue
            if e.type == pygame.QUIT:
                mode, typing, held = "quit", False, None
            if e.type == pygame.KEYUP and e.key == held:
                held = None
            if e.type == pygame.MOUSEWHEEL:
                scroll = max(0, min(scroll_max, scroll + e.y * 3))
            # A click on a button is the same as pressing its key.
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and mode == "world" and not typing:
                key = dashboard.click(e.pos, game.get_size(), pane.get_size())
                if key is not None:
                    e = pygame.event.Event(pygame.KEYDOWN, key=key, unicode="")
            if e.type != pygame.KEYDOWN:
                continue

            # The quit question comes before everything, even the text field.
            if mode == "quit":
                if not answer_quit(e):
                    mode = "world"
                continue

            # Typing in her chat takes every key.
            if typing:
                if e.key == pygame.K_ESCAPE:
                    typing = False
                elif e.key == pygame.K_RETURN:
                    text = said.strip()
                    if text:
                        for note in chat_line(text):
                            conv.write("note", note)
                        said, caret, scroll = "", 0, 0
                else:
                    said, caret = edit(said, caret, e)
                continue

            # The terminal takes every key, or WASD would drive.
            if mode == "console":
                # T closes only on an empty line, so "goto" types fine.
                if e.key == pygame.K_ESCAPE or (e.key == pygame.K_t and not line):
                    mode, held, line = "world", None, ""
                elif e.key == pygame.K_RETURN:
                    if line.strip():
                        history.extend(console.run(w, line, desk))
                        del history[:-40]
                    line, caret = "", 0
                else:
                    line, caret = edit(line, caret, e)
                continue

            if mode == "settings":
                if not settings_key(e):
                    mode, editing = "world", None
                continue

            # Looking at the view takes every key, or the arrows would drive.
            if mode == "view":
                if e.key in (pygame.K_v, pygame.K_ESCAPE):
                    mode, scroll = "world", 0
                continue

            if e.key in DIRS:
                held, next_step = e.key, now + settings.MOVE_DELAY_MS
                if mode == "world":
                    # Driving by hand cuts the drawing short.
                    reel.skip()
                    reel.destination = None  # a drive by hand has no target to label
                    w.move(*DIRS[e.key])
                else:
                    cursor = clamp_cursor(cursor, DIRS[e.key], w.here)

            elif mode == "world":
                if e.key == pygame.K_SPACE:
                    reel.skip()
                elif e.key == pygame.K_m:
                    mode, cursor = "map", w.pos
                elif e.key == pygame.K_x:
                    w.toggle_mark()
                elif e.key == pygame.K_t:
                    mode, held, caret = "console", None, 0
                elif e.key == pygame.K_q and w.phase == "day":
                    w.day_over = True
                elif e.key == pygame.K_TAB:
                    typing, held, caret = True, None, len(said)
                elif e.key == pygame.K_h:
                    settings.SHOW_THINKING = not settings.SHOW_THINKING
                    scroll = 0
                elif e.key == pygame.K_p:
                    memory_shown = not memory_shown
                # C: sit down at the desk, or leave it, for this run only.
                elif e.key == pygame.K_c:
                    settings.COMMS = not settings.COMMS
                elif e.key == pygame.K_o:
                    mode, held, notice = "settings", None, ""
                    models = ollama.installed_models()
                    registry.BY_NAME["MODEL"].choices = models
                # V shows the exact view she was last sent; V again hides it.
                elif e.key == pygame.K_v:
                    mode, scroll = "view", 0
                elif e.key == pygame.K_ESCAPE:
                    mode, held = "quit", None

            elif mode == "map":
                if e.key == pygame.K_x:
                    w.toggle_mark(cursor)
                elif e.key in (pygame.K_m, pygame.K_ESCAPE):
                    mode = "world"

        # hold-to-drive repeat
        if held and now >= next_step and not typing:
            keys = pygame.key.get_pressed()
            if keys[held]:
                next_step = now + settings.MOVE_REPEAT_MS
                if mode == "world":
                    reel.destination = None
                    w.move(*DIRS[held])
                elif mode == "map":
                    cursor = clamp_cursor(cursor, DIRS[held], w.here)
            else:
                held = None

        w.tick(dt)
        reel.tick(dt)

        render.draw_world(game, w, fonts, reel)
        if mode == "console":
            render.draw_console(game, w, fonts, line, history, caret)
        elif mode == "quit":
            render.draw_quit(game, w, fonts, run, mission_over())

        # Pumped every frame; `conv.ready` above is what holds the next request back.
        conv.pump()
        if settings.COMMS != at_desk[0]:
            shift()
        # Held while the desk is deciding whether to quit, though the day's clock runs on. A
        # replay plays every sol its tape holds.
        if mode == "quit":
            pilot.run_clock(w)  # the day's clock does not stop for the question
        else:
            if (pilot.tick(conv, w, typing=typing) == "night"
                    and not (script and script.spent)):
                if script or not mission_over():
                    nightfall()
                    scroll = 0
                elif headless():
                    leave(True)
                elif not at_end[0]:
                    at_end[0] = True
                    run.save_night(w)  # kept on disk, whatever is pressed next
                    run.save_report(report.build(w))
                    conv.write("note", "the rover is lost -- ESC to finish" if w.lost else
                               "the mission is over -- `sols N` in your terminal (T) for "
                               "more, or ESC to finish")
        scroll_max = render.draw_chat(pane, conv, w, fonts, said, typing, scroll,
                                      settings.SHOW_THINKING, reel,
                                      sight.view(w) if mode == "view" else None, memory_shown,
                                      pilot, caret)
        if mode == "map":
            render.draw_map(screen, w, fonts, cursor, reel)
        if mode == "settings":
            render.draw_settings(screen, fonts, items, picked, prefs, editing, notice,
                                 models, bool(script), caret)
        pygame.display.flip()


def clamp_cursor(cursor, d, area):
    return (max(0, min(area.w - 1, cursor[0] + d[0])),
            max(0, min(area.h - 1, cursor[1] + d[1])))


if __name__ == "__main__":
    main()
