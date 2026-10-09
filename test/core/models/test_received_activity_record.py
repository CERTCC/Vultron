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

"""ReceivedActivityRecord: the receiver's key for a received activity (CLP-10-017)."""

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.activity import VultronActivity
from vultron.core.models.note import VultronNote
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


def _activity(activity_id: str = ACTIVITY_ID) -> VultronActivity:
    return VultronActivity(
        id_=activity_id,
        type_="Create",
        actor=SENDER,
        object_=VultronNote(
            id_=NOTE_ID, content="as received", context=CASE_ID
        ),
        to=[RECEIVER],
    )


def _inline_id(obj: object) -> str | None:
    """The id of an inline object as the archive returns it (a stored dict)."""
    if isinstance(obj, dict):
        return obj.get("id") or obj.get("id_")
    return getattr(obj, "id_", None)


@pytest.fixture
def dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=RECEIVER)


@pytest.mark.spec("CLP-10-017")
def test_id_is_the_receivers_and_derived_from_the_senders():
    record = ReceivedActivityRecord.for_activity(_activity())

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
def test_round_trips_through_the_datalayer_in_both_directions(dl):
    activity = _activity()
    dl.create(ReceivedActivityRecord.for_activity(activity))

    # their key -> ours
    record = dl.read(ReceivedActivityRecord.build_id(ACTIVITY_ID))
    assert isinstance(record, ReceivedActivityRecord)
    # ours -> theirs
    assert record.activity_id == ACTIVITY_ID
    assert record.activity.id_ == ACTIVITY_ID
    assert record.activity.type_ == "Create"
    assert record.activity.actor == SENDER
    assert record.activity.to == [RECEIVER]
    # The inline object is carried as the stored snapshot (a dict keyed the
    # wire way), not re-typed: the archive is the mail, not core's record.
    assert _inline_id(record.activity.object_) == NOTE_ID
    assert isinstance(record.activity.object_, dict)
    assert record.activity.object_["content"] == "as received"
    # nothing under the sender's id, and no row of the activity's own type
    assert dl.read(ACTIVITY_ID) is None
    assert dl.by_type("Create") == {}


@pytest.mark.spec("CLP-10-017")
def test_duplicate_archive_raises_already_exists(dl):
    dl.create(ReceivedActivityRecord.for_activity(_activity()))
    with pytest.raises(VultronAlreadyExistsError):
        dl.create(ReceivedActivityRecord.for_activity(_activity()))


@pytest.mark.spec("CLP-10-017")
def test_sender_cannot_occupy_a_receiver_derived_id(dl):
    """An archived activity named after our pending-case marker blocks nothing."""
    marker_id = VultronPendingCaseInbox.build_id(CASE_ID)
    dl.create(ReceivedActivityRecord.for_activity(_activity(marker_id)))

    assert dl.read(marker_id) is None
    dl.create(VultronPendingCaseInbox(case_id=CASE_ID, case_actor_id=RECEIVER))
    assert isinstance(dl.read(marker_id), VultronPendingCaseInbox)
