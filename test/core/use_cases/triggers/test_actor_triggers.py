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
Covers SvcInviteActorToCaseUseCase (P347-PUPPETEER inline prerequisite).
"""

import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.core.use_cases.triggers.actor import SvcInviteActorToCaseUseCase
from vultron.core.use_cases.triggers.requests import (
    InviteActorToCaseTriggerRequest,
)
from vultron.errors import VultronNotFoundError
from vultron.wire.as2.vocab.activities.case import RmInviteToCaseActivity
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase


def _make_actor_dl(actor_name: str):
    """Create an as_Service actor and a per-actor SqliteDataLayer."""
    actor = as_Service(name=actor_name)
    actor_id = actor.id_
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
        assert isinstance(stored, RmInviteToCaseActivity)

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
