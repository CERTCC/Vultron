"""Vocabulary examples for the ledger-replication message flow.

Demonstrates ``Announce(as_CaseLedgerEntry)`` and
``Reject(as_CaseLedgerEntry)`` activities as specified in ADR-0077 and
``specs/sync-ledger-replication.yaml`` SYNC-09-002, SYNC-03-001,
SYNC-03-002.
"""

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

from datetime import datetime, timezone

from vultron.wire.as2.factories.sync import (
    announce_log_entry_activity,
    reject_log_entry_activity,
)
from vultron.wire.as2.vocab.examples._base import _CASE_ACTOR, _VENDOR, case
from vultron.wire.as2.vocab.objects.case_ledger_entry import as_CaseLedgerEntry

# Fixed values keep the example output stable across generator runs.
_CASE_URI = case().id_ or "https://vultron.example/cases/00000000"
_ACTIVITY_URI = (
    "https://vultron.example/activities/00000000-0000-0000-0000-000000000001"
)
_ENTRY_URI = f"{_CASE_URI}/ledger/0"
# All-zeros genesis hash for the first entry; fixed 64-char hex for entry hash.
_GENESIS_HASH = "0" * 64
_ENTRY_HASH = "a1b2c3d4" * 8
_RECEIVED_AT = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _example_ledger_entry() -> as_CaseLedgerEntry:
    return as_CaseLedgerEntry(
        id_=_ENTRY_URI,
        case_id=_CASE_URI,
        log_object_id=_ACTIVITY_URI,
        event_type="create_case",
        log_index=0,
        prev_log_hash=_GENESIS_HASH,
        entry_hash=_ENTRY_HASH,
        received_at=_RECEIVED_AT,
    )


def announce_case_ledger_entry():
    """Build ``Announce(CaseLedgerEntry)`` — fan-out replication to participants.

    Sent by the CaseActor to each participant after a log entry has been
    committed to the case event log (SYNC-09-002).
    """
    entry = _example_ledger_entry()
    return announce_log_entry_activity(entry, actor=_CASE_ACTOR.id_)


def reject_case_ledger_entry():
    """Build ``Reject(CaseLedgerEntry)`` — hash-chain mismatch from a participant.

    Sent by a participant to the CaseActor when the incoming
    ``prev_log_hash`` does not match the local ledger tail (SYNC-03-001).
    The ``context`` field carries the last accepted entry hash so the
    CaseActor can determine the replay window (SYNC-03-002).
    """
    entry = _example_ledger_entry()
    return reject_log_entry_activity(
        entry, context=_GENESIS_HASH, actor=_VENDOR.id_
    )
