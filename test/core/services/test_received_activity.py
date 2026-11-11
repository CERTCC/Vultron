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

"""Reading an activity as this actor holds it (CLP-10-017, DL-06-006, ADR-0149)."""

import json
from typing import Any

import pytest

from test.support.act_clock import ACT_AT
from test.support.received import archive_received, case_stub, hold_deferred
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
    ReceivedStage,
)
from vultron.core.models.received_activity_view import ReceivedActivityView
from vultron.core.services.received_activity import (
    held_received_body,
    held_received_record,
    holds_activity,
    holds_received_activity,
    read_held_activity,
    read_received_activity,
    sealed_body_of,
)
from vultron.errors import (
    VultronNotFoundError,
    VultronReadOnlyViewError,
    VultronWiringError,
)
from vultron.wire.as2.factories import (
    add_note_to_case_activity,
    rm_invite_to_case_activity,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

_ME = "https://example.org/actors/me"
_PEER = "https://example.org/actors/peer"
_CASE = "https://example.org/cases/held"


@pytest.fixture
def dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=_ME)


@pytest.fixture
def loader(dl: SqliteDataLayer) -> TriggerActivityAdapter:
    return TriggerActivityAdapter(dl)


def _invite(actor: str, invitee: str):
    return rm_invite_to_case_activity(
        invitee, target=case_stub(_CASE), actor=actor, to=[invitee]
    )


def _read(reader: Any, loader: Any, dl: Any, *args: str) -> Any:
    """Call *reader* with the arguments it takes."""
    if reader is read_held_activity:
        return reader(loader, dl, *args)
    return reader(loader, *args)


@pytest.mark.spec("DL-06-006")
@pytest.mark.spec("DL-06-001")
@pytest.mark.parametrize(
    "reader", [read_held_activity, read_received_activity]
)
def test_a_received_activity_is_loaded_from_its_archived_body(
    dl, loader, reader
) -> None:
    invite = _invite(_PEER, _ME)
    archive_received(dl, invite)
    assert dl.read(invite.id_) is None

    held = _read(reader, loader, dl, invite.id_)

    assert isinstance(held, ReceivedActivityView)
    assert held.id_ == invite.id_
    assert held.type_ == "Invite"
    assert getattr(held.target, "case_id", None) == _CASE


@pytest.mark.spec("DL-06-006")
def test_an_activity_this_actor_sent_is_read_under_its_own_id(
    dl, loader
) -> None:
    invite = _invite(_ME, _PEER)
    dl.create(invite)

    held = read_held_activity(loader, dl, invite.id_)

    assert held.id_ == invite.id_


@pytest.mark.parametrize(
    "reader", [read_held_activity, read_received_activity]
)
def test_an_activity_this_store_does_not_hold_is_not_found(
    dl, loader, reader
) -> None:
    with pytest.raises(VultronNotFoundError, match="Invite"):
        _read(reader, loader, dl, "urn:uuid:never-held", "Invite")


def _deferred_add(dl: SqliteDataLayer):
    add = add_note_to_case_activity(
        as_Note(content="waiting on its case", context=_CASE),
        target=_CASE,
        context=_CASE,
        actor=_PEER,
        to=[_ME],
    )
    hold_deferred(dl, add)
    return add


@pytest.mark.spec("DL-06-006")
@pytest.mark.parametrize(
    "reader", [read_held_activity, read_received_activity]
)
def test_a_deferred_activity_is_loaded_from_the_body_held_for_it(
    dl, loader, reader
) -> None:
    """Before intake archives it, the inbox's deferred record's body is
    parsed again: no summary of it is held beside the body (ADR-0149)."""
    add = _deferred_add(dl)
    assert dl.read(add.id_) is None

    held = _read(reader, loader, dl, add.id_)

    assert isinstance(held, ReceivedActivityView)
    assert held.id_ == add.id_
    assert held.type_ == "Add"


@pytest.mark.spec("DL-06-006")
def test_a_received_read_never_falls_back_to_the_senders_id(
    dl, loader
) -> None:
    """A row under the activity's own id is not a received activity."""
    invite = _invite(_PEER, _ME)
    dl.create(invite)

    with pytest.raises(VultronNotFoundError):
        read_received_activity(loader, invite.id_, "Invite")


@pytest.mark.spec("DL-06-006")
def test_holding_is_read_from_the_records_alone(dl) -> None:
    """``holds_*`` answers from the receiver's keys, and the sender's id
    counts only for an activity this actor sent."""
    received = _invite(_PEER, _ME)
    archive_received(dl, received)
    deferred = _deferred_add(dl)
    sent = _invite(_ME, _PEER)
    dl.create(sent)

    assert holds_received_activity(dl, received.id_)
    assert holds_received_activity(dl, deferred.id_)
    assert not holds_received_activity(dl, sent.id_)
    assert holds_activity(dl, sent.id_)
    assert not holds_activity(dl, "urn:uuid:never-held")


@pytest.mark.spec("DL-06-001")
def test_the_loaded_view_is_read_only_and_the_next_load_is_unchanged(
    dl, loader
) -> None:
    """Assigning to the view, or to an object nested in it, raises, and
    the next load is parsed afresh from the body (ADR-0149, AC-3)."""
    invite = _invite(_PEER, _ME)
    archive_received(dl, invite)
    view = read_received_activity(loader, invite.id_)

    with pytest.raises(VultronReadOnlyViewError):
        view.type_ = "Accept"
    with pytest.raises(VultronReadOnlyViewError):
        view.target.case_id = "https://example.org/cases/elsewhere"
    with pytest.raises(VultronReadOnlyViewError):
        del view.to
    with pytest.raises(AttributeError):
        view.to.append(_PEER)  # a tuple, not the list it was parsed into

    again = read_received_activity(loader, invite.id_)
    assert again == view
    assert again.type_ == "Invite"
    assert again.target.case_id == _CASE
    assert list(again.to) == [_ME]


@pytest.mark.spec("CLP-10-017")
@pytest.mark.spec("DL-06-004")
def test_the_archived_body_is_handed_out_decoded(dl) -> None:
    invite = _invite(_PEER, _ME)
    record = archive_received(dl, invite)

    assert held_received_body(dl, invite.id_) == json.loads(
        sealed_body_of(record)
    )


@pytest.mark.spec("CLP-10-017")
def test_a_body_still_held_for_a_replay_is_handed_out_too(dl) -> None:
    """A reader in the run reads the holding record, whatever stage it is in.

    The message is the same message whether intake archived it or a wait
    still holds it, so the reader does not ask which (ADR-0154).
    """
    deferred = _deferred_add(dl)
    record = held_received_record(dl, deferred.id_)
    assert record is not None
    assert record.stage is ReceivedStage.HELD

    assert held_received_body(dl, deferred.id_) == json.loads(
        sealed_body_of(record)
    )


@pytest.mark.spec("ARCH-15-001")
def test_a_body_this_receiver_does_not_hold_is_a_wiring_fault(dl) -> None:
    """The refusal notice runs inside the run, so a body it cannot find
    means the tree is miswired."""
    with pytest.raises(VultronWiringError, match="not held by this receiver"):
        held_received_body(dl, "urn:uuid:never-held")


@pytest.mark.spec("CLP-10-018")
def test_a_receipt_stub_has_no_body_to_hand_out(dl) -> None:
    """All a refusal left is the receipt; there is no message to embed."""
    dl.create(
        ReceivedActivityRecord(
            activity_id="urn:uuid:refused-one",
            stage=ReceivedStage.REFUSED,
            sender_id=_PEER,
            refusal_reason="not a to recipient",
            body_hash="abc123",
            received_at=ACT_AT,
        )
    )

    with pytest.raises(VultronWiringError, match="receipt stub"):
        held_received_body(dl, "urn:uuid:refused-one")
