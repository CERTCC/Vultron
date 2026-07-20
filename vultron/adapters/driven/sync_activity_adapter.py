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

"""Adapter implementing :class:`~vultron.core.ports.sync_activity.SyncActivityPort`.

Converts :class:`~vultron.core.models.case_ledger_entry.CaseLedgerEntry`
objects to wire-layer
:class:`~vultron.wire.as2.vocab.objects.case_ledger_entry.CaseLedgerEntry`
objects, builds the appropriate AS2 activity via factory functions, persists
the activity, and queues it to the actor's outbox for delivery.

This adapter is the **sole** location where sync-related domain→wire
translation occurs, keeping ``vultron/core/`` free of wire-layer imports
(ARCH-01-001).

See also:
    - ``vultron/core/ports/sync_activity.py`` — port Protocol
    - ``vultron/wire/as2/factories/sync.py`` — factory functions
    - ``vultron/wire/as2/factories/AGENTS.md``
"""

import logging

from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.use_cases._helpers import add_activity_to_outbox
from vultron.wire.as2.factories import (
    announce_log_entry_activity,
    reject_log_entry_activity,
)
from vultron.wire.as2.vocab.objects.case_ledger_entry import (
    as_CaseLedgerEntry as WireCaseLedgerEntry,
)

logger = logging.getLogger(__name__)


class SyncActivityAdapter:
    """Adapter for :class:`~vultron.core.ports.sync_activity.SyncActivityPort`.

    Owns the full domain→wire→persist→outbox pipeline for sync activities.
    Core use cases pass domain objects and never touch wire types.
    """

    def __init__(self, dl: CaseOutboxPersistence) -> None:
        self._dl = dl

    def _to_wire(self, entry: CaseLedgerEntry) -> WireCaseLedgerEntry:
        """Convert a log entry to its wire-layer representation."""
        return WireCaseLedgerEntry.model_validate(
            entry.model_dump(mode="json")
        )

    def send_reject_log_entry(
        self,
        entry: CaseLedgerEntry,
        tail_hash: str,
        actor_id: str,
        to: list[str],
    ) -> None:
        """Build and queue a ``Reject(CaseLedgerEntry)`` activity.

        Spec: SYNC-03-001.
        """
        wire_entry = self._to_wire(entry)
        reject = reject_log_entry_activity(
            entry=wire_entry,
            context=tail_hash,
            actor=actor_id,
            to=to,
        )
        self._dl.save(reject)
        self._dl.outbox_append(reject.id_)
        logger.info(
            "sync adapter: queued Reject(CaseLedgerEntry) '%s' → %s",
            reject.id_,
            to,
        )

    def send_announce_log_entry(
        self,
        entry: CaseLedgerEntry,
        actor_id: str,
        to: list[str],
    ) -> None:
        """Build and queue an ``Announce(CaseLedgerEntry)`` activity.

        Uses actor-aware outbox queueing via
        :func:`~vultron.core.use_cases._helpers.add_activity_to_outbox`.

        Spec: SYNC-02-002, SYNC-03-002.
        """
        wire_entry = self._to_wire(entry)
        announce = announce_log_entry_activity(
            entry=wire_entry,
            actor=actor_id,
            to=to,
        )
        self._dl.save(announce)
        add_activity_to_outbox(actor_id, announce.id_, self._dl)
        logger.info(
            "sync adapter: queued Announce(CaseLedgerEntry) '%s' → %s",
            announce.id_,
            to,
        )
