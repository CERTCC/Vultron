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
        "vultron.adapters.driving.fastapi.routers.actors._routes.outbox_handler",
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
