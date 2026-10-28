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

"""Loading a received activity from the body the receiver archived (ADR-0149)."""

from collections.abc import Iterator
from typing import Any

import pytest

from test.support.received import (
    archive_delivered,
    delivered_body,
    hold_deferred,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.received_archive import (
    load_received_view,
    read_held_as_received,
    read_received_as_received,
)
from vultron.core.models.received_activity_view import ReceivedActivityView
from vultron.errors import VultronNotFoundError
from vultron.wire.as2.factories import add_note_to_case_activity
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

_ME = "https://example.org/actors/me"
_PEER = "https://example.org/actors/peer"
_CASE = "https://example.org/cases/archive"


@pytest.fixture
def dl() -> Iterator[SqliteDataLayer]:
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=_ME)
    yield store
    store.close()


def _add(note_id: str = "https://example.org/notes/n-1"):
    return add_note_to_case_activity(
        as_Note(id_=note_id, content="as received", context=_CASE),
        target=_CASE,
        context=_CASE,
        actor=_PEER,
        to=[_ME],
    )


def _body(activity: Any) -> dict[str, Any]:
    body: dict[str, Any] = delivered_body(activity)
    return body


@pytest.mark.spec("DL-06-004")
def test_the_reply_seam_parses_the_archived_body_with_its_evidence(dl):
    """The parsed activity carries the archived body as its evidence, a key
    no vocabulary names included, so a reply can embed it verbatim."""
    body = {**_body(_add()), "x-peerExtension": [1, 2]}
    archive_delivered(dl, body)

    parsed = read_received_as_received(dl, body["id"])

    assert parsed.id_ == body["id"]
    assert parsed.received_evidence == body


@pytest.mark.spec("DL-06-001")
def test_core_s_view_is_the_extraction_of_the_archived_body(dl):
    add = _add()
    archive_delivered(dl, _body(add))

    view = load_received_view(dl, add.id_)

    assert isinstance(view, ReceivedActivityView)
    assert view.type_ == "Add"
    assert view.actor == _PEER


@pytest.mark.spec("DL-06-006")
def test_a_deferred_body_is_loaded_both_ways(dl):
    add = _add()
    hold_deferred(dl, add)

    view = load_received_view(dl, add.id_)
    parsed = read_received_as_received(dl, add.id_)

    assert view is not None and view.id_ == add.id_
    assert parsed.received_evidence_json is not None


@pytest.mark.spec("DL-06-006")
def test_nothing_held_is_not_found(dl):
    assert load_received_view(dl, "urn:uuid:never-held") is None
    with pytest.raises(VultronNotFoundError):
        read_received_as_received(dl, "urn:uuid:never-held", "Note")
    with pytest.raises(VultronNotFoundError):
        read_held_as_received(dl, "urn:uuid:never-held", "Note")


@pytest.mark.spec("DL-06-006")
def test_a_sent_activity_is_read_under_its_own_id(dl):
    """An activity this actor sent is held under its own id, so the held
    read returns that record and never the received loader's parse."""
    sent = _add("https://example.org/notes/sent")
    dl.create(sent)

    held = read_held_as_received(dl, sent.id_)

    assert held.id_ == sent.id_
    with pytest.raises(VultronNotFoundError):
        read_received_as_received(dl, sent.id_)
