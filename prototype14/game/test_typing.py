"""Typing a line: the caret moves, and keys act where it is, not only at the end.

    .venv/bin/python game/test_typing.py
"""

import sys

import pygame

from main import edit


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'}  {name}{'   ' + detail if detail else ''}")
    return bool(cond)


def key(k, char=""):
    return pygame.event.Event(pygame.KEYDOWN, key=k, unicode=char)


def typed(*keys, text="", caret=None):
    caret = len(text) if caret is None else caret
    for e in keys:
        text, caret = edit(text, caret, e)
    return text, caret


def test_letters_go_in_at_the_caret():
    print("letters")
    return all([
        check("typing at the end appends", typed(key(pygame.K_a, "a"), text="goto") ==
              ("gotoa", 5)),
        check("left, then a letter, goes in before the last one",
              typed(key(pygame.K_LEFT), key(pygame.K_x, "x"), text="goto") == ("gotxo", 4)),
        check("home, then a letter, goes in first",
              typed(key(pygame.K_HOME), key(pygame.K_x, "x"), text="goto") == ("xgoto", 1)),
    ])


def test_backspace_and_delete_work_at_the_caret():
    print("deleting")
    return all([
        check("backspace takes the character before the caret",
              typed(key(pygame.K_BACKSPACE), text="goto 3 4", caret=6) == ("goto  4", 5)),
        check("delete takes the one after it",
              typed(key(pygame.K_DELETE), text="goto 3 4", caret=5) == ("goto  4", 5)),
        check("backspace at the start does nothing",
              typed(key(pygame.K_BACKSPACE), text="goto", caret=0) == ("goto", 0)),
        check("delete at the end does nothing",
              typed(key(pygame.K_DELETE), text="goto") == ("goto", 4)),
        check("held backspace, as repeated presses, keeps deleting",
              typed(*[key(pygame.K_BACKSPACE)] * 3, text="goto") == ("g", 1)),
    ])


def test_the_caret_stays_on_the_line():
    print("caret")
    return all([
        check("left stops at the start", typed(*[key(pygame.K_LEFT)] * 9, text="go") ==
              ("go", 0)),
        check("right stops at the end", typed(key(pygame.K_RIGHT), text="go") == ("go", 2)),
        check("end goes to the end", typed(key(pygame.K_END), text="goto", caret=1) ==
              ("goto", 4)),
        check("a key that types nothing changes nothing",
              typed(key(pygame.K_F1), text="goto", caret=2) == ("goto", 2)),
    ])


if __name__ == "__main__":
    results = [test_letters_go_in_at_the_caret(), test_backspace_and_delete_work_at_the_caret(),
               test_the_caret_stays_on_the_line()]
    print(f"\n{sum(results)}/{len(results)} groups passed")
    sys.exit(0 if all(results) else 1)
