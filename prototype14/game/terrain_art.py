"""Rock shapes and dust storms, for the screen only.

Nothing here touches the world or the simulation's random numbers. The rocks are drawn
from the cells the rover has seen, so an outline never gives away a rock it hasn't.
"""
from collections import OrderedDict
from functools import lru_cache
import math
import random
import pygame

import config as C

SEED = 1224


def _noise(w, h, step, rnd, lo, hi):
    """Smooth random grey: a coarse grid of random values, stretched up to w x h."""
    nx, ny = max(2, w // step + 2), max(2, h // step + 2)
    small = pygame.Surface((nx, ny), 0, 32)
    for y in range(ny):
        for x in range(nx):
            v = rnd.randint(lo, hi)
            small.set_at((x, y), (v, v, v))
    return pygame.transform.smoothscale(small, (w, h))


# The arena's tile and the map's cell are both kept, and a third for a resize.
_cache = OrderedDict()


def rocks(cols, rows, T, cells):
    """(lit, dim): the rock `cells` as rounded shapes, one picture of the whole arena.

    The cells are stretched up to pixels with smoothing, which rounds every outer
    corner, and a little noise roughens the edge. Cut at half brightness, that is the
    shape. The noise is the same every time, so a newly seen rock leaves the rest as
    they were. `render` draws a rock cell's square from this and nothing else, so no
    part of a rock ever lands on the ground beside it.
    """
    key = (cols, rows, T, cells)
    if key not in _cache:
        W, H = cols * T, rows * T
        grid = pygame.Surface((cols, rows), 0, 32)
        grid.fill((0, 0, 0))
        for cell in cells:
            grid.set_at(cell, (255, 255, 255))
        soft = pygame.transform.smoothscale(grid, (W, H))
        soft.blit(_noise(W, H, max(3, T // 3), random.Random(SEED), 0, 84), (0, 0),
                  special_flags=pygame.BLEND_RGB_ADD)
        soft.fill((42, 42, 42), special_flags=pygame.BLEND_RGB_SUB)
        shape = pygame.mask.from_threshold(soft, (255, 255, 255), (127, 127, 127, 255))
        _cache[key] = (shape.to_surface(setcolor=(*C.ROCK, 255), unsetcolor=(0, 0, 0, 0)),
                       shape.to_surface(setcolor=(*C.ROCK_DIM, 255),
                                        unsetcolor=(0, 0, 0, 0)))
        if len(_cache) > 3:
            _cache.popitem(last=False)
    _cache.move_to_end(key)
    return _cache[key]


@lru_cache(maxsize=16)
def cloud(size):
    surf=pygame.Surface((size,size),pygame.SRCALPHA)
    for y in range(size):
        for x in range(size):
            nx=(x-size/2)/(size/2)
            ny=(y-size/2)/(size/2)
            r=nx*nx+ny*ny
            alpha=int(22*max(0,1-r)**2)
            surf.set_at((x,y),(202,145,82,alpha))
    return surf


def storm(surf,cells,ox,oy,size,time=None):
    if not cells:
        return
    t=pygame.time.get_ticks()/1000 if time is None else time
    puff=cloud(max(12,size*4))
    # Soft swirling dust travels across the real storm footprint. Ground remains
    # visible; only the real storm cells emit dust.
    for x,y in sorted(cells):
        cx,cy=ox+(x+.5)*size,oy+(y+.5)*size
        for layer in range(3):
            phase=x*2.1+y*1.7+layer*2.4
            dx=math.sin(t*.8+phase)*size*.45
            dy=math.cos(t*.55+phase)*size*.28
            surf.blit(puff,(round(cx+dx-puff.get_width()/2),round(cy+dy-puff.get_height()/2)))
        for j in range(3):
            drift=(t*.55+j*.31+x*.17+y*.23)%1
            xx=cx+(drift-.5)*size
            yy=cy+math.sin(drift*4+j+x)*size*.35
            pygame.draw.aaline(surf,(158,111,67),(xx,yy),(xx+max(2,size*.15),yy-1))
