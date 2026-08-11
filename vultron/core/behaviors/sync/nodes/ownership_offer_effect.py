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

Per ADR-0035 DL-06-002, SYNC-02-002, CM-21-007, ISSUE-2195.
"""

from __future__ import annotations

from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction, DataLayerCondition

_OFFER_CASE_OWNERSHIP_TRANSFER_EVENT = "offer_case_ownership_transfer"


class IsOfferOwnershipTransferEventNode(DataLayerCondition):
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
    ApplyOfferOwnershipTransferFromLedgerNode fails, both branches of the
    Selector fail and the FAILURE propagates to block PersistReceivedLogEntry
    (SYNC-12-001).

    Per BTND-08-001, BTND-08-002, CM-21-007, SYNC-02-002, SYNC-12-001.
    """

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        from vultron.core.behaviors.sync.nodes.conditions import (
            _require_log_entry,
        )

        entry = _require_log_entry(self.blackboard.activity, self.name)
        if entry.event_type == _OFFER_CASE_OWNERSHIP_TRANSFER_EVENT:
            return Status.SUCCESS
        return Status.FAILURE


class ApplyOfferOwnershipTransferFromLedgerNode(DataLayerAction):
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
    without overwriting.  Lenient on missing or unparse-able data — if the
    snapshot cannot be reconstructed into a typed offer activity, the node
    logs a warning and returns SUCCESS to avoid blocking the ``Announce``
    processing flow.

    Per ADR-0035 DL-06-002 (domain facts from a received protocol message MUST
    be recorded as core state at extraction time), SYNC-02-002, CM-21-007,
    ISSUE-2195.
    """

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        from vultron.core.behaviors.sync.nodes.conditions import (
            _require_log_entry,
        )
        from vultron.core.models.ownership_transfer_offer_record import (
            VultronOwnershipTransferOfferRecord,
        )

        entry = _require_log_entry(self.blackboard.activity, self.name)
        snapshot = (
            entry.payload_snapshot
            if isinstance(entry.payload_snapshot, dict)
            else {}
        )

        offer_id = snapshot.get("id") or getattr(entry, "log_object_id", None)
        if not offer_id:
            self.logger.debug(
                "%s: offer_case_ownership_transfer entry has no id"
                " — skipping (non-fatal)",
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

        # Extract case_id from the snapshot's object field (dict or bare string).
        object_field = snapshot.get("object")
        if isinstance(object_field, dict):
            case_id = object_field.get("id", "")
        elif isinstance(object_field, str):
            case_id = object_field
        else:
            case_id = ""

        try:
            record = VultronOwnershipTransferOfferRecord(
                offer_id=offer_id,
                object_=case_id,
            )
            self.datalayer.save(record)
            self.logger.info(
                "%s: stored VultronOwnershipTransferOfferRecord '%s'"
                " from ledger snapshot (ADR-0035 DL-06-002, ISSUE-2195)",
                self.name,
                offer_id,
            )
        except Exception as exc:
            self.logger.warning(
                "%s: could not store VultronOwnershipTransferOfferRecord"
                " for offer '%s': %s",
                self.name,
                offer_id,
                exc,
            )

        return Status.SUCCESS
