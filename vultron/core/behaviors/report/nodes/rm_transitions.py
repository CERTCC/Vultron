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

"""RM transition nodes for the report behavior tree.

Two shapes of RM transition live here, and the difference between them is the
whole point of the module layout:

**Report-phase transitions** (:class:`TransitionRMtoValid`,
:class:`TransitionRMtoInvalid`, :class:`TransitionRMtoClosed`) write a
deterministic ``ParticipantStatus`` record keyed on
``(actor, report, rm_state)``.  That record is also the idempotency *latch* read
by ``CheckRMStateValid`` / ``CheckRMStateReceivedOrInvalid``, so writing it
asserts "this transition has happened" to every later tick.

**Case-scoped transitions** (:class:`TransitionCaseParticipantRMtoClosed`,
:class:`TransitionCaseParticipantRMtoInvalid`) advance the actor's RM state on
its ``CaseParticipant`` inside a ``VulnerabilityCase``.

``RM.VALID`` is *both*: DUR-07-004 requires an established embargo, which only
exists on a case, and engage-case reads the participant's case-scoped state.  So
``TransitionRMtoValid`` requires the case and performs the case-scoped half
*before* writing the latch (ID-04-005).  ``RM.INVALID`` and ``RM.CLOSED`` in
report phase do not: a receiver may declare a bare report invalid or closed
without ever promoting it to a case, so those nodes are deliberately
case-optional and select their ``context`` via
:func:`~vultron.core.models._helpers.report_phase_context`.

Every node that *requires* the case reads ``/case_id`` from the blackboard
rather than looking the case up itself; the single lookup site is
:class:`~vultron.core.behaviors.case.nodes.case_lookup.RequireCaseForReport`
(ARCH-15-004).
"""

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
)
from vultron.core.models.dimensions import PecDimension, RmDimension
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.states.rm import RM, is_valid_rm_transition
from vultron.enums.roles import CVDRole
from vultron.core.models._helpers import (
    _report_phase_status_id,
    report_phase_context,
)
import py_trees

from vultron.core.behaviors.case.nodes.participant.status import (
    CreateParticipantStatusNode,
)
from vultron.core.use_cases._helpers import _idempotent_create


def _current_report_phase_rm_state(dl, actor_id: str, report_id: str) -> RM:
    """Return the current report-phase RM state for actor/report.

    Checks the DataLayer for existing report-phase ParticipantStatus records in
    descending-progress order (CLOSED first) and returns the highest-progress
    state found.  Returns ``RM.RECEIVED`` as the implicit default when no
    records exist — consistent with ``CheckRMStateReceivedOrInvalid`` semantics
    (absence of a status record means the report was received but not yet
    processed).

    Per BTND-10-001: callers use this to establish the *current_state* side of
    the (current_state → target_state) validity check before writing a new
    report-phase ParticipantStatus.
    """
    for rm_state in (
        RM.CLOSED,
        RM.ACCEPTED,
        RM.DEFERRED,
        RM.VALID,
        RM.INVALID,
        RM.RECEIVED,
    ):
        status_id = _report_phase_status_id(
            actor_id, report_id, rm_state.value
        )
        if dl.read(status_id) is not None:
            return rm_state
    return RM.RECEIVED


class _ReportPhaseRMTransition(DataLayerActionWithPorts):
    """Write the report-phase ``ParticipantStatus`` latch for one RM state.

    Subclasses set :attr:`_target_rm`.  This is the only place a report-phase RM
    record is constructed (ARCH-15-004); the three concrete nodes differ solely
    in their target state and in whether they require a case.

    **Deliberately outside the composed ParticipantStatus evaluator.**
    BTND-10-002 routes case-participant writes through
    :func:`~vultron.core.states.participant_transitions\
    .participant_transition_violations`, and this node does not use it because it
    is a different lifecycle, not an oversight: it operates on a *report* before
    a case exists, so there is no case participant, no VF/D/PXA dimension and no
    role to gate on, and its current state comes from
    :func:`_current_report_phase_rm_state` (report-scoped) rather than
    ``resolve_participant_state_from_dl`` (case-scoped).  RM adjacency is
    therefore the whole rule set that applies here.  Recorded as a declared
    exclusion in ``test/architecture/test_participant_status_validation.py``;
    whether the two lifecycles should share one evaluator is ISSUE-3111.
    """

    #: Target RM state; set by each concrete subclass.
    _target_rm: RM

    def __init__(
        self,
        report_id: str,
        offer_id: str,
        sender_actor_id: str | None = None,
        name: str | None = None,
    ) -> None:
        """Initialize a report-phase RM transition node.

        Args:
            report_id: ID of the VulnerabilityReport whose RM state advances.
            offer_id: ID of the Offer activity that carried the report.
            sender_actor_id: Explicit actor ID to use instead of the blackboard
                ``actor_id``.  Thread this in when the tree runs under
                ``receiving_actor_id`` but the RM transition must target the
                message sender (ADR-0022 single-BT pattern).
            name: Optional custom node name (defaults to the class name).
        """
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id
        self.offer_id = offer_id
        self.sender_actor_id = sender_actor_id

    def _acting_actor_id(self) -> str | None:
        return self.sender_actor_id

    def _guard_transition(self, actor_id: str) -> Status | None:
        """Return FAILURE when current → target is not a legal RM move.

        A repeat of the target state is allowed through so the node stays
        idempotent (ID-04-004).
        """
        current_rm = _current_report_phase_rm_state(
            self.datalayer, actor_id, self.report_id
        )
        if current_rm != self._target_rm and not is_valid_rm_transition(
            current_rm, self._target_rm
        ):
            self.feedback_message = (
                f"Invalid RM transition {current_rm!r} → {self._target_rm!r}"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        return None

    def _write_latch(self, actor_id: str, context: str) -> None:
        """Persist the deterministic report-phase ``ParticipantStatus`` record.

        Writing this record is what makes the transition observable to later
        ticks, so callers MUST only reach it once every other half of the
        transition has succeeded (ID-04-005).
        """
        assert self.datalayer is not None
        status = ParticipantStatus(
            id_=_report_phase_status_id(
                actor_id, self.report_id, self._target_rm.value
            ),
            context=context,
            attributed_to=actor_id,
            rm=RmDimension(state=self._target_rm),
            consent=PecDimension(state=PEC.NO_EMBARGO),
            cvd_role=[CVDRole.REPORTER],
        )
        _idempotent_create(
            self.datalayer,
            "ParticipantStatus",
            status.id_,
            status,
            f"ParticipantStatus (report-phase {self._target_rm.name})",
        )
        self.logger.info(
            "RM → %s for report '%s' (actor '%s')",
            self._target_rm.name,
            self.report_id,
            actor_id,
        )

    def update(self) -> Status:
        """Guard the transition, then write the report-phase latch.

        Returns:
            SUCCESS once the latch is written; FAILURE when the DataLayer or
            actor is unavailable, the transition is illegal, or the write
            raises.
        """
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        actor_id = self._acting_actor_id()
        if actor_id is None:
            self.feedback_message = "actor_id not available"
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        try:
            if (f := self._guard_transition(actor_id)) is not None:
                return f
            self._write_latch(
                actor_id, report_phase_context(self.datalayer, self.report_id)
            )
            return Status.SUCCESS
        except Exception as e:
            self.logger.error(
                "%s: Error transitioning to %s: %s",
                self.name,
                self._target_rm.name,
                e,
            )
            return Status.FAILURE


class _ValidRMLatchNode(_ReportPhaseRMTransition):
    """Write the report-phase RM.VALID latch after the case-scoped write.

    This is the second child of the ``TransitionRMtoValid`` Sequence.  It runs
    only after :class:`CreateParticipantStatusNode` has already advanced the
    actor's case-participant RM state to ``RM.VALID``, so the order guarantee
    (ID-04-005) is structural — the Sequence won't reach this node on failure.

    It is a private helper; callers use :func:`TransitionRMtoValid` to build
    the full Sequence.
    """

    _target_rm = RM.VALID


def TransitionRMtoValid(
    report_id: str,
    offer_id: str,
    sender_actor_id: str | None = None,
    name: str | None = None,
) -> py_trees.composites.Sequence:
    """Return a Sequence that advances the actor to RM.VALID in case and report phase.

    ``RM.VALID`` is a case-scoped transition (ID-04-005): the case-participant
    record is advanced *first* via :class:`CreateParticipantStatusNode` (which
    reads ``/case_id`` from the blackboard seeded by
    :class:`~vultron.core.behaviors.case.nodes.case_lookup.RequireCaseForReport`),
    and the report-phase latch is written only after that succeeds.

    Args:
        report_id: ID of the VulnerabilityReport whose RM state advances.
        offer_id: ID of the Offer activity that carried the report.
        sender_actor_id: Explicit subject actor.  Must be provided; the
            blackboard ``actor_id`` (executing actor) is not used as a fallback
            (BTND-10-005, ADR-0089).
        name: Optional name for the root Sequence node.

    Returns:
        A ``Sequence`` whose children are:

        1. :class:`CreateParticipantStatusNode` — case-scoped RM write.
        2. :class:`_ValidRMLatchNode` — report-phase idempotency latch.
    """
    return py_trees.composites.Sequence(
        name=name or "TransitionRMtoValid",
        memory=True,
        children=[
            CreateParticipantStatusNode(
                actor_id=sender_actor_id or "",
                rm_state=RM.VALID,
                vf_state=None,
                d_state=None,
                pxa_state=None,
                name="CreateRMValidStatus",
            ),
            _ValidRMLatchNode(
                report_id=report_id,
                offer_id=offer_id,
                sender_actor_id=sender_actor_id,
            ),
        ],
    )


class TransitionRMtoInvalid(_ReportPhaseRMTransition):
    """Transition the report to RM.INVALID in report phase.

    Persists a report-phase ``ParticipantStatus`` record with ``RM.INVALID``
    for the actor and report.  Deliberately case-**optional**: a receiver may
    declare a bare report invalid before any case exists, so the ``context``
    falls back to the report URI until the report→case promotion has happened
    (CLP-07-007, via :func:`report_phase_context`).

    The matching case-scoped move, when a case does exist, is
    :class:`TransitionCaseParticipantRMtoInvalid`.
    """

    _target_rm = RM.INVALID


class TransitionRMtoClosed(_ReportPhaseRMTransition):
    """Transition the report to RM.CLOSED in report phase.

    Persists a report-phase ``ParticipantStatus`` record with ``RM.CLOSED`` for
    the actor and report.  Used by both the reject-report and close-report
    trigger workflows.  Case-**optional** for the same reason as
    :class:`TransitionRMtoInvalid`: a report can be closed without ever having
    been promoted to a case.

    The matching case-scoped move, when a case does exist, is
    :class:`TransitionCaseParticipantRMtoClosed`.
    """

    _target_rm = RM.CLOSED
