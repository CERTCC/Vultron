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
"""Tests for actor invitation received use cases."""

from typing import Any, cast
from unittest.mock import MagicMock

from vultron.core.use_cases.received.actor.invite import (
    AcceptInviteActorToCaseReceivedUseCase,
    InviteActorToCaseReceivedUseCase,
    RejectInviteActorToCaseReceivedUseCase,
)
from vultron.wire.as2.factories import (
    rm_accept_invite_to_case_activity,
    rm_invite_to_case_activity,
    rm_reject_invite_to_case_activity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    VulnerabilityCaseStub,
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

    def test_reject_invite_actor_to_case_ledgers_rejection(self, make_payload):
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

        AcceptInviteActorToCaseReceivedUseCase(
            dl, event, sync_port=MagicMock()
        ).execute()

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

        AcceptInviteActorToCaseReceivedUseCase(
            dl, event, sync_port=MagicMock()
        ).execute()

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
        """Accepted invite advances the participant to RM.ACCEPTED via BT.

        PCR-08-010: Accept(Invite) IS the engage decision.  The use case
        delegates to AcceptInviteActorToCaseBT which records the participant
        at RM.ACCEPTED — no separate engage-case BT or proxy RmEngageCaseActivity
        is emitted.
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
        owner_id = "https://example.org/users/owner"
        case = VulnerabilityCase(
            id_="https://example.org/cases/caseRM001",
            name="TEST-RM-LIFECYCLE",
        )
        invite = rm_invite_to_case_activity(
            invitee,
            target=VulnerabilityCaseStub(id_=case.id_),
            actor=owner_id,
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

        # No TriggerActivityAdapter needed: RM.ACCEPTED is reached via BT.
        AcceptInviteActorToCaseReceivedUseCase(
            dl, event, sync_port=MagicMock()
        ).execute()

        updated_case = cast(Any, dl.read(case.id_))
        participant_id = updated_case.actor_participant_index.get(invitee_id)
        participant_obj = cast(Any, dl.get(id_=participant_id))
        latest_status = participant_obj.participant_statuses[-1]
        assert latest_status.rm_state == RM.ACCEPTED

    def test_accept_invite_no_identity_spoofing(self, make_payload):
        """PCR-07-008: AcceptInviteActorToCaseReceivedUseCase MUST NOT emit
        RmEngageCaseActivity (Join) with actor=invitee_id from the Case Actor
        context.  The Accept(Invite) IS the engage decision; the BT records
        RM.ACCEPTED for the invitee without spoofing the invitee's identity.
        """
        from typing import Any, cast

        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )
        from vultron.core.models.vultron_types import VultronParticipant
        from vultron.core.states.rm import RM
        from vultron.core.states.roles import CVDRole

        dl = SqliteDataLayer("sqlite:///:memory:")
        invitee_id = "https://example.org/users/coordinator_rm2"
        invitee = as_Organization(id_=invitee_id)
        owner_id = "https://example.org/users/owner"
        case_manager_participant_id = (
            "https://example.org/cases/caseRM002/participants/case-manager"
        )
        case_manager_participant = VultronParticipant(
            id_=case_manager_participant_id,
            attributed_to=owner_id,
            context="https://example.org/cases/caseRM002",
            name="CaseManager",
            case_roles=[CVDRole.CASE_MANAGER],
        )
        case = VulnerabilityCase(
            id_="https://example.org/cases/caseRM002",
            name="TEST-RM-AUTO-ENGAGE",
            case_participants=[case_manager_participant_id],
            actor_participant_index={owner_id: case_manager_participant_id},
        )
        invite = rm_invite_to_case_activity(
            invitee,
            target=VulnerabilityCaseStub(id_=case.id_),
            actor=owner_id,
            id_="https://example.org/cases/caseRM002/invitations/1",
        )
        dl.create(invitee)
        dl.create(case_manager_participant)
        dl.create(case)
        dl.create(invite)

        accept = rm_accept_invite_to_case_activity(
            invite,
            actor=invitee_id,
        )
        event = make_payload(accept)

        AcceptInviteActorToCaseReceivedUseCase(
            dl, event, sync_port=MagicMock()
        ).execute()

        # PCR-07-008: no RmEngageCaseActivity (Join) with actor=invitee_id
        # should be queued — the BT records RM.ACCEPTED for the invitee
        # without spoofing the invitee's identity.
        outbox_items = dl.clone_for_actor(invitee_id).outbox_list()
        for item_id in outbox_items:
            candidate = cast(Any, dl.read(item_id))
            if candidate is not None and str(candidate.type_) == "Join":
                assert False, (
                    f"PCR-07-008 violation: RmEngageCaseActivity (Join) with "
                    f"actor={invitee_id!r} found in outbox — identity spoofing"
                )

        # The participant should be at RM.ACCEPTED (via BT).
        updated_case = cast(Any, dl.read(case.id_))
        participant_id = updated_case.actor_participant_index.get(invitee_id)
        assert participant_id is not None
        participant_obj = cast(Any, dl.get(id_=participant_id))
        assert participant_obj is not None
        latest_status = participant_obj.participant_statuses[-1]
        assert latest_status.rm_state == RM.ACCEPTED, (
            f"Expected RM.ACCEPTED after BT transition, "
            f"got {latest_status.rm_state}"
        )

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

        AcceptInviteActorToCaseReceivedUseCase(
            dl, event, sync_port=MagicMock()
        ).execute()

        case = dl.read(case.id_)
        assert case is not None
        case = cast(VulnerabilityCase, case)
        assert len(case.events) >= 1
        event_types = [e.event_type for e in case.events]
        assert "participant_joined" in event_types

    def test_accept_invite_backfills_canonical_ledger_from_genesis(
        self, make_payload
    ):
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.use_cases.triggers.sync import (
            commit_log_entry_trigger,
        )
        from vultron.core.models.replication_state import (
            VultronReplicationState,
        )
        from vultron.wire.as2.vocab.base.objects.actors import (
            as_Organization,
            as_Service,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        invitee_id = "https://example.org/users/late-joiner"
        case_actor_id = "https://example.org/actors/case-actor-lj1"
        invitee = as_Organization(id_=invitee_id)
        case_actor = as_Service(id_=case_actor_id, context="unused")
        case = VulnerabilityCase(
            id_="https://example.org/cases/caseLJ1",
            name="TEST-LATE-JOIN-BACKFILL",
        )
        case_actor.context = case.id_
        invite = rm_invite_to_case_activity(
            invitee,
            target=VulnerabilityCaseStub(id_=case.id_),
            actor=case_actor_id,
            id_=f"{case.id_}/invitations/1",
        )
        dl.create(invitee)
        dl.create(case_actor)
        dl.create(case)
        dl.create(invite)

        first = commit_log_entry_trigger(
            case_id=case.id_,
            object_id=f"{case.id_}/events/0",
            event_type="submit_report",
            actor_id=case_actor_id,
            dl=dl,
            payload_snapshot={"index": 0},
        )
        second = commit_log_entry_trigger(
            case_id=case.id_,
            object_id=f"{case.id_}/events/1",
            event_type="add_participant_status",
            actor_id=case_actor_id,
            dl=dl,
            payload_snapshot={"index": 1},
        )

        trigger_activity = MagicMock()
        trigger_activity.announce_vulnerability_case.return_value = (
            f"{case.id_}/announce/1"
        )
        sync_port = MagicMock()

        accept = rm_accept_invite_to_case_activity(invite, actor=invitee_id)
        event = make_payload(accept)
        AcceptInviteActorToCaseReceivedUseCase(
            dl,
            event,
            sync_port=sync_port,
            trigger_activity=trigger_activity,
        ).execute()

        announced_entries = [
            kwargs["entry"]
            for _, kwargs in sync_port.send_announce_log_entry.call_args_list
        ]
        assert [entry.log_index for entry in announced_entries] == [0, 1]
        assert announced_entries[0].entry_hash == first.entry_hash
        assert announced_entries[1].entry_hash == second.entry_hash

        state_id = VultronReplicationState(
            case_id=case.id_, peer_id=invitee_id
        ).id_
        state = cast(Any, dl.read(state_id))
        assert state is not None
        assert state.join_backfill_target_index == 1
        assert state.join_backfill_last_sent_index == 1
        assert state.join_backfill_complete is True

    def test_accept_invite_resumes_backfill_without_duplicate_entries(
        self, make_payload
    ):
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.models.replication_state import (
            VultronReplicationState,
        )
        from vultron.core.use_cases.triggers.sync import (
            commit_log_entry_trigger,
        )
        from vultron.wire.as2.vocab.base.objects.actors import (
            as_Organization,
            as_Service,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        invitee_id = "https://example.org/users/late-joiner-retry"
        case_actor_id = "https://example.org/actors/case-actor-lj2"
        invitee = as_Organization(id_=invitee_id)
        case_actor = as_Service(id_=case_actor_id, context="unused")
        case = VulnerabilityCase(
            id_="https://example.org/cases/caseLJ2",
            name="TEST-LATE-JOIN-RESUME",
        )
        case_actor.context = case.id_
        invite = rm_invite_to_case_activity(
            invitee,
            target=VulnerabilityCaseStub(id_=case.id_),
            actor=case_actor_id,
            id_=f"{case.id_}/invitations/1",
        )
        dl.create(invitee)
        dl.create(case_actor)
        dl.create(case)
        dl.create(invite)

        first = commit_log_entry_trigger(
            case_id=case.id_,
            object_id=f"{case.id_}/events/0",
            event_type="submit_report",
            actor_id=case_actor_id,
            dl=dl,
            payload_snapshot={"index": 0},
        )
        second = commit_log_entry_trigger(
            case_id=case.id_,
            object_id=f"{case.id_}/events/1",
            event_type="add_participant_status",
            actor_id=case_actor_id,
            dl=dl,
            payload_snapshot={"index": 1},
        )

        # Simulate interrupted run: participant already joined and first entry
        # already replayed, but join-time backfill not complete.
        state = VultronReplicationState(
            case_id=case.id_,
            peer_id=invitee_id,
            join_backfill_target_index=1,
            join_backfill_last_sent_index=0,
            join_backfill_complete=False,
        )
        dl.save(state)

        participant_case = cast(Any, dl.read(case.id_))
        participant_case.actor_participant_index[invitee_id] = (
            f"{case.id_}/participants/late-joiner-retry"
        )
        participant = cast(
            Any,
            dl.read(participant_case.actor_participant_index[invitee_id]),
        )
        if participant is None:
            from vultron.core.models.vultron_types import VultronParticipant

            participant = VultronParticipant(
                id_=participant_case.actor_participant_index[invitee_id],
                attributed_to=invitee_id,
                context=case.id_,
            )
            dl.create(participant)
        participant_case.case_participants.append(participant.id_)
        dl.save(participant_case)

        trigger_activity = MagicMock()
        trigger_activity.announce_vulnerability_case.return_value = (
            f"{case.id_}/announce/1"
        )
        sync_port = MagicMock()

        accept = rm_accept_invite_to_case_activity(invite, actor=invitee_id)
        event = make_payload(accept)
        AcceptInviteActorToCaseReceivedUseCase(
            dl,
            event,
            sync_port=sync_port,
            trigger_activity=trigger_activity,
        ).execute()

        announced_entries = [
            kwargs["entry"]
            for _, kwargs in sync_port.send_announce_log_entry.call_args_list
        ]
        assert [entry.log_index for entry in announced_entries] == [1]
        assert announced_entries[0].entry_hash == second.entry_hash
        assert all(
            entry.entry_hash != first.entry_hash for entry in announced_entries
        )

        state_id = VultronReplicationState(
            case_id=case.id_, peer_id=invitee_id
        ).id_
        updated_state = cast(Any, dl.read(state_id))
        assert updated_state.join_backfill_last_sent_index == 1
        assert updated_state.join_backfill_complete is True

    def test_accept_invite_resumes_when_participant_exists_without_marker(
        self, make_payload
    ):
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.models.vultron_types import VultronParticipant
        from vultron.core.use_cases.triggers.sync import (
            commit_log_entry_trigger,
        )
        from vultron.wire.as2.vocab.base.objects.actors import (
            as_Organization,
            as_Service,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        invitee_id = "https://example.org/users/late-joiner-nomarker"
        case_actor_id = "https://example.org/actors/case-actor-lj3"
        invitee = as_Organization(id_=invitee_id)
        case_actor = as_Service(id_=case_actor_id, context="unused")
        case = VulnerabilityCase(
            id_="https://example.org/cases/caseLJ3",
            name="TEST-LATE-JOIN-NO-MARKER",
        )
        case_actor.context = case.id_
        participant = VultronParticipant(
            id_=f"{case.id_}/participants/late-joiner-nomarker",
            attributed_to=invitee_id,
            context=case.id_,
        )
        case.case_participants = [participant.id_]
        case.actor_participant_index = {invitee_id: participant.id_}
        invite = rm_invite_to_case_activity(
            invitee,
            target=VulnerabilityCaseStub(id_=case.id_),
            actor=case_actor_id,
            id_=f"{case.id_}/invitations/1",
        )
        dl.create(invitee)
        dl.create(case_actor)
        dl.create(participant)
        dl.create(case)
        dl.create(invite)

        commit_log_entry_trigger(
            case_id=case.id_,
            object_id=f"{case.id_}/events/0",
            event_type="submit_report",
            actor_id=case_actor_id,
            dl=dl,
            payload_snapshot={"index": 0},
        )
        commit_log_entry_trigger(
            case_id=case.id_,
            object_id=f"{case.id_}/events/1",
            event_type="add_participant_status",
            actor_id=case_actor_id,
            dl=dl,
            payload_snapshot={"index": 1},
        )

        trigger_activity = MagicMock()
        trigger_activity.announce_vulnerability_case.return_value = (
            f"{case.id_}/announce/1"
        )
        sync_port = MagicMock()

        accept = rm_accept_invite_to_case_activity(invite, actor=invitee_id)
        event = make_payload(accept)
        AcceptInviteActorToCaseReceivedUseCase(
            dl,
            event,
            sync_port=sync_port,
            trigger_activity=trigger_activity,
        ).execute()

        announced_entries = [
            kwargs["entry"]
            for _, kwargs in sync_port.send_announce_log_entry.call_args_list
        ]
        assert [entry.log_index for entry in announced_entries] == [0, 1]

    def test_accept_invite_backfill_runs_when_announce_port_missing(
        self, make_payload
    ):
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.models.replication_state import (
            VultronReplicationState,
        )
        from vultron.core.use_cases.triggers.sync import (
            commit_log_entry_trigger,
        )
        from vultron.wire.as2.vocab.base.objects.actors import (
            as_Organization,
            as_Service,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        invitee_id = "https://example.org/users/late-joiner-noannounce"
        case_actor_id = "https://example.org/actors/case-actor-lj4"
        invitee = as_Organization(id_=invitee_id)
        case_actor = as_Service(id_=case_actor_id, context="unused")
        case = VulnerabilityCase(
            id_="https://example.org/cases/caseLJ4",
            name="TEST-LATE-JOIN-NO-ANNOUNCE",
        )
        case_actor.context = case.id_
        invite = rm_invite_to_case_activity(
            invitee,
            target=VulnerabilityCaseStub(id_=case.id_),
            actor=case_actor_id,
            id_=f"{case.id_}/invitations/1",
        )
        dl.create(invitee)
        dl.create(case_actor)
        dl.create(case)
        dl.create(invite)

        commit_log_entry_trigger(
            case_id=case.id_,
            object_id=f"{case.id_}/events/0",
            event_type="submit_report",
            actor_id=case_actor_id,
            dl=dl,
            payload_snapshot={"index": 0},
        )
        commit_log_entry_trigger(
            case_id=case.id_,
            object_id=f"{case.id_}/events/1",
            event_type="add_participant_status",
            actor_id=case_actor_id,
            dl=dl,
            payload_snapshot={"index": 1},
        )

        sync_port = MagicMock()
        accept = rm_accept_invite_to_case_activity(invite, actor=invitee_id)
        event = make_payload(accept)
        AcceptInviteActorToCaseReceivedUseCase(
            dl,
            event,
            sync_port=sync_port,
            trigger_activity=None,
        ).execute()

        announced_entries = [
            kwargs["entry"]
            for _, kwargs in sync_port.send_announce_log_entry.call_args_list
        ]
        assert [entry.log_index for entry in announced_entries] == [0, 1]

        state_id = VultronReplicationState(
            case_id=case.id_, peer_id=invitee_id
        ).id_
        state = cast(Any, dl.read(state_id))
        assert state is not None
        assert state.join_backfill_complete is True
