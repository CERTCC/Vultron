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


"""Native canonical-ledger commit leaf node for a newly created case.

Commits the genesis ``create_case`` entry plus the report, participant-status
and case-status entries the CASE_MANAGER authors during initialization
(ADR-0041 AC-4, CLP-07-013).  It is the one creation commit: composed by
``create_case_proposal_received_tree`` and by the create-case trigger's
``create_case_trigger_bt``, so a case created either way commits the same
entry sequence (BTND-07-003).
"""

import json
import logging
from typing import Any, cast

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.offer_provenance import find_offer_for_report
from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.report import VulnerabilityReport
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.sync_helpers import _find_equivalent_recorded_entry

logger = logging.getLogger(__name__)


class _EntryNotCommitted(Exception):
    """A creation entry the commit tree did not commit (CLP-07-013)."""


#: ``event_type`` of a case's genesis ledger entry, the root of the
#: CASE_MANAGER's hash chain.  Its presence is what "the case's creation
#: entries are committed" means to a later step (CM-14-007, CM-14-011).
CREATE_CASE_EVENT_TYPE = "create_case"


class CommitNativeLedgerEntriesNode(DataLayerActionWithPorts):
    """Commit canonical ledger entries natively for a new case's initialization.

    The CASE_MANAGER runs it: the CaseActor on the proposal path, the
    creating actor on the create-case trigger path, where *owner_uri* is that
    same actor.

    Commits entries in causal order per ADR-0041 AC-4:

      1. ``create_case``                     actor=CaseActor
      2. ``add_report_to_case``              actor=CaseActor
      3. ``add_participant_status_to_participant`` × N  actor=CaseActor
      4. ``add_case_status_to_case``         actor=owner (the receiver set the
         genesis case status; ``("Add","CaseStatus")`` is nonetheless in
         ``_CASE_AUTHORED_SIGNATURES`` per CLP-12-001, so a CaseActor-authored
         entry would also validate)

    Every entry is required (CLP-07-013): the first entry that fails to
    commit stops the sequence, so no later entry is committed out of order,
    and the node returns FAILURE.  The records those entries carry were
    written before this node ran, so the failure is surfaced, not prevented.
    The one case it can also undo is a failed genesis on the create-case
    trigger path (*withdraw_case_on_genesis_failure*): nothing is committed
    and the ``Create`` is not yet queued, so the case the tree wrote is
    removed and the case file is as it was before the trigger.

    On the proposal path it runs *after* the accept flow has queued its
    ``Create(VulnerabilityCase)`` (``EmitCreateVulnerabilityCaseNode``):
    every commit fans its entry out through the FIFO outbox, and the
    proposer, already a participant, must hold the case object before its
    first ``Announce(CaseLedgerEntry)`` arrives (CM-14-011, CP-09-009).
    Committed ahead of the Create, the fan-out put ten entries in front of it
    and every recipient took the SYNC-15 pre-genesis path on the normal
    case-creation route (#3033, #2898).  On the create-case trigger path the
    creator is the case's only participant, so the entries fan out to nobody
    and the node runs *before* ``UpdateActorOutbox``: a case whose genesis
    does not commit is withdrawn before its ``Create`` is sent.

    Reads ``case_id`` from the blackboard.
    """

    def __init__(
        self,
        owner_uri: str,
        report_id: str | None,
        offer_id: str | None = None,
        offer_actor_id: str | None = None,
        name: str | None = None,
        *,
        withdraw_case_on_genesis_failure: bool = False,
    ) -> None:
        """Create the node.

        Args:
            owner_uri: The case owner, the author of the case-status entry.
            report_id: The report the case was created from, if any.
            offer_id: The report's ``Offer``, when the proposal carried it.
            offer_actor_id: That ``Offer``'s actor.
            name: Node name.
            withdraw_case_on_genesis_failure: Remove the case and the
                participant records it names when the genesis entry fails
                to commit.  Only the create-case trigger passes it: it
                commits before it queues the ``Create``, so nothing about
                the case has been committed or sent.  The proposal path
                queues its ``Create`` first (CP-09-009) and must not.
        """
        super().__init__(name=name or self.__class__.__name__)
        self._owner_uri = owner_uri
        self._report_id = report_id
        self._offer_id = offer_id
        self._offer_actor_id = offer_actor_id
        self._withdraw_case_on_genesis_failure = (
            withdraw_case_on_genesis_failure
        )
        self._case_id_bb: str | None = None

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id"}

    def initialise(self) -> None:
        super().initialise()
        self._case_id_bb = None
        try:
            self._case_id_bb = self.get_input("case_id")
        except (NoDataAvailable, NotImplementedError):
            pass

    def _commit_one(
        self,
        case_id: str,
        object_id: str,
        event_type: str,
        activity: tuple[str, str],
    ) -> None:
        """Commit one canonical ledger entry for a factory-built *activity*.

        *activity* is the ``(activity_id, sealed_blob)`` pair a
        :class:`~vultron.core.ports.trigger_activity.TriggerActivityPort`
        ``record_*`` method returned; the blob is the snapshot, verbatim
        (VM-08-003).

        Raises:
            _EntryNotCommitted: The commit tree did not succeed.  Every
                creation entry is required (CLP-07-013), so :meth:`update`
                stops the sequence there.
        """
        assert self.datalayer is not None
        assert self.actor_id is not None
        snapshot: dict[str, Any] = json.loads(activity[1])
        if (
            _find_equivalent_recorded_entry(
                case_id=case_id,
                object_id=object_id,
                event_type=event_type,
                payload_snapshot=snapshot,
                dl=cast(CaseOutboxPersistence, self.datalayer),
            )
            is not None
        ):
            # Already committed and fanned out by an earlier delivery.  The
            # commit tree would reuse the entry, but it would also fan it out
            # to every recipient again (CP-05-008).
            logger.debug(
                "%s: '%s' entry for '%s' already committed — skipping",
                self.name,
                event_type,
                object_id,
            )
            return
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
            raise _EntryNotCommitted(
                f"could not commit the '{event_type}' entry for"
                f" '{object_id}' on case '{case_id}':"
                f" {result.feedback_message}"
            )

    def _find_offer_id_for_report(
        self, report_id: str
    ) -> tuple[str | None, str | None]:
        """Return ``(offer_id, offer_actor_id)`` for *report_id*.

        Its own store first, then what the proposal carried (CP-01-007). The
        store answers only when this CaseActor received the
        ``Offer(VulnerabilityReport)`` itself — which a co-located one does not,
        because the ``OfferRecord`` belongs to the sibling that did and there is
        no read across that line (ADR-0073, PCR-01-003).

        The fallback is not a nicety. The ledger entry is the only place the
        report's Offer provenance (``offerId``, ``offerActorId``) survives for
        the case's participants, who were never sent the Offer and read it from
        here (CP-01-007). Without it the omission surfaces nowhere near here
        (#2548).
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
        port = self._require_trigger_activity_port()
        for report_ref in case.vulnerability_reports:
            # Resolve through the store even when the case carries the report
            # inline: the stored record StoreProposalReportNode wrote is the
            # authoritative copy, and an inline one may be a partial projection.
            report_id = _as_id(report_ref) or ""
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
            activity = port.record_report_added_to_case(
                report_id=report_id,
                case_id=case_id,
                actor=self.actor_id,
                offer_id=offer_id,
                offer_actor_id=offer_actor_id,
            )
            self._commit_one(
                case_id, report_id, "add_report_to_case", activity
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
        port = self._require_trigger_activity_port()
        for status in participant.participant_statuses:
            if not isinstance(status, ParticipantStatus):
                continue
            status_id = getattr(status, "id_", None)
            if not status_id:
                continue
            activity = port.record_participant_status_added(
                status=status,
                participant=participant,
                case_id=case_id,
                actor=self.actor_id,
            )
            self._commit_one(
                case_id,
                status_id,
                "add_participant_status_to_participant",
                activity,
            )

    def _commit_case_statuses(
        self, case: VulnerabilityCase, case_id: str
    ) -> None:
        assert self.datalayer is not None
        port = self._require_trigger_activity_port()
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
            activity = port.record_case_status_added(
                status=status, case_id=case_id, actor=self._owner_uri
            )
            self._commit_one(
                case_id, status_id, "add_case_status_to_case", activity
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

        # Audit-best-effort skip (ADR-0087; NOT Regime 1). A missing case
        # skips as SUCCESS: the node runs last, after the node that wrote the
        # case (and, on the accept flow, WriteCreateCaseMarkerNode, which
        # hard-fails on an absent case via _require_case), so the coordination
        # decision belongs to those nodes. The distinct hard-fail here is a failed
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
        # A missing port is a composition fault, raised as VultronWiringError
        # rather than reported as a failed commit (ARCH-15-001).
        port = self._require_trigger_activity_port()

        # 1. create_case  (actor = CaseActor, in _CASE_AUTHORED_SIGNATURES)
        #
        # The genesis create_case entry is the root of the CaseActor's
        # canonical hash chain: if it is missing, every later entry (and every
        # replica seeded from it) is broken.
        #
        # On the proposal path this node runs after the emit nodes, so the
        # Create(VulnerabilityCase) is already queued (with
        # Accept(as_CaseProposal), and the retry marker cleared): the failure
        # is surfaced (ERROR log, non-APPLIED verdict), not prevented, and a
        # redelivered proposal commits what this run did not.  Holding the
        # Create back would mean fanning the genesis entry out ahead of it,
        # which is the pre-genesis path CP-09-009 exists to avoid.  Pinned by
        # test_genesis_commit_failure_is_reported_after_accept_and_create_are_queued.
        try:
            self._commit_one(
                case_id,
                case_id,
                CREATE_CASE_EVENT_TYPE,
                port.record_case_created(case_id=case_id, actor=self.actor_id),
            )
        except _EntryNotCommitted as exc:
            return self._genesis_failed(case, str(exc))

        failed: str | None = None
        try:
            # 2. add_report_to_case  (actor = CaseActor)
            self._commit_add_reports(case, case_id)
            # 3. add_participant_status × N  (actor = CaseActor)
            self._commit_participant_statuses(case, case_id)
            # 4. add_case_status  (actor = owner_uri — provenance, not a guard
            #    constraint: ("Add","CaseStatus") IS in
            #    _CASE_AUTHORED_SIGNATURES per CLP-12-001, so a
            #    CaseActor-authored entry validates too)
            self._commit_case_statuses(case, case_id)
        except _EntryNotCommitted as exc:
            failed = str(exc)
        if failed is not None:
            # Every creation entry is required (CLP-07-013): stop here, so no
            # later entry is committed out of order, and fail.
            self.feedback_message = (
                f"{failed} — the case's creation entries stop there"
                " (CLP-07-013)"
            )
            logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        logger.info(
            "%s: native ledger entries committed for case '%s' (ADR-0041 AC-4)",
            self.name,
            case_id,
        )
        return Status.SUCCESS

    def _genesis_failed(self, case: VulnerabilityCase, reason: str) -> Status:
        """Report a failed genesis entry, withdrawing the case if allowed."""
        if self._withdraw_case_on_genesis_failure:
            self._withdraw_case(case)
            self.feedback_message = (
                f"genesis create_case ledger commit failed for case"
                f" '{case.id_}' ({reason}); nothing was committed or sent, so"
                " the case was withdrawn (CLP-07-013)"
            )
        else:
            self.feedback_message = (
                f"genesis create_case ledger commit failed for case"
                f" '{case.id_}' ({reason}) — the CASE_MANAGER ledger has no"
                " root; the creation messages were already queued (CP-09-009)"
            )
        logger.error("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE

    def _withdraw_case(self, case: VulnerabilityCase) -> None:
        """Remove the case and every participant record it names.

        Called only when no entry for the case was committed, so no replica
        holds any of it and the case file returns to what it was before the
        creation (CLP-07-013).  The report the case was created from is not
        the creation's write and stays.
        """
        assert self.datalayer is not None
        for participant_id in case.actor_participant_index.values():
            participant = self.datalayer.read(participant_id)
            if isinstance(participant, CaseParticipant):
                for status in participant.participant_statuses:
                    self.datalayer.delete("ParticipantStatus", status.id_)
            self.datalayer.delete("CaseParticipant", participant_id)
        self.datalayer.delete("VulnerabilityCase", case.id_)
