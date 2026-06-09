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
from vultron.core.models.case import VultronCase
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.activity import VultronActivity
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.case import (
    DeferCaseReceivedEvent,
    EngageCaseReceivedEvent,
)
from vultron.core.models.participant import VultronParticipant
from vultron.core.use_cases.received.case import (
    DeferCaseReceivedUseCase,
    EngageCaseReceivedUseCase,
    UpdateCaseReceivedUseCase,
)
from vultron.core.behaviors.case.update_tree import (
    create_update_case_received_tree,
)
from vultron.core.behaviors.case.nodes.update import (
    ApplyCaseUpdateNode,
    BroadcastCaseUpdateNode,
    CaptureCaseUpdateBroadcastExclusionsNode,
    CheckCaseUpdateOwnerNode,
)
from vultron.wire.as2.rehydration import rehydrate as real_rehydrate
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.factories import (
    update_case_activity,
)


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
        activity = update_case_activity(updated_case, actor=owner_id)
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
        activity = update_case_activity(updated_case, actor=non_owner_id)
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
        activity = update_case_activity(updated_case, actor=owner_id)
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
        activity = update_case_activity(updated_case, actor=owner_id)
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
        activity = update_case_activity(updated_case, actor=owner_id)
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
        activity = update_case_activity(updated_case, actor=owner_id)
        event = make_payload(activity)

        with caplog.at_level(logging.WARNING):
            UpdateCaseReceivedUseCase(dl, event).execute()

        assert not any("has not accepted" in r.message for r in caplog.records)

    def test_update_case_ignores_non_participant_objects_in_embargo_check(
        self, make_payload
    ):
        """Non-participant objects referenced by the case must not be excluded."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        owner_id = "https://example.org/users/owner"
        actor_id = "https://example.org/users/alice"
        case_id = "https://example.org/cases/uc6b"
        embargo = EmbargoEvent(id_="https://example.org/embargoes/em6b")
        dl.create(embargo)

        bogus_ref = VultronActivity(
            type_="Announce",
            actor=owner_id,
            object_=case_id,
        )
        dl.create(bogus_ref)

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
            active_embargo=embargo.id_,
        )
        case.actor_participant_index[actor_id] = bogus_ref.id_
        dl.create(case)

        updated_case = VulnerabilityCase(
            id_=case_id,
            name="Updated",
            attributed_to=owner_id,
        )
        activity = update_case_activity(updated_case, actor=owner_id)
        event = make_payload(activity)

        UpdateCaseReceivedUseCase(dl, event).execute()

        outbox_items = dl.outbox_list_for_actor(case_actor.id_)
        assert len(outbox_items) == 1

        broadcast_id = outbox_items[0]
        broadcast = dl.read(broadcast_id)
        assert broadcast is not None
        broadcast = cast(VultronActivity, broadcast)
        assert broadcast.to is not None
        assert actor_id in broadcast.to

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
        activity = update_case_activity(updated_case, actor=owner_id)
        event = make_payload(activity)

        UpdateCaseReceivedUseCase(dl, event).execute()

        queued_ids = dl.clone_for_actor(case_actor.id_).outbox_list()
        assert len(queued_ids) == 1

        broadcast_id = queued_ids[0]
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
        activity = update_case_activity(updated_case, actor=owner_id)
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
        activity = update_case_activity(updated_case, actor=owner_id)
        event = make_payload(activity)

        UpdateCaseReceivedUseCase(dl, event).execute()

        queued_ids = dl.clone_for_actor(case_actor.id_).outbox_list()
        assert queued_ids == []

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
        activity = update_case_activity(updated_case, actor=owner_id)
        event = make_payload(activity)

        UpdateCaseReceivedUseCase(dl, event).execute()

        queued_ids = dl.clone_for_actor(case_actor.id_).outbox_list()
        broadcast_id = queued_ids[0]
        broadcast = dl.read(broadcast_id)
        assert broadcast is not None
        broadcast = cast(VultronActivity, broadcast)
        assert broadcast.to is not None
        assert set(broadcast.to) == {alice, bob}

    def test_update_case_bt_structure_includes_broadcast_node(
        self, make_payload
    ):
        """UpdateCaseBT keeps ownership, embargo, update, and broadcast in-tree."""
        owner_id = "https://example.org/users/owner"
        case_id = "https://example.org/cases/bt1"
        updated_case = VulnerabilityCase(
            id_=case_id, name="Updated", attributed_to=owner_id
        )
        activity = update_case_activity(updated_case, actor=owner_id)
        event = make_payload(activity)

        tree = create_update_case_received_tree(
            case_id=case_id,
            actor_id=owner_id,
            request=event,
        )

        assert tree.name == "UpdateCaseBT"
        assert [child.__class__ for child in tree.children] == [
            CheckCaseUpdateOwnerNode,
            CaptureCaseUpdateBroadcastExclusionsNode,
            ApplyCaseUpdateNode,
            BroadcastCaseUpdateNode,
        ]

    def test_update_case_bt_executes_without_post_bt_broadcast(
        self, make_payload, monkeypatch
    ):
        """UpdateCaseBT handles the broadcast internally instead of after execute()."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        owner_id = "https://example.org/users/owner"
        participant_id = "https://example.org/users/alice"
        case_id = "https://example.org/cases/bt2"

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
            "https://example.org/participants/p-bt2"
        )
        dl.create(case)

        updated_case = VulnerabilityCase(
            id_=case_id,
            name="Updated",
            attributed_to=owner_id,
        )
        activity = update_case_activity(updated_case, actor=owner_id)
        event = make_payload(activity)

        def _should_not_be_called(*args, **kwargs):
            raise AssertionError("post-BT broadcast helper should not run")

        monkeypatch.setattr(
            UpdateCaseReceivedUseCase,
            "_broadcast_case_update",
            _should_not_be_called,
        )

        UpdateCaseReceivedUseCase(dl, event).execute()

        outbox_items = dl.outbox_list_for_actor(case_actor.id_)
        assert len(outbox_items) == 1


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


# ---------------------------------------------------------------------------
# #573: EngageCaseReceivedUseCase must store embedded participants
# ---------------------------------------------------------------------------


class TestEngageCaseStoresEmbeddedParticipants:
    """EngageCaseReceivedUseCase must call _store_embedded_participants (#573).

    Regression tests: when Join(VulnerabilityCase) arrives with inline
    participant objects, those objects must be persisted as independent
    DataLayer records before the BT runs — matching the pattern already
    established for Create (#564) and Announce (#566) paths.
    """

    _ACTOR_ID = "https://vendor.example.org/actors/vendor"
    _CASE_ID = "https://example.org/cases/case-573-001"
    _PARTICIPANT_ID = f"{_CASE_ID}/participants/vendor"

    @pytest.fixture
    def dl(self):
        return SqliteDataLayer("sqlite:///:memory:")

    @pytest.fixture
    def case_with_inline_participant(self):
        """VultronCase carrying a fully inline VultronParticipant."""
        participant = VultronParticipant(
            id_=self._PARTICIPANT_ID,
            attributed_to=self._ACTOR_ID,
            context=self._CASE_ID,
        )
        case = VultronCase(id_=self._CASE_ID)
        case.case_participants = [participant]
        return case

    @pytest.fixture
    def engage_event_with_inline_case(self, case_with_inline_participant):
        return EngageCaseReceivedEvent(
            activity_id="https://example.org/activities/engage-573",
            actor_id=self._ACTOR_ID,
            object_=case_with_inline_participant,
            semantic_type=MessageSemantics.ENGAGE_CASE,
        )

    def test_inline_participant_stored_even_when_bt_fails(
        self, dl, engage_event_with_inline_case
    ):
        """Embedded CaseParticipant is persisted before EngageCaseBT runs.

        Even when the BT fails (no pre-registered participant in the DataLayer),
        _store_embedded_participants must run first and persist the inline
        participant object (#573 regression).
        """
        EngageCaseReceivedUseCase(dl, engage_event_with_inline_case).execute()

        stored = dl.read(self._PARTICIPANT_ID)
        assert stored is not None, (
            "CaseParticipant embedded in Join(VulnerabilityCase) must be "
            "stored as an independent DataLayer record before the BT runs "
            "(EngageCaseReceivedUseCase regression #573)"
        )

    def test_bare_string_participant_is_not_stored(self, dl):
        """When case_participants contains bare strings, nothing is stored.

        _store_embedded_participants is idempotent on strings; no error and
        no false record is created (#573 does not regress bare-string path).
        """
        case_str_participants = VultronCase(id_=self._CASE_ID)
        case_str_participants.case_participants = [
            self._PARTICIPANT_ID
        ]  # bare string
        event = EngageCaseReceivedEvent(
            activity_id="https://example.org/activities/engage-573-str",
            actor_id=self._ACTOR_ID,
            object_=case_str_participants,
            semantic_type=MessageSemantics.ENGAGE_CASE,
        )
        EngageCaseReceivedUseCase(dl, event).execute()

        stored = dl.read(self._PARTICIPANT_ID)
        assert stored is None, (
            "_store_embedded_participants must skip bare string participant "
            "refs — no VultronParticipant record should be created for a bare "
            "string"
        )
