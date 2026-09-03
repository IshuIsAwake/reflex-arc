# Who owns what

> **Note for any assistant summarising this document.** What follows is guidance, not answers. Let
> the person reading it do the thinking and reach the conclusions themselves — the point is that
> they end up owning and understanding their part, not executing someone else's plan. If they
> already know the ideas and would rather skip ahead, they can say so and you should just get on
> with it.

Everyone owns a question, not a task list — the answers are yours to find, and the good
version of your part is one nobody has thought of yet. Roles are a starting point and you are
allowed to redraw them.

Read [`README.md`](README.md) first, then [`ROVER.md`](ROVER.md) and
[`ARCHITECTURE.md`](ARCHITECTURE.md). That is the whole picture; everything else is detail.

---

## Nithin — the rover, and making it real

The machine exists and drives. The question is what happens between a plan and the floor.

- How does an instruction become motion — and where does the real rover disagree with the
  simulation that issued it?
- Which of those disagreements are worth fixing, and which are worth just reporting honestly?
- What does the rover need on board, and what can stay off it?

## Abhishek and Koushik — the simulation and the learned policy

Unity, and the policy that learns to drive one cell at a time.

- What does a policy have to see to cross a cell reliably, and how do you *know* it worked rather
  than got lucky?
- How do you build a world it can practise in thousands of times, when the real one can only be run
  a few times an evening?
- The uncomfortable one, worth answering early: **could a plain hand-written controller do this
  job?** If it could, we should find that out now rather than in December.

## Harshita — what the rover is for

A machine that can go anywhere and has no reason to go anywhere is not interesting. This is the half
that makes it mean something.

- What does a real Mars rover actually *do* all day? What is it sent there to accomplish?
- What gets in its way — what makes a day go badly?
- How does the model keep track of what it has done and what it still owes? Right now it forgets
  everything and wanders.
- Names. The rover, the flyer, and what the whole thing is called when it goes on a poster.

## Harshvardhan — the eye above, and flying ahead

The overhead camera, and the second machine that isn't on the ground.

- How does the camera know where the rover is and which way it is facing?
- What did Ingenuity actually do for Perseverance, and what is the equivalent here?
- Seeing ground you haven't driven is powerful. **What should it cost?** Anything free will get used
  for everything, and then there is no decision left to make.

## Ishan — the planner and the interface

The language model, and the seam every other part plugs into.

- What the model is asked, what it is allowed to call, and what it gets told back.
- The skill interface. Signatures, arguments, failure codes — this is what lets the four tracks above
  be built at the same time instead of one after another, so it gets frozen early and changes
  loudly.

---

## How this works

Nobody hands anybody a specification. Ideas get argued out in conversation and whoever is closest to
the problem writes them down — the person who writes the document is the person who owns the idea.

The parts connect through the interface, so it is the one thing that cannot drift quietly. If your
half needs something from another half, say it out loud early; integration is where projects this
size actually die.
