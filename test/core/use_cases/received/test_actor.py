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


from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.core.use_cases.received.actor import (
    SuggestActorToCaseReceivedUseCase,
    AcceptSuggestActorToCaseReceivedUseCase,
    RejectSuggestActorToCaseReceivedUseCase,
    OfferCaseOwnershipTransferReceivedUseCase,
    AcceptCaseOwnershipTransferReceivedUseCase,
    RejectCaseOwnershipTransferReceivedUseCase,
    InviteActorToCaseReceivedUseCase,
    AcceptInviteActorToCaseReceivedUseCase,
    RejectInviteActorToCaseReceivedUseCase,
)


class TestInviteActorUseCases:
    """Tests for invite_actor_to_case, accept_invite_actor_to_case,
    and reject_invite_actor_to_case."""

    def test_invite_actor_to_case_stores_invite(
        self, monkeypatch, make_payload
    ):
        """InviteActorToCaseReceivedUseCase persists the Invite activity to the DataLayer."""
        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import (
            RmInviteToCaseActivity,
        )

        dl = TinyDbDataLayer(db_path=None)

        invite = RmInviteToCaseActivity(
            id_="https://example.org/cases/case1/invitations/1",
            actor="https://example.org/users/owner",
            object_="https://example.org/users/coordinator",
            target="https://example.org/cases/case1",
        )

        event = make_payload(invite)

        InviteActorToCaseReceivedUseCase(dl, event).execute()

        stored = dl.get(invite.type_.value, invite.id_)
        assert stored is not None

    def test_invite_actor_to_case_idempotent(self, monkeypatch, make_payload):
        """InviteActorToCaseReceivedUseCase skips storing a duplicate Invite."""
        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import (
            RmInviteToCaseActivity,
        )

        dl = TinyDbDataLayer(db_path=None)

        invite = RmInviteToCaseActivity(
            id_="https://example.org/cases/case1/invitations/2",
            actor="https://example.org/users/owner",
            object_="https://example.org/users/coordinator",
            target="https://example.org/cases/case1",
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
        from vultron.wire.as2.vocab.activities.case import (
            RmInviteToCaseActivity,
            RmRejectInviteToCaseActivity,
        )

        invite = RmInviteToCaseActivity(
            id_="https://example.org/cases/case1/invitations/3",
            actor="https://example.org/users/owner",
            object_="https://example.org/users/coordinator",
            target="https://example.org/cases/case1",
        )
        reject = RmRejectInviteToCaseActivity(
            actor="https://example.org/users/coordinator",
            object_=invite,
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
        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import (
            RmAcceptInviteToCaseActivity,
            RmInviteToCaseActivity,
        )
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        invitee_id = "https://example.org/users/coordinator"
        invitee = as_Organization(id_=invitee_id)
        case = VulnerabilityCase(
            id_="https://example.org/cases/caseIA1",
            name="TEST-ACCEPT-INVITE",
        )
        invite = RmInviteToCaseActivity(
            id_="https://example.org/cases/caseIA1/invitations/1",
            actor="https://example.org/users/owner",
            object_=invitee,
            target=case,
        )
        dl.create(invitee)
        dl.create(case)
        dl.create(invite)

        accept = RmAcceptInviteToCaseActivity(
            actor=invitee_id,
            object_=invite,
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
        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import (
            RmAcceptInviteToCaseActivity,
            RmInviteToCaseActivity,
        )
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
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
        invite = RmInviteToCaseActivity(
            id_="https://example.org/cases/caseIA2/invitations/1",
            actor="https://example.org/users/owner",
            object_=invitee,
            target=case,
        )
        dl.create(invitee)
        dl.create(case)
        dl.create(embargo)
        dl.create(invite)

        accept = RmAcceptInviteToCaseActivity(
            actor=invitee_id,
            object_=invite,
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

        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import (
            RmAcceptInviteToCaseActivity,
            RmInviteToCaseActivity,
        )
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )
        from vultron.core.states.rm import RM

        dl = TinyDbDataLayer(db_path=None)
        invitee_id = "https://example.org/users/coordinator_rm1"
        invitee = as_Organization(id_=invitee_id)
        case = VulnerabilityCase(
            id_="https://example.org/cases/caseRM001",
            name="TEST-RM-LIFECYCLE",
        )
        invite = RmInviteToCaseActivity(
            id_="https://example.org/cases/caseRM001/invitations/1",
            actor="https://example.org/users/owner",
            object_=invitee,
            target=case,
        )
        dl.create(invitee)
        dl.create(case)
        dl.create(invite)

        accept = RmAcceptInviteToCaseActivity(
            actor=invitee_id,
            object_=invite,
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

        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import (
            RmAcceptInviteToCaseActivity,
            RmInviteToCaseActivity,
        )
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        invitee_id = "https://example.org/users/coordinator_rm2"
        invitee = as_Organization(id_=invitee_id)
        case = VulnerabilityCase(
            id_="https://example.org/cases/caseRM002",
            name="TEST-RM-AUTO-ENGAGE",
        )
        invite = RmInviteToCaseActivity(
            id_="https://example.org/cases/caseRM002/invitations/1",
            actor="https://example.org/users/owner",
            object_=invitee,
            target=case,
        )
        dl.create(invitee)
        dl.create(case)
        dl.create(invite)

        accept = RmAcceptInviteToCaseActivity(
            actor=invitee_id,
            object_=invite,
        )
        event = make_payload(accept)

        AcceptInviteActorToCaseReceivedUseCase(dl, event).execute()

        updated_actor = cast(Any, dl.read(invitee_id))
        assert updated_actor is not None
        assert len(updated_actor.outbox.items) == 1

        engage_activity_id = updated_actor.outbox.items[0]
        engage_activity = cast(Any, dl.read(engage_activity_id))
        assert engage_activity is not None
        assert str(engage_activity.type_) == "Join"
        assert engage_activity.actor == invitee_id
        assert engage_activity.object_ == case.id_

    def test_accept_invite_actor_to_case_records_case_event(
        self, monkeypatch, make_payload
    ):
        """AcceptInviteActorToCaseReceivedUseCase appends a trusted-timestamp event to case.events (CM-02-009)."""
        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import (
            RmAcceptInviteToCaseActivity,
            RmInviteToCaseActivity,
        )
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        invitee_id = "https://example.org/users/coordinator"
        invitee = as_Organization(id_=invitee_id)
        case = VulnerabilityCase(
            id_="https://example.org/cases/caseIA3",
            name="TEST-ACCEPT-INVITE-EVENT",
        )
        invite = RmInviteToCaseActivity(
            id_="https://example.org/cases/caseIA3/invitations/1",
            actor="https://example.org/users/owner",
            object_=invitee,
            target=case,
        )
        dl.create(invitee)
        dl.create(case)
        dl.create(invite)

        accept = RmAcceptInviteToCaseActivity(
            actor=invitee_id,
            object_=invite,
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
        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.base.objects.actors import as_Actor
        from vultron.wire.as2.vocab.activities.actor import (
            RecommendActorActivity,
        )

        dl = TinyDbDataLayer(db_path=None)

        coordinator = as_Actor(id_="https://example.org/users/coordinator")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_sa1",
            name="SA Case 1",
        )
        activity = RecommendActorActivity(
            actor="https://example.org/users/finder",
            object_=coordinator,
            target=case,
            to="https://example.org/users/vendor",
        )

        event = make_payload(activity)

        SuggestActorToCaseReceivedUseCase(dl, event).execute()

        stored = dl.get(activity.type_.value, activity.id_)
        assert stored is not None

    def test_suggest_actor_to_case_idempotent(self, monkeypatch, make_payload):
        """SuggestActorToCaseReceivedUseCase is idempotent — second call is a no-op."""
        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.actor import (
            RecommendActorActivity,
        )
        from vultron.wire.as2.vocab.base.objects.actors import as_Actor

        dl = TinyDbDataLayer(db_path=None)

        coordinator = as_Actor(id_="https://example.org/users/coordinator")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_sa2",
            name="SA Case 2",
        )
        activity = RecommendActorActivity(
            actor="https://example.org/users/finder",
            object_=coordinator,
            target=case,
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
        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.actor import (
            AcceptActorRecommendationActivity,
            RecommendActorActivity,
        )
        from vultron.wire.as2.vocab.base.objects.actors import as_Actor

        dl = TinyDbDataLayer(db_path=None)

        coordinator = as_Actor(id_="https://example.org/users/coordinator")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_sa3",
            name="SA Case 3",
        )
        recommendation = RecommendActorActivity(
            actor="https://example.org/users/finder",
            object_=coordinator,
            target=case,
        )
        activity = AcceptActorRecommendationActivity(
            actor="https://example.org/users/vendor",
            object_=recommendation,
            target=case,
        )
        event = make_payload(activity)

        AcceptSuggestActorToCaseReceivedUseCase(dl, event).execute()

        stored = dl.get(activity.type_.value, activity.id_)
        assert stored is not None

    def test_reject_suggest_actor_to_case_logs_rejection(
        self, monkeypatch, caplog, make_payload
    ):
        """RejectSuggestActorToCaseReceivedUseCase logs rejection without state change."""
        from vultron.wire.as2.vocab.activities.actor import (
            RecommendActorActivity,
            RejectActorRecommendationActivity,
        )
        from vultron.wire.as2.vocab.base.objects.actors import as_Actor

        coordinator = as_Actor(id_="https://example.org/users/coordinator")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_sa4",
            name="SA Case 4",
        )
        recommendation = RecommendActorActivity(
            actor="https://example.org/users/finder",
            object_=coordinator,
            target=case,
        )
        activity = RejectActorRecommendationActivity(
            actor="https://example.org/users/vendor",
            object_=recommendation,
            target=case,
        )
        event = make_payload(activity)

        with caplog.at_level(logging.INFO):
            RejectSuggestActorToCaseReceivedUseCase(
                MagicMock(), event
            ).execute()

        assert any("rejected" in r.message.lower() for r in caplog.records)


class TestOwnershipTransferUseCases:
    """Tests for offer/accept/reject ownership transfer use cases."""

    def test_offer_case_ownership_transfer_persists_offer(
        self, monkeypatch, make_payload
    ):
        """OfferCaseOwnershipTransferReceivedUseCase persists the offer."""
        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import (
            OfferCaseOwnershipTransferActivity,
        )

        dl = TinyDbDataLayer(db_path=None)

        case = VulnerabilityCase(
            id_="https://example.org/cases/case_ot1",
            name="OT Case 1",
        )
        activity = OfferCaseOwnershipTransferActivity(
            actor="https://example.org/users/vendor",
            object_=case,
            target="https://example.org/users/coordinator",
        )
        event = make_payload(activity)

        OfferCaseOwnershipTransferReceivedUseCase(dl, event).execute()

        stored = dl.get(activity.type_.value, activity.id_)
        assert stored is not None

    def test_accept_case_ownership_transfer_updates_attributed_to(
        self, monkeypatch, make_payload
    ):
        """AcceptCaseOwnershipTransferReceivedUseCase updates case.attributed_to to new owner."""
        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import (
            AcceptCaseOwnershipTransferActivity,
            OfferCaseOwnershipTransferActivity,
        )

        dl = TinyDbDataLayer(db_path=None)
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_ot2",
            name="OT Case 2",
            attributed_to="https://example.org/users/vendor",
        )
        dl.create(case)

        offer = OfferCaseOwnershipTransferActivity(
            id_="https://example.org/activities/offer_ot2",
            actor="https://example.org/users/vendor",
            object_=case,
            target="https://example.org/users/coordinator",
        )
        dl.create(offer)

        activity = AcceptCaseOwnershipTransferActivity(
            actor="https://example.org/users/coordinator",
            object_=offer,
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
        from vultron.wire.as2.vocab.activities.case import (
            OfferCaseOwnershipTransferActivity,
            RejectCaseOwnershipTransferActivity,
        )

        case = VulnerabilityCase(
            id_="https://example.org/cases/case_ot3",
            name="OT Case 3",
        )
        offer = OfferCaseOwnershipTransferActivity(
            id_="https://example.org/activities/offer_ot3",
            actor="https://example.org/users/vendor",
            object_=case,
            target="https://example.org/users/coordinator",
        )
        activity = RejectCaseOwnershipTransferActivity(
            actor="https://example.org/users/coordinator",
            object_=offer,
        )
        event = make_payload(activity)

        with caplog.at_level(logging.INFO):
            RejectCaseOwnershipTransferReceivedUseCase(
                MagicMock(), event
            ).execute()

        assert any("rejected" in r.message.lower() for r in caplog.records)
