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
"""Tests for actor suggestion received use cases."""

import logging
from typing import Any, cast
from unittest.mock import MagicMock

import py_trees
import pytest

from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.use_cases.received.actor.suggest import (
    AcceptSuggestActorToCaseReceivedUseCase,
    RejectSuggestActorToCaseReceivedUseCase,
    SuggestActorToCaseReceivedUseCase,
)
from vultron.wire.as2.factories import (
    accept_actor_recommendation_activity,
    recommend_actor_activity,
    reject_actor_recommendation_activity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    VulnerabilityCase,
)


class TestSuggestActorUseCases:
    """Tests for suggest_actor_to_case, accept/reject suggest_actor use cases."""

    def test_suggest_actor_to_case_persists_recommendation(
        self, monkeypatch, make_payload
    ):
        """SuggestActorToCaseReceivedUseCase persists the RecommendActor offer."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.base.objects.actors import as_Actor

        dl = SqliteDataLayer("sqlite:///:memory:")

        coordinator = as_Actor(id_="https://example.org/users/coordinator")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_sa1",
            name="SA Case 1",
        )
        activity = recommend_actor_activity(
            coordinator,
            target=case,
            actor="https://example.org/users/finder",
            to="https://example.org/users/vendor",
        )

        event = make_payload(activity)

        SuggestActorToCaseReceivedUseCase(dl, event).execute()

        stored = dl.get(activity.type_.value, activity.id_)
        assert stored is not None

    def test_suggest_actor_to_case_idempotent(self, monkeypatch, make_payload):
        """SuggestActorToCaseReceivedUseCase is idempotent — second call is a no-op."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.base.objects.actors import as_Actor

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
        SuggestActorToCaseReceivedUseCase(dl, event).execute()

        stored = dl.get(activity.type_.value, activity.id_)
        assert stored is not None

    def test_accept_suggest_actor_to_case_persists_acceptance(
        self, monkeypatch, make_payload
    ):
        """AcceptSuggestActorToCaseReceivedUseCase persists the AcceptActorRecommendation."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.base.objects.actors import as_Actor

        dl = SqliteDataLayer("sqlite:///:memory:")

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

        AcceptSuggestActorToCaseReceivedUseCase(dl, event).execute()

        stored = dl.get(activity.type_.value, activity.id_)
        assert stored is not None

    def test_reject_suggest_actor_to_case_ledgers_rejection(
        self, monkeypatch, caplog, make_payload
    ):
        """RejectSuggestActorToCaseReceivedUseCase logs rejection without state change."""
        from vultron.wire.as2.vocab.base.objects.actors import as_Actor

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

        with caplog.at_level(logging.INFO):
            RejectSuggestActorToCaseReceivedUseCase(
                MagicMock(), event
            ).execute()

        assert any("rejected" in r.message.lower() for r in caplog.records)

    @pytest.fixture(autouse=True)
    def clear_blackboard(self):
        py_trees.blackboard.Blackboard.storage.clear()
        yield
        py_trees.blackboard.Blackboard.storage.clear()

    def _setup_dl_with_owner(self):
        """Return a DataLayer seeded with a local Service actor and a case."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.base.objects.actors import as_Service

        dl = SqliteDataLayer("sqlite:///:memory:")
        local_actor_id = "https://example.org/actors/local-coordinator"
        local_actor = as_Service(id_=local_actor_id)
        case_id = "https://example.org/cases/suggest-test-case"
        case = VulnerabilityCase(
            id_=case_id,
            name="SUGGEST-TEST",
            attributed_to=local_actor_id,
        )
        dl.create(local_actor)
        dl.create(case)
        return dl, local_actor_id, case_id

    def test_suggest_actor_emits_both_activities_when_owner(
        self, make_payload
    ):
        """Owner emits Accept + Invite when receiving a recommendation."""
        dl, local_actor_id, case_id = self._setup_dl_with_owner()
        recommender_id = "https://example.org/actors/finder"
        invitee_id = "https://example.org/actors/vendor"
        invitee = as_Actor(id_=invitee_id)

        recommendation = recommend_actor_activity(
            invitee,
            target=case_id,
            actor=recommender_id,
            to=[local_actor_id],
            id_="https://example.org/activities/rec-001",
        )
        event = make_payload(recommendation)

        SuggestActorToCaseReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        outbox = dl.outbox_list()
        assert (
            len(outbox) == 2
        ), f"Expected 2 outbox entries (Accept + Invite), got {len(outbox)}"

    def test_suggest_actor_skips_when_not_case_owner(self, make_payload):
        """Non-owner silently skips — no outbox entries emitted."""
        dl, local_actor_id, case_id = self._setup_dl_with_owner()
        # Override case with a different owner
        case = dl.read(case_id)
        other_owner = "https://example.org/actors/other-owner"
        case = cast(Any, case)
        case = case.model_copy(update={"attributed_to": other_owner})
        dl.save(case)

        recommender_id = "https://example.org/actors/finder"
        invitee_id = "https://example.org/actors/vendor"
        invitee = as_Actor(id_=invitee_id)

        recommendation = recommend_actor_activity(
            invitee,
            target=case_id,
            actor=recommender_id,
            to=[local_actor_id],
            id_="https://example.org/activities/rec-002",
        )
        event = make_payload(recommendation)

        SuggestActorToCaseReceivedUseCase(dl, event).execute()

        outbox = dl.outbox_list()
        assert len(outbox) == 0, (
            "Expected no outbox entries for non-owner, " f"got {len(outbox)}"
        )

    def test_suggest_actor_idempotent_when_invite_exists(self, make_payload):
        """Second execute() adds no new outbox entries."""
        dl, local_actor_id, case_id = self._setup_dl_with_owner()
        recommender_id = "https://example.org/actors/finder"
        invitee_id = "https://example.org/actors/vendor"
        invitee = as_Actor(id_=invitee_id)

        recommendation = recommend_actor_activity(
            invitee,
            target=case_id,
            actor=recommender_id,
            to=[local_actor_id],
            id_="https://example.org/activities/rec-003",
        )
        event = make_payload(recommendation)

        # First execution
        SuggestActorToCaseReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()
        outbox_after_first = len(dl.outbox_list())

        # Second execution (should be a no-op)
        py_trees.blackboard.Blackboard.storage.clear()
        SuggestActorToCaseReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()
        outbox_after_second = len(dl.outbox_list())

        assert (
            outbox_after_first == 2
        ), f"Expected 2 entries after first run, got {outbox_after_first}"
        assert outbox_after_second == outbox_after_first, (
            "Expected no new entries on second run (idempotency), "
            f"got {outbox_after_second - outbox_after_first} extra"
        )
