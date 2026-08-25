"""What the current numbers are actually worth. No asserts -- just arithmetic.

    .venv/bin/python game/economy.py

In gemma mode a day is a fixed number of steps, so the only figure that matters is
coins per step. A game's cycle is one step to play plus its cooldown paid in walking.
"""

from collections import deque

import config as C
import settings as S
from world import SOLID, TERMINALS

NEIGHBOURS = ((0, 1), (0, -1), (1, 0), (-1, 0))


def commute():
    """Steps from the Plaza spawn to standing next to each terminal, across areas.

    Uses the true map and ignores pits, so it is the friendliest possible number --
    the real walk is longer. Gemma respawns in the Plaza every day, so this comes
    out of the same budget as playing."""
    start = ("plaza", C.PLAZA_SPAWN)
    dist, q, found = {start: 0}, deque([start]), {}
    while q:
        area, cell = q.popleft()
        rows, d = C.AREAS[area], dist[(area, cell)]
        for dx, dy in NEIGHBOURS:
            n = (cell[0] + dx, cell[1] + dy)
            if not (0 <= n[0] < len(rows[0]) and 0 <= n[1] < len(rows)):
                continue
            ch = rows[n[1]][n[0]]
            if ch in TERMINALS:
                found.setdefault(TERMINALS[ch], d)
                continue
            if ch in SOLID or (area, n) in dist:
                continue
            dist[(area, n)] = d + 1
            q.append((area, n))
            link = C.LINKS.get((area, n))
            if link and link not in dist:
                dist[link] = d + 1
                q.append(link)
    return found


def main():
    print(f"day = {S.DAY_STEPS} steps\n")
    print(f"{'game':<10} {'cycle':>6} {'per day':>8} {'coins/day':>10} {'coins/step':>11}")

    rows = []
    for game, (cd, pay, chance) in S.GAMES.items():
        cycle = cd + 1                      # one step to play, cd steps of walking
        plays = S.DAY_STEPS // cycle
        per_day = plays * pay * chance
        rows.append((game, cycle, plays, per_day, per_day / S.DAY_STEPS))
        print(f"{game:<10} {cycle:>6} {plays:>8} {per_day:>10.0f} {rows[-1][4]:>11.2f}")

    walk, net = commute(), {}
    print(f"\n{'game':<10} {'walk':>6} {'left':>6} {'plays':>6} {'coins/day':>10}   after the walk from spawn")
    for game, (cd, pay, chance) in S.GAMES.items():
        w = walk[game]
        left = max(0, S.DAY_STEPS - w)
        plays = left // (cd + 1)
        net[game] = plays * pay * chance
        print(f"{game:<10} {w:>6} {left:>6} {plays:>6} {net[game]:>10.0f}")

    # The after-the-walk column is the one that decides anything. A game can pay
    # better per step and still not be worth going to.
    ladder = list(S.GAMES)
    for label, table in (("per step", {r[0]: r[4] for r in rows}),
                         ("after the walk", net)):
        ranked = sorted(ladder, key=lambda g: table[g])
        flag = "ok" if ranked == ladder else "INVERTED"
        print(f"\nby {label}, worst to best: {' < '.join(ranked)}   [{flag}]")
        if ranked != ladder:
            print("  a game earlier in settings.GAMES beats a later one, so there is")
            print("  no reason to climb the ladder and farming the safe game is simply")
            print("  correct. Raise the payout of whichever game is out of order.")

    best = max(ladder, key=lambda g: net[g])

    print("\nthe vault chain, one-time:")
    pouch = S.SHOPS["tribe"]["tool_pouch"]
    dose = S.SHOPS["shop"]["antidote"]
    cost = pouch + dose * S.POUCH_UPGRADED
    prize = S.BAGS[("savana2", (4, 17))]
    print(f"  tool_pouch {pouch} + {S.POUCH_UPGRADED} antidotes {dose * S.POUCH_UPGRADED} = {cost}")
    print(f"  vault pays {prize}, so net {prize - cost}")
    print(f"  which is {(prize - cost) / net[best]:.1f} days of farming {best}, before walking there")


if __name__ == "__main__":
    main()
