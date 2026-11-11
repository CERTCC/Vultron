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

"""A ``HANDLED`` record is in holding to every service that asks (ADR-0154).

Intake moves the record an earlier run left to ``HANDLED``, so the services
that hold, discard, settle or read a message in holding take ``HANDLED`` as
they take ``HELD``: a re-run can still wait, be dropped, be archived or be
reduced to a receipt stub, and at startup it is a record left to finish.
"""

from datetime import timedelta

import pytest

from test.core.services.test_received_holding import (
    RECEIVER,
    _absent,
    _aid,
    _archive,
    _body,
    _record,
    _stored,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models._helpers import now_utc
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
    ReceivedStage,
)
from vultron.core.services.held_ledger_announces import _record_in_holding
from vultron.core.services.received_activity import sealed_body_of
from vultron.core.services.received_holding import (
    discard_holding,
    hold_for_replay,
    hold_unjudged_for_replay,
    records_left_in_holding,
)
from vultron.core.services.received_outcome import (
    archive_applied,
    write_receipt_stub,
)

SENDER = "https://example.org/actors/reporter"


@pytest.fixture
def dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=RECEIVER)


def _handled(dl, activity_id: str) -> ReceivedActivityRecord:
    """Record *activity_id* as a re-run's intake leaves it."""
    record = ReceivedActivityRecord(
        activity_id=activity_id,
        received_body=_body(activity_id),
        stage=ReceivedStage.HANDLED,
    )
    dl.create(record)
    return record


@pytest.mark.spec("IO-03-009")
def test_holding_a_handled_record_makes_it_held_and_owing(dl):
    """``HANDLED`` never owes a replay, so the hold moves it back to ``HELD``."""
    activity_id = _aid("handled-hold")
    _handled(dl, activity_id)

    assert (
        hold_for_replay(
            dl, activity_id, _body(activity_id), received_at=now_utc()
        )
        is True
    )

    stored = _stored(dl, activity_id)
    assert (stored.stage, stored.replay_owed) == (ReceivedStage.HELD, True)


@pytest.mark.spec("SYNC-21-010")
def test_holding_an_unjudged_handled_record_makes_it_held_and_owing(dl):
    activity_id = _aid("handled-unjudged")
    _handled(dl, activity_id)

    hold_unjudged_for_replay(dl, activity_id)

    stored = _stored(dl, activity_id)
    assert (stored.stage, stored.replay_owed) == (ReceivedStage.HELD, True)


@pytest.mark.spec("SYNC-14-013")
def test_discarding_a_handled_record_deletes_it(dl):
    activity_id = _aid("handled-discard")
    _handled(dl, activity_id)

    discard_holding(dl, activity_id)

    assert _absent(dl, activity_id)


@pytest.mark.spec("CLP-10-073")
def test_an_applied_rerun_is_archived(dl):
    activity_id = _aid("handled-applied")
    _handled(dl, activity_id)

    archive_applied(dl, activity_id)

    stored = _stored(dl, activity_id)
    assert stored.stage is ReceivedStage.ARCHIVED
    assert stored.received_body == _body(activity_id)


@pytest.mark.spec("CLP-10-018")
def test_a_refused_rerun_leaves_a_receipt_stub(dl):
    activity_id = _aid("handled-refused")
    _handled(dl, activity_id)

    write_receipt_stub(
        dl,
        activity_id,
        sender_id=SENDER,
        reason="refused",
        received_at=now_utc(),
    )

    assert _stored(dl, activity_id).is_receipt_stub


@pytest.mark.spec("SYNC-14-001")
def test_a_handled_announce_still_has_its_body_to_hold(dl):
    activity_id = _aid("handled-announce")
    _handled(dl, activity_id)

    assert sealed_body_of(_record_in_holding(dl, activity_id)) == _body(
        activity_id
    )


@pytest.mark.spec("CLP-10-074")
def test_records_left_in_holding_are_the_unsettled_ones_oldest_first(dl):
    """``HELD`` and ``HANDLED`` owing nothing; never a wait or a settled one."""
    later = _record(dl, _aid("left-held"))
    earlier = _handled(dl, _aid("left-handled"))
    dl.save(
        earlier.model_copy(
            update={"received_at": later.received_at - timedelta(seconds=1)}
        )
    )
    _archive(dl, _aid("left-archived"))
    hold_for_replay(
        dl,
        _aid("left-waiting"),
        _body(_aid("left-waiting")),
        received_at=now_utc(),
    )
    write_receipt_stub(
        dl,
        _aid("left-refused"),
        sender_id=SENDER,
        reason="refused",
        received_body=_body(_aid("left-refused")),
        received_at=now_utc(),
    )

    assert [r.activity_id for r in records_left_in_holding(dl)] == [
        _aid("left-handled"),
        _aid("left-held"),
    ]
