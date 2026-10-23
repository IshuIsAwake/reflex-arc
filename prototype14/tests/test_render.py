"""Drawing: the window's layout, the map, the dashboard, and the fog leak.


No display is opened, so this runs anywhere `render` imports.
"""

import config
import pygame
import dashboard
import render
import settings


def test_the_whole_arena_fits_in_any_window():
    """1536x864 is 1920x1080 at the 125% scaling Windows ships on, and the window opens
    that size less its border. When it did not fit, the HUD went under the taskbar and a
    running game looked like one that never started. 960x640 is the smallest a resize
    allows."""
    tile, chat, size = config.TILE, settings.CHAT_W, render.DISPLAY_SIZE
    config.use("50")
    try:
        for width, height in ((1536 - settings.SCREEN_RESERVE_W, 864 - settings.SCREEN_RESERVE_H),
                              (960, 640), (3780, 2050)):
            game, pane = render.layout(width, height)
            assert game.w + pane.w == width and game.h == height, (width, height)
            assert config.VIEW_W * config.TILE + render.MARGIN * 2 <= game.w, (width, config.TILE)
            assert (config.VIEW_H * config.TILE + config.HUD_H + dashboard.HEADER + render.MARGIN * 2
                    <= height), (height, config.TILE)
            assert pane.w >= 460, "the pane wraps into uselessness below 460"
    finally:
        config.TILE, settings.CHAT_W, render.DISPLAY_SIZE = tile, chat, size
        config.use(config.DEFAULT_ARENA)


def test_a_marked_cell_draws():
    """X puts a mark on the arena; drawing one used to crash the game on the next frame."""
    from world import World
    pygame.font.init()
    w = World()
    w.toggle_mark()
    render.draw_world(pygame.Surface(render.game_size()), w, render.Fonts())


def test_dashboard_modes_draw_without_changing_the_world():
    """Compact/desktop panels, streaming, work and overlays are read-only."""
    import pickle
    import anim
    import chat
    import sight
    from world import World
    pygame.font.init()
    old_tile, old_chat = config.TILE, settings.CHAT_W
    try:
        for tile, pane_width in ((13, 544), (22, 650)):
            config.TILE, settings.CHAT_W = tile, pane_width
            w = World()
            conv = chat.Conversation(w)
            conv.lines = [("gemma", "Surveying the terrain. " * 20)] * 12
            conv.think_buf = "Checking the route and remaining battery."
            reel = anim.Reel(w)
            reel.work = (w.pos, 3, 10)
            before = pickle.dumps(w)
            f = render.Fonts()
            game = pygame.Surface(render.game_size())
            pane = pygame.Surface((settings.CHAT_W, game.get_height()))
            render.draw_world(game, w, f, reel)
            for focused, overlay, pad in ((False, None, True), (True, None, False),
                                          (False, sight.view(w), True)):
                available = render.draw_chat(pane, conv, w, f, "hello", focused, 3,
                                             True, reel, overlay, pad)
                assert available >= 0
            render.draw_map(game, w, f, w.pos)
            render.draw_console(game, w, f, "help", [("terminal output", "good")])
            assert pickle.dumps(w) == before, "drawing changed simulation state"
    finally:
        config.TILE, settings.CHAT_W = old_tile, old_chat


def test_dashboard_buttons_use_existing_controls():
    for rect, _, key in dashboard.buttons(render.game_size()):
        assert dashboard.click(rect.center, render.game_size(), (544, 634)) == key
    assert dashboard.click((-1, -1), render.game_size(), (544, 634)) is None


def test_the_scratchpad_switch_is_p_and_the_wheel_scrolls_it():
    """The MEMORY arrow flips the card like P does, and a long list scrolls."""
    import chat
    from world import World
    pygame.font.init()
    w = World()
    for i in range(12):
        w.notes.add(f"item {i}")
    f = render.Fonts()
    gw = render.game_size()[0]
    pane = pygame.Surface((settings.CHAT_W, render.game_size()[1]))
    render.draw_chat(pane, chat.Conversation(w), w, f, "", False, 0)
    centre = dashboard.pad_switch.move(gw, 0).center
    assert dashboard.click(centre, render.game_size(), pane.get_size()) == pygame.K_p
    wheel = pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-1)
    real = pygame.mouse.get_pos
    pygame.mouse.get_pos = lambda: dashboard.pad_rect.move(gw, 0).center
    try:
        assert dashboard.pad_event(wheel, gw), "the wheel over the card should scroll it"
    finally:
        pygame.mouse.get_pos = real
    render.draw_chat(pane, chat.Conversation(w), w, f, "", False, 0)
    assert dashboard.pad_scroll == 1
    render.draw_chat(pane, chat.Conversation(w), w, f, "", False, 0, memory=True)
    assert dashboard.pad_scroll == 0, "flipping the card starts it at the top"


def test_rock_art_and_weather_leave_simulation_rng_untouched():
    import random
    import terrain_art
    from world import World
    area = World().here
    state = random.getstate()
    cells = frozenset({(2, 2), (2, 3), (3, 2)})
    lit, dim = terrain_art.rocks(area.w, area.h, 12, cells)
    assert lit.get_size() == (area.w * 12, area.h * 12)
    assert terrain_art.rocks(area.w, area.h, 12, cells)[0] is lit
    terrain_art.rocks(area.w, area.h, 18, cells)  # the map's size must not evict the arena's
    assert terrain_art.rocks(area.w, area.h, 12, cells)[0] is lit
    assert lit.get_at((2 * 12 + 6, 2 * 12 + 6)).a == 255, "the middle of a rock is drawn"
    assert lit.get_at((10 * 12 + 6, 10 * 12 + 6)).a == 0, "open ground has no rock on it"
    assert lit.get_at((2 * 12 + 6, 2 * 12 + 6)) != dim.get_at((2 * 12 + 6, 2 * 12 + 6))
    a, b = pygame.Surface((200, 200)), pygame.Surface((200, 200))
    terrain_art.storm(a, cells, 0, 0, 32, time=0)
    terrain_art.storm(b, cells, 0, 0, 32, time=2)
    assert pygame.image.tostring(a, "RGB") != pygame.image.tostring(b, "RGB")
    assert random.getstate() == state, "visual randomness changed the simulation RNG"


def test_an_unseen_rock_changes_nothing_on_screen():
    """The fog leak. A rock in a cell she has not seen must not show in the cell beside
    it, ground or rock, until she has seen it."""
    from world import World
    pygame.font.init()
    w = World()
    a = w.here
    # A cell she can see with unseen ground beside it.
    seen, hidden = next(((x, y), (x + 1, y)) for y in range(a.h) for x in range(a.w - 1)
                        if a.visible(x, y) and not a.visible(x + 1, y)
                        and a.at(x, y) == "." and a.at(x + 1, y) == ".")
    f = render.Fonts()

    def put(cell, ch):
        row = a.rows[cell[1]]
        a.rows[cell[1]] = row[:cell[0]] + ch + row[cell[0] + 1:]

    def picture():
        surf = pygame.Surface(render.game_size())
        render.draw_world(surf, w, f)
        (ox, oy), _ = render.viewport(surf, a, w.pos)
        r = pygame.Rect(ox + seen[0] * config.TILE, oy + seen[1] * config.TILE, config.TILE, config.TILE)
        return pygame.image.tostring(surf.subsurface(r), "RGB")

    for ch in (".", "#"):          # the seen cell as ground, then as a rock
        put(seen, ch)
        put(hidden, ".")
        before = picture()
        put(hidden, "#")
        assert picture() == before, f"an unseen rock showed beside a seen {ch!r}"
    put(seen, ".")
    put(hidden, ".")
