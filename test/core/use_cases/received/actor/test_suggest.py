#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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
"""Tests for actor suggestion received use cases (ADR-0026 CaseActor-routed)."""

import logging
from unittest.mock import MagicMock

import py_trees
import pytest

from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.use_cases.received.actor.suggest import (
    AcceptActorRecommendationReceivedUseCase,
    OfferActorToCaseReceivedUseCase,
    RejectActorRecommendationReceivedUseCase,
)
from vultron.wire.as2.factories import (
    accept_case_participant_offer_activity,
    offer_case_participant_activity,
    recommend_actor_activity,
    reject_case_participant_offer_activity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase


class TestOfferActorToCaseReceivedUseCase:
    """Tests for the CaseActor-inbox Offer(Actor,Case) use case (CM-16)."""

    @pytest.fixture(autouse=True)
    def clear_blackboard(self):
        py_trees.blackboard.Blackboard.storage.clear()
        yield
        py_trees.blackboard.Blackboard.storage.clear()

    def _setup_dl(self, owner_is_local: bool = True):
        """Return DataLayer seeded with a Service actor and a case."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.base.objects.actors import as_Service

        dl = SqliteDataLayer("sqlite:///:memory:")
        local_actor_id = "https://example.org/actors/case-actor"
        local_actor = as_Service(id_=local_actor_id)
        case_id = "https://example.org/cases/offer-actor-test-case"
        owner_id = (
            local_actor_id if owner_is_local else "https://other.org/actor"
        )
        case = VulnerabilityCase(
            id_=case_id,
            name="OfferActorTest",
            attributed_to=owner_id,
        )
        dl.create(local_actor)
        dl.create(case)
        return dl, local_actor_id, case_id

    def test_offer_actor_to_case_emits_offer_case_participant(
        self, make_payload
    ):
        """CaseActor receives Offer(Actor, Case) and emits Offer(CaseParticipant) to owner."""
        from vultron.core.models.events.actor import (
            OfferActorToCaseReceivedEvent,
        )

        dl, local_actor_id, case_id = self._setup_dl()
        recommender_id = "https://example.org/actors/finder"
        recommended_id = "https://example.org/actors/vendor-new"
        recommended = as_Actor(id_=recommended_id)

        # Build Offer(Actor, Case) — the wire activity matched by OFFER_ACTOR_TO_CASE
        activity = recommend_actor_activity(
            recommended,
            target=case_id,
            actor=recommender_id,
            to=[local_actor_id],
        )
        event = make_payload(activity)
        assert isinstance(
            event, OfferActorToCaseReceivedEvent
        ), f"Expected OfferActorToCaseReceivedEvent, got {type(event)}"

        OfferActorToCaseReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        outbox = dl.outbox_list_for_actor(local_actor_id)
        assert (
            len(outbox) >= 1
        ), f"Expected at least 1 outbox entry (Offer(CaseParticipant)), got {len(outbox)}"

    def test_offer_actor_to_case_skips_when_no_local_actor(
        self, make_payload, caplog
    ):
        """Skips gracefully when no local actor is found in DataLayer."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer("sqlite:///:memory:")
        recommended = as_Actor(id_="https://example.org/actors/vendor-new")
        activity = recommend_actor_activity(
            recommended,
            target="https://example.org/cases/no-actor-case",
            actor="https://example.org/actors/finder",
            id_="https://example.org/activities/offer-actor-002",
        )
        event = make_payload(activity)

        with caplog.at_level(logging.WARNING):
            OfferActorToCaseReceivedUseCase(dl, event).execute()

        assert any(
            "no local actor" in r.message.lower() for r in caplog.records
        )

    def test_offer_actor_to_case_skips_missing_recommended_id(self, caplog):
        """Skips gracefully when recommended_id is missing from the event."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer("sqlite:///:memory:")
        # Build an activity with no object (can't in wire layer, so mock the event)
        mock_event = MagicMock()
        mock_event.activity_id = "https://example.org/activities/bad-offer"
        mock_event.actor_id = "https://example.org/actors/finder"
        mock_event.object_id = None
        mock_event.target_id = "https://example.org/cases/some-case"
        mock_event.activity = None

        with caplog.at_level(logging.WARNING):
            OfferActorToCaseReceivedUseCase(dl, mock_event).execute()

        assert any("missing" in r.message.lower() for r in caplog.records)


def _build_accept_reject_dl():
    """Seed a DataLayer with a CaseActor (Service), a VulnerabilityCase, and a stored recommendation.

    The recommendation is stored so that AcceptActorRecommendationReceivedUseCase and
    RejectActorRecommendationReceivedUseCase can resolve recommender_id via dl.read().
    """
    from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
    from vultron.wire.as2.vocab.base.objects.actors import as_Service

    dl = SqliteDataLayer("sqlite:///:memory:")
    local_actor_id = "https://example.org/actors/case-actor"
    case_id = "https://example.org/cases/rec-accept-reject-case"
    owner_id = "https://example.org/actors/owner"
    recommender_id = "https://example.org/actors/recommender"
    dl.create(as_Service(id_=local_actor_id))
    dl.create(
        VulnerabilityCase(
            id_=case_id,
            name="AcceptRejectTest",
            attributed_to=owner_id,
        )
    )
    # Store the original recommendation so the use cases can resolve recommender_id.
    recommendation = recommend_actor_activity(
        as_Actor(id_="https://example.org/actors/vendor-placeholder"),
        target=case_id,
        actor=recommender_id,
        id_="https://example.org/activities/orig-recommendation",
    )
    dl.create(recommendation)
    return dl, local_actor_id, case_id, owner_id, recommender_id


class TestAcceptActorRecommendationReceivedUseCase:
    """execute() unit tests for AcceptActorRecommendationReceivedUseCase (CM-16-006, ADR-0026)."""

    @pytest.fixture(autouse=True)
    def clear_blackboard(self):
        py_trees.blackboard.Blackboard.storage.clear()
        yield
        py_trees.blackboard.Blackboard.storage.clear()

    def _build_event(self, make_payload, case_id, owner_id, recommended_id):
        """Build Accept(Offer(CaseParticipant, Case)) and extract the domain event."""
        from vultron.core.models.events.actor import (
            AcceptActorRecommendationReceivedEvent,
        )

        recommended = as_Actor(id_=recommended_id)
        inner_offer = offer_case_participant_activity(
            recommended,
            target=case_id,
            actor="https://example.org/actors/case-actor",
            origin="https://example.org/activities/orig-recommendation",
        )
        activity = accept_case_participant_offer_activity(
            inner_offer,
            target=case_id,
            actor=owner_id,
        )
        event = make_payload(activity)
        assert isinstance(
            event, AcceptActorRecommendationReceivedEvent
        ), f"Expected AcceptActorRecommendationReceivedEvent, got {type(event)}"
        return event

    def test_happy_path_emits_accept_and_invite(self, make_payload):
        """Happy path: tree runs and outbox receives Accept notification + Invite."""
        dl, local_actor_id, case_id, owner_id, _recommender_id = (
            _build_accept_reject_dl()
        )
        recommended_id = "https://example.org/actors/vendor-new"
        event = self._build_event(
            make_payload, case_id, owner_id, recommended_id
        )

        AcceptActorRecommendationReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        outbox = dl.outbox_list_for_actor(local_actor_id)
        assert (
            len(outbox) >= 2
        ), f"Expected ≥2 outbox entries (Accept notification + Invite), got {len(outbox)}"

    def test_skips_when_case_id_missing(self, caplog):
        """Logs a warning and returns early when case_id is absent."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer("sqlite:///:memory:")
        mock_event = MagicMock()
        mock_event.activity_id = "https://example.org/activities/accept-bad"
        mock_event.target_id = None
        mock_event.activity = None

        with caplog.at_level(logging.WARNING):
            AcceptActorRecommendationReceivedUseCase(dl, mock_event).execute()

        assert any("missing" in r.message.lower() for r in caplog.records)

    def test_skips_when_no_local_actor(self, make_payload, caplog):
        """Logs a warning and returns early when no local actor exists in DataLayer."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer("sqlite:///:memory:")
        case_id = "https://example.org/cases/no-actor-case"
        owner_id = "https://example.org/actors/owner"
        recommended_id = "https://example.org/actors/vendor-new"
        event = self._build_event(
            make_payload, case_id, owner_id, recommended_id
        )

        with caplog.at_level(logging.WARNING):
            AcceptActorRecommendationReceivedUseCase(dl, event).execute()

        assert any(
            "no local actor" in r.message.lower() for r in caplog.records
        )


class TestRejectActorRecommendationReceivedUseCase:
    """execute() unit tests for RejectActorRecommendationReceivedUseCase (CM-16-007, ADR-0026)."""

    @pytest.fixture(autouse=True)
    def clear_blackboard(self):
        py_trees.blackboard.Blackboard.storage.clear()
        yield
        py_trees.blackboard.Blackboard.storage.clear()

    def _build_event(self, make_payload, case_id, owner_id, recommended_id):
        """Build Reject(Offer(CaseParticipant, Case)) and extract the domain event."""
        from vultron.core.models.events.actor import (
            RejectActorRecommendationReceivedEvent,
        )

        recommended = as_Actor(id_=recommended_id)
        inner_offer = offer_case_participant_activity(
            recommended,
            target=case_id,
            actor="https://example.org/actors/case-actor",
            origin="https://example.org/activities/orig-recommendation",
        )
        activity = reject_case_participant_offer_activity(
            inner_offer,
            target=case_id,
            actor=owner_id,
        )
        event = make_payload(activity)
        assert isinstance(
            event, RejectActorRecommendationReceivedEvent
        ), f"Expected RejectActorRecommendationReceivedEvent, got {type(event)}"
        return event

    def test_happy_path_emits_reject_notification(self, make_payload):
        """Happy path: tree runs and outbox receives Reject notification."""
        dl, local_actor_id, case_id, owner_id, _recommender_id = (
            _build_accept_reject_dl()
        )
        recommended_id = "https://example.org/actors/vendor-rejected"
        event = self._build_event(
            make_payload, case_id, owner_id, recommended_id
        )

        RejectActorRecommendationReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        outbox = dl.outbox_list_for_actor(local_actor_id)
        assert (
            len(outbox) >= 1
        ), f"Expected ≥1 outbox entry after reject, got {len(outbox)}"

    def test_skips_when_case_id_missing(self, caplog):
        """Logs a warning and returns early when case_id is absent."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer("sqlite:///:memory:")
        mock_event = MagicMock()
        mock_event.activity_id = "https://example.org/activities/reject-bad"
        mock_event.target_id = None
        mock_event.activity = None
        mock_event.object_id = None

        with caplog.at_level(logging.WARNING):
            RejectActorRecommendationReceivedUseCase(dl, mock_event).execute()

        assert any("missing" in r.message.lower() for r in caplog.records)

    def test_skips_when_no_local_actor(self, make_payload, caplog):
        """Logs a warning and returns early when no local actor exists in DataLayer."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer("sqlite:///:memory:")
        case_id = "https://example.org/cases/no-actor-reject-case"
        owner_id = "https://example.org/actors/owner"
        recommended_id = "https://example.org/actors/vendor-new"
        event = self._build_event(
            make_payload, case_id, owner_id, recommended_id
        )

        with caplog.at_level(logging.WARNING):
            RejectActorRecommendationReceivedUseCase(dl, event).execute()

        assert any(
            "no local actor" in r.message.lower() for r in caplog.records
        )
