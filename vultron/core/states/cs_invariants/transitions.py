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


"""CS transition validity and the two ephemeral-state rules (CSB-17).

A CS transition changes exactly one of the six dimensions, always from the
not-yet-happened to the happened value; ``vP`` and ``pX`` constrain the very
next event.  Decision: ADR-0060.
"""

from vultron.core.states.cs import (
    CS,
    CS_d,
    CS_pxa,
    CS_vf,
    is_pxa_exploit_public,
    is_pxa_public_aware,
    is_valid_d_transition,
    is_valid_pxa_transition,
    is_valid_vf_transition,
    is_vf_vendor_aware,
)
from vultron.core.states.cs_invariants.events import (
    CS_EVENTS,
    VFD_EVENTS,
    CSEvent,
    cs_dimensions,
)
from vultron.errors import (
    VultronInvalidStateTransitionError,
)


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
    vf_state, _d_state, pxa_state = cs_dimensions(state)

    # vP: the public is aware but the vendor is not -> V must fire next.
    if is_pxa_public_aware(pxa_state) and not is_vf_vendor_aware(vf_state):
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
        for event, before, after in zip(
            CS_EVENTS, src.name, dst.name, strict=False
        )
        if before != after
    ]
    if len(changed) != 1:
        return None
    return changed[0]


def _is_valid_vfd_step(
    event: CSEvent,
    src_vf: CS_vf,
    dst_vf: CS_vf,
    src_d: CS_d,
    dst_d: CS_d,
    src_pxa: CS_pxa,
    dst_pxa: CS_pxa,
) -> bool:
    if src_pxa is not dst_pxa:
        return False
    if event == CSEvent.D:
        return src_vf is dst_vf and is_valid_d_transition(src_d, dst_d)
    return src_d is dst_d and is_valid_vf_transition(src_vf, dst_vf)


def is_valid_cs_transition(
    src: CS, dst: CS, *, allow_null: bool = False
) -> bool:
    """Return True if (src -> dst) is a legal CS transition.

    A legal transition satisfies all of:

    1. Exactly one of the six dimensions changes (Hamming distance 1).
    2. The change is monotone — from the not-yet-happened to the happened
       value; CS events are irreversible.
    3. The changed dimension's per-machine transition table permits it
       (`is_valid_vf_transition` / `is_valid_d_transition` / `is_valid_pxa_transition`).
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

    src_vf, src_d, src_pxa = cs_dimensions(src)
    dst_vf, dst_d, dst_pxa = cs_dimensions(dst)

    if event in VFD_EVENTS:
        if not _is_valid_vfd_step(
            event, src_vf, dst_vf, src_d, dst_d, src_pxa, dst_pxa
        ):
            return False
    else:  # P, X, or A
        if src_vf is not dst_vf or src_d is not dst_d:
            return False
        if not is_valid_pxa_transition(src_pxa, dst_pxa):
            return False

    required = required_next_cs_events(src)
    return not (required and event not in required)


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
