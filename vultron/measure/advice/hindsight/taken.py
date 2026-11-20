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

"""Which move of the advice an entry took (#6672).

:func:`taken_move` compares the states the case reached just before and
just after an entry with each move of the advice, machine by machine.  The
first machine the entry changed decides, in this order: the public state, a
fix path, the embargo, report management (:func:`first_changed`).  An
embargo move is the one whose trigger the embargo register step names, read
through the register's own mapping (:func:`register_trigger`, ADR-0130).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from enum import IntEnum

from vultron.core.models.embargo_register import em_triggers_of
from vultron.core.states.cs_invariants import (
    CS_EVENT_TO_PXA_TRIGGER,
    CSEvent,
    cs_dimensions,
)
from vultron.core.states.em import EM, EM_Trigger
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
    RegisterTrigger,
    register_trigger_between,
)
from vultron.errors import VultronInvalidStateTransitionError
from vultron.measure.advice.case import (
    AdvisedMove,
    AllowedMove,
    CaseAdvice,
    UnbandedMove,
)
from vultron.measure.history import ReachedParticipant, ReachedState
from vultron.measure.standing import CSMove, EMMove, RMMove

#: The case-state events that move the case's public state.
PUBLIC_EVENTS: frozenset[CSEvent] = frozenset(CS_EVENT_TO_PXA_TRIGGER)

type TakenMove = AdvisedMove | UnbandedMove


def _owner(state: ReachedState, participant: str) -> ReachedParticipant:
    return state.for_participant(participant) or ReachedParticipant(
        participant=participant
    )


def reached_em(state: ReachedState) -> EM | None:
    """The EM state *state*'s embargo register gives, or ``None`` when the
    register is broken and gives none."""
    try:
        return state.em()
    except VultronInvalidStateTransitionError:
        return None


def register_trigger(
    before: Mapping[str, EmbargoRegisterStatus],
    after: Mapping[str, EmbargoRegisterStatus],
) -> EM_Trigger | None:
    """The EM trigger of the register step from *before* to *after*, read
    through the register's own mapping (:func:`em_triggers_of`, ADR-0130).

    ``None`` when the register did not change, or when its change is no one
    EM trigger's step.
    """
    triggers: list[RegisterTrigger] = []
    for embargo, status in after.items():
        was = before.get(embargo)
        if was is status:
            continue
        try:
            triggers.append(register_trigger_between(was, status))
        except VultronInvalidStateTransitionError:
            return None
    if not triggers:
        return None
    em_triggers = em_triggers_of(triggers)
    return em_triggers.pop() if len(em_triggers) == 1 else None


def _pxa_made(move: CSMove, before: ReachedState, after: ReachedState) -> bool:
    _, _, source = cs_dimensions(move.source)
    _, _, destination = cs_dimensions(move.destination)
    return (
        source != destination
        and before.pxa is source
        and after.pxa is destination
    )


def _fix_path_made(
    move: CSMove, before: ReachedState, after: ReachedState
) -> bool:
    vf, d, _ = cs_dimensions(move.source)
    to_vf, to_d, _ = cs_dimensions(move.destination)
    was, now = (_owner(state, move.participant) for state in (before, after))
    return (vf, d) != (to_vf, to_d) and (
        (was.vf, was.d, now.vf, now.d) == (vf, d, to_vf, to_d)
    )


def _em_made(move: EMMove, before: ReachedState, after: ReachedState) -> bool:
    was, now = reached_em(before), reached_em(after)
    trigger = register_trigger(before.embargo_register, after.embargo_register)
    if trigger is None:
        return False
    return (move.source, move.destination, move.trigger) == (
        was,
        now,
        trigger,
    )


def _rm_made(move: RMMove, before: ReachedState, after: ReachedState) -> bool:
    was, now = (_owner(state, move.participant) for state in (before, after))
    return (was.rm, now.rm) == (move.source, move.destination)


def owns_state(move: AllowedMove) -> bool:
    """Whether *move* moves the state of the participant it names: an RM
    move, or a case-state event on that participant's fix path.  A
    public-state move moves the case's state, and an EM move names only a
    participant who may make it."""
    return isinstance(move, RMMove) or (
        isinstance(move, CSMove) and move.event not in PUBLIC_EVENTS
    )


class Machine(IntEnum):
    """The machines whose change decides an entry's mark, in the order they
    decide it."""

    PUBLIC = 0
    FIX_PATH = 1
    EMBARGO = 2
    REPORT = 3


def machine_of(move: AllowedMove) -> Machine:
    """The machine *move* changes."""
    if isinstance(move, CSMove):
        return (
            Machine.PUBLIC if move.event in PUBLIC_EVENTS else Machine.FIX_PATH
        )
    if isinstance(move, EMMove):
        return Machine.EMBARGO
    return Machine.REPORT


def first_changed(before: ReachedState, after: ReachedState) -> Machine | None:
    """The first machine, in deciding order, whose state the entry from
    *before* to *after* changed; ``None`` when it changed none the move
    advice weighs."""
    pairs = [
        (_owner(before, now.participant), now) for now in after.participants
    ]
    if before.pxa is not after.pxa:
        return Machine.PUBLIC
    if any((was.vf, was.d) != (now.vf, now.d) for was, now in pairs):
        return Machine.FIX_PATH
    if before.embargo_register != after.embargo_register:
        return Machine.EMBARGO
    if any(was.rm is not now.rm for was, now in pairs):
        return Machine.REPORT
    return None


def _made(
    move: AllowedMove, before: ReachedState, after: ReachedState
) -> bool:
    """Whether the entry from *before* to *after* made *move*."""
    if isinstance(move, CSMove):
        if machine_of(move) is Machine.PUBLIC:
            return _pxa_made(move, before, after)
        return _fix_path_made(move, before, after)
    if isinstance(move, EMMove):
        return _em_made(move, before, after)
    return _rm_made(move, before, after)


def _candidates(advice: CaseAdvice) -> Iterator[TakenMove]:
    yield from advice.moves
    yield from advice.unbanded


def taken_move(
    advice: CaseAdvice,
    before: ReachedState,
    after: ReachedState,
    actor: str | None = None,
) -> TakenMove | None:
    """The move of *advice* that the entry from *before* to *after* made.

    The first machine the entry changed, in deciding order, decides
    (:func:`first_changed`): only a move of that machine is the step, so a
    change no listed move makes is never passed over for a later machine's.
    Among the moves that make it, an open move comes before one with no
    band, then the acting *actor*'s own: a public-state or embargo change is
    the same joint step whichever participant's move it is, so its band is
    the same, but a participant that moves no vendor's state has no band
    for it.

    Returns:
        The move, or ``None`` when no move of *advice* makes the change the
        entry made in that machine.
    """
    machine = first_changed(before, after)
    made = [
        m
        for m in _candidates(advice)
        if machine_of(m.move) is machine and _made(m.move, before, after)
    ]
    if not made:
        return None
    return min(
        made,
        key=lambda m: (
            isinstance(m, UnbandedMove),
            m.move.participant != actor,
        ),
    )


__all__ = [
    "PUBLIC_EVENTS",
    "Machine",
    "TakenMove",
    "first_changed",
    "machine_of",
    "owns_state",
    "reached_em",
    "register_trigger",
    "taken_move",
]
