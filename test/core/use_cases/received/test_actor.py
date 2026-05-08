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
"""Tests for actor-related use-case classes."""

import logging
from typing import Any, cast
from unittest.mock import MagicMock

import py_trees
import pytest

from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    VulnerabilityCase,
    VulnerabilityCaseStub,
)
from vultron.core.use_cases.received.actor import (
    AcceptCaseManagerRoleReceivedUseCase,
    AcceptCaseOwnershipTransferReceivedUseCase,
    AcceptInviteActorToCaseReceivedUseCase,
    AcceptSuggestActorToCaseReceivedUseCase,
    OfferCaseManagerRoleReceivedUseCase,
    OfferCaseOwnershipTransferReceivedUseCase,
    RejectCaseManagerRoleReceivedUseCase,
    RejectCaseOwnershipTransferReceivedUseCase,
    RejectInviteActorToCaseReceivedUseCase,
    RejectSuggestActorToCaseReceivedUseCase,
    SuggestActorToCaseReceivedUseCase,
    InviteActorToCaseReceivedUseCase,
)
from vultron.wire.as2.factories import (
    accept_actor_recommendation_activity,
    accept_case_manager_role_activity,
    accept_case_ownership_transfer_activity,
    offer_case_manager_role_activity,
    offer_case_ownership_transfer_activity,
    recommend_actor_activity,
    reject_actor_recommendation_activity,
    reject_case_manager_role_activity,
    reject_case_ownership_transfer_activity,
    rm_accept_invite_to_case_activity,
    rm_invite_to_case_activity,
    rm_reject_invite_to_case_activity,
)
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)


class TestInviteActorUseCases:
    """Tests for invite_actor_to_case, accept_invite_actor_to_case,
    and reject_invite_actor_to_case."""

    def test_invite_actor_to_case_stores_invite(
        self, monkeypatch, make_payload
    ):
        """InviteActorToCaseReceivedUseCase persists the Invite activity to the DataLayer."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer("sqlite:///:memory:")

        invite = rm_invite_to_case_activity(
            as_Actor(id_="https://example.org/users/coordinator"),
            target="https://example.org/cases/case1",
            actor="https://example.org/users/owner",
            id_="https://example.org/cases/case1/invitations/1",
        )

        event = make_payload(invite)

        InviteActorToCaseReceivedUseCase(dl, event).execute()

        stored = dl.get(invite.type_.value, invite.id_)
        assert stored is not None

    def test_invite_actor_to_case_idempotent(self, monkeypatch, make_payload):
        """InviteActorToCaseReceivedUseCase skips storing a duplicate Invite."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer("sqlite:///:memory:")

        invite = rm_invite_to_case_activity(
            as_Actor(id_="https://example.org/users/coordinator"),
            target="https://example.org/cases/case1",
            actor="https://example.org/users/owner",
            id_="https://example.org/cases/case1/invitations/2",
        )

        event = make_payload(invite)

        InviteActorToCaseReceivedUseCase(dl, event).execute()
        InviteActorToCaseReceivedUseCase(
            dl, event
        ).execute()  # second call is no-op

        stored = dl.get(invite.type_.value, invite.id_)
        assert stored is not None

    def test_reject_invite_actor_to_case_logs_rejection(self, make_payload):
        """RejectInviteActorToCaseReceivedUseCase logs without raising."""
        invite = rm_invite_to_case_activity(
            as_Actor(id_="https://example.org/users/coordinator"),
            target="https://example.org/cases/case1",
            actor="https://example.org/users/owner",
            id_="https://example.org/cases/case1/invitations/3",
        )
        reject = rm_reject_invite_to_case_activity(
            invite,
            actor="https://example.org/users/coordinator",
        )

        event = make_payload(reject)

        result = RejectInviteActorToCaseReceivedUseCase(
            MagicMock(), event
        ).execute()
        assert result is None

    def test_accept_invite_actor_to_case_adds_participant(
        self, monkeypatch, make_payload
    ):
        """AcceptInviteActorToCaseReceivedUseCase creates a CaseParticipant and adds them to the case."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        invitee_id = "https://example.org/users/coordinator"
        invitee = as_Organization(id_=invitee_id)
        case = VulnerabilityCase(
            id_="https://example.org/cases/caseIA1",
            name="TEST-ACCEPT-INVITE",
        )
        invite = rm_invite_to_case_activity(
            invitee,
            target=VulnerabilityCaseStub(id_=case.id_),
            actor="https://example.org/users/owner",
            id_="https://example.org/cases/caseIA1/invitations/1",
        )
        dl.create(invitee)
        dl.create(case)
        dl.create(invite)

        accept = rm_accept_invite_to_case_activity(
            invite,
            actor=invitee_id,
        )

        event = make_payload(accept)

        AcceptInviteActorToCaseReceivedUseCase(dl, event).execute()

        case = dl.read(case.id_)
        assert case is not None
        case = cast(VulnerabilityCase, case)
        assert invitee_id in case.actor_participant_index

    def test_accept_invite_actor_to_case_records_active_embargo(
        self, monkeypatch, make_payload
    ):
        """AcceptInviteActorToCaseReceivedUseCase records the active embargo ID on the new participant (CM-10-001, CM-10-003)."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.states.em import EM
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        invitee_id = "https://example.org/users/coordinator"
        invitee = as_Organization(id_=invitee_id)
        embargo = EmbargoEvent(
            id_="https://example.org/cases/caseIA2/embargo_events/e1",
            content="Active embargo",
        )
        case = VulnerabilityCase(
            id_="https://example.org/cases/caseIA2",
            name="TEST-ACCEPT-INVITE-EMBARGO",
        )
        case.active_embargo = embargo.id_
        case.current_status.em_state = EM.ACTIVE
        invite = rm_invite_to_case_activity(
            invitee,
            target=VulnerabilityCaseStub(id_=case.id_),
            actor="https://example.org/users/owner",
            id_="https://example.org/cases/caseIA2/invitations/1",
        )
        dl.create(invitee)
        dl.create(case)
        dl.create(embargo)
        dl.create(invite)

        accept = rm_accept_invite_to_case_activity(
            invite,
            actor=invitee_id,
        )

        event = make_payload(accept)

        AcceptInviteActorToCaseReceivedUseCase(dl, event).execute()

        case = dl.read(case.id_)
        assert case is not None
        case = cast(VulnerabilityCase, case)
        participant_id = case.actor_participant_index.get(invitee_id)
        assert participant_id is not None
        participant_obj = dl.get(id_=participant_id)
        assert participant_obj is not None
        participant_obj = cast(Any, participant_obj)
        assert embargo.id_ in participant_obj.accepted_embargo_ids

    def test_accept_invite_participant_can_reach_rm_accepted(
        self, make_payload
    ):
        """Accepted invite auto-engages the participant to RM.ACCEPTED.

        CM-11-001 requires invitation acceptance to advance the invitee to
        RM.ACCEPTED without a separate engage-case trigger. The use case still
        pre-seeds RECEIVED and VALID before invoking the engage-case logic.
        """
        from typing import Any, cast

        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )
        from vultron.core.states.rm import RM

        dl = SqliteDataLayer("sqlite:///:memory:")
        invitee_id = "https://example.org/users/coordinator_rm1"
        invitee = as_Organization(id_=invitee_id)
        case = VulnerabilityCase(
            id_="https://example.org/cases/caseRM001",
            name="TEST-RM-LIFECYCLE",
        )
        invite = rm_invite_to_case_activity(
            invitee,
            target=VulnerabilityCaseStub(id_=case.id_),
            actor="https://example.org/users/owner",
            id_="https://example.org/cases/caseRM001/invitations/1",
        )
        dl.create(invitee)
        dl.create(case)
        dl.create(invite)

        accept = rm_accept_invite_to_case_activity(
            invite,
            actor=invitee_id,
        )
        event = make_payload(accept)
        AcceptInviteActorToCaseReceivedUseCase(dl, event).execute()

        updated_case = cast(Any, dl.read(case.id_))
        participant_id = updated_case.actor_participant_index.get(invitee_id)
        participant_obj = cast(Any, dl.get(id_=participant_id))
        latest_status = participant_obj.participant_statuses[-1]
        assert latest_status.rm_state == RM.ACCEPTED

    def test_accept_invite_actor_to_case_emits_engage_activity(
        self, make_payload
    ):
        """AcceptInviteActorToCaseReceivedUseCase queues an RmEngageCaseActivity."""
        from typing import Any, cast

        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        invitee_id = "https://example.org/users/coordinator_rm2"
        invitee = as_Organization(id_=invitee_id)
        case = VulnerabilityCase(
            id_="https://example.org/cases/caseRM002",
            name="TEST-RM-AUTO-ENGAGE",
        )
        invite = rm_invite_to_case_activity(
            invitee,
            target=VulnerabilityCaseStub(id_=case.id_),
            actor="https://example.org/users/owner",
            id_="https://example.org/cases/caseRM002/invitations/1",
        )
        dl.create(invitee)
        dl.create(case)
        dl.create(invite)

        accept = rm_accept_invite_to_case_activity(
            invite,
            actor=invitee_id,
        )
        event = make_payload(accept)

        AcceptInviteActorToCaseReceivedUseCase(dl, event).execute()

        updated_actor = cast(Any, dl.read(invitee_id))
        assert updated_actor is not None
        # At least the engage (Join) activity must be present.  An Announce
        # activity may also be queued by _emit_announce_case so we allow ≥ 1.
        assert len(updated_actor.outbox.items) >= 1

        engage_activity = None
        for item_id in updated_actor.outbox.items:
            candidate = cast(Any, dl.read(item_id))
            if candidate is not None and str(candidate.type_) == "Join":
                engage_activity = candidate
                break
        assert (
            engage_activity is not None
        ), "No Join/engage activity found in outbox"
        assert engage_activity.actor == invitee_id
        assert engage_activity.object_.id_ == case.id_

    def test_accept_invite_actor_to_case_records_case_event(
        self, monkeypatch, make_payload
    ):
        """AcceptInviteActorToCaseReceivedUseCase appends a trusted-timestamp event to case.events (CM-02-009)."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        invitee_id = "https://example.org/users/coordinator"
        invitee = as_Organization(id_=invitee_id)
        case = VulnerabilityCase(
            id_="https://example.org/cases/caseIA3",
            name="TEST-ACCEPT-INVITE-EVENT",
        )
        invite = rm_invite_to_case_activity(
            invitee,
            target=VulnerabilityCaseStub(id_=case.id_),
            actor="https://example.org/users/owner",
            id_="https://example.org/cases/caseIA3/invitations/1",
        )
        dl.create(invitee)
        dl.create(case)
        dl.create(invite)

        accept = rm_accept_invite_to_case_activity(
            invite,
            actor=invitee_id,
        )

        event = make_payload(accept)

        assert len(case.events) == 0

        AcceptInviteActorToCaseReceivedUseCase(dl, event).execute()

        case = dl.read(case.id_)
        assert case is not None
        case = cast(VulnerabilityCase, case)
        assert len(case.events) >= 1
        event_types = [e.event_type for e in case.events]
        assert "participant_joined" in event_types


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

    def test_reject_suggest_actor_to_case_logs_rejection(
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


class TestOwnershipTransferUseCases:
    """Tests for offer/accept/reject ownership transfer use cases."""

    def test_offer_case_ownership_transfer_persists_offer(
        self, monkeypatch, make_payload
    ):
        """OfferCaseOwnershipTransferReceivedUseCase persists the offer."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer("sqlite:///:memory:")

        case = VulnerabilityCase(
            id_="https://example.org/cases/case_ot1",
            name="OT Case 1",
        )
        activity = offer_case_ownership_transfer_activity(
            case,
            target="https://example.org/users/coordinator",
            actor="https://example.org/users/vendor",
        )
        event = make_payload(activity)

        OfferCaseOwnershipTransferReceivedUseCase(dl, event).execute()

        stored = dl.get(activity.type_.value, activity.id_)
        assert stored is not None

    def test_accept_case_ownership_transfer_updates_attributed_to(
        self, monkeypatch, make_payload
    ):
        """AcceptCaseOwnershipTransferReceivedUseCase updates case.attributed_to to new owner."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer("sqlite:///:memory:")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_ot2",
            name="OT Case 2",
            attributed_to="https://example.org/users/vendor",
        )
        dl.create(case)

        offer = offer_case_ownership_transfer_activity(
            case,
            target="https://example.org/users/coordinator",
            actor="https://example.org/users/vendor",
            id_="https://example.org/activities/offer_ot2",
        )
        dl.create(offer)

        activity = accept_case_ownership_transfer_activity(
            offer,
            actor="https://example.org/users/coordinator",
        )
        event = make_payload(activity)

        AcceptCaseOwnershipTransferReceivedUseCase(dl, event).execute()

        updated_record = dl.get(case.type_.value, case.id_)
        assert updated_record is not None
        data = cast(Any, updated_record).get("data_", updated_record)
        assert (
            data.get("attributed_to")
            == "https://example.org/users/coordinator"
        )

    def test_reject_case_ownership_transfer_logs_rejection(
        self, monkeypatch, caplog, make_payload
    ):
        """RejectCaseOwnershipTransferReceivedUseCase logs rejection; ownership unchanged."""
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_ot3",
            name="OT Case 3",
        )
        offer = offer_case_ownership_transfer_activity(
            case,
            target="https://example.org/users/coordinator",
            actor="https://example.org/users/vendor",
            id_="https://example.org/activities/offer_ot3",
        )
        activity = reject_case_ownership_transfer_activity(
            offer,
            actor="https://example.org/users/coordinator",
        )
        event = make_payload(activity)

        with caplog.at_level(logging.INFO):
            RejectCaseOwnershipTransferReceivedUseCase(
                MagicMock(), event
            ).execute()

        assert any("rejected" in r.message.lower() for r in caplog.records)


class TestCaseManagerRoleDelegationUseCases:
    """Tests for offer/accept/reject CASE_MANAGER role delegation use cases.

    DEMOMA-08-002: CASE_MANAGER delegation is distinct from ownership transfer.
    """

    _VENDOR_URI = "https://example.org/actors/vendor"
    _CASE_ACTOR_URI = "https://example.org/actors/case-actor"
    _CASE_URI = "https://example.org/cases/urn:uuid:test-case-mgr"
    _PARTICIPANT_URI = (
        "https://example.org/participants/urn:uuid:case-actor-participant"
    )

    def _make_offer(self):
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        case = VulnerabilityCase(id_=self._CASE_URI, name="CASE-MGR-TEST")
        participant = CaseParticipant(
            id_=self._PARTICIPANT_URI,
            attributed_to=self._CASE_ACTOR_URI,
            context=self._CASE_URI,
        )
        return offer_case_manager_role_activity(
            case,
            target=participant,
            actor=self._VENDOR_URI,
        )

    def test_offer_case_manager_role_persists_offer(self, make_payload):
        """OfferCaseManagerRoleReceivedUseCase persists the offer activity."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer("sqlite:///:memory:")
        offer = self._make_offer()
        event = make_payload(offer)

        OfferCaseManagerRoleReceivedUseCase(dl, event).execute()

        stored = dl.get(offer.type_.value, offer.id_)
        assert stored is not None

    def test_offer_case_manager_role_idempotent(self, make_payload):
        """Repeated execution of OfferCaseManagerRoleReceivedUseCase is a no-op."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer("sqlite:///:memory:")
        offer = self._make_offer()
        event = make_payload(offer)

        OfferCaseManagerRoleReceivedUseCase(dl, event).execute()
        OfferCaseManagerRoleReceivedUseCase(dl, event).execute()

        stored = dl.get(offer.type_.value, offer.id_)
        assert stored is not None

    def test_accept_case_manager_role_logs_acceptance(
        self, caplog, make_payload
    ):
        """AcceptCaseManagerRoleReceivedUseCase logs acceptance without raising."""
        offer = self._make_offer()
        accept = accept_case_manager_role_activity(
            offer, actor=self._CASE_ACTOR_URI
        )
        event = make_payload(accept)

        with caplog.at_level(logging.INFO):
            AcceptCaseManagerRoleReceivedUseCase(MagicMock(), event).execute()

        assert any("accepted" in r.message.lower() for r in caplog.records)

    def test_reject_case_manager_role_logs_warning(self, caplog, make_payload):
        """RejectCaseManagerRoleReceivedUseCase logs a warning without raising."""
        offer = self._make_offer()
        reject = reject_case_manager_role_activity(
            offer, actor=self._CASE_ACTOR_URI
        )
        event = make_payload(reject)

        with caplog.at_level(logging.WARNING):
            RejectCaseManagerRoleReceivedUseCase(MagicMock(), event).execute()

        assert any("rejected" in r.message.lower() for r in caplog.records)
