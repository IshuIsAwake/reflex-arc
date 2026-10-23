"""Run me:  .venv/bin/python game/main.py [--arena 30|50] [--map grid|rle] [--sols N]
                                        [--model TAG] [--think] [--replay runs/<stamp>]
                                        [--comms on|off] [--objectives manual|auto]
                                        [--preset design] [--outage N]

TAB her chat (/help lists its commands)   T your terminal (help lists its commands)
C comms on / off   Q end the day now
V what she sees   H hide/show her reasoning   P her memory, or her list   O settings
WASD drive (hold to keep going)   M map   X mark   ESC quit
SPACE the rover has finished the leg -- with ROVER_PAUSE key

Settings come from `registry.py`: the code's defaults, then `user_settings.json`, then
flags for this launch. README.md says when each kind of change lands.

A Martian plain, a landing pad at the centre, and gemma in the pane on the right. The
rover maps what it drives past, out to `VISION_RADIUS`, and that is the only thing that
lifts fog -- Ingenuity is cut, so a sol of driving is the only way the map fills in.

**Three things are written down, and they differ by who holds the pen.** She keeps a
list that `todo` adds to and `strike` crosses off, cleared when dusk ends, and a
memory of named entries that `remember` writes and `forget` drops, which the night does
not take. The third is the operator's board, posted to from her chat and read-only to her.

**Two places to type.** Her chat (TAB) is for talking to her: words at dawn and night,
one urgent message by day, an answer when she radios, and /next, /order, /orders,
/retract, /status, /help. The terminal (T) runs the mission and the game: comms, sols,
place, and goto / distance / execute for playing by hand.

**A sol is dawn, day, dusk and night**, and `--sols 3` is three of them from one launch.
With someone at the desk each phase but the day waits for them; with nobody there, or no
window, each moves on by itself. `autopilot.py` says how.

**Live and replay.** Live, the model decides. `--replay` re-issues a kept run's calls
with no model in the loop and halts if the world stops matching the tape -- so a sol
that came out well is the demo, played back exactly. `replay.py` says why.

No human-only mode: the planner is the point.
"""

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
import config as C
import console
import logs
import nav
import registry
import render
import replay
import report
import settings as S
import sight
from world import World

def headless():
    """No window: nobody is watching, so nobody is at the desk and nobody is there to
    say whether the mission goes on."""
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
    """Puts every setting in force before anything reads one.

    Returns (args, script, carried): `carried` is the night a resumed run wakes from.

    The order is the precedence: the code's defaults, then the person's saved settings,
    then flags for this launch only, then -- on a replay -- the kept run's own values,
    which win because a replay under different settings is a different run.

    `--think` sets the trace and the sampler together, because a reasoning trace that
    starts repeating at temperature 0 has no noise to climb out with.
    """
    p = argparse.ArgumentParser(prog="game/main.py")
    p.add_argument("--map", choices=("grid", "rle"),
                   help="how the map is written into the view")
    p.add_argument("--arena", choices=tuple(C.ARENAS), help="which arena to land on")
    p.add_argument("--prompt", choices=tuple(prompts.PROMPTS), default=prompts.DEFAULT,
                   help=f"which system prompt to run (default: {prompts.DEFAULT})")
    p.add_argument("--model", help="any tag `ollama list` shows, or a `-cloud` one")
    p.add_argument("--executor", choices=("teleport", "plan"),
                   help="what a goto does; 'plan' writes the route and moves nothing")
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
    for w in prefs.warnings:
        print("settings:", w)
    if args.preset:
        registry.apply(registry.PRESETS[args.preset])
    S.OUTAGE_SOLS = tuple(args.outage or ())
    # With no window, nobody is at the desk unless the flag says so.
    comms = args.comms == "on" if args.comms else False if headless() else None
    flags = {"MAP_FORMAT": args.map, "APP_ARENA": args.arena, "MODEL": args.model,
             "EXECUTOR": args.executor, "ROVER_PAUSE": args.pause,
             "MISSION_SOLS": args.sols, "COMMS": comms, "OBJECTIVES": args.objectives}
    bad = registry.apply({k: v for k, v in flags.items() if v is not None})
    if bad:
        p.error(f"out of range: {', '.join(bad)}")
    if args.think:
        S.MODEL_THINK = True
        S.MODEL_TEMP = None

    # Loaded before pygame opens a window: a run directory that is missing or has no
    # calls in it should say so at the prompt, not behind a window that then closes.
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

    # Before anything reads `config` -- the window is sized off it and so is the world.
    C.use(C.APP_ARENA)
    # Last: the prompt is built from the arena, the map format and the turn caps.
    prompts.use(args.prompt)
    return args, script, carried


def main():
    prefs = registry.Prefs()
    args, script, carried = read_flags(sys.argv[1:], prefs)
    pygame.init()

    def title():
        """The map format is here because nothing else on screen tells the two arms
        apart. Rewritten at nightfall, when the model or the format may change."""
        pygame.display.set_caption(
            f"ANGARAKA -- prototype 11  ·  {C.VIEW_W}x{C.VIEW_H}  ·  {S.MAP_FORMAT} map"
            + (f"  ·  replay of {pathlib.Path(args.replay).name}" if args.replay else
               f"  ·  {S.MODEL}")
            + ("  ·  thinking" if S.MODEL_THINK else "")
            + ("  ·  comms on" if S.COMMS else "  ·  comms off"))

    title()
    clock = pygame.time.Clock()
    fonts = render.Fonts()

    def layout_surfaces(display):
        """The window, and the arena's and the pane's parts of it, sized off it."""
        game_rect, pane_rect = render.layout(*display.get_size())
        return display, display.subsurface(game_rect), display.subsurface(pane_rect)

    # The window fills the desktop, less its border and the taskbar, and can be dragged to
    # any size from there.
    desktop = pygame.display.get_desktop_sizes()[0]
    screen, game, pane = layout_surfaces(pygame.display.set_mode(
        (max(960, desktop[0] - S.SCREEN_RESERVE_W), max(640, desktop[1] - S.SCREEN_RESERVE_H)),
        pygame.RESIZABLE))

    # The run starts recording immediately. Whether it is kept is asked at the end;
    # see logs.py for why that order and not the other one.
    runs = pathlib.Path(__file__).resolve().parent.parent / "runs"
    run = logs.Run(runs, headless=headless())

    # SIGTERM keeps the run and exits. SDL would turn it into a window-close, which asks
    # K / D / ESC -- and a headless run has nobody to answer, so it waited for ever.
    # Installed after the window opens, so this replaces SDL's handler.
    term = []
    signal.signal(signal.SIGTERM, lambda *_: term.append(True))

    def log_settings(sol):
        """Every setting in force, and a hash of the prompt they built, once a sol.
        Two runs of one probe once scored 22% and 56% and nothing on either tape said
        which prompt they had been asked under. Replay reads these rows back."""
        run.record("settings", sol=sol, values=registry.snapshot(),
                   prompt=hashlib.sha256(prompts.SYSTEM.encode()).hexdigest()[:12])

    w = World(recorder=run.record, carried=carried)
    if S.OUTAGE_SOLS:
        # Staged, and the tape says so: a run whose sol 2 was answered by the fallback
        # because someone asked for it is not evidence of an outage.
        run.record("outage", sols=list(S.OUTAGE_SOLS), model=S.MODEL,
                   fallback=S.MODEL_FALLBACK)
    if args.resume:
        run.save_start(carried, pathlib.Path(args.resume).resolve().name)
    elif script and script.start:
        run.save_start(script.start, pathlib.Path(args.replay).resolve().name)
    log_settings(w.day)
    nav.clear_plan(w)   # this session's route file starts empty, never yesterday's
    tape = chat.Tape(run.chat_path)
    # Which model answers. One for the run: an outage does not end at nightfall.
    link = chat.Link()

    def talker():
        """The thing on the other end of the pane: Ollama, or a kept run.

        One function so the two construction sites below cannot drift -- a replay whose
        second sol quietly went back to asking the model would be the hardest kind of
        wrong to see, because it would look exactly right until the bill arrived.
        """
        if script:
            return replay.Replay(w, script, tape)
        return chat.Conversation(w, tape, link)

    conv = talker()
    conv.open_day(w)

    reel = anim.Reel(w)
    # **The planner waits for the rover.** No request goes out while a drive is still
    # being drawn, so gemma sees the outcome of one call before it can make the next.
    # It costs wall clock and that is the point: a planner seconds away from the body
    # it drives is the architecture, and here you can watch it happen.
    #
    # The rover also sits still for `SETTLE_SECONDS` after the drawing stops. A 31B
    # answers in under two seconds, so without a pause the sol is a burst of teleports
    # with nothing legible between them. `settle` holds the earliest moment the next
    # request may go out, and is pushed forward for as long as anything is moving.
    settle = [0.0]

    def ready():
        now = time.monotonic()
        if reel.busy:
            settle[0] = now + S.SETTLE_SECONDS
            return False
        return now >= settle[0]

    conv.ready = ready
    # The clock, and the desk's windows. One per sol. A replay's never waits, and nor does
    # a run with no window: nobody is there.
    pilot = autopilot.Autopilot(live=not script, attended=not headless())
    # Whether anyone was at the desk last frame. C and the settings screen both change
    # COMMS, and both land at once, so the change is noticed here rather than at either.
    at_desk = [S.COMMS]
    mode = "world"
    cursor = w.pos
    held = None
    next_step = 0
    line, history = "", []
    said, typing, scroll, scroll_max = "", False, 0, 0
    memory_shown = False    # P: the scratchpad shows her memory and the board, not the list
    picked, editing, notice, models = 0, None, "", None
    # Where the caret sits in the line being typed. Only one line is typed at a time --
    # her chat, the terminal or a setting's value -- so one caret serves all three.
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
        """`place X Y [high|medium|low] [cost]` -- an objective, on mapped ground, which
        she sees at once. `place X Y interest COST TEXT` -- an interest, hidden until the
        rover sees it again, and TEXT is what examining it finds.

        The refusal wording comes back from the world rather than being written again
        here: the guard and the explanation of the guard belong together.
        """
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
        """The orders board, from her chat. Returns the line for the pane.

        Mission control, not conversation: it goes to its own store, which the night does
        not clear. Refused rather than cut when too long, for the same reason `remember`
        is. Every change is told to her -- by day as the one urgent message, otherwise as
        a line she can answer -- and goes on the tape as its own row, which is how a
        replay posts it again before the same call.
        """
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
        if verb == "order" and len(rest) > S.ORDERS_CHARS:
            return (f"order refused -- {len(rest)} characters, and the cap is "
                    f"{S.ORDERS_CHARS}. Say it shorter.")
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
        """One line typed in her chat. Returns the pane's lines: why it did not go, or
        what it did. Empty when it went to her as words."""
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
        """Hold everything until the operator says the rover has driven the leg.

        `nav.goto` runs on this thread -- `chat._run` is deliberately main-thread, so a
        drive cannot land halfway through a redraw -- which means waiting here stops the
        game loop, redraw and events included. So this runs its own: it draws each frame
        and reads the keyboard itself, and takes only the key that ends the wait. The
        world must not change while the robot is a leg behind it, and refusing every
        other key is what guarantees that rather than hoping nothing is pressed.

        The screen still shows the rover where it was before this `goto`: the drive is
        animated from `world.reel` once the call returns. On the floor the machine is
        moving, which is the thing actually worth watching, and the HUD says what it
        was sent.
        """
        if S.ROVER_PAUSE != "key":
            return
        world.awaiting_rover = list(dirs)
        asking = False      # ESC asks the same keep-or-discard question as anywhere else
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
                clock.tick(C.FPS)
                render.draw_world(game, w, fonts, reel)
                if asking:
                    render.draw_quit(game, w, fonts, run, mission_over())
                render.draw_chat(pane, conv, w, fonts, said, typing, scroll,
                                 S.SHOW_THINKING, reel, None, memory_shown, pilot, caret)
                pygame.display.flip()
        finally:
            world.awaiting_rover = None

    nav._await_rover = await_rover

    def mission_over():
        """The last sol is done, or the rover is lost: too little charge ever to reach
        the pad again, which is the only thing that recharges it. A length changed on the
        settings screen counts already, though it lands at nightfall."""
        sols = prefs.pending.get("MISSION_SOLS", S.MISSION_SOLS)
        return w.day_over and (w.lost or bool(sols) and w.day >= sols)

    # With a window, the end of the mission is a pause, not an exit: `sols N` in the
    # terminal plays on, ESC finishes. Headless, nobody is there to choose, so the run is
    # kept and ends.
    at_end = [False]

    def add_sols(rest):
        """The terminal's `sols N`: N more sols, this run only, like C."""
        if not rest.strip().isdigit() or int(rest) < 1:
            return "sols needs a number of sols to add -- e.g.  sols 3", None
        if not S.MISSION_SOLS and not prefs.pending.get("MISSION_SOLS"):
            return "this mission has no limit (--sols 0), so there is nothing to add to", None
        n = int(rest)
        S.MISSION_SOLS = max(prefs.pending.pop("MISSION_SOLS", S.MISSION_SOLS), w.day) + n
        at_end[0] = False
        run.record("mission_extended", sols=S.MISSION_SOLS, added=n)
        return None, f"{n} more sol{'s' if n > 1 else ''} -- the mission now runs to sol " \
                     f"{S.MISSION_SOLS}"

    def set_comms(rest):
        """The terminal's `comms on|off` -- the same switch as C."""
        if rest.strip().lower() not in ("on", "off"):
            return f"comms are {'on' if S.COMMS else 'off'} -- comms on, or comms off", None
        S.COMMS = rest.strip().lower() == "on"
        return None, f"comms {'on: someone is at the desk' if S.COMMS else 'off: nobody is'}"

    desk = {"comms": set_comms, "sols": add_sols, "place": place}

    def answer_quit(e):
        """K keeps the run, D discards it, ESC goes back. Returns whether still asking."""
        if e.key == pygame.K_k:
            leave(True)
        elif e.key == pygame.K_d:
            leave(False)
        return e.key != pygame.K_ESCAPE

    def nightfall():
        """The sol rolls over. Settings waiting for it go in force first, then the
        prompt is rebuilt from them, so the new sol's planner is told the new numbers.

        A replay does the operator's half itself, and does it *before* the rollover:
        orders typed at nightfall are what the next sol opens holding.
        """
        nonlocal conv, pilot
        notes = []
        if script:
            for done in script.operator(w, w.day):
                conv.write("status", f"operator, sol {w.day} -- {done}")
            script.use_settings(w.day + 1)
        else:
            changed = prefs.nightfall()
            notes = [f"{k} {registry.show(v)}" for k, v in changed.items()]
        prompts.use(args.prompt)
        run.save_night(w)     # a crash tomorrow still resumes from tonight
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
        """Someone sat down at the desk, or left it, mid-sol. The prompt is rebuilt now
        and swapped in at her next turn (`Conversation._on_shift`). An open line closes
        on the clock's next tick if nobody is left on it."""
        at_desk[0] = S.COMMS
        prompts.use(args.prompt)
        run.record("comms", sol=w.day, on=S.COMMS, steps=w.steps,
                   prompt=hashlib.sha256(prompts.SYSTEM.encode()).hexdigest()[:12])
        conv.write("note", "comms on -- someone is at the desk, and she is told so"
                   if S.COMMS else "comms off -- nobody is at the desk, and she is told so")
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
        dt = clock.tick(C.FPS) / 1000.0
        now = pygame.time.get_ticks()

        # Held keys repeat while a line is being typed, so holding backspace keeps
        # deleting. Off the rest of the time: WASD has its own repeat, and both at once
        # would drive two cells for one.
        wants = typing or mode == "console" or editing is not None
        if wants != repeating:
            if wants:
                pygame.key.set_repeat(S.TYPE_REPEAT_DELAY_MS, S.TYPE_REPEAT_MS)
            else:
                pygame.key.set_repeat()
            repeating = wants

        for e in pygame.event.get():
            if e.type == pygame.VIDEORESIZE:
                screen, game, pane = layout_surfaces(pygame.display.set_mode(
                    (max(960, e.w), max(640, e.h)), pygame.RESIZABLE))
                continue
            if mode == "world" and not typing:
                if render.D.pad_event(e, game.get_width()):
                    continue
            if e.type == pygame.QUIT:
                mode, typing, held = "quit", False, None
            if e.type == pygame.KEYUP and e.key == held:
                held = None
            if e.type == pygame.MOUSEWHEEL:
                scroll = max(0, min(scroll_max, scroll + e.y * 3))
            # A click on a button is the same as pressing its key.
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and mode == "world" and not typing:
                key = render.D.click(e.pos, game.get_size(), pane.get_size())
                if key is not None:
                    e = pygame.event.Event(pygame.KEYDOWN, key=key, unicode="")
            if e.type != pygame.KEYDOWN:
                continue

            # The quit question outranks everything, including the text field, or
            # closing the window while mid-sentence would type into it.
            if mode == "quit":
                if not answer_quit(e):
                    mode = "world"
                continue

            # Typing to gemma eats every key, the same way the console does.
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

            # The console eats every key, or WASD would drive instead of typing.
            if mode == "console":
                # T closes only on an empty line, so "goto" and "distance" type fine.
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

            # Looking at the view eats every key, the way the console does, or the arrow
            # keys would drive the rover out from under the block being read.
            if mode == "view":
                if e.key in (pygame.K_v, pygame.K_ESCAPE):
                    mode, scroll = "world", 0
                continue

            if e.key in DIRS:
                held, next_step = e.key, now + S.MOVE_DELAY_MS
                if mode == "world":
                    # Taking the wheel cuts the replay short rather than fighting it
                    # for where the rover is drawn.
                    reel.skip()
                    reel.destination = None     # a drive by hand has no target to label
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
                # Her chat always opens: what can reach her is the window's to say, and
                # the commands in it are refused out loud when they cannot.
                elif e.key == pygame.K_TAB:
                    typing, held, caret = True, None, len(said)
                elif e.key == pygame.K_h:
                    S.SHOW_THINKING = not S.SHOW_THINKING
                    scroll = 0
                elif e.key == pygame.K_p:
                    memory_shown = not memory_shown
                # Sit down at the desk, or leave it. For this run only: the setting on
                # the settings screen is the one that is saved.
                elif e.key == pygame.K_c:
                    S.COMMS = not S.COMMS
                elif e.key == pygame.K_o:
                    mode, held, notice = "settings", None, ""
                    models = chat.installed_models()
                    registry.BY_NAME["MODEL"].choices = models
                # V overlays the view block; V again puts it away. A thing you open to
                # look at is a mode, not a message -- appending it instead once put
                # twenty-two copies of four thousand characters into one tape. Nothing is
                # written down here: every view gemma was sent is already a `view` row.
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
                next_step = now + S.MOVE_REPEAT_MS
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

        # Pumped every frame now: the hold lives in `conv.ready` above, which stops the
        # next *request* rather than the whole loop. Streaming text keeps arriving while
        # the rover drives, and no world change can slip in because nothing has been
        # asked for yet.
        conv.pump()
        if S.COMMS != at_desk[0]:
            shift()
        # Held while the desk is typing or deciding whether to quit: a word put in is not
        # talked over, a line does not close under it, and the run is not kept from under
        # the question. A replay plays every sol its tape holds, however long the mission
        # was when it was kept, and stops at the end of its last one.
        if mode == "quit":
            pilot.run_clock(w)      # the day's clock does not stop for the question
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
                    run.save_night(w)     # kept on disk, whatever is pressed next
                    run.save_report(report.build(w))
                    conv.write("note", "the rover is lost -- ESC to finish" if w.lost else
                               "the mission is over -- `sols N` in your terminal (T) for "
                               "more, or ESC to finish")
        scroll_max = render.draw_chat(pane, conv, w, fonts, said, typing, scroll,
                                      S.SHOW_THINKING, reel,
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
