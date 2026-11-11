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

"""The two outcomes that change what the receiver keeps (ADR-0154).

``received_outcome.py`` archives an applied message's record (CLP-10-073)
and gives a refused one's body up for a receipt stub (CLP-10-018).  What each
outcome leaves is driven through the inbox in
``test/adapters/driving/fastapi/test_received_outcome_stage.py``; these tests
drive the write itself.
"""

import json
from collections.abc import Iterator

import pytest

from test.support.act_clock import ACT_AT
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models._helpers import now_utc
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
    ReceivedStage,
)
from vultron.core.models.received_body import received_body_digest
from vultron.core.services.received_activity import held_received_record
from vultron.core.services.received_holding import hold_for_replay
from vultron.core.services.received_outcome import (
    archive_applied,
    write_receipt_stub,
)
from vultron.errors import VultronWiringError

SENDER = "https://example.org/actors/reporter"
RECEIVER = "https://example.org/actors/vendor"
ACTIVITY_ID = "https://example.org/activities/a-1"
CASE_ID = "https://example.org/cases/c-1"
REASON = "sender is not a participant of the case (HP-01-006)"


def _body(marker: str = "as received") -> str:
    return json.dumps(
        {"type": "Create", "id": ACTIVITY_ID, "actor": SENDER, "x": marker}
    )


@pytest.fixture
def dl() -> Iterator[SqliteDataLayer]:
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=RECEIVER)
    yield store
    store.close()


def _archive(dl: SqliteDataLayer, body: str | None = None) -> None:
    """Record the activity as intake does: ``HELD``, owed nothing."""
    dl.create(
        ReceivedActivityRecord(
            activity_id=ACTIVITY_ID,
            received_body=body or _body(),
            stage=ReceivedStage.HELD,
            replay_owed=False,
            received_at=ACT_AT,
        )
    )


@pytest.mark.spec("CLP-10-018")
def test_the_stub_keeps_the_receipt_and_gives_up_the_message(dl):
    _archive(dl)
    archived = held_received_record(dl, ACTIVITY_ID)
    assert archived is not None

    stub = write_receipt_stub(
        dl, ACTIVITY_ID, sender_id=SENDER, reason=REASON, received_at=now_utc()
    )

    assert stub.stage is ReceivedStage.REFUSED
    assert stub.received_body is None
    assert stub.sender_id == SENDER
    assert stub.refusal_reason == REASON
    assert stub.body_hash == received_body_digest(_body())
    # The time of receipt is the one the record already carried, not now:
    # the stub records when the message arrived (CLP-10-018).
    assert stub.received_at == archived.received_at


@pytest.mark.spec("DL-06-006")
def test_the_stub_replaces_the_archive_under_the_same_key(dl):
    _archive(dl)
    key = ReceivedActivityRecord.build_id(ACTIVITY_ID)

    write_receipt_stub(
        dl, ACTIVITY_ID, sender_id=SENDER, reason=REASON, received_at=now_utc()
    )

    stored = dl.read(key)
    assert isinstance(stored, ReceivedActivityRecord)
    assert stored.is_receipt_stub
    # One row, not a stub beside an archive: the seen-before question stays
    # one read of one row (ADR-0154).
    assert (
        len(
            [
                obj
                for obj in dl.list_objects(ReceivedActivityRecord.__name__)
                if isinstance(obj, ReceivedActivityRecord)
            ]
        )
        == 1
    )
    assert dl.read(ACTIVITY_ID) is None


@pytest.mark.spec("CLP-10-018")
def test_a_second_refusal_leaves_the_first_reason_standing(dl):
    _archive(dl)
    write_receipt_stub(
        dl, ACTIVITY_ID, sender_id=SENDER, reason=REASON, received_at=now_utc()
    )

    again = write_receipt_stub(
        dl,
        ACTIVITY_ID,
        sender_id=SENDER,
        reason="a later, different reason",
        received_at=now_utc(),
    )

    assert again.refusal_reason == REASON


@pytest.mark.spec("CLP-10-018")
def test_a_refusal_before_intake_stubs_the_delivered_body(dl):
    """A door refused it before intake wrote anything (ADR-0154)."""
    stub = write_receipt_stub(
        dl,
        ACTIVITY_ID,
        sender_id=SENDER,
        reason=REASON,
        received_body=_body(),
        received_at=now_utc(),
    )

    assert held_received_record(dl, ACTIVITY_ID) == stub
    assert stub.is_receipt_stub
    assert stub.body_hash == received_body_digest(_body())
    assert stub.sender_id == SENDER
    assert stub.refusal_reason == REASON


@pytest.mark.spec("ARCH-15-001")
def test_refusing_an_unheld_activity_with_no_body_raises(dl):
    """Nothing held and no sealed body: there is no digest to record."""
    with pytest.raises(VultronWiringError, match="no digest to record"):
        write_receipt_stub(
            dl,
            ACTIVITY_ID,
            sender_id=SENDER,
            reason=REASON,
            received_at=now_utc(),
        )


@pytest.mark.spec("CLP-10-073")
def test_a_refusal_never_reduces_an_archive(dl):
    """An applied message's archive outlives a later refusal of a resend."""
    dl.create(
        ReceivedActivityRecord(
            activity_id=ACTIVITY_ID, received_body=_body(), received_at=ACT_AT
        )
    )
    before = held_received_record(dl, ACTIVITY_ID)

    returned = write_receipt_stub(
        dl, ACTIVITY_ID, sender_id=SENDER, reason=REASON, received_at=now_utc()
    )

    assert returned == before
    assert held_received_record(dl, ACTIVITY_ID) == before


@pytest.mark.spec("CLP-10-073")
def test_an_applied_message_is_archived_with_its_body(dl):
    _archive(dl)
    before = held_received_record(dl, ACTIVITY_ID)
    assert before is not None

    archive_applied(dl, ACTIVITY_ID)

    record = held_received_record(dl, ACTIVITY_ID)
    assert record is not None
    assert record.stage is ReceivedStage.ARCHIVED
    assert record.received_body == _body()
    assert record.received_at == before.received_at


@pytest.mark.spec("CLP-10-076")
def test_an_applied_message_still_owed_a_replay_stays_held(dl):
    """A buffered Announce is not archived early (SYNC-14-001, ADR-0154)."""
    _archive(dl)
    hold_for_replay(dl, ACTIVITY_ID, _body(), received_at=now_utc())

    archive_applied(dl, ACTIVITY_ID)

    record = held_received_record(dl, ACTIVITY_ID)
    assert record is not None
    assert record.stage is ReceivedStage.HELD
    assert record.replay_owed is True


@pytest.mark.spec("CLP-10-073")
def test_archiving_with_nothing_held_writes_nothing(dl):
    archive_applied(dl, ACTIVITY_ID)
    assert held_received_record(dl, ACTIVITY_ID) is None


@pytest.mark.spec("IO-03-009")
@pytest.mark.spec("CLP-10-076")
def test_a_body_still_owed_to_a_replay_is_not_given_up(dl):
    """The replay would route a body the stub had dropped (CLP-10-018).

    Not a fault: the held message reaches its own outcome when the replay
    runs, so the call returns the record unchanged and raises nothing.
    """
    hold_for_replay(
        dl,
        ACTIVITY_ID,
        _body(),
        awaiting_case_id=CASE_ID,
        received_at=now_utc(),
    )
    before = held_received_record(dl, ACTIVITY_ID)

    returned = write_receipt_stub(
        dl, ACTIVITY_ID, sender_id=SENDER, reason=REASON, received_at=now_utc()
    )

    held = held_received_record(dl, ACTIVITY_ID)
    assert held is not None
    assert held == before
    assert returned == before
    assert held.received_body == _body()
    assert held.replay_owed is True
    assert not held.is_receipt_stub
