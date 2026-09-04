"""scout -- seeing ground the rover has not driven through.

The second machine. Perseverance had Ingenuity flying ahead of it, up over terrain the
rover could not see yet; here that is a window cropped out of the fixed overhead camera
and handed to the map. `ARCHITECTURE.md` -- the camera never moves, so the grid is
projected onto the image rather than painted on the floor, and a region can be revealed
by cutting it out of the picture instead of by driving through it.

**Mechanically this is one call to `Area.reveal_cells` and nothing else.** Everything
gemma is ever shown reads back through `Area.visible` -> `seen`, so `nav.py` and
`sight.py` need no knowledge that this file exists. That is the whole payoff of the fog
having one door, and it is why this landed as a new module rather than as edits spread
across four.

## The cost, which is the actual design

Seeing ground you have not driven is powerful, and anything free gets used for
everything until there is no decision left to make. So three doors, and each shuts a
different one:

  SCOUT_COST      steps, out of the same day the rover drives on -- so a sortie is
                  literally a drive not taken, and the two have to be weighed
  SCOUT_RANGE     how far the window may be centred from the rover -- so knowledge
                  cannot teleport across the map and travel stays necessary
  SCOUT_RECHARGE  steps of driving owed before the next sortie -- so a sol cannot be
                  spent parked in one spot scouting outwards

Range alone would let it scout six windows without moving. Cost alone would let it
park on the pad and buy the far corner. Recharge alone would let it walk knowledge
across the map for free. Any two of them leave a hole.

The measurement they are set against is in `settings.py`: driving buys about 5 new
cells a step early in a sol and 0.2-0.7 once half the map is known. So scouting is a
bad deal early and a good one late, the crossover moves during the day, and whether
the model notices is the thing worth watching. Nothing here special-cases that -- it
falls out of one currency and a flat price.

**It reveals rock as well as regolith**, which is deliberate and is a real cost: a
`goto` through scouted ground can no longer come back BLOCKED, and the blocked drive is
the best thing on the screen. The price is paid knowingly because planning a route you
can see is the point of scouting ahead. If most driving ever stops being into fog, the
knobs are wrong, not this rule.
"""

import nav
import settings as S


def _c(cell):
    return f"({cell[0]},{cell[1]})"


def in_range(world, x, y):
    """Chebyshev, because the window is a square and this is the distance a square
    reaches. Also the one a reader can check by eye off the grid."""
    return max(abs(x - world.pos[0]), abs(y - world.pos[1])) <= S.SCOUT_RANGE


def scout(world, x, y):
    """Fly the window to (x, y) and reveal what it covers.

    Returns `(nav.Result, advice)`. The advice is a sentence, not a field, and it is
    the lesson `FINDINGS.md` paid four days for twice over: `DONE(beside=...)` was read
    as failure until the answer said in words that stopping beside a solid thing IS
    arriving. Every refusal here says what to do instead and that nothing was spent,
    because a code alone leaves a 4B model nothing to act on.

    The wording lives in this file rather than on `nav.Result` so that `nav` keeps
    knowing nothing about the flyer. It is the same reason `flyer.py` exists at all.

    Never raises, never lies, and never moves the rover -- which the answer has to say
    out loud, because a skill that changes the map and not the position reads as one
    that did not fire.

    Refusals cost nothing. A sortie that is out of range or still recharging is a
    mistake rather than an action, the same rule `skills.BAD_ARGS` follows, and
    charging for it would make the constraint part of the difficulty instead of part
    of the decision.
    """
    a, here = world.here, world.pos

    def refuse(code, advice):
        return _log(world, x, y, nav.Result(code, to=(x, y), at=here, new=0)), advice

    if not (0 <= x < a.w and 0 <= y < a.h):
        return refuse("OFF_MAP", f"the {a.name} is {a.w} cells by {a.h}, so there is "
                                 f"nothing there to look at. Nothing was spent.")

    if not in_range(world, x, y):
        d = max(abs(x - here[0]), abs(y - here[1]))
        return refuse("OUT_OF_RANGE",
                      f"that is {d} cells from the rover and the flyer reaches "
                      f"{S.SCOUT_RANGE}. Drive closer first, then scout from there. "
                      f"Nothing was spent.")

    if world.scout_ready_in:
        return refuse("RECHARGING",
                      f"the flyer is on the ground charging and needs "
                      f"{world.scout_ready_in} more steps of driving before it can go "
                      f"up. Drive somewhere, then scout. Nothing was spent.")

    if world.day_over or world.steps_left < S.SCOUT_COST:
        return refuse("NOT_ENOUGH_CHARGE",
                      f"a sortie costs {S.SCOUT_COST} and you have "
                      f"{world.steps_left} left today. Nothing was spent.")

    # The whole capability, in two lines. Everything above is the price of it.
    window = a.box(x, y, S.SCOUT_BOX)
    new = a.reveal_cells(window)

    before = world.steps
    world.spend(S.SCOUT_COST)
    world.scout_ready_at = world.steps + S.SCOUT_RECHARGE
    world.scouts += 1

    # The window is handed over whole and the new cells separately: the box is drawn
    # even where it revealed nothing, because a sortie over already-mapped ground has
    # to look like something happened or it reads as a bug rather than as a waste.
    world.play([("start", here), ("scout", ((x, y), sorted(new)))])

    r = nav.Result("SCOUTED", steps=world.steps - before, to=(x, y), at=here,
                   new=len(new))
    # A sortie that revealed nothing is the same shape as a `goto` that cost nothing:
    # it succeeded, so there is no failure to reason about, and the only thing telling
    # it apart from a good one is a number in a line. Say it.
    advice = ("that window was over ground already on your map, so nothing changed. "
              f"Aim the next one at cells showing ? -- and the flyer now owes "
              f"{S.SCOUT_RECHARGE} steps of driving either way." if not new else
              f"the rover has not moved, only the map has. The flyer needs "
              f"{S.SCOUT_RECHARGE} steps of driving before it can go up again.")
    return _log(world, x, y, r), advice


def _log(world, x, y, result):
    """One row per sortie, whether or not it flew. A refusal is the more interesting
    record: it says the model reached for a capability it could not use, which is what
    tells you the constraints are being felt rather than merely enforced."""
    world.record("scout", area=world.area, at=world.pos, to=(x, y), code=result.code,
                 steps=result.steps, new=result.new, ready_in=world.scout_ready_in)
    return result
