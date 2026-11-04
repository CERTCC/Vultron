#!/usr/bin/env python
#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University


"""CS event application and causal history validity (CSB-17).

A history is the order in which the six events occurred; it is valid when
it replays through :func:`is_valid_cs_transition` from ``CS.vfdpxa``.
Decision: ADR-0060.
"""

from collections.abc import Iterable, Sequence

from vultron.core.states.cs import (
    CS,
)
from vultron.core.states.cs_invariants.events import (
    CS_EVENTS,
    CSEvent,
)
from vultron.core.states.cs_invariants.transitions import (
    cs_transition_event,
    is_valid_cs_transition,
    next_cs_states,
    required_next_cs_events,
)
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronValidationError,
)


def _as_cs_event(value: CSEvent | str) -> CSEvent:
    """Coerce *value* to a `CSEvent`.

    `CSEvent` is a `StrEnum`, so the single-letter strings of the legacy
    string-pattern API (``"V"``, ``"F"``, ...) are accepted.  This keeps the
    bool-returning predicates total: callers migrating from
    `case_states.validations` naturally pass strings, and a validator must
    answer their question rather than raise on the input type.

    Raises:
        VultronValidationError: if *value* is not a CS event.
    """
    try:
        return CSEvent(value)
    except ValueError as exc:
        raise VultronValidationError(
            f"CS history: {value!r} is not a CS event; expected one of"
            f" {[e.value for e in CS_EVENTS]}."
        ) from exc
    except TypeError as exc:
        raise VultronValidationError(
            f"CS history: {value!r} is not a CS event (unhashable or"
            " non-string type)."
        ) from exc


def apply_cs_event(state: CS, event: CSEvent | str) -> CS:
    """Return the state reached by applying *event* to *state*.

    Args:
        state: the current compound state
        event: the event to apply, as a `CSEvent` or its string value

    Returns:
        the resulting compound state

    Raises:
        VultronValidationError: if *event* is not a CS event.
        VultronInvalidStateTransitionError: if *event* cannot fire from
            *state* — because it already happened, because its dimension
            machine forbids it, or because *state* is ephemeral and requires
            a different event next.

    Examples::

        apply_cs_event(CS.vfdpxa, CSEvent.V)  # CS.Vfdpxa
    """
    event = _as_cs_event(event)

    for candidate in CS:
        # `!=`, not `is not`: CSEvent is a StrEnum, so a plain string compares
        # equal without being identical.
        if cs_transition_event(state, candidate) != event:
            continue
        if is_valid_cs_transition(state, candidate):
            return candidate
        break

    raise VultronInvalidStateTransitionError(
        f"CS: event '{event.value}' cannot fire from {state.name}:"
        f" {_why_event_blocked(state, event)}."
    )


def _why_event_blocked(state: CS, event: CSEvent) -> str:
    """Explain why *event* cannot fire from *state*.

    Only called on the failure path of `apply_cs_event`, where at least one of
    three things is true: the event already happened, the state is ephemeral
    and demands a different event, or the event's dimension prerequisite is
    unmet (F before V, D before F).

    More than one can hold at once — e.g. ``F`` from ``vfdpXa`` is blocked both
    by the ``pX`` ephemeral rule and by ``V`` not having occurred.  The checks
    run in order of proximity and report the first that applies, so the message
    names the constraint the caller must satisfy first rather than every
    constraint outstanding.
    """
    if state.name[CS_EVENTS.index(event)].isupper():
        return "it has already occurred"

    required = required_next_cs_events(state)
    if required:
        return (
            f"{state.name} is ephemeral and requires event(s)"
            f" {sorted(e.value for e in required)} next"
        )

    return "its dimension's prerequisite events have not occurred"


def _ensure_distinct_events(events: Sequence[CSEvent]) -> None:
    seen: set[CSEvent] = set()
    for event in events:
        if event in seen:
            raise VultronValidationError(
                f"CS history: event '{event.value}' occurs more than once;"
                " CS events are irreversible and happen at most once."
            )
        seen.add(event)


def replay_cs_history(
    events: Iterable[CSEvent | str], *, start: CS = CS.vfdpxa
) -> CS:
    """Replay *events* from *start* and return the resulting state.

    This is the causal check over a whole trajectory: each event must be
    legal given every event that preceded it.

    Args:
        events: the ordered CS events to apply, as `CSEvent` members or their
            string values (so ``"VFDPXA"`` and ``list(CSEvent)`` both work)
        start: the state to replay from, default `CS.vfdpxa`

    Returns:
        the compound state after the last event

    Raises:
        VultronValidationError: if an event repeats or is not a CS event.
        VultronInvalidStateTransitionError: if an event cannot fire at its
            position in the sequence.

    Examples::

        replay_cs_history([CSEvent.V, CSEvent.F])  # CS.VFdpxa
        replay_cs_history("VF")                    # CS.VFdpxa
    """
    sequence = [_as_cs_event(event) for event in events]
    _ensure_distinct_events(sequence)

    state = start
    for event in sequence:
        state = apply_cs_event(state, event)
    return state


def is_valid_cs_history_prefix(
    events: Sequence[CSEvent | str], *, start: CS = CS.vfdpxa
) -> bool:
    """Return True if *events* is a legal (possibly incomplete) trajectory.

    Use this on real case histories, which are usually still in progress.
    An empty sequence is trivially valid.  Events may be `CSEvent` members or
    their string values.  Anything that is not a CS event makes the sequence
    invalid rather than raising — this is a predicate, so it always answers.

    Note that a prefix ending in an ephemeral state is accepted: the
    ephemeral rules constrain what may come *next*, and nothing has come
    next yet.

    Examples::

        is_valid_cs_history_prefix([CSEvent.V, CSEvent.F])          # True
        is_valid_cs_history_prefix([CSEvent.F])                     # False
        is_valid_cs_history_prefix([CSEvent.X])                     # True  (pX)
        is_valid_cs_history_prefix([CSEvent.X, CSEvent.A])          # False
        is_valid_cs_history_prefix("VF")                            # True
    """
    try:
        replay_cs_history(events, start=start)
    except (VultronValidationError, VultronInvalidStateTransitionError):
        return False
    return True


def is_valid_cs_history(events: Sequence[CSEvent | str]) -> bool:
    """Return True if *events* is a complete, legal case history.

    A complete history contains all six events exactly once and reaches
    `CS.VFDPXA`.  Equivalent to the ordering rules ``V ≺ F ≺ D``,
    ``P ≺ X`` or ``XP`` adjacent, and ``V ≺ P`` or ``PV`` adjacent.

    Accepts the string form of the legacy `case_states.validations` API as
    well as `CSEvent` members.

    Examples::

        is_valid_cs_history(list(CSEvent))                    # True  (VFDPXA)
        is_valid_cs_history("VFDPXA")                         # True
        is_valid_cs_history([CSEvent.F, CSEvent.V, ...])      # False (F before V)
    """
    if len(events) != len(CS_EVENTS):
        return False
    if set(events) != set(CS_EVENTS):
        return False
    return is_valid_cs_history_prefix(events)


def ensure_valid_cs_history(events: Sequence[CSEvent | str]) -> None:
    """Raise unless *events* is a complete, legal case history.

    Raises:
        VultronValidationError: if the history is incomplete, contains a
            value that is not a CS event, or its events are not a
            permutation of the six CS events.
        VultronInvalidStateTransitionError: if the ordering is causally
            impossible.
    """
    sequence = [_as_cs_event(event) for event in events]
    _ensure_distinct_events(sequence)

    missing = sorted(e.value for e in set(CS_EVENTS) - set(sequence))
    if missing:
        raise VultronValidationError(
            f"CS history: incomplete, missing event(s) {missing}."
        )

    replay_cs_history(sequence)


def valid_cs_histories() -> tuple[tuple[CSEvent, ...], ...]:
    """Return every complete, legal case history.

    There are 70 of them.  Ordering is deterministic (depth-first over `CS`
    member order) so callers may rely on it in tests.

    Examples::

        len(valid_cs_histories())  # 70
    """
    histories: list[tuple[CSEvent, ...]] = []

    def walk(state: CS, acc: tuple[CSEvent, ...]) -> None:
        if state is CS.VFDPXA:
            histories.append(acc)
            return
        for candidate in next_cs_states(state):
            event = cs_transition_event(state, candidate)
            assert event is not None  # guaranteed by is_valid_cs_transition
            walk(candidate, (*acc, event))

    walk(CS.vfdpxa, ())
    return tuple(histories)
