"""The skills: tolerant of how arguments are written, loud when they can't be used, and
a malformed call never costs a step. The model writes '<nil>' for an argument it means to
leave out, so that must mean "left out", never "avoid nothing"."""

import re

import config
import nav
import settings
import skills
from world import World


PAD = {"x": 15, "y": 16}  # solid, one cell south of where the rover lands


def test_a_plain_goto_drives():
    w = World()
    w.pos = (15, 12)
    c = skills.call(w, "goto", {**PAD, "why": "back to the pad"})
    assert c.result.startswith("DONE"), "arrives"
    # The pad is solid, so this lands beside it. Without `beside=` in the answer,
    # DONE(at=(15,15)) for a goto(15,16) reads as failure and gets reissued.
    assert "beside=" in c.result, "and says it stopped beside a solid target"
    # The field alone isn't enough: arriving beside the target has to be said in words.
    assert "IS arriving" in c.result, "in words as well as a field"

    already = skills.call(w, "goto", {"x": w.pos[0], "y": w.pos[1], "why": "again"})
    # A free no-op is how a confused model bounces between two cells forever.
    assert "already standing" in already.result, "a goto to where you stand says so"
    assert already.steps == 0, "and costs nothing"
    assert c.why == "back to the pad", "the why is kept"
    assert c.steps > 0, "steps were charged"


def _repeat(w, args, n=3, name="goto"):
    history = []
    for _ in range(n):
        history.append(skills.call(w, name, args, history=history))
    return history


def test_going_nowhere_twice_is_said_out_loud():
    w = World()
    args = {**PAD, "why": "the pad"}
    skills.call(w, "goto", args)  # already beside it
    history = _repeat(w, args)
    # A costless success gives the model nothing to correct, so a repeat is said out loud.
    assert "asked for this" not in history[0].result, "the first repeat is answered plainly"
    assert "nothing has changed" in history[-1].result, "the third says it is going nowhere"
    assert history[-1].result.startswith("DONE"), "still honest about arriving"
    assert all(h.steps == 0 for h in history), "and still free"

    # No steps spent means nothing changed, so the same answer, whatever the code.
    w2 = World()
    w2.here.seen = {(x, y) for y in range(w2.here.h) for x in range(w2.here.w)}
    w2.pos = (16, 20)
    rock = {"x": 17, "y": 20, "why": "into the outcrop"}
    far = _repeat(w2, rock)
    assert (far[-1].result.startswith("UNREACHABLE")
                and "nothing has changed" in far[-1].result), "an UNREACHABLE loop is caught too"
    priced = _repeat(w2, {"x": 5, "y": 5, "why": "how far"}, name="distance")
    assert "nothing has changed" in priced[-1].result, "so is pricing the same trip over and over"

    # A call that actually did something ends the run, however often it is repeated.
    w3 = World()
    moved = [skills.call(w3, "goto", {"x": 25, "y": 22, "why": "north"}),
             skills.call(w3, "goto", {"x": 25, "y": 20, "why": "further"})]
    again = skills.call(w3, "goto", {"x": 25, "y": 22, "why": "north"}, history=moved)
    assert "nothing has changed" not in again.result, "a call that moved is left alone"
    # ...and it has to be a *consecutive* run: something else in between resets it.
    w4 = World()
    mixed = [skills.call(w4, "distance", {"x": 22, "y": 22, "why": "a"}),
             skills.call(w4, "distance", {"x": 23, "y": 23, "why": "b"}),
             skills.call(w4, "distance", {"x": 22, "y": 22, "why": "a"})]
    last = skills.call(w4, "distance", {"x": 22, "y": 22, "why": "a"}, history=mixed)
    assert "nothing has changed" not in last.result, "a broken run is not counted"


def test_drives_that_buy_no_map_are_said_out_loud_even_when_they_differ():
    """Drives that buy no map are said out loud even when every target differs: once on each
    gainless drive (Result.advice), and once there is a pattern (_stuck)."""
    w = World()
    w.here.seen = {(x, y) for y in range(w.here.h) for x in range(w.here.w)}  # nothing left

    hist = []
    for x, y in ((15, 10), (15, 20), (15, 10), (15, 20)):
        hist.append(skills.call(w, "goto", {"x": x, "y": y, "why": "casting about"},
                                history=hist))
    assert all(h.steps > 0 for h in hist), "every drive really did spend steps"
    assert all(h.gained == 0 for h in hist), "...and really did learn nothing"
    # The fact, immediately and every time. A drive that spends the day and buys no map
    # must not read as an unqualified success.
    assert all("revealed nothing new" in h.result for h in hist), "each gainless drive says so on its own"
    # The pattern, only once there is one. Driving home to the pad is a gainless drive
    # on purpose, so this must never be a first-offence scold.
    assert not any("bought no new map" in h.result for h in hist[:3]), "the first three are not accused of a habit"
    assert "bought no new map" in hist[3].result, "the fourth is"
    assert "steps," in hist[3].result, "and names what it cost"
    # Alternating targets, so the identical-call rule is not what caught it.
    assert str(hist[2]) != str(hist[1]), "the targets were never the same twice running"

    # Pricing routes is the habit the arena wants more of, not less. Four price checks
    # in a row reveal no map by construction and must not read as being stuck.
    w3 = World()
    prices = []
    for x, y in ((2, 2), (27, 27), (15, 0), (0, 29)):
        prices.append(skills.call(w3, "distance", {"x": x, "y": y, "why": "which"},
                                  history=prices))
    assert all("nothing" not in p.result.split("--")[-1] for p in prices), "comparing four routes is not being stuck"


def test_distance_spends_nothing():
    w = World()
    before = w.steps
    c = skills.call(w, "distance", {"x": 5, "y": 5, "why": "is it worth the drive"})
    assert c.result.startswith("DISTANCE"), "prices it"
    assert c.steps == 0 and w.steps == before, "costs no steps"
    assert "battery holds" in c.result and "seconds" in c.result, "and says what is left, in charge and in time"


def test_a_missing_why_never_stops_the_call():
    """`why` is optional: a call without one still runs."""
    # Not PAD: the rover lands next to the pad, so arriving there costs nothing and
    # would not show that the drive ran. This is a destination it has to travel to.
    away = {"x": 25, "y": 20}
    for label, args in (("absent", dict(away)),
                        ("empty", {**away, "why": "   "}),
                        ("<nil>", {**away, "why": "<nil>"})):
        w = World()
        c = skills.call(w, "goto", args)
        assert not c.result.startswith("BAD_ARGS"), f"{label} why still drives"
        assert c.why is None, f"...and records no reason for it"
        assert w.steps > 0, f"...and actually moved"

    # The point of relaxing one argument is that the others are still checked. A
    # coordinate that cannot be read is still the call that must not silently happen.
    w = World()
    before, where = w.steps, w.pos
    for label, args in (("no y", {"x": 25}), ("junk x", {"x": "east", "y": 26})):
        c = skills.call(w, "goto", args)
        assert c.result.startswith("BAD_ARGS"), f"{label} is still refused"
    assert w.steps == before and w.pos == where, "and neither moved nor spent"

    # Supplied, it is still trimmed and still kept -- that half is untouched.
    kept = skills.call(World(), "goto", {**PAD, "why": "  back   to the pad  "})
    assert kept.why == "back to the pad", "a why that is given is still recorded"


def test_a_bad_avoid_never_becomes_an_empty_one():
    w = World()
    # The silent-empty failure, in every disguise it arrives in.
    for bad in ("north", "the ridge", "(3,4),(5", "auto", "AUTO", 7, {"x": 1}):
        c = skills.call(w, "goto", {**PAD, "why": "w", "avoid": bad})
        assert c.result.startswith("BAD_ARGS"), f"avoid={bad!r} is refused"
    # avoid=auto is refused by name: she has no way to mark cells.
    c = skills.call(w, "goto", {**PAD, "why": "w", "avoid": "auto"})
    assert "mark" in c.result, "...and auto says why, not just no"


def test_avoid_is_read_however_it_is_punctuated():
    for text in ("(3,4),(5,6)", "3,4 5,6", " (3, 4) (5, 6) ", [[3, 4], [5, 6]],
                 [(3, 4), (5, 6)]):
        assert skills._avoid(text) == frozenset({(3, 4), (5, 6)}), f"{text!r} means two cells"
    # An omitted optional argument is the one thing allowed to become nothing, and only
    # when it says so in the ways gemma actually says it.
    for text in (None, "", "<nil>", "none", []):
        assert skills._avoid(text) is None, f"{text!r} means omitted"


def _steps_in(result):
    """The step count out of a DISTANCE line, whatever the comparator in front of it."""
    return int(re.search(r"steps\D*?(\d+)", result).group(1))


def test_an_avoid_that_parses_is_obeyed():
    w = World()
    w.here.seen = {(x, y) for y in range(w.here.h) for x in range(w.here.w)}
    w.pos = (15, 12)
    c = skills.call(w, "distance", {**PAD, "why": "clear run"})
    plain = _steps_in(c.result)
    # Seal the pad's free neighbours from the north. If the parser dropped the list on
    # the floor the number would not move, which is exactly the bug that hides.
    fence = "(14,15),(15,15),(16,15)"
    c = skills.call(w, "distance", {**PAD, "why": "dodging", "avoid": fence})
    assert (c.result.startswith("UNREACHABLE") or
               _steps_in(c.result) != plain), "the list changes the answer"


def test_coordinates_are_taken_generously():
    w = World()
    w.pos = (15, 12)
    assert skills._int("x", "25") == 25, '"25" is 25'
    assert skills._int("x", 25.0) == 25, "25.0 is 25"
    for bad in ("<nil>", "ten", None, 10.5, True, [10]):
        try:
            skills._int("x", bad)
            assert False, f"{bad!r} is refused"
        except skills.BadArgs:
            assert True, f"{bad!r} is refused"
    c = skills.call(w, "goto", {"x": "25", "y": "26", "why": "strings are fine"})
    assert c.result.startswith("DONE"), "and a call with string coordinates works"


def test_an_unknown_skill_says_what_there_is():
    w = World()
    # An unknown skill's answer names the ones that exist, or she keeps guessing at the same absent verb.
    for absent in ("look", "interact", "fly"):
        c = skills.call(w, absent, {"why": "trying it on"})
        assert c.result.startswith("NO_SUCH_SKILL"), f"{absent} refused"
        assert "goto" in c.result and "distance" in c.result, "and lists what exists"
        assert c.steps == 0, "costing nothing"


def _surveyed():
    """A world with the whole arena revealed, so counting is not about fog."""
    w = World()
    w.here.reveal(*w.pos, r=max(w.here.w, w.here.h))
    return w


def test_counting_is_exact_where_reading_the_map_is_not():
    # She can see where the rocks are but can't count their cells, so the sizes must be exact.
    import config
    was = config.ARENA
    try:
        config.use("50")
        w = _surveyed()
        r = skills.call(w, "count", {"kind": "rock"})
        assert r.steps == 0, "it costs no steps"
        assert r.result.count("cells,") == 31, "every formation is listed"
        assert "30 cells" in r.result, "including the one that is 30"
        # Twenty sixteens tie. Listing by size would put the answer at the top and do
        # the deciding; map order leaves the weighing where it belongs.
        middles = [int(m) for m in re.findall(r"middle \((\d+),", r.result)]
        sizes = [int(m) for m in re.findall(r"R\d+: (\d+) cells", r.result)]
        assert sizes != sorted(sizes, reverse=True), "and it is not handed over pre-ranked"
        assert len(middles) == len(sizes), "...but in map order"

        # A middle that is not in its own formation is a coordinate `count_cells` cannot
        # resolve. The C on this arena has its centroid in open ground inside the bay.
        big = re.search(r"R(\d+): 30 cells, middle \((\d+),(\d+)\)", r.result)
        assert bool(big), "the middle of the concave one is a cell of it"
        if big:
            x, y = int(big.group(2)), int(big.group(3))
            assert config.ARENA[y][x] == "#", "...and it really is rock"
            cells = skills.call(w, "count_cells", {"x": x, "y": y})
            assert "30 cells" in cells.result, "count_cells resolves it"
            assert "y15: x30-39" in cells.result, "...as runs, not a wall of coordinates"
            assert cells.steps == 0, "...costing nothing"
    finally:
        config.ARENA = was
        config.use(config.DEFAULT_ARENA)


def test_counting_only_ever_counts_what_she_has_seen():
    # Rock still under fog is fog. A size that silently meant "or more" would be the
    # lying success code again, wearing a number.
    w = World()  # fresh: only the landing site is revealed
    r = skills.call(w, "count", {})
    seen_rock = sum(1 for (x, y) in w.here.seen if w.here.at(x, y) == "#")
    listed = sum(int(n) for n in re.findall(r"R\d+: (\d+) cells", r.result))
    assert listed == seen_rock, "it counts revealed rock and no more"
    assert "FOG" in r.result, "and fog is reported as fog"
    # Open ground is neither, and saying so beats guessing which she meant.
    here = skills.call(w, "count_cells", {"x": w.pos[0], "y": w.pos[1]})
    assert here.result.startswith("NOT_A_FEATURE"), "a cell that is neither is refused by name"


def test_a_formation_keeps_its_name_as_it_comes_out_of_the_fog():
    # Revealed rock only ever grows, so an id is worth carrying: the one event is a
    # merge, and she may have said the losing name out loud.
    import config
    was = config.ARENA
    try:
        config.use("50")
        w = World()
        w.here.reveal(31, 16, r=3)  # part of the C
        first = skills.call(w, "count", {"kind": "rock"}).result
        got = re.search(r"R(\d+): (\d+) cells", first)
        assert bool(got), "it is named on sight"
        w.here.reveal(35, 21, r=6)  # more of the same formation
        second = skills.call(w, "count", {"kind": "rock"}).result
        assert f"R{got.group(1)}:" in second, "the same rock keeps its id"
        assert "new since you last asked" in second, "and the newly revealed cells are called out"
    finally:
        config.ARENA = was
        config.use(config.DEFAULT_ARENA)


def test_every_dialect_of_a_written_call_is_recovered():
    """Typed calls are read in every dialect the model writes: `goto(35, 25)`, keywords, and
    `call:goto{x:49,y:0}`. `count` and `end` need no arguments, so they must be read too."""
    for text, want in [
        # The brace dialect, both argument orders it has been seen in.
        ("call:goto{why:Mapping the north-east quadrant.,x:49,y:0}",
         ("goto", {"x": "49", "y": "0", "why": "Mapping the north-east quadrant."})),
        ("call:goto{x:49,y:0,why:go}", ("goto", {"x": "49", "y": "0", "why": "go"})),
        # The two older ones, which must not have regressed.
        ('goto(15, 10, "Driving north")',
         ("goto", {"x": "15", "y": "10", "why": "Driving north"})),
        ('goto(x=35, y=25, why="east")',
         ("goto", {"x": "35", "y": "25", "why": "east"})),
        # The skills that require nothing, which were unrecoverable before.
        ("count{kind:rock}", ("count", {"kind": "rock"})),
        ("count(kind=rock)", ("count", {"kind": "rock"})),
        ("end{}", ("end", {})),
        ("end()", ("end", {})),
        ("call:end{why:done for now}", ("end", {"why": "done for now"})),
        ("count_cells{x:31,y:18}", ("count_cells", {"x": "31", "y": "18"})),
    ]:
        assert skills.written_call(text) == want, f"recovered: {text[:38]}"
        assert skills.looks_like_a_call(text), f"...and seen as one: {text[:30]}"

    # Loosening the shape is what makes prose dangerous: `end` gives the turn away, so
    # a bracket in a sentence must never read as a call to it.
    for text in ("goto is the right tool here", "at the end (of the sweep) I will stop",
                 "I will count (rocks) later", "the end (of the day)",
                 "no calls here at all"):
        assert not skills.looks_like_a_call(text) and not skills.written_call(text), f"prose left alone: {text[:34]}"

    # Read off the schema, not restated here -- the two drifting apart is the bug.
    assert (skills.REQUIRED == {t["function"]["name"]:
                                    set(t["function"]["parameters"]["required"])
                                    for t in skills.TOOLS}), "what a recovery must carry comes from the schema itself"


def test_a_typed_write_is_read_in_its_own_argument_order():
    """Typed list writes (`todo("...", "why")`) are read with the skill's own argument order,
    and need no digit in the brackets."""
    for text, want in [
        ('todo("Explore north of the pad", "Initial mapping")',
         [("todo", {"text": "Explore north of the pad", "why": "Initial mapping"})]),
        ('strike(2, "done")', [("strike", {"n": "2", "why": "done"})]),
        ('remember("plan", "north first, then the C")',
         [("remember", {"name": "plan", "text": "north first, then the C"})]),
        ('forget("plan")', [("forget", {"name": "plan"})]),
        ('remember(name="plan", "north first")',
         [("remember", {"name": "plan", "text": "north first"})]),
        # Coordinates in the text are brackets of its own.
        ('todo("Execute high priority objective at (27,42)")',
         [("todo", {"text": "Execute high priority objective at (27,42)"})]),
        # A skill named inside the text is part of the text.
        ('todo("goto(10, 5) first")', [("todo", {"text": "goto(10, 5) first"})]),
        # An apostrophe in the brace dialect is a word, not a quote.
        ("call:goto{why:the rover's path,x:49,y:0}",
         [("goto", {"why": "the rover's path", "x": "49", "y": "0"})]),
    ]:
        got = skills.written_calls(text)
        assert got == want, f"read: {text[:40]}"
        assert skills.looks_like_a_call(text), f"...and seen as one: {text[:30]}"

    # Words have to be quoted to be read: unquoted, they are a sentence. A `radio` read
    # out of one would cost battery and end her turn.
    for text in ("I will radio (if needed)", "I'll forget (the old plan) for now",
                 "a todo (for later)", "remember (the C)"):
        assert not skills.written_calls(text) and not skills.looks_like_a_call(text), f"prose left alone: {text[:34]}"

    # Her night's reply from that run, verbatim: all three, in order.
    night = ('Since Order 1 has been removed, I am free to explore the rest of the Jezero '
             'flats.\n\ntodo("Explore north of the pad", "General mapping")\n'
             'todo("Explore east of the pad", "General mapping")\n'
             'todo("Identify the largest rock formation", "Mission goal")')
    got = skills.written_calls(night)
    assert ([a.get("text") for _, a in got] == [
                    "Explore north of the pad", "Explore east of the pad",
                    "Identify the largest rock formation"]), "a run of typed writes is read whole, in order"
    assert skills.written_call(night) == got[0], "and written_call is still the first of them"


def test_the_schema_matches_what_is_wired_up():
    names = {t["function"]["name"] for t in skills.TOOLS}
    assert (names == {"goto", "distance", "execute", "count", "count_cells",
                         "todo", "strike", "remember", "forget", "radio", "end"}), "exactly eleven skills"
    blob = str(skills.TOOLS)
    # Optional, and the schema has to say so.
    assert (all("why" in t["function"]["parameters"]["properties"]
                    for t in skills.TOOLS)), "why is offered on all of them"
    assert (not any("why" in t["function"]["parameters"]["required"]
                        for t in skills.TOOLS)), "...and required on none"
    # Only where a cell is what the call is about. count and end take none.
    placed = {"goto", "distance", "count_cells"}
    assert (all(({"x", "y"} <= set(t["function"]["parameters"]["required"]))
                    == (t["function"]["name"] in placed) for t in skills.TOOLS)), "...and x and y are required exactly where a cell is meant"
    # goto says it drives the whole way, or the model steps one cell per call.
    assert "whole way" in blob, "goto says it drives the whole way"
    assert "ABSOLUTE" in blob, "and that coordinates are absolute"
    # avoid="auto" has no mark() behind it yet, so it must not be offered.
    assert "auto'" not in blob and '"auto"' not in blob, "auto is not offered"
    # Nothing unbuilt may be promised in the schemas.
    for absent in ("interact", "sample", "storm", "Ingenuity",
                   "scout", "flyer"):
        assert absent.lower() not in blob.lower(), f"{absent} is not advertised"


def test_the_way_home_is_warned_about_in_time():
    w = World()
    w.pos = (15, 5)  # ten rows north of the landing site
    back = nav.home_steps(w)
    w.spend(settings.BATTERY - back - settings.BATTERY // 10 - 1)
    assert "Head back" not in skills.budget_note(w), "with charge to spare, no warning"
    w.spend(1)
    note = skills.budget_note(w)
    assert "Head back now" in note, "once the margin is gone, it says go home"
    assert f"at least {back} steps away" in note, "and how far the pad is"
    w.pos = config.SPAWN
    assert ("Head back" not in
                skills.budget_note(w)), "beside the pad, only the plain count"

    # The clock can be the one that runs short: a full battery and little day left.
    w = World()
    w.pos, w.phase = (15, 5), "day"
    w.run_clock(w.time_left - nav.drive_seconds(back) - settings.DAY_SECONDS / 10)
    assert "Head back now" in skills.budget_note(w), "short of time with charge to spare, it still says go home"
