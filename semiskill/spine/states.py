from enum import IntEnum


class EventClass(IntEnum):
    CAPTURED = 1
    ANALYZED = 2
    PROPOSED = 3
    EXECUTED = 4
    OBSERVED = 5


def is_terminal(state: EventClass) -> bool:
    return state == EventClass.OBSERVED


def next_state(state: EventClass) -> EventClass:
    if is_terminal(state):
        raise ValueError("OBSERVED is terminal; the loop is closed")
    return EventClass(state + 1)
