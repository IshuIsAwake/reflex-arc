"""Everything drawn with pygame: the arena, the map, the chat pane, the terminal, the quit question and the settings screen."""

import textwrap

import pygame

import config
import registry
import settings
from world import GLYPHS, INTEREST
import dashboard
import terrain_art

MARGIN = 15
MIN_PANE = 460  # narrower than this and the pane wraps into uselessness
DISPLAY_SIZE = None


def game_size():
    """The arena surface's size."""
    if DISPLAY_SIZE is not None:
        return DISPLAY_SIZE[0] - settings.CHAT_W, DISPLAY_SIZE[1]
    return config.VIEW_W * config.TILE + MARGIN * 2, config.VIEW_H * config.TILE + config.HUD_H + MARGIN * 2 + dashboard.HEADER


def layout(width, height):
    """Every size from the window's: the biggest tile that fits the arena's height while the
    pane keeps MIN_PANE. Returns the arena's rect and the pane's. Called again on every resize."""
    global DISPLAY_SIZE
    DISPLAY_SIZE = (width, height)
    config.TILE = max(3, min((width - MIN_PANE - MARGIN * 2) // config.VIEW_W,
                        (height - config.HUD_H - MARGIN * 2 - dashboard.HEADER) // config.VIEW_H))
    settings.CHAT_W = width - (config.VIEW_W * config.TILE + MARGIN * 2)
    gw, gh = game_size()
    return pygame.Rect(0, 0, gw, gh), pygame.Rect(gw, 0, settings.CHAT_W, gh)


class Fonts:
    def __init__(self):
        mono = "dejavusansmono,consolas,monospace"
        self.tiny = pygame.font.SysFont(mono, 12)
        self.hud = pygame.font.SysFont(mono, 14)
        self.big = pygame.font.SysFont(mono, 19, bold=True)
        self.chat = pygame.font.SysFont(mono, 15)
        self.chat_head = pygame.font.SysFont(mono, 12, bold=True)
        self.brand = pygame.font.SysFont(mono, 23, bold=True)


def viewport(surf, area, pos):
    """Pixel origin of cell (0,0), and the rect the arena may paint in. A small arena sits
    centred; a bigger one scrolls to follow the rover."""
    def axis(span, view, here, screen_span, top):
        room = view * config.TILE
        base = top + (screen_span - room) // 2
        if span <= view:
            return base + (room - span * config.TILE) // 2, base
        cam = max(0, min(here - view // 2, span - view))
        return base - cam * config.TILE, base

    play_h = surf.get_height() - config.HUD_H - dashboard.HEADER
    ox, vx = axis(area.w, config.VIEW_W, pos[0], surf.get_width(), 0)
    oy, vy = axis(area.h, config.VIEW_H, pos[1], play_h, dashboard.HEADER)
    return (ox, oy), pygame.Rect(vx, vy, config.VIEW_W * config.TILE, config.VIEW_H * config.TILE)


# Pebbles, from a hash of the cell, so they never move between frames. Decoration only:
# sight.py never sees them.
def _grit(x, y):
    """0-3 pebbles for this cell, as (dx, dy, radius, lighter) at tile scale."""
    h = (x * 73856093) ^ (y * 19349663)
    h = (h ^ (h >> 13)) & 0x7FFFFFFF
    n = (h % 7) // 3  # about a third of cells get any
    out = []
    for i in range(n):
        b = h >> (4 + i * 9)
        out.append(((b % 5) + 1, ((b >> 3) % 5) + 1,
                    1 + ((b >> 6) % 2), bool((b >> 8) & 1)))
    return out


def _ground(surf, rect, x, y, lit):
    """Ground, with the cell's pebbles on it."""
    pygame.draw.rect(surf, config.REGOLITH if lit else config.REGOLITH_DIM, rect)
    step = max(2, rect.width // 5)
    for dx, dy, r, pale in _grit(x, y):
        col = config.GRIT_LIT if (pale and lit) else config.GRIT
        pygame.draw.circle(surf, col, (rect.x + dx * step, rect.y + dy * step), r)


def _rock(surf, rect, x, y, art, lit):
    """A rock cell: ground, with its piece of the rock's rounded shape on top."""
    pygame.draw.rect(surf, config.REGOLITH if lit else config.REGOLITH_DIM, rect)
    surf.blit(art, rect, (x * rect.width, y * rect.height, rect.width, rect.height))


def _seen_rocks(a, reel):
    """The rocks the screen may show: not ones the reel is still holding under fog."""
    return frozenset((x, y) for y in range(a.h) for x in range(a.w)
                     if a.at(x, y) == "#" and a.visible(x, y)
                     and not (reel and reel.veiled((x, y))))


def _grid(surf, a, ox, oy):
    """A black line round every cell, so a coordinate can be counted off the map."""
    for x in range(a.w + 1):
        px = ox + x * config.TILE
        pygame.draw.line(surf, (0, 0, 0), (px, oy), (px, oy + a.h * config.TILE))
    for y in range(a.h + 1):
        py = oy + y * config.TILE
        pygame.draw.line(surf, (0, 0, 0), (ox, py), (ox + a.w * config.TILE, py))


def draw_world(surf, world, f, reel=None):
    """The arena. `reel`, while a drive is being drawn, says where the rover is drawn and which cells are still fog."""
    surf.fill(config.VOID)
    area = world.here
    px, py = reel.where(world.pos) if reel else world.pos
    (ox, oy), view = viewport(surf, area, (px, py))
    # Ground near the rover is drawn brighter.
    r2 = settings.VISION_RADIUS ** 2
    rock_lit, rock_dim = terrain_art.rocks(area.w, area.h, config.TILE, _seen_rocks(area, reel))

    lo_x, hi_x = (view.left - ox) // config.TILE - 1, (view.right - ox) // config.TILE + 1
    lo_y, hi_y = (view.top - oy) // config.TILE - 1, (view.bottom - oy) // config.TILE + 1
    surf.set_clip(view)

    things = []
    for y in range(max(0, lo_y), min(area.h, hi_y + 1)):
        for x in range(max(0, lo_x), min(area.w, hi_x + 1)):
            rect = pygame.Rect(ox + x * config.TILE, oy + y * config.TILE, config.TILE, config.TILE)
            if not area.visible(x, y) or (reel and reel.veiled((x, y))):
                pygame.draw.rect(surf, config.FOG, rect)
                continue

            lit = (x - px) ** 2 + (y - py) ** 2 <= r2
            ch = area.at(x, y)

            if ch == "#":
                _rock(surf, rect, x, y, rock_lit if lit else rock_dim, lit)
            elif ch == "H" or ch in GLYPHS or ch == INTEREST:
                things.append((rect, ch, lit, (x, y)))
                pygame.draw.rect(surf, config.REGOLITH if lit else config.REGOLITH_DIM, rect)
            else:
                _ground(surf, rect, x, y, lit)

            if (x, y) in area.marks:
                things.append((rect, None, lit, (x, y)))

    _grid(surf, area, ox, oy)
    for rect, ch, lit, cell in things:
        if ch == "H":
            _pad(surf, rect, lit)
        elif ch and ch in GLYPHS:  # a mark rides here with no tile of its own
            _objective(surf, rect, area.objectives[cell].priority, lit)
        elif ch == INTEREST:
            _interest(surf, rect, area.interests[cell].found, lit)
        if cell in area.marks:
            _x_mark(surf, rect)

    terrain_art.storm(surf, area.storm_cells, ox, oy, config.TILE)

    if reel:
        _reel(surf, reel, ox, oy)
    _sky(surf, world.phase, view)
    dashboard.rover(surf, ox + px * config.TILE + config.TILE // 2, oy + py * config.TILE + config.TILE // 2)
    surf.set_clip(None)
    _rim(surf, area, ox, oy)
    dashboard.map_overlay(surf, world, f, view, ox, oy, reel)
    dashboard.bottom(surf, world, f, reel)
    dashboard.header(surf, world, f)


def _cell_rect(ox, oy, cell):
    return pygame.Rect(ox + cell[0] * config.TILE, oy + cell[1] * config.TILE, config.TILE, config.TILE)


def _reel(surf, reel, ox, oy):
    """The drive being drawn: the trail it has covered, the planned route on top, and the cell that refused."""
    for cell in reel.trail:
        # Inset a pixel, so the grid line round the cell still shows.
        pygame.draw.rect(surf, config.WALKED, _cell_rect(ox, oy, cell).inflate(-2, -2))

    r = max(2, config.TILE // 4)
    for cell in reel.plan:
        pygame.draw.circle(surf, config.GOTO_ROUTE, _cell_rect(ox, oy, cell).center, r)
    for cell in reel.probe:
        pygame.draw.circle(surf, config.PATH, _cell_rect(ox, oy, cell).center, r)

    if reel.work:
        cell, done, total = reel.work
        box = _cell_rect(ox, oy, cell)
        pygame.draw.rect(surf, config.PLAN, box.inflate(4, 4), 2)
        bar = pygame.Rect(box.left, box.bottom + 2, max(1, box.width * done // total), 3)
        pygame.draw.rect(surf, config.PLAN, bar)

    if reel.bump:
        box = _cell_rect(ox, oy, reel.bump)
        pygame.draw.rect(surf, config.BUMP, box, 2)
        pygame.draw.line(surf, config.BUMP, box.topleft, box.bottomright, 2)
        pygame.draw.line(surf, config.BUMP, box.topright, box.bottomleft, 2)


def _objective(surf, rect, priority, lit):
    """An objective, as a ring coloured by priority."""
    col = {"high": config.BAD, "medium": config.PLAN, "low": config.GOOD}.get(priority, config.INK)
    if not lit:
        col = tuple(int(v * 0.55) for v in col)
    r = max(2, rect.width // 2 - 2)
    pygame.draw.circle(surf, col, rect.center, r, max(1, rect.width // 6))


def _interest(surf, rect, found, lit):
    """An interest, as a square. One she hasn't found is drawn faint, for the desk."""
    col = config.INTEREST if found else tuple(int(v * 0.35) for v in config.INTEREST)
    if not lit:
        col = tuple(int(v * 0.6) for v in col)
    inset = max(2, rect.width // 5)
    pygame.draw.rect(surf, col, rect.inflate(-inset * 2, -inset * 2),
                     max(1, rect.width // 7))


_SKY = {}


def _sky(surf, phase, view):
    """The phase washed over the arena: dark at night, lit from the east at dawn and the west at dusk."""
    if phase == "day":
        return
    key = (view.size, phase)
    if key not in _SKY:
        wash = pygame.Surface(view.size, pygame.SRCALPHA)
        width = max(1, view.width - 1)
        for x in range(view.width):
            east = x / width
            dark = {"night": 1.0, "dawn": 1.0 - east, "dusk": east}[phase]
            wash.fill((*config.NIGHT, int(config.NIGHT_ALPHA * dark)),
                      pygame.Rect(x, 0, 1, view.height))
        _SKY[key] = wash
    surf.blit(_SKY[key], view.topleft)


def _pad(surf, rect, lit):
    """The landing pad, filled edge to edge so its six cells read as one thing."""
    col = config.BASE if lit else config.BASE_DIM
    pygame.draw.rect(surf, col, rect)
    pygame.draw.rect(surf, config.ROVER_RING, rect.inflate(-rect.width + 4, -rect.height + 4))


def _rim(surf, a, ox, oy):
    """The arena has no wall, so draw a line where the ground stops."""
    pygame.draw.rect(surf, config.FAINT,
                     pygame.Rect(ox - 1, oy - 1, a.w * config.TILE + 2, a.h * config.TILE + 2), 1)


def _x_mark(surf, rect):
    r = rect.inflate(-4, -4)
    pygame.draw.line(surf, config.CYAN, r.topleft, r.bottomright, 2)
    pygame.draw.line(surf, config.CYAN, r.topright, r.bottomleft, 2)


def _map_cell(surf, area, x, y, r, rock_lit, walked):
    """One seen cell of the M map."""
    ch = area.at(x, y)
    if ch == "#":
        _rock(surf, r, x, y, rock_lit, True)
    elif ch == "H":
        _pad(surf, r, True)
    elif ch in GLYPHS:
        pygame.draw.rect(surf, config.REGOLITH, r)
        _objective(surf, r, area.objectives[(x, y)].priority, True)
    elif ch == INTEREST:
        pygame.draw.rect(surf, config.REGOLITH, r)
        _interest(surf, r, area.interests[(x, y)].found, True)
    else:
        _ground(surf, r, x, y, True)
        if walked:
            pygame.draw.circle(surf, config.WALKED, r.center, max(1, r.width // 8))


def draw_map(surf, world, f, cursor, reel=None):
    """The M map: the whole arena, scaled to fit, with the plan and the drive over it."""
    area = world.here
    overlay = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    overlay.fill((*config.VOID, 253))
    surf.blit(overlay, (0, 0))

    cell = max(2, min((surf.get_width() - 80) // area.w, (surf.get_height() - 140) // area.h))
    ox = (surf.get_width() - area.w * cell) // 2
    oy = 72

    seen = sum(1 for x, y in area.cells() if area.visible(x, y))
    dashboard.text(surf, f.big, config.ARENA_NAME.upper(), (24, 18), config.INK,
                   surf.get_width() - 210)
    dashboard.text(surf, f.tiny, f'{seen} / {area.w * area.h} CELLS SURVEYED',
                   (24, 44), config.MUTED, surf.get_width() - 210)

    for x in range(0, area.w, 5):
        s = f.tiny.render(str(x), True, config.MUTED)
        surf.blit(s, s.get_rect(midbottom=(ox + x * cell + cell // 2, oy - 2)))
    for y in range(0, area.h, 5):
        s = f.tiny.render(str(y), True, config.MUTED)
        surf.blit(s, s.get_rect(midright=(ox - 4, oy + y * cell + cell // 2)))

    # The drive is shaded into the ground; the plan is dots on top. Where they differ is where the fog lied.
    rock_lit, _ = terrain_art.rocks(area.w, area.h, cell, _seen_rocks(area, reel))
    walk_area, walked = world.last_walk
    if reel and reel.busy:
        walked = set(reel.trail)
    elif walk_area == area.name:
        walked = set(walked)
    else:
        walked = set()

    for x, y in area.cells():
        r = pygame.Rect(ox + x * cell, oy + y * cell, cell, cell)
        if not area.visible(x, y) or (reel and reel.veiled((x, y))):
            pygame.draw.rect(surf, config.FOG, r)
            continue
        _map_cell(surf, area, x, y, r, rock_lit, (x, y) in walked)
        if (x, y) in area.marks:
            _x_mark(surf, r)

    terrain_art.storm(surf, area.storm_cells, ox, oy, cell)

    path_area, path = world.last_path
    path_color = config.PATH
    if reel and reel.busy:
        path_area, path = area.name, reel.plan or reel.probe
        path_color = config.GOTO_ROUTE if reel.plan else config.PATH
    if path_area == area.name:
        for cx, cy in path:
            r = pygame.Rect(ox + cx * cell, oy + cy * cell, cell, cell)
            pygame.draw.circle(surf, path_color, r.center, max(2, cell // 5))

    pos = reel.where(world.pos) if reel else world.pos
    pr = pygame.Rect(ox + pos[0] * cell, oy + pos[1] * cell, cell, cell)
    dashboard.rover(surf, *pr.center, size=cell)

    cr = pygame.Rect(ox + cursor[0] * cell, oy + cursor[1] * cell, cell, cell)
    pygame.draw.rect(surf, config.CYAN, cr.inflate(2, 2), 2)
    if settings.MAP_LABELS:
        view = pygame.Rect(ox, oy, area.w * cell, area.h * cell)
        dashboard.map_telemetry(surf, world, f, view, ox, oy, cell, reel)

    foot = [f"cursor ({cursor[0]}, {cursor[1]})    blue = the plan    "
            "dots = the drive    teal = the pad",
            "WASD cursor   X mark   M / ESC close"]
    for i, line in enumerate(foot):
        s = f.hud.render(line, True, config.MUTED)
        surf.blit(s, s.get_rect(midtop=(surf.get_width() // 2, oy + area.h * cell + 14 + i * 20)))


def _panel(surf, f, title, sub, n_lines, width=520, line_h=22):
    overlay = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    overlay.fill((*config.VOID, 240))
    surf.blit(overlay, (0, 0))

    width = min(width, surf.get_width() - 28)
    box = pygame.Rect(0, 0, width, min(surf.get_height() - 28, 104 + line_h * max(1, n_lines)))
    box.center = (surf.get_width() // 2, surf.get_height() // 2)
    pygame.draw.rect(surf, config.CHAT_BG, box)
    pygame.draw.rect(surf, config.FAINT, box, 1)

    t = f.big.render(title, True, config.INK)
    surf.blit(t, t.get_rect(midtop=(box.centerx, box.top + 14)))
    if sub:
        s = f.hud.render(sub, True, config.MUTED)
        surf.blit(s, s.get_rect(midtop=(box.centerx, box.top + 40)))
    return box


def _foot(surf, f, box, text):
    h = f.tiny.render(text, True, config.MUTED)
    surf.blit(h, h.get_rect(midbottom=(box.centerx, box.bottom - 14)))


CONSOLE_LINES = 14


def _typed(surf, font, prompt, line, caret, pos, cols, colour):
    """`prompt`, then the line being typed with a bar at the caret. A long line scrolls to keep the caret in view."""
    start = max(0, caret - cols)
    surf.blit(font.render(prompt + line[start:start + cols], True, colour), pos)
    x = pos[0] + font.size(prompt + line[start:caret])[0]
    pygame.draw.line(surf, colour, (x, pos[1]), (x, pos[1] + font.get_height() - 2), 2)


def draw_console(surf, world, f, line, history, caret=None):
    """The terminal (T). It prints exactly what the model would get back."""
    box = _panel(surf, f, "CONSOLE", "the same strings the model gets back",
                 CONSOLE_LINES + 1, width=surf.get_width() - 60, line_h=20)

    y = box.top + 70
    for text, tone in history[-CONSOLE_LINES:]:
        col = {"good": config.GOOD, "bad": config.BAD}.get(tone, config.INK)
        dashboard.text(surf, f.hud, text, (box.left + 24, y), col, box.width - 48)
        y += 20

    y = box.bottom - 46
    pygame.draw.line(surf, config.FAINT, (box.left + 24, y - 6), (box.right - 24, y - 6))
    cols = max(8, (box.width - 48) // f.hud.size("M")[0] - 3)
    _typed(surf, f.hud, "> ", line, len(line) if caret is None else caret,
           (box.left + 24, y), cols, config.INK)
    _foot(surf, f, box, "ENTER run    help for commands    T or ESC close")


def draw_quit(surf, world, f, run, mission_over=False):
    """The quit question. The logs are already on disk; this only decides what happens to them."""
    box = _panel(surf, f, "MISSION OVER" if mission_over else "END OF SESSION",
                 f"sol {world.day}, {world.steps} steps driven, {world.elapsed:.0f}s elapsed", 5)
    where = run.dir.name if run else "nothing recorded"
    rows = [(f"  K   keep the run       runs/{run.stamp if run else '--'}/", config.GOOD),
            (f"      resume it later    --resume runs/{run.stamp if run else '--'}", config.MUTED),
            ("  D   discard it          nothing is left behind", config.BAD),
            ("  ESC cancel, keep playing", config.MUTED)]
    for i, (text, col) in enumerate(rows):
        surf.blit(f.hud.render(text, True, col), (box.left + 40, box.top + 76 + i * 24))
    _foot(surf, f, box, f"currently writing to {where}")


# The chat pane

CHAT_PAD = 20
CHAT_LINE_H = 17
CHAT_INDENT = 14
# Each speaker gets a heading, so a wrapped paragraph keeps its indent.
HEADS = {"status": ("SOL OPEN", config.GOOD),
         "you": ("OPERATOR", config.CHAT_OPERATOR),
         "urgent": ("OPERATOR · URGENT", config.BAD),
         "auto": ("MISSION CLOCK", config.GOOD),
         "gemma": ("PLANNER", config.INK),
         "think": ("PLANNER · reasoning", config.CHAT_THINK),
         "error": ("!!", config.BAD),
         "note": ("", config.CHAT_THINK),
         # The view is one line here; the tape keeps it in full.
         "view": ("", config.CHAT_THINK),
         "call": ("SKILL", config.AMBER),
         "result": ("", config.CYAN)}


def _blocks(conv, cols, show_thinking=True):
    """Every line the pane could show, wrapped, as (text, colour, indent). Replies show as they stream in."""
    out = []
    live = ([("think", conv.think_buf)] if conv.think_buf.strip() else []) + \
           ([("gemma", conv.say_buf)] if conv.say_buf.strip() else [])
    for who, text in list(conv.lines) + live:
        if who == "think" and not show_thinking:
            continue
        head, colour = HEADS.get(who, ("", config.INK))
        if head:
            out.append((head, colour, False))
        for para in text.splitlines() or [""]:
            for piece in (textwrap.wrap(para, cols) or [""]):
                out.append((piece, colour, True))
        out.append(("", colour, False))
    return out


def _overlay_lines(text, cols):
    """The view block (V), wrapped only where it must be. Leading spaces are kept, or the grid's rows would shift."""
    return [(piece, config.MUTED, False)
            for para in text.splitlines()
            for piece in (textwrap.wrap(para, cols, drop_whitespace=False) or [""])]


def _draw_transcript(surf, conv, world, f, line, focused, scroll, show_thinking=True, reel=None,
              overlay=None, pilot=None, caret=None):
    """The chat, or `overlay` (the view) instead of it. Returns how far back it can scroll."""
    surf.fill(config.CHAT_BG)
    pygame.draw.line(surf, config.CHAT_RULE, (0, 0), (0, surf.get_height()), 1)
    width, height = surf.get_size()
    x = CHAT_PAD
    inner = width - CHAT_PAD * 2
    cols = max(24, (inner - CHAT_INDENT) // f.chat.size("M")[0])
    head_h = 88
    foot_h = 66

    surf.blit(f.big.render("AI PLANNER / LIVE FEED", True, config.INK), (x, 14))
    link = conv.link
    # The sol and comms are in the bar above, so only the model is shown here.
    sub = f"{link.model}{'  (fallback)' if link.down else ''}"
    if not show_thinking:
        sub += "   ·   reasoning hidden"
    dashboard.text(surf, f.tiny, sub, (x, 40), config.MUTED, inner)

    state, tone = chat_status(conv, world, reel, pilot)
    rendered = f.tiny.render(state, True, tone)
    surf.blit(rendered, rendered.get_rect(topleft=(x, 60)))

    pygame.draw.line(surf, config.CHAT_RULE, (x, head_h - 8), (x + inner, head_h - 8))
    pygame.draw.line(surf, config.CHAT_RULE, (x, height - foot_h), (x + inner, height - foot_h))

    body_h = height - head_h - foot_h
    rows = body_h // CHAT_LINE_H
    if overlay is None:
        lines = _blocks(conv, cols, show_thinking)
    else:
        lines = _overlay_lines(overlay, max(24, inner // f.chat.size("M")[0]))
    max_scroll = max(0, len(lines) - rows)
    top = max(0, len(lines) - rows - min(scroll, max_scroll))
    for i, (text, colour, indent) in enumerate(lines[top:top + rows]):
        font = f.chat if indent else f.chat_head
        surf.blit(font.render(text, True, colour),
                  (x + (CHAT_INDENT if indent else 0), head_h + i * CHAT_LINE_H))

    y = height - foot_h + 12
    if focused:
        if caret is None:
            caret = len(line)
        _typed(surf, f.chat, "> ", line, caret, (x, y), cols - 2, config.INK)
    else:
        surf.blit(f.chat.render("TAB to type", True, config.MUTED), (x, y))
    if overlay is not None:
        hint = "V or ESC back to the conversation    wheel scrolls"
    elif focused:
        hint = "ENTER send    ESC stop typing    /help lists the commands"
    else:
        hint = "TAB her chat   T terminal   V what she sees   H thinking   P memory   O settings"
    for i, part in enumerate(dashboard.key_lines(f.tiny, hint, inner)[:2]):
        surf.blit(f.tiny.render(part, True, config.MUTED), (x, height - 34 + i * 16))
    if scroll:
        rendered = f.tiny.render(f"scrolled back {scroll}", True, config.BAD)
        surf.blit(rendered, rendered.get_rect(topright=(x + inner, height - 22)))
    return max_scroll


def chat_status(conv, world, reel, pilot):
    """The status line under the model's name, as (text, colour): what she and the rover
    are doing."""
    if world.awaiting_rover is not None:
        leg = " ".join(world.awaiting_rover)[:40]
        return f"ROVER DRIVING {leg}  ·  {dashboard.ROVER_HINT}", config.GOOD
    if conv.waiting and conv.link.hold:
        return f"checking whether {settings.MODEL} is back...", config.AMBER
    if reel and reel.work:
        (wx, wy), done, total = reel.work
        return f"working at ({wx},{wy})  ·  {done}/{total} steps", config.AMBER
    if conv.waiting or (reel and reel.busy and conv.busy):
        return "waiting for the rover...", config.AMBER
    if reel and reel.busy:
        return "the rover is driving...", config.AMBER
    if conv.busy and conv.say_buf:
        return "answering...", config.GOOD
    if conv.busy:
        return "thinking...", config.GOOD
    if pilot and pilot.wait:
        return window_status(world, pilot)
    last_sol = bool(settings.MISSION_SOLS) and world.day >= settings.MISSION_SOLS
    if world.day_over and world.lost:
        return (f"ROVER LOST on sol {world.day}  ·  cannot reach the pad  ·  ESC to finish",
                config.BAD)
    if world.day_over and last_sol:
        # A replay plays what its tape holds; only a live run can be played on.
        more = "T, then  sols N  for more  ·  "
        if pilot and not pilot.live:
            more = ""
        return f"MISSION OVER after {world.day} sols  ·  {more}ESC to finish", config.BAD
    if world.day_over and world.phase == "day":
        return f"SOL {world.day}: THE DAY IS OVER", config.BAD
    if conv.last:
        secs, tokens_in, tokens_out = conv.last
        return f"{secs}s   {tokens_in} tok in, {tokens_out} out", config.MUTED
    return "ready", config.MUTED


def window_status(world, pilot):
    """The status line while a window waits for the desk."""
    if pilot.wait == "dawn":
        state = f"DAWN OF SOL {world.day}  ·  talk, post orders, or /next"
    elif pilot.wait == "radio":
        state = "ON THE RADIO  ·  answer, or /next  ·  the clock runs"
    elif pilot.wait == "dusk":
        state = f"DUSK OF SOL {world.day}  ·  her report  ·  /next"
    elif settings.MISSION_SOLS and world.day >= settings.MISSION_SOLS:
        state = "MISSION OVER  ·  talk, or /next"
    else:
        state = f"NIGHT OF SOL {world.day}  ·  talk, or /next"
    left = pilot.wait_left()
    if left is None:
        state += "  ·  holding"
    else:
        state += f"  ·  {left:.0f}s"
    if pilot.wait == "radio":
        return state, config.BAD
    return state, config.GOOD


def draw_chat(surf, conv, world, f, line, focused, scroll, show_thinking=True, reel=None,
              overlay=None, memory=False, pilot=None, caret=None):
    """The right-hand pane: the dashboard's cards, and her chat under them."""
    surf.fill(config.VOID)
    top = dashboard.telemetry(surf, world, f, reel, memory)
    if focused or overlay is not None:
        top = dashboard.HEADER
    box = pygame.Rect(8, top, surf.get_width() - 20, surf.get_height() - top - 16)
    transcript = surf.subsurface(box)
    result = _draw_transcript(transcript, conv, world, f, line, focused, scroll,
                              show_thinking, reel, overlay, pilot, caret)
    pygame.draw.rect(surf, config.CHAT_RULE, box, 1, border_radius=8)
    return result


# The settings screen

def draw_settings(surf, f, items, picked, prefs, editing, notice, models, replaying,
                  caret=None):
    """Every registry setting over the whole window, grouped by when a change lands."""
    surf.fill(config.CHAT_BG)
    width, height = surf.get_size()
    x = 40
    surf.blit(f.big.render("SETTINGS", True, config.INK), (x, 20))
    if replaying:
        sub = "replay: the kept run's settings are in force"
    else:
        sub = f"yours are saved in {registry.USER_FILE.name}, which git ignores"
    surf.blit(f.hud.render(sub, True, config.MUTED), (x, 48))

    lines = _settings_lines(items, prefs, replaying)
    line_h = 20
    top = 80
    foot = 110
    rows = (height - top - foot) // line_h
    # Scroll so the chosen row sits in the middle.
    at = 0
    for n, (text, colour, i) in enumerate(lines):
        if i == picked:
            at = n
            break
    first = max(0, min(at - rows // 2, len(lines) - rows))
    for n, (text, colour, i) in enumerate(lines[first:first + rows]):
        y = top + n * line_h
        if i == picked:
            pygame.draw.rect(surf, config.FAINT, (x - 8, y - 2, width - 2 * x + 16, line_h))
            if editing is not None:
                prompt = f"{text.split()[0]:<16} > "
                cols = (width - 2 * x) // f.hud.size("M")[0] - len(prompt) - 1
                if caret is None:
                    caret = len(editing)
                _typed(surf, f.hud, prompt, editing, caret, (x, y), cols, colour)
                continue
        surf.blit(f.hud.render(text, True, colour), (x, y))

    about = _setting_about(items[picked], models)
    y = height - foot + 10
    pygame.draw.line(surf, config.FAINT, (x, y - 8), (width - x, y - 8))
    for piece in textwrap.wrap(about, max(40, (width - 2 * x) // f.hud.size("M")[0]))[:2]:
        surf.blit(f.hud.render(piece, True, config.INK), (x, y))
        y += 20
    if notice:
        surf.blit(f.hud.render(notice, True, config.AMBER), (x, y))
    if editing is not None:
        keys = "ENTER save    ESC cancel"
    else:
        keys = ("UP/DOWN choose    LEFT/RIGHT change    ENTER type a value or load a preset"
                "    R default    O or ESC close")
    surf.blit(f.tiny.render(keys, True, config.MUTED), (x, height - 24))


def _settings_lines(items, prefs, replaying):
    """The settings screen's lines, as (text, colour, item index or None for a heading)."""
    lines = []
    tier = None
    for i, (kind, item) in enumerate(items):
        if kind == "preset":
            lines.append((f"load preset: {item}", config.AMBER, i))
            continue
        if item.tier != tier:
            tier = item.tier
            lines.append(("", config.MUTED, None))
            lines.append((registry.TIER_NAMES[tier].upper(), config.MUTED, None))
        shown = prefs.shown(item)
        text = f"{item.name:<16} {registry.show(shown)}"
        if item.tier == "sol" and item.name in prefs.pending:
            text += f"    (now {registry.show(item.get())})"
        elif item.tier == "relaunch" and shown != item.get():
            text += f"    (now {registry.show(item.get())})"
        if shown != item.default:
            text += f"    default {registry.show(item.default)}"
        if replaying and item.tier != "now":
            lines.append((text, config.MUTED, i))  # locked on a replay
        else:
            lines.append((text, config.INK, i))
    return lines


def _setting_about(row, models):
    """The line under the settings list, about the chosen row."""
    kind, item = row
    if kind == "preset":
        parts = []
        for name, value in registry.PRESETS[item].items():
            parts.append(f"{name} {registry.show(value)}")
        return ", ".join(parts)
    about = f"{item.desc}.  {registry.TIER_NAMES[item.tier]}."
    if item.kind in ("int", "float"):
        about += f"  {registry.show(item.lo)} to {registry.show(item.hi)}."
    elif item.choices:
        about += "  " + " / ".join(registry.show(c) for c in item.choices) + "."
    if item.name == "MODEL" and models is None:
        about += "  Ollama did not answer, so no list; ENTER types a tag."
    return about
