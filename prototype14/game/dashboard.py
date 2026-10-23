"""Mission control's panels: the header, the cards, the scratchpad and the buttons.
It reads the game's state and never changes it. A button click becomes its key."""
import textwrap

import pygame

import config
import settings

HEADER = 64
# The rover pause's hint. Level 3 changes it, since there the rover says when it has stopped.
ROVER_HINT = 'SPACE once the rover has stopped'


def text(surf, font, value, pos, color=None, width=None):
    value = str(value)
    if width is not None and font.size(value)[0] > width:
        while value and font.size(value + "...")[0] > width:
            value = value[:-1]
        value += "..."
    surf.blit(font.render(value, True, color or config.INK), pos)


def key_lines(font, hint, width):
    """A hint like `TAB her chat   T terminal` as lines that fit `width`, broken between keys."""
    lines = [""]
    for group in hint.split("   "):
        group = group.strip()
        if not group:
            continue
        joined = (lines[-1] + "   " + group).strip()
        if lines[-1] and font.size(joined)[0] > width:
            lines.append(group)
        else:
            lines[-1] = joined
    return lines


def card(surf, rect, title, f, accent=config.CYAN, badge=None):
    pygame.draw.rect(surf, config.PANEL, rect, border_radius=8)
    pygame.draw.rect(surf, config.BORDER, rect, 1, border_radius=8)
    pygame.draw.rect(surf, accent, (rect.x + 13, rect.y + 14, 3, 13), border_radius=1)
    text(surf, f.chat_head, title, (rect.x + 25, rect.y + 14), accent)
    if badge and f.chat_head.size(title)[0] + f.tiny.size(badge)[0] + 60 < rect.w:
        label = f.tiny.render(badge, True, config.MUTED)
        surf.blit(label, (rect.right - label.get_width() - 14, rect.y + 15))


def bar(surf, rect, amount, color=config.CYAN):
    pygame.draw.rect(surf, (47, 53, 58), rect, border_radius=4)
    fill = rect.copy()
    fill.width = round(rect.width * max(0, min(1, amount)))
    if fill.width:
        pygame.draw.rect(surf, color, fill, border_radius=4)


def header(surf, world, f):
    pygame.draw.rect(surf, (21, 24, 28), (0, 0, surf.get_width(), HEADER - 8))
    pygame.draw.line(surf, config.BORDER, (15, HEADER - 8), (surf.get_width(), HEADER - 8))
    # The logo: three shards of an A.
    x, y = 30, 28
    pygame.draw.polygon(surf, config.AMBER, [(x, y - 15), (x - 15, y + 12), (x - 5, y + 8), (x, y - 2)])
    pygame.draw.polygon(surf, config.AMBER, [(x + 4, y - 13), (x + 17, y + 12), (x + 7, y + 8), (x + 4, y)])
    pygame.draw.polygon(surf, config.AMBER, [(x + 2, y + 4), (x - 5, y + 15), (x + 9, y + 15)])
    text(surf, f.brand, 'A N G A R A K A', (58, 10), config.AMBER)
    text(surf, f.tiny, 'MISSION CONTROL  /  REFLEX ARC', (60, 38), config.MUTED)


def rover(surf, cx, cy, size=None):
    """The rover, centred on (cx, cy): six wheels, a body and an antenna."""
    if size is None:
        size = config.TILE
    unit = max(2, size // 6)
    pygame.draw.circle(surf, (53, 73, 77), (cx, cy), unit * 4, 1)
    for dx in (-2, 2):
        for dy in (-2, 0, 2):
            wheel = pygame.Rect(cx + dx * unit - 2, cy + dy * unit - 2, 4, 4)
            pygame.draw.rect(surf, (17, 20, 23), wheel.inflate(2, 2), border_radius=2)
            pygame.draw.rect(surf, config.INK, wheel, border_radius=1)
    body = pygame.Rect(cx - unit, cy - unit * 2, unit * 2 + 1, unit * 4 + 1)
    pygame.draw.rect(surf, config.INK, body, border_radius=2)
    pygame.draw.rect(surf, config.CYAN, body.inflate(-2, -4), border_radius=1)
    pygame.draw.line(surf, config.INK, (cx + unit, cy - unit), (cx + unit * 2, cy - unit * 4))
    pygame.draw.circle(surf, config.CYAN, (cx + unit * 2, cy - unit * 4), 2)


def map_label(surf, f, view, ox, oy, tile, cell, value, color, below=False):
    """A boxed label above (or below) a cell, joined to it by a line."""
    center = (ox + cell[0] * tile + tile // 2, oy + cell[1] * tile + tile // 2)
    rendered = f.tiny.render(value, True, color)
    box = rendered.get_rect().inflate(12, 8)
    box.midbottom = (center[0], center[1] - max(16, tile))
    if below:
        box.midtop = (center[0], center[1] + max(16, tile))
    box.clamp_ip(view.inflate(-8, -8))
    pygame.draw.line(surf, color, center, box.center, 1)
    pygame.draw.rect(surf, config.PANEL, box, border_radius=4)
    pygame.draw.rect(surf, color, box, 1, border_radius=4)
    surf.blit(rendered, (box.x + 6, box.y + 4))


def map_telemetry(surf, world, f, view, ox, oy, tile, reel=None):
    """Labels on the map for the rover's cell and its drive's target (MAP_LABELS)."""
    pos = world.pos
    if reel:
        pos = reel.where(world.pos)
    if reel and reel.destination is not None:
        target = reel.destination
        rect = pygame.Rect(ox + target[0] * tile, oy + target[1] * tile, tile, tile)
        pygame.draw.rect(surf, config.PLAN, rect.inflate(4, 4), 2)
        value = f'{reel.destination_status} ({target[0]}, {target[1]})'
        map_label(surf, f, view, ox, oy, tile, target, value, config.PLAN, True)
    map_label(surf, f, view, ox, oy, tile, pos, f'BOT ({pos[0]}, {pos[1]})', config.CYAN)


def map_overlay(surf, world, f, view, ox, oy, reel):
    old = surf.get_clip()
    surf.set_clip(view)
    for cell, obj in world.here.objectives.items():
        if not world.here.visible(*cell) or (reel and reel.veiled(cell)):
            continue
        x = ox + cell[0] * config.TILE
        y = oy + cell[1] * config.TILE
        label = f'{obj.glyph} / {obj.priority.upper()}'
        text(surf, f.tiny, label, (x + config.TILE + 3, y), config.AMBER)
    text(surf, f.tiny, 'JEZERO / SURFACE TELEMETRY', (view.left + 12, view.bottom - 22),
         config.MUTED)
    if settings.MAP_LABELS:
        map_telemetry(surf, world, f, view, ox, oy, config.TILE, reel)
    surf.set_clip(old)
    pygame.draw.rect(surf, config.BORDER, view.inflate(2, 2), 1, border_radius=6)


def controls_width(width):
    """The bottom strip's left part, for the buttons and the keys. 312 fits the longer line of keys."""
    return min(380, max(312, (width - 54) // 2))


def buttons(size):
    """The three buttons, at the bottom strip's top left."""
    width, height = size
    y = height - config.HUD_H + 14
    button_w = (controls_width(width) - 16) // 3
    out = []
    labels = (('M  MAP', pygame.K_m), ('T  TERMINAL', pygame.K_t), ('O  SETTINGS', pygame.K_o))
    for i, (label, key) in enumerate(labels):
        out.append((pygame.Rect(27 + i * (button_w + 8), y, button_w, 28), label, key))
    return out


def bottom(surf, world, f, reel):
    """The strip under the arena: buttons and keys on the left, the world's last messages on the right."""
    rect = pygame.Rect(15, surf.get_height() - config.HUD_H + 4, surf.get_width() - 30,
                       config.HUD_H - 10)
    pygame.draw.rect(surf, config.PANEL, rect, border_radius=8)
    pygame.draw.rect(surf, config.BORDER, rect, 1, border_radius=8)
    for button, label, key in buttons(surf.get_size()):
        hover = pygame.display.get_init() and button.collidepoint(pygame.mouse.get_pos())
        if hover:
            pygame.draw.rect(surf, (48, 62, 64), button, border_radius=5)
            pygame.draw.rect(surf, config.AMBER, button, 1, border_radius=5)
            rendered = f.chat_head.render(label, True, config.AMBER)
        else:
            pygame.draw.rect(surf, (33, 38, 43), button, border_radius=5)
            pygame.draw.rect(surf, config.BORDER, button, 1, border_radius=5)
            rendered = f.chat_head.render(label, True, config.INK)
        surf.blit(rendered, rendered.get_rect(center=button.center))
    left = controls_width(surf.get_width())
    text(surf, f.tiny, 'WASD drive   X mark   TAB chat   ESC quit', (28, rect.y + 48),
         config.MUTED, left)
    if world.awaiting_rover is not None:
        hint = ROVER_HINT
    elif reel and reel.busy:
        hint = 'SPACE skip animation'
    else:
        hint = 'Q end day   C comms   H reasoning   P memory'
    text(surf, f.tiny, hint, (28, rect.y + 65), config.CYAN, left)
    x = 27 + left + 20
    clock = f'ELAPSED {world.elapsed:.0f}s   {settings.ANIM_SPEED:g}x ANIMATION'
    text(surf, f.tiny, clock, (rect.right - 12 - f.tiny.size(clock)[0], rect.y + 10), config.MUTED)
    # The world's last three messages, newest on top and brightest.
    for i, (msg, tone) in enumerate(reversed(world.log[-3:])):
        col = {"good": config.GOOD, "bad": config.BAD}.get(tone, config.INK)
        shade = tuple(min(255, int(v * (1 - i * 0.3))) for v in col)
        text(surf, f.hud, msg, (x, rect.y + 28 + i * 18), shade, rect.right - x - 12)


def top_bar(surf, world, f):
    """The pane's top strip: comms on the left, the sol and its phase on the right."""
    width = surf.get_width()
    pygame.draw.rect(surf, (21, 24, 28), (0, 0, width, HEADER - 8))
    pygame.draw.line(surf, config.BORDER, (0, HEADER - 8), (width - 15, HEADER - 8))
    if settings.COMMS:
        link = 'COMMS ON'
        color = config.GOOD
    else:
        link = 'COMMS OFF'
        color = config.MUTED
    pygame.draw.circle(surf, color, (22, 27), 4)
    text(surf, f.chat_head, link, (34, 20), color)
    label = f'SOL {world.day:02d} / {world.phase.upper()}'
    text(surf, f.chat_head, label, (width - f.chat_head.size(label)[0] - 20, 20), config.AMBER)


def status_card(surf, rect, world, f, reel):
    """ROVER STATUS: battery and survey bars, time left, and position, in three columns."""
    card(surf, rect, 'ROVER STATUS', f)
    gap = rect.w // 3
    left = rect.x + 16
    top = rect.y
    seen = 0
    for cell in world.here.seen:
        if not reel or not reel.veiled(cell):
            seen += 1
    coverage = seen / (world.here.w * world.here.h)
    battery = world.battery / settings.BATTERY
    text(surf, f.tiny, 'BATTERY', (left, top + 39), config.MUTED)
    text(surf, f.chat_head, f'{battery:.0%}', (left + gap - 54, top + 39), config.CYAN)
    if world.battery > settings.BATTERY * .2:
        bar(surf, pygame.Rect(left, top + 58, gap - 28, 6), battery, config.GOOD)
    else:
        bar(surf, pygame.Rect(left, top + 58, gap - 28, 6), battery, config.BAD)
    text(surf, f.tiny, 'SURVEYED', (left, top + 75), config.MUTED)
    text(surf, f.chat_head, f'{coverage:.0%}', (left + gap - 54, top + 75), config.CYAN)
    bar(surf, pygame.Rect(left, top + 94, gap - 28, 6), coverage)
    for i in (1, 2):
        pygame.draw.line(surf, config.BORDER, (rect.x + i * gap, top + 39),
                         (rect.x + i * gap, top + 99))

    mins, secs = divmod(max(0, int(world.time_left)), 60)
    # While a drive is drawn the world is already at its end, so show both positions.
    if reel and reel.at and reel.at != world.pos:
        where = f'({reel.at[0]}, {reel.at[1]}) -> ({world.pos[0]}, {world.pos[1]})'
    else:
        where = f'({world.pos[0]}, {world.pos[1]})'
    if world.stranded:
        state = 'STRANDED'
    elif world.lost:
        state = 'ROVER LOST'
    else:
        state = 'SURFACE ROVER'
    columns = ((1, 'SOL REMAINING', f'{mins:02d}:{secs:02d}', world.phase.upper()),
               (2, 'POSITION', where, state))
    for i, heading, value, sub in columns:
        x = rect.x + i * gap + 14
        text(surf, f.tiny, heading, (x, top + 39), config.MUTED, gap - 20)
        text(surf, f.hud, value, (x, top + 57), config.INK, gap - 20)
        text(surf, f.tiny, sub, (x, top + 84), config.GOOD, gap - 20)


def telemetry(surf, world, f, reel, memory=False):
    """The pane's cards above the chat: the top bar, the rover's status and the scratchpad.
    Returns where the chat may start."""
    width, height = surf.get_size()
    top_bar(surf, world, f)
    status_card(surf, pygame.Rect(8, HEADER, width - 20, 113), world, f, reel)
    # On a short screen, leave room for the chat below.
    if height < 800:
        pad_h = 104
    else:
        pad_h = 176
    top = HEADER + 123
    scratchpad(surf, pygame.Rect(8, top, width - 20, pad_h), world, f, memory)
    return top + pad_h + 10


# Left by the last drawing for main.py: the scratchpad's area (for the wheel) and its switch (for a click).
pad_rect = pygame.Rect(0, 0, 0, 0)
pad_switch = pygame.Rect(0, 0, 0, 0)
pad_scroll = 0
pad_memory = False  # the view drawn last, so a flip starts at the top


def list_rows(world):
    """Today's list: the objectives, the sites she has found, and her own items."""
    rows = []
    for o in world.here.objectives.values():
        rows.append((f'Objective {o.glyph} / {o.priority} / ({o.cell[0]}, {o.cell[1]})', 'open'))
    for i in world.here.interests.values():
        if i.found:
            rows.append((f'Examine site ({i.cell[0]}, {i.cell[1]})', 'struck' if i.done else 'open'))
    for item, struck in world.notes.todos:
        rows.append((item, 'struck' if struck else 'open'))
    if not rows:
        rows.append(("nothing on today's list", 'none'))
    return rows


def memory_rows(world, cols):
    """Her memory, then the board, wrapped to `cols`."""
    rows = []
    for name, value in world.notes.memory.items():
        for line in f'{name}: {value}'.splitlines():
            for piece in textwrap.wrap(line, cols) or ['']:
                rows.append((piece, 'text'))
    if not world.notes.memory:
        rows.append(('nothing in her memory yet', 'none'))
    rows.append(('STANDING ORDERS', 'head'))
    for i, order in enumerate(world.notes.orders, 1):
        for piece in textwrap.wrap(f'{i}. {order}', cols):
            rows.append((piece, 'text'))
    if not world.notes.orders:
        rows.append(('none posted', 'none'))
    return rows


def switch(surf, rect, f, memory):
    """The arrow at the card's top right: on to her memory, or back to the list."""
    label = f.chat_head.render('LIST' if memory else 'MEMORY', True, config.CYAN)
    box = pygame.Rect(0, 0, label.get_width() + 26, 22)
    box.topright = (rect.right - 12, rect.y + 9)
    pygame.draw.rect(surf, config.PANEL, box, border_radius=4)
    pygame.draw.rect(surf, config.BORDER, box, 1, border_radius=4)
    cy = box.centery
    if memory:
        tip = box.x + 8
        pygame.draw.polygon(surf, config.CYAN, [(tip, cy), (tip + 6, cy - 5), (tip + 6, cy + 5)])
        surf.blit(label, (box.x + 18, cy - label.get_height() // 2))
    else:
        tip = box.right - 8
        pygame.draw.polygon(surf, config.CYAN, [(tip, cy), (tip - 6, cy - 5), (tip - 6, cy + 5)])
        surf.blit(label, (box.x + 8, cy - label.get_height() // 2))
    return box


def scratchpad(surf, rect, world, f, memory):
    """One card, two views: today's list, or her memory and the board. P or the switch flips them."""
    global pad_rect, pad_switch, pad_scroll, pad_memory
    card(surf, rect, 'MEMORY AND ORDERS' if memory else 'SCRATCHPAD', f, config.AMBER)
    pad_rect = rect
    pad_switch = switch(surf, rect, f, memory)
    if memory != pad_memory:
        pad_scroll = 0
        pad_memory = memory
    if memory:
        rows = memory_rows(world, max(10, (rect.w - 40) // f.chat.size('M')[0]))
    else:
        rows = list_rows(world)
    fit = max(1, (rect.h - 43) // 23)
    pad_scroll = max(0, min(pad_scroll, len(rows) - fit))
    x = rect.x
    for i, (label, kind) in enumerate(rows[pad_scroll:pad_scroll + fit]):
        yy = rect.y + 43 + i * 23
        if kind == 'head':
            text(surf, f.tiny, label, (x + 19, yy), config.MUTED, rect.w - 35)
        elif kind == 'none':
            text(surf, f.chat, label, (x + 19, yy - 2), config.MUTED, rect.w - 35)
        elif kind == 'text':
            text(surf, f.chat, label, (x + 19, yy - 2), config.INK, rect.w - 35)
        else:
            checked = kind == 'struck'
            pygame.draw.circle(surf, config.GOOD if checked else config.MUTED, (x + 23, yy + 5), 6, 1)
            if checked:
                pygame.draw.lines(surf, config.GOOD, False,
                                  [(x + 20, yy + 5), (x + 22, yy + 7), (x + 26, yy + 2)], 2)
            text(surf, f.chat, label, (x + 38, yy - 2), config.GOOD if checked else config.INK,
                 rect.w - 55)
    below = len(rows) - fit - pad_scroll
    if below > 0:
        text(surf, f.tiny, f'+{below} more  /  the wheel scrolls',
             (x + 19, rect.bottom - 16), config.MUTED, rect.w - 35)


def pad_event(event, offset):
    """The wheel over the scratchpad scrolls it. Returns True when it did."""
    global pad_scroll
    if event.type != pygame.MOUSEWHEEL:
        return False
    mx, my = pygame.mouse.get_pos()
    if not pad_rect.collidepoint(mx - offset, my):
        return False
    pad_scroll = max(0, pad_scroll - event.y)
    return True


def click(pos, game_size, pane_size):
    """The key a mouse click stands for, or None."""
    for rect, label, key in buttons(game_size):
        if rect.collidepoint(pos):
            return key
    # The scratchpad's switch is P. The pane sits right of the arena, so its rects move.
    if pad_switch.move(game_size[0], 0).collidepoint(pos):
        return pygame.K_p
    # A click on the chat's input line is TAB.
    if pos[0] >= game_size[0] + 8 and pos[1] >= pane_size[1] - 82:
        return pygame.K_TAB
    return None
