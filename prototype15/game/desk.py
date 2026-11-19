"""Mission control's commands: what the desk types in her chat (/order, /next, ...) and the
terminal's `place` and `comms`. No pygame here."""

import settings
import sight

CHAT_HELP = [
    "words            at dawn and night, talk to her. By day, one urgent message",
    "/next [WORDS]    move on: dawn to day, dusk to night, night to the next sol, or "
    "close a radio line. WORDS go to her with whatever comes next",
    "/order TEXT      post an order on her board. /orders shows it",
    "/retract N       take order N down. /orders clear takes them all",
    "/status          the status line, as she reads it",
    "Your terminal (T) has the rest: comms, sols, place -- type help there."]


def by_day(pilot):
    """Whether what the desk types goes to her as the day's one urgent message."""
    return pilot.live and pilot.phase == "day" and pilot.wait != "radio"


def chat_line(world, pilot, conv, text):
    """One line typed in her chat. Returns the pane's lines: why it did not go, or what it did."""
    if not text.startswith("/"):
        if by_day(pilot):
            why = pilot.send_urgent(conv, world, text)
            return [why or "urgent sent -- she reads it after the call in hand"]
        why = pilot.say(conv, world, text)
        if why:
            return [why]
        return []
    word, _, rest = text.partition(" ")
    verb = word[1:].lower()
    if verb == "help":
        return CHAT_HELP
    if verb == "status":
        return [sight.status_line(world)]
    if verb in ("order", "orders", "retract"):
        return [board(world, pilot, conv, verb, rest)]
    if verb == "next":
        why = pilot.next(rest)
        if why:
            return [why]
        return []
    return [f"no such command: {word} -- /help lists them"]


def show_board(notes):
    if not notes.orders:
        return "the board is empty"
    listed = []
    for i, text in enumerate(notes.orders, 1):
        listed.append(f"{i}. {text}")
    return "the board -- " + "   ".join(listed)


def board(world, pilot, conv, verb, rest):
    """/order, /orders and /retract: the orders board. Returns the line for the pane. Every
    change is told to her (by day as the urgent message) and recorded, so a replay can post it
    again."""
    notes = world.notes
    rest = rest.strip()
    if verb == "orders" and not rest:
        return show_board(notes)
    if by_day(pilot):
        why = pilot.urgent_why_not(world)
    else:
        why = pilot.why_not()
    if why:
        return why
    if not by_day(pilot) and conv.busy:
        return "she is still talking -- wait until she has finished"
    if verb == "orders" and rest.lower() != "clear":
        return "/order <text> posts one order; /orders shows the board"
    if verb == "order" and not rest:
        return "/order needs the order -- e.g.  /order survey the north-west first"
    if verb == "order" and len(rest) > settings.ORDERS_CHARS:
        return (f"order refused -- {len(rest)} characters, and the cap is "
                f"{settings.ORDERS_CHARS}. Say it shorter.")

    if verb == "orders":
        notes.clear_orders()
        world.record("orders_cleared")
        told = "Mission control has cleared the board"
        done = "the board is cleared"
    elif verb == "order":
        n = notes.order(rest)
        world.record("order", n=n, text=rest)
        told = f"Mission control posted order {n}: {rest}"
        done = f"order {n} posted"
    else:
        n = 0
        if rest.isdigit():
            n = int(rest)
        text = notes.retract(n)
        if text is None:
            return f"there is no order {rest or '?'} -- the board has {len(notes.orders)}"
        world.record("retract", n=n, text=text)
        told = f"Mission control took down order {n}: {text}"
        done = f"order {n} retracted: {text}"
    told += ". The board in your view is current."
    if by_day(pilot):
        pilot.send_urgent(conv, world, told)
        return f"{done} -- sent to her as the urgent message"
    pilot.say(conv, world, told)
    return f"{done} -- she is told"


def is_whole_number(text):
    return text.lstrip("-").isdigit()


def place(world, text):
    """The terminal's `place X Y [high|medium|low] [cost]`: an objective on mapped ground, or
    `place X Y interest COST TEXT`: a hidden interest. Returns (refusal, None) or (None, done)."""
    words = text.split()
    if len(words) >= 3 and words[2].lower() == "interest":
        return place_interest(world, words)
    numbers = [word for word in words if is_whole_number(word)]
    if len(numbers) < 2:
        return "place needs a cell -- try  place 21 8 high 40", None
    cell = (int(numbers[0]), int(numbers[1]))
    priority = "medium"
    for word in words:
        if word.lower() in ("high", "medium", "low"):
            priority = word
            break
    cost = 30
    if len(numbers) > 2:
        cost = int(numbers[2])
    if cost <= 0:
        return f"{cost} steps of work is not work", None
    o, why = world.place_objective(cell, priority.lower(), cost)
    if not o:
        return why, None
    return None, (f"placed objective {o.glyph} at ({cell[0]},{cell[1]}), {o.priority} "
                  f"priority, {o.cost} steps of work -- it is in her view")


def place_interest(world, words):
    if (len(words) < 5 or not is_whole_number(words[0]) or not is_whole_number(words[1])
            or not words[3].isdigit()):
        return "try  place 12 8 interest 30 a ring of dark glassy stones", None
    cell = (int(words[0]), int(words[1]))
    found, why = world.place_interest(cell, " ".join(words[4:]), int(words[3]))
    if not found:
        return why, None
    return None, f"interest hidden at ({found.cell[0]},{found.cell[1]}), {found.cost} steps"


def set_comms(rest):
    """The terminal's `comms on|off`, the same switch as C."""
    if rest.strip().lower() not in ("on", "off"):
        if settings.COMMS:
            return "comms are on -- comms on, or comms off", None
        return "comms are off -- comms on, or comms off", None
    settings.COMMS = rest.strip().lower() == "on"
    if settings.COMMS:
        return None, "comms on: someone is at the desk"
    return None, "comms off: nobody is"
