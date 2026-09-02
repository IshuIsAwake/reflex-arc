"""Read a `probe_map.py` tape back and score it. No model, no GPU -- just the numbers.

Separate from the probe so a run can be scored again without paying for it again.

Baselines are the point: an answer is not evidence until it beats guessing, and "she
named four fog regions and all four were real" dissolves once the baseline is computed.
Every qualitative question carries the probability a coin would have got it, with the
exact binomial tail printed beside the score.

Usage: `.venv/bin/python game/probe_read.py runs/probe-<stamp>/probe.jsonl`
"""

import json
import sys
from collections import defaultdict
from math import comb


def binom_tail(k, n, p):
    """P(X >= k) for X ~ Binomial(n, p). One-sided: we only care about beating chance."""
    if n == 0:
        return 1.0
    return sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))


def fisher(a, b, c, d):
    """Two-sided Fisher exact on [[a,b],[c,d]]. Used for blocked vs unblocked."""
    n = a + b + c + d
    if n == 0:
        return 1.0
    def pr(x):
        return (comb(a + b, x) * comb(c + d, a + c - x)) / comb(n, a + c)
    lo = max(0, a + c - (c + d))
    hi = min(a + b, a + c)
    obs = pr(a)
    return min(1.0, sum(pr(x) for x in range(lo, hi + 1) if pr(x) <= obs * 1.000001))


def pct(k, n):
    return f"{k:>3}/{n:<3} {k / n:5.0%}" if n else "   --      "


def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


# The arms present are read off the tape rather than assumed. A hosted run is
# unblocked-only (the blocked paragraph is an artefact of the prompt gemma was given),
# and hardcoding two columns divided by zero on the cost table.
def arms_in(rows):
    return sorted({r["arm"] for r in rows}, reverse=True)   # unblocked first


def table(rows, title, keyfn, baseline=None):
    arms = arms_in(rows)
    print(f"\n{title}")
    print(f"  {'':22s} " + "  ".join(f"{a:>13s}" for a in arms)
          + f"   {'base':>5s}  {'p':>8s}")
    for key in sorted({keyfn(r) for r in rows}):
        sel = [r for r in rows if keyfn(r) == key]
        line = f"  {str(key):22s}"
        cell = {}
        for arm in arms:
            got = [r for r in sel if r["arm"] == arm]
            ok = sum(bool(r["correct"]) for r in got)
            cell[arm] = (ok, len(got))
            line += f" {pct(ok, len(got)):>13s} "
        base = baseline(sel) if baseline else None
        if base is not None:
            k, n = cell[arms[0]]
            line += f"  {base:5.0%}  {binom_tail(k, n, base):8.3g}"
        elif len(arms) == 2:
            (a, na), (c, nc) = cell[arms[0]], cell[arms[1]]
            line += f"  {'':5s}  {fisher(a, na - a, c, nc - c):8.3g}"
        print(line)


def main():
    rows = load(sys.argv[1])
    rows = [r for r in rows if not r["error"]]
    dflt = [r for r in rows if r["temp"] is None]
    greedy = [r for r in rows if r["temp"] == 0.0]

    # Named at the top, because the reason this scorer exists is to put two tapes beside
    # each other and a tape whose model has to be guessed at gets compared to the wrong one.
    print(f"model: {'/'.join(sorted({str(r.get('model', 'gemma4:e4b')) for r in rows}))}"
          f"   thinking: {'/'.join(sorted({str(r.get('thinking', False)) for r in rows}))}")
    print(f"{len(rows)} answers  |  {len(greedy)} at temp 0, {len(dflt)} at model default")
    print(f"worlds: {sorted({r['world'] for r in rows})}   "
          f"questions: {len({(r['world'], r['kind'], r['q']) for r in rows})}   "
          f"arms: {', '.join(arms_in(rows))}")
    # Two tapes are only a replication if this line matches. Older tapes predate the
    # field and say so rather than pretending to agree with anything.
    shas = sorted({r.get("system_sha", "unrecorded") for r in rows})
    print(f"system prompt: {', '.join(shas)}"
          + ("   ** unrecorded -- cannot be confirmed as the same prompt as another run"
             if "unrecorded" in shas else ""))

    for name, sel in (("MODEL DEFAULT TEMPERATURE", dflt), ("TEMP 0 (greedy)", greedy)):
        print(f"\n{'=' * 78}\n{name}  --  n={len(sel)}\n{'=' * 78}")
        table(sel, "by axis", lambda r: r["axis"])
        table([r for r in sel if r["axis"] == "quant"],
              "quantitative -- needs the grid indexed", lambda r: r["kind"])
        table([r for r in sel if r["axis"] == "qual"],
              "qualitative -- forced choice, vs its own baseline",
              lambda r: r["kind"],
              baseline=lambda s: sum(r["extra"]["baseline"] for r in s) / len(s))

        print("\n  how the answers failed")
        for arm in arms_in(sel):
            got = [r for r in sel if r["arm"] == arm]
            n = len(got) or 1
            print(f"    {arm:10s} n={len(got):<4d} "
                  f"no answer parsed {sum(r['correct'] is None for r in got) / n:4.0%}   "
                  f"refusal language {sum(r['refused'] for r in got) / n:4.0%}   "
                  f"wrote a call instead {sum(r.get('narrated') for r in got) / n:4.0%}")

        reg = [r for r in sel if r["kind"] == "region"]
        print("\n  the 30-cell boxes")
        for arm in arms_in(reg) if reg else ():
            got = [r for r in reg if r["arm"] == arm]
            ans = [r for r in got if r["parsed"] and len(r["parsed"]) == 3]
            uni = sum(bool(r["uniform"]) for r in got)
            err = [sum(abs(r["parsed"][k] - r["truth"][k]) for k in r["truth"]) / 2
                   for r in ans]
            clear = [r for r in ans if r["extra"]["clear"]]
            ghost = [r for r in clear if r["parsed"]["unseen"] > 0]
            print(f"    {arm:10s} exact {pct(sum(bool(r['correct']) for r in got), len(got))}"
                  f"   uniform fill {uni:>3}/{len(got):<3}"
                  f"   mean cells misplaced {sum(err) / len(err):5.1f}" if err else
                  f"    {arm:10s} no parseable answers")
            if clear:
                print(f"    {'':10s} fully-revealed boxes: claimed fog in "
                      f"{len(ghost)}/{len(clear)} of them")

    print(f"\n{'=' * 78}\ncost\n{'=' * 78}")
    for arm in arms_in(rows):
        got = [r for r in rows if r["arm"] == arm]
        print(f"  {arm:10s} {sum(r['seconds'] for r in got) / 60:5.1f} min   "
              f"{sum(r['tokens_out'] for r in got):>6} tokens out   "
              f"mean prompt {sum(r['tokens_in'] for r in got) // len(got)}")

    print("\nworst-case examples, unblocked, model default temperature:")
    bad = [r for r in dflt if r["arm"] == "unblocked" and r["correct"] is not True]
    seen = set()
    for r in bad:
        if r["kind"] in seen:
            continue
        seen.add(r["kind"])
        print(f"\n  [{r['kind']}] truth={r['truth'] if r['kind'] != 'biggest_fog' else '(in the largest blob)'}"
              f"  parsed={r['parsed']}")
        print(f"    Q {r['q'][:150]}")
        print(f"    A {r['said'][:250]!r}")


if __name__ == "__main__":
    main()
