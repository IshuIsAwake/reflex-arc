# agents/

**`repo_rules.md` and `this_repo.md` apply to everyone working in this repo, people and AI assistants.**
**Everything in `skills/` is optional. Use a skill only if you want to, and change it as you like.**

## What is here

| File | What it is for |
|---|---|
| `repo_rules.md` | The rules every repo with this folder shares: git, talking a change through before it is built, simple code, and how an assistant keeps notes between conversations |
| `this_repo.md` | What only this repo has: its owner, the files to read first, its plan documents, what never gets committed |
| `skills/` | Optional instructions for an AI assistant, one folder per job |
| `skills/code/` | Writing code you can explain: a plan first, modules, plain functions, comments that give the reason. Comes with a checklist and example code |
| `skills/doc/` | Writing documents a reader who isn't technical can follow: plain words, every claim with its number, no filler. Comes with a checklist and an example report |
| `skills/deck/` | Building slide decks: the idea before the demo, little text, real proof, a look of its own for each deck. Comes with a checklist and three example decks |

## Why this exists

An AI assistant makes it easy to push code nobody on the team can explain, and that shows the moment an examiner or
a reviewer asks about it. The rules keep each person in charge of what their assistant writes: talk it through
first, keep it simple, and leave notes for the next conversation.

The skills are the instructions this folder's author uses with their own assistant, made general so anyone can
reuse them. They are one person's habits, not the way things must be done here.

## How to use it

- **The rules:** nothing to do. `AGENTS.md` and `CLAUDE.md` at the top of the repo point every assistant here.
- **A skill:** copy its folder into your assistant's skills folder. For Claude Code that is `~/.claude/skills/`. For
  other tools, look up where they keep skills or custom instructions, or paste the `SKILL.md` text into your own
  instructions. Then call it by name, like `/code`.
- **Changing a skill:** a skill is a starting point. When a point gets in your way, tell your assistant to drop or
  change it, or edit your own copy. The rules are different: they change only through a pull request to this folder
  on `main`.

## Where it comes from

This folder is copied from a master repo. `README.md`, `repo_rules.md` and `skills/` are changed in the master first
and copied out from there. `this_repo.md` belongs to this repo and is never overwritten by the master.
