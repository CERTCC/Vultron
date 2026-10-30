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
    - ``vultron/wire/as2/factories/AGENTS.md`` — Architecture Violation section
"""

from enum import StrEnum
from typing import Protocol

from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.ledger_position import LedgerPosition


class ResendOutcome(StrEnum):
    """What :meth:`SyncActivityPort.resend_sealed_activity` did."""

    QUEUED = "queued"
    """The activity's sealed body was queued again, under its first id."""
    PENDING = "pending"
    """An earlier send of the activity is still pending in the outbox, so
    nothing was queued (OX-06-002, SYNC-20-004)."""
    NOT_SEALED = "not-sealed"
    """This store holds no sealed body for the id, so there is nothing to
    resend as first sent (OX-07-001, SYNC-20-003)."""


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
        entry: CaseLedgerEntry,
        tail_hash: str,
        actor_id: str,
        to: list[str],
    ) -> None:
        """Build and queue a ``Reject(CaseLedgerEntry)`` activity.

        Called when a received log entry has a hash-chain mismatch.  The
        reject states the receiver's ledger tail as its ``ledgerPosition``,
        so the CaseActor knows the last entry it applied (SYNC-03-002,
        SYNC-18-001); a receiver that holds no case yet states none.

        Args:
            entry: The domain log entry being rejected.
            tail_hash: The receiver's current chain tail hash, which keys the
                reject's derived id (ID-04-004).
            actor_id: URI of the actor sending the rejection.
            to: List of recipient actor URIs (typically the CaseActor).
        """
        ...

    def send_genesis_replay_reject(
        self,
        case_id: str,
        copy_tail_hash: str,
        actor_id: str,
        to: list[str],
    ) -> None:
        """Build and queue the ``Reject(CaseLedgerEntry)`` that names no entry.

        Called by a replica whose case was replaced by a copy ahead of its
        chain while its chain stores no entry: there is no entry to name, so
        the Reject states the empty chain's position (index -1, SYNC-18-001)
        and names the case as its ``target``, asking for a replay from
        genesis (SYNC-16-007).

        Args:
            case_id: The case to replay.
            copy_tail_hash: The ``entry_hash`` of the tail the replacing copy
                named.  It keeps each request its own: a request for a later
                copy is not a repeat of an earlier one (ID-04-004).
            actor_id: URI of the actor sending the rejection.
            to: List of recipient actor URIs (the CASE_MANAGER).
        """
        ...

    def send_read_ledger_entry(
        self,
        case_id: str,
        ledger_position: LedgerPosition,
        actor_id: str,
        to: list[str],
    ) -> None:
        """Build and queue a ``Read(CaseLedgerEntry)`` position statement.

        Called by a participant to state that it has applied *case_id*'s
        ledger up to *ledger_position*: the tail of its chain, or the
        position a case copy seeded its replica at (SYNC-17-001,
        SYNC-17-008).  The activity names the entry at that position by
        reference, the case as its ``context`` and the position as its
        ``ledgerPosition``.  Each call is a statement of its own, so it
        queues a new activity even when an earlier one named the same entry.

        Args:
            case_id: The case whose ledger position is stated.
            ledger_position: The position stated; it names an entry, so its
                ``log_index`` is not the empty ledger's.
            actor_id: URI of the participant stating its position.
            to: List of recipient actor URIs (the case's CASE_MANAGER).
        """
        ...

    def resend_sealed_activity(self, activity_id: str) -> ResendOutcome:
        """Queue *activity_id* again, exactly as it was first sent.

        The outbox delivers the body sealed when the activity was first
        emitted (OX-07-001), so the resend keeps its id, its
        ``ledgerPosition`` and every other field (SYNC-18-002, SYNC-20-003).
        Nothing is built, stored or ledgered.

        Returns:
            :attr:`ResendOutcome.QUEUED` when a row was queued,
            :attr:`ResendOutcome.PENDING` when an earlier send is still
            pending (SYNC-20-004), and :attr:`ResendOutcome.NOT_SEALED`
            when the store holds no sealed body for the id.

        Spec: SYNC-20-003, SYNC-20-004.
        """
        ...

    def send_announce_log_entry(
        self,
        entry: CaseLedgerEntry,
        actor_id: str,
        to: list[str],
    ) -> bool:
        """Build and queue an ``Announce(CaseLedgerEntry)`` activity.

        Returns ``True`` when a row was queued and ``False`` when an
        ``Announce`` of *entry* to every recipient in *to* was already pending
        in the outbox and nothing was queued (SYNC-15-012).  Callers that fan
        out may ignore the value; a replay counts only ``True`` results as
        entries sent (SYNC-15-011).

        Called when fanning out a committed entry to case participants
        or replaying missing entries to a peer (SYNC-02-002, SYNC-03-002).

        Args:
            entry: The domain log entry to announce.
            actor_id: URI of the CaseActor sending the announcement.
            to: List of recipient actor URIs.
        """
        ...
