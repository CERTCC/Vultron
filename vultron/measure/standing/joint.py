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
"""Where a case stands in its joint model, and the step each move takes there.

The expected desiderata outcomes are read from a point of the case's joint
walk (:mod:`vultron.measure.baselines.values`, #6449), so a standing is mapped
onto a :class:`~vultron.measure.baselines.WalkPrefix` here, and nowhere
else (:func:`case_prefix`).

* **The vendors** are the participants with a case-state sequence, numbered
  from 1 in the sequences' vendor-awareness order.  Each stands at its own
  report-management state and at the fix path and deployment its sequence
  reaches; every vendor's sequence reaches the same public state.
* **The embargo** stands at the case's EM state, and an exited one at the
  cause its exit records: its end time is its own terms, a threat signal is a
  threat signal, and any other cause is ``OTHER``.
* **The history** is one step per event, in the order the case reached them:
  each vendor's ``V``, ``F`` and ``D`` and the case's ``P``, ``X`` and ``A``
  where the vendor's sequence places them (CEH-05-009), each vendor's other
  report-management moves, and each embargo start, revision and exit.  The
  history records no embargo proposal; no desideratum reads one.

A move is scored by the joint step it names (:func:`joint_step`): the step
whose event the move's event or report-management move is, or, for an EM
move, the step to the move's EM state.  A move by a participant that is not a
vendor, and an EM move that keeps the EM state, name no joint step.
"""

from __future__ import annotations

from collections.abc import Iterable

from vultron.core.states.cs_invariants import (
    CSEvent,
    cs_dimensions,
    replay_cs_history,
)
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import TerminationReason
from vultron.core.states.rm import RM
from vultron.measure.baselines import (
    RM_EVENTS,
    EmbargoEnd,
    Event,
    EventKind,
    JointState,
    Step,
    VendorPath,
    WalkPrefix,
    case_model,
)
from vultron.measure.history import (
    RM_EVENT_KINDS,
    CaseEvent,
    CaseEventHistory,
    EventKind as HistoryKind,
)
from vultron.measure.sequences import CaseStateSequence, Placement
from vultron.measure.standing.moves import CSMove, EMMove, RMMove

type CasePrefix = WalkPrefix[JointState, Event]

#: The history kind of each report-management move, by the state it enters.
_RM_OF_KIND: dict[HistoryKind, RM] = {
    kind: rm for rm, kind in RM_EVENT_KINDS.items()
}

#: A step's place in the case's order: the log index and position in the
#: history of the event it follows, and how many placed events precede it
#: there (CEH-05-009).
type _Key = tuple[int, int, int]


def _keyed_sequence(
    sequence: CaseStateSequence, history: CaseEventHistory
) -> list[tuple[_Key, CSEvent]]:
    """Each member of *sequence*, keyed where the sequence places it."""
    keyed: list[tuple[_Key, CSEvent]] = []
    previous: _Key = (-1, -1, 0)
    for member in sequence.events:
        if member.placement is Placement.RECORDED:
            key = (
                member.log_index,
                history.events.index(member.event),
                0,
            )
        else:
            key = (previous[0], previous[1], previous[2] + 1)
        keyed.append((key, CSEvent(member.kind)))
        previous = key
    return keyed


def _embargo_end(exit_: CaseEvent | None) -> EmbargoEnd:
    """Why the case's embargo exited, from its exit event.

    An exit the history does not record, as when a carried register holds
    an ended entry, has no recorded cause: ``OTHER``.
    """
    if exit_ is None:
        return EmbargoEnd.OTHER
    if exit_.exit_reason is TerminationReason.END_TIME_REACHED:
        return EmbargoEnd.OWN_TERMS
    cause = (exit_.exit_cause or {}).get("kind")
    if cause == EmbargoEnd.THREAT_SIGNAL.value:
        return EmbargoEnd.THREAT_SIGNAL
    return EmbargoEnd.OTHER


def _exit_events(end: EmbargoEnd) -> frozenset[Event]:
    kinds = {
        EmbargoEnd.OWN_TERMS: EventKind.EXIT_OWN_TERMS,
        EmbargoEnd.THREAT_SIGNAL: EventKind.EXIT_THREAT,
        EmbargoEnd.OTHER: EventKind.EXIT_OTHER,
    }
    return frozenset({Event(EventKind.EXIT), Event(kinds[end])})


def _case_steps(
    history: CaseEventHistory, numbers: dict[str, int]
) -> list[tuple[_Key, frozenset[Event]]]:
    """The steps the history records other than the case-state events."""
    steps: list[tuple[_Key, frozenset[Event]]] = []
    active = False
    for position, event in enumerate(history.events):
        key = (event.log_index, position, 0)
        found = _case_step(event, numbers, active)
        if event.kind is HistoryKind.EMBARGO_START:
            active = True
        elif event.kind is HistoryKind.EMBARGO_EXIT:
            active = False
        if found:
            steps.append((key, found))
    return steps


def _case_step(
    event: CaseEvent, numbers: dict[str, int], active: bool
) -> frozenset[Event]:
    """The joint events one non-case-state history event is, if any."""
    rm = (
        _RM_OF_KIND.get(event.kind)
        if isinstance(event.kind, HistoryKind)
        else None
    )
    if rm is not None:
        vendor = numbers.get(event.participant or "")
        # Entering RECEIVED is the vendor's V, which its sequence places.
        if vendor is None or rm is RM.RECEIVED:
            return frozenset()
        return frozenset({Event(RM_EVENTS[rm], vendor)})
    if event.kind is HistoryKind.EMBARGO_START:
        kind = (
            EventKind.REVISION_SETTLED if active else EventKind.EMBARGO_START
        )
        return frozenset({Event(kind)})
    return frozenset()


def case_prefix(
    history: CaseEventHistory,
    sequences: Iterable[CaseStateSequence],
    rm_of: dict[str, RM],
    em: EM,
) -> CasePrefix | None:
    """Where the case stands in its joint model; ``None`` with no vendor.

    Args:
        history: The case's event history.
        sequences: Its vendors' case-state sequences, in vendor-awareness
            order; their order numbers the vendors.
        rm_of: Each vendor's report-management state, by participant.
        em: The case's EM state.
    """
    vendors = list(sequences)
    if not vendors:
        return None
    numbers = {s.participant: n for n, s in enumerate(vendors, start=1)}
    keyed: dict[_Key, set[Event]] = {}
    for number, sequence in enumerate(vendors, start=1):
        for key, cs_event in _keyed_sequence(sequence, history):
            case_wide = cs_event in (CSEvent.P, CSEvent.X, CSEvent.A)
            if case_wide and number != 1:
                continue  # every vendor's sequence places them alike
            keyed.setdefault(key, set()).add(
                Event(EventKind(cs_event.value), None if case_wide else number)
            )
    for key, events in _case_steps(history, numbers):
        keyed[key] = keyed.get(key, set()) | events
    end = None
    if em is EM.EXITED:
        exits = history.of_kind(HistoryKind.EMBARGO_EXIT)
        exit_ = exits[-1] if exits else None
        end = _embargo_end(exit_)
        if exit_ is not None:
            position = history.events.index(exit_)
            key = (exit_.log_index, position, 0)
            keyed[key] = keyed.get(key, set()) | _exit_events(end)
    paths = []
    for sequence in vendors:
        vf, d, pxa = cs_dimensions(replay_cs_history(sequence.kinds))
        paths.append(VendorPath(rm_of[sequence.participant], vf, d))
    # Every vendor's sequence holds the case's P, X and A alike, so each
    # reaches the same public state.
    state = JointState(tuple(paths), pxa, em, end)
    return WalkPrefix(
        state, tuple(frozenset(keyed[key]) for key in sorted(keyed))
    )


def joint_step(
    prefix: CasePrefix,
    numbers: dict[str, int],
    move: RMMove | CSMove | EMMove,
) -> Step[JointState, Event] | None:
    """The joint step *move* names from *prefix*'s state, or ``None``.

    ``None`` when the move is a non-vendor's report-management or case-state
    move, an EM move that keeps the EM state, or a step the joint model does
    not allow from there.
    """
    state = prefix.state
    steps = case_model(len(state.vendors)).steps(state)
    if isinstance(move, EMMove):
        if move.destination is move.source:
            return None
        wanted_end = (
            EmbargoEnd.OTHER if move.destination is EM.EXITED else None
        )
        matches = [
            s
            for s in steps
            if s.state.em is move.destination
            and s.state.vendors == state.vendors
            and s.state.pxa is state.pxa
            and s.state.embargo_end is wanted_end
        ]
    else:
        vendor = numbers.get(move.participant)
        if vendor is None:
            return None
        if isinstance(move, RMMove):
            wanted = Event(RM_EVENTS[move.destination], vendor)
        else:
            case_wide = move.event in (CSEvent.P, CSEvent.X, CSEvent.A)
            wanted = Event(
                EventKind(move.event.value), None if case_wide else vendor
            )
        matches = [s for s in steps if s.event == wanted]
    return matches[0] if len(matches) == 1 else None
