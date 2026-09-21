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


"""Native canonical-ledger commit leaf node for the CaseProposal received tree.

Commits the genesis ``create_case`` entry plus the report, participant-status
and case-status entries the CaseActor authors during initialization
(ADR-0041 AC-4). Composed by ``create_case_proposal_received_tree``
(BTND-07-003).
"""

import logging
from typing import Any, cast

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.ledger_snapshots import (
    build_add_case_status_snapshot,
    build_add_participant_status_snapshot,
    build_add_report_to_case_snapshot,
    build_create_case_snapshot,
)
from vultron.core.behaviors.case.offer_provenance import find_offer_for_report
from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.report import VulnerabilityReport
from vultron.core.ports.case_persistence import CaseOutboxPersistence

logger = logging.getLogger(__name__)


class CommitNativeLedgerEntriesNode(DataLayerActionWithPorts):
    """Commit canonical ledger entries natively for CaseActor initialization.

    Commits entries in causal order per ADR-0041 AC-4:

      1. ``create_case``                     actor=CaseActor
      2. ``add_report_to_case``              actor=CaseActor
      3. ``add_participant_status_to_participant`` × N  actor=CaseActor
      4. ``add_case_status_to_case``         actor=vendor (the vendor set the
         genesis case status; ``("Add","CaseStatus")`` is nonetheless in
         ``_CASE_AUTHORED_SIGNATURES`` per CLP-12-001, so a CaseActor-authored
         entry would also validate)

    Best-effort: a single failed entry logs a warning but does not abort
    the Sequence; initialization proceeds regardless (the ledger is an
    audit record, not a precondition for the Accept/Create emissions).

    Reads ``case_id`` from the blackboard.
    """

    def __init__(
        self,
        vendor_uri: str,
        report_id: str | None,
        offer_id: str | None = None,
        offer_actor_id: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._vendor_uri = vendor_uri
        self._report_id = report_id
        self._offer_id = offer_id
        self._offer_actor_id = offer_actor_id
        self._case_id_bb: str | None = None
        self.wire_render_port = None

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=False)
        ports["wire_render_port"] = PortInformation(
            data_type=object, required=False
        )
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id", "wire_render_port": "/wire_render_port"}

    def initialise(self) -> None:
        super().initialise()
        self._case_id_bb = None
        self.wire_render_port = None
        try:
            self._case_id_bb = self.get_input("case_id")
        except (NoDataAvailable, NotImplementedError):
            pass
        try:
            self.wire_render_port = self.get_input("wire_render_port")
        except (NoDataAvailable, NotImplementedError):
            pass

    def _commit_one(
        self,
        case_id: str,
        object_id: str,
        event_type: str,
        snapshot: dict[str, Any],
    ) -> bool:
        """Commit one canonical ledger entry.

        Returns ``True`` on success, ``False`` on failure.  Downstream callers
        treat most entries as best-effort (log and continue), but the genesis
        ``create_case`` entry is load-bearing — the root of the CaseActor's
        hash chain — so its result must not be silently discarded.
        """
        assert self.datalayer is not None
        assert self.actor_id is not None
        tree = create_commit_log_entry_tree(
            case_id=case_id,
            object_id=object_id,
            event_type=event_type,
            payload_snapshot=snapshot,
        )
        result = BTBridge(
            datalayer=cast(CaseOutboxPersistence, self.datalayer)
        ).execute_with_setup(tree=tree, actor_id=self.actor_id)
        if result.status != Status.SUCCESS:
            logger.warning(
                "%s: could not commit '%s' entry for case '%s' (best-effort): %s",
                self.name,
                event_type,
                case_id,
                result.feedback_message,
            )
            return False
        return True

    def _find_offer_id_for_report(
        self, report_id: str
    ) -> tuple[str | None, str | None]:
        """Return ``(offer_id, offer_actor_id)`` for *report_id*.

        Its own store first, then what the proposal carried (CP-01-007). The
        store answers only when this CaseActor received the
        ``Offer(VulnerabilityReport)`` itself — which a co-located one does not,
        because the ``OfferRecord`` belongs to the sibling that did and there is
        no read across that line (ADR-0073, PCR-01-003).

        The fallback is not a nicety. Every invited actor rebuilds its
        ``VultronOfferRecord`` from this entry's ``offerId``
        (``ApplyOfferReportFromLedgerNode``, ADR-0035 DL-06-002), and that node
        is deliberately lenient — a snapshot without one is skipped
        "(non-fatal)". So the omission surfaced nowhere near here: the invitee's
        ``validate-report`` answered ``404 Offer not found`` (#2548).
        """
        assert self.datalayer is not None
        offer_id, offer_actor_id = find_offer_for_report(
            self.datalayer, report_id
        )
        if offer_id:
            return offer_id, offer_actor_id
        return self._offer_id, self._offer_actor_id

    def _commit_add_reports(
        self, case: VulnerabilityCase, case_id: str
    ) -> None:
        assert self.datalayer is not None
        assert self.actor_id is not None
        assert self.wire_render_port is not None
        for report_id in case.vulnerability_reports:
            raw_report = self.datalayer.read(report_id)
            if not isinstance(raw_report, VulnerabilityReport):
                logger.warning(
                    "%s: report '%s' not found — skipping"
                    " add_report_to_case (best-effort). The report is written"
                    " by StoreProposalReportNode from the copy the proposal"
                    " carries inline (CP-01-004); if that node logged nothing,"
                    " the proposal arrived without one",
                    self.name,
                    report_id,
                )
                continue
            offer_id, offer_actor_id = self._find_offer_id_for_report(
                report_id
            )
            snapshot = build_add_report_to_case_snapshot(
                raw_report,
                case,
                self.actor_id,
                case_id,
                self.wire_render_port,
                offer_id=offer_id,
                offer_actor_id=offer_actor_id,
            )
            self._commit_one(
                case_id, report_id, "add_report_to_case", snapshot
            )

    def _commit_participant_statuses(
        self, case: VulnerabilityCase, case_id: str
    ) -> None:
        assert self.datalayer is not None
        assert self.actor_id is not None
        for participant_ref in case.case_participants:
            participant_id = (
                participant_ref
                if isinstance(participant_ref, str)
                else getattr(participant_ref, "id_", None)
            )
            if not participant_id:
                continue
            raw_participant = self.datalayer.read(participant_id)
            if not isinstance(raw_participant, CaseParticipant):
                logger.warning(
                    "%s: participant '%s' not found — skipping"
                    " participant_status entry (best-effort)",
                    self.name,
                    participant_id,
                )
                continue
            self._commit_one_participant_statuses(raw_participant, case_id)

    def _commit_one_participant_statuses(
        self, participant: CaseParticipant, case_id: str
    ) -> None:
        assert self.actor_id is not None
        assert self.wire_render_port is not None
        for status in participant.participant_statuses:
            if not isinstance(status, ParticipantStatus):
                continue
            status_id = getattr(status, "id_", None)
            if not status_id:
                continue
            snapshot = build_add_participant_status_snapshot(
                status,
                participant,
                self.actor_id,
                case_id,
                self.wire_render_port,
            )
            self._commit_one(
                case_id,
                status_id,
                "add_participant_status_to_participant",
                snapshot,
            )

    def _commit_case_statuses(
        self, case: VulnerabilityCase, case_id: str
    ) -> None:
        assert self.datalayer is not None
        assert self.wire_render_port is not None
        for status_ref in case.case_statuses:
            if isinstance(status_ref, CaseStatus):
                status = status_ref
            elif isinstance(status_ref, str):
                raw = self.datalayer.read(status_ref)
                if not isinstance(raw, CaseStatus):
                    continue
                status = raw
            else:
                continue
            status_id = getattr(status, "id_", None)
            if not status_id:
                continue
            snapshot = build_add_case_status_snapshot(
                status,
                case,
                self._vendor_uri,
                case_id,
                self.wire_render_port,
            )
            self._commit_one(
                case_id, status_id, "add_case_status_to_case", snapshot
            )

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        case_id = self._case_id_bb
        if not isinstance(case_id, str):
            self.feedback_message = "case_id not found in blackboard"
            return Status.FAILURE

        # Audit-best-effort skip (ADR-0087; NOT Regime 1). This node's role is
        # to record the CaseActor's *audit* ledger — it is not a coordination
        # precondition for the outbound Accept/Create emissions. A missing case
        # therefore skips as SUCCESS: the coordination decision is deferred to
        # the emission node (WriteCreateCaseMarkerNode), which hard-fails on an
        # absent case via _require_case. The distinct hard-fail here is a failed
        # *genesis commit* (case present, write fails) — see _commit_one and the
        # paired tests test_genesis_create_case_failure_aborts /
        # test_case_not_found_is_best_effort_success. Conformance allowlist.
        raw_case = self.datalayer.read_case(case_id)
        if raw_case is None:
            logger.warning(
                "%s: case '%s' not found — skipping ledger entries"
                " (best-effort)",
                self.name,
                case_id,
            )
            return Status.SUCCESS

        case = raw_case
        # 1. create_case  (actor = CaseActor, in _CASE_AUTHORED_SIGNATURES)
        #
        # The genesis create_case entry is the root of the CaseActor's
        # canonical hash chain.  Unlike the remaining best-effort entries, a
        # failure here must NOT be masked: if the genesis entry is missing,
        # the CaseActor's authoritative ledger has no root and every later
        # entry (and every replica seeded from it) is broken.  Fail fast so
        # the enclosing Sequence aborts before Accept/Create are emitted, and
        # the vendor is not told a case exists that has no canonical ledger.
        if self.wire_render_port is None:
            self.feedback_message = "wire_render_port not available"
            logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        if not self._commit_one(
            case_id,
            case_id,
            "create_case",
            build_create_case_snapshot(
                case, self.actor_id, case_id, self.wire_render_port
            ),
        ):
            self.feedback_message = (
                f"genesis create_case ledger commit failed for case"
                f" '{case_id}' — aborting native initialization"
            )
            logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        # 2. add_report_to_case  (actor = CaseActor)
        self._commit_add_reports(case, case_id)
        # 3. add_participant_status × N  (actor = CaseActor)
        self._commit_participant_statuses(case, case_id)
        # 4. add_case_status  (actor = vendor_uri — provenance, not a guard
        #    constraint: ("Add","CaseStatus") IS in _CASE_AUTHORED_SIGNATURES
        #    per CLP-12-001, so a CaseActor-authored entry validates too)
        self._commit_case_statuses(case, case_id)

        logger.info(
            "%s: native ledger entries committed for case '%s' (ADR-0041 AC-4)",
            self.name,
            case_id,
        )
        return Status.SUCCESS
