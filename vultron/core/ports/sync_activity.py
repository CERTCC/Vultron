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

from datetime import datetime
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
        *,
        in_reply_to: str,
        asked_at: datetime | None = None,
        at: datetime,
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
            in_reply_to: The id of the inbound activity that prompted the
                Reject, which it names in ``inReplyTo`` (RF-08-004): the
                ``Add(CaseLedgerEntry)`` of *entry*, or the
                ``Announce(VulnerabilityCase)`` whose copy is ahead of the
                chain (SYNC-16-007).
            asked_at: For a genesis Reject from a receiver that holds no
                case yet, when it asked; it keys the id too, so a request
                after the interval is a new activity, not a redelivery the
                CASE_MANAGER drops (SYNC-15-017, ID-02-001).  ``None`` for
                every other Reject.
        """
        ...

    def send_read_ledger(
        self,
        case_id: str,
        ledger_position: LedgerPosition,
        actor_id: str,
        to: list[str],
        *,
        at: datetime,
    ) -> None:
        """Build and queue a ``Read(<case>/ledger)`` position statement.

        Called by a participant to state, of its own accord, that it has
        applied *case_id*'s ledger up to *ledger_position*: the tail of its
        chain, or the position a case copy seeded its replica at, index -1
        when that is the empty ledger's (SYNC-17-001, SYNC-17-008).  The
        activity's object is the case's ledger, its ``context`` the case and
        its ``ledgerPosition`` the position; the CASE_MANAGER replays every
        entry after it (SYNC-17-004).  Each call is a statement of its own,
        so it queues a new activity even when an earlier one stated the same
        position.

        Args:
            case_id: The case whose ledger position is stated.
            ledger_position: The position stated.
            actor_id: URI of the participant stating its position.
            to: List of recipient actor URIs (the case's CASE_MANAGER).
        """
        ...

    def send_empty_chain_read(
        self,
        case_id: str,
        copy_tail_hash: str,
        actor_id: str,
        to: list[str],
        *,
        in_reply_to: str,
        at: datetime,
    ) -> None:
        """Build and queue the ``Read(<case>/ledger)`` that answers a case copy.

        Called by a replica whose case was replaced by a copy ahead of its
        chain while its chain stores no entry: it states the empty chain's
        position, index -1 with the case's genesis hash, which asks the
        CASE_MANAGER for every entry (SYNC-16-027).  Unlike
        :meth:`send_read_ledger`, this ``Read`` answers one inbound
        activity, so its id is derived from what it asks for: a repeat for
        the same copy queues the same activity again, never a new one
        (ID-04-004).

        Args:
            case_id: The case whose ledger is asked for.
            copy_tail_hash: The ``entry_hash`` of the tail the replacing copy
                named.  It keys the id, so a request after a later copy is
                its own, not a repeat of an earlier one.
            actor_id: URI of the replica stating its position.
            to: List of recipient actor URIs (the case's CASE_MANAGER).
            in_reply_to: The id of the ``Announce(VulnerabilityCase)`` whose
                copy replaced the case, which the ``Read`` names in
                ``inReplyTo`` (RF-08-004).  It does not key the id.
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

    def send_add_log_entry(
        self,
        entry: CaseLedgerEntry,
        actor_id: str,
        to: list[str],
        *,
        at: datetime,
    ) -> bool:
        """Build and queue an ``Add(CaseLedgerEntry)`` activity.

        The ``Add`` adds *entry* to its case's ledger, ``<case>/ledger``, with
        ``context`` the case and ``inReplyTo`` the act the entry commits, so
        it is that act's positive acknowledgement (ADR-0204).  *entry*'s
        snapshot must state the act's id.

        Returns ``True`` when a row was queued and ``False`` when an
        ``Add`` of *entry* to every recipient in *to* was already pending
        in the outbox and nothing was queued (SYNC-15-012).  Callers that fan
        out may ignore the value; a replay counts only ``True`` results as
        entries sent (SYNC-15-011).

        Called when fanning out a committed entry to case participants
        or replaying missing entries to a peer (SYNC-02-003, SYNC-03-002).

        Args:
            entry: The domain log entry to add to the ledger.
            actor_id: URI of the CASE_MANAGER sending the ``Add``.
            to: List of recipient actor URIs.
        """
        ...
