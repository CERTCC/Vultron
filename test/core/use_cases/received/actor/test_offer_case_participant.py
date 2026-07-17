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
"""Tests for Offer(CaseParticipant) round-trip received use cases (ISSUE-1332).

Covers:
- OfferCaseParticipantReceivedUseCase (Case Owner inbox)
- AcceptOfferCaseParticipantReceivedUseCase (CaseActor inbox)
- RejectOfferCaseParticipantReceivedUseCase (CaseActor inbox)
- TestAcceptOfferCaseParticipantRolesThreading (AC-1/AC-2, ISSUE-1406)
"""

import logging
from typing import Any, cast
from unittest.mock import MagicMock

import py_trees
import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.models.events.actor import (
    AcceptOfferCaseParticipantReceivedEvent,
    OfferCaseParticipantReceivedEvent,
    RejectOfferCaseParticipantReceivedEvent,
)
from vultron.core.use_cases.received.actor.offer_case_participant import (
    AcceptOfferCaseParticipantReceivedUseCase,
    OfferCaseParticipantReceivedUseCase,
    RejectOfferCaseParticipantReceivedUseCase,
)
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import (
    accept_case_participant_offer_activity,
    offer_case_participant_activity,
    reject_case_participant_offer_activity,
    rm_accept_invite_to_case_activity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor, as_Service
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

CASE_ID = "https://example.org/cases/offer-round-trip-case"
CASE_ACTOR_ID = "https://example.org/actors/case-actor"
CASE_OWNER_ID = "https://example.org/actors/case-owner"
RECOMMENDER_ID = "https://example.org/actors/finder"
RECOMMENDED_ID = "https://example.org/actors/vendor-new"


def _seed_dl_for_case_owner() -> tuple[SqliteDataLayer, str]:
    """DataLayer seeded with a Case Owner actor and a case.

    The Case Owner is the local actor that receives Offer(CaseParticipant)
    from the CaseActor.
    """
    dl = SqliteDataLayer("sqlite:///:memory:")
    owner_actor = as_Actor(id_=CASE_OWNER_ID)
    case = as_VulnerabilityCase(
        id_=CASE_ID,
        name="OfferRoundTripTest",
        attributed_to=CASE_OWNER_ID,
    )
    dl.create(owner_actor)  # type: ignore[arg-type]
    dl.create(case)
    return dl, CASE_OWNER_ID


def _seed_dl_for_case_actor() -> tuple[SqliteDataLayer, str]:
    """DataLayer seeded with a CaseActor Service and a case.

    The CaseActor is the local actor that receives Accept/Reject from the
    Case Owner.
    """
    dl = SqliteDataLayer("sqlite:///:memory:")
    case_actor = as_Service(id_=CASE_ACTOR_ID)
    case = as_VulnerabilityCase(
        id_=CASE_ID,
        name="OfferRoundTripTest",
        attributed_to=CASE_OWNER_ID,
    )
    dl.create(case_actor)
    dl.create(case)
    return dl, CASE_ACTOR_ID


def _build_offer_activity(
    actor: str = CASE_ACTOR_ID,
    to: list[str] | None = None,
):
    recommended = as_Actor(id_=RECOMMENDED_ID)
    return offer_case_participant_activity(
        recommended,
        target=CASE_ID,
        actor=actor,
        to=to or [CASE_OWNER_ID],
        origin="https://example.org/activities/orig-offer-001",
    )


# ---------------------------------------------------------------------------
# OfferCaseParticipantReceivedUseCase (Case Owner inbox)
# ---------------------------------------------------------------------------


class TestOfferCaseParticipantReceivedUseCase:
    @pytest.fixture(autouse=True)
    def clear_blackboard(self):
        py_trees.blackboard.Blackboard.storage.clear()
        yield
        py_trees.blackboard.Blackboard.storage.clear()

    def _event(self) -> OfferCaseParticipantReceivedEvent:
        activity = _build_offer_activity()
        return cast(OfferCaseParticipantReceivedEvent, extract_event(activity))

    def test_executes_without_error(self):
        dl, _ = _seed_dl_for_case_owner()
        event = self._event()
        # Should not raise
        OfferCaseParticipantReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

    def test_skips_when_no_local_actor(self, caplog):
        dl = SqliteDataLayer("sqlite:///:memory:")
        event = self._event()
        with caplog.at_level(logging.WARNING):
            OfferCaseParticipantReceivedUseCase(dl, event).execute()
        assert any(
            "no local actor" in r.message.lower() for r in caplog.records
        )

    def test_skips_when_missing_case_id(self, caplog):
        dl, _ = _seed_dl_for_case_owner()
        mock_event = MagicMock()
        mock_event.activity_id = "https://example.org/activities/bad"
        mock_event.target_id = None
        mock_event.activity = None
        with caplog.at_level(logging.WARNING):
            OfferCaseParticipantReceivedUseCase(dl, mock_event).execute()
        assert any("missing" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# AcceptOfferCaseParticipantReceivedUseCase (CaseActor inbox)
# ---------------------------------------------------------------------------


class TestAcceptOfferCaseParticipantReceivedUseCase:
    @pytest.fixture(autouse=True)
    def clear_blackboard(self):
        py_trees.blackboard.Blackboard.storage.clear()
        yield
        py_trees.blackboard.Blackboard.storage.clear()

    def _event(self) -> AcceptOfferCaseParticipantReceivedEvent:
        offer = _build_offer_activity()
        accept = accept_case_participant_offer_activity(
            offer,
            target=CASE_ID,
            actor=CASE_OWNER_ID,
            to=[CASE_ACTOR_ID],
        )
        return cast(
            AcceptOfferCaseParticipantReceivedEvent, extract_event(accept)
        )

    def test_executes_without_error(self):
        dl, _ = _seed_dl_for_case_actor()
        event = self._event()
        AcceptOfferCaseParticipantReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

    def test_skips_when_no_local_actor(self, caplog):
        dl = SqliteDataLayer("sqlite:///:memory:")
        event = self._event()
        with caplog.at_level(logging.WARNING):
            AcceptOfferCaseParticipantReceivedUseCase(dl, event).execute()
        assert any(
            "no local actor" in r.message.lower() for r in caplog.records
        )

    def test_skips_when_missing_case_id(self, caplog):
        dl, _ = _seed_dl_for_case_actor()
        mock_event = MagicMock()
        mock_event.activity_id = "https://example.org/activities/bad-accept"
        mock_event.target_id = None
        mock_event.activity = None
        with caplog.at_level(logging.WARNING):
            AcceptOfferCaseParticipantReceivedUseCase(dl, mock_event).execute()
        assert any("missing" in r.message.lower() for r in caplog.records)

    def test_skips_when_missing_invitee_id(self, caplog):
        dl, _ = _seed_dl_for_case_actor()
        mock_event = MagicMock()
        mock_event.activity_id = "https://example.org/activities/bad-accept-2"
        mock_event.target_id = CASE_ID
        mock_event.activity = MagicMock()
        # object_ has no attributed_to → invitee_id will be None
        inner_offer = MagicMock()
        inner_offer.object_ = MagicMock(attributed_to=None)
        inner_offer.origin = None
        mock_event.activity.object_ = inner_offer
        with caplog.at_level(logging.WARNING):
            AcceptOfferCaseParticipantReceivedUseCase(dl, mock_event).execute()
        assert any("missing" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# RejectOfferCaseParticipantReceivedUseCase (CaseActor inbox)
# ---------------------------------------------------------------------------


class TestRejectOfferCaseParticipantReceivedUseCase:
    @pytest.fixture(autouse=True)
    def clear_blackboard(self):
        py_trees.blackboard.Blackboard.storage.clear()
        yield
        py_trees.blackboard.Blackboard.storage.clear()

    def _event(self) -> RejectOfferCaseParticipantReceivedEvent:
        offer = _build_offer_activity()
        reject = reject_case_participant_offer_activity(
            offer,
            target=CASE_ID,
            actor=CASE_OWNER_ID,
            to=[CASE_ACTOR_ID],
        )
        return cast(
            RejectOfferCaseParticipantReceivedEvent, extract_event(reject)
        )

    def test_executes_without_error(self):
        dl, _ = _seed_dl_for_case_actor()
        event = self._event()
        RejectOfferCaseParticipantReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

    def test_skips_when_no_local_actor(self, caplog):
        dl = SqliteDataLayer("sqlite:///:memory:")
        event = self._event()
        with caplog.at_level(logging.WARNING):
            RejectOfferCaseParticipantReceivedUseCase(dl, event).execute()
        assert any(
            "no local actor" in r.message.lower() for r in caplog.records
        )

    def test_skips_when_missing_case_id(self, caplog):
        dl, _ = _seed_dl_for_case_actor()
        mock_event = MagicMock()
        mock_event.activity_id = "https://example.org/activities/bad-reject"
        mock_event.target_id = None
        mock_event.activity = None
        with caplog.at_level(logging.WARNING):
            RejectOfferCaseParticipantReceivedUseCase(dl, mock_event).execute()
        assert any("missing" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# AC-1/AC-2: suggest-actor roles threading (ISSUE-1406)
# ---------------------------------------------------------------------------

AC1_CASE_ID = "https://example.org/cases/ac1-roles-threading"
AC1_CASE_ACTOR_ID = "https://example.org/actors/ac1-case-actor"
AC1_CASE_OWNER_ID = "https://example.org/actors/ac1-case-owner"
AC1_INVITEE_ID = "https://example.org/actors/ac1-vendor"


def _seed_dl_for_ac1() -> SqliteDataLayer:
    """DataLayer seeded for the full suggest-actor roles-threading round-trip.

    The CaseActor Service has ``context=AC1_CASE_ID`` so that
    ``_find_case_actor_id()`` resolves correctly when
    ``AcceptInviteActorToCaseReceivedUseCase`` runs.
    """
    from vultron.wire.as2.vocab.base.objects.actors import as_Organization

    dl = SqliteDataLayer("sqlite:///:memory:")
    case_actor = as_Service(id_=AC1_CASE_ACTOR_ID, context=AC1_CASE_ID)
    case = as_VulnerabilityCase(
        id_=AC1_CASE_ID,
        name="AC1RolesThreading",
        attributed_to=AC1_CASE_OWNER_ID,
    )
    invitee = as_Organization(id_=AC1_INVITEE_ID)
    dl.create(case_actor)
    dl.create(case)
    dl.create(invitee)
    return dl


class TestAcceptOfferCaseParticipantRolesThreading:
    """AC-1/AC-2 (ISSUE-1406): roles threading through suggest-actor received path.

    AC-1: Full round-trip — Accept(Offer(CaseParticipant[roles])) →
          EmitInviteActorToCaseNode (roles=None, no blackboard key) →
          Invite(roles=None) stored → Accept(Invite) →
          VultronParticipant.case_roles == [].

    AC-2: Confirm that EmitInviteActorToCaseNode with no ``suggested_roles``
          blackboard key passes roles=None to invite_actor_to_case(), verifying
          no silent default substitution (ADR-0032 BT-HELPER-01).
    """

    @pytest.fixture(autouse=True)
    def clear_blackboard(self):
        py_trees.blackboard.Blackboard.storage.clear()
        yield
        py_trees.blackboard.Blackboard.storage.clear()

    def _build_accept_offer_event(
        self,
    ) -> AcceptOfferCaseParticipantReceivedEvent:
        from vultron.enums.roles import CVDRole

        recommended = as_Actor(id_=AC1_INVITEE_ID)
        offer = offer_case_participant_activity(
            recommended,
            target=AC1_CASE_ID,
            actor=AC1_CASE_ACTOR_ID,
            to=[AC1_CASE_OWNER_ID],
            roles=[CVDRole.VENDOR],
        )
        accept = accept_case_participant_offer_activity(
            offer,
            target=AC1_CASE_ID,
            actor=AC1_CASE_OWNER_ID,
            to=[AC1_CASE_ACTOR_ID],
        )
        return cast(
            AcceptOfferCaseParticipantReceivedEvent, extract_event(accept)
        )

    def test_invite_roles_none_when_no_blackboard_key(self):
        """AC-2: EmitInviteActorToCaseNode passes roles=None to factory.

        When Accept(Offer(CaseParticipant)) arrives, ``suggested_roles`` is
        absent from the blackboard (``create_accept_actor_recommendation_received_tree``
        does not write it).  ``EmitInviteActorToCaseNode._read_suggested_roles()``
        returns None, and the stored Invite has roles=None — no silent default
        substitution (ADR-0032, BT-HELPER-01).
        """
        dl = _seed_dl_for_ac1()
        event = self._build_accept_offer_event()
        AcceptOfferCaseParticipantReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        outbox = dl.outbox_list_for_actor(AC1_CASE_ACTOR_ID)
        invite_obj = None
        for act_id in outbox:
            obj = dl.read(act_id)
            if obj is not None and str(getattr(obj, "type_", "")) == "Invite":
                invite_obj = obj
                break

        assert (
            invite_obj is not None
        ), "Invite must be stored in CaseActor outbox"
        assert getattr(invite_obj, "roles", "sentinel") is None, (
            "AC-2: EmitInviteActorToCaseNode must pass roles=None when "
            "suggested_roles is absent from blackboard (no default substitution)"
        )

    def test_participant_case_roles_empty_after_full_round_trip(self):
        """AC-1: Full suggest-actor round-trip ends with participant.case_roles==[].

        Roles from Accept(Offer(CaseParticipant[VENDOR])) are NOT threaded into
        the Invite when ``suggested_roles`` is absent from the blackboard.
        The resulting participant is created with an empty case_roles list.
        """
        from vultron.core.use_cases.received.actor.invite import (
            AcceptInviteActorToCaseReceivedUseCase,
        )

        dl = _seed_dl_for_ac1()
        event = self._build_accept_offer_event()

        # Step 1: CaseActor receives Accept(Offer(CaseParticipant)) → emits Invite
        AcceptOfferCaseParticipantReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        # Step 2: find the stored Invite
        outbox = dl.outbox_list_for_actor(AC1_CASE_ACTOR_ID)
        invite_obj = None
        for act_id in outbox:
            obj = dl.read(act_id)
            if obj is not None and str(getattr(obj, "type_", "")) == "Invite":
                invite_obj = obj
                break
        assert (
            invite_obj is not None
        ), "Invite must be present in CaseActor outbox"

        # Step 3: invitee sends Accept(Invite) — BT creates VultronParticipant
        py_trees.blackboard.Blackboard.storage.clear()
        from vultron.core.models.events.actor import (
            AcceptInviteActorToCaseReceivedEvent,
        )
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Invite,
        )

        accept_invite = rm_accept_invite_to_case_activity(
            cast(as_Invite, invite_obj), actor=AC1_INVITEE_ID
        )
        accept_invite_event = cast(
            AcceptInviteActorToCaseReceivedEvent, extract_event(accept_invite)
        )
        AcceptInviteActorToCaseReceivedUseCase(
            dl, accept_invite_event, sync_port=MagicMock()
        ).execute()

        # Step 4: assert participant.case_roles == []
        reloaded_case = cast(Any, dl.read(AC1_CASE_ID))
        participant_id = reloaded_case.actor_participant_index.get(
            AC1_INVITEE_ID
        )
        assert (
            participant_id is not None
        ), "Invitee must be registered as participant"
        participant = cast(Any, dl.get(id_=participant_id))
        assert participant is not None
        assert participant.case_roles == [], (
            "AC-1: participant.case_roles must be [] when roles were not "
            "threaded from CaseParticipant offer (suggested_roles absent)"
        )
