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
"""SYNC integration tests for single-peer CaseLogEntry replication (#901)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from vultron.adapters.driven.asgi_emitter import ASGIEmitter
from test.demo.conftest import _TestASGIRouter, create_isolated_actor_app
from vultron.adapters.driving.fastapi.outbox_handler import (
    configure_default_emitter,
    get_default_emitter,
)
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

_CASE_ACTOR_BASE = "http://case-actor-sync-901.test"
_PEER_BASE = "http://peer-sync-901.test"


def _actor_slug(actor_id: str) -> str:
    return actor_id.rstrip("/").rsplit("/", 1)[-1]


def _create_actor(client, base_api: str, slug: str, actor_type: str) -> str:
    actor_id = f"{base_api}/actors/{slug}"
    response = client.post(
        "/api/v2/actors/",
        json={"type": actor_type, "name": slug, "id": actor_id},
    )
    assert response.status_code in (
        200,
        201,
    ), f"Actor creation failed ({response.status_code}): {response.text}"
    return actor_id


@pytest.fixture
def two_app_setup() -> Iterator[tuple]:
    """Create two isolated actor apps connected by ``_TestASGIRouter``."""
    router = _TestASGIRouter()
    case_actor_iso = create_isolated_actor_app(
        base_url=_CASE_ACTOR_BASE, router=router
    )
    peer_iso = create_isolated_actor_app(base_url=_PEER_BASE, router=router)

    previous_emitter = get_default_emitter()
    configure_default_emitter(router)  # type: ignore[arg-type]

    with case_actor_iso.client as case_actor_tc:
        with peer_iso.client as peer_tc:
            for iso in (case_actor_iso, peer_iso):
                emitter = getattr(iso.app.state, "emitter", None)
                if isinstance(emitter, ASGIEmitter):
                    emitter._http_fallback = router  # type: ignore[assignment]
            yield case_actor_iso, peer_iso, case_actor_tc, peer_tc

    configure_default_emitter(previous_emitter)  # type: ignore[arg-type]
    case_actor_iso.dl.close()
    peer_iso.dl.close()


@pytest.mark.spec("SYNC-07-002")
@pytest.mark.spec("SYNC-02-003")
def test_sync_single_peer_happy_path_replication(two_app_setup) -> None:
    """CaseActor commit should replicate one CaseLogEntry to a peer replica."""
    case_actor_iso, peer_iso, case_actor_tc, peer_tc = two_app_setup

    case_actor_base_api = f"{case_actor_iso.base_url}/api/v2"
    peer_base_api = f"{peer_iso.base_url}/api/v2"

    case_actor_id = _create_actor(
        case_actor_tc, case_actor_base_api, "case-actor-sync-901", "Service"
    )
    peer_actor_id = _create_actor(
        peer_tc, peer_base_api, "peer-sync-901", "Organization"
    )
    # CaseActor must know peer recipient for outbox routing.
    _create_actor(
        case_actor_tc, peer_base_api, "peer-sync-901", "Organization"
    )

    case = VulnerabilityCase(name="SYNC-901 integration case")
    case_actor_participant = CaseParticipant(
        attributed_to=case_actor_id,
        context=case.id_,
    )
    peer_participant = CaseParticipant(
        attributed_to=peer_actor_id,
        context=case.id_,
    )
    case.case_participants.append(case_actor_participant.id_)
    case.case_participants.append(peer_participant.id_)
    case.actor_participant_index[case_actor_id] = case_actor_participant.id_
    case.actor_participant_index[peer_actor_id] = peer_participant.id_

    case_actor_iso.dl.save(case_actor_participant)
    case_actor_iso.dl.save(peer_participant)
    case_actor_iso.dl.save(case)

    response = case_actor_tc.post(
        f"/api/v2/actors/{_actor_slug(case_actor_id)}/demo/sync-log-entry",
        json={
            "case_id": case.id_,
            "object_id": case.id_,
            "event_type": "sync_901_happy_path",
        },
    )
    assert response.status_code == 202, response.text
    payload = response.json()

    entry_id = payload["log_entry_id"]
    peer_entry = peer_iso.dl.read(entry_id)
    assert (
        peer_entry is not None
    ), "Expected peer replica to contain the announced CaseLogEntry."
    assert peer_entry.case_id == case.id_
    assert peer_entry.log_index == payload["log_index"]
    assert peer_entry.entry_hash == payload["entry_hash"]
    assert peer_entry.log_object_id == case.id_
    assert peer_entry.event_type == "sync_901_happy_path"

    # AC-4 guard: each actor app uses its own isolated DataLayer.
    assert case_actor_iso.dl is not peer_iso.dl
