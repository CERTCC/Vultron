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

from datetime import UTC, datetime

from vultron.core.models.case_ledger import HashChainLedgerRecord
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
# The first entry's predecessor is the example case's own genesis hash, never a
# shared constant (CLP-08-001, CLP-08-002).
_GENESIS_HASH = case().genesis_hash
_RECEIVED_AT = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)


def _example_ledger_entry() -> as_CaseLedgerEntry:
    # Built through the hashed record, so the example's ``entryHash`` is the
    # hash of its own content, as a receiver checks (SYNC-03-006).
    return HashChainLedgerRecord(
        case_id=_CASE_URI,
        log_index=0,
        object_id=_ACTIVITY_URI,
        semantic_type="create_case",
        prev_log_hash=_GENESIS_HASH,
        received_at=_RECEIVED_AT,
    ).to_ledger_entry()


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
    The ``context`` field carries the last applied entry hash so the
    CaseActor can determine the replay window (SYNC-03-002).
    """
    entry = _example_ledger_entry()
    return reject_log_entry_activity(
        entry, context=_GENESIS_HASH, actor=_VENDOR.id_
    )
