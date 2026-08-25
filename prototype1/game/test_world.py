"""Walks the world and checks it behaves. No pygame needed.

    .venv/bin/python game/test_world.py
"""

import random
from collections import deque

import config as C
import settings as S
from world import SOLID, World

STEP = {"w": (0, -1), "s": (0, 1), "a": (-1, 0), "d": (1, 0)}
NEIGHBOURS = ((0, 1), (0, -1), (1, 0), (-1, 0))


def walk(w, path):
    for ch in path:
        w.move(*STEP[ch])


def pit_cost(area, target, start):
    """Antidotes burned on the cheapest route to a tile. 0-1 BFS: stepping on a pit
    costs one, every other step is free."""
    rows = C.AREAS[area]
    dist, q, best = {start: 0}, deque([start]), None
    while q:
        cur = q.popleft()
        for dx, dy in NEIGHBOURS:
            n = (cur[0] + dx, cur[1] + dy)
            if not (0 <= n[0] < len(rows[0]) and 0 <= n[1] < len(rows)):
                continue
            ch = rows[n[1]][n[0]]
            if ch == target:
                best = dist[cur] if best is None else min(best, dist[cur])
                continue
            if ch in SOLID:
                continue
            cost = dist[cur] + (1 if ch == "^" else 0)
            if cost < dist.get(n, 1 << 30):
                dist[n] = cost
                (q.append if ch == "^" else q.appendleft)(n)
    return best


def flood(rows, start):
    seen, q = {start}, deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in NEIGHBOURS:
            n = (x + dx, y + dy)
            if (0 <= n[0] < len(rows[0]) and 0 <= n[1] < len(rows)
                    and n not in seen and rows[n[1]][n[0]] not in SOLID):
                seen.add(n)
                q.append(n)
    return seen


def test_everything_is_reachable():
    """A sealed room or an unreachable coin bag is invisible until someone
    wastes a day looking for it, so check the maps rather than trusting them."""
    entry = {"plaza": C.PLAZA_SPAWN}
    for (area, cell), (dest, landing) in C.LINKS.items():
        entry.setdefault(dest, landing)
    assert set(entry) == set(C.AREAS), f"no way into {set(C.AREAS) - set(entry)}"

    def adjacent(cells, target):
        return any((target[0] + dx, target[1] + dy) in cells for dx, dy in NEIGHBOURS)

    for name, rows in C.AREAS.items():
        rows = [r.replace("@", ".") for r in rows]
        assert len({len(r) for r in rows}) == 1, f"{name} rows are ragged"
        cells = flood(rows, entry[name])
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch in "BCFSNTL$*D":
                    assert adjacent(cells, (x, y)), f"{name} {ch} at {(x, y)} is unreachable"
                elif ch in "^Evn":
                    assert (x, y) in cells, f"{name} {ch} at {(x, y)} is unreachable"

    # every link points at a real, walkable cell on the far side
    for (area, cell), (dest, landing) in C.LINKS.items():
        assert C.AREAS[area][cell[1]][cell[0]] in "DEvn", f"{area} {cell} is not a gate"
        assert C.AREAS[dest][landing[1]][landing[0]] not in SOLID, f"{dest} {landing} is solid"

    # The vault must cost exactly a full upgraded pouch: three antidotes. One more
    # and it is unreachable; one fewer and the tool_pouch upgrade is pointless.
    vault = pit_cost("savana2", "*", C.LINKS[("savana", (16, 21))][1])
    assert vault == S.POUCH_UPGRADED, f"the vault costs {vault} antidotes"

    # The tribe sits behind a pit maze, but a solved route costs nothing -- it is a
    # thing to map, not a toll. You cannot buy the pouch if reaching it needs one.
    tribe = pit_cost("savana", "T", C.LINKS[("plaza", (20, 13))][1])
    assert tribe == 0, f"reaching the tribe costs {tribe} antidotes"

    tiles = {(n, (x, y)) for n, rows in C.AREAS.items()
             for y, row in enumerate(rows) for x, ch in enumerate(row) if ch in "$*"}
    assert tiles == set(S.BAGS), f"'$' tiles {tiles} do not match settings.BAGS {set(S.BAGS)}"
    lost = {(n, (x, y)) for n, rows in C.AREAS.items()
            for y, row in enumerate(rows) for x, ch in enumerate(row) if ch == "L"}
    assert set(S.LOST_BAG_ITEMS) <= lost, "LOST_BAG_ITEMS points at a cell with no lost bag"


def test_a_full_run():
    random.seed(1)
    w = World()

    # the notice board hands over the Plaza map -- column 3 is the cartpole booth
    # wall, so the way up is column 1
    walk(w, "a" * 9 + "w" * 6 + "d")
    assert w.pos == (2, 8), w.pos
    w.interact()
    assert w.here.has_map
    w.interact()
    assert w.log[-1][0].startswith("ALREADY_DONE"), w.log[-1]

    # pressing E next to nothing is silent
    walk(w, "s" + "d" * 3)
    assert w.pos == (5, 9) and not w.facing(), (w.pos, w.facing())
    quiet = w.log[-1]
    w.interact()
    assert w.log[-1] == quiet, "E next to nothing should say nothing"

    # the north maze holds a coin bag, which vanishes once emptied
    before = w.coins
    w.pos = (18, 1)
    w.interact()
    assert w.coins == before + S.BAGS[("plaza", (19, 1))], (before, w.coins)
    assert w.here.at(19, 1) == ".", "an emptied coin bag should stop being drawn"
    assert not w.facing(), "and stop being interactable"

    # a terminal reads 'discover' until you walk up to it, and interacting with it
    # both names it and plays it
    assert "cartpole" not in w.discovered
    w.pos = (4, 12)
    w.interact()
    assert w.discovered == {"cartpole": "plaza"}, w.discovered
    assert w.played == {"cartpole"}, w.played
    assert "cartpole" in w.cooldown, "playing it starts the cooldown"

    # shop counter at (10,16), reachable from (10,15)
    w.coins = 200
    w.pos = (10, 15)
    assert w.at_counter() == "shop"
    w.buy("savana_key")
    assert "savana_key" in w.items
    w.buy("savana_key")
    assert w.log[-1][0].startswith("NOT_STOCKED"), w.log[-1]

    # the gate opens by interacting and never by walking into it
    w.pos = (19, 13)
    w.move(1, 0)
    assert (w.area, w.pos) == ("plaza", (19, 13)), "a shut gate must not open by walking into it"
    w.interact()
    assert ("plaza", (20, 13)) in w.unlocked, w.log[-1]
    w.move(1, 0)
    assert (w.area, w.pos) == ("savana", (1, 16)), (w.area, w.pos)

    # the Savana lost bag reveals this area and no other
    w.pos = (2, 1)
    w.interact()
    assert w.here.has_map, "the lost bag should hold the Savana map"
    assert not w.areas["savana2"].has_map, "and only this area's map"
    assert w.here.at(1, 1) == ".", "an emptied lost bag should stop being drawn"

    # the south gate drops into Savana 2, which you have no map for
    w.pos = (16, 20)
    w.move(0, 1)
    assert (w.area, w.pos) == ("savana2", (15, 1)), (w.area, w.pos)
    assert not w.here.has_map

    # its lost bag carries the map and a free antidote
    w.pos = (1, 2)
    w.interact()
    assert w.here.has_map and w.antidotes == 1, (w.here.has_map, w.antidotes)

    # an antidote absorbs one pit: no coins lost, no walk home, and it is used up
    coins = w.coins
    w.area, w.pos = "savana", (12, 12)
    w.move(0, 1)
    assert (w.area, w.pos) == ("savana", (12, 13)), "the antidote should leave you standing"
    assert w.coins == coins and w.antidotes == 0

    # without one, the same pit costs coins and sends you home
    w.pos = (12, 12)
    w.move(0, 1)
    assert w.area == "plaza", "a pit should teleport you back to the Plaza"
    assert w.coins == coins - S.TRAP_PENALTY, (w.coins, coins)
    assert w.log[-1][0].startswith("TRAPPED(12, 13)"), w.log[-1]

    # the pouch holds one until the tribe upgrades it, and the tribe only sells
    # from its own counter
    w.coins = 2000
    w.pos = (10, 15)
    assert w.pouch == 1
    w.buy("antidote")
    assert w.antidotes == 1
    w.buy("antidote")
    assert w.log[-1][0].startswith("NOT_STOCKED"), w.log[-1]
    w.buy("tool_pouch")
    assert "tool_pouch" not in w.items, "the shop does not stock the tribe's upgrade"

    w.area, w.pos = "savana", (29, 16)
    assert w.at_counter() == "tribe", w.facing()
    w.buy("tool_pouch")
    assert w.pouch == S.POUCH_UPGRADED and w.antidotes == 1
    w.buy("antidote")
    assert w.antidotes == 1, "the tribe does not stock antidotes either"

    w.area, w.pos = "plaza", (10, 15)
    for _ in range(3):
        w.buy("antidote")
    assert w.antidotes == S.POUCH_UPGRADED, w.antidotes
    assert w.log[-1][0].startswith("NOT_STOCKED"), w.log[-1]

    # three antidotes is exactly enough to open the vault, and nothing is left over
    w.area, w.pos = "savana2", (8, 17)
    coins = w.coins
    for _ in range(3):
        w.move(-1, 0)
    assert (w.area, w.pos) == ("savana2", (5, 17)), (w.area, w.pos)
    assert w.antidotes == 0, "the vault should cost the whole pouch"
    w.interact()
    assert w.coins == coins + S.BAGS[("savana2", (4, 17))], (coins, w.coins)
    assert w.here.at(4, 17) == ".", "the opened vault should stop being drawn"

    # pits are never in the rendered grid, at any fog setting
    for area in w.areas.values():
        assert all(area.at(x, y) == "." for x, y in area.traps), "pits must never be visible"
    assert w.areas["savana2"].traps

    # marks
    w.toggle_mark((5, 5))
    assert (5, 5) in w.here.marks
    w.toggle_mark((5, 5))
    assert (5, 5) not in w.here.marks

    # a terminal you have not walked up to is not listed at all
    assert {g for g, _, _, _ in w.cooldown_lines()} == {"cartpole"}, w.cooldown_lines()

    # a locked one stays out of the list even once discovered
    w.area, w.pos = "plaza", (16, 12)
    w.items.discard("flappy_key")
    w.interact()
    assert w.log[-1][0].startswith("LOCKED(needs: flappy_key)"), w.log[-1]
    assert "flappy" not in {g for g, _, _, _ in w.cooldown_lines()}
    w.items.add("flappy_key")
    assert "flappy" in {g for g, _, _, _ in w.cooldown_lines()}

    return w


def test_the_day_rolls_over():
    w = test_a_full_run()
    w.coins, w.day_start_coins = 130, 100
    assert w.earned_today() == 30

    w.time_left = 0.01
    w.tick(1.0)
    assert w.day_over and w.time_left == 0, "the day should end but not roll over by itself"
    assert w.day == 1, "rolling over is the player's call"

    coins, items = w.coins, set(w.items)
    w.next_day()
    assert w.day == 2 and not w.day_over
    assert w.coins == coins and w.items == items
    assert w.areas["plaza"].has_map and w.areas["savana"].has_map
    assert w.log == [], "yesterday's log is noise once the day is closed"
    assert not w.cooldown and (w.area, w.pos) == ("plaza", C.PLAZA_SPAWN)
    assert w.earned_today() == 0

    # TIME_SCALE speeds the clock and the cooldowns together
    w.cooldown["cartpole"] = 10.0
    before = w.time_left
    scale, S.TIME_SCALE = S.TIME_SCALE, 4.0
    w.tick(1.0)
    S.TIME_SCALE = scale
    assert abs(before - w.time_left - 4.0) < 1e-6, w.time_left
    assert abs(w.cooldown["cartpole"] - 6.0) < 1e-6, w.cooldown


def test_gemma_mode_counts_steps():
    """In gemma mode the day is actions, not seconds, so a slow model gets the same
    day as a fast one -- and cannot wait out a cooldown by thinking."""
    mode = S.DAY_MODE
    S.DAY_MODE = "gemma"
    try:
        w = World()
        assert w.steps == 0 and w.steps_left == S.DAY_STEPS

        # walking into a wall is free; a move that happens is not
        w.pos = (1, 14)
        w.move(-1, 0)
        assert w.steps == 0, "a blocked move should cost nothing"
        w.move(1, 0)
        assert w.steps == 1, w.steps

        # thinking is free: the clock only watches
        w.cooldown["cartpole"] = 5.0
        w.tick(60.0)
        assert w.cooldown["cartpole"] == 5.0, "cooldowns must not tick on wall time"
        assert not w.day_over and w.elapsed >= 60.0
        assert w.steps_left == S.DAY_STEPS - 1

        # ...but acting is not
        for _ in range(5):
            w.spend()
        assert "cartpole" not in w.cooldown, "cooldowns tick per step in gemma mode"

        # the day ends when the budget runs out, and only then
        w.spend(S.DAY_STEPS)
        assert w.day_over and w.steps_left == 0
        w.next_day()
        assert w.steps == 0 and w.elapsed == 0.0
        assert w.history[-1]["day"] == 1 and w.history[-1]["steps"] >= S.DAY_STEPS
    finally:
        S.DAY_MODE = mode


def test_human_mode_still_counts_seconds():
    w = World()
    assert S.DAY_MODE == "human", "the committed default should stay playable by hand"
    w.cooldown["cartpole"] = 5.0
    w.tick(6.0)
    assert "cartpole" not in w.cooldown
    w.tick(S.DAY_SECONDS)
    assert w.day_over and w.time_left == 0


if __name__ == "__main__":
    test_everything_is_reachable()
    test_a_full_run()
    test_the_day_rolls_over()
    test_gemma_mode_counts_steps()
    test_human_mode_still_counts_seconds()
    print("all checks passed")
