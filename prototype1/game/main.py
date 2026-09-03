"""Run:  python prototype1/game/main.py           the human's game
        or:  python prototype1/game/main.py --gemma   ...with gemma beside it

WASD move (hold to keep going)   E interact   M map   X mark   Q end day

Under --gemma the day is measured in steps rather than seconds, the window gains a
pane on the right, and gemma is in it.
"""

import argparse
import pathlib
import sys
from datetime import datetime   # not `as dt` -- the frame delta already owns that name

import pygame

import chat
import config as C
import settings as S
import console
import render
import sight
from world import World

DIRS = {pygame.K_w: (0, -1), pygame.K_s: (0, 1), pygame.K_a: (-1, 0), pygame.K_d: (1, 0),
        pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1), pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0)}


def main(with_gemma=False):
    # Before World(), because the day it builds is made of whichever thing this says.
    if with_gemma:
        S.DAY_MODE = "gemma"

    pygame.init()
    pygame.display.set_caption("Reflex Arc -- prototype 1" + ("  +gemma" if with_gemma else ""))
    screen = pygame.display.set_mode(render.window_size(chat=with_gemma))
    clock = pygame.time.Clock()
    fonts = render.Fonts()

    # The game draws into a subsurface the size of the window it has always had, so
    # every overlay still fills exactly the half it was written for and the pane
    # beside it is never painted over.
    gw, gh = render.game_size()
    game = screen.subsurface(pygame.Rect(0, 0, gw, gh))
    pane = screen.subsurface(pygame.Rect(gw, 0, S.CHAT_W, gh)) if with_gemma else None

    w = World()
    mode = "world"
    cursor = w.pos
    shop_sel = 0
    counter = None
    day_sel = 0
    held = None
    next_step = 0
    line, history = "", []

    conv = tape = None
    said, typing, scroll, scroll_max = "", False, 0, 0
    if with_gemma:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        runs = pathlib.Path(__file__).resolve().parent.parent / "runs"
        tape = chat.Tape(runs / f"chat-{stamp}" / "chat.jsonl")
        conv = chat.Conversation(w, tape)
        conv.open_day(w)

    while True:
        dt = clock.tick(C.FPS) / 1000.0
        now = pygame.time.get_ticks()

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if e.type == pygame.KEYUP and e.key == held:
                held = None
            if e.type == pygame.MOUSEWHEEL and with_gemma:
                scroll = max(0, min(scroll_max, scroll + e.y * 3))
            if e.type != pygame.KEYDOWN:
                continue

            # Typing to gemma eats every key, the same way the console does.
            if typing:
                if e.key == pygame.K_ESCAPE:
                    typing = False
                elif e.key == pygame.K_RETURN:
                    text = said.strip()
                    if text == "/status":
                        conv.send(chat.status_line(w), who="status")
                    elif text:
                        conv.send(text)
                    said, scroll = "", 0
                elif e.key == pygame.K_BACKSPACE:
                    said = said[:-1]
                elif e.unicode and e.unicode.isprintable():
                    said += e.unicode
                continue

            # The console eats every key, or WASD would walk instead of typing.
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

            if e.key in DIRS:
                if mode == "shop":
                    shop_sel = (shop_sel + DIRS[e.key][1]) % len(S.SHOPS[counter])
                    continue
                if mode == "dayend":
                    day_sel = (day_sel + DIRS[e.key][1]) % 2
                    continue
                held, next_step = e.key, now + S.MOVE_DELAY_MS
                if mode == "world":
                    w.move(*DIRS[e.key])
                else:
                    cursor = clamp_cursor(cursor, DIRS[e.key], w.here)

            elif mode == "world":
                if e.key == pygame.K_e:
                    counter = w.at_counter()
                    if counter:
                        mode, shop_sel = "shop", 0
                    else:
                        w.interact()
                elif e.key == pygame.K_m:
                    mode, cursor = "map", w.pos
                elif e.key == pygame.K_b:
                    mode = "bag"
                elif e.key == pygame.K_c:
                    mode = "cooldown"
                elif e.key == pygame.K_x:
                    w.toggle_mark()
                elif e.key == pygame.K_t:
                    mode, held = "console", None
                elif e.key == pygame.K_q:
                    w.day_over = True
                elif e.key == pygame.K_TAB and with_gemma:
                    typing, held = True, None
                # You start the day, not the loop. The old conversation is dropped
                # here rather than carried, so anything gemma wanted to keep had to
                # be said while the day it belonged to was still open.
                elif e.key == pygame.K_n and with_gemma and w.day_over:
                    w.next_day()
                    conv = chat.Conversation(w, tape)
                    conv.open_day(w)
                    scroll = 0
                # V prints the view verbatim into the pane. Gemma is normally sent a
                # block the pane only summarises, and being able to read exactly what
                # it was told -- rather than inferring it from the answer -- is what
                # makes a disagreement with the screen diagnosable.
                elif e.key == pygame.K_v and with_gemma:
                    conv.write("note", sight.view(w))
                    scroll = 0
                elif e.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()

            elif mode == "map":
                if e.key == pygame.K_x:
                    w.toggle_mark(cursor)
                elif e.key in (pygame.K_m, pygame.K_ESCAPE):
                    mode = "world"

            elif mode == "bag":
                if e.key in (pygame.K_b, pygame.K_ESCAPE):
                    mode = "world"

            elif mode == "cooldown":
                if e.key in (pygame.K_c, pygame.K_ESCAPE):
                    mode = "world"

            elif mode == "shop":
                items = list(S.SHOPS[counter])
                if e.key == pygame.K_RETURN:
                    w.buy(items[shop_sel], counter)
                elif e.key == pygame.K_ESCAPE:
                    mode = "world"

            elif mode == "dayend" and e.key == pygame.K_RETURN:
                if day_sel:
                    pygame.quit()
                    sys.exit()
                w.next_day()
                mode, held = "world", None

        # hold-to-move repeat
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
        # With gemma there, the day ending is not a menu -- the pane says so and
        # waits for you, because the point is to talk to it before you move on.
        if w.day_over and mode != "dayend" and not with_gemma:
            mode, day_sel = "dayend", 0

        render.draw_world(game, w, fonts)
        if mode == "map":
            render.draw_map(game, w, fonts, cursor)
        elif mode == "shop":
            render.draw_shop(game, w, fonts, shop_sel, counter)
        elif mode == "bag":
            render.draw_bag(game, w, fonts)
        elif mode == "cooldown":
            render.draw_cooldowns(game, w, fonts)
        elif mode == "console":
            render.draw_console(game, w, fonts, line, history)
        elif mode == "dayend":
            render.draw_dayend(game, w, fonts, day_sel)

        if with_gemma:
            conv.pump()
            scroll_max = render.draw_chat(pane, conv, w, fonts, said, typing, scroll)
        pygame.display.flip()


def clamp_cursor(cursor, d, area):
    return (max(0, min(area.w - 1, cursor[0] + d[0])),
            max(0, min(area.h - 1, cursor[1] + d[1])))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gemma", action="store_true",
                    help="steps instead of a clock, and gemma in a pane beside the game")
    main(ap.parse_args().gemma)
