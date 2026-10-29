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

import logging

from pydantic import ValidationError

from vultron.core.models.case_ledger_entry import ledger_entry_id
from vultron.core.models.ledger_position import (
    EMPTY_LEDGER_LOG_INDEX,
    LedgerPosition,
)
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
    **kwargs,
) -> as_Reject:
    """Build a Reject(CaseLedgerEntry) — hash-chain mismatch report.

    Sent by a participant to the CaseActor when an incoming
    ``Announce(CaseLedgerEntry)``'s ``prev_log_hash`` does not match the
    participant's local tail hash (SYNC-03-001).  ``context`` names the
    entry's case.  The participant's tail, which the CaseActor replays
    after, is the ``ledgerPosition`` every case activity states
    (SYNC-18-001), stamped by :func:`stamp_ledger_position` when the sender
    holds the case.

    Args:
        entry: The ``CaseLedgerEntry`` the receiver could not apply.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``, ``id_``).

    Returns:
        An ``as_Reject`` whose ``object_`` is the unapplied log entry.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    kwargs.setdefault("context", getattr(entry, "case_id", None))
    try:
        return _RejectLogEntryActivity(object_=entry, **kwargs)
    except ValidationError as exc:
        logger.warning("reject_log_entry_activity: invalid arguments: %s", exc)
        raise VultronActivityConstructionError(
            "reject_log_entry_activity: invalid arguments"
        ) from exc


def genesis_replay_reject_activity(
    case_id: str, ledger_position: LedgerPosition, **kwargs
) -> as_Reject:
    """Build the Reject(CaseLedgerEntry) that names no entry (SYNC-16-007).

    Sent by a replica whose case was replaced by a copy ahead of its chain
    and whose chain stores no entry: there is nothing to name, so it asks
    for a replay from genesis.  Its *ledger_position* is the sender's tail,
    which for a chain that stores no entry is index -1 and the case's
    genesis hash (SYNC-18-001, CLP-08-004); the case is both the ``target``
    and the ``context``.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails,
            including a *ledger_position* that names an entry: a sender
            that holds one names it instead (``as_Reject``).
    """
    try:
        return _RejectLogEntryActivity(
            target=case_id,
            context=case_id,
            ledger_position=ledger_position,
            **kwargs,
        )
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
    ``ledgerPosition`` its ``log_index`` and ``entry_hash``.  It is
    :func:`read_ledger_position_activity` for the entry's own position.

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
        position = LedgerPosition(
            log_index=entry.log_index, entry_hash=entry.entry_hash
        )
    except ValidationError as exc:
        logger.warning(
            "read_ledger_entry_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "read_ledger_entry_activity: invalid arguments"
        ) from exc
    return read_ledger_position_activity(entry.case_id, position, **kwargs)


def read_ledger_position_activity(
    case_id: str,
    ledger_position: LedgerPosition,
    **kwargs,
) -> as_Read:
    """Build a Read(CaseLedgerEntry) stating *ledger_position* in *case_id*.

    The same position statement as :func:`read_ledger_entry_activity`, for
    a sender that knows the position but does not store the entry there: a
    participant whose replica a case copy has just seeded holds the case at
    the copy's position before its chain stores any entry (SYNC-16-007).  The
    entry goes by reference, its id derived from its ledger coordinates
    (:func:`~vultron.core.models.case_ledger_entry.ledger_entry_id`); the
    ``context`` is the case and the ``ledgerPosition`` the position.

    Args:
        case_id: The case whose ledger the position is in.
        ledger_position: The position the sender states, which names an
            entry.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``, ``id_``).

    Returns:
        An ``as_Read`` naming the entry at *ledger_position* by reference.

    Raises:
        VultronActivityConstructionError: If *ledger_position* is the empty
            ledger's, which names no entry (SYNC-17-001), or Pydantic
            validation fails.
    """
    if ledger_position.log_index == EMPTY_LEDGER_LOG_INDEX:
        raise VultronActivityConstructionError(
            "read_ledger_position_activity: the empty ledger's position names"
            " no entry to state (SYNC-17-001)"
        )
    try:
        return _ReadLogEntryActivity(
            object_=ledger_entry_id(case_id, ledger_position.log_index),
            context=case_id,
            ledger_position=ledger_position,
            **kwargs,
        )
    except ValidationError as exc:
        logger.warning(
            "read_ledger_position_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "read_ledger_position_activity: invalid arguments"
        ) from exc
