# Repo rules
Ishu is the only exemption ; )

## Git

- **Never push to `main` directly.** Branch, then open a pull reques. If
  it breaks, we want to know whose branch it came from.
- **Commit messages say what changed and why.** A sentence someone can read in a log six weeks from
  now. `fix`, `update`, `changes` and `asdf` all tell the next person nothing. No prefixes or
  ceremony needed — look at `git log` for the shape.
- **Do not commit what a model wrote for you.** `HANDOFF.md`, `.claude/`, chat transcripts, run
  logs, tapes. All gitignored already; keep them that way. Everyone keeps their own handoff and
  nobody has to read anybody else's.

## Context is a budget, so spend it

Every file a model reads costs you room to think in. Most of what makes these tools stupid is
feeding them too much.

- **Your `HANDOFF.md` is for the next conversation, not a diary.** Hard cap it — the number here is
  100 lines — and when you hit the cap, delete before you add. Pointers to files beat copies of
  them.
- **Point a model at the files it actually needs.** Not the repo. Not the whole directory. If you
  cannot say why a file is open, close it. Models these days are smart enough about - asking them to read the handoff and only reading files required would achieve this.


## Ideas

- **Argue it out in person first, then write it once.** Documents drafted mid-argument are mostly
  material that gets deleted. Reach the conclusion out loud, check it, then write.
- **Whoever owns the idea writes it down.** Not the person who is best at writing — the person whose
  part it is. That is how it stays yours.
- **Rejected ideas keep their reasoning**, in the document that rejected them, in about three lines.
  Otherwise somebody rediscovers them in November.
- **Say plainly what is undecided.** Padding an open question to fill a heading fools nobody and
  gets rewritten anyway.
