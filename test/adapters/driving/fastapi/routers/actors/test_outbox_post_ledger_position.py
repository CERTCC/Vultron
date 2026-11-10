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
"""A case activity posted to an actor's outbox states its ledger tail (SYNC-18-001)."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.deps import get_actor_dl
from vultron.adapters.driving.fastapi.routers import actors as actors_router
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.ledger_position import EMPTY_LEDGER_LOG_INDEX
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.models.sender_sequence import SenderSequenceCounter
from vultron.wire.as2.factories import add_note_to_case_activity
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.base.objects.object_types import as_Note


@pytest.fixture
def actor_dl() -> Iterator[tuple[as_Service, SqliteDataLayer]]:
    actor = as_Service(name="Vendor Co")
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor.id_)
    dl.create(actor)
    yield actor, dl
    dl.clear_all()
    dl.close()


_MANAGER = "https://example.org/users/manager"


def _post(dl: SqliteDataLayer, actor: as_Service, activity, monkeypatch):
    return _post_content(
        dl,
        actor,
        activity.model_dump_json(by_alias=True, exclude_none=True).encode(),
        monkeypatch,
    )


def _post_content(
    dl: SqliteDataLayer, actor: as_Service, content: bytes, monkeypatch
):
    # The outbox drain is not this test's subject.
    monkeypatch.setattr(
        "vultron.adapters.driving.fastapi.routers.actors._routes.mailbox"
        ".outbox_handler",
        lambda *args, **kwargs: None,
    )
    app = FastAPI()
    app.include_router(actors_router.router)
    app.dependency_overrides[get_actor_dl] = lambda: dl
    return TestClient(app).post(
        f"/actors/{actor.id_}/outbox/",
        content=content,
        headers={"Content-Type": "application/json"},
    )


def _case_with_manager(
    dl: SqliteDataLayer, actor: as_Service
) -> VulnerabilityCase:
    case = VulnerabilityCase(attributed_to=actor.id_)
    dl.create(case)
    # The address the case's CASE_MANAGER was reached at (CBT-01-006).
    dl.save(
        VultronReportCaseLink(
            report_id=f"{case.id_}/report",
            case_id=case.id_,
            case_manager_id=_MANAGER,
        )
    )
    return case


def _note_to_manager(case: VulnerabilityCase, actor: as_Service, tag: str):
    return add_note_to_case_activity(
        as_Note(id_=f"{case.id_}/notes/{tag}", content=tag, context=case.id_),
        target=case.id_,
        actor=actor.id_,
        to=[_MANAGER],
    )


def _posted_number(dl, actor, activity, monkeypatch) -> object:
    response = _post(dl, actor, activity, monkeypatch)
    assert response.status_code == 200, response.text
    body = read_sealed_body_dict(dl, activity.id_)
    assert body is not None
    return body.get("senderSequence")


@pytest.mark.spec("SYNC-21-001")
@pytest.mark.spec("SYNC-21-002")
def test_posted_activities_to_the_case_manager_are_numbered_one_up(
    actor_dl, monkeypatch
) -> None:
    actor, dl = actor_dl
    case = _case_with_manager(dl, actor)

    numbers = [
        _posted_number(
            dl, actor, _note_to_manager(case, actor, n), monkeypatch
        )
        for n in ("1", "2")
    ]

    assert numbers == [1, 2]


@pytest.mark.spec("SYNC-21-002")
def test_a_posted_number_is_kept_and_never_used_again(
    actor_dl, monkeypatch
) -> None:
    actor, dl = actor_dl
    case = _case_with_manager(dl, actor)
    numbered = _note_to_manager(case, actor, "numbered").model_copy(
        update={"sender_sequence": 5}
    )

    kept = _posted_number(dl, actor, numbered, monkeypatch)
    after = _posted_number(
        dl, actor, _note_to_manager(case, actor, "after"), monkeypatch
    )

    assert (kept, after) == (5, 6)


class _QueueDown(Exception):
    """The outbox append fails after the number is allocated."""


@pytest.mark.spec("SYNC-21-003")
def test_a_post_whose_outbox_append_fails_gives_its_number_back(
    actor_dl, monkeypatch
) -> None:
    actor, dl = actor_dl
    case = _case_with_manager(dl, actor)
    lost = _note_to_manager(case, actor, "lost")

    def _fail(_activity_id: str) -> None:
        raise _QueueDown

    with monkeypatch.context() as patch:
        patch.setattr(dl, "outbox_append", _fail)
        with pytest.raises(_QueueDown):
            _post(dl, actor, lost, monkeypatch)

    assert read_sealed_body_dict(dl, lost.id_) is None
    assert dl.read(SenderSequenceCounter.build_id(case.id_, actor.id_)) is None
    assert (
        _posted_number(
            dl, actor, _note_to_manager(case, actor, "next"), monkeypatch
        )
        == 1
    )


@pytest.mark.spec("SYNC-18-001")
def test_a_posted_case_activity_is_sealed_with_the_actors_tail(
    actor_dl, monkeypatch
) -> None:
    actor, dl = actor_dl
    case = VulnerabilityCase(attributed_to=actor.id_)
    dl.create(case)
    note = add_note_to_case_activity(
        as_Note(id_=f"{case.id_}/notes/1", content="n", context=case.id_),
        target=case.id_,
        actor=actor.id_,
        to=["https://example.org/users/manager"],
    )
    # The outbox drain is not this test's subject.
    monkeypatch.setattr(
        "vultron.adapters.driving.fastapi.routers.actors._routes.mailbox"
        ".outbox_handler",
        lambda *args, **kwargs: None,
    )
    app = FastAPI()
    app.include_router(actors_router.router)
    app.dependency_overrides[get_actor_dl] = lambda: dl

    response = TestClient(app).post(
        f"/actors/{actor.id_}/outbox/",
        content=note.model_dump_json(by_alias=True, exclude_none=True),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200, response.text
    body = read_sealed_body_dict(dl, note.id_)
    assert body is not None
    assert body["ledgerPosition"] == {
        "logIndex": EMPTY_LEDGER_LOG_INDEX,
        "entryHash": case.genesis_hash,
    }


@pytest.mark.spec("SIG-01-001")
def test_a_posted_activity_that_cannot_be_signed_is_refused_422(
    actor_dl, monkeypatch
) -> None:
    """The signer's refusal is the client's content, so 422; nothing is kept."""
    from vultron.adapters import outbox_sealed_body
    from vultron.wire.as2.errors import VultronUnsignableJsonError

    def _refuse(_activity: object, _owner_id: str) -> str:
        raise VultronUnsignableJsonError("value cannot be canonicalized")

    monkeypatch.setattr(outbox_sealed_body, "signed_outbound_body", _refuse)
    actor, dl = actor_dl
    case = _case_with_manager(dl, actor)
    note = _note_to_manager(case, actor, "unsignable")

    response = _post(dl, actor, note, monkeypatch)

    assert response.status_code == 422, response.text
    assert response.json()["detail"]["error"] == "ValidationError"
    assert dl.read(note.id_) is None
    assert read_sealed_body_dict(dl, note.id_) is None
    assert dl.outbox_list() == []


@pytest.mark.spec("SIG-05-004")
def test_a_posted_activity_another_actor_wrote_is_refused_400(
    actor_dl, monkeypatch
) -> None:
    """An outbox signs only its own actor's activities: a foreign one is 400.

    Nothing is stored, sealed or queued, and no key is computed for the
    foreign author.
    """
    from vultron.wire.as2 import signing

    computed: list[str] = []
    monkeypatch.setattr(signing, "seeded_signing_key", computed.append)
    actor, dl = actor_dl
    case = _case_with_manager(dl, actor)
    foreign = _note_to_manager(case, actor, "foreign").model_copy(
        update={"actor": _MANAGER}
    )

    response = _post(dl, actor, foreign, monkeypatch)

    assert response.status_code == 400, response.text
    assert computed == []
    assert dl.read(foreign.id_) is None
    assert read_sealed_body_dict(dl, foreign.id_) is None
    assert dl.outbox_list() == []


def test_a_posted_activity_keeps_its_object_and_target(
    actor_dl, monkeypatch
) -> None:
    """The wire parser reads the body, so its ``object`` and ``target`` are
    sealed as posted; the bare ``as_Activity`` dropped both."""
    actor, dl = actor_dl
    case = _case_with_manager(dl, actor)
    note = _note_to_manager(case, actor, "kept")

    response = _post(dl, actor, note, monkeypatch)

    assert response.status_code == 200, response.text
    body = read_sealed_body_dict(dl, note.id_)
    assert body is not None
    assert body["type"] == "Add"
    assert body["object"]["id"] == f"{case.id_}/notes/kept"
    assert body["object"]["content"] == "kept"
    assert body["target"] == case.id_


@pytest.mark.spec("IE-07-001")
@pytest.mark.parametrize(
    "content",
    [
        pytest.param(b"not json", id="not-json"),
        pytest.param(b'{"ratio": NaN}', id="nan"),
        pytest.param('{"type": "Add"}'.encode("utf-16"), id="utf-16"),
    ],
)
def test_a_posted_body_that_is_not_json_is_refused_400(
    actor_dl, monkeypatch, content: bytes
) -> None:
    """The outbox decodes its body as the inbox does (RFC 9110)."""
    actor, dl = actor_dl

    response = _post_content(dl, actor, content, monkeypatch)

    assert response.status_code == 400, response.text
    assert response.json()["detail"]["error"] == "JsonSyntaxError"
    assert dl.outbox_list() == []


@pytest.mark.spec("IE-04-002")
@pytest.mark.parametrize(
    "content",
    [
        pytest.param(b"[1, 2]", id="not-an-object"),
        pytest.param(b'{"type": "Add", "type": "Note"}', id="duplicate-key"),
    ],
)
def test_a_posted_body_of_refused_json_is_refused_422(
    actor_dl, monkeypatch, content: bytes
) -> None:
    actor, dl = actor_dl

    response = _post_content(dl, actor, content, monkeypatch)

    assert response.status_code == 422, response.text
    assert response.json()["detail"]["error"] == "ValidationError"
    assert dl.outbox_list() == []
