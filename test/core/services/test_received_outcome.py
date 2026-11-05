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

"""A refusal gives the body up for a receipt stub (CLP-10-018, ADR-0154).

``received_outcome.py`` owns the one final outcome that changes what the
receiver keeps.  What each outcome leaves is driven through the inbox in
``test/adapters/driving/fastapi/test_received_outcome_stage.py``; these tests
drive the write itself.
"""

import json
from collections.abc import Iterator

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
    ReceivedStage,
)
from vultron.core.models.received_body import received_body_digest
from vultron.core.services.received_activity import held_received_record
from vultron.core.services.received_holding import hold_for_replay
from vultron.core.services.received_outcome import write_receipt_stub
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
    dl.create(
        ReceivedActivityRecord(
            activity_id=ACTIVITY_ID, received_body=body or _body()
        )
    )


@pytest.mark.spec("CLP-10-018")
def test_the_stub_keeps_the_receipt_and_gives_up_the_message(dl):
    _archive(dl)
    archived = held_received_record(dl, ACTIVITY_ID)
    assert archived is not None

    stub = write_receipt_stub(dl, ACTIVITY_ID, sender_id=SENDER, reason=REASON)

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

    write_receipt_stub(dl, ACTIVITY_ID, sender_id=SENDER, reason=REASON)

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
    write_receipt_stub(dl, ACTIVITY_ID, sender_id=SENDER, reason=REASON)

    again = write_receipt_stub(
        dl, ACTIVITY_ID, sender_id=SENDER, reason="a later, different reason"
    )

    assert again.refusal_reason == REASON


@pytest.mark.spec("ARCH-15-001")
def test_refusing_an_activity_this_receiver_does_not_hold_raises(dl):
    """The outcome stage runs after intake, which holds every delivery."""
    with pytest.raises(VultronWiringError, match="not held by this receiver"):
        write_receipt_stub(dl, ACTIVITY_ID, sender_id=SENDER, reason=REASON)


@pytest.mark.spec("IO-03-009")
def test_a_body_still_owed_to_a_replay_is_not_given_up(dl):
    """The replay would route a body the stub had dropped (CLP-10-018)."""
    hold_for_replay(dl, ACTIVITY_ID, _body(), awaiting_case_id=CASE_ID)

    with pytest.raises(VultronWiringError, match="still owes a replay"):
        write_receipt_stub(dl, ACTIVITY_ID, sender_id=SENDER, reason=REASON)

    held = held_received_record(dl, ACTIVITY_ID)
    assert held is not None
    assert held.received_body == _body()
    assert held.replay_owed is True


@pytest.mark.spec("IE-10-002")
def test_the_digest_tells_the_same_body_from_a_different_one(dl):
    """What the stub keeps is enough to answer a resend (CLP-10-018)."""
    _archive(dl, _body("first"))

    stub = write_receipt_stub(dl, ACTIVITY_ID, sender_id=SENDER, reason=REASON)

    assert stub.body_hash == received_body_digest(_body("first"))
    assert stub.body_hash != received_body_digest(_body("second"))
