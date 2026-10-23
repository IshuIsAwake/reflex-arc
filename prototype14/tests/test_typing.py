"""Typing a line: the caret moves, and keys act where it is, not only at the end.

"""


import pygame

from main import edit


def key(k, char=""):
    return pygame.event.Event(pygame.KEYDOWN, key=k, unicode=char)


def typed(*keys, text="", caret=None):
    caret = len(text) if caret is None else caret
    for e in keys:
        text, caret = edit(text, caret, e)
    return text, caret


def test_letters_go_in_at_the_caret():
    assert typed(key(pygame.K_a, "a"), text="goto") == ("gotoa", 5)
    assert typed(key(pygame.K_LEFT), key(pygame.K_x, "x"), text="goto") == ("gotxo", 4)
    assert typed(key(pygame.K_HOME), key(pygame.K_x, "x"), text="goto") == ("xgoto", 1)


def test_backspace_and_delete_work_at_the_caret():
    assert typed(key(pygame.K_BACKSPACE), text="goto 3 4", caret=6) == ("goto  4", 5)
    assert typed(key(pygame.K_DELETE), text="goto 3 4", caret=5) == ("goto  4", 5)
    assert typed(key(pygame.K_BACKSPACE), text="goto", caret=0) == ("goto", 0)
    assert typed(key(pygame.K_DELETE), text="goto") == ("goto", 4)
    assert typed(*[key(pygame.K_BACKSPACE)] * 3, text="goto") == ("g", 1)


def test_the_caret_stays_on_the_line():
    assert typed(*[key(pygame.K_LEFT)] * 9, text="go") == ("go", 0)
    assert typed(key(pygame.K_RIGHT), text="go") == ("go", 2)
    assert typed(key(pygame.K_END), text="goto", caret=1) == ("goto", 4)
    assert typed(key(pygame.K_F1), text="goto", caret=2) == ("goto", 2)
