r"""Does the window fit on the screen.

    .venv\Scripts\python.exe game\test_render.py

The shipped 17px tile and 1000px pane want an 1880x990 window, and a 1536x864 laptop
is a normal laptop. When it does not fit, the pane hangs off the right edge and the HUD
goes under the taskbar -- the game is running perfectly and looks like it never
started, which is a fault worth a test of its own.

No display is opened: `get_desktop_sizes` is swapped for a stub, so this runs anywhere
`render` imports.
"""

import config as C
import pygame
import render
import settings as S

# Clear skies unless a suite asks otherwise. The weather is real and shipped on,
# but it is a scenario, not terrain -- letting one drift across an arena would make
# every route assertion here depend on STORM_RADIUS. `test_hazards.py` turns it on.
S.STORM_ON = False


def fitted(w, h):
    """`fit_to_display` against a pretend screen, with the globals put back after.

    On the 50, which is what `main.py` opens and the only size that overflows -- the
    30 at 17px fits a laptop with room to spare, so measuring there would test nothing.

    It mutates `C.TILE` and `S.CHAT_W` by design -- every drawing function reads them
    -- so a test that forgot to restore them would quietly resize the next one.
    """
    real, tile, chat = pygame.display.get_desktop_sizes, C.TILE, S.CHAT_W
    pygame.display.get_desktop_sizes = lambda: [(w, h)]
    C.use("50")
    try:
        # `wide` is the arena the fit was computed against, returned rather than read
        # back afterwards: the globals are restored on the way out, so a test checking
        # the parts add up would otherwise measure the 50's window against the 30's.
        return render.fit_to_display(), C.TILE, S.CHAT_W, C.VIEW_W
    finally:
        pygame.display.get_desktop_sizes = real
        C.TILE, S.CHAT_W = tile, chat
        C.use(C.DEFAULT_ARENA)


def test_a_laptop_screen_gets_a_window_that_fits_on_it():
    """1536x864 is 1920x1080 at the 125% scaling Windows ships on. The measured case."""
    (w, h), tile, chat, wide = fitted(1536, 864)
    assert w <= 1536 and h <= 864, (w, h)
    assert tile < C.TILE, "the tile has to shrink -- nothing else changes the height"
    assert chat >= render.MIN_CHAT
    assert w == wide * tile + render.MARGIN * 2 + chat, "the parts stopped adding up"


def test_a_big_monitor_is_left_exactly_as_shipped():
    """Fitting is a floor, not a policy. Room to spare means the designed numbers."""
    (w, h), tile, chat, wide = fitted(3840, 2160)
    assert (tile, chat) == (C.TILE, S.CHAT_W), "a big screen changed the shipped sizes"
    assert w == wide * tile + render.MARGIN * 2 + chat, (w, wide, tile, chat)


def test_a_tiny_screen_stops_at_the_floors_rather_than_vanishing():
    """Below the minimums there is no good answer, so it stops shrinking and overflows
    visibly. A 3px tile that technically fits is worse than a window you can drag."""
    _, tile, chat, _ = fitted(640, 480)
    assert tile == render.MIN_TILE and chat == render.MIN_CHAT


def test_no_display_leaves_the_shipped_numbers_alone():
    """Headless, `get_desktop_sizes` raises. Guessing a size would be worse than not."""
    real, tile, chat = pygame.display.get_desktop_sizes, C.TILE, S.CHAT_W

    def boom():
        raise pygame.error("no video device")

    pygame.display.get_desktop_sizes = boom
    try:
        assert render.fit_to_display() == render.window_size()
        assert (C.TILE, S.CHAT_W) == (tile, chat)
    finally:
        pygame.display.get_desktop_sizes = real


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("all render checks passed")
