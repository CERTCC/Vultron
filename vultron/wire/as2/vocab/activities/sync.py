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
"""Wire-layer AS2 activity classes for LedgerFanout/LedgerReconciliation log replication.

Provides :class:`_AnnounceLogEntryActivity` used by the CaseActor to fan
out canonical log entries to participant actors, and
:class:`_RejectLogEntryActivity` used by participants to report hash-chain
mismatches back to the CaseActor, and :class:`_ReadLogEntryActivity` used by
participants to state their ledger position (SYNC-17-001).
"""

from typing import Any

from pydantic import Field

from vultron.core.models.ledger_position import LedgerPosition
from vultron.primitives import NonEmptyString
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Announce,
    as_Read,
    as_Reject,
)
from vultron.wire.as2.vocab.objects.case_ledger_entry import (
    as_CaseLedgerEntry,
)


class _AnnounceLogEntryActivity(as_Announce):
    """The CaseActor is announcing a canonical as_CaseLedgerEntry for replication.

    Sent to each participant actor after a new log entry has been committed
    to the case event log (SYNC-09-002).

    object_: :class:`~vultron.core.models.case_ledger_entry.CaseLedgerEntry`
        being replicated.
    """

    object_: as_CaseLedgerEntry = Field(
        default=...,
        validation_alias="object",
        serialization_alias="object",
    )


class _RejectLogEntryActivity(as_Reject):
    """Participant rejects a ``as_CaseLedgerEntry`` announcement due to hash-chain mismatch.

    Sent by a participant actor to the CaseActor when the incoming
    ``Announce(as_CaseLedgerEntry)``'s ``prev_log_hash`` does not match the
    participant's local tail hash.

    The ``context`` field (inherited from ``as_Object``) carries the
    last applied entry hash as a plain string so the CaseActor can
    determine which entries need to be replayed (SYNC-03-001).

    object_: :class:`~vultron.wire.as2.vocab.objects.case_ledger_entry.as_CaseLedgerEntry`
        the receiver could not apply, or absent when the receiver holds no
        entry and asks for a replay from genesis.  Then ``context`` is empty
        and ``target`` names the case (SYNC-16-007).
    context: Last applied entry hash string.

    Spec: SYNC-03-001, SYNC-03-002, SYNC-16-007.
    """

    object_: as_CaseLedgerEntry | None = Field(  # type: ignore[assignment]
        default=None,
        validation_alias="object",
        serialization_alias="object",
    )

    # context carries the last_accepted_hash as a plain string and is
    # inherited from as_Object as ``context: Any | None = None``.
    context: Any = Field(  # type: ignore[assignment]
        default=None,
    )


class _ReadLogEntryActivity(as_Read):
    """Participant states its ledger position: ``Read(CaseLedgerEntry)``.

    Sent by a participant to the case's CASE_MANAGER to state that it has
    applied the case's ledger up to the entry it names (SYNC-17-001,
    ADR-0155).  ``Read`` states a fact and asks for nothing; the
    CASE_MANAGER answers a lag with a replay (SYNC-17-004).

    object_: the id of the last canonical entry the participant has applied,
        by reference.
    context: the case the entry belongs to.
    ledger_position: the entry's ``logIndex`` and ``entryHash``, so the
        CASE_MANAGER can tell a lag from a position its ledger does not hold
        (SYNC-17-005).

    Spec: SYNC-17-001.
    """

    object_: NonEmptyString = Field(  # type: ignore[assignment]
        default=...,
        validation_alias="object",
        serialization_alias="object",
    )
    context: NonEmptyString = Field(  # type: ignore[assignment]
        default=...,
    )
    ledger_position: LedgerPosition = Field(  # type: ignore[assignment]
        default=...,
        validation_alias="ledgerPosition",
        serialization_alias="ledgerPosition",
    )
