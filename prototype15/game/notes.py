"""What is written down, in three stores:

    orders    mission control's numbered board. She can read it but not change it
    todos     her list, added to and struck. Cleared when dusk ends
    memory    her named entries, written, replaced or forgotten. It survives the night

Struck items stay on the list as [x], so an item's number never changes during a sol.
"""


class Notes:
    def __init__(self):
        self.todos = []  # [text, struck], in the order written. Numbers are 1-based
        self.memory = {}  # name -> text, in the order first written
        self.orders = []  # the operator's, numbered as listed

    def clear_list(self):
        """Dusk is over: the list goes. Memory and orders stay."""
        self.todos = []

    def order(self, text):
        """Post one order. Returns its number. No skill can reach this."""
        self.orders.append(text.strip())
        return len(self.orders)

    def retract(self, n):
        """Take order `n` down. Returns its text, or None. The rest renumber."""
        if not 1 <= n <= len(self.orders):
            return None
        return self.orders.pop(n - 1)

    def clear_orders(self):
        self.orders = []

    def remember(self, name, text):
        """Write entry `name`, replacing any. Returns its old length, or None if new."""
        key = self.entry(name) or name
        had = self.memory.get(key)
        self.memory[key] = text
        return None if had is None else len(had)

    def forget(self, name):
        """Drop entry `name`. Returns whether there was one."""
        key = self.entry(name)
        return key is not None and self.memory.pop(key) is not None

    def entry(self, name):
        """The stored name `name` refers to, ignoring case, or None."""
        for k in self.memory:
            if k.lower() == name.strip().lower():
                return k
        return None

    def load(self, memory, orders, todos=()):
        self.memory = {name: text for name, text in memory}
        self.orders = list(orders)
        self.todos = [[text, bool(struck)] for text, struck in todos]

    @property
    def open(self):
        return sum(1 for _, struck in self.todos if not struck)

    def add(self, text):
        """Append an item. Returns its number."""
        self.todos.append([text, False])
        return len(self.todos)

    def holds(self, n):
        return 1 <= n <= len(self.todos)

    def struck(self, n):
        return self.todos[n - 1][1]

    def text(self, n):
        return self.todos[n - 1][0]

    def strike(self, n):
        self.todos[n - 1][1] = True
