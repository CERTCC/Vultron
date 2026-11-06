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
"""The factory stamp of a sender's sequence number (SYNC-21-001, ADR-0178)."""

import json

import pytest

from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.ledger_position import LedgerPosition
from vultron.errors import VultronActivityConstructionError
from vultron.wire.as2.factories import (
    add_note_to_case_activity,
    is_ledger_request,
    rm_engage_case_activity,
    sender_sequence_case_ids,
    stamp_ledger_position,
    stamp_sender_sequence,
)
from vultron.wire.as2.factories.sync import (
    genesis_replay_reject_activity,
    read_ledger_position_activity,
    reject_log_entry_activity,
)
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.case_ledger_entry import as_CaseLedgerEntry

_CASE = "https://example.org/cases/sequence"
_ACTOR = "https://example.org/users/vendor"
_TAIL = LedgerPosition(log_index=4, entry_hash="ab" * 32)
_EMPTY = LedgerPosition(log_index=-1, entry_hash="cd" * 32)


def _note(*, positioned: bool = True):
    note = add_note_to_case_activity(
        as_Note(id_=f"{_CASE}/notes/1", content="n", context=_CASE),
        target=_CASE,
        actor=_ACTOR,
    )
    return stamp_ledger_position(note, _TAIL) if positioned else note


def _entry() -> as_CaseLedgerEntry:
    core = CaseLedgerEntry(
        case_id=_CASE,
        log_index=4,
        log_object_id=f"{_CASE}/activities/4",
        semantic_type="add_note_to_case",
        payload_snapshot={},
        prev_log_hash="00" * 32,
        entry_hash="ab" * 32,
    )
    return as_CaseLedgerEntry.model_validate(core.model_dump(by_alias=True))


@pytest.mark.spec("SYNC-21-004")
def test_the_stamp_is_a_copy_carrying_the_number() -> None:
    note = _note()

    stamped = stamp_sender_sequence(note, 3)

    assert stamped is not note
    assert note.sender_sequence is None
    assert stamped.sender_sequence == 3
    dumped = json.loads(stamped.model_dump_json(by_alias=True))
    assert dumped["senderSequence"] == 3


@pytest.mark.spec("SYNC-21-003")
def test_a_numbered_activity_keeps_its_first_number() -> None:
    first = stamp_sender_sequence(_note(), 1)

    assert stamp_sender_sequence(first, 2) is first


@pytest.mark.parametrize("number", [0, -1, True])
def test_only_a_positive_integer_is_a_number(number: int) -> None:
    with pytest.raises(VultronActivityConstructionError):
        stamp_sender_sequence(_note(), number)


@pytest.mark.spec("SYNC-21-001")
def test_a_positioned_case_activity_may_take_a_number() -> None:
    assert next(sender_sequence_case_ids(_note())) == _CASE
    engage = stamp_ledger_position(
        rm_engage_case_activity(_CASE, actor=_ACTOR), _TAIL
    )
    assert _CASE in list(sender_sequence_case_ids(engage))


@pytest.mark.spec("SYNC-21-001")
def test_an_activity_with_no_position_takes_no_number() -> None:
    assert list(sender_sequence_case_ids(_note(positioned=False))) == []


@pytest.mark.spec("SYNC-21-001")
def test_a_numbered_activity_still_names_its_cases() -> None:
    """The adapter counts a number it did not give as used (SYNC-21-002)."""
    numbered = stamp_sender_sequence(_note(), 1)

    assert _CASE in list(sender_sequence_case_ids(numbered))
    assert stamp_sender_sequence(numbered, 2).sender_sequence == 1


@pytest.mark.spec("SYNC-21-001")
def test_the_ledger_requests_take_no_number() -> None:
    read = read_ledger_position_activity(_CASE, _TAIL, actor=_ACTOR)
    reject = stamp_ledger_position(
        reject_log_entry_activity(_entry(), actor=_ACTOR), _TAIL
    )
    genesis = genesis_replay_reject_activity(_CASE, _EMPTY, actor=_ACTOR)

    for request in (read, reject, genesis):
        assert is_ledger_request(request)
        assert list(sender_sequence_case_ids(request)) == []
    assert not is_ledger_request(_note())


@pytest.mark.spec("SYNC-21-001")
def test_a_parsed_ledger_request_takes_no_number() -> None:
    """A ``Read`` posted by a client parses to a plain ``as_Read``."""
    read = read_ledger_position_activity(_CASE, _TAIL, actor=_ACTOR)
    parsed = parse_activity(json.loads(read.model_dump_json(by_alias=True)))

    assert is_ledger_request(parsed)


@pytest.mark.spec("SYNC-21-001")
def test_an_inbound_number_survives_the_parse() -> None:
    body = json.loads(
        stamp_sender_sequence(_note(), 7).model_dump_json(
            by_alias=True, exclude_none=True
        )
    )

    assert parse_activity(body).sender_sequence == 7


@pytest.mark.spec("SYNC-21-017")
@pytest.mark.parametrize("number", ["two", "2", 0, -3, 1.5, True])
def test_an_inbound_number_that_is_no_positive_integer_is_set_aside(
    number: object,
) -> None:
    """The parse edge sets the number aside; the evidence keeps it.

    A malformed number is the CASE_MANAGER's to refuse, with a notice naming
    the number it expects, after its door and sender guards (SYNC-21-017,
    SYNC-21-023), so the activity parses as one that carries no number, and
    the received body keeps the value as it arrived (VM-08-002).
    """
    body = json.loads(
        _note().model_dump_json(by_alias=True, exclude_none=True)
    )
    body["senderSequence"] = number

    parsed = parse_activity(body)

    assert parsed.sender_sequence is None
    assert parsed.received_evidence is not None
    assert parsed.received_evidence["senderSequence"] == number
