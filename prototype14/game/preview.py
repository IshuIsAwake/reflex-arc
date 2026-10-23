"""Draws the README's screenshot, preview.png, with no model and no window.
The map is fully surveyed so the rocks show; a real mission starts in fog."""
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import chat
import config
import render
import settings
from world import World


def main():
    pygame.init()
    settings.STORM_ON = False
    config.use(config.APP_ARENA)
    screen = pygame.Surface((1600, 900))
    game_rect, pane_rect = render.layout(*screen.get_size())
    world = World()
    world.phase = "day"
    world.here.seen.update((x, y) for y in range(world.here.h) for x in range(world.here.w))
    world.toggle_mark((30, 22))
    world.notes.add("survey the C-shaped rock to the north-east")
    world.notes.add("back to the pad before the battery is under 100")
    conv = chat.Conversation(world)
    conv.lines = [("gemma", "Ready to survey Jezero flats. I'll start with the rock "
                            "formation to the north-east.")]
    fonts = render.Fonts()
    render.draw_world(screen.subsurface(game_rect), world, fonts)
    render.draw_chat(screen.subsurface(pane_rect), conv, world, fonts, "", False, 0)
    path = Path(__file__).resolve().parents[1] / "preview.png"
    pygame.image.save(screen, path)
    print(path)
    pygame.quit()


if __name__ == "__main__":
    main()
