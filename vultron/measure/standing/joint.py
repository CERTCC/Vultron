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
  from 1 in the sequences' vendor-awareness order (:func:`vendor_numbers`).  Each stands at its own
  report-management state and at the fix path and deployment its sequence
  reaches; every vendor's sequence reaches the same public state.
* **The embargo** stands at the case's EM state, and an exited one at the
  cause its exit records: its end time, or fixes ready or deployed, is its
  own terms, a threat signal is a threat signal, and any other cause is
  ``OTHER``.
* **The history** is one step per event, in the order the case reached them:
  each vendor's ``V``, ``F`` and ``D`` and the case's ``P``, ``X`` and ``A``
  where the vendor's sequence places them (CEH-05-009), each vendor's other
  report-management moves, and each embargo start, revision and exit.  The
  history records no embargo proposal; no desideratum reads one.

A move is scored by the joint step it names (:func:`joint_step`): the step
whose event the move's event or report-management move is, or, for an EM
move, the step to the move's EM state.  An embargo end is an own-terms exit
once every vendor has its fix ready, and an ``OTHER`` exit before that.  A
move by a participant that is not a vendor, an EM move that keeps the EM
state, and a move the joint model does not allow from here name no joint
step, and :class:`NoJointStep` says which.
"""

from __future__ import annotations

from collections.abc import Iterable

from vultron.core.models.embargo_termination import TerminationCauseKind
from vultron.core.states.cs import CS_vf
from vultron.core.states.cs_invariants import (
    CS_EVENT_TO_PXA_TRIGGER,
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

#: The case-state events that move the case's public state, which the joint
#: model holds once for the case rather than per vendor.
_CASE_WIDE: frozenset[CSEvent] = frozenset(CS_EVENT_TO_PXA_TRIGGER)

#: What a recorded termination cause means for the joint model's exit:
#: fixes ready or deployed end the embargo on its own terms, a threat signal
#: ends it for that signal (``process_model_desiderata.md`` § "Splitting
#: embargo exit by cause").  Any other cause is ``OTHER``.
_END_OF_CAUSE: dict[TerminationCauseKind, EmbargoEnd] = {
    TerminationCauseKind.FIX_READY: EmbargoEnd.OWN_TERMS,
    TerminationCauseKind.FIX_DEPLOYED: EmbargoEnd.OWN_TERMS,
    TerminationCauseKind.THREAT_SIGNAL: EmbargoEnd.THREAT_SIGNAL,
}


class NoJointStep(ValueError):
    """A move the case's joint model holds no step for; the message says
    why."""


def vendor_numbers(sequences: Iterable[CaseStateSequence]) -> dict[str, int]:
    """Each vendor's number in the joint model, by participant: its place,
    from 1, in vendor-awareness order.  The one numbering every reader of
    the joint model uses."""
    return {s.participant: n for n, s in enumerate(sequences, start=1)}


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

    An embargo that reached its end time ends on its own terms.  An early
    end takes the meaning of its recorded cause (:data:`_END_OF_CAUSE`).  An
    exit the history does not record, as when a carried register holds an
    ended entry, has no recorded cause: ``OTHER``.
    """
    if exit_ is None:
        return EmbargoEnd.OTHER
    if exit_.exit_reason is TerminationReason.END_TIME_REACHED:
        return EmbargoEnd.OWN_TERMS
    kind = (exit_.exit_cause or {}).get("kind")
    for cause, end in _END_OF_CAUSE.items():
        if kind == cause.value:
            return end
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
    numbers = vendor_numbers(vendors)
    keyed: dict[_Key, set[Event]] = {}
    for number, sequence in enumerate(vendors, start=1):
        for key, cs_event in _keyed_sequence(sequence, history):
            case_wide = cs_event in _CASE_WIDE
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
) -> Step[JointState, Event]:
    """The joint step *move* names from *prefix*'s state.

    An embargo end is the joint model's own-terms exit when every vendor has
    its fix ready (``process_model_desiderata.md`` § "Splitting embargo exit
    by cause": fixes ready end an embargo on its own terms), and its other
    exit before that.

    Raises:
        NoJointStep: when the joint model holds no step for *move*: an EM
            move that keeps the EM state, a non-vendor's report-management
            or case-state move, or a step the joint model does not allow
            from here (as in an ephemeral state, where only the event it
            requires may come next).
    """
    state = prefix.state
    steps = case_model(len(state.vendors)).steps(state)
    if isinstance(move, EMMove):
        if move.destination is move.source:
            raise NoJointStep(f"{move.name} keeps the case's EM state")
        wanted_end = None
        if move.destination is EM.EXITED:
            fixes_ready = all(v.vf is CS_vf.VF for v in state.vendors)
            wanted_end = (
                EmbargoEnd.OWN_TERMS if fixes_ready else EmbargoEnd.OTHER
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
            raise NoJointStep(
                f"{move.name} by {move.participant} moves no vendor's state"
                " in the case's joint model"
            )
        if isinstance(move, RMMove):
            wanted = Event(RM_EVENTS[move.destination], vendor)
        else:
            case_wide = move.event in _CASE_WIDE
            wanted = Event(
                EventKind(move.event.value), None if case_wide else vendor
            )
        matches = [s for s in steps if s.event == wanted]
    if not matches:
        raise NoJointStep(
            f"the case's joint model allows no {move.name} by"
            f" {move.participant} from here"
        )
    if len(matches) > 1:
        raise LookupError(
            f"{move.name} by {move.participant} names {len(matches)} joint"
            " steps; a move names at most one"
        )
    return matches[0]
