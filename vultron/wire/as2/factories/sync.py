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
"""
Factory functions for outbound Vultron case-ledger synchronization activities.

These are the sole public construction API for LedgerFanout/LedgerReconciliation log
replication activities. Internal activity subclasses are imported here
and MUST NOT be imported by callers.

Spec: ``specs/activity-factories.yaml`` AF-01-001 through AF-04-003.
Spec: ``specs/sync-ledger-replication.yaml`` SYNC-09-002,
SYNC-03-001, SYNC-03-002, SYNC-17-001, SYNC-18-001.
"""

from datetime import datetime

from vultron.core.models.case_ledger_entry import case_ledger_id
from vultron.core.models.ledger_position import LedgerPosition
from vultron.errors import VultronCanonicalEntryError
from vultron.wire.as2.factories._construct import (
    build_activity,
    guarded_build,
)
from vultron.wire.as2.vocab.activities.sync import (
    _AddLogEntryActivity,
    _ReadLedgerActivity,
    _RejectLogEntryActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Add,
    as_Read,
    as_Reject,
)
from vultron.wire.as2.vocab.base.objects.collections import (
    as_OrderedCollection,
)
from vultron.wire.as2.vocab.objects.case_ledger_entry import as_CaseLedgerEntry


def add_log_entry_activity(
    entry: as_CaseLedgerEntry,
    *,
    at: datetime,
    **kwargs,
) -> as_Add:
    """Build an Add(CaseLedgerEntry): a commit, fanned out to participants.

    Sent by the CASE_MANAGER to each active participant after a new entry
    has been committed to the case ledger (SYNC-09-002).  The ``Add`` adds
    the entry to the case's ledger, ``<case>/ledger``, its ``target``; its
    ``context`` is the case; and its ``inReplyTo`` is the act the entry
    commits, so it is that act's positive acknowledgement (ADR-0204).  All
    three are read from *entry*, so a caller cannot misname them.  It lists
    nothing in ``result`` (SYNC-02-009).

    Args:
        entry: The ``CaseLedgerEntry`` being replicated.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Add`` whose ``object_`` is the log entry.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails, or
            the entry's snapshot names no committed act.
    """
    return build_activity(
        "add_log_entry_activity",
        _AddLogEntryActivity,
        at,
        lambda: {**_ledger_add_fields(entry), **kwargs},
        also=(VultronCanonicalEntryError,),
    )


def _ledger_add_fields(entry: as_CaseLedgerEntry) -> dict[str, object]:
    """The fields an ``Add`` of *entry* reads from it (ADR-0204).

    Anything but an entry is passed on as the object alone, which the
    activity class refuses.

    Raises:
        VultronCanonicalEntryError: *entry*'s snapshot names no act.
    """
    if not isinstance(entry, as_CaseLedgerEntry):
        return {"object_": entry}
    return {
        "object_": entry,
        "target": case_ledger_id(entry.context),
        "context": entry.context,
        "in_reply_to": entry.committed_act_id(),
    }


def reject_log_entry_activity(
    entry: as_CaseLedgerEntry,
    in_reply_to: str,
    *,
    at: datetime,
    **kwargs,
) -> as_Reject:
    """Build a Reject(CaseLedgerEntry) — hash-chain mismatch report.

    Sent by a participant to the CaseActor when an incoming
    ``Add(CaseLedgerEntry)``'s ``prev_log_hash`` does not match the
    participant's local tail hash (SYNC-03-001).  ``context`` names the
    entry's case.  The participant's tail, which the CaseActor replays
    after, is the ``ledgerPosition`` every case activity states
    (SYNC-18-001), stamped by :func:`stamp_ledger_position` when the sender
    holds the case.

    Args:
        entry: The ``CaseLedgerEntry`` the receiver could not apply.
        in_reply_to: The id of the inbound activity that prompted the
            Reject: the ``Add(CaseLedgerEntry)``, or the
            ``Announce(VulnerabilityCase)`` whose copy is ahead of the
            chain (RF-08-004).
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``, ``id_``).

    Returns:
        An ``as_Reject`` whose ``object_`` is the unapplied log entry.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    kwargs.setdefault("context", getattr(entry, "context", None))
    return build_activity(
        "reject_log_entry_activity",
        _RejectLogEntryActivity,
        at,
        lambda: {"object_": entry, "in_reply_to": in_reply_to, **kwargs},
    )


def read_ledger_at_entry_activity(
    entry: as_CaseLedgerEntry,
    *,
    at: datetime,
    **kwargs,
) -> as_Read:
    """Build ``Read(<case>/ledger)`` stating the position of *entry*.

    Sent by a participant to the case's CASE_MANAGER to state that it has
    applied the case's ledger up to *entry* (SYNC-17-001).  It is
    :func:`read_ledger_position_activity` for the entry's case and position.

    Args:
        entry: The last ledger entry the participant has applied.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``, ``id_``).

    Returns:
        An ``as_Read`` of *entry*'s case's ledger.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    position = guarded_build(
        "read_ledger_at_entry_activity",
        lambda: LedgerPosition(
            log_index=entry.log_index, entry_hash=entry.entry_hash
        ),
    )
    return read_ledger_position_activity(
        entry.context, position, **kwargs, at=at
    )


def read_ledger_position_activity(
    case_id: str,
    ledger_position: LedgerPosition,
    *,
    at: datetime,
    **kwargs,
) -> as_Read:
    """Build ``Read(<case>/ledger)``: a participant's ledger position statement.

    The participant states its tail in *case_id*'s ledger: the last entry
    it holds, the position a case copy seeded its replica at
    (SYNC-16-023), or the empty ledger's, index -1 with the case's genesis
    hash, when it holds no entry (SYNC-17-001, SYNC-16-027).  The CASE_MANAGER
    replays every entry after it (SYNC-17-004).  The ``object`` is the
    case's ledger, an ``OrderedCollection`` with identity only (ADR-0204);
    the ``context`` is the case and the ``ledgerPosition`` the position.

    Args:
        case_id: The case whose ledger the position is in.
        ledger_position: The position the sender states.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``, ``id_``, ``in_reply_to``).

    Returns:
        An ``as_Read`` of the case's ledger.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    return build_activity(
        "read_ledger_position_activity",
        _ReadLedgerActivity,
        at,
        lambda: {
            "object_": as_OrderedCollection(
                id_=case_ledger_id(case_id), published=None, updated=None
            ),
            "context": case_id,
            "ledger_position": ledger_position,
            **kwargs,
        },
    )
