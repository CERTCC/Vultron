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
SvcAcceptCaseInviteUseCase, and SvcOfferCaseManagerRoleUseCase.
Includes DR-09 regression tests verifying that short UUIDs in actor_id
are normalised to full URIs before use.
"""

import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.enums.roles import CVDRole
from vultron.core.use_cases.triggers.actor import (
    SvcAcceptCaseInviteUseCase,
    SvcInviteActorToCaseUseCase,
    SvcOfferCaseManagerRoleUseCase,
    SvcSuggestActorToCaseUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptCaseInviteTriggerRequest,
    InviteActorToCaseTriggerRequest,
    OfferCaseManagerRoleTriggerRequest,
    SuggestActorToCaseTriggerRequest,
)
from vultron.errors import VultronNotFoundError, VultronValidationError
from vultron.wire.as2.factories import rm_invite_to_case_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Invite
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
    VulnerabilityCaseStub,
)
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)

_BASE = "http://coordinator:7999/api/v2/actors"
_UUID = "24d63c7d-6b1e-4f61-a5e1-180d27192d0b"
_HTTP_ACTOR_ID = f"{_BASE}/{_UUID}"
_CREATED_DLS: list[SqliteDataLayer] = []


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
        attributed_to=owner_actor_id, name="Test Case", content="Content"
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


class TestSvcInviteActorToCaseUseCase:
    """Tests for the invite-actor-to-case trigger use case."""

    def test_invite_creates_activity_and_populates_to(self):
        actor, dl = _make_actor_dl("Coordinator")
        invitee, _ = _make_actor_dl("Finder")

        # Seed invitee and case in actor's DL
        dl.create(invitee)
        case = as_VulnerabilityCase(
            attributed_to=actor.id_,
            name="Test Case",
            content="Test case content",
        )
        dl.create(case)

        request = InviteActorToCaseTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            invitee_id=invitee.id_,
        )
        result = SvcInviteActorToCaseUseCase(
            dl, request, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        assert "activity" in result
        activity_data = result["activity"]
        assert activity_data["type"] == "Invite"
        assert activity_data["actor"] == actor.id_
        assert invitee.id_ in activity_data.get("to", [])

    def test_invite_persisted_in_datalayer(self):
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
        result = SvcInviteActorToCaseUseCase(
            dl, request, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        invite_id = result["activity"]["id"]
        stored = dl.read(invite_id)
        assert stored is not None
        assert isinstance(stored, as_Invite)

    def test_invite_raises_when_invitee_not_in_dl(self):
        actor, dl = _make_actor_dl("Coordinator")
        # invitee NOT seeded in actor's DL
        missing_id = "https://example.org/actors/nobody"
        case = as_VulnerabilityCase(
            attributed_to=actor.id_, name="Test Case", content="Content"
        )
        dl.create(case)

        request = InviteActorToCaseTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            invitee_id=missing_id,
        )
        with pytest.raises(VultronNotFoundError):
            SvcInviteActorToCaseUseCase(
                dl, request, trigger_activity=TriggerActivityAdapter(dl)
            ).execute()

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
        with pytest.raises(Exception):
            SvcInviteActorToCaseUseCase(
                dl, request, trigger_activity=TriggerActivityAdapter(dl)
            ).execute()

    def test_invite_normalises_short_uuid_actor_id(self):
        """DR-09: short UUID in actor_id is resolved to full URI."""
        actor, dl = _make_actor_dl_with_http_id("Coordinator", _HTTP_ACTOR_ID)
        invitee, _ = _make_actor_dl("Finder")
        dl.create(invitee)
        case = as_VulnerabilityCase(
            attributed_to=_HTTP_ACTOR_ID, name="Test Case", content="Content"
        )
        dl.create(case)

        # Pass the bare UUID (as the FastAPI router does from the URL path)
        request = InviteActorToCaseTriggerRequest(
            actor_id=_UUID,
            case_id=case.id_,
            invitee_id=invitee.id_,
        )
        result = SvcInviteActorToCaseUseCase(
            dl, request, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        # Activity actor field must be the full canonical URI, not the short UUID
        assert result["activity"]["actor"] == _HTTP_ACTOR_ID

    def test_invite_uses_case_actor_when_present(self):
        """PCR-08-007: when a Case Actor Service exists the invite actor must
        be the Case Actor ID, not the case-owner actor ID.  The case owner's
        ID is carried in ``attributedTo`` instead.
        """
        from vultron.wire.as2.vocab.base.objects.actors import as_Service

        actor, dl = _make_actor_dl("Vendor")
        invitee, _ = _make_actor_dl("Coordinator")
        dl.create(invitee)
        case = as_VulnerabilityCase(
            attributed_to=actor.id_, name="PCR Test Case", content="Content"
        )
        dl.create(case)

        # Register a Case Actor Service with context = case.id_
        case_actor = as_Service(
            id_=f"{actor.id_}/case-actor",
            context=case.id_,
            name="CaseActorService",
        )
        dl.create(case_actor)

        request = InviteActorToCaseTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            invitee_id=invitee.id_,
        )
        result = SvcInviteActorToCaseUseCase(
            dl, request, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        activity_data = result["activity"]
        assert activity_data["type"] == "Invite"
        # Invite actor MUST be the Case Actor Service ID (PCR-08-007)
        assert activity_data["actor"] == case_actor.id_
        # Case owner attribution is preserved
        assert activity_data.get("attributedTo") == actor.id_
        # The activity must be in the Case Actor's outbox, not the owner's
        case_actor_outbox = dl.clone_for_actor(case_actor.id_).outbox_list()
        assert activity_data["id"] in case_actor_outbox


class TestInviteRolesAndEmbargoEnrichment:
    """AC-1 through AC-6: roles + embargo enrichment on Invite (CM-17-002/003)."""

    def setup_method(self):
        import py_trees

        py_trees.blackboard.Blackboard.enable_activity_stream()

    def teardown_method(self):
        import py_trees

        py_trees.blackboard.Blackboard.clear()
        py_trees.blackboard.Blackboard.disable_activity_stream()

    def _setup_invite(self, with_embargo=False, with_active_embargo=False):
        """Create actor, invitee, case; optionally add active embargo."""
        from vultron.core.states.em import EM
        from vultron.wire.as2.vocab.objects.embargo_event import (
            as_EmbargoEvent,
        )

        actor, dl = _make_actor_dl("CaseOwner")
        invitee, _ = _make_actor_dl("Invitee")
        dl.create(invitee)
        case = as_VulnerabilityCase(
            attributed_to=actor.id_, name="Test Case", content="Content"
        )
        dl.create(case)
        if with_active_embargo:
            embargo = as_EmbargoEvent(
                id_=f"{case.id_}/embargo/e1",
                content="Active embargo",
            )
            dl.create(embargo)
            case.active_embargo = embargo.id_
            case.current_status.em_state = EM.ACTIVE
            dl.save(case)
        elif with_embargo:
            case.active_embargo = f"{case.id_}/embargo/e1"
            dl.save(case)
        return actor, invitee, dl, case

    def test_ac6_roles_field_accepted_in_request(self):
        """AC-6: InviteActorToCaseTriggerRequest accepts optional roles field."""
        actor, invitee, dl, case = self._setup_invite()
        request = InviteActorToCaseTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            invitee_id=invitee.id_,
            roles=[CVDRole.VENDOR],
        )
        assert request.roles == [CVDRole.VENDOR]

    def test_ac3_roles_carried_in_invite_activity(self):
        """AC-3: Invite wire object carries roles field with intended CVD roles."""
        actor, invitee, dl, case = self._setup_invite()
        request = InviteActorToCaseTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            invitee_id=invitee.id_,
            roles=[CVDRole.VENDOR],
        )
        result = SvcInviteActorToCaseUseCase(
            dl, request, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        activity_data = result["activity"]
        assert "roles" in activity_data
        assert activity_data["roles"] == ["vendor"]

        invite_id = activity_data["id"]
        stored = dl.read(invite_id)
        assert isinstance(stored, as_Invite)
        assert stored.roles == ["vendor"]

    def test_ac3_no_roles_when_not_specified(self):
        """AC-3 negative: Invite carries no roles when none requested."""
        actor, invitee, dl, case = self._setup_invite()
        request = InviteActorToCaseTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            invitee_id=invitee.id_,
        )
        result = SvcInviteActorToCaseUseCase(
            dl, request, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        activity_data = result["activity"]
        assert activity_data.get("roles") is None

    def test_ac1_active_embargo_enriches_case_stub(self):
        """AC-1: Invite.target stub carries activeEmbargo.endTime and emState=ACTIVE."""
        from datetime import datetime, timezone

        from vultron.wire.as2.vocab.objects.embargo_event import (
            as_EmbargoEvent,
        )

        actor, invitee, dl, case = self._setup_invite()
        end_time = datetime(2030, 1, 1, tzinfo=timezone.utc)
        embargo = as_EmbargoEvent(
            id_=f"{case.id_}/embargo/e1",
            content="Active embargo",
            end_time=end_time,
        )
        dl.create(embargo)
        from vultron.core.states.em import EM

        case.active_embargo = embargo.id_
        case.current_status.em_state = EM.ACTIVE
        dl.save(case)

        request = InviteActorToCaseTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            invitee_id=invitee.id_,
        )
        result = SvcInviteActorToCaseUseCase(
            dl, request, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        activity_data = result["activity"]
        target = activity_data.get("target", {})
        active_embargo = target.get("activeEmbargo")
        assert (
            active_embargo is not None
        ), "activeEmbargo must be present when em_state==ACTIVE"
        assert (
            isinstance(active_embargo, dict) and "endTime" in active_embargo
        ), "activeEmbargo must be a full embargo object with endTime (CM-17-002)"
        case_status = target.get("caseStatus", {})
        assert case_status.get("emState") in (
            "active",
            "ACTIVE",
        ), "caseStatus.emState must be present when em_state==ACTIVE"

    def test_ac2_no_embargo_fields_when_not_active(self):
        """AC-2: Invite.target stub has no embargo fields when em_state != ACTIVE."""
        actor, invitee, dl, case = self._setup_invite()
        request = InviteActorToCaseTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            invitee_id=invitee.id_,
        )
        result = SvcInviteActorToCaseUseCase(
            dl, request, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        activity_data = result["activity"]
        target = activity_data.get("target", {})
        assert (
            target.get("activeEmbargo") is None
        ), "activeEmbargo must not be present when em_state != ACTIVE"
        assert (
            target.get("caseStatus") is None
        ), "caseStatus must not be present when em_state != ACTIVE"


class TestRolesThreadingIntegration:
    """AC-1 / AC-2: full roles-threading round-trip end-to-end (Issue-1405).

    InviteActorToCaseTriggerRequest.roles flows through the BT blackboard
    (suggested_roles) → Invite wire object → Accept(Invite) BT →
    VultronParticipant.case_roles.
    """

    def setup_method(self):
        import py_trees

        py_trees.blackboard.Blackboard.enable_activity_stream()

    def teardown_method(self):
        import py_trees

        py_trees.blackboard.Blackboard.clear()
        py_trees.blackboard.Blackboard.disable_activity_stream()

    def _run_round_trip(self, roles, make_payload):
        """Trigger Invite then Accept(Invite); return the new VultronParticipant."""
        from typing import Any, cast
        from unittest.mock import MagicMock

        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.use_cases.received.actor.invite import (
            AcceptInviteActorToCaseReceivedUseCase,
        )
        from vultron.wire.as2.factories import (
            rm_accept_invite_to_case_activity,
        )
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Invite,
        )
        from vultron.wire.as2.vocab.base.objects.actors import (
            as_Organization,
            as_Service,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        # Shared DataLayer: both trigger and receive sides use it so the
        # persisted Invite is visible when Accept is processed.
        dl = SqliteDataLayer("sqlite:///:memory:")
        _CREATED_DLS.append(dl)

        owner = as_Service(name="CaseOwner")
        dl.create(owner)
        invitee_id = "https://example.org/actors/invitee-roundtrip"
        invitee = as_Organization(id_=invitee_id)
        dl.create(invitee)
        case = as_VulnerabilityCase(
            attributed_to=owner.id_, name="Roles Round-Trip Test"
        )
        dl.create(case)

        from vultron.adapters.driven.datalayer_sqlite import reset_datalayer

        reset_datalayer(owner.id_)
        owner_dl = SqliteDataLayer("sqlite:///:memory:", actor_id=owner.id_)
        _CREATED_DLS.append(owner_dl)
        owner_dl.create(owner)
        owner_dl.create(invitee)
        owner_dl.create(case)

        request = InviteActorToCaseTriggerRequest(
            actor_id=owner.id_,
            case_id=case.id_,
            invitee_id=invitee_id,
            roles=roles,
        )
        result = SvcInviteActorToCaseUseCase(
            owner_dl,
            request,
            trigger_activity=TriggerActivityAdapter(owner_dl),
        ).execute()

        invite_id = result["activity"]["id"]
        invite_obj = owner_dl.read(invite_id)
        assert isinstance(invite_obj, as_Invite)
        dl.create(invite_obj)

        accept = rm_accept_invite_to_case_activity(
            invite_obj, actor=invitee_id
        )
        event = make_payload(accept)

        AcceptInviteActorToCaseReceivedUseCase(
            dl, event, sync_port=MagicMock()
        ).execute()

        updated_case = cast(Any, dl.read(case.id_))
        participant_id = updated_case.actor_participant_index.get(invitee_id)
        assert (
            participant_id is not None
        ), "invitee must be registered after Accept"
        participant = cast(Any, dl.read(participant_id))
        assert (
            participant is not None
        ), "participant object not found in DataLayer"
        return participant

    def test_ac1_roles_vendor_reaches_participant_case_roles(
        self, make_payload
    ):
        """AC-1 (CM-17-003/004): roles=[CVDRole.VENDOR] in request results in
        VultronParticipant.case_roles=[CVDRole.VENDOR] after Accept(Invite)."""
        participant = self._run_round_trip(
            roles=[CVDRole.VENDOR], make_payload=make_payload
        )
        assert (
            CVDRole.VENDOR in participant.case_roles
        ), f"AC-1: expected CVDRole.VENDOR in case_roles, got {participant.case_roles!r}"

    def test_ac2_none_roles_gives_empty_case_roles(self, make_payload):
        """AC-2 (CM-17-003/004): roles=None in request results in
        VultronParticipant.case_roles=[] after Accept(Invite)."""
        participant = self._run_round_trip(
            roles=None, make_payload=make_payload
        )
        assert (
            participant.case_roles == []
        ), f"AC-2: expected empty case_roles, got {participant.case_roles!r}"


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
            dl, request, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        assert "activity" in result
        assert result["activity"]["actor"] == actor.id_
        assert result["activity"].get("to") == [case_actor.id_]

    def test_suggest_raises_when_suggested_actor_missing(self):
        actor, dl = _make_actor_dl("Coordinator")
        case_actor, _ = _make_actor_dl("Case Actor")
        dl.create(case_actor)
        case = _make_case_with_case_manager(dl, actor.id_, case_actor.id_)

        request = SuggestActorToCaseTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            suggested_actor_id="https://example.org/actors/ghost",
        )
        with pytest.raises(VultronNotFoundError):
            SvcSuggestActorToCaseUseCase(
                dl, request, trigger_activity=TriggerActivityAdapter(dl)
            ).execute()

    def test_suggest_normalises_short_uuid_actor_id(self):
        """DR-09: short UUID in actor_id is resolved to full URI."""
        actor, dl = _make_actor_dl_with_http_id("Coordinator", _HTTP_ACTOR_ID)
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
            dl, request, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        assert result["activity"]["actor"] == _HTTP_ACTOR_ID
        assert result["activity"].get("to") == [case_actor.id_]

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
                dl, request, trigger_activity=TriggerActivityAdapter(dl)
            ).execute()


class TestSvcAcceptCaseInviteUseCase:
    """Tests for the accept-case-invite trigger use case."""

    def test_accept_creates_activity(self):
        inviter, dl_inviter = _make_actor_dl("Coordinator")
        invitee, dl_invitee = _make_actor_dl("Finder")
        dl_inviter.create(invitee)

        case = as_VulnerabilityCase(
            attributed_to=inviter.id_, name="Test Case", content="Content"
        )
        dl_inviter.create(case)

        invite = rm_invite_to_case_activity(
            invitee,
            target=VulnerabilityCaseStub(id_=case.id_),
            actor=inviter.id_,
            to=[invitee.id_],
        )
        dl_invitee.create(inviter)
        dl_invitee.create(invite)

        request = AcceptCaseInviteTriggerRequest(
            actor_id=invitee.id_,
            invite_id=invite.id_,
        )
        result = SvcAcceptCaseInviteUseCase(
            dl_invitee,
            request,
            trigger_activity=TriggerActivityAdapter(dl_invitee),
        ).execute()

        assert "activity" in result
        assert result["activity"]["actor"] == invitee.id_
        assert result["activity"]["inReplyTo"] == invite.id_
        assert result["activity"].get("to") == [inviter.id_]

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
                dl, request, trigger_activity=TriggerActivityAdapter(dl)
            ).execute()

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
            target=VulnerabilityCaseStub(id_=case.id_),
            actor=inviter.id_,
            to=[invitee.id_],
        )
        dl_invitee.create(inviter)
        dl_invitee.create(invite)

        # Pass the bare UUID (as the FastAPI router does from the URL path)
        request = AcceptCaseInviteTriggerRequest(
            actor_id=_UUID,
            invite_id=invite.id_,
        )
        result = SvcAcceptCaseInviteUseCase(
            dl_invitee,
            request,
            trigger_activity=TriggerActivityAdapter(dl_invitee),
        ).execute()

        assert result["activity"]["actor"] == _HTTP_ACTOR_ID


def _make_case_with_case_actor(
    dl: SqliteDataLayer, owner_actor_id: str, case_actor_id: str
) -> tuple[as_VulnerabilityCase, str]:
    """Create a as_VulnerabilityCase with a registered Case Actor service and
    CASE_MANAGER participant.  Returns ``(case, case_actor_participant_id)``.
    """
    case = as_VulnerabilityCase(
        attributed_to=owner_actor_id, name="Test Case", content="Content"
    )
    owner_participant = as_CaseParticipant(
        attributed_to=owner_actor_id,
        context=case.id_,
        case_roles=[CVDRole.CASE_OWNER],
    )
    case_actor_participant = as_CaseParticipant(
        attributed_to=case_actor_id,
        context=case.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    case.actor_participant_index[owner_actor_id] = owner_participant.id_
    case.actor_participant_index[case_actor_id] = case_actor_participant.id_
    case.case_participants.append(owner_participant.id_)
    case.case_participants.append(case_actor_participant.id_)
    dl.create(case)
    dl.create(owner_participant)
    dl.create(case_actor_participant)
    return case, case_actor_participant.id_


class TestSvcOfferCaseManagerRoleUseCase:
    """Tests for the offer-case-manager-role trigger use case."""

    def test_offer_creates_activity_and_enqueues_outbox(self):
        """Happy path: offer is created and queued in the Case Actor's outbox."""
        actor, dl = _make_actor_dl("Vendor")
        # Case Actor service uses a deterministic ID pattern.
        case_actor = as_Service(
            id_=f"{actor.id_}/case-actor",
            name="CaseActorService",
        )
        dl.create(case_actor)
        case, _ = _make_case_with_case_actor(dl, actor.id_, case_actor.id_)
        # Wire the case_actor_id via the Service context so _find_case_actor_id
        # resolves it.
        case_actor_with_context = as_Service(
            id_=case_actor.id_,
            name="CaseActorService",
            context=case.id_,
        )
        dl.save(case_actor_with_context)

        request = OfferCaseManagerRoleTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
        )
        result = SvcOfferCaseManagerRoleUseCase(
            dl, request, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        # Activity should be queued in the Case Actor's outbox.
        case_actor_dl = dl.clone_for_actor(case_actor.id_)
        outbox = case_actor_dl.outbox_list()
        assert (
            len(outbox) >= 1
        ), "Offer activity must be in Case Actor's outbox"

        # result["activity"] should be populated via _handle_result.
        assert result.get("activity") is not None
        activity = result["activity"]
        assert activity["type"] == "Offer"
        assert activity["actor"] == case_actor.id_

    def test_offer_raises_when_case_actor_missing(self):
        """VultronNotFoundError when no Case Actor Service exists for the case."""
        actor, dl = _make_actor_dl("Vendor")
        case = as_VulnerabilityCase(
            attributed_to=actor.id_, name="No CaseActor Case", content="..."
        )
        dl.create(case)

        request = OfferCaseManagerRoleTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
        )
        with pytest.raises(VultronNotFoundError):
            SvcOfferCaseManagerRoleUseCase(
                dl, request, trigger_activity=TriggerActivityAdapter(dl)
            ).execute()

    def test_offer_raises_when_case_not_found(self):
        """VultronNotFoundError when the case_id does not exist."""
        actor, dl = _make_actor_dl("Vendor")

        request = OfferCaseManagerRoleTriggerRequest(
            actor_id=actor.id_,
            case_id="https://example.org/cases/no-such-case",
        )
        with pytest.raises(Exception):
            SvcOfferCaseManagerRoleUseCase(
                dl, request, trigger_activity=TriggerActivityAdapter(dl)
            ).execute()

    def test_offer_activity_persisted_in_datalayer(self):
        """Offer activity is readable from the DataLayer after execution."""
        actor, dl = _make_actor_dl("Vendor")
        case_actor = as_Service(
            id_=f"{actor.id_}/case-actor",
            name="CaseActorService",
            context="placeholder",  # will be updated below
        )
        dl.create(case_actor)
        case, _ = _make_case_with_case_actor(dl, actor.id_, case_actor.id_)
        case_actor_with_context = as_Service(
            id_=case_actor.id_,
            name="CaseActorService",
            context=case.id_,
        )
        dl.save(case_actor_with_context)

        request = OfferCaseManagerRoleTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
        )
        result = SvcOfferCaseManagerRoleUseCase(
            dl, request, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        activity_id = result.get("activity", {}).get("id")
        assert activity_id is not None
        stored = dl.read(activity_id)
        assert stored is not None
        assert getattr(stored, "type_", None) == "Offer"
