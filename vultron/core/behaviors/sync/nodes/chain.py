#!/usr/bin/env python
#
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
"""Action nodes for SYNC chain reconstruction and log entry creation."""

from __future__ import annotations

import logging
from typing import Any, Literal, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models._helpers import _now_utc
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
from vultron.core.models.protocols import is_log_entry_model
from vultron.core.sync_helpers import _find_equivalent_recorded_entry
from vultron.core.sync_helpers import _reconstruct_tail_hash
from vultron.errors import VultronCanonicalEntryError
from vultron.errors import VultronError

logger = logging.getLogger(__name__)

_CANONICAL_PAYLOAD_SIGNATURES: tuple[tuple[str, str], ...] = (
    ("Create", "VulnerabilityCase"),
    ("Offer", "VulnerabilityReport"),
    ("Offer", "VulnerabilityCase"),
    # Accept(Offer(VulnerabilityReport)) — validate_report (RV message).
    # The payload object is the Offer wrapping the VulnerabilityReport.
    ("Accept", "Offer"),
    # TentativeReject(Offer(VulnerabilityReport)) — invalidate_report (RI).
    ("TentativeReject", "Offer"),
    # Reject(Offer(VulnerabilityReport)) — close_report (RC).
    ("Reject", "Offer"),
    # Read(Offer(VulnerabilityReport)) — ack_report (RK message, ADR-0021).
    ("Read", "Offer"),
    ("Add", "Note"),
    ("Add", "ParticipantStatus"),
    ("Add", "EmbargoEvent"),
    ("Remove", "EmbargoEvent"),
    ("Offer", "EmbargoEvent"),
    ("Invite", "EmbargoEvent"),
    ("Accept", "EmbargoEvent"),
    ("Reject", "EmbargoEvent"),
    ("Join", "VulnerabilityCase"),
    ("Ignore", "VulnerabilityCase"),
    ("Leave", "VulnerabilityCase"),
    ("Invite", "VulnerabilityCase"),
    ("Accept", "Invite"),
    ("Reject", "Invite"),
    ("Announce", "VulnerabilityCase"),
)
_CASE_AUTHORED_SIGNATURES: frozenset[tuple[str, str]] = frozenset(
    {
        ("Announce", "VulnerabilityCase"),
        ("Add", "EmbargoEvent"),
        ("Remove", "EmbargoEvent"),
        ("Invite", "EmbargoEvent"),
        ("Offer", "VulnerabilityCase"),
        # Leave(VulnerabilityCase) is emitted by the case-actor's
        # AutoCloseBranchNode when all participants reach RM.CLOSED.
        # The case-actor is the canonical author of this closure assertion.
        ("Leave", "VulnerabilityCase"),
    }
)
_INLINE_OBJECT_KEYS: frozenset[str] = frozenset(
    {"object", "object_", "target"}
)


def _require_log_entry(
    activity: Any, node_name: str
) -> VultronCaseLedgerEntry:
    entry = getattr(activity, "log_entry", None)
    if entry is None:
        entry = getattr(activity, "object_", None)
    if is_log_entry_model(entry):
        if isinstance(entry, VultronCaseLedgerEntry):
            return entry
        return VultronCaseLedgerEntry.model_validate(
            entry.model_dump(mode="json")
        )
    raise VultronError(
        f"{node_name}: activity did not carry a VultronCaseLedgerEntry"
    )


def _require_case_id_from_activity(activity: Any, node_name: str) -> str:
    entry = getattr(activity, "log_entry", None)
    if entry is None:
        entry = getattr(activity, "rejected_entry", None)
    if entry is None:
        entry = getattr(activity, "object_", None)
    if is_log_entry_model(entry):
        return entry.case_id
    raise VultronError(f"{node_name}: could not resolve case_id from activity")


def _to_persistable_entry(
    chain_entry: HashChainLedgerRecord,
) -> VultronCaseLedgerEntry:
    return VultronCaseLedgerEntry(
        case_id=chain_entry.case_id,
        log_index=chain_entry.log_index,
        disposition=chain_entry.disposition,
        term=chain_entry.term,
        log_object_id=chain_entry.object_id,
        event_type=chain_entry.event_type,
        payload_snapshot=dict(chain_entry.payload_snapshot),
        prev_log_hash=chain_entry.prev_log_hash,
        entry_hash=chain_entry.entry_hash,
        reason_code=chain_entry.reason_code,
        reason_detail=chain_entry.reason_detail,
    )


def _snapshot_type(snapshot: dict[str, Any]) -> str | None:
    activity_type = snapshot.get("type") or snapshot.get("type_")
    return (
        activity_type
        if isinstance(activity_type, str) and activity_type
        else None
    )


def _snapshot_object_type(snapshot: dict[str, Any]) -> str | None:
    snapshot_object = snapshot.get("object")
    if not isinstance(snapshot_object, dict):
        snapshot_object = snapshot.get("object_")
    if not isinstance(snapshot_object, dict):
        return None
    object_type = snapshot_object.get("type") or snapshot_object.get("type_")
    return (
        object_type if isinstance(object_type, str) and object_type else None
    )


def _bare_inline_object_path(
    value: Any, path: str = "payloadSnapshot"
) -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in _INLINE_OBJECT_KEYS and isinstance(child, str):
                return child_path
            nested_path = _bare_inline_object_path(child, child_path)
            if nested_path is not None:
                return nested_path
        return None
    if isinstance(value, list):
        for index, item in enumerate(value):
            nested_path = _bare_inline_object_path(item, f"{path}[{index}]")
            if nested_path is not None:
                return nested_path
    return None


def _validate_canonical_entry(
    *,
    case_id: str,
    actor_id: str | None,
    case_actor_id: str | None = None,
    disposition: str,
    payload_snapshot: dict[str, Any],
    event_type: str,
) -> None:
    # Validation runs before idempotency check so malformed entries are
    # rejected outright and never reach the equivalence lookup (CLP-07).
    if disposition != "recorded":
        # Rejected entries carry the refused payload for audit purposes;
        # structural validation is relaxed for non-recorded dispositions.
        return
    if not payload_snapshot:
        raise VultronCanonicalEntryError(
            f"{event_type}: recorded canonical entries require a non-empty "
            "payloadSnapshot"
        )

    snapshot_actor = payload_snapshot.get("actor")
    if not isinstance(snapshot_actor, str) or not snapshot_actor:
        raise VultronCanonicalEntryError(
            f"{event_type}: payloadSnapshot.actor must be a non-empty URI"
        )

    activity_type = _snapshot_type(payload_snapshot)
    object_type = _snapshot_object_type(payload_snapshot)
    signature = (activity_type or "", object_type or "")

    bare_reference_path = _bare_inline_object_path(payload_snapshot)
    if bare_reference_path is not None:
        raise VultronCanonicalEntryError(
            f"{event_type}: {bare_reference_path} must be an inline object, "
            "not a bare ID string"
        )

    if signature not in _CANONICAL_PAYLOAD_SIGNATURES:
        raise VultronCanonicalEntryError(
            f"{event_type}: payloadSnapshot type/object pair {signature!r} "
            "is not canonical"
        )

    # CLP-07-003: only CaseActor-authored activities may have the CaseActor as
    # snapshot actor; all participant-originated activities must have a
    # participant (non-CaseActor) actor.
    if (
        case_actor_id
        and snapshot_actor == case_actor_id
        and signature not in _CASE_AUTHORED_SIGNATURES
    ):
        raise VultronCanonicalEntryError(
            f"{event_type}: payloadSnapshot.actor must not be the CaseActor"
            f" for non-case-authored entries (signature={signature!r})"
        )

    context = payload_snapshot.get("context")
    if context != case_id:
        raise VultronCanonicalEntryError(
            f"{event_type}: payloadSnapshot.context must equal the case URI"
        )


class ReconstructChainTailNode(DataLayerAction):
    def __init__(
        self, case_id: str | None = None, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="tail_hash", access=py_trees.common.Access.WRITE
        )
        self.blackboard.register_key(
            key="tail_index", access=py_trees.common.Access.WRITE
        )
        if self._case_id is None:
            self.blackboard.register_key(
                key="activity", access=py_trees.common.Access.READ
            )

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE

        if self._case_id is not None:
            case_id = self._case_id
        else:
            case_id = _require_case_id_from_activity(
                self.blackboard.activity, self.name
            )

        tail_hash, tail_index = _reconstruct_tail_hash(case_id, self.datalayer)
        self.blackboard.tail_hash = tail_hash
        self.blackboard.tail_index = tail_index
        self.logger.debug(
            "%s: reconstructed case '%s' tail hash %.16s… at index %d",
            self.name,
            case_id,
            tail_hash,
            tail_index,
        )
        return Status.SUCCESS


class UpdateReplicationStateNode(DataLayerAction):
    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE

        from vultron.core.models.replication_state import (
            VultronReplicationState,
        )

        activity = self.blackboard.activity
        entry = getattr(activity, "rejected_entry", None)
        if entry is None:
            entry = getattr(activity, "object_", None)
        if not is_log_entry_model(entry):
            raise VultronError(
                f"{self.name}: activity did not carry a VultronCaseLedgerEntry"
            )

        if isinstance(entry, VultronCaseLedgerEntry):
            rejected_entry = entry
        else:
            rejected_entry = VultronCaseLedgerEntry.model_validate(
                entry.model_dump(mode="json")
            )

        peer_id = activity.actor_id
        if not peer_id:
            raise VultronError(
                f"{self.name}: Reject(CaseLedgerEntry) missing peer actor_id"
            )

        state = VultronReplicationState(
            case_id=rejected_entry.case_id,
            peer_id=peer_id,
            last_acknowledged_hash=activity.last_accepted_hash,
        )
        existing = self.datalayer.read(state.id_)
        if existing is not None:
            existing_state = cast(VultronReplicationState, existing)
            existing_state.last_acknowledged_hash = activity.last_accepted_hash
            existing_state.updated_at = _now_utc()
            self.datalayer.save(existing_state)
        else:
            self.datalayer.save(state)
        return Status.SUCCESS


class CreateLogEntryNode(DataLayerAction):
    def __init__(
        self,
        case_id: str,
        object_id: str,
        event_type: str,
        *,
        payload_snapshot: dict[str, Any] | None = None,
        term: int | None = None,
        reason_code: str | None = None,
        reason_detail: str | None = None,
        disposition: Literal["recorded", "rejected"] = "recorded",
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.object_id = object_id
        self.event_type = event_type
        self.payload_snapshot = payload_snapshot or {}
        self.term = term
        self.reason_code = reason_code
        self.reason_detail = reason_detail
        self.disposition: Literal["recorded", "rejected"] = disposition

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="tail_hash", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="tail_index", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="log_entry", access=py_trees.common.Access.WRITE
        )
        self.blackboard.register_key(
            key="log_entry_preexisting", access=py_trees.common.Access.WRITE
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE

        from vultron.core.use_cases._helpers import _find_case_actor_id

        case_actor_id = _find_case_actor_id(self.datalayer, self.case_id)
        _validate_canonical_entry(
            case_id=self.case_id,
            actor_id=self.actor_id,
            case_actor_id=case_actor_id,
            disposition=self.disposition,
            payload_snapshot=self.payload_snapshot,
            event_type=self.event_type,
        )

        existing = _find_equivalent_recorded_entry(
            case_id=self.case_id,
            object_id=self.object_id,
            event_type=self.event_type,
            payload_snapshot=self.payload_snapshot,
            dl=self.datalayer,
        )
        if existing is not None:
            if isinstance(existing, VultronCaseLedgerEntry):
                entry = existing
            else:
                entry = VultronCaseLedgerEntry.model_validate(
                    existing.model_dump(mode="json")
                )
            self.blackboard.log_entry = entry
            self.blackboard.log_entry_preexisting = True
            self.logger.info(
                "%s: reusing existing log entry case_id=%s event_type=%s "
                "log_index=%d",
                self.name,
                entry.case_id,
                entry.event_type,
                entry.log_index,
            )
            return Status.SUCCESS

        tail_hash = self.blackboard.tail_hash
        tail_index = self.blackboard.tail_index
        chain_entry = HashChainLedgerRecord(
            case_id=self.case_id,
            log_index=tail_index + 1,
            object_id=self.object_id,
            event_type=self.event_type,
            disposition=self.disposition,
            payload_snapshot=self.payload_snapshot,
            prev_log_hash=tail_hash,
            term=self.term,
            reason_code=self.reason_code,
            reason_detail=self.reason_detail,
        )
        self.blackboard.log_entry = _to_persistable_entry(chain_entry)
        self.blackboard.log_entry_preexisting = False
        return Status.SUCCESS


class PersistLogEntryNode(DataLayerAction):
    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="log_entry", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="log_entry_preexisting", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE

        entry = cast(VultronCaseLedgerEntry, self.blackboard.log_entry)
        try:
            preexisting = bool(self.blackboard.log_entry_preexisting)
        except KeyError:
            preexisting = False
        if preexisting:
            self.logger.info(
                "%s: log entry already exists for case_id=%s event_type=%s "
                "log_index=%d actor_id=%s",
                self.name,
                entry.case_id,
                entry.event_type,
                entry.log_index,
                self.actor_id,
            )
            return Status.SUCCESS

        self.datalayer.save(entry)
        self.logger.info(
            "%s: committed log entry case_id=%s event_type=%s log_index=%d actor_id=%s",
            self.name,
            entry.case_id,
            entry.event_type,
            entry.log_index,
            self.actor_id,
        )
        self.logger.debug(
            "%s: entry_hash=%.16s… payload_snapshot=%s",
            self.name,
            entry.entry_hash,
            entry.payload_snapshot,
        )
        return Status.SUCCESS
