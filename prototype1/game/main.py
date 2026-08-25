"""Run me:  python prototype1/game/main.py

WASD move (hold to keep going)   E interact   M map   X mark   Q end day
"""

import sys

import pygame

import config as C
import settings as S
import console
import render
from world import World

DIRS = {pygame.K_w: (0, -1), pygame.K_s: (0, 1), pygame.K_a: (-1, 0), pygame.K_d: (1, 0),
        pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1), pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0)}


def main():
    pygame.init()
    pygame.display.set_caption("Reflex Arc -- prototype 1")
    screen = pygame.display.set_mode(render.window_size())
    clock = pygame.time.Clock()
    fonts = render.Fonts()

    w = World()
    mode = "world"
    cursor = w.pos
    shop_sel = 0
    counter = None
    day_sel = 0
    held = None
    next_step = 0
    line, history = "", []

    while True:
        dt = clock.tick(C.FPS) / 1000.0
        now = pygame.time.get_ticks()

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if e.type == pygame.KEYUP and e.key == held:
                held = None
            if e.type != pygame.KEYDOWN:
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
        if held and now >= next_step:
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
        if w.day_over and mode != "dayend":
            mode, day_sel = "dayend", 0

        render.draw_world(screen, w, fonts)
        if mode == "map":
            render.draw_map(screen, w, fonts, cursor)
        elif mode == "shop":
            render.draw_shop(screen, w, fonts, shop_sel, counter)
        elif mode == "bag":
            render.draw_bag(screen, w, fonts)
        elif mode == "cooldown":
            render.draw_cooldowns(screen, w, fonts)
        elif mode == "console":
            render.draw_console(screen, w, fonts, line, history)
        elif mode == "dayend":
            render.draw_dayend(screen, w, fonts, day_sel)
        pygame.display.flip()


def clamp_cursor(cursor, d, area):
    return (max(0, min(area.w - 1, cursor[0] + d[0])),
            max(0, min(area.h - 1, cursor[1] + d[1])))


if __name__ == "__main__":
    main()
