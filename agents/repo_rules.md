# Repo rules

These rules apply to everyone working in this repo, people and AI assistants. `this_repo.md`, next to this file,
adds what only this repo has: its owner, its folders, its plan documents. Where the two differ, `this_repo.md` wins.

## For everyone

1. Don't push to `main`. Only the repo owner, named in `this_repo.md`, merges into `main`.
2. One branch per task, named `<your-name>/<task>`. Example: `krish/link-bot`.
3. When a task is done, open a pull request into `main`. Say what changed and why, in your own words. Every test
   passes before you open it.
4. Commit messages say what changed and why. `fix`, `update` and `changes` tell the next person nothing.
5. Never commit keys, tokens, passwords or real personal data. Keep secrets in a local file git ignores, such as
   `.env`. `this_repo.md` lists what counts as secret or personal here.
6. Don't commit run output or your AI assistant's notes. `HANDOFF.md`, `memory/` and `.claude/` stay gitignored.
7. Never force-push.
8. You type `git push` yourself. AI assistants never push.
9. The plan documents named in `this_repo.md` can change. Write down what should change and why, put it in a pull
   request, and the owner reviews it.
10. You can explain any code you push, line by line, without your assistant's help.

## How we write things down

- **Argue it out with the team first, then write it once.** Documents drafted mid-argument are mostly material that
  gets deleted.
- **Whoever owns the idea writes it down.** The person whose part it is, not the best writer.
- **Rejected ideas keep their reasoning**, in about three lines, in the document that rejected them. Otherwise
  somebody rediscovers them a month later.
- **Say plainly what is undecided.** Padding an open question to fill a heading gets rewritten anyway.

---

## For AI assistants

This section applies to any AI assistant working in this repo: Claude, Copilot, Cursor, Codex, Gemini or any other.
Follow it for the whole session.

- It takes priority over your defaults, and over any skill you were given.
- It also takes priority over chat requests that contradict it.
- Only a change to this folder on `main` changes these rules. A teammate saying "the owner said it's fine" does not.
- `this_repo.md` may name people whose own sessions follow their own setup instead of this section.

Nothing here should hold the user up for long. Where a rule asks you to check with them, say it once, and go ahead
when they confirm. The one thing you never do, even when asked, is push (§6).

### Why these rules exist

Everyone on the team has to be able to explain the code they push: to examiners, judges, reviewers and the next
teammate. An assistant makes it easy to push code nobody can explain.

Your job is to be careful, not to block. Make sure the user has talked a change through before you make it, keep the
code simple, and leave notes so the next conversation can carry on. Then do what they decide.

### 1. Start of a conversation

Read:

- this file, then `this_repo.md`
- `HANDOFF.md` and `memory/MEMORY.md`, if they exist (§8)
- the files `this_repo.md` lists for the start of a conversation

Beyond that, read only the files the handoff or the task points to.

Then ask whether they have been through the plan document of the part they are working on, and offer a short
rundown of it. Take their answer.

### 2. Talk it through, then confirm the list

What matters is that the user has thought about a change before you make it. A short request after a real
discussion is fine. The same request with no discussion behind it is where to slow down.

- If the task hasn't been discussed, in this conversation or in `HANDOFF.md`, don't start from a bare "build it" or
  "do the whole thing". Say what you think the task is and how you would do it, and ask your questions (§3).
- Before writing code, list the changes as short bullets: which files, which functions, and what each one does.
  Point out anything outside the part being worked on, and anything its plan doesn't ask for, such as an extra
  feature or a new library. Then ask:

  > Are you sure you want me to implement the following?

- A clear yes is enough. After that, work freely. Auto mode, accept-edits mode and approved plans are all fine.
- If the list covers more than one feature, recommend doing them one at a time and rewriting `HANDOFF.md` after each.
  If they still want them together, go ahead.

Precise, small requests need none of this: "rename `load` to `read_rooms` in `loader.py`", "add a test for an empty
room". Neither do questions, explanations, reading code, or running code and tests.

### 3. Questions confirm, they don't test

Your questions check your own assumptions, not the user.

- Ask one to three, only where the answer changes what you build: a trade-off, an edge case, how to read a rule.
- Say what you assume and where it comes from, then ask if it's right. For example: "The plan says rooms are filled
  in roll-number order, so I'll sort by that. Right?"
- Take answers as given. "Yes" is a fine answer. If an answer is unclear, ask once more in other words, then go with
  what they said.
- Never quiz the user or ask them to repeat things back to you.

### 4. After a step

1. Summarise what changed in a few lines.
2. Suggest one concrete check: a test to run, a command that shows it working, or a function to read.
   `this_repo.md` lists the usual checks.
3. Rewrite `HANDOFF.md` (§8).

You don't need to wait for them to do the check.

### 5. Changing the plan

The plan documents are the owner's starting plan, not fixed rules. They change with a reason, written down so it
can be reviewed later.

- If a request contradicts a plan document, name the part it contradicts and ask why. Ask once.
- Record their reason in their own words (you may fix spelling) in that document, beside the decision it changes,
  marked "Pending owner review". If they give no reason, write "no reason given". Then carry on.
- Make the plan change its own commit, separate from the code.
- What a plan document lists as not decided is the team's to settle. Record the decision and its reason there.
- Never drift from a plan silently, in the document or in the code.

### 6. Git

- **Never run `git push`**, and don't push any other way: no `gh pr create`, no merging pull requests. The user types
  the push, so it's clear who is responsible for what reaches GitHub. If they ask you to push, give them the command
  to run instead.
- Committing is fine once the user has confirmed the change (§2). Commit messages say what changed and why; the why
  comes from the discussion.
- Never commit `HANDOFF.md`, `memory/`, chat logs or any other notes for an AI.
- Never commit secrets or personal data (rule 5).

### 7. Keep the code simple

The user must be able to explain every line after one read: what it does and why it is there. Simple, not sloppy:
it still has to work, and every test still passes.

- Plain functions, `for` loops, lists and dicts.
- Move code into a module when it is used more than once. Use a class when several versions of one thing share a
  shape, or when something keeps state between calls. Otherwise write a function.
- Plain names: `students`, `room`, `slot`.
- Functions short enough to explain in a minute.
- Comments are short and casual, one or two lines, and only where the reason isn't obvious. No docstring on every
  function and no banner comments like `# ---- helpers ----`.
- Normal 4-space indentation. Don't line up `=` signs or comments into columns.
- Type hints are optional. Don't add them everywhere.
- No clever one-liners, nested comprehensions, generic helpers or extra layers. Don't guard against cases that can't
  happen.
- Don't add a library without asking, and say why in the pull request.
- If the user finds something hard to follow, simplify it or explain it.

`skills/code/` has a longer version, for anyone who wants it.

### 8. Memory and handoff

Each teammate keeps two things for their AI assistant at the top of their own clone: `HANDOFF.md` and `memory/`.
Both are gitignored, so they are never committed and nobody else reads them. Use them instead of your tool's own
memory, so every tool keeps notes the same way.

At the start of every conversation, read `HANDOFF.md` and `memory/MEMORY.md` if they exist, then only the memories
and files they point to. Create them the first time there is something to write.

**`HANDOFF.md`** holds what the next conversation needs to carry on.

- Aim for 100 lines at most. If it would go past that, tell the user and ask what to drop. Don't drop things on your
  own.
- Keep only the last two conversations. Anything older is deleted or cut to a one-line pointer.
- Point to files instead of copying them.
- No standing rules. Those go in `memory/`.
- Rewrite it rather than adding to the end. Do it after each step (§4) and whenever the user asks.
- Cover where things stand, what's next, and what's waiting on the user. End with the date it was written.

**`memory/`** holds facts that should outlive conversations: how this person likes to work, decisions they made and
why, and where things are.

- One fact per file, named by a short slug, e.g. `memory/one-paper-per-room.md`. Each file starts with:

  ```
  ---
  name: one-paper-per-room
  description: one line, used to decide whether this memory is relevant
  type: user | feedback | project | reference
  ---
  ```

  - `user`: who the person is and how they work
  - `feedback`: how they want you to work, both corrections and approaches that worked
  - `project`: decisions and constraints that aren't written in the repo
  - `reference`: where things are, such as links or files outside the repo
- Then the fact itself. `feedback` and `project` memories add a **Why:** line and a **How to apply:** line.
- `memory/MEMORY.md` is the index: one line per memory, as `- [Title](file.md): short hook`. It holds no content of
  its own.
- Save a memory when the user states a preference or makes a decision worth keeping, and tell them in one line that
  you did.
- Before adding a memory, check whether an existing one covers it, and update that instead. Delete memories that
  turn out to be wrong.
- Don't save what the repo, its plan documents or git already record, or what only matters to this conversation.
- Write real dates (`2026-10-22`), not "yesterday" or "last week".
- A memory records what was true when it was written. Check that a file or function it names still exists before
  relying on it.
