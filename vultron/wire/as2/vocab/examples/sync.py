"""Vocabulary examples for the ledger-replication message flow.

Demonstrates ``Add(CaseLedgerEntry)``,
``Reject(CaseLedgerEntry)`` and ``Read(<case>/ledger)`` activities as
specified in ADR-0077, ADR-0155 and ``specs/sync-ledger-replication.yaml``
SYNC-09-002, SYNC-03-001, SYNC-03-002, SYNC-17-001.
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
from vultron.core.models.ledger_position import LedgerPosition
from vultron.wire.as2.factories.sync import (
    add_log_entry_activity,
    read_ledger_at_entry_activity,
    reject_log_entry_activity,
)
from vultron.wire.as2.vocab.examples._base import (
    _CASE_ACTOR,
    _VENDOR,
    EXAMPLE_TIMESTAMP,
    case,
)
from vultron.wire.as2.vocab.objects.case_ledger_entry import as_CaseLedgerEntry

# Fixed values keep the example entries' own fields stable across generator
# runs; the case URI and its genesis hash come from the example case.
_CASE_URI = case().id_ or "https://vultron.example/cases/00000000"
# The first entry's predecessor is the example case's own genesis hash, never a
# shared constant (CLP-08-001, CLP-08-002).
_GENESIS_HASH = case().genesis_hash
_RECEIVED_AT = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)


def _example_record(
    log_index: int, semantic_type: str, prev_log_hash: str
) -> HashChainLedgerRecord:
    # Built through the hashed record, so the example's ``entryHash`` is the
    # hash of its own content, as a receiver checks (SYNC-03-006).
    act_id = (
        "https://vultron.example/activities/"
        f"00000000-0000-0000-0000-{log_index + 1:012d}"
    )
    return HashChainLedgerRecord(
        case_id=_CASE_URI,
        log_index=log_index,
        object_id=act_id,
        semantic_type=semantic_type,
        # The committed act, which the entry's Add names in inReplyTo
        # (ADR-0204); trimmed to its id for the example.
        payload_snapshot={"id": act_id},
        prev_log_hash=prev_log_hash,
        received_at=_RECEIVED_AT,
    )


# The example chain: the case's first three entries.
_ENTRY_0 = _example_record(0, "create_case", _GENESIS_HASH)
_ENTRY_1 = _example_record(1, "add_report_to_case", _ENTRY_0.entry_hash)
_ENTRY_2 = _example_record(2, "engage_case", _ENTRY_1.entry_hash)


def _example_ledger_entry() -> as_CaseLedgerEntry:
    return _ENTRY_0.to_ledger_entry()


def add_case_ledger_entry():
    """Build ``Add(CaseLedgerEntry)`` — fan-out replication to participants.

    Sent by the CASE_MANAGER to each participant after a log entry has been
    committed to the case ledger (SYNC-09-002).  Its ``target`` is the case's
    ledger, ``<case>/ledger``, its ``context`` the case, and its
    ``inReplyTo`` the committed act (ADR-0204).
    """
    entry = _example_ledger_entry()
    return add_log_entry_activity(
        entry, actor=_CASE_ACTOR.id_, at=EXAMPLE_TIMESTAMP
    )


def reject_case_ledger_entry():
    """Build ``Reject(CaseLedgerEntry)`` — hash-chain mismatch from a participant.

    Sent by a participant to the CaseActor when the incoming
    ``prev_log_hash`` does not match the local ledger tail (SYNC-03-001).
    Its ``ledgerPosition`` is that tail, the last entry it applied, so the
    CaseActor can determine the replay window (SYNC-03-002, SYNC-18-001);
    ``context`` names the case.

    The example participant holds only the first entry and missed the
    second, so the third entry's ``prev_log_hash`` does not match its tail,
    and its ``ledgerPosition`` names the first entry.  Its ``inReplyTo``
    names the ``Add`` that carried the third entry (RF-08-004).
    """
    entry = _ENTRY_2.to_ledger_entry()
    add = add_log_entry_activity(
        entry, actor=_CASE_ACTOR.id_, at=EXAMPLE_TIMESTAMP
    )
    return reject_log_entry_activity(
        entry,
        in_reply_to=add.id_,
        ledger_position=LedgerPosition(
            log_index=_ENTRY_0.log_index, entry_hash=_ENTRY_0.entry_hash
        ),
        actor=_VENDOR.id_,
        at=EXAMPLE_TIMESTAMP,
    )


def read_case_ledger():
    """Build ``Read(<case>/ledger)`` — a participant states its position.

    Sent by a participant to the case's CASE_MANAGER to state how far it
    has applied the case's ledger (SYNC-17-001, ADR-0204).  The object is
    the case's ledger; the example participant has applied the first two
    entries, so its ``ledgerPosition`` is the second's.  A participant that
    holds no entry states index -1 and the case's genesis hash, which asks
    for the whole ledger (SYNC-16-027).
    """
    entry = _ENTRY_1.to_ledger_entry()
    return read_ledger_at_entry_activity(
        entry, actor=_VENDOR.id_, to=[_CASE_ACTOR.id_], at=EXAMPLE_TIMESTAMP
    )
