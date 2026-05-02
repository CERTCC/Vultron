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
Covers SvcInviteActorToCaseUseCase, SvcSuggestActorToCaseUseCase, and
SvcAcceptCaseInviteUseCase.  Includes DR-09 regression tests verifying
that short UUIDs in actor_id are normalised to full URIs before use.
"""

import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.core.use_cases.triggers.actor import (
    SvcAcceptCaseInviteUseCase,
    SvcInviteActorToCaseUseCase,
    SvcSuggestActorToCaseUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptCaseInviteTriggerRequest,
    InviteActorToCaseTriggerRequest,
    SuggestActorToCaseTriggerRequest,
)
from vultron.errors import VultronNotFoundError
from vultron.wire.as2.factories import rm_invite_to_case_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Invite
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    VulnerabilityCase,
    VulnerabilityCaseStub,
)

_BASE = "http://coordinator:7999/api/v2/actors"
_UUID = "24d63c7d-6b1e-4f61-a5e1-180d27192d0b"
_HTTP_ACTOR_ID = f"{_BASE}/{_UUID}"


def _make_actor_dl(actor_name: str):
    """Create an as_Service actor and a per-actor SqliteDataLayer."""
    actor = as_Service(name=actor_name)
    actor_id = actor.id_
    reset_datalayer(actor_id)
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
    dl.clear_all()
    dl.create(actor)
    return actor, dl


def _make_actor_dl_with_http_id(actor_name: str, actor_id: str):
    """Create an actor with an explicit HTTP-style ID (for short-UUID tests)."""
    actor = as_Service(name=actor_name, id_=actor_id)
    reset_datalayer(actor_id)
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
    dl.clear_all()
    dl.create(actor)
    return actor, dl


class TestSvcInviteActorToCaseUseCase:
    """Tests for the invite-actor-to-case trigger use case."""

    def test_invite_creates_activity_and_populates_to(self):
        actor, dl = _make_actor_dl("Coordinator")
        invitee, _ = _make_actor_dl("Finder")

        # Seed invitee and case in actor's DL
        dl.create(invitee)
        case = VulnerabilityCase(
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
        result = SvcInviteActorToCaseUseCase(dl, request).execute()

        assert "activity" in result
        activity_data = result["activity"]
        assert activity_data["type"] == "Invite"
        assert activity_data["actor"] == actor.id_
        assert invitee.id_ in activity_data.get("to", [])

    def test_invite_persisted_in_datalayer(self):
        actor, dl = _make_actor_dl("Coordinator")
        invitee, _ = _make_actor_dl("Finder")
        dl.create(invitee)
        case = VulnerabilityCase(
            attributed_to=actor.id_, name="Test Case", content="Content"
        )
        dl.create(case)

        request = InviteActorToCaseTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            invitee_id=invitee.id_,
        )
        result = SvcInviteActorToCaseUseCase(dl, request).execute()

        invite_id = result["activity"]["id"]
        stored = dl.read(invite_id)
        assert stored is not None
        assert isinstance(stored, as_Invite)

    def test_invite_raises_when_invitee_not_in_dl(self):
        actor, dl = _make_actor_dl("Coordinator")
        # invitee NOT seeded in actor's DL
        missing_id = "https://example.org/actors/nobody"
        case = VulnerabilityCase(
            attributed_to=actor.id_, name="Test Case", content="Content"
        )
        dl.create(case)

        request = InviteActorToCaseTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            invitee_id=missing_id,
        )
        with pytest.raises(VultronNotFoundError):
            SvcInviteActorToCaseUseCase(dl, request).execute()

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
            SvcInviteActorToCaseUseCase(dl, request).execute()

    def test_invite_normalises_short_uuid_actor_id(self):
        """DR-09: short UUID in actor_id is resolved to full URI."""
        actor, dl = _make_actor_dl_with_http_id("Coordinator", _HTTP_ACTOR_ID)
        invitee, _ = _make_actor_dl("Finder")
        dl.create(invitee)
        case = VulnerabilityCase(
            attributed_to=_HTTP_ACTOR_ID, name="Test Case", content="Content"
        )
        dl.create(case)

        # Pass the bare UUID (as the FastAPI router does from the URL path)
        request = InviteActorToCaseTriggerRequest(
            actor_id=_UUID,
            case_id=case.id_,
            invitee_id=invitee.id_,
        )
        result = SvcInviteActorToCaseUseCase(dl, request).execute()

        # Activity actor field must be the full canonical URI, not the short UUID
        assert result["activity"]["actor"] == _HTTP_ACTOR_ID


class TestSvcSuggestActorToCaseUseCase:
    """Tests for the suggest-actor-to-case trigger use case."""

    def test_suggest_creates_activity(self):
        actor, dl = _make_actor_dl("Coordinator")
        suggested, _ = _make_actor_dl("Vendor")
        dl.create(suggested)
        case = VulnerabilityCase(
            attributed_to=actor.id_, name="Test Case", content="Content"
        )
        dl.create(case)

        request = SuggestActorToCaseTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            suggested_actor_id=suggested.id_,
        )
        result = SvcSuggestActorToCaseUseCase(dl, request).execute()

        assert "activity" in result
        assert result["activity"]["actor"] == actor.id_

    def test_suggest_raises_when_suggested_actor_missing(self):
        actor, dl = _make_actor_dl("Coordinator")
        case = VulnerabilityCase(
            attributed_to=actor.id_, name="Test Case", content="Content"
        )
        dl.create(case)

        request = SuggestActorToCaseTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            suggested_actor_id="https://example.org/actors/ghost",
        )
        with pytest.raises(VultronNotFoundError):
            SvcSuggestActorToCaseUseCase(dl, request).execute()

    def test_suggest_normalises_short_uuid_actor_id(self):
        """DR-09: short UUID in actor_id is resolved to full URI."""
        actor, dl = _make_actor_dl_with_http_id("Coordinator", _HTTP_ACTOR_ID)
        suggested, _ = _make_actor_dl("Vendor")
        dl.create(suggested)
        case = VulnerabilityCase(
            attributed_to=_HTTP_ACTOR_ID, name="Test Case", content="Content"
        )
        dl.create(case)

        request = SuggestActorToCaseTriggerRequest(
            actor_id=_UUID,
            case_id=case.id_,
            suggested_actor_id=suggested.id_,
        )
        result = SvcSuggestActorToCaseUseCase(dl, request).execute()

        assert result["activity"]["actor"] == _HTTP_ACTOR_ID


class TestSvcAcceptCaseInviteUseCase:
    """Tests for the accept-case-invite trigger use case."""

    def test_accept_creates_activity(self):
        inviter, dl_inviter = _make_actor_dl("Coordinator")
        invitee, dl_invitee = _make_actor_dl("Finder")
        dl_inviter.create(invitee)

        case = VulnerabilityCase(
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
        result = SvcAcceptCaseInviteUseCase(dl_invitee, request).execute()

        assert "activity" in result
        assert result["activity"]["actor"] == invitee.id_
        assert result["activity"]["inReplyTo"] == invite.id_

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
            SvcAcceptCaseInviteUseCase(dl, request).execute()

    def test_accept_normalises_short_uuid_actor_id(self):
        """DR-09: short UUID in actor_id is resolved to full URI."""
        inviter, dl_inviter = _make_actor_dl("Coordinator")
        invitee, dl_invitee = _make_actor_dl_with_http_id(
            "Finder", _HTTP_ACTOR_ID
        )
        dl_inviter.create(invitee)

        case = VulnerabilityCase(
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
        result = SvcAcceptCaseInviteUseCase(dl_invitee, request).execute()

        assert result["activity"]["actor"] == _HTTP_ACTOR_ID
