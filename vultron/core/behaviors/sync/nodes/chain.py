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

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.sync.nodes.canonical_entry import (
    _validate_canonical_entry,
)
from vultron.core.models._helpers import _now_utc
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.sync_helpers import _find_equivalent_recorded_entry
from vultron.core.sync_helpers import _reconstruct_tail_hash
from vultron.errors import VultronError
from vultron.errors import VultronValidationError

logger = logging.getLogger(__name__)


def _require_log_entry(
    activity: Any, node_name: str
) -> VultronCaseLedgerEntry:
    entry = getattr(activity, "log_entry", None)
    if entry is None:
        entry = getattr(activity, "object_", None)
    if isinstance(entry, CaseLedgerEntry):
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
    if isinstance(entry, CaseLedgerEntry):
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


class ReconstructChainTailNode(DataLayerActionWithPorts):
    def __init__(
        self, case_id: str | None = None, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["activity"] = PortInformation(data_type=object, required=False)
        return ports

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {
            "tail_hash": PortInformation(data_type=object, required=True),
            "tail_index": PortInformation(data_type=object, required=True),
        }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "activity": "/activity",
            "tail_hash": "/tail_hash",
            "tail_index": "/tail_index",
        }

    def initialise(self) -> None:
        super().initialise()
        if self._case_id is None:
            try:
                self.activity = self.get_input("activity")
            except Exception:
                self.activity = None
        else:
            self.activity = None

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        if self._case_id is not None:
            case_id = self._case_id
        else:
            case_id = _require_case_id_from_activity(self.activity, self.name)

        try:
            tail_hash, tail_index = _reconstruct_tail_hash(
                case_id, self.datalayer
            )
        except VultronValidationError as exc:
            # _reconstruct_tail_hash raises here for exactly one condition:
            # an empty local ledger with no per-case genesis hash yet — the
            # pre-genesis bootstrap window where an Announce(CaseLedgerEntry)
            # arrived before the Create(VulnerabilityCase) that seeds genesis.
            # This is an expected, self-healing situation, NOT a fault: the
            # downstream ReconstructOrRejectOnMissingCase selector fires a
            # Reject(CaseLedgerEntry) carrying the empty tail_hash sentinel,
            # prompting the CaseActor to replay from genesis (SYNC-15-001,
            # CLP-08-005).  Log at WARNING so this designed recovery does not
            # surface as spurious ERROR noise on replica containers (#2169).
            # (Genuine chain corruption — hash mismatch, index gaps — is
            # handled separately by CheckHashOrRejectOnMismatchNode and never
            # reaches this branch.)
            self.logger.warning(
                "%s: pre-genesis window for case '%s' — sending Reject to "
                "replay from genesis (CLP-08-005): %s",
                self.name,
                case_id,
                exc,
            )
            # Write sentinel values so the downstream reject node can fire even
            # though the tree would normally stop at this FAILURE.  An empty
            # tail_hash signals "replay from genesis" to the CaseActor
            # (SYNC-15-001, CLP-08-005).
            self._set_output("tail_hash", "")
            self._set_output("tail_index", -1)
            return Status.FAILURE
        self._set_output("tail_hash", tail_hash)
        self._set_output("tail_index", tail_index)
        self.logger.debug(
            "%s: reconstructed case '%s' tail hash %.16s… at index %d",
            self.name,
            case_id,
            tail_hash,
            tail_index,
        )
        return Status.SUCCESS


class UpdateReplicationStateNode(DataLayerActionWithPorts):
    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["activity"] = PortInformation(data_type=object, required=True)
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def initialise(self) -> None:
        super().initialise()
        self.activity = self.get_input("activity")

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        activity = self.activity
        entry = getattr(activity, "rejected_entry", None)
        if entry is None:
            entry = getattr(activity, "object_", None)
        if not isinstance(entry, CaseLedgerEntry):
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


class CreateLogEntryNode(DataLayerActionWithPorts):
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
        self.payload_snapshot = dict(payload_snapshot or {})
        self.term = term
        self.reason_code = reason_code
        self.reason_detail = reason_detail
        self.disposition: Literal["recorded", "rejected"] = disposition

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["tail_hash"] = PortInformation(data_type=object, required=True)
        ports["tail_index"] = PortInformation(data_type=object, required=True)
        return ports

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {
            "log_entry": PortInformation(data_type=object, required=True),
            "log_entry_preexisting": PortInformation(
                data_type=object, required=True
            ),
        }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "tail_hash": "/tail_hash",
            "tail_index": "/tail_index",
            "log_entry": "/log_entry",
            "log_entry_preexisting": "/log_entry_preexisting",
        }

    def initialise(self) -> None:
        super().initialise()
        self.tail_hash = self.get_input("tail_hash")
        self.tail_index = self.get_input("tail_index")

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

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
            self._set_output("log_entry", entry)
            self._set_output("log_entry_preexisting", True)
            self.logger.info(
                "%s: reusing existing log entry case_id=%s event_type=%s "
                "log_index=%d",
                self.name,
                entry.case_id,
                entry.event_type,
                entry.log_index,
            )
            return Status.SUCCESS

        tail_hash = self.tail_hash
        tail_index = self.tail_index
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
        self._set_output("log_entry", _to_persistable_entry(chain_entry))
        self._set_output("log_entry_preexisting", False)
        return Status.SUCCESS


class PersistLogEntryNode(DataLayerActionWithPorts):
    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["log_entry"] = PortInformation(data_type=object, required=True)
        ports["log_entry_preexisting"] = PortInformation(
            data_type=bool, required=False
        )
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "log_entry": "/log_entry",
            "log_entry_preexisting": "/log_entry_preexisting",
        }

    def initialise(self) -> None:
        super().initialise()
        self.log_entry = self.get_input("log_entry")
        self.log_entry_preexisting: bool = self.get_input(
            "log_entry_preexisting", default=False
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        entry = cast(VultronCaseLedgerEntry, self.log_entry)
        preexisting = bool(self.log_entry_preexisting)
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
