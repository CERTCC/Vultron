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
:class:`TransitionRMtoInvalid`, :class:`TransitionRMtoClosed`) record the
current RM state on the report's ``VultronReportCaseLink`` record
(BTND-10-006, ADR-0089).  That field is the idempotency source read by
``CheckRMStateValid`` / ``CheckRMStateReceivedOrInvalid``.

**Case-scoped transitions** advance the actor's RM state on
its ``CaseParticipant`` inside a ``VulnerabilityCase``.

``RM.VALID`` is *both*: DUR-07-004 requires an established embargo, which only
exists on a case, and engage-case reads the participant's case-scoped state.  So
``TransitionRMtoValid`` requires the case and performs the case-scoped half
*before* updating the ReportCaseLink field (ID-04-005).  ``RM.INVALID`` and
``RM.CLOSED`` in report phase do not: a receiver may declare a bare report
invalid or closed without ever promoting it to a case.

Every node that *requires* the case reads ``/case_id`` from the blackboard
rather than looking the case up itself; the single lookup site is
:class:`~vultron.core.behaviors.case.nodes.case_lookup.RequireCaseForReport`
(ARCH-15-004).
"""

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
)
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.states.rm import RM, is_valid_rm_transition
import py_trees

from vultron.core.behaviors.case.nodes.participant.status import (
    CreateParticipantStatusNode,
)


class _ReportPhaseRMTransition(DataLayerActionWithPorts):
    """Write the report-phase RM state for one RM state on ReportCaseLink.

    Subclasses set :attr:`_target_rm`.  The RM state is stored on the
    ``VultronReportCaseLink`` record rather than as a deterministic
    ``ParticipantStatus`` latch (BTND-10-006, ADR-0089).

    **Deliberately outside the composed ParticipantStatus evaluator.**
    This node operates on a *report* before a case exists; there is no
    case participant, no VF/D/PXA dimension and no role gate for the
    shared evaluator to apply.  RM adjacency on ``ReportCaseLink.rm_state``
    is the whole rule set that applies here.
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
            sender_actor_id: Retained for API compatibility; no longer used
                for state reads or writes (ADR-0089).
            name: Optional custom node name (defaults to the class name).
        """
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id
        self.offer_id = offer_id
        self.sender_actor_id = sender_actor_id

    def _get_link(self) -> VultronReportCaseLink | None:
        """Read the ReportCaseLink for this report from the DataLayer."""
        assert self.datalayer is not None
        link_id = VultronReportCaseLink.build_id(self.report_id)
        link = self.datalayer.read(link_id)
        if not isinstance(link, VultronReportCaseLink):
            return None
        return link

    def update(self) -> Status:
        """Guard the transition, then update ReportCaseLink.rm_state.

        Returns:
            SUCCESS once the field is written; FAILURE when the DataLayer
            is unavailable, the ReportCaseLink is missing, the transition
            is illegal, or the write raises.
        """
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        link = self._get_link()
        if link is None:
            self.feedback_message = (
                f"ReportCaseLink not found for report '{self.report_id}'"
            )
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        current_rm = link.rm_state
        if current_rm != self._target_rm and not is_valid_rm_transition(
            current_rm, self._target_rm
        ):
            self.feedback_message = (
                f"Invalid RM transition {current_rm!r} → {self._target_rm!r}"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        try:
            link.rm_state = self._target_rm
            self.datalayer.save(link)
            self.logger.info(
                "RM → %s for report '%s'",
                self._target_rm.name,
                self.report_id,
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
    """Update ReportCaseLink.rm_state to RM.VALID after the case-scoped write.

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
    and the ReportCaseLink field is updated only after that succeeds.

    Args:
        report_id: ID of the VulnerabilityReport whose RM state advances.
        offer_id: ID of the Offer activity that carried the report.
        sender_actor_id: Subject actor for the case-scoped RM write.
            When ``None``, the executing actor's ``actor_id`` from the BT
            blackboard is used as a fallback (BTND-10-005, ADR-0089).
        name: Optional name for the root Sequence node.

    Returns:
        A ``Sequence`` whose children are:

        1. :class:`CreateParticipantStatusNode` — case-scoped RM write.
        2. :class:`_ValidRMLatchNode` — ReportCaseLink rm_state update.
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

    Updates ``ReportCaseLink.rm_state`` to ``RM.INVALID``.
    Deliberately case-**optional**: a receiver may declare a bare report
    invalid before any case exists.

    The matching case-scoped move, when a case does exist, is handled
    via ``CreateParticipantStatusNode``.
    """

    _target_rm = RM.INVALID


class TransitionRMtoClosed(_ReportPhaseRMTransition):
    """Transition the report to RM.CLOSED in report phase.

    Updates ``ReportCaseLink.rm_state`` to ``RM.CLOSED``.
    Used by both the reject-report and close-report trigger workflows.
    Case-**optional** for the same reason as
    :class:`TransitionRMtoInvalid`: a report can be closed without ever having
    been promoted to a case.

    The matching case-scoped move, when a case does exist, is handled
    via ``CreateParticipantStatusNode``.
    """

    _target_rm = RM.CLOSED
