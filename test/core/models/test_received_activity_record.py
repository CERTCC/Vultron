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
from typing import Any

import pytest
from pydantic import ValidationError

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.core.models.received_activity_record import (
    BODY_BEARING_STAGES,
    HOLDING_STAGES,
    ReceivedActivityRecord,
    ReceivedStage,
)
from vultron.core.models.received_body import received_body_digest
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


def test_a_stored_core_summary_is_refused_as_an_unknown_key():
    """The former summary field is an unknown key (ADR-0149, ADR-0175)."""
    with pytest.raises(ValueError, match="extra_forbidden"):
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


# --------------------------------------------------------------------------
# The stage/replay invariant (ADR-0154)
#
# One record carries two independent facts — how far the message got
# (``stage``) and whether a replay is still owed from its body
# (``replay_owed``) — because both values of the flag are reachable in
# holding.  Three of the four pairings are legitimate; the fourth, an archive
# owing a replay, would apply an applied message again and is refused at
# construction.
# --------------------------------------------------------------------------


@pytest.mark.spec("CLP-10-017")
@pytest.mark.parametrize(
    ("stage", "replay_owed"),
    [
        # Applied, and the outcome stage archived it: the ordinary archive.
        (ReceivedStage.ARCHIVED, False),
        # Held for a replay: the inbox deferred it, or the handling tree held
        # it for a ledger gap after intake recorded it.
        (ReceivedStage.HELD, True),
        # In holding and owed nothing: intake recorded it and its run is in
        # progress, or ended with no verdict (CLP-10-074).
        (ReceivedStage.HELD, False),
        # Handled again: a later run's intake met the record a run left.
        (ReceivedStage.HANDLED, False),
    ],
)
def test_the_four_reachable_stage_and_replay_pairings_are_accepted(
    stage, replay_owed
):
    record = ReceivedActivityRecord(
        activity_id=ACTIVITY_ID,
        received_body=_body(),
        stage=stage,
        replay_owed=replay_owed,
    )
    assert record.stage is stage
    assert record.replay_owed is replay_owed


@pytest.mark.spec("CLP-10-073")
def test_an_archive_owing_a_replay_is_refused():
    """The archive holds only applied messages, so a replay would apply one
    again: a message still owed a replay stays HELD (ADR-0154)."""
    with pytest.raises(ValidationError) as caught:
        ReceivedActivityRecord(
            activity_id=ACTIVITY_ID,
            received_body=_body(),
            stage=ReceivedStage.ARCHIVED,
            replay_owed=True,
        )
    assert "ARCHIVED and owes a replay" in str(caught.value)


@pytest.mark.spec("CLP-10-074")
def test_a_handled_record_owing_a_replay_is_refused():
    """A message a run is handling again is not also waiting (ADR-0154)."""
    with pytest.raises(ValidationError) as caught:
        ReceivedActivityRecord(
            activity_id=ACTIVITY_ID,
            received_body=_body(),
            stage=ReceivedStage.HANDLED,
            replay_owed=True,
        )
    assert "HANDLED and owes a replay" in str(caught.value)


@pytest.mark.spec("CLP-10-074")
def test_a_handled_record_with_no_body_is_refused():
    """``HANDLED`` is run again from its body, so it must hold one.

    Named outright rather than through ``BODY_BEARING_STAGES``, so a stage
    dropped from that set is caught here (CLP-10-017).
    """
    with pytest.raises(ValidationError) as caught:
        ReceivedActivityRecord(
            activity_id=ACTIVITY_ID, stage=ReceivedStage.HANDLED
        )
    assert "no received body" in str(caught.value)


@pytest.mark.spec("CLP-10-017")
def test_a_handled_record_carrying_a_stubs_field_is_refused():
    """The other direction: a ``HANDLED`` record keeps no stub field."""
    with pytest.raises(ValidationError) as caught:
        ReceivedActivityRecord(
            activity_id=ACTIVITY_ID,
            received_body=_body(),
            stage=ReceivedStage.HANDLED,
            refusal_reason="x",
        )
    assert "only a receipt stub keeps" in str(caught.value)


@pytest.mark.spec("CLP-10-074")
def test_the_handled_invariant_survives_assignment():
    record = ReceivedActivityRecord(
        activity_id=ACTIVITY_ID,
        received_body=_body(),
        stage=ReceivedStage.HANDLED,
    )
    with pytest.raises(ValidationError):
        record.replay_owed = True


def test_the_holding_stages_are_held_and_handled():
    """The stages a reader asks about to mean "still in holding" (ADR-0154)."""
    assert {ReceivedStage.HELD, ReceivedStage.HANDLED} == HOLDING_STAGES
    assert HOLDING_STAGES < BODY_BEARING_STAGES


@pytest.mark.spec("IO-03-009")
def test_awaiting_a_case_with_no_replay_owed_is_refused():
    """A wait that owes no replay could never end."""
    with pytest.raises(ValidationError) as caught:
        ReceivedActivityRecord(
            activity_id=ACTIVITY_ID,
            received_body=_body(),
            stage=ReceivedStage.ARCHIVED,
            replay_owed=False,
            awaiting_case_id=CASE_ID,
        )
    assert "could never end" in str(caught.value)


@pytest.mark.spec("IO-03-009")
def test_awaiting_a_case_is_accepted_when_a_replay_is_owed():
    """The positive side of the invariant above, so neither reads vacuously."""
    record = ReceivedActivityRecord(
        activity_id=ACTIVITY_ID,
        received_body=_body(),
        stage=ReceivedStage.HELD,
        replay_owed=True,
        awaiting_case_id=CASE_ID,
    )
    assert record.awaiting_case_id == CASE_ID


@pytest.mark.spec("CLP-10-017")
def test_the_invariant_survives_assignment(dl):
    """``validate_assignment`` applies it after construction too (ARCH-21-001)."""
    record = _record()
    with pytest.raises(ValidationError):
        record.replay_owed = True


@pytest.mark.spec("IO-03-009")
def test_the_default_record_is_an_archive_owing_nothing():
    """A record needs no stage arguments to mean "archived"."""
    record = _record()
    assert record.stage is ReceivedStage.ARCHIVED
    assert record.replay_owed is False
    assert record.awaiting_case_id is None
    assert record.replay_rows_json == "[]"


@pytest.mark.spec("IO-03-009")
def test_the_replay_rows_round_trip_through_the_datalayer(dl):
    """The staged inline rows the replay needs survive storage (IO-03-009)."""
    rows = json.dumps([{"id_": NOTE_ID, "type_": "Note", "data_": "{}"}])
    dl.create(
        ReceivedActivityRecord(
            activity_id=ACTIVITY_ID,
            received_body=_body(),
            stage=ReceivedStage.HELD,
            replay_owed=True,
            replay_rows_json=rows,
        )
    )
    stored = dl.read(ReceivedActivityRecord.build_id(ACTIVITY_ID))
    assert stored.replay_rows_json == rows
    assert json.loads(stored.replay_rows_json)[0]["id_"] == NOTE_ID


# --------------------------------------------------------------------------
# The stage/body invariant: a receipt stub keeps the receipt, not the message
# (CLP-10-018, ADR-0154)
#
# ``received_body`` and the stub's three fields are each required in one
# stage and forbidden in another, so the record is ``X | None`` against
# ARCH-10-001's fail-fast rule.  That is paid for by checking the pairing at
# construction, in both directions, which is what these tests pin.  Disable
# ``_a_stub_keeps_no_body`` and every one of them fails.
# --------------------------------------------------------------------------

_DIGEST = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def _stub(**overrides: Any) -> ReceivedActivityRecord:
    """A whole receipt stub, as the outcome stage writes one."""
    fields: dict[str, Any] = {
        "activity_id": ACTIVITY_ID,
        "stage": ReceivedStage.REFUSED,
        "sender_id": SENDER,
        "refusal_reason": "not a to recipient (HP-01-005)",
        "body_hash": _DIGEST,
    }
    fields.update(overrides)
    return ReceivedActivityRecord(**fields)


@pytest.mark.spec("CLP-10-018")
def test_a_whole_receipt_stub_is_accepted_and_keeps_no_body():
    stub = _stub()

    assert stub.stage is ReceivedStage.REFUSED
    assert stub.is_receipt_stub
    assert stub.received_body is None
    assert stub.sender_id == SENDER
    assert stub.body_hash == _DIGEST
    assert "HP-01-005" in (stub.refusal_reason or "")
    # Still the receiver's own key, so the seen-before question stays one
    # read of one row (DL-06-006).
    assert stub.id_ == ReceivedActivityRecord.build_id(ACTIVITY_ID)


@pytest.mark.spec("CLP-10-018")
def test_a_stub_is_the_digest_of_the_body_it_gave_up():
    """The digest is the one definition both sides use (IE-10-002)."""
    stub = _stub(body_hash=received_body_digest(_body()))

    assert stub.body_hash == received_body_digest(_body())
    assert stub.body_hash != received_body_digest(_body() + " ")


@pytest.mark.spec("CLP-10-018")
@pytest.mark.parametrize("stage", sorted(BODY_BEARING_STAGES))
def test_a_body_bearing_stage_with_no_body_is_refused(stage):
    with pytest.raises(ValidationError) as caught:
        ReceivedActivityRecord(
            activity_id=ACTIVITY_ID,
            stage=stage,
            replay_owed=stage is ReceivedStage.HELD,
        )
    assert "no received body" in str(caught.value)


@pytest.mark.spec("CLP-10-017")
@pytest.mark.parametrize("field", ["sender_id", "refusal_reason", "body_hash"])
def test_a_body_bearing_record_carrying_a_stubs_field_is_refused(field):
    """Nothing derived from the body is stored beside it (ADR-0149)."""
    carried: dict[str, Any] = {field: SENDER if field == "sender_id" else "x"}
    with pytest.raises(ValidationError) as caught:
        ReceivedActivityRecord(
            activity_id=ACTIVITY_ID, received_body=_body(), **carried
        )
    assert field in str(caught.value)
    assert "only a receipt stub keeps" in str(caught.value)


@pytest.mark.spec("CLP-10-018")
def test_a_stub_that_kept_the_body_is_refused():
    """The refusal did not take effect if the message is still there."""
    with pytest.raises(ValidationError) as caught:
        _stub(received_body=_body())
    assert "still holds its received body" in str(caught.value)


@pytest.mark.spec("CLP-10-018")
@pytest.mark.parametrize("field", ["sender_id", "refusal_reason", "body_hash"])
def test_a_stub_missing_any_of_its_three_is_refused(field):
    with pytest.raises(ValidationError) as caught:
        _stub(**{field: None})
    assert f"missing {field}" in str(caught.value)


@pytest.mark.spec("CLP-10-018")
def test_a_stub_owing_a_replay_is_refused():
    """The replay would route a body that is no longer there."""
    with pytest.raises(ValidationError) as caught:
        _stub(replay_owed=True)
    assert "owes a replay" in str(caught.value)


@pytest.mark.spec("CLP-10-018")
def test_the_stub_invariant_survives_assignment():
    """``validate_assignment`` applies it after construction too."""
    stub = _stub()
    with pytest.raises(ValidationError):
        stub.stage = ReceivedStage.ARCHIVED
    record = _record()
    with pytest.raises(ValidationError):
        record.refusal_reason = "refused"


@pytest.mark.spec("CLP-10-018")
def test_a_receipt_stub_round_trips_through_the_datalayer(dl):
    dl.create(_stub())

    stored = dl.read(ReceivedActivityRecord.build_id(ACTIVITY_ID))
    assert isinstance(stored, ReceivedActivityRecord)
    assert stored.is_receipt_stub
    assert stored.received_body is None
    assert stored.sender_id == SENDER
    assert stored.body_hash == _DIGEST
