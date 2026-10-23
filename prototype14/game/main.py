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
import config
import console
import dashboard
import desk
import logs
import nav
import ollama
import prompts
import registry
import render
import replay
import report
import settings
import sight
from world import World

RUNS = pathlib.Path(__file__).resolve().parent.parent / "runs"

DIRS = {pygame.K_w: (0, -1), pygame.K_s: (0, 1), pygame.K_a: (-1, 0), pygame.K_d: (1, 0),
        pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1), pygame.K_LEFT: (-1, 0),
        pygame.K_RIGHT: (1, 0)}


def headless():
    """No window: nobody is watching, so nobody is at the desk."""
    return os.environ.get("SDL_VIDEODRIVER") == "dummy"


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
    p.add_argument("--pause", choices=registry.BY_NAME["ROVER_PAUSE"].choices,
                   help="who says the rover finished a leg; 'key' is SPACE at every pause")
    p.add_argument("--sols", type=int, help="sols in the mission; 0 is no limit")
    p.add_argument("--comms", choices=("on", "off"),
                   help="whether anyone is at the desk to talk to her; a run with no "
                        "window starts with it off")
    p.add_argument("--objectives", choices=registry.BY_NAME["OBJECTIVES"].choices,
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
    comms = None
    if args.comms:
        comms = args.comms == "on"
    elif headless():
        comms = False
    flags = {"APP_ARENA": args.arena, "MODEL": args.model, "ROVER_PAUSE": args.pause,
             "MISSION_SOLS": args.sols, "COMMS": comms, "OBJECTIVES": args.objectives}
    given = {}
    for name, value in flags.items():
        if value is not None:
            given[name] = value
    bad = registry.apply(given)
    if bad:
        p.error(f"out of range: {', '.join(bad)}")
    if args.think:
        settings.MODEL_THINK = True
        settings.MODEL_TEMP = None

    # Loaded before the window opens, so a bad run directory is reported at the prompt.
    script = None
    carried = None
    if args.replay:
        script = replay.load(pathlib.Path(args.replay))
        script.use_settings(script.first_sol)
        carried = script.start
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


def prompt_hash():
    return hashlib.sha256(prompts.SYSTEM.encode()).hexdigest()[:12]


def space_ends_pause(e):
    """Whether a SPACE ends the rover pause. While the real rover drives (Level 3), only the
    SPACE Level 3 posts for it, marked rover=True, does; one from the keyboard is ignored."""
    if e.dict.get("rover"):
        return True
    if nav.rover_driving and nav.rover_driving():
        print("[rover] (SPACE ignored -- the rover is still driving)")
        return False
    return True


def clamp_cursor(cursor, d, area):
    return (max(0, min(area.w - 1, cursor[0] + d[0])),
            max(0, min(area.h - 1, cursor[1] + d[1])))


class Game:
    """Everything one session holds: the run, the world, the conversation, and what the
    screen is showing. One per launch."""

    def __init__(self, args, script, carried, prefs):
        self.args = args
        self.script = script  # the kept run being replayed, or None
        self.prefs = prefs
        self.title()
        self.clock = pygame.time.Clock()
        self.fonts = render.Fonts()
        # The window fills the desktop, less its border and the taskbar.
        desktop = pygame.display.get_desktop_sizes()[0]
        self.resize(max(960, desktop[0] - settings.SCREEN_RESERVE_W),
                    max(640, desktop[1] - settings.SCREEN_RESERVE_H))

        # The run is recorded from the start; whether it is kept is asked at the end.
        self.run = logs.Run(RUNS, headless=headless())
        # SIGTERM keeps the run and exits. SDL would turn it into the K/D/ESC question, which
        # a headless run has nobody to answer.
        self.terminated = False
        signal.signal(signal.SIGTERM, self.on_sigterm)

        self.world = World(recorder=self.run.record, carried=carried)
        if settings.OUTAGE_SOLS:
            # A staged outage goes on the tape, so it is never mistaken for a real one.
            self.run.record("outage", sols=list(settings.OUTAGE_SOLS), model=settings.MODEL,
                            fallback=settings.MODEL_FALLBACK)
        if args.resume:
            self.run.save_start(carried, pathlib.Path(args.resume).resolve().name)
        elif script and script.start:
            self.run.save_start(script.start, pathlib.Path(args.replay).resolve().name)
        self.log_settings()
        nav.clear_plan(self.world)  # the route file starts empty, never with yesterday's leg
        self.tape = chat.Tape(self.run.chat_path)
        # Which model answers. One for the run: an outage does not end at nightfall.
        self.link = ollama.Link()
        self.reel = anim.Reel(self.world)
        # The earliest time the next request may go out (see ready).
        self.settle_until = 0.0
        self.conv = self.new_conversation()
        self.conv.open_day(self.world)
        # The clock and the desk's windows, new every sol. A replay or a headless run never waits.
        self.pilot = autopilot.Autopilot(live=not script, attended=not headless())
        # Whether anyone was at the desk last frame, so a change from C or the settings screen
        # is noticed.
        self.at_desk = settings.COMMS
        self.at_end = False  # the mission is over and waiting for `sols N` or ESC
        nav.wait_for_rover = self.await_rover

        self.mode = "world"  # or "map", "console", "settings", "view", "quit"
        self.typing = False  # in her chat (TAB)
        self.cursor = self.world.pos  # the map's cursor
        self.held = None  # the direction key held down
        self.next_step = 0  # when a held key drives again
        self.said = ""  # the line being typed in her chat
        self.line = ""  # the line being typed in the terminal
        self.history = []  # the terminal's lines
        self.scroll = 0
        self.scroll_max = 0
        self.memory_shown = False  # P: the scratchpad shows her memory and the board, not the list
        self.picked = 0  # the settings screen's chosen row
        self.editing = None  # the settings value being typed, or None
        self.notice = ""  # the settings screen's last message
        self.models = None  # `ollama list`, read when the settings screen opens
        # Only one line is typed at a time (her chat, the terminal or a setting), so one
        # caret serves all three.
        self.caret = 0
        self.repeating = False  # whether held keys repeat right now
        self.items = []  # the settings screen's rows: the presets, then every setting
        for label in registry.PRESETS:
            self.items.append(("preset", label))
        for setting in registry.SETTINGS:
            self.items.append(("setting", setting))
        self.desk = {"comms": desk.set_comms, "sols": self.add_sols, "place": self.place}

    def title(self):
        """Rewritten at nightfall, when the model may change."""
        text = f"ANGARAKA -- prototype 14  ·  {config.VIEW_W}x{config.VIEW_H}"
        if self.args.replay:
            text += f"  ·  replay of {pathlib.Path(self.args.replay).name}"
        else:
            text += f"  ·  {settings.MODEL}"
        if settings.MODEL_THINK:
            text += "  ·  thinking"
        if settings.COMMS:
            text += "  ·  comms on"
        else:
            text += "  ·  comms off"
        pygame.display.set_caption(text)

    def resize(self, width, height):
        """The window, and the arena's and the pane's parts of it."""
        self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
        arena_rect, pane_rect = render.layout(*self.screen.get_size())
        self.arena = self.screen.subsurface(arena_rect)
        self.pane = self.screen.subsurface(pane_rect)

    def on_sigterm(self, signum, frame):
        self.terminated = True

    def log_settings(self):
        """Every setting in force, and a hash of the prompt they built, once a sol."""
        self.run.record("settings", sol=self.world.day, values=registry.snapshot(),
                        prompt=prompt_hash())

    def new_conversation(self):
        """The other end of the chat: Ollama, or a kept run."""
        if self.script:
            conv = replay.Replay(self.world, self.script, self.tape)
        else:
            conv = chat.Conversation(self.world, self.tape, self.link)
        conv.ready = self.ready
        return conv

    def ready(self):
        """The planner waits for the rover: no request goes out while a drive is still being
        drawn, and for SETTLE_SECONDS after, so each drive can be seen."""
        now = time.monotonic()
        if self.reel.busy:
            self.settle_until = now + settings.SETTLE_SECONDS
            return False
        return now >= self.settle_until

    def leave(self, keep):
        world = self.world
        self.run.record("quit", kept=keep, day=world.day, steps=world.steps,
                        seconds=round(world.elapsed, 1))
        if keep:
            self.run.save_night(world)
            self.run.save_report(report.build(world))
        self.tape.close()
        if keep:
            print(f"kept {self.run.keep()}", flush=True)
        else:
            self.run.discard()
        pygame.quit()
        sys.exit()

    def answer_quit(self, e):
        """K keeps the run, D discards it, ESC goes back. Returns whether still asking."""
        if e.key == pygame.K_k:
            self.leave(True)
        elif e.key == pygame.K_d:
            self.leave(False)
        return e.key != pygame.K_ESCAPE

    def mission_over(self):
        """The last sol is done, or the rover is lost. A length changed on the settings
        screen counts already."""
        world = self.world
        sols = self.prefs.pending.get("MISSION_SOLS", settings.MISSION_SOLS)
        return world.day_over and (world.lost or bool(sols) and world.day >= sols)

    def place(self, text):
        return desk.place(self.world, text)

    def add_sols(self, rest):
        """The terminal's `sols N`: N more sols, this run only."""
        if not rest.strip().isdigit() or int(rest) < 1:
            return "sols needs a number of sols to add -- e.g.  sols 3", None
        if not settings.MISSION_SOLS and not self.prefs.pending.get("MISSION_SOLS"):
            return "this mission has no limit (--sols 0), so there is nothing to add to", None
        n = int(rest)
        sols = self.prefs.pending.pop("MISSION_SOLS", settings.MISSION_SOLS)
        settings.MISSION_SOLS = max(sols, self.world.day) + n
        self.at_end = False
        self.run.record("mission_extended", sols=settings.MISSION_SOLS, added=n)
        if n > 1:
            return None, f"{n} more sols -- the mission now runs to sol {settings.MISSION_SOLS}"
        return None, f"{n} more sol -- the mission now runs to sol {settings.MISSION_SOLS}"

    def await_rover(self, world, dirs):
        """The SPACE pause: wait until the rover has driven the leg. goto runs on this thread,
        so this runs its own loop, drawing and reading keys, and takes only SPACE (or the quit
        question)."""
        if settings.ROVER_PAUSE != "key":
            return
        world.awaiting_rover = list(dirs)
        asking = False  # ESC asks the same keep-or-discard question as anywhere else
        try:
            while True:
                if self.terminated:
                    self.leave(True)
                for e in pygame.event.get():
                    if e.type == pygame.QUIT:
                        asking = True
                    if e.type != pygame.KEYDOWN:
                        continue
                    if asking:
                        asking = self.answer_quit(e)
                    elif e.key == pygame.K_SPACE:
                        if space_ends_pause(e):
                            return
                    elif e.key == pygame.K_ESCAPE:
                        asking = True
                self.clock.tick(config.FPS)
                render.draw_world(self.arena, self.world, self.fonts, self.reel)
                if asking:
                    render.draw_quit(self.arena, self.world, self.fonts, self.run,
                                     self.mission_over())
                render.draw_chat(self.pane, self.conv, self.world, self.fonts, self.said,
                                 self.typing, self.scroll, settings.SHOW_THINKING, self.reel,
                                 None, self.memory_shown, self.pilot, self.caret)
                pygame.display.flip()
        finally:
            world.awaiting_rover = None

    def nightfall(self):
        """The sol rolls over. Settings waiting for it go in force first, then the prompt is
        rebuilt. A replay does the operator's actions itself, before the rollover."""
        world = self.world
        notes = []
        if self.script:
            for done in self.script.operator(world, world.day):
                self.conv.write("status", f"operator, sol {world.day} -- {done}")
            self.script.use_settings(world.day + 1)
        else:
            changed = self.prefs.nightfall()
            for name, value in changed.items():
                notes.append(f"{name} {registry.show(value)}")
        prompts.use()
        self.run.save_night(world)  # a crash tomorrow still resumes from tonight
        self.run.save_report(report.build(world))
        world.next_day()
        self.log_settings()
        self.title()
        self.conv = self.new_conversation()
        self.conv.open_day(world)
        self.pilot = autopilot.Autopilot(live=not self.script, attended=not headless(),
                                         words=self.pilot.words)
        if notes:
            self.conv.write("note", "settings from this sol: " + ", ".join(notes))

    def shift(self):
        """Someone sat down at the desk, or left it, mid-sol. The prompt is rebuilt and she
        is told."""
        self.at_desk = settings.COMMS
        prompts.use()
        self.run.record("comms", sol=self.world.day, on=settings.COMMS,
                        steps=self.world.steps, prompt=prompt_hash())
        if settings.COMMS:
            self.conv.write("note", "comms on -- someone is at the desk, and she is told so")
        else:
            self.conv.write("note", "comms off -- nobody is at the desk, and she is told so")
        self.title()

    # The keys, one function per mode.

    def key_quit(self, e):
        if not self.answer_quit(e):
            self.mode = "world"

    def key_chat(self, e):
        """Typing in her chat takes every key."""
        if e.key == pygame.K_ESCAPE:
            self.typing = False
        elif e.key == pygame.K_RETURN:
            text = self.said.strip()
            if text:
                for note in desk.chat_line(self.world, self.pilot, self.conv, text):
                    self.conv.write("note", note)
                self.said = ""
                self.caret = 0
                self.scroll = 0
        else:
            self.said, self.caret = edit(self.said, self.caret, e)

    def key_terminal(self, e):
        """The terminal takes every key, or WASD would drive. T closes it only on an empty
        line, so "goto" types fine."""
        if e.key == pygame.K_ESCAPE or (e.key == pygame.K_t and not self.line):
            self.mode = "world"
            self.held = None
            self.line = ""
        elif e.key == pygame.K_RETURN:
            if self.line.strip():
                self.history.extend(console.run(self.world, self.line, self.desk))
                del self.history[:-40]
            self.line = ""
            self.caret = 0
        else:
            self.line, self.caret = edit(self.line, self.caret, e)

    def key_settings(self, e):
        """One key on the settings screen. Returns False when the screen closes."""
        kind, item = self.items[self.picked]
        locked = bool(self.script) and (kind == "preset" or item.tier != "now")
        if self.editing is not None:
            if e.key == pygame.K_ESCAPE:
                self.editing = None
            elif e.key == pygame.K_RETURN:
                self.notice = self.change(item, self.editing)
                self.editing = None
            else:
                self.editing, self.caret = edit(self.editing, self.caret, e)
            return True
        if e.key in (pygame.K_ESCAPE, pygame.K_o):
            return False
        up = e.key in (pygame.K_UP, pygame.K_w)
        down = e.key in (pygame.K_DOWN, pygame.K_s)
        left = e.key in (pygame.K_LEFT, pygame.K_a)
        right = e.key in (pygame.K_RIGHT, pygame.K_d)
        if up or down:
            step = -1 if up else 1
            self.picked = (self.picked + step) % len(self.items)
            self.notice = ""
        elif locked and (left or right or e.key in (pygame.K_RETURN, pygame.K_r)):
            self.notice = "a replay runs on the kept run's settings; only 'now' ones change"
        elif kind == "preset" and e.key == pygame.K_RETURN:
            self.prefs.preset(item)
            self.notice = f"loaded {item}; each value lands on its own tier"
        elif kind == "setting" and (left or right):
            step = -1 if left else 1
            self.notice = self.change(item, item.nudge(self.prefs.shown(item), step))
        elif kind == "setting" and e.key == pygame.K_RETURN:
            shown = self.prefs.shown(item)
            self.editing = "" if shown is None else str(shown)
            self.caret = len(self.editing)
        elif kind == "setting" and e.key == pygame.K_r:
            self.notice = self.change(item, item.default)
        return True

    def change(self, setting, value):
        try:
            value = self.prefs.set(setting.name, value)
        except ValueError as err:
            return f"{setting.name} not changed: {err}"
        if setting.name == "MODEL" and self.models is not None and value not in self.models:
            return f"{value} is not in `ollama list`; pull it before the next sol"
        return f"{setting.name} {registry.show(value)} -- {registry.TIER_NAMES[setting.tier]}"

    def key_view(self, e):
        """Looking at the view takes every key, or the arrows would drive."""
        if e.key in (pygame.K_v, pygame.K_ESCAPE):
            self.mode = "world"
            self.scroll = 0

    def key_direction(self, e, now):
        self.held = e.key
        self.next_step = now + settings.MOVE_DELAY_MS
        if self.mode == "world":
            # Driving by hand cuts the drawing short.
            self.reel.skip()
            self.reel.destination = None  # a drive by hand has no target to label
            self.world.move(*DIRS[e.key])
        else:
            self.cursor = clamp_cursor(self.cursor, DIRS[e.key], self.world.here)

    def key_world(self, e):
        if e.key == pygame.K_SPACE:
            self.reel.skip()
        elif e.key == pygame.K_m:
            self.mode = "map"
            self.cursor = self.world.pos
        elif e.key == pygame.K_x:
            self.world.toggle_mark()
        elif e.key == pygame.K_t:
            self.mode = "console"
            self.held = None
            self.caret = 0
        elif e.key == pygame.K_q and self.world.phase == "day":
            self.world.day_over = True
        elif e.key == pygame.K_TAB:
            self.typing = True
            self.held = None
            self.caret = len(self.said)
        elif e.key == pygame.K_h:
            settings.SHOW_THINKING = not settings.SHOW_THINKING
            self.scroll = 0
        elif e.key == pygame.K_p:
            self.memory_shown = not self.memory_shown
        elif e.key == pygame.K_c:
            # Sit down at the desk, or leave it, for this run only.
            settings.COMMS = not settings.COMMS
        elif e.key == pygame.K_o:
            self.mode = "settings"
            self.held = None
            self.notice = ""
            self.models = ollama.installed_models()
            registry.BY_NAME["MODEL"].choices = self.models
        elif e.key == pygame.K_v:
            # The exact view she was last sent; V again hides it.
            self.mode = "view"
            self.scroll = 0
        elif e.key == pygame.K_ESCAPE:
            self.mode = "quit"
            self.held = None

    def key_map(self, e):
        if e.key == pygame.K_x:
            self.world.toggle_mark(self.cursor)
        elif e.key in (pygame.K_m, pygame.K_ESCAPE):
            self.mode = "world"

    def handle(self, e, now):
        """One event."""
        if e.type == pygame.VIDEORESIZE:
            self.resize(max(960, e.w), max(640, e.h))
            return
        if self.mode == "world" and not self.typing:
            if dashboard.pad_event(e, self.arena.get_width()):
                return
        if e.type == pygame.QUIT:
            self.mode = "quit"
            self.typing = False
            self.held = None
        if e.type == pygame.KEYUP and e.key == self.held:
            self.held = None
        if e.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, min(self.scroll_max, self.scroll + e.y * 3))
        # A click on a button is the same as pressing its key.
        if (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.mode == "world"
                and not self.typing):
            key = dashboard.click(e.pos, self.arena.get_size(), self.pane.get_size())
            if key is not None:
                e = pygame.event.Event(pygame.KEYDOWN, key=key, unicode="")
        if e.type != pygame.KEYDOWN:
            return

        # The quit question comes first, even before the text field.
        if self.mode == "quit":
            self.key_quit(e)
        elif self.typing:
            self.key_chat(e)
        elif self.mode == "console":
            self.key_terminal(e)
        elif self.mode == "settings":
            if not self.key_settings(e):
                self.mode = "world"
                self.editing = None
        elif self.mode == "view":
            self.key_view(e)
        elif e.key in DIRS:
            self.key_direction(e, now)
        elif self.mode == "world":
            self.key_world(e)
        elif self.mode == "map":
            self.key_map(e)

    def drive_held(self, now):
        """A held direction key drives again every MOVE_REPEAT_MS."""
        if not self.held or now < self.next_step or self.typing:
            return
        if not pygame.key.get_pressed()[self.held]:
            self.held = None
            return
        self.next_step = now + settings.MOVE_REPEAT_MS
        if self.mode == "world":
            self.reel.destination = None
            self.world.move(*DIRS[self.held])
        elif self.mode == "map":
            self.cursor = clamp_cursor(self.cursor, DIRS[self.held], self.world.here)

    def advance_sol(self):
        """Let the autopilot run the sol, and roll the night over when it says so. Held while
        the desk is deciding whether to quit, though the day's clock runs on."""
        if self.mode == "quit":
            self.pilot.run_clock(self.world)
            return
        if self.pilot.tick(self.conv, self.world, typing=self.typing) != "night":
            return
        # A replay plays every sol its tape holds, then stops.
        if self.script and self.script.spent:
            return
        if self.script or not self.mission_over():
            self.nightfall()
            self.scroll = 0
        elif headless():
            self.leave(True)
        elif not self.at_end:
            self.at_end = True
            self.run.save_night(self.world)  # kept on disk, whatever is pressed next
            self.run.save_report(report.build(self.world))
            if self.world.lost:
                self.conv.write("note", "the rover is lost -- ESC to finish")
            else:
                self.conv.write("note", "the mission is over -- `sols N` in your terminal (T) "
                                        "for more, or ESC to finish")

    def frame(self):
        """One frame: keys, the world, the conversation, the sol, and the drawing."""
        if self.terminated:
            self.leave(True)
        dt = self.clock.tick(config.FPS) / 1000.0
        now = pygame.time.get_ticks()

        # Held keys repeat while a line is typed; otherwise WASD has its own repeat.
        wants = self.typing or self.mode == "console" or self.editing is not None
        if wants != self.repeating:
            if wants:
                pygame.key.set_repeat(settings.TYPE_REPEAT_DELAY_MS, settings.TYPE_REPEAT_MS)
            else:
                pygame.key.set_repeat()
            self.repeating = wants

        for e in pygame.event.get():
            self.handle(e, now)
        self.drive_held(now)
        self.world.tick(dt)
        self.reel.tick(dt)

        render.draw_world(self.arena, self.world, self.fonts, self.reel)
        if self.mode == "console":
            render.draw_console(self.arena, self.world, self.fonts, self.line, self.history,
                                self.caret)
        elif self.mode == "quit":
            render.draw_quit(self.arena, self.world, self.fonts, self.run, self.mission_over())

        # Pumped every frame; `ready` is what holds the next request back.
        self.conv.pump()
        if settings.COMMS != self.at_desk:
            self.shift()
        self.advance_sol()

        view = None
        if self.mode == "view":
            view = sight.view(self.world)
        self.scroll_max = render.draw_chat(self.pane, self.conv, self.world, self.fonts,
                                           self.said, self.typing, self.scroll,
                                           settings.SHOW_THINKING, self.reel, view,
                                           self.memory_shown, self.pilot, self.caret)
        if self.mode == "map":
            render.draw_map(self.screen, self.world, self.fonts, self.cursor, self.reel)
        if self.mode == "settings":
            render.draw_settings(self.screen, self.fonts, self.items, self.picked, self.prefs,
                                 self.editing, self.notice, self.models, bool(self.script),
                                 self.caret)
        pygame.display.flip()


def main():
    prefs = registry.Prefs()
    args, script, carried = read_flags(sys.argv[1:], prefs)
    pygame.init()
    game = Game(args, script, carried, prefs)
    while True:
        game.frame()


if __name__ == "__main__":
    main()
