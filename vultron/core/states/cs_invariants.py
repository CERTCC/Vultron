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

"""CS-internal validity, transition, and history invariants.

This module expresses the Case State (CS) validity rules of the MPCVD
state-based model against the current enum models in
`vultron.core.states.cs` — `CS`, `CS_vfd`, `CS_pxa`, and the per-dimension
transition tables that back `VfdDimension` / `PxaDimension`.

Three rule families live here:

Compound state validity
    The 32 members of `CS` *are* the valid compound states.  The two
    impossible-combination rules of the formal model (`vF` — a fix ready
    while the vendor is unaware; `fD` — a fix deployed that was never ready)
    are enforced structurally by `CS_vfd` having only four members, so no
    runtime predicate is needed.  `test_cs_invariants.py` ratchets the enum
    against an independent derivation of the rule.

Transition validity (`is_valid_cs_transition`)
    A CS transition changes exactly one of the six dimensions, always from
    the not-yet-happened to the happened value, and must respect the two
    *ephemeral state* rules below.

Ephemeral states (`is_ephemeral_cs_state`, `required_next_cs_events`)
    Two compound states are transient in the formal model and constrain the
    very next event rather than being forbidden outright:

    - ``vP`` (public aware, vendor unaware) — the next event MUST be ``V``.
    - ``pX`` (exploit public, public unaware) — the next event MUST be ``P``.

History validity (`is_valid_cs_history`, `is_valid_cs_history_prefix`)
    A *history* is the order in which the six events occurred.  History
    validity is a **causal** property of a whole sequence, not a
    point-in-time or wall-clock one: it is what lets a consumer reject a
    reported case trajectory that no real case could have produced.

The complete-history ordering rules

- ``V ≺ F ≺ D``
- ``P ≺ X`` or ``P`` immediately follows ``X``
- ``V ≺ P`` or ``V`` immediately follows ``P``

are provably equivalent to replaying the sequence through
`is_valid_cs_transition` from `CS.vfdpxa`; both admit exactly the same 70
histories.  `test_cs_invariants.py` asserts that equivalence directly, so
the two formulations cannot drift apart.

Reference: Householder, A. D., and Spring, J.
*A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure
(MPCVD)*, CMU/SEI-2021-SR-021. <https://doi.org/10.1184/R1/16416771>

Spec: `specs/cs-behavior.yaml` CSB-17.  Decision: ADR-0060.
"""

from collections.abc import Iterable, Sequence
from enum import StrEnum

from vultron.core.states.cs import (
    CS,
    CS_pxa,
    CS_vfd,
    PXA_Trigger,
    VFD_Trigger,
    is_pxa_exploit_public,
    is_pxa_public_aware,
    is_valid_pxa_transition,
    is_valid_vfd_transition,
    is_vfd_vendor_aware,
)
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronValidationError,
)


class CSEvent(StrEnum):
    """The six CS transition events, in canonical dimension order.

    Each event flips exactly one CS dimension from its not-yet-happened value
    to its happened value.  Events are irreversible and occur at most once in
    a case history.
    """

    V = "V"
    """Vendor becomes aware."""
    F = "F"
    """Fix becomes ready."""
    D = "D"
    """Fix is deployed."""
    P = "P"
    """Public becomes aware."""
    X = "X"
    """Exploit is made public."""
    A = "A"
    """Attacks are observed."""


CS_EVENTS: tuple[CSEvent, ...] = tuple(CSEvent)
"""All six CS events in canonical (`VFDPXA`) order."""

VFD_EVENTS: frozenset[CSEvent] = frozenset({CSEvent.V, CSEvent.F, CSEvent.D})
"""The CS events belonging to the vendor fix path (VFD) dimension."""

PXA_EVENTS: frozenset[CSEvent] = frozenset({CSEvent.P, CSEvent.X, CSEvent.A})
"""The CS events belonging to the public/exploit/attack (PXA) dimension."""

CS_EVENT_TO_VFD_TRIGGER: dict[CSEvent, VFD_Trigger] = {
    CSEvent.V: VFD_Trigger.V,
    CSEvent.F: VFD_Trigger.F,
    CSEvent.D: VFD_Trigger.D,
}
"""Maps a VFD-dimension CS event to the `VfdDimension.transition()` trigger.

Exported for callers that drive the dimension machines directly rather than
going through `apply_cs_event` — e.g. emit-time guards that already hold a
`VfdDimension` and need the trigger for a CS event.
"""

CS_EVENT_TO_PXA_TRIGGER: dict[CSEvent, PXA_Trigger] = {
    CSEvent.P: PXA_Trigger.P,
    CSEvent.X: PXA_Trigger.X,
    CSEvent.A: PXA_Trigger.A,
}
"""Maps a PXA-dimension CS event to the `PxaDimension.transition()` trigger.

The PXA counterpart of `CS_EVENT_TO_VFD_TRIGGER`; see that map for the
rationale.
"""


def cs_dimensions(state: CS) -> tuple[CS_vfd, CS_pxa]:
    """Return the (VFD, PXA) dimension states of a compound CS state.

    Examples::

        cs_dimensions(CS.vfdpxa)  # (CS_vfd.vfd, CS_pxa.pxa)
        cs_dimensions(CS.VFdPXa)  # (CS_vfd.VFd, CS_pxa.PXa)
    """
    compound = state.value
    return compound.vfd_state, compound.pxa_state


def cs_from_dimensions(vfd_state: CS_vfd, pxa_state: CS_pxa) -> CS:
    """Return the compound `CS` member for a (VFD, PXA) dimension pair.

    Every one of the 4 x 8 combinations is a valid compound state, so this
    never fails for well-typed inputs.

    Examples::

        cs_from_dimensions(CS_vfd.VFd, CS_pxa.Pxa)  # CS.VFdPxa
    """
    return CS[f"{vfd_state.name}{pxa_state.name}"]


def is_ephemeral_cs_state(state: CS) -> bool:
    """Return True if *state* is transient and constrains the next event.

    A state is ephemeral when the formal model requires a specific event to
    fire next: ``vP`` requires ``V``, ``pX`` requires ``P``.  The two
    conditions are mutually exclusive, because ``vP`` needs ``P`` set and
    ``pX`` needs it unset.

    Examples::

        is_ephemeral_cs_state(CS.vfdPxa)  # True  (public aware, vendor unaware)
        is_ephemeral_cs_state(CS.vfdpXa)  # True  (exploit public, public unaware)
        is_ephemeral_cs_state(CS.VfdPxa)  # False
    """
    return bool(required_next_cs_events(state))


def required_next_cs_events(state: CS) -> frozenset[CSEvent]:
    """Return the events that *state* permits as its immediate successor.

    An empty set means the state is not ephemeral and imposes no
    next-event requirement of its own — any event still available under the
    per-dimension machines may fire.

    Examples::

        required_next_cs_events(CS.vfdPxa)  # frozenset({CSEvent.V})
        required_next_cs_events(CS.vfdpXa)  # frozenset({CSEvent.P})
        required_next_cs_events(CS.VfdPxa)  # frozenset()
    """
    vfd_state, pxa_state = cs_dimensions(state)

    # vP: the public is aware but the vendor is not -> V must fire next.
    if is_pxa_public_aware(pxa_state) and not is_vfd_vendor_aware(vfd_state):
        return frozenset({CSEvent.V})

    # pX: an exploit is public but the public is not aware -> P must fire next.
    if is_pxa_exploit_public(pxa_state) and not is_pxa_public_aware(pxa_state):
        return frozenset({CSEvent.P})

    return frozenset()


def cs_transition_event(src: CS, dst: CS) -> CSEvent | None:
    """Return the single event that distinguishes *src* from *dst*.

    Returns None when the two states differ in zero or more than one
    dimension bit, i.e. when no single event can account for the change.

    Examples::

        cs_transition_event(CS.vfdpxa, CS.Vfdpxa)  # CSEvent.V
        cs_transition_event(CS.vfdpxa, CS.vfdpxa)  # None (no change)
        cs_transition_event(CS.vfdpxa, CS.VfdPxa)  # None (two bits changed)
    """
    changed = [
        event
        for event, before, after in zip(CS_EVENTS, src.name, dst.name)
        if before != after
    ]
    if len(changed) != 1:
        return None
    return changed[0]


def is_valid_cs_transition(
    src: CS, dst: CS, *, allow_null: bool = False
) -> bool:
    """Return True if (src -> dst) is a legal CS transition.

    A legal transition satisfies all of:

    1. Exactly one of the six dimensions changes (Hamming distance 1).
    2. The change is monotone — from the not-yet-happened to the happened
       value; CS events are irreversible.
    3. The changed dimension's per-machine transition table permits it
       (`is_valid_vfd_transition` / `is_valid_pxa_transition`).
    4. If *src* is ephemeral, *dst* must be reached by its required event.

    Args:
        src: the source compound state
        dst: the destination compound state
        allow_null: if True, treat ``src is dst`` as valid.  Use for
            same-state status re-assertions, which are bookkeeping rather
            than transitions.

    Examples::

        is_valid_cs_transition(CS.vfdpxa, CS.Vfdpxa)  # True
        is_valid_cs_transition(CS.vfdPxa, CS.vfdPxA)  # False (vP needs V next)
        is_valid_cs_transition(CS.vfdpXa, CS.vfdpXA)  # False (pX needs P next)
        is_valid_cs_transition(CS.Vfdpxa, CS.vfdpxa)  # False (not monotone)
    """
    if src is dst:
        return allow_null

    event = cs_transition_event(src, dst)
    if event is None:
        return False

    src_vfd, src_pxa = cs_dimensions(src)
    dst_vfd, dst_pxa = cs_dimensions(dst)

    if event in VFD_EVENTS:
        if src_pxa is not dst_pxa:
            return False
        if not is_valid_vfd_transition(src_vfd, dst_vfd):
            return False
    else:
        if src_vfd is not dst_vfd:
            return False
        if not is_valid_pxa_transition(src_pxa, dst_pxa):
            return False

    required = required_next_cs_events(src)
    if required and event not in required:
        return False

    return True


def ensure_valid_cs_transition(
    src: CS, dst: CS, *, allow_null: bool = False
) -> None:
    """Raise unless (src -> dst) is a legal CS transition.

    Raises:
        VultronInvalidStateTransitionError: if the transition is not legal.
    """
    if is_valid_cs_transition(src, dst, allow_null=allow_null):
        return

    required = required_next_cs_events(src)
    if required:
        detail = (
            f" — {src.name} is ephemeral and requires event(s)"
            f" {sorted(e.value for e in required)} next"
        )
    else:
        detail = ""
    raise VultronInvalidStateTransitionError(
        f"CS: transition {src.name} -> {dst.name} is not permitted{detail}."
    )


def next_cs_states(state: CS) -> tuple[CS, ...]:
    """Return every compound state reachable from *state* in one transition.

    Examples::

        next_cs_states(CS.VFDPXA)  # () — terminal state
        len(next_cs_states(CS.vfdPxa))  # 1 — ephemeral, V only
    """
    return tuple(
        candidate
        for candidate in CS
        if is_valid_cs_transition(state, candidate)
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
            walk(candidate, acc + (event,))

    walk(CS.vfdpxa, ())
    return tuple(histories)
