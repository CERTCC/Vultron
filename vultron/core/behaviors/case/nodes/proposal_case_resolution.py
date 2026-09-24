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


"""Case-resolution leaf nodes for the CaseProposal received-side tree.

Resolve which ``VulnerabilityCase`` a ``Create(as_CaseProposal)`` applies
to (reuse an existing one or create a new one) and persist the report the
proposal carried inline. Composed by ``create_case_proposal_received_tree``
in the sibling ``case_proposal_received_tree.py`` (BTND-07-003).
"""

import logging

from py_trees.common import Status
from py_trees.ports import PortInformation
from pydantic import ValidationError

from vultron.core.behaviors.case.nodes.case_lookup import RequireCaseForReport
from vultron.core.behaviors.helpers import (
    DataLayerAction,
    DataLayerActionWithPorts,
)
from vultron.core.models._helpers import project_wire_snapshot_to_core
from vultron.core.models.case import VultronCase
from vultron.core.models.report import VulnerabilityReport
from vultron.errors import VultronAlreadyExistsError

logger = logging.getLogger(__name__)


class LoadExistingCaseNode(RequireCaseForReport):
    """Find an existing ``VulnerabilityCase`` for *report_id* and load it.

    AC-1 / AC-2 (CP-05-006): detects a duplicate ``Create(as_CaseProposal)``
    for a report that already has a case.  Writes the existing ``case_id`` to
    the blackboard so ``EmitAcceptCaseProposalNode`` and
    ``WriteCreateCaseMarkerNode`` can reference it, then returns SUCCESS.

    Returns FAILURE when no existing case is found, allowing the outer
    Selector to fall through to ``CreateCaseFromProposalNode`` (normal path).

    Behaviour is inherited wholesale from
    :class:`~vultron.core.behaviors.case.nodes.case_lookup.RequireCaseForReport`
    — "resolve this store's case for a report, publish ``/case_id``, fail when
    absent" has exactly one implementation (ARCH-15-004).  The subclass exists
    only to keep the CP-05-006 node name in BT traces and to document what
    FAILURE means *here*: no duplicate, so create the case.
    """


class CreateCaseFromProposalNode(DataLayerActionWithPorts):
    """Create a VulnerabilityCase from the proposal and write case_id to blackboard.

    The case-actor service is the ``attributed_to`` author of the new case,
    preserving AS2 "I created this" semantics (CP-05-003, ADR-0023).
    """

    def __init__(
        self,
        report_id: str | None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._report_id = report_id

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "case_id": PortInformation(data_type=str, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id"}

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        case = VultronCase(attributed_to=self.actor_id)
        if self._report_id is not None:
            case.vulnerability_reports.append(self._report_id)

        try:
            self.datalayer.create(case)
        except ValueError as exc:
            self.feedback_message = f"Case creation failed: {exc}"
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        self._set_output("case_id", case.id_)
        logger.info(
            "%s: Created VulnerabilityCase '%s' from proposal",
            self.name,
            case.id_,
        )
        return Status.SUCCESS


class StoreProposalReportNode(DataLayerAction):
    """Persist the report the proposal carried inline, if not already stored.

    Nothing else in this tree did, and three downstream nodes need it:
    ``AddReporterParticipantNode``, ``CommitNativeLedgerEntriesNode`` and
    ``SeedReporterSignatoryNode`` each ``read(report_id)`` and skip
    "best-effort" when it is absent. So one missing write degraded silently in
    three places, and the visible symptom was a participant who never appeared
    and a replica the reporter never received.

    A shared store hid it: the *vendor* had stored the report when it received
    the Offer, and that row was visible to everyone. With per-actor stores the
    CaseActor has its own, and the report only reaches it inline on the proposal
    (CP-01-004) — so it has to be written here.

    Prefers *inline_report*, a report already converted to the core shape by the
    caller. The fallback — validating the proposal's serialised ``object`` — can
    only be as good as that dict's spelling, and the dict the received-side use
    case has is a ``by_alias=True`` wire dump, because the ``Accept`` must carry
    the proposal inline on the wire (CP-05-003, AKM-03-001). In wire spelling the
    reporter is ``attributedTo``; this core model declares ``attributed_to`` and
    sets ``extra="ignore"``, so validating that dict quietly produced a report
    with no reporter, and the complaint surfaced three nodes later as "has no
    attributed_to" (#2482). Converting is the wire layer's job — it owns
    ``to_core()`` — and core MUST NOT import wire to do it itself (ARCH-03-001),
    so the caller converts and passes the result down.
    """

    def __init__(
        self,
        report_id: str | None,
        proposal_dict: dict | None,
        inline_report: VulnerabilityReport | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._report_id = report_id
        self._proposal_dict = proposal_dict
        self._inline_report = inline_report

    def _report_from_proposal_dict(self) -> VulnerabilityReport | None:
        """Rebuild the report from the proposal's serialised inline object.

        Accepts either spelling of the key: ``object`` is the wire alias and
        ``object_`` the field name, and which one a caller has depends on
        whether its dump used ``by_alias``.
        """
        proposal = self._proposal_dict or {}
        raw = proposal.get("object")
        if not isinstance(raw, dict):
            raw = proposal.get("object_")
        if not isinstance(raw, dict):
            logger.warning(
                "%s: proposal carried no inline report for '%s' (got %s), so"
                " the reporter participant and its ledger entry cannot be"
                " derived; the proposal should inline it (CP-01-004)",
                self.name,
                self._report_id,
                type(raw).__name__,
            )
            return None
        try:
            return VulnerabilityReport.model_validate(
                project_wire_snapshot_to_core(VulnerabilityReport, raw)
            )
        except ValidationError as exc:
            # A malformed inline report cannot be reconstructed; stay lenient
            # and fall back to the reference-only path.  A non-validation error
            # would indicate a real fault and must surface (CS-23-001).
            logger.warning(
                "%s: could not reconstruct the inline report '%s' from the"
                " proposal: %s",
                self.name,
                self._report_id,
                exc,
            )
            return None

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        if not self._report_id:
            return Status.SUCCESS
        if self.datalayer.read(self._report_id) is not None:
            return Status.SUCCESS

        report = self._inline_report or self._report_from_proposal_dict()
        if report is None:
            return Status.SUCCESS
        self._warn_if_unattributed(report)

        try:
            self.datalayer.create(report)
        except VultronAlreadyExistsError as exc:
            logger.debug(
                "%s: report '%s' already stored: %s",
                self.name,
                self._report_id,
                exc,
            )
            return Status.SUCCESS

        logger.info(
            "%s: stored report '%s' from the inline proposal",
            self.name,
            self._report_id,
        )
        return Status.SUCCESS

    def _warn_if_unattributed(self, report: VulnerabilityReport) -> None:
        """Say out loud that a storable report is useless for what follows.

        Three downstream nodes derive from ``attributed_to``; without it each
        reports the absence separately and much further from the cause.
        """
        if report.attributed_to:
            return
        logger.warning(
            "%s: the inline report '%s' has no attributed_to, so the"
            " reporter participant, its ledger entry and the SIGNATORY"
            " seed cannot be derived from it (CP-01-004 requires a report"
            " attributed to its reporter)",
            self.name,
            self._report_id,
        )
