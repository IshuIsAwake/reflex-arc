"""All the pygame drawing. Martian red-brown and black, one pale dot.

Two surfaces, and they do not look like the same program on purpose. The left is
terrain -- warm, textured, lit where the rover is. The right is a console: black, flat,
monospace, no decoration at all. The rover's world and the room it is driven from.
"""

import textwrap

import pygame

import config as C
import registry
import settings as S
import world as W

MARGIN = 15


def game_size():
    """The arena surface. Everything on the left draws against this."""
    return C.VIEW_W * C.TILE + MARGIN * 2, C.VIEW_H * C.TILE + C.HUD_H + MARGIN * 2


def window_size():
    gw, gh = game_size()
    return gw + S.CHAT_W, gh


MIN_CHAT = 460      # narrower than this and the pane wraps into uselessness
MIN_TILE = 6        # smaller and the grid stops being readable at all


def fit_to_display():
    """Shrink the tile and the pane until the window fits the desktop it opens on.

    The shipped 17px tile and 1000px pane make an 1880x990 window. That is bigger than
    a 1536x864 laptop, and the way it fails is bad: the pane hangs off the right edge,
    the HUD sits under the taskbar, and a window whose controls you cannot reach looks
    from the outside exactly like a game that did not start.

    Height sets the tile, because only the tile can shrink it; width then buys back
    whatever is left for the pane. Never grows either -- the numbers in `config.py` and
    `settings.py` stay the ceiling, so a big monitor gets what was designed and a small
    one gets the same layout, smaller. Below the minimums it stops and overflows
    visibly: a 3px tile that technically fits is worse than a window you can drag.

    Mutates `C.TILE` and `S.CHAT_W`, which every other size here is derived from, so
    call it once after `pygame.init()` and before anything reads either. Returns the
    window size that results. `S.FIT_TO_SCREEN = False` leaves the shipped numbers
    exactly, which is what a screenshot that has to match somebody else's needs.
    """
    if not S.FIT_TO_SCREEN:
        return window_size()
    try:
        sw, sh = pygame.display.get_desktop_sizes()[0]
    except (pygame.error, IndexError):
        return window_size()        # no display to ask; leave the shipped numbers
    sw, sh = sw - S.SCREEN_RESERVE_W, sh - S.SCREEN_RESERVE_H

    by_height = (sh - C.HUD_H - MARGIN * 2) // C.VIEW_H
    by_width = (sw - MIN_CHAT - MARGIN * 2) // C.VIEW_W
    C.TILE = max(MIN_TILE, min(C.TILE, by_height, by_width))
    S.CHAT_W = max(MIN_CHAT, min(S.CHAT_W, sw - game_size()[0]))
    return window_size()


class Fonts:
    def __init__(self):
        mono = "dejavusansmono,consolas,monospace"
        self.tile = pygame.font.SysFont(mono, 12, bold=True)
        self.tiny = pygame.font.SysFont(mono, 10)
        self.hud = pygame.font.SysFont(mono, 14)
        self.big = pygame.font.SysFont(mono, 19, bold=True)
        self.chat = pygame.font.SysFont(mono, 13)
        self.chat_head = pygame.font.SysFont(mono, 11, bold=True)


def viewport(surf, area, pos):
    """Pixel origin of cell (0,0) plus the rect the arena is allowed to paint in.

    An arena smaller than the view sits centred; a bigger one scrolls to follow the
    rover and stops at its own edges. At the shipped numbers the whole 50x50 fits and
    nothing scrolls -- raising `TILE` in config.py just starts it scrolling, which is
    why this is kept rather than simplified away."""
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


# --- texture ---------------------------------------------------------------
# Scatter, from a hash of the cell. Deterministic, so the grit never crawls between
# frames and the arena looks the same on every run and in every screenshot.
#
# Decoration, not a tile. `sight.py` must never learn about it -- a pebble the human
# sees and gemma does not is fine only while it means nothing. test_sight.py holds that
# line. Grit is small and never fills a cell; rock is large and always does.
def _grit(x, y):
    """0-3 pebbles for this cell, as (dx, dy, radius, lighter) at tile scale."""
    h = (x * 73856093) ^ (y * 19349663)
    h = (h ^ (h >> 13)) & 0x7FFFFFFF
    n = (h % 7) // 3                     # about a third of cells get anything
    out = []
    for i in range(n):
        b = h >> (4 + i * 9)
        out.append(((b % 5) + 1, ((b >> 3) % 5) + 1,
                    1 + ((b >> 6) % 2), bool((b >> 8) & 1)))
    return out


def _rock_shade(x, y):
    """Outcrops vary a little, so a boulder field does not read as one flat mass."""
    h = ((x * 83492791) ^ (y * 29863271)) & 0x7FFFFFFF
    return (h % 7) - 3


def draw_world(surf, w, f, reel=None):
    """The arena. `reel`, when one is playing, moves the rover and holds the fog.

    The world has already finished whatever is being drawn here -- see anim.py. So
    everything the reel touches is a *substitution*: where the rover appears, and which
    cells still count as fog. Nothing is read back.
    """
    surf.fill(C.VOID)
    a = w.here
    px, py = reel.where(w.pos) if reel else w.pos
    (ox, oy), view = viewport(surf, a, (px, py))
    # A lamp, not vision -- the rover reveals nothing by driving. Fog is drawn from
    # `a.visible` below; this only brightens ground that is already on the map.
    r2 = S.VISION_RADIUS ** 2

    lo_x, hi_x = (view.left - ox) // C.TILE - 1, (view.right - ox) // C.TILE + 1
    lo_y, hi_y = (view.top - oy) // C.TILE - 1, (view.bottom - oy) // C.TILE + 1
    surf.set_clip(view)

    step = max(2, C.TILE // 5)
    things = []
    for y in range(max(0, lo_y), min(a.h, hi_y + 1)):
        for x in range(max(0, lo_x), min(a.w, hi_x + 1)):
            rect = pygame.Rect(ox + x * C.TILE, oy + y * C.TILE, C.TILE, C.TILE)
            if not a.visible(x, y) or (reel and reel.veiled((x, y))):
                pygame.draw.rect(surf, C.FOG, rect)
                continue

            lit = (x - px) ** 2 + (y - py) ** 2 <= r2
            ch = a.at(x, y)

            if ch == "#":
                shade = _rock_shade(x, y)
                base = C.ROCK if lit else C.ROCK_DIM
                pygame.draw.rect(surf, tuple(max(0, min(255, v + shade)) for v in base),
                                 rect)
            elif ch == "H" or ch in W.GLYPHS or ch == W.INTEREST:
                things.append((rect, ch, lit, (x, y)))
                pygame.draw.rect(surf, C.REGOLITH if lit else C.REGOLITH_DIM, rect)
            else:
                pygame.draw.rect(surf, C.REGOLITH if lit else C.REGOLITH_DIM, rect)
                for dx, dy, r, pale in _grit(x, y):
                    col = C.GRIT_LIT if (pale and lit) else C.GRIT
                    pygame.draw.circle(surf, col,
                                       (rect.x + dx * step, rect.y + dy * step), r)

            if (x, y) in a.marks:
                things.append((rect, None, lit, (x, y)))

    for rect, ch, lit, cell in things:
        if ch == "H":
            _pad(surf, rect, lit)
        elif ch and ch in W.GLYPHS:       # a mark rides here with no tile of its own
            _objective(surf, rect, a.objectives[cell].priority, lit)
        elif ch == W.INTEREST:
            _interest(surf, rect, a.interests[cell].found, lit)
        if cell in a.marks:
            _x_mark(surf, rect)

    # Over the ground and under the rover: the storm is weather sitting on the arena,
    # not a thing in it. Hatched rather than filled so the map still reads underneath --
    # a solid block would look like terrain, which is the one thing it is not.
    for cell in a.storm_cells:
        r = _cell_rect(ox, oy, cell)
        pygame.draw.rect(surf, C.STORM, r)
        pygame.draw.line(surf, C.STORM_DARK, r.bottomleft, r.topright, 1)

    if reel:
        _reel(surf, reel, ox, oy)
    _sky(surf, w.phase, view)
    _rover(surf, ox + px * C.TILE + C.TILE // 2, oy + py * C.TILE + C.TILE // 2)
    surf.set_clip(None)
    _rim(surf, a, ox, oy)
    _hud(surf, w, f, reel)


def _cell_rect(ox, oy, cell):
    return pygame.Rect(ox + cell[0] * C.TILE, oy + cell[1] * C.TILE, C.TILE, C.TILE)


def _reel(surf, reel, ox, oy):
    """The drive being replayed: where it has been, what it believes, what refused.

    Order matters and it is the order of what happened. The trail is ground that is
    now fact, so it goes underneath. The plan is a hypothesis, so it goes on top of the
    ground it has not reached yet. The bump goes last because it is the moment the
    hypothesis died.
    """
    for cell in reel.trail:
        pygame.draw.rect(surf, C.WALKED, _cell_rect(ox, oy, cell))

    r = max(2, C.TILE // 4)
    for cell in reel.plan:
        pygame.draw.circle(surf, C.PLAN, _cell_rect(ox, oy, cell).center, r)
    for cell in reel.probe:
        pygame.draw.circle(surf, C.PATH, _cell_rect(ox, oy, cell).center, r)

    if reel.work:
        cell, done, total = reel.work
        box = _cell_rect(ox, oy, cell)
        pygame.draw.rect(surf, C.PLAN, box.inflate(4, 4), 2)
        bar = pygame.Rect(box.left, box.bottom + 2, max(1, box.width * done // total), 3)
        pygame.draw.rect(surf, C.PLAN, bar)

    if reel.bump:
        box = _cell_rect(ox, oy, reel.bump)
        pygame.draw.rect(surf, C.BUMP, box, 2)
        pygame.draw.line(surf, C.BUMP, box.topleft, box.bottomright, 2)
        pygame.draw.line(surf, C.BUMP, box.topright, box.bottomleft, 2)


def _objective(surf, rect, priority, lit):
    """An instrument to be worked, drawn as a ring so the ground still shows through.

    Priority picks the hue and the three are the traffic-light order, which is the one
    ranking the environment is allowed to hand over -- it is a fact about the mission,
    not a judgement about what to do first. Read off the objective, not its glyph: a
    placed `4` is whatever priority it was given.
    """
    col = {"high": C.BAD, "medium": C.PLAN, "low": C.GOOD}.get(priority, C.INK)
    if not lit:
        col = tuple(int(v * 0.55) for v in col)
    r = max(2, rect.width // 2 - 2)
    pygame.draw.circle(surf, col, rect.center, r, max(1, rect.width // 6))


def _interest(surf, rect, found, lit):
    """A point of interest: a square, so it never reads as an objective's ring. One she
    has not found yet -- placed on ground already mapped -- is drawn faint, for the desk
    that placed it."""
    col = C.INTEREST if found else tuple(int(v * 0.35) for v in C.INTEREST)
    if not lit:
        col = tuple(int(v * 0.6) for v in col)
    inset = max(2, rect.width // 5)
    pygame.draw.rect(surf, col, rect.inflate(-inset * 2, -inset * 2),
                     max(1, rect.width // 7))


_SKY = {}


def _sky(surf, phase, view):
    """The phase, washed over the arena. Day is clear and night is dark; dawn is lit
    from the east and dusk from the west, so either is obvious at a glance."""
    if phase == "day":
        return
    key = (view.size, phase)
    if key not in _SKY:
        wash = pygame.Surface(view.size, pygame.SRCALPHA)
        width = max(1, view.width - 1)
        for x in range(view.width):
            east = x / width
            dark = {"night": 1.0, "dawn": 1.0 - east, "dusk": east}[phase]
            wash.fill((*C.NIGHT, int(C.NIGHT_ALPHA * dark)),
                      pygame.Rect(x, 0, 1, view.height))
        _SKY[key] = wash
    surf.blit(_SKY[key], view.topleft)


def _pad(surf, rect, lit):
    """The landing pad. Plate rather than glyph -- it is a structure, not a symbol.

    Filled edge to edge on purpose: the pad is six tiles and insetting each one drew
    six separate squares where there is one thing. A single rivet keeps it from
    reading as a flat blank.
    """
    col = C.BASE if lit else C.BASE_DIM
    pygame.draw.rect(surf, col, rect)
    pygame.draw.rect(surf, C.ROVER_RING, rect.inflate(-C.TILE + 4, -C.TILE + 4))


def _rover(surf, cx, cy):
    """A dot, and a ring so it never disappears into the lit pale pad beneath it."""
    r = max(3, C.TILE // 2 - 2)
    pygame.draw.circle(surf, C.ROVER_RING, (cx, cy), r + 2)
    pygame.draw.circle(surf, C.ROVER, (cx, cy), r)


def _rim(surf, a, ox, oy):
    """The arena has no wall, so it needs an edge you can see.

    Drawn, never a tile. Prototype 1 walled its areas and 22% of gemma's calls were
    spent aiming at that wall, because a known wall is deliberately UNREACHABLE. Here
    (0,0) is a cell you can stand on and this line is only where the ground stops.
    """
    pygame.draw.rect(surf, C.FAINT,
                     pygame.Rect(ox - 1, oy - 1, a.w * C.TILE + 2, a.h * C.TILE + 2), 1)


def _x_mark(surf, rect):
    r = rect.inflate(-4, -4)
    pygame.draw.line(surf, C.MARK, r.topleft, r.bottomright, 2)
    pygame.draw.line(surf, C.MARK, r.topright, r.bottomleft, 2)


def budget(w):
    """The phase, the clock and the battery. One wording, in one place."""
    mins, secs = divmod(max(0, int(w.time_left)), 60)
    return (f"{w.phase.upper()}  {mins}:{secs:02d}    battery {w.battery}/{S.BATTERY}"
            + ("  (stranded)" if w.stranded else ""))


def _hud(surf, w, f, reel=None):
    y0 = surf.get_height() - C.HUD_H
    pygame.draw.line(surf, C.FAINT, (0, y0), (surf.get_width(), y0), 1)

    head = f.big.render(f"SOL {w.day}    {budget(w)}", True, C.INK)
    surf.blit(head, (MARGIN, y0 + 12))
    # The messages sit right of the longest that line gets, never under it.
    side = MARGIN + max(300, head.get_width() + 30)
    # The world is ahead of the screen while a drive is replaying, so say where the
    # rover is being *drawn* and where it actually already is. A HUD that showed only
    # the true position would disagree with the dot for several seconds at a time.
    if reel and reel.at and reel.at != w.pos:
        where = f"({reel.at[0]}, {reel.at[1]})  ->  ({w.pos[0]}, {w.pos[1]})"
    else:
        where = f"({w.pos[0]}, {w.pos[1]})"
    surf.blit(f.hud.render(f"{C.ARENA_NAME.upper()}   {where}", True, C.MUTED),
              (MARGIN, y0 + 40))
    # The stopwatch is shown even though it costs nothing, because what it records is
    # the measurement the day/night clock has to be designed against.
    surf.blit(f.tiny.render(f"elapsed {w.elapsed:.0f}s", True, C.FAINT),
              (MARGIN, y0 + 62))
    hint = ("SPACE skip the drive   " if reel and reel.busy else
            "WASD drive   M map   X mark   T console   ")
    surf.blit(f.tiny.render(hint + "TAB her chat   T terminal   ESC quit",
                            True, C.FAINT), (MARGIN, y0 + 84))
    surf.blit(f.tiny.render("O settings   P scratchpad   H thinking   Q end the day   "
                            "C comms " + ("off" if S.COMMS else "on"),
                            True, C.FAINT), (MARGIN, y0 + 100))

    # The rover is out on the floor driving a leg and everything here is held until it
    # is done. Say what it was given, or the operator is being asked to confirm
    # something they have no way to check.
    if w.awaiting_rover is not None:
        leg = " ".join(w.awaiting_rover)
        surf.blit(f.hud.render(f"ROVER DRIVING  {leg[:40]}", True, C.GOOD),
                  (side, y0 + 14))
        surf.blit(f.tiny.render("SPACE when it has stopped", True, C.INK),
                  (side, y0 + 38))
        return

    for i, (msg, tone) in enumerate(reversed(w.log[-3:])):
        col = {"good": C.GOOD, "bad": C.BAD}.get(tone, C.INK)
        shade = tuple(min(255, int(v * (1 - i * 0.3))) for v in col)
        surf.blit(f.hud.render(msg[:64], True, shade), (side, y0 + 14 + i * 22))


def draw_map(surf, w, f, cursor):
    """Full-arena view, scaled to fit, with the plan and the drive drawn over it."""
    a = w.here
    overlay = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    overlay.fill((*C.VOID, 253))
    surf.blit(overlay, (0, 0))

    cell = min(22, (surf.get_width() - 80) // a.w, (surf.get_height() - 160) // a.h)
    ox = (surf.get_width() - a.w * cell) // 2
    oy = 72

    seen = sum(1 for y in range(a.h) for x in range(a.w) if a.visible(x, y))
    t = f.big.render(f"{C.ARENA_NAME.upper()} -- {seen} of {a.w * a.h} cells surveyed",
                     True, C.INK)
    surf.blit(t, t.get_rect(midtop=(surf.get_width() // 2, 26)))

    for x in range(0, a.w, 5):
        s = f.tiny.render(str(x), True, C.MUTED)
        surf.blit(s, s.get_rect(midbottom=(ox + x * cell + cell // 2, oy - 2)))
    for y in range(0, a.h, 5):
        s = f.tiny.render(str(y), True, C.MUTED)
        surf.blit(s, s.get_rect(midright=(ox - 4, oy + y * cell + cell // 2)))

    # Two routes, and the difference between them is the whole point. The drive is
    # shaded into the ground and is what happened. The plan goes on top as dots and is
    # a hypothesis -- through fog it crosses rock it could not have known about. The
    # plan is replaced on every replan and the drive is not, so wherever the shading
    # goes somewhere the dots do not, that is where the surprises were.
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
                pygame.draw.rect(surf, C.ROCK, r)
            elif ch == "H":
                pygame.draw.rect(surf, C.BASE, r)
            elif ch in W.GLYPHS:
                pygame.draw.rect(surf, C.REGOLITH_DIM, r)
                _objective(surf, r, a.objectives[(x, y)].priority, True)
            elif ch == W.INTEREST:
                pygame.draw.rect(surf, C.REGOLITH_DIM, r)
                _interest(surf, r, a.interests[(x, y)].found, True)
            else:
                pygame.draw.rect(surf, C.WALKED if (x, y) in walked else C.REGOLITH_DIM, r)
            if (x, y) in a.storm_cells:
                pygame.draw.rect(surf, C.STORM, r)
            if (x, y) in a.marks:
                _x_mark(surf, r)

    path_area, path = w.last_path
    if path_area == a.name:
        for cx, cy in path:
            r = pygame.Rect(ox + cx * cell, oy + cy * cell, cell, cell)
            pygame.draw.circle(surf, C.PATH, r.center, max(2, cell // 5))

    pr = pygame.Rect(ox + w.pos[0] * cell, oy + w.pos[1] * cell, cell, cell)
    pygame.draw.circle(surf, C.ROVER, pr.center, max(2, cell // 2 - 1))

    cr = pygame.Rect(ox + cursor[0] * cell, oy + cursor[1] * cell, cell, cell)
    pygame.draw.rect(surf, C.MARK, cr.inflate(2, 2), 2)

    foot = [f"cursor ({cursor[0]}, {cursor[1]})    blue = the plan    "
            "shaded = the drive    pale = the pad",
            "WASD move cursor    X mark/unmark    M or ESC close"]
    for i, line in enumerate(foot):
        s = f.hud.render(line, True, C.MUTED)
        surf.blit(s, s.get_rect(midtop=(surf.get_width() // 2, oy + a.h * cell + 14 + i * 20)))


def _panel(surf, f, title, sub, n_lines, width=520, line_h=22):
    overlay = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    overlay.fill((*C.VOID, 240))
    surf.blit(overlay, (0, 0))

    box = pygame.Rect(0, 0, width, 104 + line_h * max(1, n_lines))
    box.center = (surf.get_width() // 2, surf.get_height() // 2)
    pygame.draw.rect(surf, C.CHAT_BG, box)
    pygame.draw.rect(surf, C.FAINT, box, 1)

    t = f.big.render(title, True, C.INK)
    surf.blit(t, t.get_rect(midtop=(box.centerx, box.top + 14)))
    if sub:
        s = f.hud.render(sub, True, C.MUTED)
        surf.blit(s, s.get_rect(midtop=(box.centerx, box.top + 40)))
    return box


def _foot(surf, f, box, text):
    h = f.tiny.render(text, True, C.MUTED)
    surf.blit(h, h.get_rect(midbottom=(box.centerx, box.bottom - 14)))


CONSOLE_LINES = 14


def draw_console(surf, w, f, line, history):
    """The planner's front door. What it prints is what gemma reads, verbatim."""
    box = _panel(surf, f, "CONSOLE", "the same strings the model gets back",
                 CONSOLE_LINES + 1, width=surf.get_width() - 60, line_h=20)

    y = box.top + 70
    for text, tone in history[-CONSOLE_LINES:]:
        col = {"good": C.GOOD, "bad": C.BAD}.get(tone, C.INK)
        surf.blit(f.hud.render(text[:92], True, col), (box.left + 24, y))
        y += 20

    y = box.bottom - 46
    pygame.draw.line(surf, C.FAINT, (box.left + 24, y - 6), (box.right - 24, y - 6))
    surf.blit(f.hud.render(f"> {line}_", True, C.INK), (box.left + 24, y))
    _foot(surf, f, box, "ENTER run    help for commands    T or ESC close")


def draw_quit(surf, w, f, run, mission_over=False):
    """The one question asked at the end. Nothing is buffered waiting for the answer --
    the logs are already on disk and this only decides what happens to them."""
    box = _panel(surf, f, "MISSION OVER" if mission_over else "END OF SESSION",
                 f"sol {w.day}, {w.steps} steps driven, {w.elapsed:.0f}s elapsed", 5)
    where = run.dir.name if run else "nothing recorded"
    rows = [(f"  K   keep the run       runs/{run.stamp if run else '--'}/", C.GOOD),
            (f"      resume it later    --resume runs/{run.stamp if run else '--'}", C.MUTED),
            ("  D   discard it          nothing is left behind", C.BAD),
            ("  ESC cancel, keep playing", C.MUTED)]
    for i, (text, col) in enumerate(rows):
        surf.blit(f.hud.render(text, True, col), (box.left + 40, box.top + 76 + i * 24))
    _foot(surf, f, box, f"currently writing to {where}")


# --- the chat pane ---------------------------------------------------------
# Black, flat and monospace. It is the room the rover is driven from, not part of the
# game, and it should not look like one.

CHAT_PAD = 20
CHAT_LINE_H = 17
CHAT_INDENT = 14
# Headings rather than inline prefixes -- a wrapped paragraph that keeps its indent
# reads better than one carrying a tag on line one.
HEADS = {"status": ("SOL OPEN", C.CHAT_GOOD),
         "you": ("OPERATOR", C.CHAT_OPERATOR),
         "urgent": ("OPERATOR · URGENT", C.CHAT_BAD),
         "brief": ("MISSION CLOCK · BRIEFED", C.CHAT_OPERATOR),
         # Not the operator's colour: nobody coached a sol the clock opened.
         "auto": ("MISSION CLOCK", C.CHAT_GOOD),
         "gemma": ("PLANNER", C.CHAT_PLANNER),
         "think": ("PLANNER · reasoning", C.CHAT_THINK),
         "error": ("!!", C.CHAT_BAD),
         "note": ("", C.CHAT_THINK),
         # The view is summarised to a line here and written in full to the tape -- the
         # human has the real arena on the left and does not need the ASCII.
         "view": ("", C.CHAT_THINK),
         "call": ("SKILL", C.CHAT_SKILL),
         "result": ("", C.CHAT_RESULT)}


def _blocks(conv, cols, show_thinking=True):
    """Every line the pane could show, wrapped, as (text, colour, indent).

    The two streaming buffers are appended live, so a reply appears as it arrives
    rather than in one lump when it finishes. Thinking is dropped here rather than
    where it is recorded: hiding it is a display choice and the tape keeps it either
    way, so turning it off can never cost a run its record.
    """
    out = []
    live = ([("think", conv.think_buf)] if conv.think_buf.strip() else []) + \
           ([("gemma", conv.say_buf)] if conv.say_buf.strip() else [])
    for who, text in list(conv.lines) + live:
        if who == "think" and not show_thinking:
            continue
        head, colour = HEADS.get(who, ("", C.CHAT_TEXT))
        if head:
            out.append((head, colour, False))
        for para in text.splitlines() or [""]:
            for piece in (textwrap.wrap(para, cols) or [""]):
                out.append((piece, colour, True))
        out.append(("", colour, False))
    return out


def _overlay_lines(text, cols):
    """The view block, wrapped only where it has to be, at full pane width.

    Not indented and not given a speaker head: it is the request, verbatim, and the point
    of looking at it is that it is character-for-character what gemma was sent. Wrapping
    keeps `drop_whitespace` off because the grid's row labels are leading spaces, and
    eating them would shift every row of the picture by two columns -- a rendering bug
    that looks exactly like the model misreading its own map.
    """
    return [(piece, C.CHAT_MUTED, False)
            for para in text.splitlines()
            for piece in (textwrap.wrap(para, cols, drop_whitespace=False) or [""])]


def _pad_lines(w, cols, open_):
    """The scratchpad: her list as checkboxes, then the note and the orders under it."""
    n = w.notes
    head = f"SCRATCHPAD   {n.open} open of {len(n.todos)}"
    if not open_:
        return [(head + "   P to show", C.CHAT_MUTED, False)]
    out = [(head + "   P to hide", C.CHAT_MUTED, False)]
    for i, (text, struck) in enumerate(n.todos, 1):
        box = "[x]" if struck else "[ ]"
        tone = C.CHAT_MUTED if struck else C.CHAT_TEXT
        for k, piece in enumerate(textwrap.wrap(text, cols - 7) or [""]):
            out.append(((f"{box} {i:>2} " if k == 0 else " " * 7) + piece, tone, True))
    if not n.todos:
        out.append(("nothing on today's list", C.CHAT_THINK, True))
    sections = (("MEMORY", [f"{k}: {v}" for k, v in n.memory.items()], C.CHAT_PLANNER),
                ("STANDING ORDERS", [f"{i}. {t}" for i, t in enumerate(n.orders, 1)],
                 C.CHAT_OPERATOR))
    for title, items, tone in sections:
        out.append((title, C.CHAT_MUTED, False))
        for item in items:
            for line in item.splitlines():
                for piece in textwrap.wrap(line, cols) or [""]:
                    out.append((piece, tone, True))
        if not items:
            out.append(("(none)", C.CHAT_THINK, True))
    return out


def draw_chat(surf, conv, w, f, line, focused, scroll, show_thinking=True, reel=None,
              overlay=None, pad=None, pilot=None):
    """The right-hand pane. Returns how far back it is still possible to scroll.

    `overlay` replaces the transcript with a block to read -- V, and the view. It is
    drawn instead of the conversation rather than appended to it, so looking at what
    gemma was sent cannot cost you the conversation you were reading.
    """
    surf.fill(C.CHAT_BG)
    pygame.draw.line(surf, C.CHAT_RULE, (0, 0), (0, surf.get_height()), 1)
    W, H = surf.get_size()
    x, inner = CHAT_PAD, W - CHAT_PAD * 2
    cols = max(24, (inner - CHAT_INDENT) // f.chat.size("M")[0])
    head_h, foot_h = 66, 56

    surf.blit(f.big.render("MISSION PLANNER", True, C.CHAT_TEXT), (x, 14))
    link = conv.link
    sub = (f"{link.model}{'  (fallback)' if link.down else ''}   ·   sol {conv.day}   ·   "
           + ("comms on" if S.COMMS else "comms off"))
    if not show_thinking:
        sub += "   ·   reasoning hidden"
    surf.blit(f.tiny.render(sub, True, C.CHAT_MUTED), (x, 40))

    # The held state gets its own word. Without it the pane reads "ready" for the
    # several seconds the planner is deliberately sitting still, which looks like a
    # hang rather than the round trip it is.
    if conv.waiting and conv.link.hold:
        state, tone = f"checking whether {S.MODEL} is back...", C.CHAT_SKILL
    elif reel and reel.work:
        (x_, y_), done, total = reel.work
        state, tone = f"working at ({x_},{y_})  ·  {done}/{total} steps", C.CHAT_SKILL
    elif conv.waiting or (reel and reel.busy and conv.busy):
        state, tone = "waiting for the rover...", C.CHAT_SKILL
    elif conv.busy:
        state, tone = ("thinking..." if not conv.say_buf else "answering..."), C.CHAT_GOOD
    elif pilot and pilot.wait:
        left = pilot.wait_left()
        last = bool(S.MISSION_SOLS) and w.day >= S.MISSION_SOLS
        state = {"dawn": f"DAWN OF SOL {w.day}  ·  talk, post orders, or /next",
                 "radio": "ON THE RADIO  ·  answer, or /next  ·  the clock runs",
                 "dusk": f"DUSK OF SOL {w.day}  ·  her report  ·  /next",
                 "night": ("MISSION OVER" if last else f"NIGHT OF SOL {w.day}")
                          + "  ·  talk, or /next"}[pilot.wait]
        state += (f"  ·  {left:.0f}s" if left is not None else "  ·  holding")
        tone = C.CHAT_BAD if pilot.wait == "radio" else C.CHAT_GOOD
    elif w.day_over and w.lost:
        state, tone = (f"ROVER LOST on sol {w.day}  ·  cannot reach the pad  ·  "
                       f"ESC to finish", C.CHAT_BAD)
    elif w.day_over and S.MISSION_SOLS and w.day >= S.MISSION_SOLS:
        # A replay plays what its tape holds; only a live run can be played on.
        more = "" if getattr(conv, "script", None) else "T, then  sols N  for more  ·  "
        state, tone = f"MISSION OVER after {w.day} sols  ·  {more}ESC to finish", C.CHAT_BAD
    elif w.day_over and w.phase == "day":
        state, tone = f"SOL {w.day}: THE DAY IS OVER", C.CHAT_BAD
    elif conv.last:
        secs, pin, pout = conv.last
        state, tone = f"{secs}s   {pin} tok in, {pout} out", C.CHAT_MUTED
    else:
        state, tone = "ready", C.CHAT_MUTED
    t = f.tiny.render(state, True, tone)
    surf.blit(t, t.get_rect(topright=(x + inner, 40)))

    pygame.draw.line(surf, C.CHAT_RULE, (x, head_h - 8), (x + inner, head_h - 8))
    pygame.draw.line(surf, C.CHAT_RULE, (x, H - foot_h), (x + inner, H - foot_h))

    # The scratchpad sits above the transcript and takes at most two fifths of it.
    if pad is not None and overlay is None:
        rows_pad = _pad_lines(w, cols, pad)
        fit = (H - head_h - foot_h) * 2 // 5 // CHAT_LINE_H
        if len(rows_pad) > fit:
            rows_pad = rows_pad[:fit - 1] + [("...", C.CHAT_MUTED, True)]
        for i, (text, colour, indent) in enumerate(rows_pad):
            font = f.chat if indent else f.chat_head
            surf.blit(font.render(text, True, colour),
                      (x + (CHAT_INDENT if indent else 0), head_h + i * CHAT_LINE_H))
        head_h += len(rows_pad) * CHAT_LINE_H + 6
        pygame.draw.line(surf, C.CHAT_RULE, (x, head_h - 4), (x + inner, head_h - 4))

    body_h = H - head_h - foot_h
    rows = body_h // CHAT_LINE_H
    lines = (_blocks(conv, cols, show_thinking) if overlay is None else
             _overlay_lines(overlay, max(24, inner // f.chat.size("M")[0])))
    max_scroll = max(0, len(lines) - rows)
    top = max(0, len(lines) - rows - min(scroll, max_scroll))
    for i, (text, colour, indent) in enumerate(lines[top:top + rows]):
        font = f.chat if indent else f.chat_head
        surf.blit(font.render(text, True, colour),
                  (x + (CHAT_INDENT if indent else 0), head_h + i * CHAT_LINE_H))

    y = H - foot_h + 12
    if focused:
        shown = line[-(cols - 2):]
        surf.blit(f.chat.render(f"> {shown}_", True, C.CHAT_TEXT), (x, y))
    else:
        surf.blit(f.chat.render("TAB to type", True, C.CHAT_MUTED), (x, y))
    hint = ("V or ESC back to the conversation    wheel scrolls" if overlay is not None
            else "ENTER send    ESC stop typing    /help lists the commands" if focused
            else "TAB her chat   T terminal   V what she sees   H thinking   P scratchpad   "
                 "O settings")
    surf.blit(f.tiny.render(hint, True, C.CHAT_MUTED), (x, H - 22))
    if scroll:
        s = f.tiny.render(f"scrolled back {scroll}", True, C.CHAT_BAD)
        surf.blit(s, s.get_rect(topright=(x + inner, H - 22)))
    return max_scroll


# --- the settings screen ---------------------------------------------------
# Plain on purpose: the UI team restyles it from `registry`, they do not rebuild it.

def draw_settings(surf, f, items, picked, prefs, editing, notice, models, replaying):
    """Every registry setting over the whole window, grouped by when a change lands."""
    surf.fill(C.CHAT_BG)
    W_, H_ = surf.get_size()
    x = 40
    surf.blit(f.big.render("SETTINGS", True, C.INK), (x, 20))
    sub = (f"yours are saved in {registry.USER_FILE.name}, which git ignores"
           if not replaying else "replay: the kept run's settings are in force")
    surf.blit(f.hud.render(sub, True, C.MUTED), (x, 48))

    lines = []          # (text, colour, item index or None)
    tier = None
    for i, (kind, it) in enumerate(items):
        if kind == "preset":
            lines.append((f"load preset: {it}", C.CHAT_SKILL, i))
            continue
        if it.tier != tier:
            tier = it.tier
            lines.append(("", C.MUTED, None))
            lines.append((registry.TIER_NAMES[tier].upper(), C.MUTED, None))
        shown = prefs.shown(it)
        text = f"{it.name:<16} {registry.show(shown)}"
        if it.tier == "sol" and it.name in prefs.pending:
            text += f"    (now {registry.show(it.value)})"
        elif it.tier == "relaunch" and shown != it.value:
            text += f"    (now {registry.show(it.value)})"
        if shown != it.default:
            text += f"    default {registry.show(it.default)}"
        locked = replaying and it.tier != "now"
        lines.append((text, C.MUTED if locked else C.INK, i))

    line_h = 20
    top, foot = 80, 110
    rows = (H_ - top - foot) // line_h
    at = next(n for n, (_, _, i) in enumerate(lines) if i == picked)
    first = max(0, min(at - rows // 2, len(lines) - rows))
    for n, (text, colour, i) in enumerate(lines[first:first + rows]):
        y = top + n * line_h
        if i == picked:
            pygame.draw.rect(surf, C.FAINT, (x - 8, y - 2, W_ - 2 * x + 16, line_h))
            if editing is not None:
                text = f"{text.split()[0]:<16} > {editing}_"
        surf.blit(f.hud.render(text, True, colour), (x, y))

    kind, it = items[picked]
    if kind == "preset":
        about = ", ".join(f"{k} {registry.show(v)}"
                          for k, v in registry.PRESETS[it].items())
    else:
        about = f"{it.desc}.  {registry.TIER_NAMES[it.tier]}."
        if it.kind in ("int", "float"):
            about += f"  {registry.show(it.lo)} to {registry.show(it.hi)}."
        elif it.choices:
            about += "  " + " / ".join(registry.show(c) for c in it.choices) + "."
    if kind == "setting" and it.name == "MODEL" and models is None:
        about += "  Ollama did not answer, so no list; ENTER types a tag."
    y = H_ - foot + 10
    pygame.draw.line(surf, C.FAINT, (x, y - 8), (W_ - x, y - 8))
    for piece in textwrap.wrap(about, max(40, (W_ - 2 * x) // f.hud.size("M")[0]))[:2]:
        surf.blit(f.hud.render(piece, True, C.INK), (x, y))
        y += 20
    if notice:
        surf.blit(f.hud.render(notice, True, C.CHAT_SKILL), (x, y))
    keys = ("ENTER save    ESC cancel" if editing is not None else
            "UP/DOWN choose    LEFT/RIGHT change    ENTER type a value or load a preset"
            "    R default    O or ESC close")
    surf.blit(f.tiny.render(keys, True, C.MUTED), (x, H_ - 24))
