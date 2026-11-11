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

"""The one-vendor and two-vendor joint models of ADR-0182.

A joint state holds, for each vendor, its report management (RM) state and its
vendor fix path (``CS_vf``) and fix deployment (``CS_d``); for the case, the
public, exploit and attack flags (``CS_pxa``) and the embargo management (EM)
state, with the cause of the embargo's exit once it has one.

Every rule comes from :mod:`vultron.core.states`, never restated here:

* **RM moves** follow the RM transition table
  (:func:`~vultron.core.states.rm.is_valid_rm_transition`).
* **CS moves** follow CSB-17: a vendor's six-event projection
  ``(vf, d, pxa)`` must move by a legal transition
  (:func:`~vultron.core.states.cs_invariants.is_valid_cs_transition`), and a
  projection in an ephemeral state (``vP`` or ``pX``) restricts the next step
  to an event it requires
  (:func:`~vultron.core.states.cs_invariants.required_next_cs_events`).  With
  two vendors, a step must satisfy at least one ephemeral projection, so two
  vendors unaware at publication learn of it one after the other.
* **Every reached state satisfies the composite invariants**: RM↔VF, RM↔D and
  VF↔D (:func:`~vultron.core.states.composite_state_invariants\
.composite_state_violations`, CSB-18-001 — a fix needs the report Accepted,
  Deferred or Closed), and PXA↔EM
  (:func:`~vultron.core.states.composite_state_invariants\
.violation_pxa_em_entailment`, CSB-18-002 to CSB-18-004 — no active embargo
  beside public awareness, a public exploit or observed attacks).
* **EM moves** follow :data:`~vultron.core.states.em.EM_TRANSITIONS`.

Four couplings join the tables, from
``docs/topics/process_models/model_interactions/rm_em_cs.md`` and EMB-16-001:

* **Vendor awareness is report receipt.**  The RM move ``START → RECEIVED``
  and the CS event ``V`` are one step (§ "Vendor Notification").
* **A threat signal ends the embargo.**  When ``P``, ``X`` or ``A`` would put
  the case in breach of the PXA↔EM invariant, the same step exits the embargo
  with the cause :attr:`EmbargoEnd.THREAT_SIGNAL` (§ "Public Awareness",
  "Exploit Public", "Attacks Observed": an existing embargo terminates).
* **A threat signal cancels a pending proposal.**  ``P``, ``X`` or ``A``
  while EM is ``PROPOSED`` cancels every open proposal in the same step, so EM
  derives ``NONE`` (EMB-16-001).
* **No embargo is sought that could never start.**  Once the PXA↔EM
  invariant would refuse an active embargo, no new proposal is made (§ "Public
  Awareness": "New embargoes SHALL NOT be sought").

An embargo that ends without a threat signal ends on its own terms
(:attr:`EmbargoEnd.OWN_TERMS`: its end time, or fixes ready or deployed) or
otherwise (:attr:`EmbargoEnd.OTHER`), as ``process_model_desiderata.md``
§ "Splitting embargo exit by cause" splits it.  The two are distinct steps,
equally likely by indifference.

No rule that the protocol states only as a SHOULD constrains the walk: the
desiderata measure exactly those preferences, so chance must be free to break
them.  The models leave out Participant Embargo Consent and joining, because
no ordering desideratum names those events.
"""

from enum import StrEnum
from typing import NamedTuple

from vultron.core.states.composite_state_invariants import (
    composite_state_violations,
    violation_pxa_em_entailment,
)
from vultron.core.states.cs import (
    CS,
    CS_d,
    CS_pxa,
    CS_vf,
    is_valid_d_transition,
    is_valid_pxa_transition,
    is_valid_vf_transition,
)
from vultron.core.states.cs_invariants import (
    CSEvent,
    cs_from_dimensions,
    cs_transition_event,
    is_valid_cs_transition,
    required_next_cs_events,
)
from vultron.core.states.em import EM, EM_EMBARGO_ACTIVE, EM_TRANSITIONS
from vultron.core.states.rm import RM, is_valid_rm_transition
from vultron.errors import VultronInvalidStateTransitionError
from vultron.measure.baselines.walk import Step


class EmbargoEnd(StrEnum):
    """Why the embargo exited.

    ``process_model_desiderata.md`` § "Splitting embargo exit by cause".
    """

    OWN_TERMS = "OWN_TERMS"
    THREAT_SIGNAL = "THREAT_SIGNAL"
    OTHER = "OTHER"


class EventKind(StrEnum):
    """The kinds of event a joint-model step emits.

    The symbols are those of ``docs/topics/measuring_cvd/_case_events.md``.
    """

    V = "V"
    """Vendor awareness, which is also report receipt."""
    F = "F"
    """Fix readiness."""
    D = "D"
    """Fix deployment."""
    P = "P"
    """Public awareness."""
    X = "X"
    """Exploit public."""
    A = "A"
    """Attacks observed."""
    INVALIDATED = "I"
    """The report moves to RM Invalid."""
    VALIDATED = "Va"
    """The report moves to RM Valid (report validation)."""
    DEFERRED = "Df"
    """The report moves to RM Deferred."""
    ACCEPTED = "Ac"
    """The report moves to RM Accepted (report acceptance)."""
    CLOSED = "C"
    """The report moves to RM Closed (report closure)."""
    EMBARGO_PROPOSED = "Ep"
    """An embargo is proposed while none is active."""
    EMBARGO_REJECTED = "Er"
    """Every pending proposal is rejected while none is active."""
    EMBARGO_CANCELLED = "Ec"
    """A threat signal cancels every pending proposal while none is active."""
    EMBARGO_START = "E"
    """An embargo becomes active."""
    REVISION_PROPOSED = "Rp"
    """A revision of the active embargo is proposed."""
    REVISION_SETTLED = "Rs"
    """Every pending revision is accepted or rejected."""
    EXIT = "Ex"
    """The embargo exits, whatever the cause."""
    EXIT_OWN_TERMS = "ExOwn"
    """The embargo exits on its own terms."""
    EXIT_THREAT = "ExThreat"
    """A threat signal ends the embargo."""
    EXIT_OTHER = "ExOther"
    """The embargo exits early for another reason, or none recorded."""


class Event(NamedTuple):
    """One event: its kind, and the vendor it belongs to (``None`` for a case event)."""

    kind: EventKind
    vendor: int | None = None

    def __str__(self) -> str:
        return (
            self.kind.value
            if self.vendor is None
            else f"{self.kind.value}_{self.vendor}"
        )


class VendorPath(NamedTuple):
    """One vendor's report-management state, fix path and fix deployment."""

    rm: RM
    vf: CS_vf
    d: CS_d


class JointState(NamedTuple):
    """A state of a joint model.

    ``vendors[i]`` belongs to vendor ``i + 1``.  ``embargo_end`` is set
    exactly when ``em`` is ``EXITED``.
    """

    vendors: tuple[VendorPath, ...]
    pxa: CS_pxa
    em: EM
    embargo_end: EmbargoEnd | None = None


_RM_EVENT: dict[RM, EventKind] = {
    RM.RECEIVED: EventKind.V,
    RM.INVALID: EventKind.INVALIDATED,
    RM.VALID: EventKind.VALIDATED,
    RM.DEFERRED: EventKind.DEFERRED,
    RM.ACCEPTED: EventKind.ACCEPTED,
    RM.CLOSED: EventKind.CLOSED,
}

_PXA_EVENT: dict[CSEvent, EventKind] = {
    CSEvent.P: EventKind.P,
    CSEvent.X: EventKind.X,
    CSEvent.A: EventKind.A,
}

_EXITS: tuple[tuple[EmbargoEnd, EventKind], ...] = (
    (EmbargoEnd.OWN_TERMS, EventKind.EXIT_OWN_TERMS),
    (EmbargoEnd.OTHER, EventKind.EXIT_OTHER),
)


def _projection(vendor: VendorPath, pxa: CS_pxa) -> CS:
    """The vendor's six-event case state."""
    return cs_from_dimensions(vendor.vf, vendor.d, pxa)


def _consistent(vendor: VendorPath) -> bool:
    return not composite_state_violations(vendor.rm, vendor.vf, vendor.d)


def _em_event(source: EM, dest: EM) -> EventKind:
    """The event an EM move other than an exit is."""
    if dest in EM_EMBARGO_ACTIVE and source not in EM_EMBARGO_ACTIVE:
        return EventKind.EMBARGO_START
    if dest is EM.REVISE:
        return EventKind.REVISION_PROPOSED
    if dest is EM.ACTIVE:
        return EventKind.REVISION_SETTLED
    if dest is EM.PROPOSED:
        return EventKind.EMBARGO_PROPOSED
    return EventKind.EMBARGO_REJECTED


class JointModel:
    """The joint model for ``vendor_count`` vendors sharing one case.

    A :class:`~vultron.measure.baselines.walk.ChanceModel` over
    :class:`JointState` with :class:`Event` labels.
    """

    def __init__(self, vendor_count: int) -> None:
        if vendor_count < 1:
            raise ValueError(
                f"a joint model needs at least one vendor, not {vendor_count}"
            )
        self.vendor_count = vendor_count
        self._memo: dict[JointState, tuple[Step[JointState, Event], ...]] = {}

    @property
    def initial(self) -> JointState:
        """No vendor aware, nothing public, no embargo."""
        start = VendorPath(RM.START, CS_vf.vf, CS_d.d)
        return JointState((start,) * self.vendor_count, CS_pxa.pxa, EM.NONE)

    def steps(self, state: JointState) -> tuple[Step[JointState, Event], ...]:
        """Every step the rules allow from *state*, each to a distinct state."""
        known = self._memo.get(state)
        if known is None:
            known = self._memo[state] = self._allowed(state)
        return known

    def _allowed(
        self, state: JointState
    ) -> tuple[Step[JointState, Event], ...]:
        candidates = [
            *self._vendor_steps(state),
            *self._pxa_steps(state),
            *self._em_steps(state),
        ]
        required = self._required(state)
        if required:
            candidates = [s for s in candidates if s.event in required]
        found: dict[JointState, Step[JointState, Event]] = {}
        for step in candidates:
            known = found.get(step.state)
            if known is not None and known.events != step.events:
                raise VultronInvalidStateTransitionError(
                    f"two steps from {state} reach {step.state} as different"
                    f" events: {known.events} and {step.events}"
                )
            found.setdefault(step.state, step)
        return tuple(found.values())

    def apply(self, state: JointState, event: Event) -> JointState:
        """The state the step *event* reaches from *state*.

        Raises:
            VultronInvalidStateTransitionError: the rules allow no step
                *event* from *state*, or more than one (accepting one of
                several pending proposals starts the embargo as ``ACTIVE``
                or as ``REVISE``).
        """
        matches = [s.state for s in self.steps(state) if s.event == event]
        if len(matches) != 1:
            reason = "is not allowed" if not matches else "is ambiguous"
            raise VultronInvalidStateTransitionError(
                f"joint model: {event} {reason} from {state}"
            )
        return matches[0]

    def _required(self, state: JointState) -> frozenset[Event]:
        """The events an ephemeral vendor projection requires next."""
        required: set[Event] = set()
        for number, vendor in enumerate(state.vendors, start=1):
            for cs_event in required_next_cs_events(
                _projection(vendor, state.pxa)
            ):
                if cs_event is CSEvent.V:
                    required.add(Event(EventKind.V, number))
                else:
                    required.add(Event(_PXA_EVENT[cs_event]))
        return frozenset(required)

    def _vendor_steps(
        self, state: JointState
    ) -> list[Step[JointState, Event]]:
        found = []
        for number, vendor in enumerate(state.vendors, start=1):
            moved = [
                VendorPath(dest, vendor.vf, vendor.d)
                for dest in RM
                if is_valid_rm_transition(vendor.rm, dest)
                and vendor.rm is not RM.START
            ]
            if vendor.rm is RM.START and is_valid_vf_transition(
                vendor.vf, CS_vf.Vf
            ):
                moved.append(VendorPath(RM.RECEIVED, CS_vf.Vf, vendor.d))
            moved += [
                VendorPath(vendor.rm, dest, vendor.d)
                for dest in CS_vf
                if vendor.vf is CS_vf.Vf
                and is_valid_vf_transition(vendor.vf, dest)
            ]
            moved += [
                VendorPath(vendor.rm, vendor.vf, dest)
                for dest in CS_d
                if is_valid_d_transition(vendor.d, dest)
            ]
            for after in moved:
                step = self._vendor_step(state, number, vendor, after)
                if step is not None:
                    found.append(step)
        return found

    def _vendor_step(
        self,
        state: JointState,
        number: int,
        before: VendorPath,
        after: VendorPath,
    ) -> Step[JointState, Event] | None:
        """The step moving vendor *number* from *before* to *after*, if the rules allow it."""
        if not _consistent(after):
            return None
        source, dest = (
            _projection(before, state.pxa),
            _projection(after, state.pxa),
        )
        if source is not dest and not is_valid_cs_transition(source, dest):
            return None
        if after.rm is not before.rm:
            kind = _RM_EVENT[after.rm]
        else:
            cs_event = cs_transition_event(source, dest)
            assert cs_event is not None
            kind = EventKind(cs_event.value)
        vendors = list(state.vendors)
        vendors[number - 1] = after
        return Step(
            Event(kind, number), state._replace(vendors=tuple(vendors))
        )

    def _pxa_steps(self, state: JointState) -> list[Step[JointState, Event]]:
        found = []
        for dest in CS_pxa:
            if not is_valid_pxa_transition(state.pxa, dest):
                continue
            if not all(
                is_valid_cs_transition(
                    _projection(v, state.pxa), _projection(v, dest)
                )
                for v in state.vendors
            ):
                continue
            first = _projection(state.vendors[0], state.pxa)
            cs_event = cs_transition_event(
                first, _projection(state.vendors[0], dest)
            )
            assert cs_event is not None
            event = Event(_PXA_EVENT[cs_event])
            if state.em is EM.PROPOSED:
                cancelled = state._replace(pxa=dest, em=EM.NONE)
                also = frozenset({Event(EventKind.EMBARGO_CANCELLED)})
                found.append(Step(event, cancelled, also))
                continue
            if violation_pxa_em_entailment(dest, state.em) is None:
                found.append(Step(event, state._replace(pxa=dest)))
                continue
            ended = state._replace(
                pxa=dest, em=EM.EXITED, embargo_end=EmbargoEnd.THREAT_SIGNAL
            )
            also = frozenset(
                {Event(EventKind.EXIT), Event(EventKind.EXIT_THREAT)}
            )
            found.append(Step(event, ended, also))
        return found

    def _em_steps(self, state: JointState) -> list[Step[JointState, Event]]:
        found = []
        for moves in EM_TRANSITIONS.values():
            for source, dest in moves:
                if source is not state.em or dest is source:
                    continue
                if dest is EM.EXITED:
                    for end, kind in _EXITS:
                        found.append(
                            Step(
                                Event(kind),
                                state._replace(em=dest, embargo_end=end),
                                frozenset({Event(EventKind.EXIT)}),
                            )
                        )
                    continue
                if violation_pxa_em_entailment(state.pxa, dest) is not None:
                    continue
                if (
                    dest is EM.PROPOSED
                    and violation_pxa_em_entailment(state.pxa, EM.ACTIVE)
                    is not None
                ):
                    continue
                found.append(
                    Step(
                        Event(_em_event(source, dest)),
                        state._replace(em=dest),
                    )
                )
        return found


ONE_VENDOR_MODEL = JointModel(1)
"""One vendor with the case's shared events and the embargo."""

TWO_VENDOR_MODEL = JointModel(2)
"""Two vendors with the case's shared events and the embargo."""
