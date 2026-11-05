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

"""Holding transitions on the one received record (ADR-0154, IO-03-009).

The case that matters here is the record that is **archived and still owes a
replay** — a buffered ``Announce(CaseLedgerEntry)``.  Before ADR-0154 that was
two rows, and releasing or discarding the hold deleted the second one while
the archive stood.  With one row, the same must hold: the archive survives and
only the replay claim goes (CLP-10-018).
"""

import json
from datetime import timedelta

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
    ReceivedStage,
)
from vultron.core.services.received_holding import (
    discard_holding,
    held_for_replay,
    hold_for_replay,
    owes_replay,
    records_awaiting_case,
    release_from_holding,
    stop_awaiting_case,
)
from vultron.core.services.received_outcome import write_receipt_stub
from vultron.errors import VultronWiringError

SENDER = "https://example.org/actors/reporter"
RECEIVER = "https://example.org/actors/vendor"
CASE_ID = "https://example.org/cases/c-1"
OTHER_CASE_ID = "https://example.org/cases/c-2"


def _body(activity_id: str) -> str:
    return json.dumps(
        {
            "type": "Create",
            "id": activity_id,
            "actor": SENDER,
            "to": [RECEIVER],
        }
    )


def _aid(suffix: str) -> str:
    return f"https://example.org/activities/{suffix}"


@pytest.fixture
def dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=RECEIVER)


def _archive(dl, activity_id: str) -> ReceivedActivityRecord:
    """Archive *activity_id* as intake does."""
    record = ReceivedActivityRecord(
        activity_id=activity_id,
        received_body=_body(activity_id),
        stage=ReceivedStage.ARCHIVED,
        replay_owed=False,
    )
    dl.create(record)
    return record


def _stored(dl, activity_id: str) -> ReceivedActivityRecord:
    """The record *dl* holds for *activity_id*, which must be there.

    Fails loudly rather than answering ``None``: every caller is asserting
    something *about* the record, so a missing one is the test's own setup
    being wrong, not the thing under test.
    """
    record = dl.read(ReceivedActivityRecord.build_id(activity_id))
    assert isinstance(record, ReceivedActivityRecord), (
        f"{activity_id!r} is not held"
    )
    return record


def _absent(dl, activity_id: str) -> bool:
    """Whether *dl* holds no record at all for *activity_id*."""
    return dl.read(ReceivedActivityRecord.build_id(activity_id)) is None


# --------------------------------------------------------------------------
# Holding a body the receiver has not archived
# --------------------------------------------------------------------------


@pytest.mark.spec("IO-03-009")
def test_holding_an_unknown_activity_creates_a_held_record(dl):
    activity_id = _aid("a-1")
    assert hold_for_replay(dl, activity_id, _body(activity_id)) is True

    record = _stored(dl, activity_id)
    assert record is not None
    assert record.stage is ReceivedStage.HELD
    assert record.replay_owed is True
    assert record.received_body == _body(activity_id)


@pytest.mark.spec("IE-10-001")
def test_holding_again_keeps_the_body_first_held(dl):
    """A redelivery of a held activity is not held again (IE-10-001)."""
    activity_id = _aid("a-1")
    hold_for_replay(dl, activity_id, _body(activity_id))

    different = json.dumps({"type": "Create", "id": activity_id, "x": "later"})
    assert hold_for_replay(dl, activity_id, different) is False

    record = _stored(dl, activity_id)
    assert record.received_body == _body(activity_id)


@pytest.mark.spec("IO-03-009")
def test_releasing_a_never_archived_record_deletes_it(dl):
    """It existed only for this replay, so nothing would read it again."""
    activity_id = _aid("a-1")
    hold_for_replay(dl, activity_id, _body(activity_id))

    released = release_from_holding(dl, activity_id)
    assert released is not None
    assert released.received_body == _body(activity_id)
    assert _absent(dl, activity_id)


@pytest.mark.spec("IO-03-009")
def test_discarding_a_never_archived_record_deletes_it(dl):
    activity_id = _aid("a-1")
    hold_for_replay(dl, activity_id, _body(activity_id))

    discard_holding(dl, activity_id)
    assert _absent(dl, activity_id)


@pytest.mark.spec("CLP-10-018")
@pytest.mark.spec("IO-03-009")
def test_holding_over_a_receipt_stub_holds_the_body_again(dl):
    """A resend of a refused message that waits before intake runs.

    The stub has no body to replay, so the hold writes a whole ``HELD``
    record over it, one the stage/body invariant accepts, and keeps the
    stub's time of receipt.  A copy of the stub that only gained the replay
    flag would owe a replay of a body that is not there.
    """
    activity_id = _aid("refused-1")
    _archive(dl, activity_id)
    stub = write_receipt_stub(
        dl, activity_id, sender_id=SENDER, reason="refused for this test"
    )

    assert (
        hold_for_replay(
            dl, activity_id, _body(activity_id), awaiting_case_id=CASE_ID
        )
        is True
    )

    record = _stored(dl, activity_id)
    ReceivedActivityRecord.model_validate(record.model_dump())
    assert record.stage is ReceivedStage.HELD
    assert not record.is_receipt_stub
    assert record.received_body == _body(activity_id)
    assert record.replay_owed is True
    assert record.awaiting_case_id == CASE_ID
    assert record.received_at == stub.received_at
    assert (record.sender_id, record.refusal_reason, record.body_hash) == (
        None,
        None,
        None,
    )


# --------------------------------------------------------------------------
# The buffered Announce: archived *and* owing a replay
# --------------------------------------------------------------------------


@pytest.mark.spec("SYNC-14-001")
def test_holding_an_archived_activity_keeps_the_archive(dl):
    activity_id = _aid("announce-1")
    _archive(dl, activity_id)

    assert hold_for_replay(dl, activity_id, _body(activity_id)) is True

    record = _stored(dl, activity_id)
    assert record.stage is ReceivedStage.ARCHIVED
    assert record.replay_owed is True


@pytest.mark.spec("CLP-10-018")
def test_releasing_an_archived_hold_leaves_the_archive_standing(dl):
    """The archive outlives the replay it owed (CLP-10-018, SYNC-14-009)."""
    activity_id = _aid("announce-1")
    _archive(dl, activity_id)
    hold_for_replay(dl, activity_id, _body(activity_id))

    release_from_holding(dl, activity_id)

    record = _stored(dl, activity_id)
    assert record.stage is ReceivedStage.ARCHIVED
    assert record.replay_owed is False
    assert record.received_body == _body(activity_id)


@pytest.mark.spec("CLP-10-018")
def test_discarding_an_archived_hold_leaves_the_archive_standing(dl):
    """A bound that evicts a held Announce keeps what intake archived."""
    activity_id = _aid("announce-1")
    _archive(dl, activity_id)
    hold_for_replay(dl, activity_id, _body(activity_id))

    discard_holding(dl, activity_id)

    record = _stored(dl, activity_id)
    assert record.replay_owed is False
    assert record.received_body == _body(activity_id)


# --------------------------------------------------------------------------
# Reads: what owes a replay, and what waits on a case
# --------------------------------------------------------------------------


@pytest.mark.spec("IO-03-009")
def test_owes_replay_distinguishes_a_hold_from_an_archive(dl):
    held, archived, absent = _aid("h"), _aid("a"), _aid("none")
    hold_for_replay(dl, held, _body(held))
    _archive(dl, archived)

    assert owes_replay(dl, held) is True
    assert owes_replay(dl, archived) is False
    assert owes_replay(dl, absent) is False


@pytest.mark.spec("IO-03-009")
def test_held_for_replay_answers_only_a_record_owing_one(dl):
    held, archived = _aid("h"), _aid("a")
    hold_for_replay(dl, held, _body(held))
    _archive(dl, archived)

    owing = held_for_replay(dl, held)
    assert owing is not None, "the held record owes a replay"
    assert owing.activity_id == held
    assert held_for_replay(dl, archived) is None


@pytest.mark.spec("IO-03-009")
def test_records_awaiting_a_case_are_in_arrival_order(dl):
    """The replay order is the arrival order the retired list gave."""
    first, second, third = _aid("first"), _aid("second"), _aid("third")
    for activity_id in (first, second, third):
        hold_for_replay(
            dl, activity_id, _body(activity_id), awaiting_case_id=CASE_ID
        )
    # Arrival order is the record's own receipt time, not insertion order in
    # any list, so set them out of lexical order to prove it is read.
    base = _stored(dl, first).received_at
    for offset, activity_id in ((2, first), (0, second), (1, third)):
        record = _stored(dl, activity_id)
        dl.save(
            record.model_copy(
                update={"received_at": base + timedelta(seconds=offset)}
            )
        )

    waiting = records_awaiting_case(dl, CASE_ID)
    assert [r.activity_id for r in waiting] == [second, third, first]


@pytest.mark.spec("IO-03-009")
def test_records_awaiting_a_case_exclude_other_waits(dl):
    mine, theirs, no_case = _aid("mine"), _aid("theirs"), _aid("nocase")
    hold_for_replay(dl, mine, _body(mine), awaiting_case_id=CASE_ID)
    hold_for_replay(dl, theirs, _body(theirs), awaiting_case_id=OTHER_CASE_ID)
    # A hold with no case named waits on something else (a ledger gap, a
    # fetch, a retry) and is no business of this case's queue.
    hold_for_replay(dl, no_case, _body(no_case))

    assert [r.activity_id for r in records_awaiting_case(dl, CASE_ID)] == [
        mine
    ]


@pytest.mark.spec("IO-03-009")
def test_stopping_the_case_wait_keeps_the_body_held(dl):
    """Queued for the drain: no longer waiting, still held to be replayed."""
    activity_id = _aid("a-1")
    hold_for_replay(
        dl, activity_id, _body(activity_id), awaiting_case_id=CASE_ID
    )

    stop_awaiting_case(dl, activity_id)

    assert records_awaiting_case(dl, CASE_ID) == []
    record = _stored(dl, activity_id)
    assert record.replay_owed is True, "the drain still needs the held body"
    assert record.awaiting_case_id is None


@pytest.mark.spec("IO-03-009")
def test_releasing_nothing_held_answers_none(dl):
    assert release_from_holding(dl, _aid("never-held")) is None


# --------------------------------------------------------------------------
# A body held for one wait and then deferred on its case (#5045a regression)
# --------------------------------------------------------------------------


@pytest.mark.spec("IO-03-009")
def test_naming_a_case_on_an_existing_hold_records_the_wait(dl):
    """Else the message is held but nothing ever replays it."""
    activity_id = _aid("a-1")
    # Held first with no case: a retry, or a fetch the activity waits on.
    hold_for_replay(dl, activity_id, _body(activity_id))
    assert records_awaiting_case(dl, CASE_ID) == []

    # Then deferred on its case; the body is unchanged, the wait is recorded.
    assert (
        hold_for_replay(
            dl, activity_id, _body(activity_id), awaiting_case_id=CASE_ID
        )
        is False
    )
    assert [r.activity_id for r in records_awaiting_case(dl, CASE_ID)] == [
        activity_id
    ]
    assert _stored(dl, activity_id).received_body == _body(activity_id)


@pytest.mark.spec("IO-03-009")
def test_a_second_case_on_one_hold_is_refused(dl):
    """One record cannot wait on two cases; guessing which would lose one."""
    activity_id = _aid("a-1")
    hold_for_replay(
        dl, activity_id, _body(activity_id), awaiting_case_id=CASE_ID
    )

    with pytest.raises(VultronWiringError, match="cannot also wait"):
        hold_for_replay(
            dl,
            activity_id,
            _body(activity_id),
            awaiting_case_id=OTHER_CASE_ID,
        )
