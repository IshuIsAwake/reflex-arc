"""Draws the README's screenshot, preview.png, with no model and no window.
The map is fully surveyed so the rocks show; a real mission starts in fog."""
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import chat
import config as C
import render
import settings as S
from world import World


def main():
    pygame.init()
    S.STORM_ON = False
    C.use(C.APP_ARENA)
    screen = pygame.Surface((1600, 900))
    game_rect, pane_rect = render.layout(*screen.get_size())
    w = World()
    w.phase = "day"
    w.here.seen.update((x, y) for y in range(w.here.h) for x in range(w.here.w))
    w.toggle_mark((30, 22))
    w.notes.add("survey the C-shaped rock to the north-east")
    w.notes.add("back to the pad before the battery is under 100")
    conv = chat.Conversation(w)
    conv.lines = [("gemma", "Ready to survey Jezero flats. I'll start with the rock "
                            "formation to the north-east.")]
    fonts = render.Fonts()
    render.draw_world(screen.subsurface(game_rect), w, fonts)
    render.draw_chat(screen.subsurface(pane_rect), conv, w, fonts, "", False, 0)
    path = Path(__file__).resolve().parents[1] / "preview.png"
    pygame.image.save(screen, path)
    print(path)
    pygame.quit()


if __name__ == "__main__":
    main()
