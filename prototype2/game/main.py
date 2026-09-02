"""Run me:  .venv/bin/python game/main.py

WASD drive (hold to keep going)   M map   X mark   T console
TAB talk to the planner   V what it sees   H hide/show its reasoning
N next sol (once one has ended)   Q end the sol   ESC quit

Prototype 2: the arena the hackathon build mimics. One 50x50 Martian plain, fog you
can only clear by driving through it, a landing pad at the centre, and gemma in the
pane on the right with `goto` and `distance`.

There is no `--gemma` flag. Prototype 1 had one because the model was an addition to a
game that already worked; here the planner is the point and a human-only mode would be
a rover with nobody to drive it.

**Not built yet, in the order they are coming:** returning to base before dark, ridges
and dust storms and quakes, the day/night clock, Ingenuity, `interact`, notes carried
between sols. The prompt says nothing about any of them, deliberately.
"""

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
    """`--think`, and nothing else yet. Mutates `settings` before anything reads it.

    **Thinking and greedy decoding do not go together, so one flag sets both.** A
    reasoning trace that starts repeating itself at temperature 0 has no noise available
    to climb out, and `MODEL_TEMP = 0.0` is otherwise pinned deliberately -- see the
    comment there, which also records what unpinning it costs. Leaving the two as
    separate switches guarantees somebody eventually runs thinking greedily and reads the
    loop as a fact about the model.

    `None` rather than a number of our choosing: it makes `chat._stream` omit the option,
    so top_k and top_p come from the model's Modelfile alongside temperature instead of
    half the sampler being ours and half being gemma's.

    Returns the flags it did not recognise, so a typo is loud rather than ignored.
    """
    rest = [a for a in argv if a != "--think"]
    if "--think" in argv:
        S.MODEL_THINK = True
        S.MODEL_TEMP = None
    return rest


def main():
    unknown = read_flags(sys.argv[1:])
    if unknown:
        sys.exit(f"unknown option(s): {' '.join(unknown)}\nusage: main.py [--think]")
    pygame.init()
    pygame.display.set_caption("Reflex Arc -- prototype 2" +
                              ("  ·  thinking, sampler unpinned" if S.MODEL_THINK else ""))
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
                # V shows the view block over the pane, and V again puts it away. Gemma
                # is normally sent a block the pane only summarises, and being able to
                # read exactly what it was told -- rather than inferring it from the
                # answer -- is what makes a disagreement with the screen diagnosable.
                #
                # **It used to append the block to the conversation, and that was the
                # wrong shape for it.** Fifty lines land at the bottom of a transcript
                # that only scrolls by wheel; pressing V again -- which is what anyone
                # does when a key does not appear to have toggled anything -- appends
                # fifty more. `runs/20260830-100921/` has twenty-two copies of the same
                # four thousand characters, over half that tape, and no way back to the
                # conversation short of a thousand lines of scrolling. A thing you open
                # to look at is a mode, not a message.
                #
                # Nothing is written down here now. Every view gemma was actually sent is
                # already on the tape as a `view` row, which is the copy that matters for
                # diagnosing a disagreement; a human glancing at the current one between
                # calls is not part of the record.
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
