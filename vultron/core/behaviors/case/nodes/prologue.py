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

"""Prologue ledger commit node for case-initialization entries.

When the CaseActor accepts its CASE_MANAGER role it must back-fill ledger
entries for all protocol actions that occurred before it was appointed.
This module provides :class:`WritePrologueLedgerEntriesNode` which is
inserted as the first action in
:func:`~vultron.core.behaviors.case.offer_case_manager_role_received_tree.create_offer_case_manager_role_received_tree`.

Entries committed in causal order:

1. ``submit_report``        — Offer(VulnerabilityReport, to=vendor)
2. ``create_case``          — Create(VulnerabilityCase)
3. ``add_report_to_case``   — Add(VulnerabilityReport, target=case)
4. Per-participant          — Add(ParticipantStatus, target=participant)
5. ``add_case_status_to_case`` — Add(CaseStatus, target=case)

Per Issue #1688.
"""

import logging
from typing import Any, cast

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.report import VulnerabilityReport
from vultron.core.ports.case_persistence import CaseOutboxPersistence

logger = logging.getLogger(__name__)


def _obj_to_inline_dict(obj: Any) -> dict[str, Any]:
    """Return a JSON-serializable dict for *obj* suitable for payloadSnapshot.

    For Pydantic models, calls ``model_dump(mode="json", by_alias=True,
    exclude_none=True)``.  For plain dicts, returns a copy.  Returns an
    empty dict for ``None``.
    """
    if obj is None:
        return {}
    if hasattr(obj, "model_dump"):
        result = obj.model_dump(mode="json", by_alias=True, exclude_none=True)
        return result if isinstance(result, dict) else {}
    if isinstance(obj, dict):
        return dict(obj)
    return {}


def _find_offer_record_for_report(
    dl: Any, report_id: str
) -> VultronOfferRecord | None:
    """Return the first OfferRecord whose report_id matches *report_id*."""
    for obj in dl.list_objects("OfferRecord"):
        if isinstance(obj, VultronOfferRecord) and obj.report_id == report_id:
            return obj
    return None


def _build_submit_report_snapshot(
    offer_record: VultronOfferRecord,
    report: VulnerabilityReport,
    vendor_id: str,
    case_id: str,
) -> dict[str, Any]:
    report_dict = _obj_to_inline_dict(report)
    report_dict.setdefault("type", "VulnerabilityReport")
    return {
        "type": "Offer",
        "id": offer_record.offer_id,
        "actor": offer_record.offer_actor_id,
        "object": report_dict,
        "to": [vendor_id],
        "context": case_id,
    }


def _build_create_case_snapshot(
    case: VulnerabilityCase,
    vendor_id: str,
    case_id: str,
) -> dict[str, Any]:
    case_dict = _obj_to_inline_dict(case)
    case_dict.setdefault("type", "VulnerabilityCase")
    return {
        "type": "Create",
        "actor": vendor_id,
        "object": case_dict,
        "context": case_id,
    }


def _build_add_report_to_case_snapshot(
    report: VulnerabilityReport,
    case: VulnerabilityCase,
    vendor_id: str,
    case_id: str,
) -> dict[str, Any]:
    report_dict = _obj_to_inline_dict(report)
    report_dict.setdefault("type", "VulnerabilityReport")
    case_dict = _obj_to_inline_dict(case)
    case_dict.setdefault("type", "VulnerabilityCase")
    return {
        "type": "Add",
        "actor": vendor_id,
        "object": report_dict,
        "target": case_dict,
        "context": case_id,
    }


def _build_add_participant_status_snapshot(
    status: ParticipantStatus,
    participant: CaseParticipant,
    actor_id: str,
    case_id: str,
) -> dict[str, Any]:
    status_dict = _obj_to_inline_dict(status)
    # model_dump renders the PEC dimension as {"consent": {"state": "VALUE"}}.
    # Invariant 9 (and the wire schema) expect the flat key "emConsentState".
    if "consent" in status_dict and "emConsentState" not in status_dict:
        pec_state = status_dict.pop("consent", {}).get("state")
        if pec_state is not None:
            status_dict["emConsentState"] = pec_state
    status_dict.setdefault("type", "ParticipantStatus")
    participant_dict = _obj_to_inline_dict(participant)
    participant_dict.setdefault("type", "CaseParticipant")
    return {
        "type": "Add",
        "actor": actor_id,
        "object": status_dict,
        "target": participant_dict,
        "context": case_id,
    }


def _build_add_case_status_snapshot(
    status: CaseStatus,
    case: VulnerabilityCase,
    vendor_id: str,
    case_id: str,
) -> dict[str, Any]:
    status_dict = _obj_to_inline_dict(status)
    status_dict.setdefault("type", "CaseStatus")
    case_dict = _obj_to_inline_dict(case)
    case_dict.setdefault("type", "VulnerabilityCase")
    return {
        "type": "Add",
        "actor": vendor_id,
        "object": status_dict,
        "target": case_dict,
        "context": case_id,
    }


class WritePrologueLedgerEntriesNode(DataLayerAction):
    """Commit case-initialization prologue entries to the canonical ledger.

    Runs in ``OfferCaseManagerRoleReceivedBT`` after the guarded
    ``offer_case_manager_role`` commit and before ``StoreActivityNode``.
    Reads the persisted
    ``VulnerabilityCase`` and its participants from the DataLayer and commits
    one ledger entry per initialization event in causal order.

    Idempotent: ``CreateLogEntryNode`` (via ``create_commit_log_entry_tree``)
    recognises duplicate entries by ``(case_id, object_id, event_type)`` and
    returns the existing entry without writing again.

    Best-effort: if the case cannot be read (split deployment) or an
    individual entry commit fails (e.g. no genesis hash), the node logs a
    warning and returns ``SUCCESS`` anyway so the enclosing Sequence continues
    to the ``offer_case_manager_role`` entry.

    Per Issue #1688.
    """

    def __init__(
        self,
        case_id: str,
        vendor_id: str,
        name: str | None = None,
    ) -> None:
        """Initialise the node.

        Args:
            case_id: ID of the ``VulnerabilityCase`` whose prologue is written.
            vendor_id: Actor ID of the vendor/coordinator who submitted the
                report and created the case.  Used as the ``actor`` field in
                prologue payload snapshots (these events were performed by the
                vendor, not the CaseActor).
            name: Optional display name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._vendor_id = vendor_id

    def _commit_entry(
        self,
        object_id: str,
        event_type: str,
        payload_snapshot: dict[str, Any],
    ) -> None:
        """Commit a single ledger entry (best-effort; logs warnings on failure)."""
        assert self.datalayer is not None
        assert self.actor_id is not None
        tree = create_commit_log_entry_tree(
            case_id=self._case_id,
            object_id=object_id,
            event_type=event_type,
            payload_snapshot=payload_snapshot,
            disposition="recorded",
        )
        result = BTBridge(
            datalayer=cast(CaseOutboxPersistence, self.datalayer)
        ).execute_with_setup(tree=tree, actor_id=self.actor_id)
        if result.status != Status.SUCCESS:
            self.logger.warning(
                "%s: could not commit %s entry for case '%s': %s"
                " (best-effort prologue — skipping this entry)",
                self.name,
                event_type,
                self._case_id,
                result.feedback_message,
            )

    def _commit_submit_report(self, case: VulnerabilityCase) -> None:
        if not case.vulnerability_reports:
            return

        for report_id in case.vulnerability_reports:
            raw_report = self.datalayer.read(report_id)  # type: ignore[union-attr]
            if not isinstance(raw_report, VulnerabilityReport):
                self.logger.warning(
                    "%s: report '%s' not found — skipping submit_report entry",
                    self.name,
                    report_id,
                )
                continue

            offer_record = _find_offer_record_for_report(
                self.datalayer, report_id
            )
            if offer_record is None:
                report_dict = _obj_to_inline_dict(raw_report)
                report_dict.setdefault("type", "VulnerabilityReport")
                snapshot = {
                    "type": "Offer",
                    "actor": self._vendor_id,
                    "object": report_dict,
                    "to": [self._vendor_id],
                    "context": self._case_id,
                }
                self._commit_entry(report_id, "submit_report", snapshot)
            else:
                snapshot = _build_submit_report_snapshot(
                    offer_record, raw_report, self._vendor_id, self._case_id
                )
                self._commit_entry(
                    offer_record.offer_id, "submit_report", snapshot
                )

    def _commit_create_case(self, case: VulnerabilityCase) -> None:
        snapshot = _build_create_case_snapshot(
            case, self._vendor_id, self._case_id
        )
        self._commit_entry(self._case_id, "create_case", snapshot)

    def _commit_add_report_to_case(self, case: VulnerabilityCase) -> None:
        for report_id in case.vulnerability_reports:
            raw_report = self.datalayer.read(report_id)  # type: ignore[union-attr]
            if not isinstance(raw_report, VulnerabilityReport):
                self.logger.warning(
                    "%s: report '%s' not found — skipping add_report_to_case",
                    self.name,
                    report_id,
                )
                continue
            snapshot = _build_add_report_to_case_snapshot(
                raw_report, case, self._vendor_id, self._case_id
            )
            self._commit_entry(report_id, "add_report_to_case", snapshot)

    def _commit_participant_statuses(self, case: VulnerabilityCase) -> None:
        for participant_ref in case.case_participants:
            participant_id = (
                participant_ref
                if isinstance(participant_ref, str)
                else getattr(participant_ref, "id_", None)
            )
            if not participant_id:
                continue
            raw_participant = self.datalayer.read(participant_id)  # type: ignore[union-attr]
            if not isinstance(raw_participant, CaseParticipant):
                self.logger.warning(
                    "%s: participant '%s' not found — skipping status entries",
                    self.name,
                    participant_id,
                )
                continue

            actor_for_participant = (
                getattr(raw_participant, "attributed_to", None)
                or self._vendor_id
            )

            for status in raw_participant.participant_statuses:
                if not isinstance(status, ParticipantStatus):
                    continue
                status_id = getattr(status, "id_", None)
                if not status_id:
                    continue
                snapshot = _build_add_participant_status_snapshot(
                    status,
                    raw_participant,
                    actor_for_participant,
                    self._case_id,
                )
                self._commit_entry(
                    status_id,
                    "add_participant_status_to_participant",
                    snapshot,
                )

    def _commit_case_status(self, case: VulnerabilityCase) -> None:
        for status_ref in case.case_statuses:
            if isinstance(status_ref, CaseStatus):
                status = status_ref
            elif isinstance(status_ref, str):
                raw = self.datalayer.read(status_ref)  # type: ignore[union-attr]
                if not isinstance(raw, CaseStatus):
                    self.logger.warning(
                        "%s: case_status '%s' not found — skipping",
                        self.name,
                        status_ref,
                    )
                    continue
                status = raw
            else:
                continue

            status_id = getattr(status, "id_", None)
            if not status_id:
                continue
            snapshot = _build_add_case_status_snapshot(
                status, case, self._vendor_id, self._case_id
            )
            self._commit_entry(status_id, "add_case_status_to_case", snapshot)

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        raw_case = self.datalayer.read(self._case_id)
        if not isinstance(raw_case, VulnerabilityCase):
            # Case may not be on this DataLayer instance (split deployment).
            # Best-effort prologue — skip with a warning rather than failing.
            self.logger.warning(
                "%s: case '%s' not found — skipping prologue (best-effort)",
                self.name,
                self._case_id,
            )
            return Status.SUCCESS

        case = raw_case
        self._commit_submit_report(case)
        self._commit_create_case(case)
        self._commit_add_report_to_case(case)
        self._commit_participant_statuses(case)
        self._commit_case_status(case)

        self.logger.info(
            "%s: prologue entries committed for case '%s'",
            self.name,
            self._case_id,
        )
        return Status.SUCCESS
