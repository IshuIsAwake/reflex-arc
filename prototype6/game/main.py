"""Run me:  .venv/bin/python game/main.py [--map grid|rle] [--think]

WASD drive (hold to keep going)   M map   X mark   T console
TAB talk to the planner   V what it sees   H hide/show its reasoning
N next sol (once one has ended)   Q end the sol   ESC quit

One 50x50 Martian plain, fog you can only clear by driving through it, a landing pad at
the centre, and gemma in the pane on the right with `goto` and `distance`.

No human-only mode: the planner is the point.
"""

import argparse
import pathlib
import sys

import pygame

import anim
import chat
import config as C
import console
import logs
import render
import settings as S
import sight
from world import World

DIRS = {pygame.K_w: (0, -1), pygame.K_s: (0, 1), pygame.K_a: (-1, 0), pygame.K_d: (1, 0),
        pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1), pygame.K_LEFT: (-1, 0),
        pygame.K_RIGHT: (1, 0)}


def read_flags(argv):
    """Mutates `settings` before anything reads it. Defaults come from `settings.py`.

    `--think` sets the trace and the sampler together, because a reasoning trace that
    starts repeating at temperature 0 has no noise to climb out with. `None` rather than
    a number of our choosing, so `chat._stream` omits the option and the whole sampler
    comes from the model.
    """
    p = argparse.ArgumentParser(prog="game/main.py")
    p.add_argument("--map", choices=("grid", "rle"), default=S.MAP_FORMAT,
                   help=f"how the map is written into the view (default: {S.MAP_FORMAT})")
    p.add_argument("--think", action="store_true",
                   help="reasoning trace on, and the sampler left to the model")
    args = p.parse_args(argv)
    S.MAP_FORMAT = args.map
    if args.think:
        S.MODEL_THINK = True
        S.MODEL_TEMP = None
    return args


def main():
    read_flags(sys.argv[1:])
    pygame.init()
    # The map format is in the title bar because the two arms are told apart by nothing
    # else on screen -- the pane shows a one-line summary either way.
    pygame.display.set_caption(
        f"Reflex Arc -- prototype 3  ·  {S.MAP_FORMAT} map"
        + ("  ·  thinking, sampler unpinned" if S.MODEL_THINK else ""))
    screen = pygame.display.set_mode(render.window_size())
    clock = pygame.time.Clock()
    fonts = render.Fonts()

    # The arena draws into a subsurface its own size, so every overlay fills exactly
    # the half it was written for and the pane beside it is never painted over.
    gw, gh = render.game_size()
    game = screen.subsurface(pygame.Rect(0, 0, gw, gh))
    pane = screen.subsurface(pygame.Rect(gw, 0, S.CHAT_W, gh))

    # The run starts recording immediately. Whether it is kept is asked at the end;
    # see logs.py for why that order and not the other one.
    runs = pathlib.Path(__file__).resolve().parent.parent / "runs"
    run = logs.Run(runs)
    # The conditions go on the tape, not in the directory name. Two runs differing by one
    # setting are otherwise told apart only by their timestamps, which is not evidence.
    run.record("run", map_format=S.MAP_FORMAT, model=S.MODEL, temp=S.MODEL_TEMP,
               think=S.MODEL_THINK, ctx=S.MODEL_CTX, vision=S.VISION_RADIUS,
               replans=S.NAV_REPLANS, day_steps=S.DAY_STEPS)
    w = World(recorder=run.record)
    tape = chat.Tape(run.chat_path)
    conv = chat.Conversation(w, tape)
    conv.open_day(w)

    reel = anim.Reel(w)
    # **The planner waits for the rover.** No request goes out while a drive is still
    # being drawn, so gemma sees the outcome of one call before it can make the next.
    # It costs wall clock and that is the point: a planner seconds away from the body
    # it drives is the architecture, and here you can watch it happen.
    conv.ready = lambda: not reel.busy
    mode = "world"
    cursor = w.pos
    held = None
    next_step = 0
    line, history = "", []
    said, typing, scroll, scroll_max = "", False, 0, 0
    show_thinking = S.SHOW_THINKING

    def leave(keep):
        run.record("quit", kept=keep, day=w.day, steps=w.steps,
                   seconds=round(w.elapsed, 1))
        tape.close()
        run.keep() if keep else run.discard()
        pygame.quit()
        sys.exit()

    while True:
        dt = clock.tick(C.FPS) / 1000.0
        now = pygame.time.get_ticks()

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                mode, typing, held = "quit", False, None
            if e.type == pygame.KEYUP and e.key == held:
                held = None
            if e.type == pygame.MOUSEWHEEL:
                scroll = max(0, min(scroll_max, scroll + e.y * 3))
            if e.type != pygame.KEYDOWN:
                continue

            # The quit question outranks everything, including the text field, or
            # closing the window while mid-sentence would type into it.
            if mode == "quit":
                if e.key == pygame.K_k:
                    leave(True)
                elif e.key == pygame.K_d:
                    leave(False)
                elif e.key == pygame.K_ESCAPE:
                    mode = "world"
                continue

            # Typing to gemma eats every key, the same way the console does.
            if typing:
                if e.key == pygame.K_ESCAPE:
                    typing = False
                elif e.key == pygame.K_RETURN:
                    text = said.strip()
                    if text == "/status":
                        conv.send(sight.status_line(w), who="status")
                    elif text:
                        conv.send(text)
                    said, scroll = "", 0
                elif e.key == pygame.K_BACKSPACE:
                    said = said[:-1]
                elif e.unicode and e.unicode.isprintable():
                    said += e.unicode
                continue

            # The console eats every key, or WASD would drive instead of typing.
            if mode == "console":
                # T closes only on an empty line, so "goto" and "distance" type fine.
                if e.key == pygame.K_ESCAPE or (e.key == pygame.K_t and not line):
                    mode, held, line = "world", None, ""
                elif e.key == pygame.K_RETURN:
                    if line.strip():
                        history.extend(console.run(w, line))
                        del history[:-40]
                    line = ""
                elif e.key == pygame.K_BACKSPACE:
                    line = line[:-1]
                elif e.unicode and e.unicode.isprintable():
                    line += e.unicode
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
                    mode, held = "console", None
                elif e.key == pygame.K_q:
                    w.day_over = True
                elif e.key == pygame.K_TAB:
                    typing, held = True, None
                elif e.key == pygame.K_h:
                    show_thinking = not show_thinking
                    scroll = 0
                # You start the sol, not the loop. The old conversation is dropped here
                # rather than carried, so anything gemma wanted to keep had to be said
                # while the sol it belonged to was still open. Carrying it is item 7.
                elif e.key == pygame.K_n and w.day_over:
                    w.next_day()
                    conv = chat.Conversation(w, tape)
                    conv.open_day(w)
                    scroll = 0
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
                    w.move(*DIRS[held])
                elif mode == "map":
                    cursor = clamp_cursor(cursor, DIRS[held], w.here)
            else:
                held = None

        if mode == "world":
            w.tick(dt)
        reel.tick(dt)

        render.draw_world(game, w, fonts, reel)
        if mode == "map":
            render.draw_map(game, w, fonts, cursor)
        elif mode == "console":
            render.draw_console(game, w, fonts, line, history)
        elif mode == "quit":
            render.draw_quit(game, w, fonts, run)

        # Pumped every frame now: the hold lives in `conv.ready` above, which stops the
        # next *request* rather than the whole loop. Streaming text keeps arriving while
        # the rover drives, and no world change can slip in because nothing has been
        # asked for yet.
        conv.pump()
        scroll_max = render.draw_chat(pane, conv, w, fonts, said, typing, scroll,
                                      show_thinking, reel,
                                      sight.view(w) if mode == "view" else None)
        pygame.display.flip()


def clamp_cursor(cursor, d, area):
    return (max(0, min(area.w - 1, cursor[0] + d[0])),
            max(0, min(area.h - 1, cursor[1] + d[1])))


if __name__ == "__main__":
    main()
