r"""Can gemma read the map she is sent? Measured, both arms, at two temperatures.

Answered: she cannot count cells off the picture, and gemini can. The table is in
`../prototype2/results.md`.

Every answer is scored against the view block she was actually shown, never against the
true arena, which she cannot see.

Two axes:
  * *quantitative* -- name the cell at (x,y), count the classes in a box, list the rock
    on a row. All of these need indexing a coordinate into a 50-character row.
  * *qualitative* -- which quadrant holds the most fog, where is the biggest unexplored
    region. No counting, just texture. Each is forced-choice with a baseline computed in
    code, so "lucky" is a number rather than a worry.

Two prompts: the live one, and the same with the two sentences restored that forbade
counting cells off the grid. Temp 0 runs once as the deterministic reference and the
model's own defaults run N times for a distribution; the two are never averaged.

No tools are sent, so the turn has to end in words and a refusal is a refusal.

`--backend gemini` puts the identical prompt, view and questions in front of a hosted
model -- only the transport differs. The hosted arm runs unblocked only.

Run:
    ..\.venv\Scripts\python.exe game\probe_map.py --pilot                 # six calls, to time it
    ..\.venv\Scripts\python.exe game\probe_map.py --samples 1             # the gemma arm
    GEMINI_API_KEY=... game/probe_map.py --list-models         # what the key can reach
    GEMINI_API_KEY=... game/probe_map.py --backend gemini      # the hosted arm
    ..\.venv\Scripts\python.exe game\probe_read.py runs/<dir>/probe.jsonl # score either, offline
"""

import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import chat
import config as C
import nav
import settings as S
import sight
import skills
from world import World, components

# The paragraph the current prompt had until 2026-08-31, restored here so the control
# arm is the prompt that produced the 0/3 rather than some other prompt. Swapped in by
# string replacement, with an assert, so an edit upstream fails loudly instead of
# quietly running the same arm twice.
BLOCKED_PARA = """\
**Never work out for yourself whether the rover can reach something.** The picture of
the map is the shape of the place, not a table, and you will misread it if you count
cells off it. Everything exact -- what is beside the rover, how far each way is open,
where each landmark is -- is written out underneath the picture. Read it there."""

LIVE_PARA_HEAD = "**The map in your view is a real map and you can read it.**"


def systems():
    """(unblocked, blocked) system prompts, differing only in the map paragraph."""
    live = chat.SYSTEM
    assert LIVE_PARA_HEAD in live, "the unblocked map paragraph is gone from chat.SYSTEM"
    head = live.index(LIVE_PARA_HEAD)
    tail = live.index("Use `distance` only to compare journeys")
    blocked = live[:head] + BLOCKED_PARA + "\n\n" + live[tail:]
    assert blocked != live and LIVE_PARA_HEAD not in blocked
    return live, blocked


def view_for(w, blocked):
    """The view block as it would have been built under either heading.

    `sight.view` reads both constants at call time, so swapping them is enough and no
    second copy of the renderer has to exist to be kept in step with the first.
    """
    if not blocked:
        return sight.view(w)
    keep = sight.GRID_HEADING, sight.REVEAL_RULE
    sight.GRID_HEADING = sight.blocked_GRID_HEADING
    sight.REVEAL_RULE = sight.blocked_REVEAL_RULE
    try:
        return sight.view(w)
    finally:
        sight.GRID_HEADING, sight.REVEAL_RULE = keep


# --- the worlds ------------------------------------------------------------
# Three coverage levels, because varying the world state is the only honest way to get
# more than one sample out of a greedy decoder. The drives are fixed, so every arm sees
# byte-identical maps and the comparison is paired.
DRIVES = [
    [(25, 40), (10, 40), (10, 20)],
    [(25, 40), (10, 40), (10, 20), (40, 20), (40, 45), (5, 45), (5, 5), (45, 5)],
    [(25, 40), (10, 40), (10, 20), (40, 20), (40, 45), (5, 45), (5, 5), (45, 5),
     (25, 25), (18, 10), (32, 35), (45, 30), (3, 30), (30, 3), (20, 47)],
]


def build_worlds():
    out = []
    for drives in DRIVES:
        w = World()
        for x, y in drives:
            nav.goto(w, x, y)
        out.append(w)
    return out


def cls(w, x, y):
    """The three answers a cell can have, as gemma's own map has them."""
    ch = nav.known(w.here, x, y)
    if ch is None:
        return "unseen"
    return "rock" if ch == "#" else "open"


ROW = re.compile(r"^\s*(\d{1,2})  (.{50})$", re.M)


def audit(w):
    """Check `cls` against the grid actually rendered, and die if they disagree.

    An answer is scored against the block she was handed
    and never against the true arena, because the two differ everywhere she has not
    driven. `cls` reads `nav.known`, which is one layer below the renderer -- close
    enough to be right and close enough to drift. So the rendered rows are parsed back
    and compared, which costs nothing and makes the claim checkable rather than trusted.

    The rover's own cell renders as `@` and is skipped: it is drawn over whatever is
    underneath, and it is excluded from every question for the same reason.
    """
    rows = dict(ROW.findall(sight.grid(w)))
    assert len(rows) == w.here.h, f"parsed {len(rows)} rows, not {w.here.h}"
    bad = []
    for y in range(w.here.h):
        line = rows[str(y)]
        for x in range(w.here.w):
            if (x, y) == w.pos:
                continue
            drawn = {"?": "unseen", "#": "rock"}.get(line[x], "open")
            if drawn != cls(w, x, y):
                bad.append((x, y, line[x], cls(w, x, y)))
    assert not bad, f"{len(bad)} cells disagree with the rendered grid, e.g. {bad[:3]}"
    return len(rows)


def box(w, x0, x1, y0, y1):
    got = {"rock": 0, "open": 0, "unseen": 0}
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            got[cls(w, x, y)] += 1
    return got


def quadrant_counts(w, kind):
    a = w.here
    mx, my = a.w // 2, a.h // 2
    got = {"NW": 0, "NE": 0, "SW": 0, "SE": 0}
    for y in range(a.h):
        for x in range(a.w):
            if cls(w, x, y) != kind:
                continue
            got[("N" if y < my else "S") + ("W" if x < mx else "E")] += 1
    return got


# --- the questions ---------------------------------------------------------
# Each returns (prompt_text, truth, scorer_key, extra). `truth` is computed here and
# never parsed back out of prose.
FORMAT = {
    "cell": "Answer with exactly one word: ROCK, OPEN, or UNSEEN.",
    "region": "Answer in exactly this form and nothing else: rock=N open=N unseen=N",
    "row": "Answer in exactly this form: rock at x=1,2,3   (or: rock at x=none)",
    "quad": "Answer with exactly one of: NW, NE, SW, SE",
    "cellpick": "Answer with exactly one coordinate in the form (x,y)",
    "near": "Answer with exactly one word: ROCKY or CLEAR",
}


def make_questions(worlds, seed=7):
    rng = random.Random(seed)
    qs = []
    for wi, w in enumerate(worlds):
        a = w.here
        # The rover's own cell is drawn as `@` over whatever is underneath it, so it is
        # the one cell where the grid and `cls` legitimately disagree. Kept out of every
        # question rather than special-cased in the scoring.
        cells = {"rock": [], "open": [], "unseen": []}
        for y in range(a.h):
            for x in range(a.w):
                if (x, y) != w.pos:
                    cells[cls(w, x, y)].append((x, y))

        # --- quantitative: every one of these needs the grid indexed ---
        for kind in ("rock", "open", "unseen"):
            if not cells[kind]:
                continue
            x, y = rng.choice(cells[kind])
            qs.append(dict(
                world=wi, axis="quant", kind="cell", scorer="cell",
                q=f"What is at cell ({x},{y}) on your map? {FORMAT['cell']}",
                truth=kind, extra={"cell": [x, y]}))

        # Two boxes: one mixed, and one with no fog in it at all. The second is probe 3
        # the region she refused to describe was fully revealed.
        picked = []
        for want_clear in (False, True):
            for _ in range(400):
                x0 = rng.randrange(0, a.w - 6)
                y0 = rng.randrange(0, a.h - 5)
                got = box(w, x0, x0 + 5, y0, y0 + 4)
                if want_clear and got["unseen"]:
                    continue
                if not want_clear and (got["unseen"] == 0 or got["rock"] == 0):
                    continue
                if max(got.values()) == 30:      # a uniform box cannot catch a uniform fill
                    continue
                if x0 <= w.pos[0] <= x0 + 5 and y0 <= w.pos[1] <= y0 + 4:
                    continue                     # the `@` cell, kept out -- see `audit`
                picked.append((x0, y0, got))
                break
        for x0, y0, got in picked:
            qs.append(dict(
                world=wi, axis="quant", kind="region", scorer="region",
                q=(f"Look at the rectangle from x={x0} to x={x0 + 5} and y={y0} to "
                   f"y={y0 + 4} on your map, 30 cells in all. How many of those cells "
                   f"are rock, how many are open regolith, and how many have never "
                   f"been seen? {FORMAT['region']}"),
                truth=got, extra={"x0": x0, "y0": y0, "clear": got["unseen"] == 0}))

        # A row segment, which is the same read stretched sideways.
        for _ in range(400):
            y = rng.randrange(a.h)
            x0 = rng.randrange(0, a.w - 20)
            seg = [x for x in range(x0, x0 + 20) if cls(w, x, y) == "rock"]
            if y == w.pos[1] and x0 <= w.pos[0] <= x0 + 19:
                continue                         # the `@` cell, kept out -- see `audit`
            if 1 <= len(seg) <= 8:
                qs.append(dict(
                    world=wi, axis="quant", kind="row", scorer="row",
                    q=(f"On row y={y} of your map, looking only at columns x={x0} "
                       f"through x={x0 + 19}, which x coordinates are rock? "
                       f"{FORMAT['row']}"),
                    truth=seg, extra={"y": y, "x0": x0}))
                break

        # --- qualitative: texture, no indexing, forced choice ---
        for kind, word in (("unseen", "never been seen"), ("rock", "rock")):
            got = quadrant_counts(w, kind)
            best = max(got, key=got.get)
            if sorted(got.values())[-1] == sorted(got.values())[-2]:
                continue                      # a tie has no right answer
            qs.append(dict(
                world=wi, axis="qual", kind=f"quad_{kind}", scorer="quad",
                q=(f"Divide your map into four quadrants: NW is x<25 and y<25, NE is "
                   f"x>=25 and y<25, SW is x<25 and y>=25, SE is x>=25 and y>=25. "
                   f"Which quadrant contains the most cells that have {word}? "
                   f"{FORMAT['quad']}"),
                truth=best, extra={"counts": got, "baseline": 0.25}))

        blobs = components(a.w, a.h, lambda x, y: (x, y) not in a.seen)
        if blobs:
            total = sum(len(b) for b in blobs)
            qs.append(dict(
                world=wi, axis="qual", kind="biggest_fog", scorer="cellpick",
                q=("Find the single largest connected region of never-seen (?) ground "
                   "on your map. Give me one coordinate that lies inside it. "
                   f"{FORMAT['cellpick']}"),
                truth=sorted(blobs[0]),
                extra={"baseline": round(len(blobs[0]) / total, 3),
                       "blobs": len(blobs), "biggest": len(blobs[0])}))

        px, py = w.pos
        near = any(cls(w, px + dx, py + dy) == "rock"
                   for dx in range(-5, 6) for dy in range(-5, 6)
                   if 0 <= px + dx < a.w and 0 <= py + dy < a.h)
        qs.append(dict(
            world=wi, axis="qual", kind="near_rock", scorer="near",
            q=(f"The rover is at ({px},{py}). Looking at your map, is there any rock "
               f"within 5 cells of it in any direction? {FORMAT['near']}"),
            truth="rocky" if near else "clear", extra={"baseline": 0.5}))
    return qs


# --- reading the answers ---------------------------------------------------
REFUSAL = re.compile(
    r"cannot|can't|can not|unable|do not have|don't have|no access|not allowed|"
    r"without driving|need to drive|must drive|have not (?:yet )?(?:seen|explored)|"
    r"impossible to|not possible to|i do not know|i don't know", re.I)

WORDS = {"rock": r"\brock|\boutcrop|\bboulder|\bimpassable",
         "open": r"\bopen\b|\bregolith|\bclear\b|\bdrivable|\bwalkable|\bfloor",
         "unseen": r"\bunseen|\bunexplored|\bnever seen|\bunknown|\bfog|\bnot seen"}


# She answers with the glyph itself about as often as with the word -- the pilot got a
# bare `?` back, which is the map's own character for never-seen and is a perfectly good
# answer that the word list scored as silence. Only accepted when the whole reply is the
# glyph, because `#` and `.` inside a sentence are punctuation.
GLYPH = {"?": "unseen", "#": "rock", ".": "open"}


def _first_word(text, table):
    bare = (text or "").strip().strip("'\"`*. \n")
    if bare in GLYPH:
        return GLYPH[bare]
    hits = []
    for name, pat in table.items():
        m = re.search(pat, text, re.I)
        if m:
            hits.append((m.start(), name))
    return min(hits)[1] if hits else None


def score(q, said):
    """Returns (verdict, parsed). verdict is True/False/None -- None means no answer."""
    t, k = said or "", q["scorer"]
    if k == "cell":
        got = _first_word(t, WORDS)
        return (None, None) if got is None else (got == q["truth"], got)
    if k == "region":
        got = {}
        for name in ("rock", "open", "unseen"):
            m = re.search(rf"{name}\s*[=:]\s*(\d+)", t, re.I)
            if m:
                got[name] = int(m.group(1))
        if len(got) < 3:
            return None, got or None
        return got == q["truth"], got
    if k == "row":
        if re.search(r"\bnone\b", t, re.I) and not re.search(r"x\s*=\s*\d", t, re.I):
            return q["truth"] == [], []
        x0 = q["extra"]["x0"]
        got = sorted({int(n) for n in re.findall(r"\d+", t)
                      if x0 <= int(n) <= x0 + 19})
        if not got:
            return None, None
        return got == sorted(q["truth"]), got
    if k == "quad":
        m = re.search(r"\b(NW|NE|SW|SE)\b", t, re.I)
        if not m:
            return None, None
        got = m.group(1).upper()
        return got == q["truth"], got
    if k == "cellpick":
        m = re.search(r"\(\s*(\d+)\s*,\s*(\d+)\s*\)", t)
        if not m:
            return None, None
        got = [int(m.group(1)), int(m.group(2))]
        return got in [list(c) for c in q["truth"]], got
    if k == "near":
        m = re.search(r"\brocky\b|\bclear\b", t, re.I)
        if not m:
            return None, None
        got = m.group(0).lower()
        return got == q["truth"], got
    raise AssertionError(k)


def uniform_fill(q, parsed):
    """Did she answer a 30-cell box as though every cell were the same thing?

    The signature failure: not an off-by-one, a whole box reported as
    one class. Worth counting separately, because it is the shape of an answer produced
    without looking rather than a misread.
    """
    if q["scorer"] != "region" or not parsed or len(parsed) < 3:
        return None
    return max(parsed.values()) == sum(parsed.values()) == 30


# --- the call --------------------------------------------------------------
# Two backends behind one signature. The *only* thing that differs between them is the
# transport: identical system prompt, identical view block, identical question text,
# identical scorer. Anything else that varied would make the comparison worthless,
# which is the whole reason the gemini arm is worth running at all.
def ask(system, view, question, temp):
    """One request, shaped exactly the way `chat._go` shapes one: the question is a
    user turn and the view is appended after it. No tools, so it must answer in words."""
    options = {"num_ctx": S.MODEL_CTX}
    if temp is not None:
        options["temperature"] = temp
    payload = {"model": S.MODEL, "stream": False, "think": False,
               "keep_alive": S.MODEL_KEEP_ALIVE, "options": options,
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": question},
                            {"role": "user", "content": view}]}
    req = urllib.request.Request(S.OLLAMA_HOST, json.dumps(payload).encode(),
                                {"Content-Type": "application/json"})
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=S.MODEL_TIMEOUT) as r:
        d = json.loads(r.read())
    said = chat.clean((d.get("message") or {}).get("content") or "")[0]
    return said, round(time.monotonic() - t0, 1), d.get("prompt_eval_count", 0), \
        d.get("eval_count", 0)


def _key():
    """The key, from the environment. Never from a settings file that gets committed.

    The paste check is here because the setting is an indirection -- it holds the
    *name* of an environment variable, not a key -- and on 2026-09-02 the obvious thing
    happened: the key went into the setting, `os.environ` was asked for a variable named
    after a secret, and the failure message read `set AQ.Ab8RN6... -- get one from`.
    A confusing name earns a sentence rather than a shrug.
    """
    name = S.GEMINI_KEY_ENV
    if name.startswith(("AQ.", "AIza")) or len(name) > 40:
        sys.exit(f"settings.GEMINI_KEY_ENV holds the NAME of an environment variable, "
                 f"not the key itself. Set it back to 'GEMINI_API_KEY' and run "
                 f"`export GEMINI_API_KEY=...` in the shell.")
    key = os.environ.get(name, "").strip()
    if not key:
        sys.exit(f"set {name} -- get one from https://aistudio.google.com/apikey")
    return key


def _post(url, payload, key):
    """POST, and put the server's own explanation into the exception.

    **urllib discards the response body on a 4xx, and that is what made a 401 opaque.**
    Google answers with JSON naming the actual fault -- `ACCESS_TOKEN_TYPE_UNSUPPORTED`,
    `API_KEY_INVALID`, a quota message -- and none of it reached the screen, so a known
    key-format problem looked like a bug in this file for twenty minutes.
    """
    head = {"Content-Type": "application/json"}
    head.update({"bearer": {"Authorization": f"Bearer {key}"}}
                .get(S.GEMINI_AUTH, {"x-goog-api-key": key}))
    body = json.dumps(payload).encode() if payload else None
    for attempt in range(S.GEMINI_RETRIES + 1):
        try:
            req = urllib.request.Request(url, body, head)
            with urllib.request.urlopen(req, timeout=S.MODEL_TIMEOUT) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            text = (e.read() or b"").decode("utf-8", "replace")[:900]
            err = urllib.error.HTTPError(
                e.url, e.code, f"{e.reason} -- {text}", e.headers, None)
            # **429 and 5xx are weather; 4xx is a fault.** A key that is not accepted
            # will not be accepted in eight seconds, and retrying it burns quota to
            # learn nothing. "high demand, spikes are usually temporary" is the
            # opposite case and is the one thing here worth waiting out.
            if e.code != 429 and e.code < 500:
                raise err from None
            # Not every 429 is a rate limit. `input_token_count` is per minute and
            # pacing fixes it; `requests` is a daily allowance no backoff recovers.
            wait = 2 ** attempt * 2
            if e.code == 429:
                asked = re.search(r"retry[_ ]?delay\"?[:\s\"]+(\d+)", text, re.I)
                if asked:
                    wait = max(wait, int(asked.group(1)))
                metric = re.search(r"metric:\s*\S*?/(\w+)", text)
                name = metric.group(1) if metric else ""
                # KNOWN WRONG -- see prototype3/HANDOFF.md. The regex above misses the
                # server's actual wording ("Please retry in 58.5s"), so this aborts runs
                # that had quota left and should have waited.
                spent = name.endswith("_requests") or "per_day" in name
                if spent or wait > S.GEMINI_MAX_BACKOFF:
                    raise urllib.error.HTTPError(
                        e.url, e.code,
                        f"quota exhausted, not a rate limit -- {name or 'unknown metric'}"
                        + (f"; server asks for {wait}s" if asked else
                           "; server sent no retryDelay")
                        + f". It resets at midnight Pacific; a different model has its "
                          f"own allowance (quota is per model) -- {text}",
                        e.headers, None) from None
            if attempt == S.GEMINI_RETRIES:
                raise err from None
            print(f"    {e.code}, retrying in {wait}s "
                  f"({attempt + 1}/{S.GEMINI_RETRIES})", file=sys.stderr)
            time.sleep(wait)


def ask_gemini(system, view, question, temp):
    """The same request against a hosted model. Returns the same tuple as `ask`.

    The two user turns are kept as two turns rather than concatenated, because `chat`
    sends them as two and the point of this arm is that nothing but the model changed.

    **Thinking is pinned to the lowest setting the model offers.** The gemma arm ran
    with it off, and a gemini answering with a reasoning budget gemma never had would
    measure the budget rather than the model. `S.GEMINI_THINKING` is on every row of
    the tape so that choice is visible rather than buried here.
    """
    turn = lambda t: {"type": "user_input", "content": [{"type": "text", "text": t}]}
    # Empty means send no thinking setting at all. Not every model on this host takes
    # `thinking_level` -- the Gemma models are the ones to watch -- and a 400 over a
    # field we only set for comparability would stop a run for nothing.
    cfg = {"thinking_level": S.GEMINI_THINKING} if S.GEMINI_THINKING else {}
    if temp is not None:
        cfg["temperature"] = temp
    payload = {"model": S.GEMINI_MODEL, "system_instruction": system,
               "input": [turn(question), turn(view)], "generation_config": cfg}
    t0 = time.monotonic()
    d = _post(S.GEMINI_HOST, payload, _key())
    # The response is a list of steps and a `thought` step can come first, so the text
    # is found by type rather than by index. Reading steps[0] would score the reasoning
    # trace on the turns that have one and the answer on the turns that do not.
    said = ""
    for step in d.get("steps") or []:
        if step.get("type") == "model_output":
            said = "".join(c.get("text") or "" for c in (step.get("content") or []))
            break
    u = d.get("usage") or {}
    return chat.clean(said)[0], round(time.monotonic() - t0, 1), \
        u.get("total_input_tokens", 0), u.get("total_output_tokens", 0)


def list_models():
    """What this key can actually reach. Model names move and this repo does not guess
    them -- paste one of these into `settings.GEMINI_MODEL`.

    **Run this before the probe, always.** It is one request against the same host with
    the same auth, so it separates "the key does not work" from "the probe is wrong"
    for free, instead of discovering it 210 calls into a fourteen-minute run.
    """
    key = _key()
    print(f"key {key[:4]}... via {S.GEMINI_AUTH} -> {S.GEMINI_MODELS_URL}",
          file=sys.stderr)
    try:
        d = _post(S.GEMINI_MODELS_URL, None, key)
    except urllib.error.HTTPError as e:
        print(f"\n{e}\n", file=sys.stderr)
        if "ACCESS_TOKEN_TYPE_UNSUPPORTED" in str(e) or key.startswith("AQ."):
            print("This is the known `AQ.` key problem, not a bug here. AI Studio has\n"
                  "started issuing keys prefixed `AQ.` where the REST API still wants\n"
                  "the older `AIza` form. Two things to try, in order:\n"
                  "  1. settings.GEMINI_AUTH = 'bearer', then run this again.\n"
                  "  2. Make an `AIza` key in the Google Cloud console for the same\n"
                  "     project (APIs & Services -> Credentials -> Create API key),\n"
                  "     with the Generative Language API enabled on it.",
                  file=sys.stderr)
        return 1
    for m in d.get("models") or []:
        name = (m.get("name") or "").replace("models/", "")
        print(f"  {name:44s} {m.get('displayName', '')}")
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pilot", action="store_true", help="six calls, to time it")
    p.add_argument("--samples", type=int, default=3, help="repeats at model default temp")
    p.add_argument("--axis", choices=("quant", "qual", "all"), default="all",
                   help="ask only one half of the set. The free tier meters requests "
                        "per day, not tokens, so `--axis quant --samples 0` is 18 "
                        "calls at temp 0 and fits inside a 20-request bucket.")
    p.add_argument("--backend", choices=("gemma", "gemini"), default="gemma")
    p.add_argument("--model", default=None,
                   help="override settings.GEMINI_MODEL for this run, e.g. gemma-4-31b-it")
    p.add_argument("--thinking", default=None, metavar="LEVEL",
                   help="reasoning budget, and the allowed values differ by model: "
                        "'minimal'/'high' for gemma-4, 'low' for gemini-3.x. "
                        "'off' sends no setting at all. Use the lowest the model has.")
    p.add_argument("--list-models", action="store_true",
                   help="what the gemini key can reach, then exit")
    p.add_argument("--out", default=None)
    args = p.parse_args()

    if args.list_models:
        return list_models()

    hosted = args.backend == "gemini"
    # Both are written back onto the settings module rather than threaded through, so
    # that `ask_gemini` sends them and the tape records them from one place. A flag the
    # request honours but the tape does not is how two runs get compared as one.
    if hosted and args.model:
        S.GEMINI_MODEL = args.model      # `ask_gemini` reads it at call time
    if hosted and args.thinking is not None:
        S.GEMINI_THINKING = "" if args.thinking.lower() in ("off", "none", "") \
            else args.thinking
    if hosted and not S.GEMINI_MODEL:
        sys.exit("settings.GEMINI_MODEL is blank -- run --list-models and paste one in")
    send, model = (ask_gemini, S.GEMINI_MODEL) if hosted else (ask, S.MODEL)

    worlds = build_worlds()
    live, blocked = systems()
    # Filtered after generation, never inside `make_questions`, so the seeded rng draws
    # the same questions whatever is asked. `--axis quant` has to be the same eighteen
    # questions the full run would have asked, or it is a different probe wearing the
    # same name. Nothing extra goes on the tape: every row already carries its own
    # `axis` and `kind`, so a filtered tape describes itself.
    qs = [q for q in make_questions(worlds)
          if args.axis in ("all", q["axis"])]
    if not qs:
        sys.exit(f"--axis {args.axis} selected no questions")

    for i, w in enumerate(worlds):
        a = w.here
        rows = audit(w)
        print(f"world {i}: seen {len(a.seen)}/{a.w * a.h} "
              f"({len(a.seen) / (a.w * a.h):.0%}), rover at {w.pos}, "
              f"{rows} rendered rows agree with ground truth", file=sys.stderr)
    print(f"{len(qs)} questions "
          f"({sum(q['axis'] == 'quant' for q in qs)} quant, "
          f"{sum(q['axis'] == 'qual' for q in qs)} qual)", file=sys.stderr)

    views = {(wi, b): view_for(worlds[wi], b)
             for wi in range(len(worlds)) for b in (False, True)}

    # Unblocked only for the hosted arm: the question is whether a bigger model can read
    # the view we actually ship, and running both would double a scarce request budget.
    arms = (("unblocked", live),) if hosted else \
           (("unblocked", live), ("blocked", blocked))
    runs = []
    for q in qs:
        for arm, system in arms:
            for temp, n in ((0.0, 1), (None, args.samples)):
                for s in range(n):
                    runs.append((q, arm, system, temp, s))
    if args.pilot:
        runs = runs[:6]

    stamp = time.strftime("%Y%m%d-%H%M%S")
    # The model goes in the directory name as well as on every row. Two hosted runs in
    # one evening is now the expected case, and `probe-gemini-<stamp>` twice over is a
    # pair of tapes you have to open to tell apart.
    tag = "probe" if not hosted else f"probe-{model}"
    out = Path(args.out or Path(__file__).resolve().parents[1] /
               "runs" / f"{tag}-{stamp}" / "probe.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    # Sleep to stay under the free-tier ceiling rather than retrying on 429: a retry
    # storm against a shared quota is rude, and four extra minutes cost nothing.
    gap = 60.0 / S.GEMINI_RPM if hosted else 0.0
    print(f"{len(runs)} calls to {model} -> {out}"
          + (f" (>={gap:.1f}s apart, ~{len(runs) * gap / 60:.0f}m)" if gap else ""),
          file=sys.stderr)

    t0, errs, run_of_errors = time.monotonic(), 0, 0
    with out.open("w", encoding="utf-8") as f:
        for i, (q, arm, system, temp, s) in enumerate(runs):
            view = views[(q["world"], arm == "blocked")]
            sent = time.monotonic()
            try:
                said, secs, tin, tout = send(system, view, q["q"], temp)
                err = None
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
                said, secs, tin, tout, err = "", 0, 0, 0, f"{type(e).__name__}: {e}"
                errs, run_of_errors = errs + 1, run_of_errors + 1
            else:
                run_of_errors = 0
            ok, parsed = score(q, said) if not err else (None, None)
            # Asked what sits at (12,35), the blocked arm once replied with a `goto`
            # call. No tools were sent, so it could not have driven. Counted rather than
            # binned: answering a map question by trying to move is the behaviour.
            rec = {"i": i, "world": q["world"], "axis": q["axis"], "kind": q["kind"],
                   "arm": arm, "temp": temp, "sample": s, "q": q["q"],
                   "truth": q["truth"], "extra": q["extra"], "said": said,
                   "parsed": parsed, "correct": ok,
                   "refused": bool(REFUSAL.search(said)),
                   "narrated": bool(skills.written_call(said)),
                   "uniform": uniform_fill(q, parsed),
                   "seconds": secs, "tokens_in": tin, "tokens_out": tout, "error": err,
                   # On every row, because a tape whose model has to be inferred from
                   # its directory name is a tape that gets compared to the wrong one.
                   "model": model,
                   "thinking": S.GEMINI_THINKING if hosted else False,
                   # Which prompt asked it. Two tapes were once compared as replications
                   # when `chat.SYSTEM` had changed between them and nothing said so.
                   "system_sha": hashlib.sha256(system.encode()).hexdigest()[:8]}
            f.write(json.dumps(rec, ensure_ascii=False, default=list) + "\n")
            f.flush()
            done = i + 1
            rate = (time.monotonic() - t0) / done
            print(f"[{done}/{len(runs)}] {arm:9s} t={str(temp):4s} {q['kind']:12s} "
                  f"{'ok ' if ok else ('MISS' if ok is False else '-- ')} "
                  f"{secs}s  eta {(len(runs) - done) * rate / 60:.0f}m"
                  + (f"  {err}" if err else ""), file=sys.stderr)
            # Auth and quota faults are not transient: every remaining call fails the
            # same way. Grinding through 210 of them takes fourteen minutes and writes
            # a tape of nothing. Stop once the failing row is safely on the tape, so
            # the server's own explanation can be read back out of it.
            if run_of_errors >= 3:
                print(f"\n** stopped after {run_of_errors} consecutive failures.\n"
                      f"** {err}\n"
                      f"** nothing retries here -- fix the cause and run it again.",
                      file=sys.stderr)
                break
            # Pace on whichever quota is slower. `tin` is what the last call actually
            # cost, so this self-corrects to the real prompt size instead of guessing.
            if gap and done < len(runs):
                wait = max(gap, 60.0 * tin / S.GEMINI_TPM if tin else 0.0)
                time.sleep(max(0.0, wait - (time.monotonic() - sent)))
    # Said out loud rather than left in the tape. A hosted run that quietly lost a
    # third of its calls to 429s scores like a model that could not answer them.
    print(f"\nwrote {out}", file=sys.stderr)
    if errs:
        print(f"** {errs} of {len(runs)} calls FAILED -- check `error` before scoring",
              file=sys.stderr)


if __name__ == "__main__":
    main()
