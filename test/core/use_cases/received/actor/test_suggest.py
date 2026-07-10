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
"""Tests for actor suggestion received use cases (ADR-0026 CaseActor-routed).

Covers:
- OfferActorToCaseReceivedUseCase (new CaseActor-inbox path, CM-16)
- Legacy stub use cases: SuggestActorToCaseReceivedUseCase (drop + warn),
  AcceptSuggestActorToCaseReceivedUseCase, RejectSuggestActorToCaseReceivedUseCase
"""

import logging
from unittest.mock import MagicMock

import py_trees
import pytest

from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.use_cases.received.actor.suggest import (
    AcceptSuggestActorToCaseReceivedUseCase,
    OfferActorToCaseReceivedUseCase,
    RejectSuggestActorToCaseReceivedUseCase,
    SuggestActorToCaseReceivedUseCase,
)
from vultron.wire.as2.factories import (
    accept_actor_recommendation_activity,
    offer_case_participant_activity,
    recommend_actor_activity,
    reject_actor_recommendation_activity,
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

        # Build Offer(CaseParticipant) — the wire activity matched by OFFER_ACTOR_TO_CASE
        activity = offer_case_participant_activity(
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


class TestLegacySuggestActorUseCases:
    """Tests for legacy pre-ADR-0026 stub use cases — all drop and warn."""

    def test_suggest_actor_to_case_logs_warning(self, make_payload, caplog):
        """SuggestActorToCaseReceivedUseCase (legacy) drops activity with warning."""
        coordinator = as_Actor(id_="https://example.org/users/coordinator")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_sa1",
            name="SA Case 1",
        )
        activity = recommend_actor_activity(
            coordinator,
            target=case,
            actor="https://example.org/users/finder",
        )
        event = make_payload(activity)

        with caplog.at_level(logging.WARNING):
            SuggestActorToCaseReceivedUseCase(MagicMock(), event).execute()

        assert any(
            "legacy" in r.message.lower() or "dropped" in r.message.lower()
            for r in caplog.records
        )

    def test_suggest_actor_to_case_no_outbox(self, make_payload):
        """SuggestActorToCaseReceivedUseCase (legacy) does not write to outbox."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer("sqlite:///:memory:")
        coordinator = as_Actor(id_="https://example.org/users/coordinator")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_sa2",
            name="SA Case 2",
        )
        activity = recommend_actor_activity(
            coordinator,
            target=case,
            actor="https://example.org/users/finder",
        )
        event = make_payload(activity)

        SuggestActorToCaseReceivedUseCase(dl, event).execute()

        assert len(dl.outbox_list()) == 0

    def test_accept_suggest_actor_to_case_logs_warning(
        self, make_payload, caplog
    ):
        """AcceptSuggestActorToCaseReceivedUseCase (legacy) drops with warning."""
        coordinator = as_Actor(id_="https://example.org/users/coordinator")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_sa3",
            name="SA Case 3",
        )
        recommendation = recommend_actor_activity(
            coordinator,
            target=case,
            actor="https://example.org/users/finder",
        )
        activity = accept_actor_recommendation_activity(
            recommendation,
            target=case,
            actor="https://example.org/users/vendor",
        )
        event = make_payload(activity)

        with caplog.at_level(logging.WARNING):
            AcceptSuggestActorToCaseReceivedUseCase(
                MagicMock(), event
            ).execute()

        assert any(
            "legacy" in r.message.lower() or "dropped" in r.message.lower()
            for r in caplog.records
        )

    def test_reject_suggest_actor_to_case_logs_warning(
        self, make_payload, caplog
    ):
        """RejectSuggestActorToCaseReceivedUseCase (legacy) drops with warning."""
        coordinator = as_Actor(id_="https://example.org/users/coordinator")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_sa4",
            name="SA Case 4",
        )
        recommendation = recommend_actor_activity(
            coordinator,
            target=case,
            actor="https://example.org/users/finder",
        )
        activity = reject_actor_recommendation_activity(
            recommendation,
            target=case,
            actor="https://example.org/users/vendor",
        )
        event = make_payload(activity)

        with caplog.at_level(logging.WARNING):
            RejectSuggestActorToCaseReceivedUseCase(
                MagicMock(), event
            ).execute()

        assert any(
            "legacy" in r.message.lower() or "dropped" in r.message.lower()
            for r in caplog.records
        )
