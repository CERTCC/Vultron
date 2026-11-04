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

"""Report-phase RM transitions: RM.INVALID and RM.CLOSED on the report link.

They record the RM state on the report's ``VultronReportCaseLink``
(BTND-10-006, ADR-0089) and need no case.
"""

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.states.rm import RM, is_rm_write_permitted


def _read_report_case_link(
    datalayer: CasePersistence, report_id: str
) -> VultronReportCaseLink | None:
    """Read the ReportCaseLink for *report_id*, or None if absent or mistyped.

    Shared by the report-phase transition nodes and
    :class:`~vultron.core.behaviors.report.nodes.rm_transitions.valid.TransitionRMtoValid`
    so the id derivation and type guard live in one place (CS-22-001).
    """
    link = datalayer.read(VultronReportCaseLink.build_id(report_id))
    return link if isinstance(link, VultronReportCaseLink) else None


class _ReportPhaseRMTransition(DataLayerActionWithPorts, StateWriteCapable):
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
        return _read_report_case_link(self.datalayer, self.report_id)

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
        if not is_rm_write_permitted(current_rm, self._target_rm):
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
        except Exception as e:  # noqa: BLE001  # ruff-baseline #3768
            self.logger.error(  # noqa: TRY400  # ruff-baseline #3353
                "%s: Error transitioning to %s: %s",
                self.name,
                self._target_rm.name,
                e,
            )
            return Status.FAILURE


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
    Used by the reject-report trigger workflow.
    Case-**optional** for the same reason as
    :class:`TransitionRMtoInvalid`: a report can be closed without ever having
    been promoted to a case.

    The matching case-scoped move, when a case does exist, is handled
    via ``CreateParticipantStatusNode``.
    """

    _target_rm = RM.CLOSED
