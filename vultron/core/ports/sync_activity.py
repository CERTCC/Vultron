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

"""Driven port for emitting sync-related wire activities.

Core use cases call these fire-and-forget methods with domain objects.
The adapter handles domain→wire conversion, persistence, and outbox
queueing. Core modules MUST NOT import wire-layer types directly
(ARCH-01-001); this port is the boundary.

See also:
    - ``vultron/adapters/driven/sync_activity_adapter.py`` — adapter
    - ``specs/architecture.yaml`` ARCH-01-001
    - ``notes/activity-factories.md`` — Architecture Violation section
"""

from typing import Protocol

from vultron.core.models.case_log_entry import VultronCaseLogEntry


class SyncActivityPort(Protocol):
    """Driven port for sync-related outbound activity construction.

    Methods are fire-and-forget: the adapter converts the domain log
    entry to its wire representation, builds the appropriate AS2
    activity via factory functions, persists the activity, and queues
    it to the actor's outbox for delivery.

    Core use cases and trigger functions accept this port as a
    parameter alongside ``CasePersistence`` / ``CaseOutboxPersistence``.
    """

    def send_reject_log_entry(
        self,
        entry: VultronCaseLogEntry,
        tail_hash: str,
        actor_id: str,
        to: list[str],
    ) -> None:
        """Build and queue a ``Reject(CaseLogEntry)`` activity.

        Called when a received log entry has a hash-chain mismatch.
        The reject carries *tail_hash* as context so the CaseActor
        knows the receiver's last accepted hash (SYNC-03-001).

        Args:
            entry: The domain log entry being rejected.
            tail_hash: The receiver's current chain tail hash.
            actor_id: URI of the actor sending the rejection.
            to: List of recipient actor URIs (typically the CaseActor).
        """
        ...

    def send_announce_log_entry(
        self,
        entry: VultronCaseLogEntry,
        actor_id: str,
        to: list[str],
    ) -> None:
        """Build and queue an ``Announce(CaseLogEntry)`` activity.

        Called when fanning out a committed entry to case participants
        or replaying missing entries to a peer (SYNC-02-002, SYNC-03-002).

        Args:
            entry: The domain log entry to announce.
            actor_id: URI of the CaseActor sending the announcement.
            to: List of recipient actor URIs.
        """
        ...
