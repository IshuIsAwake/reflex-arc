"""What is written down. Three stores, and they differ by who holds the pen.

    orders    mission control's numbered board, posted and retracted one at a time from
              her chat between sols. She cannot write it
    todos     her own items, added and struck. Cleared when dusk ends, by
              `World.evening`, so what she writes at night is the next day's list.
    memory    her named entries, each written or replaced whole, or forgotten. Hers, and
              it crosses the night.

**Orders need their own store rather than a corner of an existing one.** `next_day`
clears the message log, so anything typed at nightfall is gone by morning unless it
lives somewhere that survives. The two that do are hers: she strikes the list, and
`remember` replaces memory wholesale. Put orders in either and she deletes mission
control on her next call. So it sits here, written only through `order()`, which no skill reaches.

This is the write path. Everything else in the prototype hands her facts and takes them
back; nothing she produced used to outlive her own turn, which makes the planner
structurally a lookup however good the view gets. `docs/course.md` §4.

**Neither store is for terrain.** The world already remembers the map, the formation ids
and which objectives are finished, and rebuilds all of it into the view every request. A
note that copies the map is a stale copy competing with a live one, which is the failure
`chat.cut_fabrication` exists to stop -- with the difference that this one would be
sanctioned. What belongs here is what the view will not say tomorrow: what she tried,
what she judged not worth it, and what she meant to do next.

Struck items stay on the list as `[x]` rather than being removed, so an id means the
same thing all sol. A list that renumbers underneath her is a list she cannot strike
from -- the same failure as a coordinate she has to count out of a grid.

`remember` replaces an entry rather than appending to it. Append-only means she can never
correct herself, and correction is the thing most worth watching: the outcrop she wrote
off that was never in the way. Settled in prototype 1 (`docs/findings.md`), not re-argued.
Entries rather than one paragraph because a whole-paragraph rewrite every night is where a
standing constraint gets dropped: an entry she does not touch survives untouched.

Pure state. The wording of every result lives in `skills.py` beside the other failure
codes, and the rendering in `sight.py` beside the rest of the view, so this file has no
opinion about either and does no I/O.
"""


class Notes:
    """One expedition's writing. It hangs off `World`, which is what gives it its
    lifetime: the memory survives a `next_day` for the same reason the map does."""

    def __init__(self):
        self.todos = []       # [text, struck], in the order written. Ids are 1-based.
        self.memory = {}      # name -> text, in the order first written
        self.orders = []      # the operator's, numbered as listed. Read-only to her

    def clear_list(self):
        """Dusk is over. The list goes; the memory and the orders stay.

        Cleared when dusk ends rather than at dawn, so a plan she makes when the desk
        talks with her at night is the list she wakes to. In the 14 Oct team run her
        night's "explore north, explore east" never reached the morning.

        Orders last until replaced rather than for a sol, so a run where the operator
        types nothing on sol 3 is one where sol 2's orders still stand -- which is what
        standing orders are. Clearing them would make silence mean "do nothing".
        """
        self.todos = []

    def order(self, text):
        """Post one order. Returns its number. The operator's door in.

        Deliberately not a skill and deliberately not `remember`: the one store she can
        read and cannot touch is the only place a standing instruction is safe from her
        own next rewrite.
        """
        self.orders.append(text.strip())
        return len(self.orders)

    def retract(self, n):
        """Take order `n` down. Returns its text, or None if there is no such order. The
        rest renumber: she reads the board whole every request and never cites a number."""
        if not 1 <= n <= len(self.orders):
            return None
        return self.orders.pop(n - 1)

    def clear_orders(self):
        self.orders = []

    def remember(self, name, text):
        """Write entry `name`, replacing it if there is one. Returns the length it had,
        or None if it is new. Names match whatever their case."""
        key = self.entry(name) or name
        had = self.memory.get(key)
        self.memory[key] = text
        return None if had is None else len(had)

    def forget(self, name):
        """Drop entry `name`. Returns whether there was one."""
        key = self.entry(name)
        return key is not None and self.memory.pop(key) is not None

    def entry(self, name):
        """The stored name `name` refers to, or None."""
        return next((k for k in self.memory if k.lower() == name.strip().lower()), None)

    def load(self, memory, orders, todos=()):
        """A saved night's notes. Nights kept before the list crossed the night have none."""
        self.memory = {name: text for name, text in memory}
        self.orders = list(orders)
        self.todos = [[text, bool(struck)] for text, struck in todos]

    @property
    def open(self):
        """How many items are still to do."""
        return sum(1 for _, struck in self.todos if not struck)

    def add(self, text):
        """Append an item. Returns its id, which then means that item all sol."""
        self.todos.append([text, False])
        return len(self.todos)

    def holds(self, n):
        """Is `n` an item on the list at all?"""
        return 1 <= n <= len(self.todos)

    def struck(self, n):
        return self.todos[n - 1][1]

    def text(self, n):
        return self.todos[n - 1][0]

    def strike(self, n):
        """Cross item `n` off. The caller has already checked it is there."""
        self.todos[n - 1][1] = True
