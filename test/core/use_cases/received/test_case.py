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

from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.activity import VultronActivity
from vultron.core.use_cases.received.case import UpdateCaseReceivedUseCase
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
        dl = TinyDbDataLayer(db_path=None)
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
        dl = TinyDbDataLayer(db_path=None)
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
        dl = TinyDbDataLayer(db_path=None)
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
        dl = TinyDbDataLayer(db_path=None)
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
        dl = TinyDbDataLayer(db_path=None)
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
        dl = TinyDbDataLayer(db_path=None)
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
        dl = TinyDbDataLayer(db_path=None)
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
        queue_table = dl._db.table(f"{case_actor.id_}_outbox")
        queued_ids = [row["activity_id"] for row in queue_table.all()]
        assert broadcast_id in queued_ids

    def test_update_case_no_broadcast_when_no_case_actor(self, make_payload):
        """Broadcast is skipped gracefully when no CaseActor exists."""
        dl = TinyDbDataLayer(db_path=None)
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
        dl = TinyDbDataLayer(db_path=None)
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
        dl = TinyDbDataLayer(db_path=None)
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
