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

"""ReceivedActivityRecord: the receiver's key for a received activity (CLP-10-017).

The record holds the body that arrived and nothing derived from it (ADR-0149).
"""

import json

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.errors import VultronAlreadyExistsError

SENDER = "https://example.org/actors/reporter"
RECEIVER = "https://example.org/actors/vendor"
ACTIVITY_ID = "https://example.org/activities/create-note-7"
NOTE_ID = "https://example.org/notes/n-7"
CASE_ID = "https://example.org/cases/c-7"


def _body(activity_id: str = ACTIVITY_ID) -> str:
    """A received body, as the parser seals one."""
    return json.dumps(
        {
            "type": "Create",
            "id": activity_id,
            "actor": SENDER,
            "to": [RECEIVER],
            "object": {
                "type": "Note",
                "id": NOTE_ID,
                "content": "as received",
                "context": CASE_ID,
            },
            "fooBar": "a key no vocabulary names",
        }
    )


def _record(activity_id: str = ACTIVITY_ID) -> ReceivedActivityRecord:
    return ReceivedActivityRecord(
        activity_id=activity_id, received_body=_body(activity_id)
    )


@pytest.fixture
def dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=RECEIVER)


@pytest.mark.spec("CLP-10-017")
def test_id_is_the_receivers_and_derived_from_the_senders():
    record = _record()

    assert record.id_ == ReceivedActivityRecord.build_id(ACTIVITY_ID)
    assert record.id_ != ACTIVITY_ID
    assert record.id_.startswith("received-activity/")
    assert record.activity_id == ACTIVITY_ID


def test_build_id_is_stable_and_injective():
    a = ReceivedActivityRecord.build_id("https://example.org/a/1")
    b = ReceivedActivityRecord.build_id("https://example.org/a/2")
    assert a == ReceivedActivityRecord.build_id("https://example.org/a/1")
    assert a != b
    # A sender id that already looks like one of our keys still maps to a
    # distinct key of ours (the slug quotes the slash).
    nested = ReceivedActivityRecord.build_id("received-activity/x")
    assert nested != "received-activity/x"


@pytest.mark.spec("CLP-10-017")
def test_round_trips_the_body_through_the_datalayer_unchanged(dl):
    dl.create(_record())

    # their key -> ours
    record = dl.read(ReceivedActivityRecord.build_id(ACTIVITY_ID))
    assert isinstance(record, ReceivedActivityRecord)
    # ours -> theirs
    assert record.activity_id == ACTIVITY_ID
    # The body is kept as the text that was sealed, every key included: the
    # archive is the mail, not core's record of it.
    assert record.received_body == _body()
    # nothing under the sender's id, and no row of the activity's own type
    assert dl.read(ACTIVITY_ID) is None
    assert dl.by_type("Create") == {}


@pytest.mark.spec("VM-08-002")
@pytest.mark.parametrize("body", ["not json", "[1, 2]", '"text"'])
def test_a_body_that_is_not_a_json_object_is_refused(body):
    with pytest.raises(ValueError, match="received_body"):
        ReceivedActivityRecord(activity_id=ACTIVITY_ID, received_body=body)


def test_a_stored_core_summary_is_refused_as_retired():
    """The retired summary field is refused with the reason (ADR-0149)."""
    with pytest.raises(ValueError, match="retired"):
        ReceivedActivityRecord.model_validate(
            {
                "activity_id": ACTIVITY_ID,
                "received_body": _body(),
                "activity": {"type": "Create"},
            }
        )


@pytest.mark.spec("CLP-10-017")
def test_duplicate_archive_raises_already_exists(dl):
    dl.create(_record())
    with pytest.raises(VultronAlreadyExistsError):
        dl.create(_record())


@pytest.mark.spec("CLP-10-017")
def test_sender_cannot_occupy_a_receiver_derived_id(dl):
    """An archived activity named after our pending-case marker blocks nothing."""
    marker_id = VultronPendingCaseInbox.build_id(CASE_ID)
    dl.create(_record(marker_id))

    assert dl.read(marker_id) is None
    dl.create(VultronPendingCaseInbox(case_id=CASE_ID, case_actor_id=RECEIVER))
    assert isinstance(dl.read(marker_id), VultronPendingCaseInbox)
