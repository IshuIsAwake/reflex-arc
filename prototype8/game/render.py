"""All the pygame drawing. Martian red-brown and black, one pale dot.

Two surfaces, and they do not look like the same program on purpose. The left is
terrain -- warm, textured, lit where the rover is. The right is a console: black, flat,
monospace, no decoration at all. The rover's world and the room it is driven from.
"""

import textwrap

import pygame

import config as C
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
            elif ch == "H" or ch in W.GLYPHS:
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
        elif ch in W.GLYPHS:
            _objective(surf, rect, ch, lit)
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

    if reel.scout:
        # Outline only, and drawn over the fog without lifting it -- for the half
        # second before `scoutlift` fires, the window sits framing black. That frame
        # is the one worth having: a square of nothing, and then it is ground.
        cx, cy = reel.scout
        rr = S.SCOUT_BOX
        rect = _cell_rect(ox, oy, (cx - rr, cy - rr))
        rect.width = rect.height = (2 * rr + 1) * C.TILE
        pygame.draw.rect(surf, C.SCOUT, rect, 2)
        pygame.draw.circle(surf, C.SCOUT, _cell_rect(ox, oy, (cx, cy)).center, 3)

    if reel.bump:
        box = _cell_rect(ox, oy, reel.bump)
        pygame.draw.rect(surf, C.BUMP, box, 2)
        pygame.draw.line(surf, C.BUMP, box.topleft, box.bottomright, 2)
        pygame.draw.line(surf, C.BUMP, box.topright, box.bottomleft, 2)


def _objective(surf, rect, ch, lit):
    """An instrument to be worked, drawn as a ring so the ground still shows through.

    Priority picks the hue and the three are the traffic-light order, which is the one
    ranking the environment is allowed to hand over -- it is a fact about the mission,
    not a judgement about what to do first.
    """
    col = {"1": C.BAD, "2": C.PLAN, "3": C.GOOD}.get(ch, C.INK)
    if not lit:
        col = tuple(int(v * 0.55) for v in col)
    r = max(2, rect.width // 2 - 2)
    pygame.draw.circle(surf, col, rect.center, r, max(1, rect.width // 6))


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
    """Whichever thing the day is actually made of. One wording, changed in one place
    when the clock lands."""
    if S.DAY_MODE == "human":
        mins, secs = divmod(max(0, int(w.time_left)), 60)
        return f"{mins}:{secs:02d}"
    return f"{w.steps_left} steps"


def _hud(surf, w, f, reel=None):
    y0 = surf.get_height() - C.HUD_H
    pygame.draw.line(surf, C.FAINT, (0, y0), (surf.get_width(), y0), 1)

    surf.blit(f.big.render(f"SOL {w.day}    {budget(w)}", True, C.INK), (MARGIN, y0 + 12))
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
    surf.blit(f.tiny.render(hint + "TAB talk   H thinking   Q end sol   ESC quit",
                            True, C.FAINT), (MARGIN, y0 + 84))

    for i, (msg, tone) in enumerate(reversed(w.log[-3:])):
        col = {"good": C.GOOD, "bad": C.BAD}.get(tone, C.INK)
        shade = tuple(min(255, int(v * (1 - i * 0.3))) for v in col)
        surf.blit(f.hud.render(msg[:64], True, shade), (MARGIN + 300, y0 + 14 + i * 22))


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
                _objective(surf, r, ch, True)
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


def draw_quit(surf, w, f, run):
    """The one question asked at the end. Nothing is buffered waiting for the answer --
    the logs are already on disk and this only decides what happens to them."""
    box = _panel(surf, f, "END OF SESSION",
                 f"sol {w.day}, {w.steps} steps driven, {w.elapsed:.0f}s elapsed", 4)
    where = run.dir.name if run else "nothing recorded"
    rows = [(f"  K   keep the logs      runs/{run.stamp if run else '--'}/", C.GOOD),
            ("  D   discard them        nothing is left behind", C.BAD),
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


def draw_chat(surf, conv, w, f, line, focused, scroll, show_thinking=True, reel=None,
              overlay=None):
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
    sub = f"{S.MODEL}   ·   sol {conv.day}"
    if not show_thinking:
        sub += "   ·   reasoning hidden"
    surf.blit(f.tiny.render(sub, True, C.CHAT_MUTED), (x, 40))

    # The held state gets its own word. Without it the pane reads "ready" for the
    # several seconds the planner is deliberately sitting still, which looks like a
    # hang rather than the round trip it is.
    if conv.waiting or (reel and reel.busy and conv.busy):
        state, tone = "waiting for the rover...", C.CHAT_SKILL
    elif conv.busy:
        state, tone = ("thinking..." if not conv.say_buf else "answering..."), C.CHAT_GOOD
    elif w.day_over:
        state, tone = f"SOL {w.day} OVER  ·  talk, then N for sol {w.day + 1}", C.CHAT_BAD
    elif conv.last:
        secs, pin, pout = conv.last
        state, tone = f"{secs}s   {pin} tok in, {pout} out", C.CHAT_MUTED
    else:
        state, tone = "ready", C.CHAT_MUTED
    t = f.tiny.render(state, True, tone)
    surf.blit(t, t.get_rect(topright=(x + inner, 40)))

    pygame.draw.line(surf, C.CHAT_RULE, (x, head_h - 8), (x + inner, head_h - 8))
    pygame.draw.line(surf, C.CHAT_RULE, (x, H - foot_h), (x + inner, H - foot_h))

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
            else "ENTER send    ESC stop typing    /status resend the line" if focused
            else "TAB talk    V what it sees    H thinking    N next sol    wheel scrolls")
    surf.blit(f.tiny.render(hint, True, C.CHAT_MUTED), (x, H - 22))
    if scroll:
        s = f.tiny.render(f"scrolled back {scroll}", True, C.CHAT_BAD)
        surf.blit(s, s.get_rect(topright=(x + inner, H - 22)))
    return max_scroll
