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

"""Ownership-transfer *offer* condition and ledger backfill nodes.

Provides :class:`IsOfferOwnershipTransferEventNode` and
:class:`ApplyOfferOwnershipTransferFromLedgerNode`, which together form the
``OfferOwnershipTransferEffects`` slot in ``create_announce_log_entry_tree``.

When a participant receives ``Announce(CaseLedgerEntry)`` for the
``offer_case_ownership_transfer`` entry, the backfill node extracts the offer
id and case id from the entry's ``payloadSnapshot`` and stores a
:class:`~vultron.core.models.ownership_transfer_offer_record.VultronOwnershipTransferOfferRecord`
in the local DataLayer.  This makes the offer readable by
``SvcAcceptCaseOwnershipTransferUseCase._prepare``, which calls
``dl.read(offer_id)`` and 404s when the object is absent (#2195).

Per ADR-0035 DL-06-002, SYNC-02-002, SYNC-12-001, CM-21-005, ISSUE-2195.

(CM-21-005 governs the offer hop this slot materializes — the offer is addressed
to the CaseActor inbox and forwarded by it.  CM-21-007, which covers the ledger
commit and broadcast that follow a successful *accept*, is a different hop.)
"""

from __future__ import annotations

from typing import Any

from py_trees.common import Status
from pydantic import ValidationError

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
    PortInformation,
)

_OFFER_CASE_OWNERSHIP_TRANSFER_EVENT = "offer_case_ownership_transfer"


class IsOfferOwnershipTransferEventNode(DataLayerConditionWithPorts):
    """Precondition: SUCCESS when entry IS an offer_case_ownership_transfer event.

    Used as the precondition in the ``OfferOwnershipTransferEffects`` Selector's
    inner Sequence in ``AnnounceLogEntryReceivedBT``::

        Selector(OfferOwnershipTransferEffects)
          Sequence
            IsOfferOwnershipTransferEventNode   <- SUCCESS iff event_type matches
            ApplyOfferOwnershipTransferFromLedgerNode
          Inverter(IsOfferOwnershipTransferEventNode)  <- SUCCESS iff wrong type

    The Inverter fires SUCCESS only when the condition does NOT match (routing
    no-op for the wrong event type).  When the condition matches but
    ApplyOfferOwnershipTransferFromLedgerNode returns FAILURE — i.e. the effect
    itself could not be applied — both branches of the Selector fail and the
    FAILURE propagates to block PersistReceivedLogEntry, so the entry is not
    persisted without its effects (SYNC-12-001).

    Per BTND-08-001, BTND-08-002, CM-21-005, SYNC-02-002, SYNC-12-001.
    """

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
        from vultron.core.behaviors.sync.nodes.conditions import (
            _require_log_entry,
        )

        entry = _require_log_entry(self.activity, self.name)
        if entry.event_type == _OFFER_CASE_OWNERSHIP_TRANSFER_EVENT:
            return Status.SUCCESS
        return Status.FAILURE


class ApplyOfferOwnershipTransferFromLedgerNode(DataLayerActionWithPorts):
    """Apply an ``offer_case_ownership_transfer`` ledger entry to the local DataLayer.

    When a participant receives ``Announce(CaseLedgerEntry)`` for the
    canonical ``offer_case_ownership_transfer`` entry, this node extracts
    ``offer_id`` and ``case_id`` from the entry's ``payloadSnapshot`` and
    stores a :class:`~vultron.core.models.ownership_transfer_offer_record.VultronOwnershipTransferOfferRecord`
    keyed by ``offer_id``.

    This is the SYNC-path equivalent of what ``OfferCaseOwnershipTransferReceivedUseCase``
    does on the HTTP-inbox path: the replica MUST hold a readable record so that
    ``SvcAcceptCaseOwnershipTransferUseCase._prepare`` can call
    ``dl.read(offer_id)`` without a 404 (#2195).

    Idempotent: if the object is already present the node returns SUCCESS
    without overwriting.

    Status contract — the distinction matters for SYNC-12-001, which forbids
    persisting a ledger entry whose effects did not apply:

    - **Nothing to apply** → SUCCESS.  The snapshot carries no offer id, or no
      case id, or is not a dict at all.  There is no effect to fail; the entry
      is still a valid ledger fact and must not be blocked.  A partially
      populated record is *not* written — one that cannot name its case would
      only convert ``_prepare``'s "offer not found" 404 into "case not found in
      offer" (#2195).
    - **Effect failed** → FAILURE.  The record was well-formed but the
      DataLayer write raised.  That is a genuine effect failure, so the node
      fails and the surrounding Selector blocks ``PersistReceivedLogEntry``.

    Per ADR-0035 DL-06-002 (domain facts from a received protocol message MUST
    be recorded as core state at extraction time), SYNC-02-002, SYNC-12-001,
    CM-21-005, ISSUE-2195.
    """

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

        from vultron.core.behaviors.sync.nodes.conditions import (
            _require_log_entry,
        )

        entry = _require_log_entry(self.activity, self.name)
        snapshot = (
            entry.payload_snapshot
            if isinstance(entry.payload_snapshot, dict)
            else {}
        )

        offer_id = snapshot.get("id") or getattr(entry, "log_object_id", None)
        if not offer_id:
            self.logger.debug(
                "%s: offer_case_ownership_transfer entry has no id"
                " — nothing to apply (non-fatal)",
                self.name,
            )
            return Status.SUCCESS

        if self.datalayer.read(offer_id) is not None:
            self.logger.debug(
                "%s: offer '%s' already present — idempotent no-op",
                self.name,
                offer_id,
            )
            return Status.SUCCESS

        case_id = _case_id_from_snapshot(snapshot)
        if not case_id:
            self.logger.warning(
                "%s: offer '%s' snapshot carries no resolvable case id"
                " — declining to store a record that cannot name its case"
                " (nothing to apply, non-fatal)",
                self.name,
                offer_id,
            )
            return Status.SUCCESS

        return self._save_offer_record(
            offer_id,
            case_id,
            actor_id=_id_from_snapshot_field(snapshot.get("actor")),
            target_id=_id_from_snapshot_field(snapshot.get("target")),
        )

    def _save_offer_record(
        self,
        offer_id: str,
        case_id: str,
        actor_id: str | None = None,
        target_id: str | None = None,
    ) -> Status:
        """Build and persist the record; FAILURE only if the write itself fails."""
        assert self.datalayer is not None
        from vultron.core.models.ownership_transfer_offer_record import (
            VultronOwnershipTransferOfferRecord,
        )

        try:
            record = VultronOwnershipTransferOfferRecord(
                offer_id=offer_id,
                case_id=case_id,
                actor_id=actor_id,
                target_id=target_id,
            )
        except ValidationError as exc:
            # Malformed snapshot data, not a failed effect — stay lenient so a
            # bad payload cannot wedge ledger replication (SYNC-12-001 applies
            # to effects that fail, not to entries with nothing to apply).
            self.logger.warning(
                "%s: offer '%s' snapshot did not validate into a"
                " VultronOwnershipTransferOfferRecord: %s",
                self.name,
                offer_id,
                exc,
            )
            return Status.SUCCESS

        try:
            self.datalayer.save(record)
        except Exception as exc:
            # A well-formed effect that could not be written IS a failed
            # effect: fail so the Selector blocks PersistReceivedLogEntry and
            # the entry is not persisted without it (SYNC-12-001).
            self.logger.error(
                "%s: could not store VultronOwnershipTransferOfferRecord"
                " for offer '%s': %s",
                self.name,
                offer_id,
                exc,
            )
            return Status.FAILURE

        self.logger.info(
            "%s: stored VultronOwnershipTransferOfferRecord '%s' for case '%s'"
            " from ledger snapshot (ADR-0035 DL-06-002, ISSUE-2195)",
            self.name,
            offer_id,
            case_id,
        )
        return Status.SUCCESS


def _id_from_snapshot_field(field: Any) -> str | None:
    """Return the URI carried by a snapshot field, or ``None``.

    Snapshot fields may be an inline dict (``{"id": ..., "type": ...}``) or a
    bare URI string, depending on how the activity was serialized.
    """
    if isinstance(field, dict):
        value = field.get("id")
        return value if isinstance(value, str) and value else None
    if isinstance(field, str) and field:
        return field
    return None


def _case_id_from_snapshot(snapshot: dict[str, Any]) -> str:
    """Extract the offered case URI from a snapshot ``object`` field."""
    return _id_from_snapshot_field(snapshot.get("object")) or ""
