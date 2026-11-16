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

"""A case event history read in the joint models' events (ADR-0182).

The extended desiderata name events the six-event sequence does not hold:
report validation and acceptance, the embargo's start and its exit by cause.
:class:`CaseRecord` reads them from the case event history, for the case and
for each vendor, as the events of
:mod:`vultron.measure.baselines.joint`, and answers two questions:

* **When did an event first occur?**  :meth:`CaseRecord.position` gives the
  log index of its first occurrence.  Two events of one ledger entry share
  it, and are simultaneous, as the events of one step of the walk are.  A
  vendor's ``V``, ``F`` and ``D`` come from its projected sequence, so an
  event a transient state forces (CEH-05-009) sits with the event that
  forced it: an aware public makes the vendor aware at once.  Likewise
  ``P`` sits no later than ``X``, because ``pX`` forces ``P`` (CSB-17-003).
* **Where does the case stand?**  :meth:`CaseRecord.state` gives the joint
  state the walk goes on from: each vendor's report-management state, fix
  path and deployment, the case's public state, and its embargo state with
  the cause of its exit.  Public awareness, a public exploit or observed
  attacks end an embargo in force at once, as a threat signal, even before
  the ledger records the exit.  A state the joint model has no place for,
  such as a fix ready before the report is accepted, or an embargo that
  starts after publication, whatever follows it, is refused with its reason
  (:class:`NotAJointStateError`), never scored.

The embargo exit splits by cause as ``process_model_desiderata.md``
§ "Splitting embargo exit by cause" splits it: ``END_TIME_REACHED``,
``FIX_READY`` and ``FIX_DEPLOYED`` are on its own terms, ``THREAT_SIGNAL`` is
a threat signal, and any other early end is other.  The history records no
embargo proposal, so a case with none in force is read as ``EM.NONE``.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import NamedTuple

from vultron.core.models.embargo_termination import TerminationCauseKind
from vultron.core.states.composite_state_invariants import (
    composite_state_violations,
    violation_pxa_em_entailment,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.cs_invariants import (
    CSEvent,
    cs_dimensions,
    replay_cs_history,
)
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import TerminationReason
from vultron.core.states.rm import RM
from vultron.measure.baselines import (
    RM_EVENT,
    EmbargoEnd,
    Event,
    EventKind,
    JointState,
    VendorPath,
)
from vultron.measure.history import (
    RM_EVENT_KINDS,
    CaseEvent,
    CaseEventHistory,
    EventKind as RecordKind,
)
from vultron.measure.sequences import CaseStateSequence, Placement

_RM_OF_KIND: dict[RecordKind, RM] = {
    kind: rm for rm, kind in RM_EVENT_KINDS.items()
}

_OWN_TERMS_CAUSES = frozenset(
    {TerminationCauseKind.FIX_READY, TerminationCauseKind.FIX_DEPLOYED}
)

_EXIT_EVENT: dict[EmbargoEnd, EventKind] = {
    EmbargoEnd.OWN_TERMS: EventKind.EXIT_OWN_TERMS,
    EmbargoEnd.THREAT_SIGNAL: EventKind.EXIT_THREAT,
    EmbargoEnd.OTHER: EventKind.EXIT_OTHER,
}

_VENDOR_PATH = frozenset({CSEvent.V, CSEvent.F, CSEvent.D})
"""The case-state events that belong to a vendor; the others are the case's."""


class NotAJointStateError(ValueError):
    """The case stands where the joint model has no state, so no walk goes on.

    Attributes:
        problems: Every rule the state breaks (EH-07-001).
    """

    def __init__(self, problems: Iterable[str]) -> None:
        self.problems = tuple(problems)
        super().__init__(
            "the case stands in no joint-model state: "
            + "; ".join(self.problems)
        )


def exit_end(event: CaseEvent) -> EmbargoEnd:
    """The cause *event*, an embargo exit, ends the embargo by.

    Raises:
        ValueError: *event* is not an embargo exit.
    """
    if event.kind is not RecordKind.EMBARGO_EXIT:
        raise ValueError(f"a {event.kind} event is not an embargo exit")
    if event.exit_reason is TerminationReason.END_TIME_REACHED:
        return EmbargoEnd.OWN_TERMS
    cause = (event.exit_cause or {}).get("kind")
    if not isinstance(cause, str):
        return EmbargoEnd.OTHER
    if cause in _OWN_TERMS_CAUSES:
        return EmbargoEnd.OWN_TERMS
    if cause == TerminationCauseKind.THREAT_SIGNAL:
        return EmbargoEnd.THREAT_SIGNAL
    return EmbargoEnd.OTHER


def _first(found: dict[EventKind, int], kind: EventKind, index: int) -> None:
    found.setdefault(kind, index)


class _CaseReading(NamedTuple):
    """The case's own events, read in one pass over the history."""

    positions: dict[EventKind, int]
    """The first log index of each case event."""
    em: EM
    """The embargo state at the end of the history."""
    end: EmbargoEnd | None
    """The cause of the embargo's exit, once it has exited."""
    problems: tuple[str, ...]
    """Every embargo start the public state left no room for."""


def _read_case(history: CaseEventHistory) -> _CaseReading:
    """The case's event positions and embargo state, read together.

    A public-state event that leaves no room for an embargo in force ends
    it as a threat signal at once (CSB-18-002 to CSB-18-004), as the joint
    model couples them, so the exit is placed at that event whether or not
    the ledger records it yet; a later exit of an embargo already ended
    changes nothing.  An embargo that starts where the public state leaves
    it no room is a problem, kept for :meth:`CaseRecord.state`, and never
    in force, whatever follows it.  ``P`` is
    placed no later than ``X``.
    """
    found: dict[EventKind, int] = {}
    em, end = EM.NONE, None
    public: set[EventKind] = set()
    problems: list[str] = []

    def exit_at(cause: EmbargoEnd, index: int) -> None:
        nonlocal em, end
        em, end = EM.EXITED, cause
        _first(found, EventKind.EXIT, index)
        _first(found, _EXIT_EVENT[cause], index)

    for event in history.events:
        if event.participant is not None:
            continue
        index = event.log_index
        if isinstance(event.kind, CSEvent):
            _first(found, EventKind(event.kind.value), index)
            public.add(EventKind(event.kind.value))
            if (
                em is EM.ACTIVE
                and violation_pxa_em_entailment(_public_state(public), em)
                is not None
            ):
                exit_at(EmbargoEnd.THREAT_SIGNAL, index)
        elif event.kind is RecordKind.EMBARGO_START:
            refused = violation_pxa_em_entailment(
                _public_state(public), EM.ACTIVE
            )
            if refused is not None:
                problems.append(
                    f"the embargo starting at log index {index}: {refused}"
                )
                continue
            em, end = EM.ACTIVE, None
            _first(found, EventKind.EMBARGO_START, index)
        elif event.kind is RecordKind.EMBARGO_EXIT and em is EM.ACTIVE:
            exit_at(exit_end(event), index)
    if EventKind.X in found:
        found[EventKind.P] = min(
            found.get(EventKind.P, found[EventKind.X]), found[EventKind.X]
        )
    return _CaseReading(found, em, end, tuple(problems))


def _recorded_rm(event: CaseEvent) -> RM | None:
    """The RM state *event* enters, or ``None`` when it is no RM event."""
    if isinstance(event.kind, RecordKind):
        return _RM_OF_KIND.get(event.kind)
    return None


def _vendor_positions(
    history: CaseEventHistory, sequence: CaseStateSequence
) -> dict[EventKind, int]:
    """The first log index of each of *sequence*'s vendor's own events.

    A forced member (CEH-05-009) takes the position of the member before it.
    """
    found: dict[EventKind, int] = {}
    position = 0
    for member in sequence.events:
        if member.placement is Placement.RECORDED:
            position = member.log_index
        if member.kind in _VENDOR_PATH:
            _first(found, EventKind(member.kind.value), position)
    for event in history.for_participant(sequence.participant):
        rm = _recorded_rm(event)
        if rm is not None and rm is not RM.RECEIVED:
            _first(found, RM_EVENT[rm], event.log_index)
    return found


def _vendor_rm(history: CaseEventHistory, participant: str) -> RM:
    """*participant*'s report-management state at the end of the history.

    A vendor aware of the vul has received its report, so a vendor with no
    later state recorded stands at ``RECEIVED``.
    """
    rm = RM.RECEIVED
    for event in history.for_participant(participant):
        recorded = _recorded_rm(event)
        if recorded is not None:
            rm = recorded
    return rm


def _public_state(public: Iterable[EventKind]) -> CS_pxa:
    """The public state once *public* have occurred; ``X`` brings ``P``."""
    seen = set(public)
    if EventKind.X in seen:
        seen.add(EventKind.P)
    name = "".join(
        letter.upper() if kind in seen else letter
        for letter, kind in (
            ("p", EventKind.P),
            ("x", EventKind.X),
            ("a", EventKind.A),
        )
    )
    return CS_pxa[name]


class CaseRecord:
    """One case's event history, read as the joint models' events.

    Built from the history and the vendors' projected sequences
    (:func:`vultron.measure.sequences.case_state_sequences`); each vendor is
    read alone, and no case-wide sequence is built (CEH-05-006).
    """

    def __init__(
        self,
        history: CaseEventHistory,
        sequences: Iterable[CaseStateSequence],
    ) -> None:
        self.case_id = history.case_id
        case = _read_case(history)
        self._case = case.positions
        self._vendors: dict[str, dict[EventKind, int]] = {}
        self._paths: dict[str, VendorPath] = {}
        for sequence in sequences:
            participant = sequence.participant
            self._vendors[participant] = _vendor_positions(history, sequence)
            vf, d, _ = cs_dimensions(replay_cs_history(sequence.kinds))
            self._paths[participant] = VendorPath(
                _vendor_rm(history, participant), vf, d
            )
        self._pxa = _public_state(self._case)
        self._em, self._end = case.em, case.end
        self._problems = case.problems

    @property
    def vendors(self) -> tuple[str, ...]:
        """The vendors read, in the order of their sequences."""
        return tuple(self._vendors)

    def position(self, event: Event, vendors: tuple[str, ...]) -> int | None:
        """The log index at which *event* first occurred, or ``None``.

        *vendors* names the vendor each vendor number of *event* stands for:
        vendor 1 is ``vendors[0]``.

        Raises:
            KeyError: *event* names a vendor number *vendors* has no vendor
                for, or a vendor this record did not read.
        """
        if event.vendor is None:
            return self._case.get(event.kind)
        if not 1 <= event.vendor <= len(vendors):
            raise KeyError(
                f"vendor {event.vendor} of {event} is not among {vendors}"
            )
        return self._vendors[vendors[event.vendor - 1]].get(event.kind)

    def path(self, vendor: str) -> VendorPath:
        """*vendor*'s report-management state, fix path and deployment now.

        Raises:
            KeyError: this record did not read *vendor*.
        """
        return self._paths[vendor]

    def state(self, paths: tuple[VendorPath, ...]) -> JointState:
        """The joint state of the case now, with *paths* for its vendors.

        Raises:
            NotAJointStateError: the joint model has no such state.
        """
        problems = list(self._problems)
        problems += [
            v.message
            for path in paths
            for v in composite_state_violations(path.rm, path.vf, path.d)
        ]
        if problems:
            raise NotAJointStateError(problems)
        return JointState(paths, self._pxa, self._em, self._end)
