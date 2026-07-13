import pytest
from semiskill.spine.states import EventClass, next_state, is_terminal


def test_happy_path_transitions():
    s = EventClass.CAPTURED
    seq = [s]
    while not is_terminal(s):
        s = next_state(s)
        seq.append(s)
    assert seq == [EventClass.CAPTURED, EventClass.ANALYZED, EventClass.PROPOSED,
                   EventClass.EXECUTED, EventClass.OBSERVED]


def test_cannot_advance_past_terminal():
    with pytest.raises(ValueError):
        next_state(EventClass.OBSERVED)
