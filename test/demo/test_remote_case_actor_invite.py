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

A container emits only as actors it hosts (ADR-0109).  So the Case Owner's
``invite-actor-to-case`` trigger does not emit the Invite itself: it sends the
owner's own ``Offer(Actor, Case)`` with the requested roles to the case's
CASE_MANAGER, and the CASE_MANAGER's recommend-actor tree emits the Invite from
its own store and commits it there (CM-17-007, CM-17-006).  The Invite carries
no ``cc:`` copy, because the CASE_MANAGER does not mail itself.

This module runs that flow on three containers: the owner on one, the CaseActor
on a second, the invitee on a third.  The CaseActor is on a different container
from the owner, as a case handoff leaves it (CP-09-004).  Only that layout
shows what the flow must hold:

* the owner's ``202`` names the owner's Offer, emitted as the owner;
* the Invite is emitted as the CaseActor and committed in the CaseActor's own
  ledger, with the case stub's embargo terms (CM-17-002) and the offered roles,
  and with no ``cc``;
* the invitee receives the Invite;
* no store on the owner's container holds a ledger entry the owner minted for
  the Invite, and no store there is named for the remote CaseActor.

Each node in this harness has its *own* storage deployment, which is
essential: while every node shared one anonymous ``sqlite:///:memory:``, the
cross-authority slug collision that
:func:`~vultron.adapters.driven.datalayer_sqlite.engine.actor_slug` produces for
two ``.../actors/case-actor`` ids resolved to a single shared store, so a write
into the wrong container's store looked correct locally.  See
``test/demo/conftest.py::node_db_url``.

Issues: #2484, #3821
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from test.demo.conftest import (
    IsolatedActorApp,
    _TestClientRouter,
    create_isolated_actor_app,
)
from test.support.embargo_register import register
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.actor import CoreActor
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import EmDimension
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.protocols import PersistableModel
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import EmbargoConsentState
from vultron.core.use_cases._helpers import read_received_activity
from vultron.enums.roles import CVDRole

#: Characters that cannot appear in a hostname label.
_UNSAFE_IN_HOST = re.compile(r"[^a-z0-9-]+")


@dataclass(frozen=True)
class _Topology:
    """Three containers, as ``docker-compose-multi-actor.yml`` arranges them.

    After a case handoff the CaseActor is *not* on the container that owns the
    case (CP-09-004).  So ``ca_host`` and ``owner`` are separate nodes: the
    CaseActor's actor id is under ``ca_host``'s authority and holds the
    authoritative case, while ``owner`` holds a replica.

    Attributes:
        ca_host: The node hosting the case's CaseActor and the authoritative case.
        owner: The node hosting the Case Owner, which holds a case replica.
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

    The *slug* stays ``case-actor`` in every case, purely as a readable label —
    ADR-0088 gives the string no protocol meaning (CM-02-013).  What makes each
    node's authority genuinely distinct is the differing *authority* in its base
    URL, which is the cross-authority isolation this test exercises.

    Deliberately does *not* patch ``VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL``: the
    replica is seeded directly with a remote CASE_MANAGER, which is the state a
    handoff leaves behind, and the owner's trigger addresses its Offer to the
    roster's CASE_MANAGER rather than to configuration.

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


def _seed_case(
    dl,
    topo: _Topology,
    case_id: str,
    published: datetime | None = None,
) -> None:
    """Write a case replica whose CASE_MANAGER is the remote CaseActor.

    This is the post-handoff shape: the participant wearing
    ``CVDRole.CASE_MANAGER`` is attributed to a CaseActor on a container the
    owner's node does not host (CP-09-004).  The owner holds
    ``CVDRole.CASE_OWNER``, which is what makes the CASE_MANAGER treat the
    owner's Offer as a direct invite rather than a recommendation to forward
    (CM-17-007).

    The case is seeded **under an active embargo**, and that is load-bearing
    rather than incidental colour.  ``_project_case_to_stub`` enriches the
    Invite's ``target`` only when ``em_state == EM.ACTIVE`` and the case names
    an ``active_embargo`` (CM-17-002); with no embargo it returns a stub
    carrying nothing but an id, which AS2 serialises to a bare URI string —
    exactly what a *failed* case read produces.  Under an active embargo the two
    outcomes differ, so
    ``test_the_invite_carries_the_embargo_terms_and_the_roles`` can tell "read
    the case" from "read an empty store".

    *published* pins the VulnerabilityCase timestamp so all replicas share the
    same genesis hash regardless of wall-clock second boundaries.  When None a
    fresh timestamp is used — callers seeding multiple replicas MUST pass the
    same value to all calls or they risk divergent genesis hashes (#2727).
    """
    embargo = EmbargoEvent(
        id_=f"{case_id}/embargoes/e0",
        context=case_id,
        end_time=days_from_now_utc(45),
    )
    manager = CaseParticipant(
        id_=f"{case_id}/participants/case-actor",
        attributed_to=topo.ca_actor_id,
        case_roles=[CVDRole.COORDINATOR, CVDRole.CASE_MANAGER],
        embargo_consents=[
            EmbargoConsent(
                embargo_id=str(embargo.id_),
                state=EmbargoConsentState.ACCEPTED,
            )
        ],
    )
    # Party to the active embargo, so the owner is an active participant and
    # the CaseActor's ledger fan-out reaches it; otherwise the CM-10-005 gate
    # rightly withholds every ledger entry from it (CM-10-004).
    owner_participant = CaseParticipant(
        id_=f"{case_id}/participants/owner",
        attributed_to=topo.owner_actor_id,
        case_roles=[CVDRole.VENDOR, CVDRole.CASE_OWNER],
        embargo_consents=[
            EmbargoConsent(
                embargo_id=str(embargo.id_),
                state=EmbargoConsentState.ACCEPTED,
            )
        ],
    )
    case_kwargs: dict = dict(
        id_=case_id,
        name="remote CaseActor invite",
        stub_summary="Security issue — details shared after acceptance",
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
        embargo_register=register(active=str(embargo.id_)),
    )
    if published is not None:
        case_kwargs["published"] = published
    case = VulnerabilityCase(**case_kwargs)
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
        node a replica.
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

    # A single shared timestamp pins genesis_hash across both replicas.
    # Without this, each VulnerabilityCase() call uses _now_utc() independently;
    # if a wall-clock second ticks between the two _seed_case calls the two
    # replicas diverge, and CheckHashOrRejectOnMismatchNode fires when ca_host
    # fans out Announce(CaseLedgerEntry) to owner (#2727).
    case_published = datetime.now(UTC).replace(microsecond=0)

    owner_dl = topo.owner.store_for(topo.owner_actor_id)
    ca_dl = topo.ca_host.store_for(topo.ca_actor_id)
    _seed_case(owner_dl, topo, case_id, published=case_published)
    _seed_case(ca_dl, topo, case_id, published=case_published)
    return owner_dl, ca_dl, topo.invitee.store_for(topo.invitee_actor_id)


def _invite(topo: _Topology, case_id: str) -> dict:
    """POST ``invite-actor-to-case`` to the owner's *own* container."""
    resp = topo.owner.client.post(
        "/api/v2/actors/owner/trigger/invite-actor-to-case",
        json={
            "case_id": case_id,
            "invitee_id": topo.invitee_actor_id,
            "roles": _OFFERED_ROLES,
        },
    )
    assert resp.status_code == 202, (
        f"invite-actor-to-case failed ({resp.status_code}): {resp.text}"
    )
    body: dict = resp.json()
    return body


#: Roles the owner offers the invitee; not the CASE_MANAGER's VENDOR default
#: (CM-16-003), so their presence on the Invite shows they were carried.
_OFFERED_ROLES = ["coordinator", "deployer"]


def _case_actor_invite(topo: _Topology, ca_dl) -> PersistableModel:
    """The one Invite the CaseActor emitted as itself."""
    invites = [
        invite
        for invite in ca_dl.list_objects("Invite")
        if getattr(invite, "actor", None) == topo.ca_actor_id
    ]
    assert len(invites) == 1, (
        "the CaseActor's store must hold exactly one Invite emitted as the"
        f" CaseActor after the owner's trigger; found {invites!r}"
    )
    found: PersistableModel = invites[0]
    return found


def _ledger_entries(dl, case_id: str) -> list:
    return [
        entry
        for entry in dl.list_objects("CaseLedgerEntry")
        if getattr(entry, "case_id", None) == case_id
    ]


def _snapshot_id(entry) -> str | None:
    snapshot = getattr(entry, "payload_snapshot", None) or {}
    return snapshot.get("id") if isinstance(snapshot, dict) else None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBootstrapInvariant:
    """Bootstrap invariants that must hold before any scenario test runs.

    These guard the preconditions that every test in TestInviteWithARemoteCaseActor
    depends on.  A failure here is a test-infrastructure defect, not a protocol
    bug.  See issue #2727.
    """

    def test_genesis_hash_matches_across_replicas(self, topology):
        """Both case replicas must share the same genesis hash.

        ``_bootstrap`` seeds the same VulnerabilityCase on owner_dl and ca_dl.
        If the two VulnerabilityCase instances are constructed at different
        wall-clock seconds they receive different ``published`` timestamps,
        which feeds ``compute_genesis_hash`` and produces divergent hashes.
        When ca_host later fans out ``Announce(CaseLedgerEntry)`` with
        ``prev_log_hash`` derived from ca_host's genesis, owner's
        ``CheckHashOrRejectOnMismatchNode`` detects the mismatch and rejects
        the entry, so the owner's replica of the CaseActor's ledger diverges.

        The fix: ``_bootstrap`` passes a single shared ``published`` timestamp
        to both ``_seed_case`` calls so both replicas compute the same hash.
        """
        case_id = "urn:uuid:genesis-hash-invariant"
        owner_dl, ca_dl, _ = _bootstrap(topology, case_id)

        owner_case = owner_dl.read(case_id)
        ca_case = ca_dl.read(case_id)

        assert owner_case is not None, "case not seeded on owner"
        assert ca_case is not None, "case not seeded on ca_host"

        owner_genesis = getattr(owner_case, "genesis_hash", None)
        ca_genesis = getattr(ca_case, "genesis_hash", None)

        assert owner_genesis, "owner case has no genesis_hash"
        assert ca_genesis, "ca_host case has no genesis_hash"
        assert owner_genesis == ca_genesis, (
            "owner and ca_host case replicas have divergent genesis hashes:"
            f" owner={owner_genesis!r}, ca_host={ca_genesis!r}."
            " This causes CheckHashOrRejectOnMismatchNode to fire when"
            " ca_host fans out Announce(CaseLedgerEntry) to owner (#2727)."
        )


@pytest.mark.spec("CM-17-007", "CM-17-006", "PCR-08-007")
class TestOwnerInviteThroughARemoteCaseActor:
    """The owner asks; the CaseActor on another container invites (ADR-0109)."""

    def test_the_owners_trigger_sends_the_owners_own_offer(self, topology):
        """The owner's ``202`` means its Offer was queued, not an Invite sent.

        A container emits only as actors it hosts, so the trigger answered on
        the owner's container emits as the owner and addresses the CASE_MANAGER
        (CM-17-007).
        """
        case_id = "urn:uuid:remote-ca-owner-offer"
        _bootstrap(topology, case_id)

        result = _invite(topology, case_id)

        assert result.get("emitting_actor_id") == topology.owner_actor_id
        activity = result.get("activity") or {}
        assert activity.get("type") == "Offer"
        assert activity.get("actor") == topology.owner_actor_id
        assert activity.get("to") == [topology.ca_actor_id]
        assert "cc" not in activity

    def test_the_case_actor_emits_and_commits_the_invite(self, topology):
        """CM-17-006: the emitter commits the Invite in its own ledger."""
        case_id = "urn:uuid:remote-ca-emit-and-commit"
        _, ca_dl, _ = _bootstrap(topology, case_id)

        _invite(topology, case_id)

        invite = _case_actor_invite(topology, ca_dl)
        assert getattr(invite, "attributed_to", None) == (
            topology.owner_actor_id
        ), "the Invite must name the owner who asked for it"
        committed = [
            entry
            for entry in _ledger_entries(ca_dl, case_id)
            if _snapshot_id(entry) == invite.id_
        ]
        assert len(committed) == 1, (
            "the CaseActor's ledger must hold exactly one entry for the Invite"
            f" it emitted; found {committed!r}"
        )

    def test_the_invite_carries_the_embargo_terms_and_the_roles(
        self, topology
    ):
        """CM-17-002 and CM-16-018, on the wire form the invitee is sent.

        The sealed body is what the CaseActor's outbox delivers, so it is the
        boundary that decides what the invitee sees.  An ``activeEmbargo`` on
        the target means the CaseActor read the case *and* its EmbargoEvent out
        of a store that holds them.
        """
        case_id = "urn:uuid:remote-ca-target-enrichment"
        _, ca_dl, _ = _bootstrap(topology, case_id)

        _invite(topology, case_id)

        invite = _case_actor_invite(topology, ca_dl)
        wire = read_sealed_body_dict(ca_dl, str(invite.id_))
        assert wire is not None, "the CaseActor sealed no body for its Invite"
        target = wire.get("target")
        assert isinstance(target, dict), (
            "the Invite's target degraded to a bare case id, so the emit read a"
            f" store with no case in it. target={target!r}"
        )
        assert target.get("activeEmbargo"), (
            "the target carries no embargo terms, so the invitee could not give"
            f" informed consent (CM-17-002). target={target!r}"
        )
        assert wire.get("roles") == _OFFERED_ROLES
        assert "cc" not in wire, (
            "the CaseActor mailed itself a cc: copy of its own Invite (ADR-0109)"
        )

    def test_the_invitee_receives_the_invite(self, topology):
        """The CaseActor's Invite reaches the invitee's container.

        The invitee holds no case yet, so its inbox defers the Invite until the
        bootstrap its Accept brings; ``read_received_activity`` reads the Invite
        however the invitee holds it.
        """
        case_id = "urn:uuid:remote-ca-delivery"
        _, ca_dl, invitee_dl = _bootstrap(topology, case_id)

        _invite(topology, case_id)

        invite = _case_actor_invite(topology, ca_dl)
        received = read_received_activity(
            invitee_dl, str(invite.id_), "Invite"
        )
        assert getattr(received, "actor", None) == topology.ca_actor_id

    def test_the_owner_mints_no_ledger_entry_for_the_invite(self, topology):
        """The owner is not the Invite's emitter, so it commits nothing.

        Every ledger entry the owner's store holds for the case must be a copy
        of one the CaseActor committed: the owner neither commits its Offer nor
        writes a correlation marker for an Invite it did not send.
        """
        case_id = "urn:uuid:remote-ca-owner-ledger"
        owner_dl, ca_dl, _ = _bootstrap(topology, case_id)

        _invite(topology, case_id)

        canonical = {
            entry.entry_hash for entry in _ledger_entries(ca_dl, case_id)
        }
        self_minted = [
            entry
            for entry in _ledger_entries(owner_dl, case_id)
            if entry.entry_hash not in canonical
        ]
        assert self_minted == [], (
            "the owner's store holds ledger entries the CaseActor never"
            f" committed: {[_snapshot_id(e) for e in self_minted]!r}"
        )

    def test_no_store_is_minted_for_the_remote_case_actor(self, topology):
        """A write into a foreign authority's store reaches nobody.

        ``clone_for_actor`` succeeds for any well-formed id, so writing as the
        remote CaseActor from the owner's container would fail silently: the
        activity and its ledger entry would land in a store nothing reads.
        """
        case_id = "urn:uuid:remote-ca-phantom-store"
        _bootstrap(topology, case_id)

        _invite(topology, case_id)

        phantom = topology.owner.store_for(topology.ca_actor_id)
        assert phantom.get_all("CaseLedgerEntry") == []
        assert phantom.get_all("Invite") == []
