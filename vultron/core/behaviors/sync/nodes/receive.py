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
"""Action nodes for SYNC log-replication receive workflows."""

from __future__ import annotations

import logging
from typing import Any, cast

import py_trees
from py_trees.common import Status
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.ledger_gap_buffer import LedgerGapBuffer
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.errors import VultronError

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


class LogDeliveryConfirmationNode(DataLayerActionWithPorts):
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
        entry = _require_log_entry(self.activity, self.name)
        self.logger.debug(
            "%s: received round-trip delivery confirmation for log entry '%s'",
            self.name,
            entry.id_,
        )
        return Status.SUCCESS


class PersistReceivedLogEntryNode(DataLayerActionWithPorts):
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
        entry = _require_log_entry(self.activity, self.name)
        self.datalayer.save(entry)
        self.logger.info(
            "%s: stored received log entry '%s' for case '%s'",
            self.name,
            entry.id_,
            entry.case_id,
        )
        return Status.SUCCESS


class CheckHashMatchesNode(DataLayerConditionWithPorts):
    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["activity"] = PortInformation(data_type=object, required=True)
        ports["tail_hash"] = PortInformation(data_type=str, required=True)
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity", "tail_hash": "/tail_hash"}

    def initialise(self) -> None:
        super().initialise()
        self.activity = self.get_input("activity")
        self.tail_hash: str = self.get_input("tail_hash")

    def update(self) -> Status:
        entry = _require_log_entry(self.activity, self.name)
        if entry.prev_log_hash == self.tail_hash:
            return Status.SUCCESS
        return Status.FAILURE


class BufferOutOfOrderEntryNode(DataLayerActionWithPorts):
    """Hold a forward-gap ledger entry so it is not permanently dropped.

    When a received entry's ``prev_log_hash`` does not match the local tail
    *and* the entry sits ahead of the tail (``log_index > tail_index + 1``),
    it is a genuine forward gap: a predecessor has not yet been delivered.
    Because delivery is not ordered (and Vultron may not be the only
    implementation on the wire), dropping such an entry can lose it
    permanently.  This node parks the entry in the actor-local
    :class:`~vultron.core.models.ledger_gap_buffer.LedgerGapBuffer` keyed by its
    ``prev_log_hash`` so the receive path can drain it once its predecessor
    arrives (issue #1556, SYNC-10-004).

    Returns SUCCESS when the entry was buffered, FAILURE otherwise (buffering
    disabled, no gap buffer injected, a stale/duplicate entry at-or-behind the
    tail, or the size bound dropped it).  Its status only structures the
    enclosing tree — a ``Reject(CaseLedgerEntry)`` is sent on **every** mismatch
    regardless of whether buffering succeeded, so the CaseActor's replay remains
    the backstop against a predecessor that is genuinely lost (never delivered)
    rather than merely reordered.  The entry is deliberately NOT persisted here;
    the drain applies effects before persisting, honouring SYNC-12-001.
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._gap_buffer: LedgerGapBuffer | None = None

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["activity"] = PortInformation(data_type=object, required=True)
        ports["tail_index"] = PortInformation(data_type=int, required=False)
        ports["gap_buffer"] = PortInformation(data_type=object, required=False)
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "activity": "/activity",
            "tail_index": "/tail_index",
            "gap_buffer": "/gap_buffer",
        }

    def initialise(self) -> None:
        super().initialise()
        self.activity = self.get_input("activity")
        try:
            self.tail_index: int | None = self.get_input("tail_index")
        except (NoDataAvailable, NotImplementedError):
            self.tail_index = None
        try:
            self._gap_buffer = cast(
                LedgerGapBuffer, self.get_input("gap_buffer")
            )
        except (NoDataAvailable, NotImplementedError):
            self._gap_buffer = None

    def update(self) -> Status:
        if self._gap_buffer is None or self.tail_index is None:
            return Status.FAILURE

        entry = _require_log_entry(self.activity, self.name)

        # Only buffer genuine *forward* gaps.  An entry at or behind the tail
        # index is stale, a duplicate, or a fork — not a reorder we can heal by
        # waiting, so let it fall through to the rejection path.
        if entry.log_index <= self.tail_index + 1:
            self.logger.debug(
                "%s: entry index=%d is not a forward gap (tail_index=%d) — "
                "not buffering",
                self.name,
                entry.log_index,
                self.tail_index,
            )
            return Status.FAILURE

        if self._gap_buffer.buffer(entry):
            self.logger.info(
                "%s: buffered out-of-order entry '%s' (index=%d) pending "
                "predecessor",
                self.name,
                entry.id_,
                entry.log_index,
            )
            return Status.SUCCESS
        return Status.FAILURE


class BufferPreGenesisEntryNode(DataLayerActionWithPorts):
    """Hold a ledger entry that arrived before its ``VulnerabilityCase`` seed.

    This is the *pre-genesis* companion to :class:`BufferOutOfOrderEntryNode`.
    When ``ReconstructChainTail`` cannot derive the per-case genesis hash
    because the ``VulnerabilityCase`` is not yet present in the DataLayer
    (CLP-08-005), the receive path would otherwise send a
    ``Reject(CaseLedgerEntry)`` and *drop* the entry, leaving convergence to the
    reject → replay round-trip (which can itself reorder and churn — #2169).

    Because delivery is unordered, an ``Announce(CaseLedgerEntry)`` can precede
    the ``Create``/``Announce(VulnerabilityCase)`` that seeds the case.  This
    node parks the entry in the actor-local
    :class:`~vultron.core.models.ledger_gap_buffer.LedgerGapBuffer` keyed by its
    ``prev_log_hash`` so the case-seed path can drain it once the genesis anchor
    is known (issue #2186, SYNC-15-004).

    Unlike :class:`BufferOutOfOrderEntryNode`, it does **not** apply a
    forward-gap check: there is no reconstructed tail in the pre-genesis window,
    so *every* entry for the missing case is held — including the genesis entry
    (``log_index == 0``), whose ``prev_log_hash`` equals the per-case genesis
    hash and therefore drains first once the case is seeded.

    Returns SUCCESS when the entry was buffered, FAILURE otherwise (buffering
    disabled, no gap buffer injected, or the size bound dropped it).  Its status
    only structures the enclosing tree — a ``Reject(CaseLedgerEntry)`` is sent
    on every pre-genesis entry regardless, so the CaseActor's replay remains the
    backstop (SYNC-15-001).  The entry is deliberately NOT persisted here; the
    drain applies effects before persisting, honouring SYNC-12-001 / SYNC-14-005.
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._gap_buffer: LedgerGapBuffer | None = None

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["activity"] = PortInformation(data_type=object, required=True)
        ports["gap_buffer"] = PortInformation(data_type=object, required=False)
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity", "gap_buffer": "/gap_buffer"}

    def initialise(self) -> None:
        super().initialise()
        self.activity = self.get_input("activity")
        try:
            self._gap_buffer = cast(
                LedgerGapBuffer, self.get_input("gap_buffer")
            )
        except (NoDataAvailable, NotImplementedError):
            self._gap_buffer = None

    def update(self) -> Status:
        if self._gap_buffer is None:
            return Status.FAILURE

        entry = _require_log_entry(self.activity, self.name)
        if self._gap_buffer.buffer(entry):
            self.logger.info(
                "%s: buffered pre-genesis entry '%s' (index=%d) for case '%s' "
                "pending VulnerabilityCase seed",
                self.name,
                entry.id_,
                entry.log_index,
                entry.case_id,
            )
            return Status.SUCCESS
        return Status.FAILURE


class SendRejectLogEntryNode(DataLayerActionWithPorts):
    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._sync_port: SyncActivityPort | None = None

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["activity"] = PortInformation(data_type=object, required=True)
        ports["tail_hash"] = PortInformation(data_type=str, required=True)
        ports["sync_port"] = PortInformation(data_type=object, required=False)
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "activity": "/activity",
            "tail_hash": "/tail_hash",
            "sync_port": "/sync_port",
        }

    def initialise(self) -> None:
        super().initialise()
        self.activity = self.get_input("activity")
        self.tail_hash: str = self.get_input("tail_hash")
        try:
            self._sync_port = cast(
                SyncActivityPort, self.get_input("sync_port")
            )
        except (NoDataAvailable, NotImplementedError):
            self._sync_port = None

    def update(self) -> Status:
        if self.actor_id is None:
            self.logger.error("%s: actor_id not available", self.name)
            return Status.FAILURE

        entry = _require_log_entry(self.activity, self.name)

        sender_id = getattr(self.activity, "actor_id", None)
        if self._sync_port is None:
            raise VultronError(
                f"{self.name}: sync_port must be injected to send rejection"
            )
        if not sender_id:
            raise VultronError(
                f"{self.name}: activity.actor_id missing for rejection target"
            )

        self.logger.warning(
            "%s: log entry '%s' prev_log_hash %.16s… does not match local tail "
            "%.16s…; sending Reject(CaseLedgerEntry)",
            self.name,
            entry.id_,
            entry.prev_log_hash,
            self.tail_hash,
        )
        self._sync_port.send_reject_log_entry(
            entry=entry,
            tail_hash=self.tail_hash,
            actor_id=self.actor_id,
            to=[sender_id],
        )
        return Status.FAILURE


class CheckHashOrRejectOnMismatchNode(py_trees.composites.Selector):
    """Accept a chain-extending entry, or buffer-and-reject a mismatch.

    Structure::

        Selector(CheckHashOrRejectOnMismatch)
          CheckHashMatches                      ← SUCCESS: entry extends tail
          Sequence(BufferAndReject)
            FailureIsSuccess(BufferOutOfOrderEntry)  ← buffer forward gaps; the
                                                        wrapper lets the reject
                                                        fire whether or not the
                                                        entry was buffered
            SendRejectLogEntry                  ← FAILURE: reject sent, entry
                                                  not persisted this pass

    When the hash matches, the Selector short-circuits SUCCESS and the parent
    Sequence proceeds to apply effects and persist.  On a mismatch, the entry
    is buffered when it is a genuine forward gap (so it is not permanently
    dropped) and a ``Reject(CaseLedgerEntry)`` is always sent as the loss
    backstop; the Selector then returns FAILURE so ``PersistReceivedLogEntry``
    does not run for the out-of-order entry (issue #1556, SYNC-10-004).
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(
            name=name or self.__class__.__name__,
            memory=False,
            children=[
                CheckHashMatchesNode(name="CheckHashMatches"),
                py_trees.composites.Sequence(
                    name="BufferAndReject",
                    memory=False,
                    children=[
                        py_trees.decorators.FailureIsSuccess(
                            name="BufferIfForwardGap",
                            child=BufferOutOfOrderEntryNode(
                                name="BufferOutOfOrderEntry"
                            ),
                        ),
                        SendRejectLogEntryNode(name="SendRejectLogEntry"),
                    ],
                ),
            ],
        )
