"""What is written down. Three stores, and they differ by who holds the pen.

    orders    mission control's, typed by the operator at nightfall. She cannot write it
    todos     her own items, added and struck. Wiped by `World.next_day`.
    memory    one paragraph, replaced whole. Hers, and it crosses the night.

**Orders need their own store rather than a corner of an existing one.** `next_day`
clears the message log and the todos, so anything typed at nightfall is gone by morning
unless it lives somewhere that survives -- and the only other such place is `memory`,
which `remember` replaces wholesale. Put orders there and she deletes mission control on
her next call. So it sits here, written only through `order()`, which no skill reaches.

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

`remember` replaces the whole doc rather than appending. Append-only means she can never
correct herself, and correction is the thing most worth watching: the outcrop she wrote
off that was never in the way. Settled in `prototype1/DESIGN.md` and not re-argued.

Pure state. The wording of every result lives in `skills.py` beside the other failure
codes, and the rendering in `sight.py` beside the rest of the view, so this file has no
opinion about either and does no I/O.
"""


class Notes:
    """One expedition's writing. It hangs off `World`, which is what gives it its
    lifetime: the memory survives a `next_day` for the same reason the map does."""

    def __init__(self):
        self.todos = []       # [text, struck], in the order written. Ids are 1-based.
        self.memory = ""
        self.orders = ""      # the operator's. Read-only to her, and it outlives the sol

    def new_day(self):
        """Nightfall. The list goes; the memory and the orders stay.

        Orders last until replaced rather than for a sol, so a run where the operator
        types nothing on sol 3 is one where sol 2's orders still stand -- which is what
        standing orders are. Clearing them would make silence mean "do nothing".
        """
        self.todos = []

    def order(self, text):
        """Mission control, replacing whatever stood before. The operator's door in.

        Deliberately not a skill and deliberately not `remember`: the one store she can
        read and cannot touch is the only place a standing instruction is safe from her
        own next rewrite.
        """
        self.orders = text.strip()

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
