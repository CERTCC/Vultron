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
"""A received actor reference never replaces a fuller held record (ADR-0159).

Spec coverage:
- AKM-05-005: a receiver reads the fields an actor reference lacks as unknown.

Drives the real FastAPI ingress and dispatch adapters with an ``Offer(Actor)``
whose actor is an id-and-type reference, sent to a CASE_MANAGER that already
holds the actor's full profile.
"""

from collections.abc import Iterator
from typing import Any

import pytest

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_owner_participant,
)
from test.support.received import delivered_body
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.inbox_handler import make_dispatcher
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIDispatchAdapter,
    FastAPIIngressAdapter,
)
from vultron.core.behaviors.inbox import InboxOutcomeStatus, process_payload
from vultron.wire.as2.factories import recommend_actor_activity
from vultron.wire.as2.vocab.base.objects.actors import as_Organization
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_CASE_ACTOR_ID = "https://example.org/actors/case-actor-ref"
_VENDOR_ID = "https://example.org/users/vendor-ref"
_PEER_ID = "https://example.org/users/peer-ref"
_CASE_ID = "https://example.org/cases/case-ref"


@pytest.fixture(autouse=True)
def clear_actor_locks() -> Iterator[None]:
    from vultron.adapters.driving.fastapi import inbox_orchestration

    inbox_orchestration._actor_inbox_locks.clear()
    yield
    inbox_orchestration._actor_inbox_locks.clear()


@pytest.fixture
def case_actor_dl() -> Iterator[SqliteDataLayer]:
    """The CASE_MANAGER's store, holding the peer's full profile."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_ID)
    dl.clear_all()
    case = as_VulnerabilityCase(
        id_=_CASE_ID,
        name="Reference receipt",
        stub_summary="A case the peer is recommended to",
        attributed_to=_VENDOR_ID,
    )
    seed_case_manager_participant(dl, case, _CASE_ACTOR_ID)
    seed_case_owner_participant(dl, case, _VENDOR_ID)
    dl.create(case)
    dl.create(as_Organization(id_=_PEER_ID, name="Peer Co"))
    yield dl
    dl.clear_all()
    dl.close()


def _recommendation_with_reference() -> dict[str, Any]:
    """An ``Offer(Actor)`` whose actor is an id-and-type actor reference."""
    offer = recommend_actor_activity(
        recommended=_PEER_ID,
        target=_CASE_ID,
        actor=_VENDOR_ID,
        to=[_CASE_ACTOR_ID],
        suggested_roles=["vendor"],
    )
    body = delivered_body(offer)
    body["object"] = {"id": _PEER_ID, "type": "Actor"}
    return body


@pytest.mark.spec("AKM-05-005")
def test_a_received_actor_reference_keeps_the_held_profile(case_actor_dl):
    outcome = process_payload(
        _recommendation_with_reference(),
        FastAPIIngressAdapter(dl=case_actor_dl),
        FastAPIDispatchAdapter(
            dl=case_actor_dl,
            actor_id=_CASE_ACTOR_ID,
            dispatcher=make_dispatcher(),
        ),
    )

    assert outcome.status is InboxOutcomeStatus.PROCESSED, (
        outcome.failure_reason
    )
    held = case_actor_dl.read(_PEER_ID)
    assert held is not None
    assert getattr(held, "name", None) == "Peer Co"
