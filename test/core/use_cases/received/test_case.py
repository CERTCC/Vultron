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
"""Tests for case-related use-case classes."""

import logging
from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.base import VultronObject
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.activity import VultronActivity
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.case import (
    DeferCaseReceivedEvent,
    EngageCaseReceivedEvent,
)
from vultron.core.use_cases.received.case import (
    DeferCaseReceivedUseCase,
    EngageCaseReceivedUseCase,
    UpdateCaseReceivedUseCase,
)
from vultron.wire.as2.rehydration import rehydrate as real_rehydrate
from vultron.wire.as2.vocab.activities.case import UpdateCaseActivity
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase


class TestCaseUseCases:
    """Tests for update_case handler."""

    def test_update_case_applies_scalar_updates(
        self, monkeypatch, caplog, make_payload
    ):
        """update_case applies name/summary/content updates from a full object."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        owner_id = "https://example.org/users/owner"
        case = VulnerabilityCase(
            id_="https://example.org/cases/uc1",
            name="Original Name",
            attributed_to=owner_id,
        )
        dl.create(case)

        updated_case = VulnerabilityCase(
            id_=case.id_,
            name="Updated Name",
            content="New content",
            attributed_to=owner_id,
        )
        activity = UpdateCaseActivity(
            actor=owner_id,
            object_=updated_case,
        )
        event = make_payload(activity)

        def _mock_rehydrate_applies(obj, **kwargs):
            if obj == case.id_:
                return updated_case
            return real_rehydrate(obj, **kwargs)

        monkeypatch.setattr(
            "vultron.wire.as2.rehydration.rehydrate",
            _mock_rehydrate_applies,
        )

        with caplog.at_level(logging.INFO):
            UpdateCaseReceivedUseCase(dl, event).execute()

        stored = dl.read(case.id_)
        assert stored is not None
        stored = cast(VulnerabilityCase, stored)
        assert stored.name == "Updated Name"
        assert stored.content == "New content"

    def test_update_case_rejects_non_owner(
        self, monkeypatch, caplog, make_payload
    ):
        """update_case logs a warning and skips if actor is not the case owner."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        owner_id = "https://example.org/users/owner"
        non_owner_id = "https://example.org/users/other"
        case = VulnerabilityCase(
            id_="https://example.org/cases/uc2",
            name="Original Name",
            attributed_to=owner_id,
        )
        dl.create(case)

        updated_case = VulnerabilityCase(
            id_=case.id_,
            name="Hijacked Name",
            attributed_to=owner_id,
        )
        activity = UpdateCaseActivity(
            actor=non_owner_id,
            object_=updated_case,
        )
        event = make_payload(activity)

        with caplog.at_level(logging.WARNING):
            UpdateCaseReceivedUseCase(dl, event).execute()

        stored = dl.read(case.id_)
        assert stored is not None
        stored = cast(VulnerabilityCase, stored)
        assert stored.name == "Original Name"
        assert any("not the owner" in r.message for r in caplog.records)

    def test_update_case_idempotent(self, monkeypatch, make_payload):
        """update_case with same data produces the same result (last-write-wins)."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        owner_id = "https://example.org/users/owner"
        case = VulnerabilityCase(
            id_="https://example.org/cases/uc3",
            name="Original",
            attributed_to=owner_id,
        )
        dl.create(case)

        updated_case = VulnerabilityCase(
            id_=case.id_,
            name="Updated",
            attributed_to=owner_id,
        )
        activity = UpdateCaseActivity(
            actor=owner_id,
            object_=updated_case,
        )
        event = make_payload(activity)

        def _mock_rehydrate_idempotent(obj, **kwargs):
            if obj == case.id_:
                return updated_case
            return real_rehydrate(obj, **kwargs)

        monkeypatch.setattr(
            "vultron.wire.as2.rehydration.rehydrate",
            _mock_rehydrate_idempotent,
        )

        UpdateCaseReceivedUseCase(dl, event).execute()
        UpdateCaseReceivedUseCase(dl, event).execute()

        stored = dl.read(case.id_)
        assert stored is not None
        stored = cast(VulnerabilityCase, stored)
        assert stored.name == "Updated"

    def test_update_case_warns_when_participant_has_not_accepted_embargo(
        self, monkeypatch, caplog, make_payload
    ):
        """update_case logs WARNING per CM-10-004 when a participant has not accepted the active embargo."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        owner_id = "https://example.org/users/owner"
        actor_id = "https://example.org/users/alice"
        embargo = EmbargoEvent(id_="https://example.org/embargoes/em1")
        dl.create(embargo)

        participant = CaseParticipant(
            id_="https://example.org/participants/p1",
            attributed_to=actor_id,
            context="https://example.org/cases/uc4",
            accepted_embargo_ids=[],
        )
        dl.create(participant)

        case = VulnerabilityCase(
            id_="https://example.org/cases/uc4",
            name="Original",
            attributed_to=owner_id,
            active_embargo=embargo.id_,
        )
        case.actor_participant_index[actor_id] = participant.id_
        dl.create(case)

        updated_case = VulnerabilityCase(
            id_=case.id_,
            name="Updated",
            attributed_to=owner_id,
        )
        activity = UpdateCaseActivity(actor=owner_id, object_=updated_case)
        event = make_payload(activity)

        with caplog.at_level(logging.WARNING):
            UpdateCaseReceivedUseCase(dl, event).execute()

        assert any(
            "has not accepted" in r.message and "CM-10-004" in r.message
            for r in caplog.records
        )

    def test_update_case_no_warning_when_all_participants_accepted_embargo(
        self, monkeypatch, caplog, make_payload
    ):
        """update_case does NOT warn when all participants have accepted the active embargo (CM-10-004)."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        owner_id = "https://example.org/users/owner"
        actor_id = "https://example.org/users/bob"
        embargo = EmbargoEvent(id_="https://example.org/embargoes/em2")
        dl.create(embargo)

        participant = CaseParticipant(
            id_="https://example.org/participants/p2",
            attributed_to=actor_id,
            context="https://example.org/cases/uc5",
            accepted_embargo_ids=[embargo.id_],
        )
        dl.create(participant)

        case = VulnerabilityCase(
            id_="https://example.org/cases/uc5",
            name="Original",
            attributed_to=owner_id,
            active_embargo=embargo.id_,
        )
        case.actor_participant_index[actor_id] = participant.id_
        dl.create(case)

        updated_case = VulnerabilityCase(
            id_=case.id_,
            name="Updated",
            attributed_to=owner_id,
        )
        activity = UpdateCaseActivity(actor=owner_id, object_=updated_case)
        event = make_payload(activity)

        with caplog.at_level(logging.WARNING):
            UpdateCaseReceivedUseCase(dl, event).execute()

        assert not any("has not accepted" in r.message for r in caplog.records)

    def test_update_case_no_warning_when_no_active_embargo(
        self, monkeypatch, caplog, make_payload
    ):
        """update_case does NOT warn when there is no active embargo (CM-10-004)."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        owner_id = "https://example.org/users/owner"
        actor_id = "https://example.org/users/carol"

        participant = CaseParticipant(
            id_="https://example.org/participants/p3",
            attributed_to=actor_id,
            context="https://example.org/cases/uc6",
            accepted_embargo_ids=[],
        )
        dl.create(participant)

        case = VulnerabilityCase(
            id_="https://example.org/cases/uc6",
            name="Original",
            attributed_to=owner_id,
            active_embargo=None,
        )
        case.actor_participant_index[actor_id] = participant.id_
        dl.create(case)

        updated_case = VulnerabilityCase(
            id_=case.id_,
            name="Updated",
            attributed_to=owner_id,
        )
        activity = UpdateCaseActivity(actor=owner_id, object_=updated_case)
        event = make_payload(activity)

        with caplog.at_level(logging.WARNING):
            UpdateCaseReceivedUseCase(dl, event).execute()

        assert not any("has not accepted" in r.message for r in caplog.records)

    # ------------------------------------------------------------------
    # Broadcast tests (CM-06-001, CM-06-002)
    # ------------------------------------------------------------------

    def test_update_case_broadcasts_announce_to_participants(
        self, make_payload
    ):
        """After a case update, the CaseActor outbox contains an Announce."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        owner_id = "https://example.org/users/owner"
        participant_id = "https://example.org/users/alice"
        case_id = "https://example.org/cases/bc1"

        case_actor = VultronCaseActor(
            id_=f"{case_id}/actor",
            name=f"CaseActor for {case_id}",
            attributed_to=owner_id,
            context=case_id,
        )
        dl.create(case_actor)

        case = VulnerabilityCase(
            id_=case_id,
            name="Original",
            attributed_to=owner_id,
        )
        case.actor_participant_index[participant_id] = (
            "https://example.org/participants/p-bc1"
        )
        dl.create(case)

        updated_case = VulnerabilityCase(
            id_=case_id, name="Updated", attributed_to=owner_id
        )
        activity = UpdateCaseActivity(actor=owner_id, object_=updated_case)
        event = make_payload(activity)

        UpdateCaseReceivedUseCase(dl, event).execute()

        refreshed_actor = dl.read(case_actor.id_)
        assert refreshed_actor is not None
        refreshed_actor = cast(VultronCaseActor, refreshed_actor)
        assert len(refreshed_actor.outbox.items) == 1

        broadcast_id = refreshed_actor.outbox.items[0]
        broadcast = dl.read(broadcast_id)
        assert broadcast is not None
        broadcast = cast(VultronActivity, broadcast)
        assert broadcast.type_ == "Announce"
        assert broadcast.actor == case_actor.id_
        assert broadcast.to is not None
        assert participant_id in broadcast.to

        # Verify the broadcast is also enqueued for delivery by outbox_handler
        scoped_dl = dl.clone_for_actor(case_actor.id_)
        queued_ids = scoped_dl.outbox_list()
        assert broadcast_id in queued_ids

    def test_update_case_no_broadcast_when_no_case_actor(self, make_payload):
        """Broadcast is skipped gracefully when no CaseActor exists."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        owner_id = "https://example.org/users/owner"
        case_id = "https://example.org/cases/bc2"

        case = VulnerabilityCase(
            id_=case_id, name="Original", attributed_to=owner_id
        )
        dl.create(case)

        updated_case = VulnerabilityCase(
            id_=case_id, name="Updated", attributed_to=owner_id
        )
        activity = UpdateCaseActivity(actor=owner_id, object_=updated_case)
        event = make_payload(activity)

        # Should not raise
        UpdateCaseReceivedUseCase(dl, event).execute()

        stored = dl.read(case_id)
        assert stored is not None
        stored = cast(VulnerabilityCase, stored)
        assert stored.name == "Updated"

    def test_update_case_no_broadcast_when_no_participants(self, make_payload):
        """Broadcast is skipped gracefully when the case has no participants."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        owner_id = "https://example.org/users/owner"
        case_id = "https://example.org/cases/bc3"

        case_actor = VultronCaseActor(
            id_=f"{case_id}/actor",
            name=f"CaseActor for {case_id}",
            attributed_to=owner_id,
            context=case_id,
        )
        dl.create(case_actor)

        case = VulnerabilityCase(
            id_=case_id, name="Original", attributed_to=owner_id
        )
        dl.create(case)

        updated_case = VulnerabilityCase(
            id_=case_id, name="Updated", attributed_to=owner_id
        )
        activity = UpdateCaseActivity(actor=owner_id, object_=updated_case)
        event = make_payload(activity)

        UpdateCaseReceivedUseCase(dl, event).execute()

        refreshed_actor = dl.read(case_actor.id_)
        assert refreshed_actor is not None
        refreshed_actor = cast(VultronCaseActor, refreshed_actor)
        assert refreshed_actor.outbox.items == []

    def test_update_case_broadcast_includes_all_participants(
        self, make_payload
    ):
        """Broadcast Announce.to includes every participant actor ID."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        owner_id = "https://example.org/users/owner"
        case_id = "https://example.org/cases/bc4"
        alice = "https://example.org/users/alice"
        bob = "https://example.org/users/bob"

        case_actor = VultronCaseActor(
            id_=f"{case_id}/actor",
            name=f"CaseActor for {case_id}",
            attributed_to=owner_id,
            context=case_id,
        )
        dl.create(case_actor)

        case = VulnerabilityCase(
            id_=case_id, name="Original", attributed_to=owner_id
        )
        case.actor_participant_index[alice] = (
            "https://example.org/participants/p-bc4-alice"
        )
        case.actor_participant_index[bob] = (
            "https://example.org/participants/p-bc4-bob"
        )
        dl.create(case)

        updated_case = VulnerabilityCase(
            id_=case_id, name="Updated", attributed_to=owner_id
        )
        activity = UpdateCaseActivity(actor=owner_id, object_=updated_case)
        event = make_payload(activity)

        UpdateCaseReceivedUseCase(dl, event).execute()

        refreshed_actor = dl.read(case_actor.id_)
        assert refreshed_actor is not None
        refreshed_actor = cast(VultronCaseActor, refreshed_actor)
        broadcast_id = refreshed_actor.outbox.items[0]
        broadcast = dl.read(broadcast_id)
        assert broadcast is not None
        broadcast = cast(VultronActivity, broadcast)
        assert broadcast.to is not None
        assert set(broadcast.to) == {alice, bob}


class TestEngageDeferCaseBTFailureReason:
    """Regression tests for BUG-471.6.

    When EngageCaseBT or DeferCaseBT fails (e.g., no participant record
    exists for the given actor), the WARNING log must include a non-empty
    failure reason — not a trailing colon with nothing after it.
    """

    @pytest.fixture
    def dl(self):
        return SqliteDataLayer("sqlite:///:memory:")

    @pytest.fixture
    def actor_id(self):
        return "https://example.org/actors/vendor"

    @pytest.fixture
    def case_id(self):
        return "urn:uuid:338a1bc3-0000-0000-0000-000000000001"

    def _engage_event(
        self, actor_id: str, case_id: str
    ) -> EngageCaseReceivedEvent:
        return EngageCaseReceivedEvent(
            activity_id="https://example.org/activities/engage-001",
            actor_id=actor_id,
            object_=VultronObject(id_=case_id),
            semantic_type=MessageSemantics.ENGAGE_CASE,
        )

    def _defer_event(
        self, actor_id: str, case_id: str
    ) -> DeferCaseReceivedEvent:
        return DeferCaseReceivedEvent(
            activity_id="https://example.org/activities/defer-001",
            actor_id=actor_id,
            object_=VultronObject(id_=case_id),
            semantic_type=MessageSemantics.DEFER_CASE,
        )

    def test_engage_case_failure_reason_is_nonempty(
        self, dl, actor_id, case_id, caplog
    ):
        """EngageCaseBT WARNING includes a non-empty failure reason.

        When CheckParticipantExists fails (no participant record),
        the warning must name the failing node, not end with a bare colon.
        """
        event = self._engage_event(actor_id, case_id)

        with caplog.at_level(logging.WARNING):
            EngageCaseReceivedUseCase(dl, event).execute()

        records = [
            r
            for r in caplog.records
            if "EngageCaseBT did not succeed" in r.message
        ]
        assert records, "Expected EngageCaseBT warning to be emitted"
        reason = records[0].message.rsplit(":", 1)[-1].strip()
        assert reason, (
            "EngageCaseBT warning must include a non-empty failure reason; "
            f"got: {records[0].message!r}"
        )

    def test_defer_case_failure_reason_is_nonempty(
        self, dl, actor_id, case_id, caplog
    ):
        """DeferCaseBT WARNING includes a non-empty failure reason.

        When CheckParticipantExists fails (no participant record),
        the warning must name the failing node, not end with a bare colon.
        """
        event = self._defer_event(actor_id, case_id)

        with caplog.at_level(logging.WARNING):
            DeferCaseReceivedUseCase(dl, event).execute()

        records = [
            r
            for r in caplog.records
            if "DeferCaseBT did not succeed" in r.message
        ]
        assert records, "Expected DeferCaseBT warning to be emitted"
        reason = records[0].message.rsplit(":", 1)[-1].strip()
        assert reason, (
            "DeferCaseBT warning must include a non-empty failure reason; "
            f"got: {records[0].message!r}"
        )
