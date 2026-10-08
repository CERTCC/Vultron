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
from vultron.core.models._helpers import (
    _new_urn,
    now_utc,
    project_wire_snapshot_to_core,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.report import VulnerabilityReport
from vultron.errors import VultronAlreadyExistsError

logger = logging.getLogger(__name__)


class LoadExistingCaseNode(RequireCaseForReport):
    """Find the *proposer's own* case for *report_id* and load it.

    CP-05-006 / CP-05-008: a ``Create(as_CaseProposal)`` under a new proposal
    id may name a report that already has a case.  The case is reused only
    when the proposer owns it (``attributed_to``); a case for the same report
    owned by anyone else is not this proposer's, so this node fails and the
    outer Selector creates a separate case (CBT-06-002).  ``report_id`` is
    chosen by the sender, so the report alone never identifies a case.

    Writes the existing ``case_id`` to the blackboard so
    ``EmitAcceptCaseProposalNode`` and ``WriteCreateCaseMarkerNode`` can
    reference it, then returns SUCCESS.  Returns FAILURE when the proposer owns
    no case for the report, allowing the Selector to fall through to
    ``CreateCaseFromProposalNode`` (normal path).

    The store may hold several cases for one report (one per proposer), so the
    single-row ``find_case_by_report_id`` lookup is only the fast path; when it
    returns another proposer's case the cases are scanned for the proposer's.
    """

    def __init__(
        self,
        report_id: str | None,
        owner_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(report_id=report_id, name=name)
        self._owner_id = owner_id

    def _find_case(self, report_id: str) -> VulnerabilityCase | None:
        assert self.datalayer is not None
        first = self.datalayer.find_case_by_report_id(report_id)
        if first is None:
            return None
        if str(first.attributed_to) == self._owner_id:
            return first
        for case in self.datalayer.list_objects("VulnerabilityCase"):
            if (
                isinstance(case, VulnerabilityCase)
                and str(case.attributed_to) == self._owner_id
                and report_id in _report_ids(case)
            ):
                return case
        return None

    def _absence_message(self, report_id: str) -> str:
        return (
            f"no VulnerabilityCase for report '{report_id}' owned by"
            f" '{self._owner_id}' in this actor's store"
        )


def _report_ids(case: VulnerabilityCase) -> set[str]:
    """The report ids *case* references, whether stored bare or inline."""
    return {
        entry if isinstance(entry, str) else str(entry.id_)
        for entry in case.vulnerability_reports
    }


class CreateCaseFromProposalNode(DataLayerActionWithPorts):
    """Create a VulnerabilityCase from the proposal and write case_id to blackboard.

    The new case is attributed to the **proposing actor** — the report
    receiver, who becomes the CASE_OWNER — never to the CASE_MANAGER that
    creates it (CP-09-001, CM-22-001, CM-02-008).  ``attributed_to`` is the
    case's owner field: the update gate, embargo consent and answers, and
    teardown authorization all read it (CM-13-001), and ownership transfer
    rewrites it (CM-21-002), so naming the CASE_MANAGER there would make
    every one of those checks treat it as the owner.  The CASE_MANAGER's
    authorship is carried where AS2 puts it instead: it is the ``actor`` of
    the ``Create(VulnerabilityCase)`` it emits (CP-05-003).

    *owner_id* is the actor that sent the ``Create(as_CaseProposal)``, the one
    ``AddOwnerParticipantNode`` records as CASE_OWNER, so the owner field
    and the CASE_OWNER participant cannot name different actors.  The proposal's
    ``attributed_to`` names the same actor (CP-01-010).

    The genesis hash is anchored to that owner, not to the CaseActor creating
    the case: the CaseActor is the owner's delegated proxy, so a case it
    creates hashes exactly as one the owner created itself (CLP-08-002).  No
    hash is passed here; ``VulnerabilityCase`` computes it from
    ``attributed_to`` at construction, the single definition of the formula.
    """

    def __init__(
        self,
        report_id: str | None,
        owner_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._report_id = report_id
        self._owner_id = owner_id

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "case_id": PortInformation(data_type=str, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id"}

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None and self.actor_id is not None

        case = VulnerabilityCase(
            id_=_new_urn(),
            published=now_utc(),
            attributed_to=self._owner_id,
        )
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
            "%s: Created VulnerabilityCase '%s' from proposal, owned by '%s'",
            self.name,
            case.id_,
            self._owner_id,
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

    A shared store hid it: the *report receiver* had stored the report when it received
    the Offer, and that row was visible to everyone. With per-actor stores the
    CaseActor has its own, and the report only reaches it inline on the proposal
    (CP-01-004) — so it has to be written here.

    Prefers *inline_report*, the ``VulnerabilityReport`` the wire parser
    validated on the proposal — under ADR-0099 detail 3 that object already
    *is* the core class, so the caller hands it down unchanged (ARCH-20-008).
    The fallback — rebuilding from the proposal's serialised ``object`` — can
    only be as good as that dict's spelling, and the dict the received-side use
    case has is a ``by_alias=True`` wire dump, because the ``Accept`` must carry
    the proposal inline on the wire (CP-05-003, AKM-03-001). In wire spelling the
    reporter is ``attributedTo``; before the core model carried the AS2 alias,
    validating that dict quietly produced a report with no reporter, and the
    complaint surfaced three nodes later as "has no attributed_to" (#2482). The
    rebuild therefore goes through ``project_wire_snapshot_to_core``, the one
    seam core has for a snapshot dict (ARCH-20-008).
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
            " reporter participant, its ledger entry and the signatory"
            " seed cannot be derived from it (CP-01-004 requires a report"
            " attributed to its reporter)",
            self.name,
            self._report_id,
        )
