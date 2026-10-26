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
SYNC-03-001, SYNC-03-002, SYNC-17-001.
"""

import logging

from pydantic import ValidationError

from vultron.core.models.ledger_position import LedgerPosition
from vultron.wire.as2.factories.errors import VultronActivityConstructionError
from vultron.wire.as2.vocab.activities.sync import (
    _AnnounceLogEntryActivity,
    _ReadLogEntryActivity,
    _RejectLogEntryActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Announce,
    as_Read,
    as_Reject,
)
from vultron.wire.as2.vocab.objects.case_ledger_entry import as_CaseLedgerEntry

logger = logging.getLogger(__name__)


def announce_log_entry_activity(
    entry: as_CaseLedgerEntry,
    **kwargs,
) -> as_Announce:
    """Build an Announce(CaseLedgerEntry) — fan-out replication to participants.

    Sent by the CaseActor to each participant actor after a new log
    entry has been committed to the case event log (SYNC-09-002).

    Args:
        entry: The ``CaseLedgerEntry`` being replicated.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Announce`` whose ``object_`` is the log entry.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _AnnounceLogEntryActivity(object_=entry, **kwargs)
    except ValidationError as exc:
        logger.warning(
            "announce_log_entry_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "announce_log_entry_activity: invalid arguments"
        ) from exc


def reject_log_entry_activity(
    entry: as_CaseLedgerEntry,
    context: str | None = None,
    **kwargs,
) -> as_Reject:
    """Build a Reject(CaseLedgerEntry) — hash-chain mismatch report.

    Sent by a participant to the CaseActor when an incoming
    ``Announce(CaseLedgerEntry)``'s ``prev_log_hash`` does not match the
    participant's local tail hash (SYNC-03-001).

    Args:
        entry: The ``CaseLedgerEntry`` the receiver could not apply.
        context: The last applied entry hash string, so the CaseActor
            can determine which entries need to be replayed.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Reject`` whose ``object_`` is the unapplied log entry and
        ``context`` carries the last applied hash.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _RejectLogEntryActivity(
            object_=entry, context=context, **kwargs
        )
    except ValidationError as exc:
        logger.warning("reject_log_entry_activity: invalid arguments: %s", exc)
        raise VultronActivityConstructionError(
            "reject_log_entry_activity: invalid arguments"
        ) from exc


def genesis_replay_reject_activity(case_id: str, **kwargs) -> as_Reject:
    """Build the Reject(CaseLedgerEntry) that names no entry (SYNC-16-007).

    Sent by a replica whose case was replaced by a copy ahead of its chain
    and whose chain stores no entry: there is nothing to name, so it asks
    for a replay from genesis.  The last-accepted hash is empty and the case
    is the ``target``.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _RejectLogEntryActivity(target=case_id, context="", **kwargs)
    except ValidationError as exc:
        logger.warning(
            "genesis_replay_reject_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "genesis_replay_reject_activity: invalid arguments"
        ) from exc


def read_ledger_entry_activity(
    entry: as_CaseLedgerEntry,
    **kwargs,
) -> as_Read:
    """Build a Read(CaseLedgerEntry) — a participant's ledger position statement.

    Sent by a participant to the case's CASE_MANAGER to state that it has
    applied the case's ledger up to *entry* (SYNC-17-001).  The entry goes by
    reference: the ``object`` is its id, the ``context`` its case, and the
    ``ledgerPosition`` its ``log_index`` and ``entry_hash``.

    Args:
        entry: The last ledger entry the participant has applied.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``, ``id_``).

    Returns:
        An ``as_Read`` naming *entry* by reference.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _ReadLogEntryActivity(
            object_=entry.id_,
            context=entry.case_id,
            ledger_position=LedgerPosition(
                log_index=entry.log_index, entry_hash=entry.entry_hash
            ),
            **kwargs,
        )
    except ValidationError as exc:
        logger.warning(
            "read_ledger_entry_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "read_ledger_entry_activity: invalid arguments"
        ) from exc
