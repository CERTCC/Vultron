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

"""
Unit tests for actor-level trigger use cases.
Covers SvcInviteActorToCaseUseCase, SvcSuggestActorToCaseUseCase,
SvcAcceptCaseInviteUseCase, SvcRejectCaseInviteUseCase,
and SvcAcceptActorRecommendationUseCase.
Includes DR-09 regression tests verifying that short UUIDs in actor_id
are normalised to full URIs before use.
"""

import json
import logging
from datetime import UTC
from typing import Any, cast

import pytest
from pydantic import ValidationError

from test.support.received import archive_received
from test.support.trigger_results import activity_of
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.adapters.outbox_sealed_body import read_sealed_body
from vultron.core.models.use_case_result import RoleOfferResult
from vultron.core.use_cases.triggers.actor import (
    SvcAcceptActorRecommendationUseCase,
    SvcAcceptCaseInviteUseCase,
    SvcInviteActorToCaseUseCase,
    SvcOfferCaseParticipantRoleUseCase,
    SvcRejectCaseInviteUseCase,
    SvcSuggestActorToCaseUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptActorRecommendationTriggerRequest,
    AcceptCaseInviteTriggerRequest,
    InviteActorToCaseTriggerRequest,
    OfferCaseParticipantRoleTriggerRequest,
    RejectCaseInviteTriggerRequest,
    SuggestActorToCaseTriggerRequest,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronNotFoundError, VultronValidationError
from vultron.wire.as2.factories import rm_invite_to_case_activity
from vultron.wire.as2.factories.actor import offer_case_participant_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Invite
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_BASE = "http://coordinator:7999/api/v2/actors"
_UUID = "24d63c7d-6b1e-4f61-a5e1-180d27192d0b"
_HTTP_ACTOR_ID = f"{_BASE}/{_UUID}"
_CREATED_DLS: list[SqliteDataLayer] = []
_CASE_MANAGER_ID = "https://example.org/actors/case-manager"


def _make_actor_dl(actor_name: str):
    """Create an as_Service actor and a per-actor SqliteDataLayer."""
    actor = as_Service(name=actor_name)
    actor_id = actor.id_
    reset_datalayer(actor_id)
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
    dl.clear_all()
    dl.create(actor)
    _CREATED_DLS.append(dl)
    return actor, dl


def _make_actor_dl_with_http_id(actor_name: str, actor_id: str):
    """Create an actor with an explicit HTTP-style ID (for short-UUID tests)."""
    actor = as_Service(name=actor_name, id_=actor_id)
    reset_datalayer(actor_id)
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
    dl.clear_all()
    dl.create(actor)
    _CREATED_DLS.append(dl)
    return actor, dl


@pytest.fixture(autouse=True)
def _cleanup_created_dls():
    """Close any helper-created DataLayers to avoid unraisable sqlite warnings."""
    yield
    while _CREATED_DLS:
        _CREATED_DLS.pop().close()


def _make_case_with_case_manager(
    dl: SqliteDataLayer, owner_actor_id: str, case_actor_id: str
) -> as_VulnerabilityCase:
    case = as_VulnerabilityCase(
        attributed_to=owner_actor_id,
        name="Test Case",
        content="Content",
        stub_summary="Security issue — details shared after acceptance",
    )
    owner_participant = as_CaseParticipant(
        attributed_to=owner_actor_id,
        context=case.id_,
        case_roles=[CVDRole.CASE_OWNER],
    )
    case_manager_participant = as_CaseParticipant(
        attributed_to=case_actor_id,
        context=case.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    case.actor_participant_index[owner_actor_id] = owner_participant.id_
    case.actor_participant_index[case_actor_id] = case_manager_participant.id_
    case.case_participants.append(owner_participant.id_)
    case.case_participants.append(case_manager_participant.id_)
    dl.create(case)
    dl.create(owner_participant)
    dl.create(case_manager_participant)
    return case


def _shared_case_with_case_manager(
    owner_actor_id: str, case_actor_id: str, *dls: SqliteDataLayer
) -> as_VulnerabilityCase:
    """One case, with the same CASE_OWNER/CASE_MANAGER roster, in every store.

    The owner and the CASE_MANAGER are distinct actors with their own stores
    (ADR-0073); each holds its replica of the same case.
    """
    case = as_VulnerabilityCase(
        attributed_to=owner_actor_id,
        name="Test Case",
        content="Content",
        stub_summary="Security issue — details shared after acceptance",
    )
    owner_participant = as_CaseParticipant(
        attributed_to=owner_actor_id,
        context=case.id_,
        case_roles=[CVDRole.CASE_OWNER],
    )
    case_manager_participant = as_CaseParticipant(
        attributed_to=case_actor_id,
        context=case.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    case.actor_participant_index[owner_actor_id] = owner_participant.id_
    case.actor_participant_index[case_actor_id] = case_manager_participant.id_
    case.case_participants.append(owner_participant.id_)
    case.case_participants.append(case_manager_participant.id_)
    for dl in dls:
        dl.create(case)
        dl.create(owner_participant)
        dl.create(case_manager_participant)
    return case


def _activate_embargo(dl: SqliteDataLayer, case_id: str) -> str:
    """Give *case_id* an ACTIVE embargo in *dl*; return the embargo id."""
    from datetime import datetime

    from vultron.core.states.em import EM
    from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

    embargo = as_EmbargoEvent(
        id_=f"{case_id}/embargo/e1",
        content="Active embargo",
        end_time=datetime(2030, 1, 1, tzinfo=UTC),
        context=case_id,
    )
    dl.create(embargo)
    case = cast(Any, dl.read(case_id))
    object.__setattr__(case, "active_embargo", embargo.id_)
    case.append_case_status(em_state=EM.ACTIVE)
    dl.save(case)
    return embargo.id_


class _OwnerDirectInvite:
    """The owner's trigger, then the CASE_MANAGER's receipt of its Offer.

    Under ADR-0109 the owner's container never emits as the CASE_MANAGER: the
    owner sends its own ``Offer(Actor, Case)`` and the CASE_MANAGER's
    recommend-actor received tree emits the ``Invite`` (CM-17-007).  This
    harness runs both halves against two stores so a test can inspect either.
    """

    def __init__(self, with_active_embargo: bool = False) -> None:
        self.owner, self.owner_dl = _make_actor_dl("CaseOwner")
        self.manager, self.manager_dl = _make_actor_dl("CaseManager")
        self.invitee, _ = _make_actor_dl("Invitee")
        self.owner_dl.create(self.invitee)
        self.owner_dl.create(self.manager)
        self.manager_dl.create(self.owner)
        self.case = _shared_case_with_case_manager(
            self.owner.id_, self.manager.id_, self.owner_dl, self.manager_dl
        )
        if with_active_embargo:
            _activate_embargo(self.manager_dl, self.case.id_)

    def trigger(self, roles: list[CVDRole] | None = None) -> dict[str, Any]:
        """Run the owner's trigger; return the activity it captured."""
        request = InviteActorToCaseTriggerRequest(
            actor_id=self.owner.id_,
            case_id=self.case.id_,
            invitee_id=self.invitee.id_,
            roles=roles,
        )
        result = SvcInviteActorToCaseUseCase(
            self.owner_dl,
            request,
            trigger_activity=TriggerActivityAdapter(self.owner_dl),
            sync_port=SyncActivityAdapter(self.owner_dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()
        return activity_of(result)

    def deliver_to_manager(self, offer_id: str, make_payload) -> Any:
        """Process the owner's Offer on the CASE_MANAGER's inbox."""
        from vultron.core.use_cases.received.actor.suggest import (
            OfferActorToCaseReceivedUseCase,
        )

        offer = self.owner_dl.read(offer_id)
        assert offer is not None
        event = make_payload(offer, receiving_actor_id=self.manager.id_)
        return OfferActorToCaseReceivedUseCase(
            self.manager_dl,
            event,
            trigger_activity=TriggerActivityAdapter(self.manager_dl),
            sync_port=SyncActivityAdapter(self.manager_dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

    def manager_invite(self) -> Any:
        """The single Invite the CASE_MANAGER queued."""
        queued = [
            self.manager_dl.read(item)
            for item in self.manager_dl.outbox_list()
        ]
        invites = [q for q in queued if isinstance(q, as_Invite)]
        assert len(invites) == 1, f"expected one Invite, got {queued!r}"
        return invites[0]

    def invite(
        self, make_payload, roles: list[CVDRole] | None = None
    ) -> tuple[Any, dict[str, Any]]:
        """Both halves; return the CASE_MANAGER's Invite and its wire form."""
        offer = self.trigger(roles)
        result = self.deliver_to_manager(offer["id"], make_payload)
        assert result.disposition.value == "applied", result
        invite = self.manager_invite()
        # The body the outbox relays is the sealed one (OX-07-001), so that is
        # the wire form a recipient sees.
        sealed = read_sealed_body(self.manager_dl, invite.id_)
        assert sealed is not None, "the CASE_MANAGER's Invite was not sealed"
        return invite, json.loads(sealed.body)


class TestSvcInviteActorToCaseUseCase:
    """The owner-direct invite trigger (CM-17-007, CM-24-004, ADR-0109)."""

    @pytest.mark.spec("CM-17-007")
    def test_invite_sends_the_owners_own_offer_to_the_case_manager(self):
        """The owner's activity is an Offer from the owner, to the CASE_MANAGER."""
        harness = _OwnerDirectInvite()

        activity = harness.trigger(roles=[CVDRole.VENDOR])

        assert activity["type"] == "Offer"
        assert activity["actor"] == harness.owner.id_
        assert activity.get("to") == [harness.manager.id_]
        assert activity.get("suggestedRoles") == ["vendor"]
        obj = activity["object"]
        assert (obj["id"] if isinstance(obj, dict) else obj) == (
            harness.invitee.id_
        )
        assert "cc" not in activity

    @pytest.mark.spec("CM-24-004")
    def test_invite_is_queued_in_the_owners_outbox_only(self):
        """The Offer leaves from the owner's outbox; nothing is queued as the
        CASE_MANAGER and nothing is committed by the owner."""
        harness = _OwnerDirectInvite()

        activity = harness.trigger()

        assert activity["id"] in harness.owner_dl.outbox_list()
        stored = harness.owner_dl.read(activity["id"])
        assert stored is not None and not isinstance(stored, as_Invite)
        assert harness.manager_dl.outbox_list() == []
        assert (
            harness.owner_dl.clone_for_actor(harness.manager.id_).outbox_list()
            == []
        )
        assert harness.owner_dl.list_objects("CaseLedgerEntry") == []

    @pytest.mark.spec("CM-24-004")
    def test_invite_uses_no_delegated_context(self, monkeypatch):
        """The trigger never resolves a delegated CASE_MANAGER identity."""
        import vultron.core.use_cases._helpers as use_case_helpers
        import vultron.core.use_cases.triggers.actor as actor_triggers

        def _forbidden(*_args, **_kwargs):
            raise AssertionError("the owner must not emit as the CASE_MANAGER")

        monkeypatch.setattr(actor_triggers, "delegated_authorship", _forbidden)
        monkeypatch.setattr(
            use_case_helpers, "_find_case_actor_id", _forbidden
        )
        harness = _OwnerDirectInvite()

        activity = harness.trigger()

        assert activity["actor"] == harness.owner.id_

    def test_invite_raises_when_no_case_manager(self):
        actor, dl = _make_actor_dl("Coordinator")
        invitee, _ = _make_actor_dl("Finder")
        dl.create(invitee)
        case = as_VulnerabilityCase(
            attributed_to=actor.id_, name="Test Case", content="Content"
        )
        dl.create(case)
        request = InviteActorToCaseTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            invitee_id=invitee.id_,
        )
        with pytest.raises(VultronValidationError):
            SvcInviteActorToCaseUseCase(
                dl,
                request,
                trigger_activity=TriggerActivityAdapter(dl),
                sync_port=SyncActivityAdapter(dl),
                wire_render_port=As2WireRenderAdapter(),
            ).execute()
        assert dl.outbox_list() == []

    @pytest.mark.spec("AKM-05-001")
    def test_invite_proceeds_when_invitee_not_in_dl(self, caplog):
        """An invitee is named by URI; a local record is not required.

        This asserted a 404 before. Holding a local record was never a protocol
        requirement — delivery derives the invitee's inbox from its URI alone,
        and under per-actor storage a peer's record lives in *its* store, not
        the inviter's (ADR-0073#peer-records-in-knowers-store).

        With the injectable ActorDiscoveryCallOutBundle seam (ADR-0025), the
        default DETERMINISTIC backend (AlwaysSucceed) logs at DEBUG rather than
        WARNING — the seam is wired, no gap to report (AKM-05-002).
        """
        actor, dl = _make_actor_dl("Coordinator")
        missing_id = "https://example.org/actors/nobody"
        case = _make_case_with_case_manager(dl, actor.id_, _CASE_MANAGER_ID)

        request = InviteActorToCaseTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            invitee_id=missing_id,
        )
        with caplog.at_level(logging.WARNING):
            result = SvcInviteActorToCaseUseCase(
                dl,
                request,
                trigger_activity=TriggerActivityAdapter(dl),
                sync_port=SyncActivityAdapter(dl),
                wire_render_port=As2WireRenderAdapter(),
            ).execute()

        assert activity_of(result)["type"] == "Offer"
        assert "actor discovery returned" not in caplog.text

    @pytest.mark.parametrize(
        ("bad_id", "refused_by_model"),
        [
            ("nobody", True),  # bare name, no scheme
            ("/actors/nobody", True),  # relative path
            ("https:///actors/nobody", False),  # scheme but no netloc
            ("ftp://example.org/actors/nobody", False),  # non-HTTP scheme
        ],
    )
    def test_invite_rejects_undeliverable_invitee_uri(
        self, bad_id, refused_by_model
    ):
        """An unknown invitee is minted, but only from a deliverable URI.

        Absence is not grounds for refusal (see the test above), which leaves
        the id itself as the only thing that can be checked. It has to be an
        absolute http(s) URI because it *is* the address the invitation is
        POSTed to: a typo'd or relative id would otherwise become a case
        participant that no delivery attempt can ever reach, failing far away
        in the retry loop instead of here.

        Two layers refuse: an id that is not a URI at all never builds a
        request, because the request derives from the ``UriString``-typed body
        model (validate at the edge, ADR-0032); a URI-shaped id that is not
        deliverable is refused by the use case.
        """
        actor, dl = _make_actor_dl("Coordinator")
        case = as_VulnerabilityCase(
            attributed_to=actor.id_, name="Test Case", content="Content"
        )
        dl.create(case)

        if refused_by_model:
            with pytest.raises(ValidationError, match="must be a URI"):
                InviteActorToCaseTriggerRequest(
                    actor_id=actor.id_,
                    case_id=case.id_,
                    invitee_id=bad_id,
                )
        else:
            request = InviteActorToCaseTriggerRequest(
                actor_id=actor.id_,
                case_id=case.id_,
                invitee_id=bad_id,
            )
            with pytest.raises(
                VultronValidationError, match="deliverable actor URI"
            ):
                SvcInviteActorToCaseUseCase(
                    dl,
                    request,
                    trigger_activity=TriggerActivityAdapter(dl),
                    sync_port=SyncActivityAdapter(dl),
                    wire_render_port=As2WireRenderAdapter(),
                ).execute()

        assert dl.read(bad_id) is None, (
            "a rejected invitee must not be recorded as a known actor"
        )

    def test_invite_raises_when_case_not_in_dl(self):
        actor, dl = _make_actor_dl("Coordinator")
        invitee, _ = _make_actor_dl("Finder")
        dl.create(invitee)
        # case NOT seeded

        missing_case_id = "https://example.org/cases/nope"
        request = InviteActorToCaseTriggerRequest(
            actor_id=actor.id_,
            case_id=missing_case_id,
            invitee_id=invitee.id_,
        )
        with pytest.raises(Exception):  # noqa: B017  # ruff-baseline #3353
            SvcInviteActorToCaseUseCase(
                dl,
                request,
                trigger_activity=TriggerActivityAdapter(dl),
                sync_port=SyncActivityAdapter(dl),
                wire_render_port=As2WireRenderAdapter(),
            ).execute()

    def test_invite_normalises_short_uuid_actor_id(self):
        """DR-09: short UUID in actor_id is resolved to full URI."""
        _actor, dl = _make_actor_dl_with_http_id("Coordinator", _HTTP_ACTOR_ID)
        invitee, _ = _make_actor_dl("Finder")
        dl.create(invitee)
        case = _make_case_with_case_manager(
            dl, _HTTP_ACTOR_ID, _CASE_MANAGER_ID
        )

        # Pass the bare UUID (as the FastAPI router does from the URL path)
        request = InviteActorToCaseTriggerRequest(
            actor_id=_UUID,
            case_id=case.id_,
            invitee_id=invitee.id_,
        )
        result = SvcInviteActorToCaseUseCase(
            dl,
            request,
            trigger_activity=TriggerActivityAdapter(dl),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        # Activity actor field must be the full canonical URI, not the short UUID
        assert activity_of(result)["actor"] == _HTTP_ACTOR_ID


class TestInviteRolesAndEmbargoEnrichment:
    """Roles and embargo enrichment on the CASE_MANAGER's Invite (CM-17-002/003).

    The owner's Offer carries the roles; the CASE_MANAGER's Invite carries them
    on, and enriches its case stub from the CASE_MANAGER's own replica.
    """

    def setup_method(self):
        import py_trees

        py_trees.blackboard.Blackboard.enable_activity_stream()

    def teardown_method(self):
        import py_trees

        py_trees.blackboard.Blackboard.clear()
        py_trees.blackboard.Blackboard.disable_activity_stream()

    def test_roles_field_accepted_in_request(self):
        """InviteActorToCaseTriggerRequest accepts an optional roles field."""
        request = InviteActorToCaseTriggerRequest(
            actor_id="https://example.org/actors/owner",
            case_id="https://example.org/cases/c1",
            invitee_id="https://example.org/actors/invitee",
            roles=[CVDRole.VENDOR],
        )
        assert request.roles == [CVDRole.VENDOR]

    @pytest.mark.spec("CM-17-003")
    def test_roles_carried_to_the_case_managers_invite(self, make_payload):
        harness = _OwnerDirectInvite()

        invite, wire = harness.invite(make_payload, roles=[CVDRole.VENDOR])

        assert invite.roles == ["vendor"]
        assert wire["roles"] == ["vendor"]

    @pytest.mark.spec("CM-16-003")
    def test_no_roles_requested_gives_the_default_vendor_role(
        self, make_payload
    ):
        """With no roles named, the CASE_MANAGER assigns the default role."""
        harness = _OwnerDirectInvite()

        _invite, wire = harness.invite(make_payload)

        assert wire["roles"] == ["vendor"]

    @pytest.mark.spec("CM-17-007")
    def test_invite_is_the_case_managers_attributed_to_the_owner(
        self, make_payload
    ):
        harness = _OwnerDirectInvite()

        _invite, wire = harness.invite(make_payload)

        assert wire["actor"] == harness.manager.id_
        assert wire.get("attributedTo") == harness.owner.id_
        assert wire.get("to") == [harness.invitee.id_]
        assert "cc" not in wire

    @pytest.mark.spec("CM-17-002")
    def test_active_embargo_enriches_case_stub(self, make_payload):
        """The Invite stub carries activeEmbargo.endTime and emState=ACTIVE."""
        harness = _OwnerDirectInvite(with_active_embargo=True)

        _invite, wire = harness.invite(make_payload)

        target = wire.get("target", {})
        active_embargo = target.get("activeEmbargo")
        assert isinstance(active_embargo, dict), (
            "activeEmbargo must be a full embargo object (CM-17-002)"
        )
        assert "endTime" in active_embargo
        assert target.get("caseStatus", {}).get("emState") in (
            "active",
            "ACTIVE",
        )

    @pytest.mark.spec("CM-17-002")
    def test_no_embargo_fields_when_not_active(self, make_payload):
        harness = _OwnerDirectInvite()

        _invite, wire = harness.invite(make_payload)

        target = wire.get("target", {})
        assert target.get("activeEmbargo") is None
        assert target.get("caseStatus") is None


class TestRolesThreadingIntegration:
    """The full roles-threading round trip (CM-17-003/004, Issue-1405).

    The owner's request roles → the owner's Offer → the CASE_MANAGER's Invite →
    Accept(Invite) on the CASE_MANAGER → CaseParticipant.case_roles.
    """

    def setup_method(self):
        import py_trees

        py_trees.blackboard.Blackboard.enable_activity_stream()

    def teardown_method(self):
        import py_trees

        py_trees.blackboard.Blackboard.clear()
        py_trees.blackboard.Blackboard.disable_activity_stream()

    def _run_round_trip(self, roles, make_payload):
        """Run the owner-direct invite, then Accept(Invite); return the
        CaseParticipant the CASE_MANAGER created."""
        from unittest.mock import MagicMock

        from vultron.core.use_cases.received.actor.invite import (
            AcceptInviteActorToCaseReceivedUseCase,
        )
        from vultron.wire.as2.factories import (
            rm_accept_invite_to_case_activity,
        )

        harness = _OwnerDirectInvite()
        invite, _wire = harness.invite(make_payload, roles=roles)

        accept = rm_accept_invite_to_case_activity(
            invite, actor=harness.invitee.id_
        )
        event = make_payload(accept, receiving_actor_id=harness.manager.id_)
        AcceptInviteActorToCaseReceivedUseCase(
            harness.manager_dl,
            event,
            sync_port=MagicMock(),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        updated_case = cast(Any, harness.manager_dl.read(harness.case.id_))
        participant_id = updated_case.actor_participant_index.get(
            harness.invitee.id_
        )
        assert participant_id is not None, (
            "invitee must be registered after Accept"
        )
        participant = cast(Any, harness.manager_dl.read(participant_id))
        assert participant is not None
        return participant

    @pytest.mark.spec("CM-17-004")
    def test_roles_vendor_reaches_participant_case_roles(self, make_payload):
        participant = self._run_round_trip(
            roles=[CVDRole.VENDOR], make_payload=make_payload
        )
        assert CVDRole.VENDOR in participant.case_roles

    @pytest.mark.spec("CM-16-003")
    def test_no_roles_gives_the_default_vendor_role(self, make_payload):
        participant = self._run_round_trip(
            roles=None, make_payload=make_payload
        )
        assert participant.case_roles == [CVDRole.VENDOR]


class TestSvcSuggestActorToCaseUseCase:
    """Tests for the suggest-actor-to-case trigger use case."""

    def test_suggest_creates_activity(self):
        actor, dl = _make_actor_dl("Coordinator")
        case_actor, _ = _make_actor_dl("Case Actor")
        suggested, _ = _make_actor_dl("Vendor")
        dl.create(case_actor)
        dl.create(suggested)
        case = _make_case_with_case_manager(dl, actor.id_, case_actor.id_)

        request = SuggestActorToCaseTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            suggested_actor_id=suggested.id_,
        )
        result = SvcSuggestActorToCaseUseCase(
            dl,
            request,
            trigger_activity=TriggerActivityAdapter(dl),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert result.activity is not None
        assert activity_of(result)["actor"] == actor.id_
        assert activity_of(result).get("to") == [case_actor.id_]

    def test_suggest_proceeds_when_suggested_actor_missing(self, caplog):
        """A recommended actor is named by URI; a local record is not required.

        This asserted a 404 before, for the same reason the invite path did, and
        it was wrong for the same reason: the whole point of a recommendation is
        to name an actor the case does not have yet, and under per-actor storage
        that actor's record lives in *its* store (ADR-0073#peer-records-in-knowers-store). The old
        behaviour refused every genuinely remote candidate — in the fcvcv demo,
        ``suggest-actor-to-case`` answered ``404 Actor '…/vendor-deployer' not
        found`` for a vendor that was running and reachable in another container
        (#2548).

        With the injectable ActorDiscoveryCallOutBundle seam (ADR-0025), the
        default DETERMINISTIC backend (AlwaysSucceed) logs at DEBUG, not WARNING.
        """
        actor, dl = _make_actor_dl("Coordinator")
        case_actor, _ = _make_actor_dl("Case Actor")
        dl.create(case_actor)
        case = _make_case_with_case_manager(dl, actor.id_, case_actor.id_)

        missing_id = "https://example.org/actors/ghost"
        request = SuggestActorToCaseTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            suggested_actor_id=missing_id,
        )
        with caplog.at_level(logging.WARNING):
            result = SvcSuggestActorToCaseUseCase(
                dl,
                request,
                trigger_activity=TriggerActivityAdapter(dl),
                sync_port=SyncActivityAdapter(dl),
                wire_render_port=As2WireRenderAdapter(),
            ).execute()

        assert result is not None
        # No WARNING with the default DETERMINISTIC bundle (AlwaysSucceed)
        assert "actor discovery returned" not in caplog.text

    @pytest.mark.parametrize(
        ("bad_id", "refused_by_model"),
        [
            ("ghost", True),
            ("/actors/ghost", True),
            ("https:///actors/ghost", False),
        ],
    )
    def test_suggest_rejects_undeliverable_actor_uri(
        self, bad_id, refused_by_model
    ):
        """The id is the address the eventual invitation is POSTed to.

        A non-URI id is refused by the ``UriString``-typed body model the
        request derives from (ADR-0032); a URI-shaped but undeliverable one by
        the use case.
        """
        actor, dl = _make_actor_dl("Coordinator")
        case_actor, _ = _make_actor_dl("Case Actor")
        dl.create(case_actor)
        case = _make_case_with_case_manager(dl, actor.id_, case_actor.id_)

        if refused_by_model:
            with pytest.raises(ValidationError, match="must be a URI"):
                SuggestActorToCaseTriggerRequest(
                    actor_id=actor.id_,
                    case_id=case.id_,
                    suggested_actor_id=bad_id,
                )
        else:
            request = SuggestActorToCaseTriggerRequest(
                actor_id=actor.id_,
                case_id=case.id_,
                suggested_actor_id=bad_id,
            )
            with pytest.raises(
                VultronValidationError, match="deliverable actor URI"
            ):
                SvcSuggestActorToCaseUseCase(
                    dl,
                    request,
                    trigger_activity=TriggerActivityAdapter(dl),
                    sync_port=SyncActivityAdapter(dl),
                    wire_render_port=As2WireRenderAdapter(),
                ).execute()

        assert dl.read(bad_id) is None, (
            "a rejected candidate must not be recorded as a known actor"
        )

    def test_suggest_normalises_short_uuid_actor_id(self):
        """DR-09: short UUID in actor_id is resolved to full URI."""
        _actor, dl = _make_actor_dl_with_http_id("Coordinator", _HTTP_ACTOR_ID)
        case_actor, _ = _make_actor_dl("Case Actor")
        suggested, _ = _make_actor_dl("Vendor")
        dl.create(case_actor)
        dl.create(suggested)
        case = _make_case_with_case_manager(
            dl, owner_actor_id=_HTTP_ACTOR_ID, case_actor_id=case_actor.id_
        )

        request = SuggestActorToCaseTriggerRequest(
            actor_id=_UUID,
            case_id=case.id_,
            suggested_actor_id=suggested.id_,
        )
        result = SvcSuggestActorToCaseUseCase(
            dl,
            request,
            trigger_activity=TriggerActivityAdapter(dl),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert activity_of(result)["actor"] == _HTTP_ACTOR_ID
        assert activity_of(result).get("to") == [case_actor.id_]

    def test_suggest_raises_when_no_case_manager(self):
        actor, dl = _make_actor_dl("Coordinator")
        suggested, _ = _make_actor_dl("Vendor")
        dl.create(suggested)
        case = as_VulnerabilityCase(
            attributed_to=actor.id_, name="Test Case", content="Content"
        )
        dl.create(case)
        request = SuggestActorToCaseTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            suggested_actor_id=suggested.id_,
        )
        with pytest.raises(VultronValidationError):
            SvcSuggestActorToCaseUseCase(
                dl,
                request,
                trigger_activity=TriggerActivityAdapter(dl),
                sync_port=SyncActivityAdapter(dl),
                wire_render_port=As2WireRenderAdapter(),
            ).execute()


class TestSvcAcceptCaseInviteUseCase:
    """Tests for the accept-case-invite trigger use case."""

    @pytest.mark.parametrize(
        "hold",
        [
            pytest.param(archive_received, id="archived-by-intake"),
            pytest.param(
                lambda dl, invite: dl.create(invite),
                id="held-by-the-inbox-until-the-case-bootstrap",
            ),
        ],
    )
    def test_accept_creates_activity(self, hold):
        inviter, dl_inviter = _make_actor_dl("Coordinator")
        invitee, dl_invitee = _make_actor_dl("Finder")
        dl_inviter.create(invitee)

        case = as_VulnerabilityCase(
            attributed_to=inviter.id_, name="Test Case", content="Content"
        )
        dl_inviter.create(case)

        invite = rm_invite_to_case_activity(
            invitee,
            target=case.id_,
            actor=inviter.id_,
            to=[invitee.id_],
        )
        dl_invitee.create(inviter)
        hold(dl_invitee, invite)

        request = AcceptCaseInviteTriggerRequest(
            actor_id=invitee.id_,
            invite_id=invite.id_,
        )
        result = SvcAcceptCaseInviteUseCase(
            dl_invitee,
            request,
            trigger_activity=TriggerActivityAdapter(dl_invitee),
            sync_port=SyncActivityAdapter(dl_invitee),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert result.activity is not None
        assert activity_of(result)["actor"] == invitee.id_
        assert activity_of(result)["inReplyTo"] == invite.id_
        assert activity_of(result).get("to") == [inviter.id_]

    def test_accept_raises_when_invite_missing(self):
        _, dl = _make_actor_dl("Finder")
        request = AcceptCaseInviteTriggerRequest(
            actor_id=_HTTP_ACTOR_ID,
            invite_id="https://example.org/activities/no-such-invite",
        )
        # Need an actor in the DL first
        actor = as_Service(name="Finder", id_=_HTTP_ACTOR_ID)
        dl.create(actor)

        with pytest.raises(VultronNotFoundError):
            SvcAcceptCaseInviteUseCase(
                dl,
                request,
                trigger_activity=TriggerActivityAdapter(dl),
                sync_port=SyncActivityAdapter(dl),
                wire_render_port=As2WireRenderAdapter(),
            ).execute()

    def test_accept_no_type_check_on_invite(self):
        """AC-2: type check removed — _prepare() only guards existence (ADR-0035 DL-06).

        The semantic type-check ('invite_type != Invite') was removed.
        _prepare() now only raises VultronNotFoundError when the invite is
        absent; passing an existing invite_id must reach the BT execution
        stage regardless of the stored object's type_.  Invites are always
        stored as as_Invite objects by invite_actor_to_case(), so this test
        uses a real Invite — it confirms no VultronValidationError is raised,
        which was the removed guard's error type.
        """
        inviter, dl_inviter = _make_actor_dl("Coordinator")
        invitee, dl_invitee = _make_actor_dl("Finder")
        dl_inviter.create(invitee)

        case = as_VulnerabilityCase(
            attributed_to=inviter.id_, name="Test Case", content="Content"
        )
        dl_inviter.create(case)

        invite = rm_invite_to_case_activity(
            invitee,
            target=case.id_,
            actor=inviter.id_,
            to=[invitee.id_],
        )
        dl_invitee.create(inviter)
        archive_received(dl_invitee, invite)

        request = AcceptCaseInviteTriggerRequest(
            actor_id=invitee.id_,
            invite_id=invite.id_,
        )
        # Should not raise VultronValidationError (type check removed per DL-06)
        result = SvcAcceptCaseInviteUseCase(
            dl_invitee,
            request,
            trigger_activity=TriggerActivityAdapter(dl_invitee),
            sync_port=SyncActivityAdapter(dl_invitee),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()
        assert result.activity is not None

    def test_accept_normalises_short_uuid_actor_id(self):
        """DR-09: short UUID in actor_id is resolved to full URI."""
        inviter, dl_inviter = _make_actor_dl("Coordinator")
        invitee, dl_invitee = _make_actor_dl_with_http_id(
            "Finder", _HTTP_ACTOR_ID
        )
        dl_inviter.create(invitee)

        case = as_VulnerabilityCase(
            attributed_to=inviter.id_, name="Test Case", content="Content"
        )
        dl_inviter.create(case)

        invite = rm_invite_to_case_activity(
            invitee,
            target=case.id_,
            actor=inviter.id_,
            to=[invitee.id_],
        )
        dl_invitee.create(inviter)
        archive_received(dl_invitee, invite)

        # Pass the bare UUID (as the FastAPI router does from the URL path)
        request = AcceptCaseInviteTriggerRequest(
            actor_id=_UUID,
            invite_id=invite.id_,
        )
        result = SvcAcceptCaseInviteUseCase(
            dl_invitee,
            request,
            trigger_activity=TriggerActivityAdapter(dl_invitee),
            sync_port=SyncActivityAdapter(dl_invitee),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert activity_of(result)["actor"] == _HTTP_ACTOR_ID


class TestSvcRejectCaseInviteUseCase:
    """Tests for the reject-case-invite trigger use case."""

    def test_reject_creates_activity(self):
        inviter, dl_inviter = _make_actor_dl("Coordinator")
        invitee, dl_invitee = _make_actor_dl("Vendor")
        dl_inviter.create(invitee)

        case = as_VulnerabilityCase(
            attributed_to=inviter.id_, name="Test Case", content="Content"
        )
        dl_inviter.create(case)

        invite = rm_invite_to_case_activity(
            invitee,
            target=case.id_,
            actor=inviter.id_,
            to=[invitee.id_],
        )
        dl_invitee.create(inviter)
        archive_received(dl_invitee, invite)

        request = RejectCaseInviteTriggerRequest(
            actor_id=invitee.id_,
            invite_id=invite.id_,
        )
        result = SvcRejectCaseInviteUseCase(
            dl_invitee,
            request,
            trigger_activity=TriggerActivityAdapter(dl_invitee),
            sync_port=SyncActivityAdapter(dl_invitee),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert result.activity is not None
        assert activity_of(result)["actor"] == invitee.id_
        assert activity_of(result).get("to") == [inviter.id_]

    def test_reject_raises_when_invite_missing(self):
        _, dl = _make_actor_dl("Vendor")
        request = RejectCaseInviteTriggerRequest(
            actor_id=_HTTP_ACTOR_ID,
            invite_id="https://example.org/activities/no-such-invite",
        )
        actor = as_Service(name="Vendor", id_=_HTTP_ACTOR_ID)
        dl.create(actor)

        with pytest.raises(VultronNotFoundError):
            SvcRejectCaseInviteUseCase(
                dl,
                request,
                trigger_activity=TriggerActivityAdapter(dl),
                sync_port=SyncActivityAdapter(dl),
                wire_render_port=As2WireRenderAdapter(),
            ).execute()

    def test_reject_normalises_short_uuid_actor_id(self):
        """DR-09: short UUID in actor_id is resolved to full URI."""
        inviter, dl_inviter = _make_actor_dl("Coordinator")
        invitee, dl_invitee = _make_actor_dl_with_http_id(
            "Vendor", _HTTP_ACTOR_ID
        )
        dl_inviter.create(invitee)

        case = as_VulnerabilityCase(
            attributed_to=inviter.id_, name="Test Case", content="Content"
        )
        dl_inviter.create(case)

        invite = rm_invite_to_case_activity(
            invitee,
            target=case.id_,
            actor=inviter.id_,
            to=[invitee.id_],
        )
        dl_invitee.create(inviter)
        archive_received(dl_invitee, invite)

        request = RejectCaseInviteTriggerRequest(
            actor_id=_UUID,
            invite_id=invite.id_,
        )
        result = SvcRejectCaseInviteUseCase(
            dl_invitee,
            request,
            trigger_activity=TriggerActivityAdapter(dl_invitee),
            sync_port=SyncActivityAdapter(dl_invitee),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert activity_of(result)["actor"] == _HTTP_ACTOR_ID


class TestSvcAcceptActorRecommendationUseCase:
    """Tests for the accept-actor-recommendation trigger use case."""

    def _make_cp_offer(
        self, dl: SqliteDataLayer, vendor_id: str, case_actor_id: str
    ):
        vendor = as_Service(id_=vendor_id, name="Vendor")
        offer = offer_case_participant_activity(
            recommended=vendor,
            actor=case_actor_id,
            to=["http://owner:7999/api/v2/actors/owner"],
        )
        dl.create(cast(as_CaseParticipant, offer.object_))
        dl.create(offer)
        return offer

    def test_accept_creates_accept_activity(self):
        owner, dl = _make_actor_dl("Owner")
        case_actor = as_Service(name="CaseActor")
        vendor = as_Service(name="Vendor")
        dl.create(case_actor)
        dl.create(vendor)

        offer = self._make_cp_offer(dl, vendor.id_, case_actor.id_)

        request = AcceptActorRecommendationTriggerRequest(
            actor_id=owner.id_,
            cp_offer_id=offer.id_,
            case_actor_id=case_actor.id_,
        )
        result = SvcAcceptActorRecommendationUseCase(
            dl,
            request,
            trigger_activity=TriggerActivityAdapter(dl),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert result.activity is not None
        activity = activity_of(result)
        assert activity["type"] == "Accept"

    def test_accept_raises_when_offer_not_found(self):
        owner, dl = _make_actor_dl("Owner")
        case_actor = as_Service(name="CaseActor")
        dl.create(case_actor)

        request = AcceptActorRecommendationTriggerRequest(
            actor_id=owner.id_,
            cp_offer_id="https://example.org/activities/no-such-offer",
            case_actor_id=case_actor.id_,
        )
        with pytest.raises(Exception):  # noqa: B017  # ruff-baseline #3353
            SvcAcceptActorRecommendationUseCase(
                dl,
                request,
                trigger_activity=TriggerActivityAdapter(dl),
                sync_port=SyncActivityAdapter(dl),
                wire_render_port=As2WireRenderAdapter(),
            ).execute()

    def test_accept_raises_when_actor_not_found(self):
        _, dl = _make_actor_dl("Owner")
        case_actor = as_Service(name="CaseActor")
        vendor = as_Service(name="Vendor")
        dl.create(case_actor)
        dl.create(vendor)
        offer = self._make_cp_offer(dl, vendor.id_, case_actor.id_)

        request = AcceptActorRecommendationTriggerRequest(
            actor_id="https://example.org/actors/ghost",
            cp_offer_id=offer.id_,
            case_actor_id=case_actor.id_,
        )
        with pytest.raises(VultronNotFoundError):
            SvcAcceptActorRecommendationUseCase(
                dl,
                request,
                trigger_activity=TriggerActivityAdapter(dl),
                sync_port=SyncActivityAdapter(dl),
                wire_render_port=As2WireRenderAdapter(),
            ).execute()


def _seed_delegated_case(owner, dl, *peers):
    """A case whose roster names a separate CASE_MANAGER (CM-24-006).

    The delegated emit runs as the CASE_MANAGER, and a BT reads and writes its
    executing actor's own store (ADR-0073), so the manager's store is seeded
    with the case as well.
    """
    case = as_VulnerabilityCase(
        attributed_to=owner.id_, name="Test Case", content="Content"
    )
    case_actor = as_Service(
        id_=f"{owner.id_}/case-actor", name="CaseActorService"
    )
    dl.create(case_actor)
    manager = as_CaseParticipant(
        id_=f"{case.id_}/participants/case-manager",
        context=case.id_,
        attributed_to=case_actor.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    dl.create(manager)
    case.case_participants.append(manager.id_)
    case.actor_participant_index[case_actor.id_] = manager.id_
    dl.create(case)
    case_actor_dl = dl.clone_for_actor(case_actor.id_)
    _CREATED_DLS.append(case_actor_dl)
    for obj in (owner, *peers, case, case_actor, manager):
        case_actor_dl.create(obj)
    return case, case_actor


class TestSvcOfferCaseOwnershipTransferUseCase:
    """Tests for the offer-case-ownership-transfer trigger use case (TRIG-11-001)."""

    def test_offer_creates_activity(self):
        owner, dl = _make_actor_dl("Vendor")
        transferee, _ = _make_actor_dl("Coordinator")
        dl.create(transferee)
        case, case_actor = _seed_delegated_case(owner, dl, transferee)

        from vultron.core.use_cases.triggers.actor import (
            SvcOfferCaseOwnershipTransferUseCase,
        )
        from vultron.core.use_cases.triggers.requests import (
            OfferCaseOwnershipTransferTriggerRequest,
        )

        request = OfferCaseOwnershipTransferTriggerRequest(
            actor_id=owner.id_,
            case_id=case.id_,
            transferee_id=transferee.id_,
        )
        result = SvcOfferCaseOwnershipTransferUseCase(
            dl,
            request,
            trigger_activity=TriggerActivityAdapter(dl),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert result.activity is not None
        activity_data = activity_of(result)
        assert activity_data["type"] == "Offer"
        assert activity_data["actor"] == case_actor.id_
        assert activity_data["attributedTo"] == owner.id_

    def test_offer_persisted_in_datalayer(self):
        owner, dl = _make_actor_dl("Vendor")
        transferee, _ = _make_actor_dl("Coordinator")
        dl.create(transferee)
        case, case_actor = _seed_delegated_case(owner, dl, transferee)

        from vultron.core.use_cases.triggers.actor import (
            SvcOfferCaseOwnershipTransferUseCase,
        )
        from vultron.core.use_cases.triggers.requests import (
            OfferCaseOwnershipTransferTriggerRequest,
        )

        request = OfferCaseOwnershipTransferTriggerRequest(
            actor_id=owner.id_,
            case_id=case.id_,
            transferee_id=transferee.id_,
        )
        result = SvcOfferCaseOwnershipTransferUseCase(
            dl,
            request,
            trigger_activity=TriggerActivityAdapter(dl),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        offer_id = activity_of(result)["id"]
        stored = dl.clone_for_actor(case_actor.id_).read(offer_id)
        assert stored is not None

    def test_offer_proceeds_when_transferee_not_in_dl(self, caplog):
        """A transferee is a peer named by URI; a local record is not required.

        Handing a case to an actor on another node is the ordinary case, and
        under per-actor storage that node's record is in *its* store (ADR-0073
        decision 5) — so the old 404 refused exactly the transfers the protocol
        exists to support. Same defect as the invite and recommend paths; all
        three share ``_record_named_peer`` with the ActorDiscoveryCallOutBundle
        seam. With DETERMINISTIC (AlwaysSucceed), no WARNING fires (AKM-05-002).
        """
        owner, dl = _make_actor_dl("Vendor")
        missing_id = "https://example.org/actors/nobody"
        case, _ = _seed_delegated_case(owner, dl)

        from vultron.core.use_cases.triggers.actor import (
            SvcOfferCaseOwnershipTransferUseCase,
        )
        from vultron.core.use_cases.triggers.requests import (
            OfferCaseOwnershipTransferTriggerRequest,
        )

        request = OfferCaseOwnershipTransferTriggerRequest(
            actor_id=owner.id_,
            case_id=case.id_,
            transferee_id=missing_id,
        )
        with caplog.at_level(logging.WARNING):
            result = SvcOfferCaseOwnershipTransferUseCase(
                dl,
                request,
                trigger_activity=TriggerActivityAdapter(dl),
                sync_port=SyncActivityAdapter(dl),
                wire_render_port=As2WireRenderAdapter(),
            ).execute()

        assert result is not None
        # No WARNING with the default DETERMINISTIC bundle (AlwaysSucceed)
        assert "actor discovery returned" not in caplog.text

    def test_offer_raises_when_case_not_in_dl(self):
        owner, dl = _make_actor_dl("Vendor")
        transferee, _ = _make_actor_dl("Coordinator")
        dl.create(transferee)

        from vultron.core.use_cases.triggers.actor import (
            SvcOfferCaseOwnershipTransferUseCase,
        )
        from vultron.core.use_cases.triggers.requests import (
            OfferCaseOwnershipTransferTriggerRequest,
        )

        request = OfferCaseOwnershipTransferTriggerRequest(
            actor_id=owner.id_,
            case_id="https://example.org/cases/nope",
            transferee_id=transferee.id_,
        )
        with pytest.raises(Exception):  # noqa: B017  # ruff-baseline #3353
            SvcOfferCaseOwnershipTransferUseCase(
                dl,
                request,
                trigger_activity=TriggerActivityAdapter(dl),
                sync_port=SyncActivityAdapter(dl),
                wire_render_port=As2WireRenderAdapter(),
            ).execute()

    def test_offer_uses_case_actor_as_sender_when_present(self):
        """CM-24-001/002: when the authority is a separate actor, the Offer actor
        MUST be that actor's ID and attributedTo MUST be the offering actor ID.
        """
        owner, dl = _make_actor_dl("Vendor")
        transferee, _ = _make_actor_dl("Coordinator")
        dl.create(transferee)
        case = as_VulnerabilityCase(
            attributed_to=owner.id_, name="Test Case", content="Content"
        )

        # The authority is resolved from the case's roster, not from a Service
        # whose `context` is the case id — ADR-0088 retired that signal
        # (ARCH-24-004).
        case_actor = as_Service(
            id_=f"{owner.id_}/case-actor",
            name="CaseActorService",
        )
        dl.create(case_actor)
        manager = as_CaseParticipant(
            id_=f"{case.id_}/participants/case-manager",
            context=case.id_,
            attributed_to=case_actor.id_,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        dl.create(manager)
        case.case_participants.append(manager.id_)
        case.actor_participant_index[case_actor.id_] = manager.id_
        dl.create(case)

        # The delegated-emit contract makes the CaseActor the actor this BT
        # executes as (CM-24-001), and a BT reads and writes its executing
        # actor's own store (ADR-0073) — which is *not* the owner's, even when
        # the two are co-located on one container.  In a deployment the
        # CaseActor's store holds the case because the CaseActor is the case
        # manager and keeps its canonical log; seeded here so the emit has a
        # case to enrich the wire object from (CM-17-002) instead of failing on
        # an empty store.
        case_actor_dl = dl.clone_for_actor(case_actor.id_)
        _CREATED_DLS.append(case_actor_dl)
        for obj in (owner, transferee, case, case_actor, manager):
            case_actor_dl.create(obj)

        from vultron.core.use_cases.triggers.actor import (
            SvcOfferCaseOwnershipTransferUseCase,
        )
        from vultron.core.use_cases.triggers.requests import (
            OfferCaseOwnershipTransferTriggerRequest,
        )

        request = OfferCaseOwnershipTransferTriggerRequest(
            actor_id=owner.id_,
            case_id=case.id_,
            transferee_id=transferee.id_,
        )
        result = SvcOfferCaseOwnershipTransferUseCase(
            dl,
            request,
            trigger_activity=TriggerActivityAdapter(dl),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        activity_data = activity_of(result)
        assert activity_data["type"] == "Offer"
        # CM-24-001: Offer actor MUST be the CaseActor, not the offering actor
        assert activity_data["actor"] == case_actor.id_
        # CM-24-002: offering actor attribution MUST be preserved
        assert activity_data.get("attributedTo") == owner.id_
        # The activity must be in the CaseActor's outbox (CM-24-004)
        case_actor_outbox = dl.clone_for_actor(case_actor.id_).outbox_list()
        assert activity_data["id"] in case_actor_outbox


class TestSvcAcceptCaseOwnershipTransferUseCase:
    """Tests for the accept-case-ownership-transfer trigger use case (TRIG-11-002)."""

    def _make_ownership_offer(
        self,
        dl: SqliteDataLayer,
        owner_id: str,
        transferee_id: str,
        case: as_VulnerabilityCase,
    ):
        from vultron.wire.as2.factories.case import (
            offer_case_ownership_transfer_activity,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase as _VC,
        )

        case_wire = _VC.model_validate(
            {"id": case.id_, "name": case.name or "Test"}
        )
        offer = offer_case_ownership_transfer_activity(
            case=case_wire,
            target=transferee_id,
            actor=owner_id,
            to=[transferee_id],
        )
        dl.create(offer)
        return offer

    def test_accept_creates_activity(self):
        # The *transferee* accepts, so the store is the transferee's own: it is
        # the actor that received the Offer, and the store an execution runs
        # against is the executing actor's (ADR-0073, DL-07-009).
        owner, _ = _make_actor_dl("Vendor")
        transferee, dl = _make_actor_dl("Coordinator")
        dl.create(owner)
        case = as_VulnerabilityCase(
            attributed_to=owner.id_, name="Test Case", content="Content"
        )
        dl.create(case)
        offer = self._make_ownership_offer(dl, owner.id_, transferee.id_, case)

        from vultron.core.use_cases.triggers.actor import (
            SvcAcceptCaseOwnershipTransferUseCase,
        )
        from vultron.core.use_cases.triggers.requests import (
            AcceptCaseOwnershipTransferTriggerRequest,
        )

        request = AcceptCaseOwnershipTransferTriggerRequest(
            actor_id=transferee.id_,
            offer_id=offer.id_,
        )
        result = SvcAcceptCaseOwnershipTransferUseCase(
            dl,
            request,
            trigger_activity=TriggerActivityAdapter(dl),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert result.activity is not None
        activity_data = activity_of(result)
        assert activity_data["type"] == "Accept"
        assert activity_data["actor"] == transferee.id_

    def test_accept_persisted_in_datalayer(self):
        # The transferee's own store, for the reason given in
        # ``test_accept_creates_activity``; it is also the store the Accept must
        # land in, which is what this test reads back.
        owner, _ = _make_actor_dl("Vendor")
        transferee, dl = _make_actor_dl("Coordinator")
        dl.create(owner)
        case = as_VulnerabilityCase(
            attributed_to=owner.id_, name="Test Case", content="Content"
        )
        dl.create(case)
        offer = self._make_ownership_offer(dl, owner.id_, transferee.id_, case)

        from vultron.core.use_cases.triggers.actor import (
            SvcAcceptCaseOwnershipTransferUseCase,
        )
        from vultron.core.use_cases.triggers.requests import (
            AcceptCaseOwnershipTransferTriggerRequest,
        )

        request = AcceptCaseOwnershipTransferTriggerRequest(
            actor_id=transferee.id_,
            offer_id=offer.id_,
        )
        result = SvcAcceptCaseOwnershipTransferUseCase(
            dl,
            request,
            trigger_activity=TriggerActivityAdapter(dl),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        accept_id = activity_of(result)["id"]
        stored = dl.read(accept_id)
        assert stored is not None

    def test_accept_raises_when_offer_not_in_dl(self):
        _owner, dl = _make_actor_dl("Vendor")
        transferee, _ = _make_actor_dl("Coordinator")
        dl.create(transferee)

        from vultron.core.use_cases.triggers.actor import (
            SvcAcceptCaseOwnershipTransferUseCase,
        )
        from vultron.core.use_cases.triggers.requests import (
            AcceptCaseOwnershipTransferTriggerRequest,
        )

        request = AcceptCaseOwnershipTransferTriggerRequest(
            actor_id=transferee.id_,
            offer_id="https://example.org/activities/nope",
        )
        with pytest.raises(VultronNotFoundError):
            SvcAcceptCaseOwnershipTransferUseCase(
                dl,
                request,
                trigger_activity=TriggerActivityAdapter(dl),
                sync_port=SyncActivityAdapter(dl),
                wire_render_port=As2WireRenderAdapter(),
            ).execute()

    def test_accept_raises_when_actor_not_found(self):
        owner, dl = _make_actor_dl("Vendor")
        case = as_VulnerabilityCase(
            attributed_to=owner.id_, name="Test Case", content="Content"
        )
        dl.create(case)
        transferee_id = "https://example.org/actors/coordinator"
        offer = self._make_ownership_offer(dl, owner.id_, transferee_id, case)

        from vultron.core.use_cases.triggers.actor import (
            SvcAcceptCaseOwnershipTransferUseCase,
        )
        from vultron.core.use_cases.triggers.requests import (
            AcceptCaseOwnershipTransferTriggerRequest,
        )

        request = AcceptCaseOwnershipTransferTriggerRequest(
            actor_id="https://example.org/actors/ghost",
            offer_id=offer.id_,
        )
        with pytest.raises(VultronNotFoundError):
            SvcAcceptCaseOwnershipTransferUseCase(
                dl,
                request,
                trigger_activity=TriggerActivityAdapter(dl),
                sync_port=SyncActivityAdapter(dl),
                wire_render_port=As2WireRenderAdapter(),
            ).execute()

    def test_accept_raises_when_offer_has_no_case_reference(self):
        """VultronNotFoundError raised when the Offer names no case.

        ``_prepare`` accepts either shape of stored offer — the SYNC replica's
        ``VultronOwnershipTransferOfferRecord`` (case URI in ``case_id``) or the
        HTTP-inbox path's wire Offer activity (case in ``object_``) — and raises
        only when neither yields an id.  Both attributes must therefore be
        cleared on the mock; a bare ``MagicMock`` would auto-create a truthy
        ``case_id`` and silently satisfy the guard.
        """
        from unittest.mock import MagicMock

        from vultron.core.use_cases.triggers.actor import (
            SvcAcceptCaseOwnershipTransferUseCase,
        )
        from vultron.core.use_cases.triggers.requests import (
            AcceptCaseOwnershipTransferTriggerRequest,
        )

        actor_id = "https://example.org/actors/transferee-nobj"
        offer_id = "https://example.org/activities/offer-nobj"

        actor_mock = MagicMock()
        actor_mock.id_ = actor_id

        offer_mock = MagicMock()
        offer_mock.case_id = None
        offer_mock.object_ = None

        mock_dl = MagicMock()
        mock_dl.read.side_effect = lambda id_: (
            actor_mock if id_ == actor_id else offer_mock
        )

        request = AcceptCaseOwnershipTransferTriggerRequest(
            actor_id=actor_id,
            offer_id=offer_id,
        )
        with pytest.raises(VultronNotFoundError):
            SvcAcceptCaseOwnershipTransferUseCase(
                mock_dl,
                request,
                trigger_activity=TriggerActivityAdapter(mock_dl),
                sync_port=SyncActivityAdapter(mock_dl),
                wire_render_port=As2WireRenderAdapter(),
            ).execute()

    def test_accept_to_field_is_case_actor(self):
        """Accept activity must be addressed to the CaseActor (CM-21-006 / ADR-0053).

        ``EmitAcceptCaseOwnershipTransferNode._call_factory()`` calls
        ``resolve_case_manager_id`` and sets ``to=[case_actor_id]``.
        This test seeds a case with a CASE_MANAGER participant and verifies
        the emitted ``to`` field carries the case actor URI.
        """
        # The store is the *transferee's*: it is the requesting actor, so it is
        # the actor the BT executes as, and a BT reads and writes its executing
        # actor's own store (ADR-0073).  Holding the owner's store instead left
        # the tree looking for the case in an empty one, and `to` fell back to an
        # actor that is not the case manager — the assertion below failed on a
        # value that had nothing to do with `resolve_case_manager_id`.
        transferee, dl = _make_actor_dl("Coordinator")

        owner, _ = _make_actor_dl("Vendor")
        dl.create(owner)

        case_actor, _ = _make_actor_dl("CaseActor")
        dl.create(case_actor)

        # _make_case_with_case_manager seeds CASE_MANAGER participant so
        # resolve_case_manager_id can find case_actor.id_ from the case.
        case = _make_case_with_case_manager(dl, owner.id_, case_actor.id_)
        offer = self._make_ownership_offer(dl, owner.id_, transferee.id_, case)

        from vultron.core.use_cases.triggers.actor import (
            SvcAcceptCaseOwnershipTransferUseCase,
        )
        from vultron.core.use_cases.triggers.requests import (
            AcceptCaseOwnershipTransferTriggerRequest,
        )

        request = AcceptCaseOwnershipTransferTriggerRequest(
            actor_id=transferee.id_,
            offer_id=offer.id_,
        )
        result = SvcAcceptCaseOwnershipTransferUseCase(
            dl,
            request,
            trigger_activity=TriggerActivityAdapter(dl),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        activity_data = activity_of(result)
        assert activity_data["type"] == "Accept"
        # Primary invariant of ADR-0053 CM-21-006: Accept is routed to CaseActor.
        assert case_actor.id_ in activity_data.get("to", [])


class TestSvcOfferCaseParticipantRoleUseCase:
    """Tests for SvcOfferCaseParticipantRoleUseCase (SE-08-003, ADR-0039)."""

    def _setup(self):
        actor, dl = _make_actor_dl("Vendor")
        target, _ = _make_actor_dl("Coordinator")
        dl.create(target)
        case = as_VulnerabilityCase(
            attributed_to=actor.id_, name="CPR Test Case", content="Content"
        )
        dl.create(case)
        return actor, target, dl, case

    def test_happy_path_returns_activity(self):
        """SE-08-003: successful offer returns activity_id and activity dict."""
        actor, target, dl, case = self._setup()
        request = OfferCaseParticipantRoleTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            target_actor_id=target.id_,
            role=CVDRole.CASE_MANAGER,
        )
        result = SvcOfferCaseParticipantRoleUseCase(
            dl, request, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        assert isinstance(result, RoleOfferResult)
        assert result.activity["type"] == "Offer"

    def test_happy_path_activity_persisted(self):
        """Emitted Offer activity is readable from the DataLayer."""
        actor, target, dl, case = self._setup()
        request = OfferCaseParticipantRoleTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            target_actor_id=target.id_,
            role=CVDRole.VENDOR,
        )
        result = SvcOfferCaseParticipantRoleUseCase(
            dl, request, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        stored = dl.read(result.activity_id)
        assert stored is not None

    def test_raises_when_trigger_activity_missing(self):
        """RuntimeError when trigger_activity is None (SE-08-003 guard)."""
        actor, target, dl, case = self._setup()
        request = OfferCaseParticipantRoleTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            target_actor_id=target.id_,
        )
        with pytest.raises(RuntimeError):
            SvcOfferCaseParticipantRoleUseCase(
                dl, request, trigger_activity=None
            ).execute()


class TestActorDiscoveryCallOut:
    """Tests for the ActorDiscoveryCallOutBundle seam (ADR-0024, ADR-0025, AKM-05).

    Verifies that the injectable call-out factory:
    - fires no WARNING with the DETERMINISTIC (AlwaysSucceed) default
    - fires a WARNING when a FAILURE backend is injected
    - proceeds in both cases (annotating, not blocking — AC-4)
    """

    def test_default_bundle_no_warning_on_missing_invitee(self, caplog):
        """DETERMINISTIC (AlwaysSucceed) logs at DEBUG; no WARNING emitted."""
        from vultron.core.behaviors.call_out.bundles.actor_discovery import (
            ACTOR_DISCOVERY_DETERMINISTIC,
        )

        actor, dl = _make_actor_dl("Coordinator")
        missing_id = "https://example.org/actors/discovery-test"
        case = _make_case_with_case_manager(dl, actor.id_, _CASE_MANAGER_ID)

        request = InviteActorToCaseTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            invitee_id=missing_id,
        )
        with caplog.at_level(logging.WARNING):
            result = SvcInviteActorToCaseUseCase(
                dl,
                request,
                trigger_activity=TriggerActivityAdapter(dl),
                sync_port=SyncActivityAdapter(dl),
                call_out=ACTOR_DISCOVERY_DETERMINISTIC,
                wire_render_port=As2WireRenderAdapter(),
            ).execute()

        assert result is not None
        assert "actor discovery returned" not in caplog.text

    def test_failure_backend_warns_on_missing_invitee(self, caplog):
        """When the backend returns FAILURE an explicit WARNING is emitted (AKM-05-002)."""
        from vultron.core.behaviors.call_out.bundles.actor_discovery import (
            ActorDiscoveryCallOutBundle,
        )
        from vultron.core.behaviors.call_out.nodes import AlwaysFail

        def _always_fail(name: str):
            return AlwaysFail(name)

        fail_bundle = ActorDiscoveryCallOutBundle(
            resolve_actor_factory=_always_fail  # type: ignore[arg-type]
        )

        actor, dl = _make_actor_dl("Coordinator")
        missing_id = "https://example.org/actors/unreachable"
        case = _make_case_with_case_manager(dl, actor.id_, _CASE_MANAGER_ID)

        request = InviteActorToCaseTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            invitee_id=missing_id,
        )
        with caplog.at_level(logging.WARNING):
            result = SvcInviteActorToCaseUseCase(
                dl,
                request,
                trigger_activity=TriggerActivityAdapter(dl),
                sync_port=SyncActivityAdapter(dl),
                call_out=fail_bundle,
                wire_render_port=As2WireRenderAdapter(),
            ).execute()

        # Invite proceeds even on FAILURE — annotating, not blocking (AC-4)
        assert result is not None
        # Explicit WARNING is emitted (AC-3, AKM-05-002)
        assert "actor discovery returned FAILURE" in caplog.text
        assert missing_id in caplog.text

    def test_failure_backend_records_minimal_peer(self):
        """Even when discovery fails, a minimal CoreActor record is created."""
        from vultron.core.behaviors.call_out.bundles.actor_discovery import (
            ActorDiscoveryCallOutBundle,
        )
        from vultron.core.behaviors.call_out.nodes import AlwaysFail

        def _always_fail(name: str):
            return AlwaysFail(name)

        fail_bundle = ActorDiscoveryCallOutBundle(
            resolve_actor_factory=_always_fail  # type: ignore[arg-type]
        )

        actor, dl = _make_actor_dl("Coordinator")
        missing_id = "https://example.org/actors/unreachable2"
        case = _make_case_with_case_manager(dl, actor.id_, _CASE_MANAGER_ID)

        request = InviteActorToCaseTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            invitee_id=missing_id,
        )
        SvcInviteActorToCaseUseCase(
            dl,
            request,
            trigger_activity=TriggerActivityAdapter(dl),
            sync_port=SyncActivityAdapter(dl),
            call_out=fail_bundle,
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        # Peer recorded even on FAILURE (protocol proceeds with URI-only record)
        recorded = dl.read(missing_id)
        assert recorded is not None
        assert str(recorded.id_) == missing_id

    @pytest.mark.spec("BT-18-011")
    def test_running_backend_degrades_gracefully(self, caplog):
        """A RUNNING backend violates BT-18-011; this procedural path degrades.

        The guard rejects a RUNNING return by raising CallOutContractError. In
        this single-tick, non-BT path there is no tree to busy-loop, so the
        request must not crash: it records a minimal peer (as with any other
        non-SUCCESS) and surfaces the offending backend via a WARNING.
        """
        import py_trees
        from py_trees.common import Status

        from vultron.core.behaviors.call_out.bundles.actor_discovery import (
            ActorDiscoveryCallOutBundle,
        )

        class _Running(py_trees.behaviour.Behaviour):
            def update(self):
                return Status.RUNNING

        running_bundle = ActorDiscoveryCallOutBundle(
            resolve_actor_factory=_Running  # type: ignore[arg-type]
        )

        actor, dl = _make_actor_dl("Coordinator")
        missing_id = "https://example.org/actors/still-resolving"
        case = _make_case_with_case_manager(dl, actor.id_, _CASE_MANAGER_ID)

        request = InviteActorToCaseTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            invitee_id=missing_id,
        )
        with caplog.at_level(logging.WARNING):
            # Must NOT raise CallOutContractError out of the use case.
            result = SvcInviteActorToCaseUseCase(
                dl,
                request,
                trigger_activity=TriggerActivityAdapter(dl),
                sync_port=SyncActivityAdapter(dl),
                call_out=running_bundle,
                wire_render_port=As2WireRenderAdapter(),
            ).execute()

        assert result is not None
        # Minimal peer still recorded; the offending backend is named in the log.
        recorded = dl.read(missing_id)
        assert recorded is not None
        assert str(recorded.id_) == missing_id
        assert "BT-18-011" in caplog.text
        assert missing_id in caplog.text
