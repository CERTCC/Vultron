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
from typing import cast

import py_trees
from py_trees.common import Status
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.sync.nodes._helpers import hold_received_announce
from vultron.core.behaviors.sync.nodes.conditions import _require_log_entry
from vultron.core.models.case_ledger import ledger_entry_hash_intact
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.errors import VultronError, VultronWiringError

logger = logging.getLogger(__name__)


class LogDeliveryConfirmationNode(DataLayerActionWithPorts):
    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

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
    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

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


class CheckEntryHashIntactNode(DataLayerConditionWithPorts):
    """Refuse a received entry whose content does not reproduce its hash.

    Runs before the already-stored check and the tail lookup, so an entry
    that fails it is refused and logged, and neither buffered, applied nor
    stored.  No ``Reject(CaseLedgerEntry)`` is sent:
    a replay would resend the same entry, and the replica's unmoved tail
    already makes the next entry ask for one (SYNC-03-006, SYNC-08-001).
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def initialise(self) -> None:
        super().initialise()
        self.activity = self.get_input("activity")

    def update(self) -> Status:
        entry = _require_log_entry(self.activity, self.name)
        if ledger_entry_hash_intact(entry):
            return Status.SUCCESS
        self.logger.error(
            "%s: refusing ledger entry '%s' (case '%s', log_index=%d) in"
            " activity '%s' from actor '%s': its content does not reproduce"
            " its entry_hash %.16s…",
            self.name,
            entry.id_,
            entry.case_id,
            entry.log_index,
            getattr(self.activity, "activity_id", None),
            getattr(self.activity, "actor_id", None),
            entry.entry_hash,
        )
        return Status.FAILURE


class CheckHashMatchesNode(DataLayerConditionWithPorts):
    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
        "tail_hash": PortInformation(data_type=str, required=True),
    }

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
    """Hold the ``Announce`` of a forward-gap entry so it is not dropped.

    When a received entry's ``prev_log_hash`` does not match the local tail
    *and* the entry sits ahead of the tail (``log_index > tail_index + 1``),
    it is a genuine forward gap: a predecessor has not yet been delivered.
    Because delivery is not ordered (and Vultron may not be the only
    implementation on the wire), dropping such an entry can lose it
    permanently.  This node holds the received ``Announce(CaseLedgerEntry)``
    as it arrived, keyed on its entry's ``prev_log_hash``, so the drain
    replays it once its predecessor commits (SYNC-14-001, SYNC-14-009).

    Returns SUCCESS when the ``Announce`` is held, FAILURE otherwise (a
    stale/duplicate entry at-or-behind the tail, no tail, or the size bound
    dropped it).  Its status only structures the enclosing tree — a
    ``Reject(CaseLedgerEntry)`` is sent on **every** mismatch regardless of
    whether holding succeeded, so the CaseActor's replay remains the backstop
    against a predecessor that is genuinely lost (never delivered) rather
    than merely reordered (SYNC-14-002).  The entry is deliberately NOT
    persisted here; its replay applies effects before persisting
    (SYNC-12-001).
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
        "tail_index": PortInformation(data_type=int, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity", "tail_index": "/tail_index"}

    def initialise(self) -> None:
        super().initialise()
        self.activity = self.get_input("activity")
        try:
            self.tail_index: int | None = self.get_input("tail_index")
        except (NoDataAvailable, NotImplementedError):
            self.tail_index = None

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        if self.tail_index is None:
            return Status.FAILURE

        entry = _require_log_entry(self.activity, self.name)

        # Only hold genuine *forward* gaps.  An entry at or behind the tail
        # index is stale, a duplicate, or a fork — not a reorder we can heal by
        # waiting, so let it fall through to the rejection path.
        if entry.log_index <= self.tail_index + 1:
            self.logger.debug(
                "%s: entry index=%d is not a forward gap (tail_index=%d) — "
                "not holding",
                self.name,
                entry.log_index,
                self.tail_index,
            )
            return Status.FAILURE

        if hold_received_announce(
            self.name, self.datalayer, self.activity, self.actor_id
        ):
            self.logger.info(
                "%s: holding the Announce '%s' of out-of-order entry '%s'"
                " (index=%d) for actor '%s' pending predecessor",
                self.name,
                getattr(self.activity, "activity_id", None),
                entry.id_,
                entry.log_index,
                self.actor_id,
            )
            return Status.SUCCESS
        return Status.FAILURE


class BufferPreGenesisEntryNode(DataLayerActionWithPorts):
    """Hold the ``Announce`` of an entry that arrived before its case seed.

    This is the *pre-genesis* companion to :class:`BufferOutOfOrderEntryNode`.
    When ``ReconstructChainTail`` cannot derive the per-case genesis hash
    because the ``VulnerabilityCase`` is not yet present in the DataLayer
    (CLP-08-005), the receive path would otherwise send a
    ``Reject(CaseLedgerEntry)`` and *drop* the entry, leaving convergence to the
    reject → replay round-trip (which can itself reorder and churn — #2169).

    Because delivery is unordered, an ``Announce(CaseLedgerEntry)`` can precede
    the ``Create``/``Announce(VulnerabilityCase)`` that seeds the case.  This
    node holds the received ``Announce`` as it arrived, keyed on its entry's
    ``prev_log_hash``, so the case-seed path replays it once the genesis
    anchor is known (SYNC-15-004, SYNC-15-005).

    Unlike :class:`BufferOutOfOrderEntryNode`, it does **not** apply a
    forward-gap check: there is no reconstructed tail in the pre-genesis window,
    so *every* entry for the missing case is held — including the genesis entry
    (``log_index == 0``), whose ``prev_log_hash`` equals the per-case genesis
    hash and therefore replays first once the case is seeded.

    Returns SUCCESS when the ``Announce`` is held, FAILURE when the size bound
    dropped it.  Its status only structures the enclosing tree — a
    ``Reject(CaseLedgerEntry)`` is sent on every pre-genesis entry regardless,
    so the CaseActor's replay remains the backstop (SYNC-15-001).  The entry
    is deliberately NOT persisted here; its replay applies effects before
    persisting, honouring SYNC-12-001 / SYNC-14-005.
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

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
        if hold_received_announce(
            self.name, self.datalayer, self.activity, self.actor_id
        ):
            self.logger.info(
                "%s: holding the Announce '%s' of pre-genesis entry '%s'"
                " (index=%d) for case '%s', actor '%s', pending"
                " VulnerabilityCase seed",
                self.name,
                getattr(self.activity, "activity_id", None),
                entry.id_,
                entry.log_index,
                entry.case_id,
                self.actor_id,
            )
            return Status.SUCCESS
        return Status.FAILURE


class SendRejectLogEntryNode(DataLayerActionWithPorts):
    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._sync_port: SyncActivityPort | None = None

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
        "tail_hash": PortInformation(data_type=str, required=True),
        "sync_port": PortInformation(data_type=object, required=False),
    }

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
            raise VultronWiringError(
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
