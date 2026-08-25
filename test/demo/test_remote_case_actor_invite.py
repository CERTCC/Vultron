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

"""``invite-actor-to-case`` when the case's CaseActor is on another container.

PCR-08-007 has the Invite go out from the *CaseActor's* identity, so
``SvcInviteActorToCaseUseCase._prepare`` sets ``self._actor_id`` to whatever
``_find_case_actor_id`` resolves and the BT then runs as that actor.  Under
ADR-0073 "runs as that actor" means "in that actor's store", which
``BTBridge._store_for_actor`` arranges by cloning the handed DataLayer.

That is sound while the CaseActor is co-hosted with the actor holding the case.
It is not sound after a handoff.  ``_find_case_actor_id`` path 3 resolves the
``CVDRole.CASE_MANAGER`` participant whenever its id has the container-level
CaseActor shape (``.../actors/case-actor``, ADR-0041), and that shape answers
for *remote* containers just as readily as local ones — which is the point of
it, since a replica's CASE_MANAGER is normally somewhere else.  So on a
post-handoff owner the resolved CaseActor is on a different authority, and
``clone_for_actor`` happily mints a fresh **empty local** store for it: no case,
no participants, no ledger.  Nothing raises.

This module pins down that configuration, because three things have to hold and
none of them is obvious from reading the emit path:

* the Invite still reaches the invitee, from the CaseActor's identity;
* the emitted Invite carries the case (CM-17-002) rather than a bare id string,
  which it cannot do if the store the emit reads has no case in it;
* the ledger entry lands in a store somebody reads.

Only a multi-node setup can show this, and only since each node in this harness
got its *own* storage deployment: while every node shared one anonymous
``sqlite:///:memory:``, the cross-authority slug collision that
:func:`~vultron.adapters.driven.datalayer_sqlite.engine.actor_slug` produces for
two ``.../actors/case-actor`` ids (#2549) resolved to a single shared store, so
the phantom store *was* the real one and this whole failure mode was invisible
locally while failing under Docker.  See ``test/demo/conftest.py::node_db_url``.

Issue: #2484
"""

import re
from dataclasses import dataclass

import pytest

from test.demo.conftest import (
    IsolatedActorApp,
    _TestClientRouter,
    create_isolated_actor_app,
)
from vultron.core.models.actor import CoreActor
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import EmDimension
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.states.em import EM
from vultron.enums.roles import CVDRole

#: Characters that cannot appear in a hostname label.
_UNSAFE_IN_HOST = re.compile(r"[^a-z0-9-]+")


@dataclass(frozen=True)
class _Topology:
    """Three containers, as ``docker-compose-multi-actor.yml`` arranges them.

    The CaseActor is self-hosted by the container that first received the report
    (CP-08-003), which after a handoff is *not* the container that owns the case.
    So ``ca_host`` and ``owner`` are separate nodes, and the CaseActor's actor id
    is under ``ca_host``'s authority while the case replica lives on ``owner``.

    Attributes:
        ca_host: The node hosting the case's CaseActor and the authoritative case.
        owner: The node holding the case replica and answering the trigger.
        invitee: The node hosting the actor being invited.
    """

    ca_host: IsolatedActorApp
    owner: IsolatedActorApp
    invitee: IsolatedActorApp

    @property
    def ca_actor_id(self) -> str:
        """Container-level CaseActor identity on the CaseActor's node (ADR-0041)."""
        return f"{self.ca_host.base_url}/api/v2/actors/case-actor"

    @property
    def owner_actor_id(self) -> str:
        return f"{self.owner.base_url}/api/v2/actors/owner"

    @property
    def invitee_actor_id(self) -> str:
        return f"{self.invitee.base_url}/api/v2/actors/invitee"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def topology(request):
    """CaseActor host + case owner + invitee, each its own container.

    Base URLs carry the test's own name, so every test gets three genuinely
    fresh stores.  ``get_datalayer`` caches on ``(actor_id, db_url)`` and this
    harness derives ``db_url`` from the node's base URL, so tests sharing a base
    URL would share stores across the whole module and each would inherit the
    last one's records.

    The *slug* stays ``case-actor`` in every case: that is what
    :func:`~vultron.core.behaviors.case.case_actor_identity.is_case_actor_identity`
    reads, and varying the authority instead is also what keeps the
    cross-authority slug collision (#2549) in play — which is the condition
    under test.

    Deliberately does *not* patch ``VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL``: the
    replica is seeded directly with a remote CASE_MANAGER, which is the state a
    handoff leaves behind, and resolution is by identity shape rather than by
    configuration.  Patching it would only obscure which input the resolver
    actually reads.

    Yields:
        The :class:`_Topology` for this test, with all three clients entered.
    """
    from vultron.adapters.driving.fastapi.outbox_handler import (
        configure_default_emitter,
        get_default_emitter,
    )

    tag = _UNSAFE_IN_HOST.sub("-", request.node.name.lower()).strip("-")
    router = _TestClientRouter()
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
        yield topo

    configure_default_emitter(previous_emitter)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_actor(client, actor_id: str, name: str, type_: str) -> None:
    """Create *actor_id* on the node behind *client*."""
    resp = client.post(
        "/api/v2/actors/",
        json={"type": type_, "name": name, "id": actor_id},
    )
    assert resp.status_code in (200, 201), (
        f"Actor creation for '{actor_id}' failed"
        f" ({resp.status_code}): {resp.text}"
    )


def _seed_case(dl, topo: _Topology, case_id: str) -> None:
    """Write a case replica whose CASE_MANAGER is the remote CaseActor.

    This is the post-handoff shape: the participant wearing
    ``CVDRole.CASE_MANAGER`` is attributed to a CaseActor on a container the
    node holding this replica does not host (CP-09-004).

    The case is seeded **under an active embargo**, and that is load-bearing
    rather than incidental colour.  ``_project_case_to_stub`` enriches the
    Invite's ``target`` only when ``em_state == EM.ACTIVE`` and the case names
    an ``active_embargo`` (CM-17-002); with no embargo it returns a stub
    carrying nothing but an id, which AS2 serialises to a bare URI string —
    exactly what a *failed* case read produces.  Under an active embargo the two
    outcomes finally differ, so ``test_the_invite_carries_the_case_not_a_bare_id``
    can tell "read the case" from "read an empty store".
    """
    manager = CaseParticipant(
        id_=f"{case_id}/participants/case-actor",
        attributed_to=topo.ca_actor_id,
        case_roles=[CVDRole.COORDINATOR, CVDRole.CASE_MANAGER],
    )
    owner_participant = CaseParticipant(
        id_=f"{case_id}/participants/owner",
        attributed_to=topo.owner_actor_id,
        case_roles=[CVDRole.VENDOR],
    )
    embargo = EmbargoEvent(
        id_=f"{case_id}/embargoes/e0",
        context=case_id,
    )
    case = VulnerabilityCase(
        id_=case_id,
        name="remote CaseActor invite",
        attributed_to=topo.ca_actor_id,
        case_participants=[manager, owner_participant],
        actor_participant_index={
            topo.ca_actor_id: str(manager.id_),
            topo.owner_actor_id: str(owner_participant.id_),
        },
        case_statuses=[
            CaseStatus(
                context=case_id,
                attributed_to=topo.ca_actor_id,
                em=EmDimension(state=EM.ACTIVE),
            )
        ],
        active_embargo=str(embargo.id_),
    )
    dl.create(manager)
    dl.create(owner_participant)
    dl.create(embargo)
    dl.create(case)
    if dl.read(topo.ca_actor_id) is None:
        # The owner knows the CaseActor as a peer — a handoff leaves this
        # behind — but knowing a URI is not the same as hosting what it names.
        dl.create(CoreActor(id_=topo.ca_actor_id, name="Case Actor"))


def _bootstrap(topo: _Topology, case_id: str):
    """Provision the three actors and seed both copies of the case.

    Returns:
        Tuple of (owner_dl, ca_dl, invitee_dl) — each node's store for the actor
        it hosts.  The CaseActor's node gets the authoritative case, the owner's
        node a replica; which of the two the owner's emit actually touches is
        what the assertions are about.
    """
    _create_actor(
        topo.ca_host.client, topo.ca_actor_id, "Case Actor", "Service"
    )
    _create_actor(
        topo.owner.client, topo.owner_actor_id, "Owner", "Organization"
    )
    _create_actor(
        topo.invitee.client, topo.invitee_actor_id, "Invitee", "Organization"
    )

    owner_dl = topo.owner.store_for(topo.owner_actor_id)
    ca_dl = topo.ca_host.store_for(topo.ca_actor_id)
    _seed_case(owner_dl, topo, case_id)
    _seed_case(ca_dl, topo, case_id)
    return owner_dl, ca_dl, topo.invitee.store_for(topo.invitee_actor_id)


def _invite(topo: _Topology, case_id: str) -> dict:
    """POST ``invite-actor-to-case`` to the owner's *own* container."""
    resp = topo.owner.client.post(
        "/api/v2/actors/owner/trigger/invite-actor-to-case",
        json={"case_id": case_id, "invitee_id": topo.invitee_actor_id},
    )
    assert (
        resp.status_code == 202
    ), f"invite-actor-to-case failed ({resp.status_code}): {resp.text}"
    return resp.json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.spec("PCR-08-007")
class TestInviteWithARemoteCaseActor:
    """The emit resolves a CaseActor this node does not host."""

    def test_the_invite_is_emitted_as_the_remote_case_actor(self, topology):
        """PCR-08-007 holds regardless of which container answers the trigger.

        This is the premise the rest of the module rests on: posting to the
        owner's own container is *not* a way of emitting as the owner.  The use
        case resolves the case's CaseActor and emits as it, so a scenario that
        posts to the CaseActor's container in order to "emit as the CaseActor"
        buys nothing and addresses an actor that container may not host.
        """
        case_id = "urn:uuid:remote-ca-emitting-identity"
        _bootstrap(topology, case_id)

        result = _invite(topology, case_id)

        assert result.get("emitting_actor_id") == topology.ca_actor_id, (
            "the Invite must be emitted from the case's CaseActor identity"
            f" even though the trigger arrived on {topology.owner.base_url}"
        )

    def test_the_invitee_receives_the_invite(self, topology):
        """Delivery must survive the cross-container emit.

        The outbox drained by ``trigger_invite_actor_to_case`` is the *emitting*
        actor's, and the emitting actor is remote — so this asserts that
        whichever store was chosen, the activity and its queue entry ended up in
        the same one (ISSUE-2548) and delivery went out.
        """
        case_id = "urn:uuid:remote-ca-delivery"
        _, _, invitee_dl = _bootstrap(topology, case_id)

        _invite(topology, case_id)

        invites = invitee_dl.list_objects("Invite")
        assert len(invites) == 1, (
            "the invitee's store must hold exactly one Invite after the owner's"
            " trigger; a cross-container emit that lands the activity and the"
            " outbox entry in different stores delivers nothing and says so"
            " only at debug level"
        )
        assert getattr(invites[0], "actor", None) == topology.ca_actor_id

    def test_the_emitted_invite_carries_the_case_not_a_bare_id(self, topology):
        """CM-17-002: the emit must read a store that actually holds the case.

        ``EmitInviteActorToCaseNode._emit`` reads the case from the store the BT
        runs in and passes ``target=None`` when that read fails; the adapter
        then re-reads from the same store and falls back to the bare ``case_id``
        string.  A store minted for a foreign actor is empty, so a remote
        CaseActor produces exactly that unless the emit stays in a store that
        holds the case (AKM-03-001).

        The embargo terms are the observable difference, and that is why
        ``_seed_case`` puts the case at ``EM.ACTIVE`` with an ``active_embargo``
        rather than leaving it bare.  ``_project_case_to_stub`` enriches the
        stub only under exactly that condition, so an ``activeEmbargo`` on the
        emitted target means the case *and* its ``EmbargoEvent`` were both read
        out of a store that really holds them — which an empty phantom store
        cannot fake.

        Asserted on the **emitting** side, against the requester's own record of
        what it sent, because that is the boundary this issue governs.  The
        invitee's copy is not a usable probe for it: the enrichment does not
        currently survive the wire hop at all, for reasons that have nothing to
        do with which store the emit ran in (#2624 — the outbox's stub allowlist
        collapses any stub richer than ``{id, type, summary}``).  Checking the
        invitee here would fail on that unrelated defect and say "wrong store"
        while meaning "the outbox flattened the stub".
        """
        case_id = "urn:uuid:remote-ca-target-enrichment"
        owner_dl, _, _ = _bootstrap(topology, case_id)

        _invite(topology, case_id)

        invites = owner_dl.list_objects("Invite")
        assert len(invites) == 1
        target = getattr(invites[0], "target", None)
        assert not isinstance(target, str), (
            "the Invite's target degraded to a bare case id, so the emit read a"
            f" store with no case in it. target={target!r}"
        )
        assert getattr(target, "active_embargo", None) is not None, (
            "the target is inline but carries no embargo terms, so the invitee"
            " could not give informed consent (CM-17-002); the case was read but"
            f" its EmbargoEvent was not. target={target!r}"
        )

    def test_no_store_is_minted_for_the_remote_case_actor(self, topology):
        """A write into a foreign authority's store reaches nobody.

        ``clone_for_actor`` succeeds for any well-formed id, so the failure is
        silent: the ledger entry, the activity and the outbox entry all land in
        a store on the *owner's* node named after an actor the *CaseActor's*
        node hosts.  Nothing ever reads it.
        """
        case_id = "urn:uuid:remote-ca-phantom-store"
        _bootstrap(topology, case_id)

        _invite(topology, case_id)

        phantom = topology.owner.store_for(topology.ca_actor_id)
        assert phantom.get_all("CaseLedgerEntry") == [], (
            "the ledger entry for invite_actor_to_case was committed into a"
            f" store on {topology.owner.base_url} named for an actor hosted on"
            f" {topology.ca_host.base_url}; the CaseActor's real ledger never"
            " sees it (ADR-0021)"
        )
        assert (
            phantom.get_all("Invite") == []
        ), "the Invite activity itself was persisted into the phantom store"

    def test_the_owners_own_store_records_the_invite(self, topology):
        """The owner must be able to account for an Invite it caused.

        With the emit kept in a store the node actually hosts, the ledger
        correlation marker is readable by the actor that asked for the invite.
        The canonical entry remains the CaseActor's, arriving via the ``cc:``
        self-delivery (CLP-10-001).
        """
        case_id = "urn:uuid:remote-ca-owner-ledger"
        owner_dl, _, _ = _bootstrap(topology, case_id)

        _invite(topology, case_id)

        events = [
            str(getattr(entry, "event_type", ""))
            for entry in owner_dl.list_objects("CaseLedgerEntry")
        ]
        assert any("invite_actor_to_case" in e for e in events), (
            "the owner's own store holds no ledger entry for the invite it"
            f" emitted; entries seen: {events}"
        )

    def test_the_remote_case_actor_is_told_about_the_invite(self, topology):
        """CLP-10-001: ``cc:`` self-delivery is what reaches the real CaseActor.

        A node cannot write into another node's store, so the only way the
        canonical ledger learns of this invite is over the wire.  That makes the
        ``cc`` on the emitted Invite load-bearing rather than decorative.
        """
        case_id = "urn:uuid:remote-ca-cc-selfdelivery"
        _, ca_dl, _ = _bootstrap(topology, case_id)

        _invite(topology, case_id)

        assert ca_dl.list_objects("Invite"), (
            "the CaseActor's own store holds no Invite: the cc: copy never"
            " arrived, so nothing on that container knows the invite happened"
        )
