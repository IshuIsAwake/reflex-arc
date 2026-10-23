"""Angaraka mission-control presentation. Reads game state; never changes it.

All clickable controls return existing keyboard actions to main.py.
"""
import textwrap
import pygame
import config as C
import settings as S

HEADER = 64
AMBER = (190, 177, 148)
CYAN = (111, 190, 183)
PANEL = (30, 34, 39)
BORDER = (53, 60, 67)


def text(surf, font, value, pos, color=None, width=None):
    value = str(value)
    if width is not None and font.size(value)[0] > width:
        while value and font.size(value + "...")[0] > width:
            value = value[:-1]
        value += "..."
    surf.blit(font.render(value, True, color or C.INK), pos)


def key_lines(font, hint, width):
    """A hint like `TAB her chat   T terminal` as lines that fit `width`, broken between
    keys and never inside one."""
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


def card(surf, rect, title, f, accent=CYAN, badge=None):
    pygame.draw.rect(surf, PANEL, rect, border_radius=8)
    pygame.draw.rect(surf, BORDER, rect, 1, border_radius=8)
    pygame.draw.rect(surf, accent, (rect.x + 13, rect.y + 14, 3, 13), border_radius=1)
    text(surf, f.chat_head, title, (rect.x + 25, rect.y + 14), accent)
    if badge and f.chat_head.size(title)[0] + f.tiny.size(badge)[0] + 60 < rect.w:
        label = f.tiny.render(badge, True, C.MUTED)
        surf.blit(label, (rect.right - label.get_width() - 14, rect.y + 15))


def bar(surf, rect, amount, color=CYAN):
    pygame.draw.rect(surf, (47, 53, 58), rect, border_radius=4)
    fill = rect.copy()
    fill.width = round(rect.width * max(0, min(1, amount)))
    if fill.width:
        pygame.draw.rect(surf, color, fill, border_radius=4)


def header(surf, w, f):
    pygame.draw.rect(surf, (21, 24, 28), (0, 0, surf.get_width(), HEADER - 8))
    pygame.draw.line(surf, BORDER, (15, HEADER - 8), (surf.get_width(), HEADER - 8))
    x, y = 30, 28
    pygame.draw.polygon(surf, AMBER, [(x, y-15), (x-15, y+12), (x-5, y+8), (x, y-2)])
    pygame.draw.polygon(surf, AMBER, [(x+4, y-13), (x+17, y+12), (x+7, y+8), (x+4, y)])
    pygame.draw.polygon(surf, AMBER, [(x+2,y+4),(x-5,y+15),(x+9,y+15)])
    text(surf, f.brand, 'A N G A R A K A', (58, 10), AMBER)
    text(surf, f.tiny, 'MISSION CONTROL  /  REFLEX ARC', (60, 38), C.MUTED)


def rover(surf, cx, cy, size=None):
    unit = max(2, (C.TILE if size is None else size) // 6)
    pygame.draw.circle(surf, (53, 73, 77), (cx,cy), unit*4, 1)
    for dx in (-2, 2):
        for dy in (-2, 0, 2):
            r = pygame.Rect(cx+dx*unit-2, cy+dy*unit-2, 4, 4)
            pygame.draw.rect(surf, (17,20,23), r.inflate(2,2), border_radius=2)
            pygame.draw.rect(surf, C.INK, r, border_radius=1)
    r = pygame.Rect(cx-unit, cy-unit*2, unit*2+1, unit*4+1)
    pygame.draw.rect(surf, C.INK, r, border_radius=2)
    pygame.draw.rect(surf, CYAN, r.inflate(-2,-4), border_radius=1)
    pygame.draw.line(surf, C.INK, (cx+unit,cy-unit), (cx+unit*2,cy-unit*4))
    pygame.draw.circle(surf, CYAN, (cx+unit*2,cy-unit*4), 2)


def map_telemetry(surf, w, f, view, ox, oy, tile, reel=None):
    """Floating grid coordinates follow the displayed bot and its route target."""
    pos = reel.where(w.pos) if reel else w.pos
    def label(cell, value, color, below=False):
        center = (ox + cell[0]*tile + tile//2, oy + cell[1]*tile + tile//2)
        rendered = f.tiny.render(value, True, color)
        box = rendered.get_rect().inflate(12, 8)
        box.midbottom = (center[0], center[1] - max(16, tile))
        if below:
            box.midtop = (center[0], center[1] + max(16, tile))
        box.clamp_ip(view.inflate(-8, -8))
        pygame.draw.line(surf, color, center, box.center, 1)
        pygame.draw.rect(surf, PANEL, box, border_radius=4)
        pygame.draw.rect(surf, color, box, 1, border_radius=4)
        surf.blit(rendered, (box.x+6, box.y+4))
    if reel and reel.destination is not None:
        target = reel.destination
        rect = pygame.Rect(ox+target[0]*tile, oy+target[1]*tile, tile, tile)
        pygame.draw.rect(surf, C.PLAN, rect.inflate(4, 4), 2)
        label(target, f'{reel.destination_status} ({target[0]}, {target[1]})', C.PLAN, True)
    label(pos, f'BOT ({pos[0]}, {pos[1]})', CYAN)


def map_overlay(surf, w, f, view, ox, oy, reel):
    # Labels go only on objects that are visible.
    old = surf.get_clip()
    surf.set_clip(view)
    for cell, obj in w.here.objectives.items():
        if not w.here.visible(*cell) or (reel and reel.veiled(cell)):
            continue
        x, y = ox+cell[0]*C.TILE, oy+cell[1]*C.TILE
        text(surf, f.tiny, f'{obj.glyph} / {obj.priority.upper()}', (x+C.TILE+3,y), AMBER)
    text(surf, f.tiny, 'JEZERO / SURFACE TELEMETRY', (view.left+12,view.bottom-22), C.MUTED)
    if S.MAP_LABELS:
        map_telemetry(surf, w, f, view, ox, oy, C.TILE, reel)
    surf.set_clip(old)
    pygame.draw.rect(surf, BORDER, view.inflate(2,2), 1, border_radius=6)


def controls_width(width):
    """The bottom strip's left part, for the buttons and the keys. Messages get the rest.
    312 is what the longer line of keys needs, so it never gets cut."""
    return min(380, max(312, (width - 54) // 2))


def buttons(size):
    """The three buttons, at the bottom strip's top left."""
    width, height = size
    y = height-C.HUD_H+14
    bw = (controls_width(width)-16)//3
    return [(pygame.Rect(27+i*(bw+8),y,bw,28), label,key)
            for i,(label,key) in enumerate((('M  MAP',pygame.K_m),
                ('T  TERMINAL',pygame.K_t),('O  SETTINGS',pygame.K_o)))]


def bottom(surf, w, f, reel):
    """The strip under the arena: buttons and keys on the left; the stopwatch, and the
    world's last three messages, on the right."""
    rect = pygame.Rect(15, surf.get_height()-C.HUD_H+4, surf.get_width()-30, C.HUD_H-10)
    pygame.draw.rect(surf, PANEL, rect, border_radius=8)
    pygame.draw.rect(surf, BORDER, rect, 1, border_radius=8)
    for r,label,key in buttons(surf.get_size()):
        hover = pygame.display.get_init() and r.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(surf,(48,62,64) if hover else (33,38,43),r,border_radius=5)
        pygame.draw.rect(surf,AMBER if hover else BORDER,r,1,border_radius=5)
        label_s = f.chat_head.render(label,True,AMBER if hover else C.INK)
        surf.blit(label_s,label_s.get_rect(center=r.center))
    left = controls_width(surf.get_width())
    text(surf, f.tiny, 'WASD drive   X mark   TAB chat   ESC quit', (28, rect.y + 48),
         C.MUTED, left)
    hint = 'SPACE confirm rover stopped' if w.awaiting_rover is not None else (
        'SPACE skip animation' if reel and reel.busy else 'Q end day   C comms   H reasoning   P memory')
    text(surf, f.tiny, hint, (28, rect.y + 65), CYAN, left)
    x = 27 + left + 20
    clock = f'ELAPSED {w.elapsed:.0f}s   {S.ANIM_SPEED:g}x ANIMATION'
    text(surf, f.tiny, clock, (rect.right - 12 - f.tiny.size(clock)[0], rect.y + 10), C.MUTED)
    # The world's last three messages, newest on top and brightest: what the terminal
    # printed, or what X just marked.
    for i, (msg, tone) in enumerate(reversed(w.log[-3:])):
        col = {"good": C.GOOD, "bad": C.BAD}.get(tone, C.INK)
        shade = tuple(min(255, int(v * (1 - i * 0.3))) for v in col)
        text(surf, f.hud, msg, (x, rect.y + 28 + i * 18), shade, rect.right - x - 12)


def telemetry(surf, w, f, reel, memory=False):
    width,height = surf.get_size()
    pygame.draw.rect(surf,(21,24,28),(0,0,width,HEADER-8))
    pygame.draw.line(surf,BORDER,(0,HEADER-8),(width-15,HEADER-8))
    link = 'COMMS ON' if S.COMMS else 'COMMS OFF'
    color = C.GOOD if S.COMMS else C.MUTED
    pygame.draw.circle(surf,color,(22,27),4)
    text(surf,f.chat_head,link,(34,20),color)
    label = f'SOL {w.day:02d} / {w.phase.upper()}'
    text(surf,f.chat_head,label,(width-f.chat_head.size(label)[0]-20,20),AMBER)
    x,wide = 8,width-20
    status = pygame.Rect(x,HEADER,wide,113)
    card(surf,status,'ROVER STATUS',f)
    gap = wide//3
    seen = sum(1 for cell in w.here.seen if not reel or not reel.veiled(cell))
    coverage = seen/(w.here.w*w.here.h)
    left = x+16
    text(surf,f.tiny,'BATTERY',(left,HEADER+39),C.MUTED)
    text(surf,f.chat_head,f'{w.battery / max(1,S.BATTERY):.0%}',(left+gap-54,HEADER+39),CYAN)
    bar(surf,pygame.Rect(left,HEADER+58,gap-28,6),w.battery/max(1,S.BATTERY),C.GOOD if w.battery>S.BATTERY*.2 else C.BAD)
    text(surf,f.tiny,'SURVEYED',(left,HEADER+75),C.MUTED)
    text(surf,f.chat_head,f'{coverage:.0%}',(left+gap-54,HEADER+75),CYAN)
    bar(surf,pygame.Rect(left,HEADER+94,gap-28,6),coverage)
    for i in (1,2):
        pygame.draw.line(surf,BORDER,(x+i*gap,HEADER+39),(x+i*gap,HEADER+99))
    mins,secs=divmod(max(0,int(w.time_left)),60)
    # While a drive is being drawn the world is already at its end, so say both: where
    # the rover is drawn, and where it already is.
    if reel and reel.at and reel.at != w.pos:
        where = f'({reel.at[0]}, {reel.at[1]}) -> ({w.pos[0]}, {w.pos[1]})'
    else:
        where = f'({w.pos[0]}, {w.pos[1]})'
    for i,heading,value,sub in ((1,'SOL REMAINING',f'{mins:02d}:{secs:02d}',w.phase.upper()),
                               (2,'POSITION',where,
                                'STRANDED' if w.stranded else 'ROVER LOST' if w.lost else 'SURFACE ROVER')):
        xx=x+i*gap+14
        text(surf,f.tiny,heading,(xx,HEADER+39),C.MUTED,gap-20)
        text(surf,f.hud,value,(xx,HEADER+57),C.INK,gap-20)
        text(surf,f.tiny,sub,(xx,HEADER+84),C.GOOD,gap-20)
    # At laptop height retain room for the full, scrollable planner below.
    objective_h = 104 if height < 800 else 176
    top = HEADER+123
    scratchpad(surf, pygame.Rect(x, top, wide, objective_h), w, f, memory)
    return top + objective_h + 10


# Left behind by the last drawing, for main.py: where the scratchpad is, for the wheel,
# and where its switch is, for a click.
pad_rect = pygame.Rect(0, 0, 0, 0)
pad_switch = pygame.Rect(0, 0, 0, 0)
pad_scroll = 0
pad_memory = False      # the view drawn last, so a flip starts at the top


def list_rows(w):
    """Today's list: the objectives, the sites she has found, and her own items."""
    rows = [(f'Objective {o.glyph} / {o.priority} / ({o.cell[0]}, {o.cell[1]})', 'open')
            for o in w.here.objectives.values()]
    rows += [(f'Examine site ({o.cell[0]}, {o.cell[1]})', 'struck' if o.done else 'open')
             for o in w.here.interests.values() if o.found]
    rows += [(t, 'struck' if struck else 'open') for t, struck in w.notes.todos]
    return rows or [("nothing on today's list", 'none')]


def memory_rows(w, cols):
    """What lasts past the night: her memory, then the board, wrapped to `cols`."""
    rows = []
    for name, value in w.notes.memory.items():
        for line in f'{name}: {value}'.splitlines():
            rows += [(piece, 'text') for piece in textwrap.wrap(line, cols) or ['']]
    if not w.notes.memory:
        rows.append(('nothing in her memory yet', 'none'))
    rows.append(('STANDING ORDERS', 'head'))
    for i, order in enumerate(w.notes.orders, 1):
        rows += [(piece, 'text') for piece in textwrap.wrap(f'{i}. {order}', cols)]
    if not w.notes.orders:
        rows.append(('none posted', 'none'))
    return rows


def switch(surf, rect, f, memory):
    """The arrow at the card's top right: on to her memory, or back to the list."""
    label = f.chat_head.render('LIST' if memory else 'MEMORY', True, CYAN)
    box = pygame.Rect(0, 0, label.get_width() + 26, 22)
    box.topright = (rect.right - 12, rect.y + 9)
    pygame.draw.rect(surf, PANEL, box, border_radius=4)
    pygame.draw.rect(surf, BORDER, box, 1, border_radius=4)
    cy = box.centery
    if memory:
        tip = box.x + 8
        pygame.draw.polygon(surf, CYAN, [(tip, cy), (tip + 6, cy - 5), (tip + 6, cy + 5)])
        surf.blit(label, (box.x + 18, cy - label.get_height() // 2))
    else:
        tip = box.right - 8
        pygame.draw.polygon(surf, CYAN, [(tip, cy), (tip - 6, cy - 5), (tip - 6, cy + 5)])
        surf.blit(label, (box.x + 8, cy - label.get_height() // 2))
    return box


def scratchpad(surf, rect, w, f, memory):
    """One card, two views: today's list, or her memory and the board. The switch at its
    top right flips them, and so does P. The wheel scrolls whichever is showing."""
    global pad_rect, pad_switch, pad_scroll, pad_memory
    card(surf, rect, 'MEMORY AND ORDERS' if memory else 'SCRATCHPAD', f, AMBER)
    pad_rect, pad_switch = rect, switch(surf, rect, f, memory)
    if memory != pad_memory:
        pad_scroll, pad_memory = 0, memory
    if memory:
        rows = memory_rows(w, max(10, (rect.w - 40) // f.chat.size('M')[0]))
    else:
        rows = list_rows(w)
    fit = max(1, (rect.h - 43) // 23)
    pad_scroll = max(0, min(pad_scroll, len(rows) - fit))
    x = rect.x
    for i, (label, kind) in enumerate(rows[pad_scroll:pad_scroll + fit]):
        yy = rect.y + 43 + i * 23
        if kind == 'head':
            text(surf, f.tiny, label, (x + 19, yy), C.MUTED, rect.w - 35)
        elif kind == 'none':
            text(surf, f.chat, label, (x + 19, yy - 2), C.MUTED, rect.w - 35)
        elif kind == 'text':
            text(surf, f.chat, label, (x + 19, yy - 2), C.INK, rect.w - 35)
        else:
            checked = kind == 'struck'
            pygame.draw.circle(surf, C.GOOD if checked else C.MUTED, (x + 23, yy + 5), 6, 1)
            if checked:
                pygame.draw.lines(surf, C.GOOD, False,
                                  [(x + 20, yy + 5), (x + 22, yy + 7), (x + 26, yy + 2)], 2)
            text(surf, f.chat, label, (x + 38, yy - 2), C.GOOD if checked else C.INK,
                 rect.w - 55)
    below = len(rows) - fit - pad_scroll
    if below > 0:
        text(surf, f.tiny, f'+{below} more  /  the wheel scrolls',
             (x + 19, rect.bottom - 16), C.MUTED, rect.w - 35)


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
    for rect,label,key in buttons(game_size):
        if rect.collidepoint(pos):
            return key
    # The scratchpad's switch is P. The pane sits right of the arena, so its rects move.
    if pad_switch.move(game_size[0], 0).collidepoint(pos):
        return pygame.K_p
    # Clicking the planner's existing input has the same effect as TAB.
    if pos[0] >= game_size[0]+8 and pos[1] >= pane_size[1]-82:
        return pygame.K_TAB
    return None
