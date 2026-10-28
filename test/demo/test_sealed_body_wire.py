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

"""The body the adapter sealed is the body that crossed the wire (VM-08-003).

Three containers, as ``test_remote_case_actor_invite`` arranges them, with the
in-process router instrumented to keep every body it POSTs.  The owner
triggers ``invite-actor-to-case``, which sends the owner's Offer to the
CaseActor; the CaseActor emits the Invite (ADR-0109).  Then:

- the body the router delivered to the invitee is the body the adapter
  sealed, byte for byte — the ledger snapshot on the emitting side is that
  same body decoded (pinned at unit level in
  ``test_actor_and_announce_nodes``), so the two agree;
- the wire carries the enriched case stub — the ``activeEmbargo`` CM-17-002
  requires for informed consent, which the old re-read-and-dehydrate delivery
  path collapsed to a bare URI (#2624).

What this deliberately does not assert is a received entry: the invitee is no
CASE_MANAGER and commits none, and a received entry recording the received
body verbatim (CLP-07-011) is pinned in
``test/core/use_cases/received/test_verbatim_received_snapshot.py``.  Nor the
invitee's stored ``Invite.target``: the receiver's record is dehydrated on
write and the invitee holds no case to rehydrate it from, so the wire body is
the only faithful probe of what arrived.
"""

import json
import re
from collections.abc import Iterator, Mapping
from typing import Any

import pytest

from test.demo._helpers import make_testclient_call
from test.demo.test_remote_case_actor_invite import (
    _bootstrap,
    _invite,
    _Topology,
)
from vultron.adapters.outbox_sealed_body import read_sealed_body
from vultron.demo.helpers.seeding import seed_case_actor_peers
from vultron.demo.in_process import (
    InProcessRouter,
    create_isolated_actor_app,
)
from vultron.demo.utils import DataLayerClient, seed_peer
from vultron.wire.as2.vocab.base.objects.actors import as_Organization

_UNSAFE_IN_HOST = re.compile(r"[^a-z0-9-]+")


class _RecordingRouter(InProcessRouter):
    """The in-process router, keeping every body it delivers."""

    def __init__(self) -> None:
        super().__init__()
        self.delivered: list[tuple[str, str, str]] = []

    async def emit(
        self,
        activity_id: str,
        json_body: str,
        recipients: list[str],
        inboxes: Mapping[str, str] | None = None,
    ) -> None:
        for recipient in recipients:
            self.delivered.append((activity_id, json_body, recipient))
        await super().emit(activity_id, json_body, recipients, inboxes)


@pytest.fixture
def recorded_topology(request):
    from vultron.adapters.driving.fastapi.outbox_handler import (
        configure_default_emitter,
        get_default_emitter,
    )

    tag = _UNSAFE_IN_HOST.sub("-", request.node.name.lower()).strip("-")
    router = _RecordingRouter()
    topo = _Topology(
        ca_host=create_isolated_actor_app(
            base_url=f"http://ca-host-{tag}.test",
            router=router,
            actor_slug="case-actor",
        ),
        owner=create_isolated_actor_app(
            base_url=f"http://owner-{tag}.test",
            router=router,
            actor_slug="owner",
        ),
        invitee=create_isolated_actor_app(
            base_url=f"http://invitee-{tag}.test",
            router=router,
            actor_slug="invitee",
        ),
    )
    previous_emitter = get_default_emitter()
    configure_default_emitter(router)  # type: ignore[arg-type]
    with topo.ca_host.client, topo.owner.client, topo.invitee.client:
        yield topo, router
    configure_default_emitter(previous_emitter)  # type: ignore[arg-type]


@pytest.mark.integration
@pytest.mark.spec("VM-08-003")
@pytest.mark.spec("CM-17-002")
class TestTheWireCarriesTheSealedBody:
    def test_delivered_body_is_the_sealed_body_byte_for_byte(
        self, recorded_topology
    ):
        topo, router = recorded_topology
        case_id = "urn:uuid:sealed-body-wire"
        _, ca_dl, _ = _bootstrap(topo, case_id)

        _invite(topo, case_id)

        invites = [
            (aid, body, to)
            for aid, body, to in router.delivered
            if json.loads(body).get("type") == "Invite"
            and to == topo.invitee_actor_id
        ]
        assert len(invites) == 1, "the invitee must receive exactly one Invite"
        invite_id, delivered_body, _ = invites[0]

        # The CaseActor emits the Invite (ADR-0109), so its store holds the seal.
        sealed = read_sealed_body(ca_dl, invite_id)
        assert sealed is not None, "the emitting store must hold the seal"
        assert delivered_body == sealed.body, (
            "the emitter must be handed the sealed body itself, byte for byte"
        )
        delivered = json.loads(delivered_body)
        assert delivered["id"] == invite_id
        assert delivered["actor"] == topo.ca_actor_id
        assert delivered["context"] == case_id

    def test_the_wire_carries_the_enriched_case_stub(self, recorded_topology):
        """CM-17-002 reaches the wire: the collapsed-stub defect (#2624) is gone."""
        topo, router = recorded_topology
        case_id = "urn:uuid:sealed-body-stub-arrives"
        _bootstrap(topo, case_id)

        _invite(topo, case_id)

        delivered = [
            json.loads(body)
            for _, body, to in router.delivered
            if to == topo.invitee_actor_id
        ]
        (invite,) = [d for d in delivered if d.get("type") == "Invite"]
        target = invite.get("target")
        assert isinstance(target, dict), (
            "Invite.target crossed the wire as a bare URI: the enriched stub was"
            f" collapsed before delivery. target={target!r}"
        )
        assert target["type"] == "VulnerabilityCaseStub"
        assert target["caseId"] == case_id
        assert target["id"] == f"{case_id}/stub"
        assert "activeEmbargo" in target, (
            "the invitee was not sent the embargo terms it is asked to consent"
            f" to (CM-17-002). target={target!r}"
        )
        assert "caseStatus" in target


#: The ActivityStreams actor types an inline actor carries.
_ACTOR_TYPES = frozenset(
    {"Actor", "Application", "Group", "Organization", "Person", "Service"}
)


def _inline_actors(value: Any) -> Iterator[dict[str, Any]]:
    """Every inline actor object anywhere in a decoded body."""
    if isinstance(value, dict):
        if value.get("type") in _ACTOR_TYPES and "id" in value:
            yield value
        for nested in value.values():
            yield from _inline_actors(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _inline_actors(nested)


def _seed_like_the_demos(topo, monkeypatch) -> None:
    """Register every actor as a peer on every other node, as the demos do.

    The demo seeders register each actor on each other actor's node
    (:func:`~vultron.demo.utils.seed_peer`) and, on the dedicated case-actor
    node, in the CaseActor's address book
    (:func:`~vultron.demo.helpers.seeding.seed_case_actor_peers`).
    """
    nodes = {
        f"{app.base_url}/api/v2": app.client
        for app in (topo.ca_host, topo.owner, topo.invitee)
    }
    calls = {
        base: make_testclient_call(client, base)
        for base, client in nodes.items()
    }
    monkeypatch.setattr(
        DataLayerClient,
        "call",
        lambda self, method, path, **kw: calls[self.base_url](
            self, method, path, **kw
        ),
    )
    owner = as_Organization(id_=topo.owner_actor_id, name="Owner")
    invitee = as_Organization(id_=topo.invitee_actor_id, name="Invitee")
    seed_peer(
        DataLayerClient(base_url=f"{topo.owner.base_url}/api/v2"),
        local_actor_id=topo.owner_actor_id,
        peer_id=invitee.id_,
        name="Invitee",
    )
    seed_case_actor_peers(
        DataLayerClient(base_url=f"{topo.ca_host.base_url}/api/v2"),
        [owner, invitee],
    )


@pytest.mark.integration
@pytest.mark.spec("AKM-05-005")
def test_every_actor_a_seeded_demo_names_travels_as_its_profile(
    recorded_topology, monkeypatch
):
    """No actor in a seeded demo's traffic travels as a bare reference.

    The demos seed every peer they name, the CaseActor's address book among
    them, so each actor an activity carries inline is the seeded profile the
    sender holds, never an id-and-type actor reference (ADR-0159).
    """
    topo, router = recorded_topology
    case_id = "urn:uuid:sealed-body-seeded-profiles"
    _bootstrap(topo, case_id)
    _seed_like_the_demos(topo, monkeypatch)

    _invite(topo, case_id)

    carried = [
        actor
        for _, body, _ in router.delivered
        for actor in _inline_actors(json.loads(body))
    ]
    invitee = [a for a in carried if a["id"] == topo.invitee_actor_id]
    assert invitee, "the Invite must carry the invitee inline"
    references = [a for a in carried if "name" not in a]
    assert references == [], (
        "a seeded demo sent an actor as a bare reference, not its profile"
    )
    assert {a["name"] for a in invitee} == {"Invitee"}
