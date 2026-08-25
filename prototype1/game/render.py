"""All the pygame drawing. Paper-white daylight, black ink, one red blob."""

import pygame

import config as C
import settings as S
from world import TERMINALS as TERMINAL_NAMES

MARGIN = 15
LABELS = {"B": "board", "S": "shop", "T": "tribe", "L": "lost bag", "$": "coins",
          "*": "discover",  # the vault never says what is in it until you open it
          "D": "east gate", "E": "west gate", "v": "south gate", "n": "north gate"}
GOLDISH = set("L$*")
GATES = "DEvn"


def window_size():
    return C.VIEW_W * C.TILE + MARGIN * 2, C.VIEW_H * C.TILE + C.HUD_H + MARGIN * 2


class Fonts:
    def __init__(self):
        self.tile = pygame.font.SysFont("dejavusansmono,consolas,monospace", 17, bold=True)
        self.tiny = pygame.font.SysFont("dejavusansmono,consolas,monospace", 10)
        self.hud = pygame.font.SysFont("dejavusansmono,consolas,monospace", 14)
        self.big = pygame.font.SysFont("dejavusansmono,consolas,monospace", 19, bold=True)


def viewport(surf, area, pos):
    """Pixel origin of cell (0,0) plus the rect the world is allowed to paint in.

    An area smaller than the view sits centred; a bigger one scrolls to follow the
    player and stops at its own edges."""
    def axis(span, view, here, screen_span, top):
        room = view * C.TILE
        base = top + (screen_span - room) // 2
        if span <= view:
            return base + (room - span * C.TILE) // 2, base
        cam = max(0, min(here - view // 2, span - view))
        return base - cam * C.TILE, base

    play_h = surf.get_height() - C.HUD_H
    ox, vx = axis(area.w, C.VIEW_W, pos[0], surf.get_width(), 0)
    oy, vy = axis(area.h, C.VIEW_H, pos[1], play_h, 0)
    return (ox, oy), pygame.Rect(vx, vy, C.VIEW_W * C.TILE, C.VIEW_H * C.TILE)


def _rulers(surf, f, area, ox, oy, view):
    """Coordinate ticks every 5 cells, so noting a cell down is easy."""
    for x in range(0, area.w, 5):
        px = ox + x * C.TILE + C.TILE // 2
        if view.left <= px <= view.right:
            t = f.tiny.render(str(x), True, (150, 147, 141))
            surf.blit(t, t.get_rect(midbottom=(px, view.top - 1)))
    for y in range(0, area.h, 5):
        py = oy + y * C.TILE + C.TILE // 2
        if view.top <= py <= view.bottom:
            t = f.tiny.render(str(y), True, (150, 147, 141))
            surf.blit(t, t.get_rect(midright=(view.left - 3, py)))


def label_for(w, ch):
    """A terminal you have not walked up to reads 'discover'."""
    if ch in TERMINAL_NAMES:
        game = TERMINAL_NAMES[ch]
        return game if game in w.discovered else "discover"
    return LABELS.get(ch)


def draw_world(surf, w, f):
    surf.fill(C.PAPER)
    a = w.here
    (ox, oy), view = viewport(surf, a, w.pos)
    px, py = w.pos
    r2 = S.VISION_RADIUS ** 2
    _rulers(surf, f, a, ox, oy, view)

    lo_x, hi_x = (view.left - ox) // C.TILE - 1, (view.right - ox) // C.TILE + 1
    lo_y, hi_y = (view.top - oy) // C.TILE - 1, (view.bottom - oy) // C.TILE + 1
    surf.set_clip(view)

    # Ground first, then everything that overflows its cell -- labels spill into the
    # row below and would otherwise be painted over by it.
    things = []
    for y in range(max(0, lo_y), min(a.h, hi_y + 1)):
        for x in range(max(0, lo_x), min(a.w, hi_x + 1)):
            rect = pygame.Rect(ox + x * C.TILE, oy + y * C.TILE, C.TILE, C.TILE)
            if not a.visible(x, y):
                pygame.draw.rect(surf, C.FOG, rect)
                continue

            lit = (x - px) ** 2 + (y - py) ** 2 <= r2
            ch = a.at(x, y)

            if ch == "#":
                pygame.draw.rect(surf, C.INK if lit else (58, 58, 66), rect)
            else:
                pygame.draw.rect(surf, C.PAPER if lit else C.ROAD, rect)
                pygame.draw.rect(surf, C.FAINT, rect, 1)

            if ch not in "#." or (x, y) in a.marks:
                things.append((rect, ch, lit, (x, y)))

    for rect, ch, lit, cell in things:
        if ch not in "#.":
            _glyph(surf, f, rect, ch, lit, (w.area, cell) in w.unlocked, label_for(w, ch))
        if cell in a.marks:
            _x_mark(surf, rect)

    # the red blob
    cx = ox + px * C.TILE + C.TILE // 2
    cy = oy + py * C.TILE + C.TILE // 2
    pygame.draw.circle(surf, C.PLAYER, (cx, cy), C.TILE // 2 - 4)
    pygame.draw.circle(surf, C.INK, (cx, cy), C.TILE // 2 - 4, 2)

    surf.set_clip(None)
    _hud(surf, w, f)


def _glyph(surf, f, rect, ch, lit, unlocked=False, label=None):
    if ch in GATES:
        colour = C.GOOD if (ch != "D" or unlocked) else C.INK
        pygame.draw.rect(surf, colour, rect.inflate(-6, -2))
        return
    colour = C.GOLD if ch in GOLDISH else C.INK
    if not lit:
        colour = tuple(min(255, v + 40) for v in colour)
    pygame.draw.rect(surf, colour, rect.inflate(-4, -4), 2)
    g = f.tile.render(ch, True, colour)
    surf.blit(g, g.get_rect(center=rect.center))
    # Label whatever is visible, lit or merely remembered -- otherwise things you
    # have already found go anonymous the moment you step away from them. Labels sit
    # in the row below, which is often a wall, so give them a paper backing.
    if label:
        t = f.tiny.render(label, True, colour, C.PAPER)
        surf.blit(t, t.get_rect(midtop=(rect.centerx, rect.bottom + 1)))


def _x_mark(surf, rect):
    r = rect.inflate(-8, -8)
    pygame.draw.line(surf, C.MARK, r.topleft, r.bottomright, 3)
    pygame.draw.line(surf, C.MARK, r.topright, r.bottomleft, 3)


def budget(w):
    """Whichever thing the day is actually made of."""
    if S.DAY_MODE == "human":
        mins, secs = divmod(max(0, int(w.time_left)), 60)
        return f"{mins}:{secs:02d}"
    return f"{w.steps_left} steps"


def _hud(surf, w, f):
    y0 = surf.get_height() - C.HUD_H
    pygame.draw.line(surf, C.INK, (0, y0), (surf.get_width(), y0), 2)

    surf.blit(f.big.render(f"DAY {w.day}   {budget(w)}   {w.coins} coins", True, C.INK),
              (MARGIN, y0 + 10))
    surf.blit(f.hud.render(f"{C.DISPLAY_NAMES[w.area].upper()}  ({w.pos[0]}, {w.pos[1]})",
                           True, C.INK), (MARGIN, y0 + 38))
    if S.DAY_MODE != "human":
        surf.blit(f.tiny.render(f"stopwatch {w.elapsed:.0f}s", True, (140, 137, 131)),
                  (MARGIN + 200, y0 + 41))
    surf.blit(f.tiny.render("WASD move  E interact  M map  B bag  C cooldowns  X mark  T console  Q end day",
                            True, (120, 120, 126)), (MARGIN, y0 + 68))

    for i, (msg, tone) in enumerate(reversed(w.log[-3:])):
        col = {"good": C.GOOD, "bad": C.BAD}.get(tone, C.INK)
        shade = tuple(min(255, v + i * 55) for v in col)
        surf.blit(f.hud.render(msg, True, shade), (MARGIN + 360, y0 + 12 + i * 22))


def draw_map(surf, w, f, cursor):
    """Full-area view. Entry and exit points marked. Traps never appear here."""
    a = w.here
    overlay = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    overlay.fill((247, 245, 240, 248))
    surf.blit(overlay, (0, 0))

    cell = min(22, (surf.get_width() - 80) // a.w, (surf.get_height() - 150) // a.h)
    ox = (surf.get_width() - a.w * cell) // 2
    oy = 70

    name = C.DISPLAY_NAMES[a.name].upper()
    title = f"{name} MAP" if a.has_map else f"{name} -- no map, only what you have walked"
    t = f.big.render(title, True, C.INK)
    surf.blit(t, t.get_rect(midtop=(surf.get_width() // 2, 26)))

    for x in range(0, a.w, 5):
        t = f.tiny.render(str(x), True, (140, 137, 131))
        surf.blit(t, t.get_rect(midbottom=(ox + x * cell + cell // 2, oy - 2)))
    for y in range(0, a.h, 5):
        t = f.tiny.render(str(y), True, (140, 137, 131))
        surf.blit(t, t.get_rect(midright=(ox - 4, oy + y * cell + cell // 2)))

    # Two routes, and the difference between them is the whole point. The walk is
    # shaded into the floor and is what happened. The plan goes on top as dots and
    # is a hypothesis -- through fog it crosses walls it could not have known about.
    # The plan is also replaced on every replan and the walk is not, so wherever the
    # shading goes somewhere the dots do not, that is where the surprises were.
    walk_area, walked = w.last_walk
    walked = set(walked) if walk_area == a.name else set()

    for y in range(a.h):
        for x in range(a.w):
            r = pygame.Rect(ox + x * cell, oy + y * cell, cell, cell)
            if not a.visible(x, y):
                pygame.draw.rect(surf, C.FOG, r)
                continue
            ch = a.at(x, y)
            if ch == "#":
                pygame.draw.rect(surf, C.INK, r)
            else:
                pygame.draw.rect(surf, C.WALKED if (x, y) in walked else C.PAPER, r)
                pygame.draw.rect(surf, C.FAINT, r, 1)
            if ch in GATES:
                pygame.draw.rect(surf, C.GOOD, r.inflate(-3, -3))
            elif ch not in "#.":
                col = C.GOLD if ch in GOLDISH else C.INK
                g = f.hud.render(ch, True, col)
                surf.blit(g, g.get_rect(center=r.center))
            if (x, y) in a.marks:
                _x_mark(surf, r)

    # Seeing a wrong plan beats inferring one from the failure code.
    path_area, path = w.last_path
    if path_area == a.name:
        for cx, cy in path:
            r = pygame.Rect(ox + cx * cell, oy + cy * cell, cell, cell)
            pygame.draw.circle(surf, C.PATH, r.center, max(2, cell // 6))

    pr = pygame.Rect(ox + w.pos[0] * cell, oy + w.pos[1] * cell, cell, cell)
    pygame.draw.circle(surf, C.PLAYER, pr.center, cell // 2 - 2)

    cr = pygame.Rect(ox + cursor[0] * cell, oy + cursor[1] * cell, cell, cell)
    pygame.draw.rect(surf, C.MARK, cr.inflate(2, 2), 2)

    foot = [f"cursor ({cursor[0]}, {cursor[1]})   green = gates   "
            "blue = the plan   shaded = the walk",
            "WASD move cursor   X mark/unmark   M or ESC close"]
    for i, line in enumerate(foot):
        s = f.hud.render(line, True, C.INK)
        surf.blit(s, s.get_rect(midtop=(surf.get_width() // 2, oy + a.h * cell + 12 + i * 20)))


def _panel(surf, f, title, sub, n_lines, width=460, line_h=26):
    overlay = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    overlay.fill((247, 245, 240, 248))
    surf.blit(overlay, (0, 0))

    box = pygame.Rect(0, 0, width, 104 + line_h * max(1, n_lines))
    box.center = (surf.get_width() // 2, surf.get_height() // 2)
    pygame.draw.rect(surf, C.PAPER, box)
    pygame.draw.rect(surf, C.INK, box, 2)

    t = f.big.render(title, True, C.INK)
    surf.blit(t, t.get_rect(midtop=(box.centerx, box.top + 12)))
    if sub:
        s = f.hud.render(sub, True, C.INK)
        surf.blit(s, s.get_rect(midtop=(box.centerx, box.top + 38)))
    return box


def _foot(surf, f, box, text):
    h = f.tiny.render(text, True, (120, 120, 126))
    surf.blit(h, h.get_rect(midbottom=(box.centerx, box.bottom - 14)))


def draw_dayend(surf, w, f, sel):
    box = _panel(surf, f, f"DAY {w.day} OVER",
                 f"earned {w.earned_today()} coins today   {w.coins} in hand", 4)
    surf.blit(f.tiny.render(f"{w.steps} steps in {w.elapsed:.0f}s", True, (140, 137, 131)),
              (box.left + 42, box.top + 60))
    for i, line in enumerate((f"continue to day {w.day + 1}", "exit")):
        chosen = i == sel
        surf.blit(f.hud.render(("> " if chosen else "  ") + line, True,
                               C.INK if chosen else C.FAINT),
                  (box.left + 40, box.top + 88 + i * 26))
    _foot(surf, f, box, "W/S choose   ENTER confirm")


def draw_shop(surf, w, f, sel, counter):
    stock = S.SHOPS[counter]
    box = _panel(surf, f, counter.upper(), f"you have {w.coins} coins", len(stock) + 1)
    for i, (item, price) in enumerate(stock.items()):
        if item == "antidote":
            note, spent = f"   {w.antidotes}/{w.pouch} carried", w.antidotes >= w.pouch
        else:
            note, spent = ("   owned" if item in w.items else ""), item in w.items
        col = C.FAINT if spent else (C.INK if w.coins >= price else C.BAD)
        line = f"{'>' if i == sel else ' '} {item:<14} {price:>4}{note}"
        surf.blit(f.hud.render(line, True, col), (box.left + 40, box.top + 74 + i * 26))
    _foot(surf, f, box, "W/S choose   ENTER buy   ESC leave")


def draw_bag(surf, w, f):
    items = sorted(w.items)
    maps = [C.DISPLAY_NAMES[a.name] for a in w.areas.values() if a.has_map]
    box = _panel(surf, f, "BAG", f"{w.coins} coins", max(1, len(items)) + 4)

    y = box.top + 74
    surf.blit(f.hud.render(f"  antidotes  {w.antidotes}/{w.pouch}", True,
                           C.INK if w.antidotes else C.FAINT), (box.left + 40, y))
    y += 26
    for item in items or [None]:
        text, col = (f"  {item}", C.INK) if item else ("  no keys yet", C.FAINT)
        surf.blit(f.hud.render(text, True, col), (box.left + 40, y))
        y += 26
    y += 8
    surf.blit(f.hud.render(f"  maps:  {', '.join(maps) or 'none'}", True, C.INK), (box.left + 40, y))
    surf.blit(f.hud.render(f"  marks in {C.DISPLAY_NAMES[w.area]}:  {len(w.here.marks)}",
                           True, C.MARK), (box.left + 40, y + 26))
    _foot(surf, f, box, "B or ESC close")


CONSOLE_LINES = 12


def draw_console(surf, w, f, line, history):
    """The planner's front door. What it prints is what gemma reads, verbatim."""
    box = _panel(surf, f, "CONSOLE", "the same strings the model gets back",
                 CONSOLE_LINES + 1, width=surf.get_width() - 60, line_h=20)

    y = box.top + 66
    for text, tone in history[-CONSOLE_LINES:]:
        col = {"good": C.GOOD, "bad": C.BAD}.get(tone, C.INK)
        surf.blit(f.hud.render(text[:88], True, col), (box.left + 24, y))
        y += 20

    y = box.bottom - 44
    pygame.draw.line(surf, C.FAINT, (box.left + 24, y - 6), (box.right - 24, y - 6))
    surf.blit(f.hud.render(f"> {line}_", True, C.INK), (box.left + 24, y))
    _foot(surf, f, box, "ENTER run   help for commands   T or ESC close")


def draw_cooldowns(surf, w, f):
    rows = w.cooldown_lines()
    box = _panel(surf, f, "TERMINALS", None, max(1, len(rows)))
    if not rows:
        surf.blit(f.hud.render("  none found yet", True, C.FAINT), (box.left + 40, box.top + 54))
    for i, (game, area, state, tone) in enumerate(rows):
        col = {"good": C.GOOD, "bad": C.BAD}.get(tone, C.INK)
        surf.blit(f.hud.render(f"  {game:<10} {area:<8} {state}", True, col),
                  (box.left + 40, box.top + 54 + i * 26))
    _foot(surf, f, box, "C or ESC close")
