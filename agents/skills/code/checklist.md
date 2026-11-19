# Code checklist

Check new or changed code against `SKILL.md` and the repo's own rules. Report problems; don't fix them while
checking.

## What to read
1. The files you were given. If none were named, the uncommitted changes: `git status`, `git diff`, and any new
   untracked files. Check the changed lines and enough around them to judge them.
2. The repo's rules (`agents/repo_rules.md`, `agents/this_repo.md`) and any instructions file they point to. Where
   they differ from `SKILL.md`, the repo wins.
3. `SKILL.md`, and `notebooks.md` for any notebook.

## What to ask, in this order
1. Could the user explain every line after one read? Flag tricks, dense lines, maths with no formula in a comment,
   and names that hide what a thing is.
2. Is the layout right? Logic in a notebook that belongs in a module, code copied instead of imported, a class with
   no reason, a function doing two jobs.
3. Is anything there that shouldn't be? Dead code, unused options, guards for cases that can't happen, a new library.
4. Comments: a missing reason or formula where a line isn't obvious, comments that repeat the code or tell history,
   em dashes, banner comments.
5. Notebooks: a number in markdown that no output above shows, more than one plot call in a cell, a missing summary
   or `---`.

## Report
- Group by file and keep the order above. One line per problem: `path:line`, what is wrong, then the plain version
  (as code if it is short).
- Mark a judgment call as one, and say why.
- End with the number of problems, or "Nothing found". No praise and no summary of what the code does.
