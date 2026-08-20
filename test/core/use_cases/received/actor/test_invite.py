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


def _seed_ledger_entry(
    dl,
    case_id: str,
    object_id: str,
    event_type: str,
    actor_id: str,
    payload_snapshot: dict | None = None,
):
    """Test-only helper: commit a ledger entry directly, bypassing BT validation.

    Replicates the chain-building logic from the now-deleted
    ``commit_log_entry_trigger`` for use in test setup fixtures.
    """
    from vultron.core.models.case_ledger import HashChainLedgerRecord
    from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
    from vultron.core.sync_helpers import _reconstruct_tail_hash

    tail_hash, tail_index = _reconstruct_tail_hash(case_id, dl)
    chain_entry = HashChainLedgerRecord(
        case_id=case_id,
        log_index=tail_index + 1,
        object_id=object_id,
        event_type=event_type,
        disposition="recorded",
        payload_snapshot=payload_snapshot or {},
        prev_log_hash=tail_hash,
    )
    entry = VultronCaseLedgerEntry(
        case_id=chain_entry.case_id,
        log_index=chain_entry.log_index,
        disposition=chain_entry.disposition,
        term=chain_entry.term,
        log_object_id=chain_entry.object_id,
        event_type=chain_entry.event_type,
        payload_snapshot=dict(chain_entry.payload_snapshot),
        prev_log_hash=chain_entry.prev_log_hash,
        entry_hash=chain_entry.entry_hash,
        reason_code=chain_entry.reason_code,
        reason_detail=chain_entry.reason_detail,
    )
    dl.save(entry)
    return entry


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

    def test_invite_receipt_logged_in_narrative_form(
        self, make_payload, caplog
    ):
        """The invitee logs the invite receipt at INFO (SL-04-001, AC-17)."""
        import logging

        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer("sqlite:///:memory:")
        invitee_id = "https://example.org/users/coordinator"
        sender_id = "https://example.org/users/owner"
        case_id = "https://example.org/cases/case1"

        invite = rm_invite_to_case_activity(
            as_Actor(id_=invitee_id),
            target=case_id,
            actor=sender_id,
            id_=f"{case_id}/invitations/narrative-1",
        )
        event = make_payload(invite)

        with caplog.at_level(logging.INFO):
            InviteActorToCaseReceivedUseCase(dl, event).execute()

        narrative = [
            r
            for r in caplog.records
            if "received case invite" in r.getMessage()
            and r.levelno == logging.INFO
        ]
        assert narrative, "Expected a narrative invite-receipt line at INFO"
        message = narrative[0].getMessage()
        assert (
            message == f"Actor '{invitee_id}' received case invite"
            f" for '{case_id}' from '{sender_id}'"
        )

    def test_invite_stub_awaiting_line_is_debug(self, make_payload, caplog):
        """The "Awaiting AnnounceVulnerabilityCase" note is DEBUG detail."""
        import logging

        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer("sqlite:///:memory:")
        invite = rm_invite_to_case_activity(
            as_Actor(id_="https://example.org/users/coordinator"),
            target="https://example.org/cases/case1",
            actor="https://example.org/users/owner",
            id_="https://example.org/cases/case1/invitations/narrative-2",
        )
        event = make_payload(invite)

        with caplog.at_level(logging.DEBUG):
            InviteActorToCaseReceivedUseCase(dl, event).execute()

        awaiting = [
            r
            for r in caplog.records
            if "Awaiting AnnounceVulnerabilityCase" in r.getMessage()
        ]
        assert awaiting, "Expected the case-stub awaiting log entry"
        assert all(r.levelno == logging.DEBUG for r in awaiting)

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

    def test_reject_invite_actor_to_case_commits_ledger_entry(
        self, make_payload
    ):
        """RejectInviteActorToCaseReceivedUseCase commits a CaseLedgerEntry (AC-3).

        Reject(Invite(actor, case)) carries the case reference in the nested
        Invite's ``target`` field (``inner_target_id``), not the top-level
        ``target`` of the Reject.  CM-11-003: use ``request.case_id`` which
        reads ``inner_target_id``.
        """
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.models.case_ledger_entry import (
            CaseLedgerEntry as WireCaseLedgerEntry,
        )
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        case_id = "https://example.org/cases/case-reject-ri1"
        case_actor_id = f"{case_id}/actor"
        invitee_id = "https://example.org/users/coordinator"

        case = as_VulnerabilityCase(
            id_=case_id,
            name="TEST-REJECT-INVITE",
            attributed_to=case_actor_id,
        )
        case_manager_participant = as_CaseParticipant(
            id_=f"{case_id}/participants/case-actor-p",
            attributed_to=case_actor_id,
            context=case_id,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        case.case_participants.append(case_manager_participant.id_)
        case.actor_participant_index[case_actor_id] = (
            case_manager_participant.id_
        )
        invite = rm_invite_to_case_activity(
            as_Actor(id_=invitee_id),
            target=VulnerabilityCaseStub(id_=case_id),
            actor=case_actor_id,
            id_=f"{case_id}/invitations/1",
        )
        dl.create(case_manager_participant)
        dl.create(case)
        dl.create(invite)

        reject = rm_reject_invite_to_case_activity(
            invite,
            actor=invitee_id,
        )
        event = make_payload(reject)

        assert (
            event.target_id is None
        ), "Precondition: Reject(Invite) has no top-level target"
        assert (
            event.case_id == case_id
        ), "Precondition: case_id resolves via inner_target_id"

        RejectInviteActorToCaseReceivedUseCase(
            dl,
            event.model_copy(update={"receiving_actor_id": case_actor_id}),
        ).execute()

        entries = [
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, WireCaseLedgerEntry) and e.case_id == case_id
        ]
        assert (
            len(entries) >= 1
        ), "Expected at least one CaseLedgerEntry after reject-invite"
        assert any(
            "reject" in e.event_type for e in entries
        ), f"Expected a reject-invite ledger entry; got: {[e.event_type for e in entries]}"

    def test_accept_invite_actor_to_case_adds_participant(
        self, monkeypatch, make_payload
    ):
        """AcceptInviteActorToCaseReceivedUseCase creates a as_CaseParticipant and adds them to the case."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        invitee_id = "https://example.org/users/coordinator"
        invitee = as_Organization(id_=invitee_id)
        case = as_VulnerabilityCase(
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
        case = cast(as_VulnerabilityCase, case)
        assert invitee_id in case.actor_participant_index

    def test_accept_invite_actor_to_case_records_active_embargo(
        self, monkeypatch, make_payload
    ):
        """AcceptInviteActorToCaseReceivedUseCase records the active embargo ID on the new participant (CM-10-001, CM-10-003)."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.states.em import EM
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization
        from vultron.wire.as2.vocab.objects.embargo_event import (
            as_EmbargoEvent,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        invitee_id = "https://example.org/users/coordinator"
        invitee = as_Organization(id_=invitee_id)
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/caseIA2",
            name="TEST-ACCEPT-INVITE-EMBARGO",
        )
        embargo = as_EmbargoEvent(
            id_="https://example.org/cases/caseIA2/embargo_events/e1",
            content="Active embargo",
            context=case.id_,
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
        case = cast(as_VulnerabilityCase, case)
        participant_id = case.actor_participant_index.get(invitee_id)
        assert participant_id is not None
        participant_obj = dl.get(id_=participant_id)
        assert participant_obj is not None
        participant_obj = cast(Any, participant_obj)
        assert embargo.id_ in participant_obj.accepted_embargo_ids

    def test_accept_invite_participant_recorded_at_rm_received(
        self, make_payload
    ):
        """Accepted invite records the participant at RM.RECEIVED only.

        CM-11-001: Accept(Invite) signals willingness to join; the CaseActor
        records RM.RECEIVED only.  The full triage cycle (VALID/ACCEPTED) is
        a distinct step run by the invitee after the case replica is delivered.
        """
        from typing import Any, cast

        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )
        from vultron.core.states.rm import RM

        dl = SqliteDataLayer("sqlite:///:memory:")
        invitee_id = "https://example.org/users/coordinator_rm1"
        invitee = as_Organization(id_=invitee_id)
        owner_id = "https://example.org/users/owner"
        case = as_VulnerabilityCase(
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

        AcceptInviteActorToCaseReceivedUseCase(
            dl, event, sync_port=MagicMock()
        ).execute()

        updated_case = cast(Any, dl.read(case.id_))
        participant_id = updated_case.actor_participant_index.get(invitee_id)
        participant_obj = cast(Any, dl.get(id_=participant_id))
        rm_states = [s.rm.state for s in participant_obj.participant_statuses]
        assert RM.VALID not in rm_states, "CM-11-001: no VALID at invite time"
        assert (
            RM.ACCEPTED not in rm_states
        ), "CM-11-001: no ACCEPTED at invite time"
        latest_status = participant_obj.participant_statuses[-1]
        assert latest_status.rm.state == RM.RECEIVED

    def test_accept_invite_no_identity_spoofing(self, make_payload):
        """PCR-07-008: AcceptInviteActorToCaseReceivedUseCase MUST NOT emit
        RmEngageCaseActivity (Join) with actor=invitee_id from the Case Actor
        context.  The BT records RM.RECEIVED for the invitee without spoofing
        the invitee's identity (CM-11-001, PCR-08-010).
        """
        from typing import Any, cast

        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )
        from vultron.core.models.vultron_types import VultronParticipant
        from vultron.core.states.rm import RM
        from vultron.enums.roles import CVDRole

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
        case = as_VulnerabilityCase(
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
        # should be queued — the BT records RM.RECEIVED for the invitee
        # without spoofing the invitee's identity.
        outbox_items = dl.clone_for_actor(invitee_id).outbox_list()
        for item_id in outbox_items:
            candidate = cast(Any, dl.read(item_id))
            if candidate is not None and str(candidate.type_) == "Join":
                assert False, (
                    f"PCR-07-008 violation: RmEngageCaseActivity (Join) with "
                    f"actor={invitee_id!r} found in outbox — identity spoofing"
                )

        # The participant should be at RM.RECEIVED only (CM-11-001).
        updated_case = cast(Any, dl.read(case.id_))
        participant_id = updated_case.actor_participant_index.get(invitee_id)
        assert participant_id is not None
        participant_obj = cast(Any, dl.get(id_=participant_id))
        assert participant_obj is not None
        rm_states = [s.rm.state for s in participant_obj.participant_statuses]
        assert RM.VALID not in rm_states, "CM-11-001: no VALID at invite time"
        assert (
            RM.ACCEPTED not in rm_states
        ), "CM-11-001: no ACCEPTED at invite time"
        latest_status = participant_obj.participant_statuses[-1]
        assert latest_status.rm.state == RM.RECEIVED, (
            f"Expected RM.RECEIVED after Accept(Invite) (CM-11-001), "
            f"got {latest_status.rm.state}"
        )

    def test_accept_invite_actor_to_case_records_case_event(
        self, monkeypatch, make_payload
    ):
        """AcceptInviteActorToCaseReceivedUseCase commits a canonical
        as_CaseLedgerEntry with event_type 'accept_invite_actor_to_case'
        (CM-02-009).

        record_event('participant_joined') was removed in #789; the trust
        guarantee now lives in as_CaseLedgerEntry.received_at written by
        CommitCaseLedgerEntryNode.
        """
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization
        from vultron.core.models.case_ledger_entry import (
            CaseLedgerEntry as WireCaseLedgerEntry,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        invitee_id = "https://example.org/users/coordinator"
        case_actor_id = "https://example.org/cases/caseIA3/actor"
        invitee = as_Organization(id_=invitee_id)
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/caseIA3",
            name="TEST-ACCEPT-INVITE-EVENT",
            attributed_to=case_actor_id,
        )
        invite = rm_invite_to_case_activity(
            invitee,
            target=VulnerabilityCaseStub(id_=case.id_),
            actor="https://example.org/users/owner",
            id_="https://example.org/cases/caseIA3/invitations/1",
        )
        dl.create(invitee)
        dl.create(case)
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )
        from vultron.wire.as2.vocab.base.objects.actors import as_Service

        dl.create(as_Service(id_=case_actor_id, context=case.id_))
        case_manager_participant = as_CaseParticipant(
            id_=f"{case.id_}/participants/case-actor-p",
            attributed_to=case_actor_id,
            context=case.id_,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        dl.create(case_manager_participant)
        case.case_participants.append(case_manager_participant.id_)
        case.actor_participant_index[case_actor_id] = (
            case_manager_participant.id_
        )
        dl.save(case)
        dl.create(invite)

        accept = rm_accept_invite_to_case_activity(
            invite,
            actor=invitee_id,
        )

        event = make_payload(accept)

        AcceptInviteActorToCaseReceivedUseCase(
            dl, event, sync_port=MagicMock()
        ).execute()

        entries = [
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, WireCaseLedgerEntry) and e.case_id == case.id_
        ]
        assert len(entries) >= 1
        assert any(
            e.event_type == "accept_invite_actor_to_case" for e in entries
        )

    def test_accept_invite_backfills_canonical_ledger_from_genesis(
        self, make_payload
    ):
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.models.replication_state import (
            VultronReplicationState,
        )
        from vultron.wire.as2.vocab.base.objects.actors import (
            as_Organization,
            as_Service,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        invitee_id = "https://example.org/users/late-joiner"
        case_actor_id = "https://example.org/actors/case-actor-lj1"
        invitee = as_Organization(id_=invitee_id)
        case_actor = as_Service(id_=case_actor_id, context="unused")
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/caseLJ1",
            name="TEST-LATE-JOIN-BACKFILL",
            attributed_to=case_actor_id,
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
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

        case_manager_participant = as_CaseParticipant(
            id_=f"{case.id_}/participants/case-actor-p",
            attributed_to=case_actor_id,
            context=case.id_,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        dl.create(case_manager_participant)
        case.case_participants.append(case_manager_participant.id_)
        case.actor_participant_index[case_actor_id] = (
            case_manager_participant.id_
        )
        dl.save(case)
        dl.create(invite)

        first = _seed_ledger_entry(
            dl,
            case_id=case.id_,
            object_id=f"{case.id_}/events/0",
            event_type="submit_report",
            actor_id=case_actor_id,
            payload_snapshot={"index": 0},
        )
        second = _seed_ledger_entry(
            dl,
            case_id=case.id_,
            object_id=f"{case.id_}/events/1",
            event_type="add_participant_status",
            actor_id=case_actor_id,
            payload_snapshot={"index": 1},
        )

        trigger_activity = MagicMock()
        trigger_activity.announce_vulnerability_case.return_value = (
            f"{case.id_}/announce/1"
        )
        trigger_activity.add_participant_to_case.return_value = (
            f"{case.id_}/activities/add-participant-1"
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

        announced_log_indices = [
            kwargs["entry"].log_index
            for _, kwargs in sync_port.send_announce_log_entry.call_args_list
        ]
        announced_entries = [
            kwargs["entry"]
            for _, kwargs in sync_port.send_announce_log_entry.call_args_list
        ]
        # Entry 2 (accept_invite): committed before invitee is registered —
        #   fan-out does NOT include the invitee.
        # Entry 3 (add_case_participant): committed AFTER invitee is persisted —
        #   fan-out INCLUDES the invitee (they are now a case participant).
        # Backfill: runs after invitee is registered with post-commit target (3),
        #   sending entries 0, 1, 2, and 3.
        # So invitee receives: [3 (fan-out), 0, 1, 2, 3 (backfill)].
        assert announced_log_indices == [3, 0, 1, 2, 3]
        # First backfill entry (index 1 in announced list) is the seeded entry 0.
        assert announced_entries[1].entry_hash == first.entry_hash
        assert announced_entries[2].entry_hash == second.entry_hash

        state_id = VultronReplicationState(
            case_id=case.id_, peer_id=invitee_id
        ).id_
        state = cast(Any, dl.read(state_id))
        assert state is not None
        # accept_invite (2) and add_case_participant (3) are both committed;
        # backfill target is the post-commit last entry (3).
        assert state.join_backfill_target_index == 3
        assert state.join_backfill_last_sent_index == 3
        assert state.join_backfill_complete is True

    def test_accept_invite_resumes_backfill_without_duplicate_entries(
        self, make_payload
    ):
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.models.replication_state import (
            VultronReplicationState,
        )
        from vultron.wire.as2.vocab.base.objects.actors import (
            as_Organization,
            as_Service,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        invitee_id = "https://example.org/users/late-joiner-retry"
        case_actor_id = "https://example.org/actors/case-actor-lj2"
        invitee = as_Organization(id_=invitee_id)
        case_actor = as_Service(id_=case_actor_id, context="unused")
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/caseLJ2",
            name="TEST-LATE-JOIN-RESUME",
            attributed_to=case_actor_id,
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
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

        case_manager_participant = as_CaseParticipant(
            id_=f"{case.id_}/participants/case-actor-p",
            attributed_to=case_actor_id,
            context=case.id_,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        dl.create(case_manager_participant)
        case.case_participants.append(case_manager_participant.id_)
        case.actor_participant_index[case_actor_id] = (
            case_manager_participant.id_
        )
        dl.save(case)
        dl.create(invite)

        first = _seed_ledger_entry(
            dl,
            case_id=case.id_,
            object_id=f"{case.id_}/events/0",
            event_type="submit_report",
            actor_id=case_actor_id,
            payload_snapshot={"index": 0},
        )
        second = _seed_ledger_entry(
            dl,
            case_id=case.id_,
            object_id=f"{case.id_}/events/1",
            event_type="add_participant_status",
            actor_id=case_actor_id,
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
        trigger_activity.add_participant_to_case.return_value = (
            f"{case.id_}/activities/add-participant-1"
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
        # Commit-first ordering: CommitCaseLedgerEntryNode fans out the new
        # accept_invite entry (2) first (invitee already registered), then
        # backfill resumes from the pre-commit target index and sends entry 1.
        assert [entry.log_index for entry in announced_entries] == [2, 1]
        assert announced_entries[1].entry_hash == second.entry_hash
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
        from vultron.wire.as2.vocab.base.objects.actors import (
            as_Organization,
            as_Service,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        invitee_id = "https://example.org/users/late-joiner-nomarker"
        case_actor_id = "https://example.org/actors/case-actor-lj3"
        invitee = as_Organization(id_=invitee_id)
        case_actor = as_Service(id_=case_actor_id, context="unused")
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/caseLJ3",
            name="TEST-LATE-JOIN-NO-MARKER",
            attributed_to=case_actor_id,
        )
        case_actor.context = case.id_
        participant = VultronParticipant(
            id_=f"{case.id_}/participants/late-joiner-nomarker",
            attributed_to=invitee_id,
            context=case.id_,
        )
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

        case_manager_participant = as_CaseParticipant(
            id_=f"{case.id_}/participants/case-actor-p",
            attributed_to=case_actor_id,
            context=case.id_,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        case.case_participants = [
            participant.id_,
            case_manager_participant.id_,
        ]
        case.actor_participant_index = {
            invitee_id: participant.id_,
            case_actor_id: case_manager_participant.id_,
        }
        invite = rm_invite_to_case_activity(
            invitee,
            target=VulnerabilityCaseStub(id_=case.id_),
            actor=case_actor_id,
            id_=f"{case.id_}/invitations/1",
        )
        dl.create(invitee)
        dl.create(case_actor)
        dl.create(participant)
        dl.create(case_manager_participant)
        dl.create(case)
        dl.create(invite)

        _seed_ledger_entry(
            dl,
            case_id=case.id_,
            object_id=f"{case.id_}/events/0",
            event_type="submit_report",
            actor_id=case_actor_id,
            payload_snapshot={"index": 0},
        )
        _seed_ledger_entry(
            dl,
            case_id=case.id_,
            object_id=f"{case.id_}/events/1",
            event_type="add_participant_status",
            actor_id=case_actor_id,
            payload_snapshot={"index": 1},
        )

        trigger_activity = MagicMock()
        trigger_activity.announce_vulnerability_case.return_value = (
            f"{case.id_}/announce/1"
        )
        trigger_activity.add_participant_to_case.return_value = (
            f"{case.id_}/activities/add-participant-1"
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
        # Commit-first ordering: CommitCaseLedgerEntryNode fans out the new
        # accept_invite entry (2) first (invitee already registered), then
        # backfill sends entries 0 and 1 that the invitee missed.
        assert [entry.log_index for entry in announced_entries] == [2, 0, 1]

    def test_accept_invite_backfill_runs_when_announce_port_missing(
        self, make_payload
    ):
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.models.replication_state import (
            VultronReplicationState,
        )
        from vultron.wire.as2.vocab.base.objects.actors import (
            as_Organization,
            as_Service,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        invitee_id = "https://example.org/users/late-joiner-noannounce"
        case_actor_id = "https://example.org/actors/case-actor-lj4"
        invitee = as_Organization(id_=invitee_id)
        case_actor = as_Service(id_=case_actor_id, context="unused")
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/caseLJ4",
            name="TEST-LATE-JOIN-NO-ANNOUNCE",
            attributed_to=case_actor_id,
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
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

        case_manager_participant = as_CaseParticipant(
            id_=f"{case.id_}/participants/case-actor-p",
            attributed_to=case_actor_id,
            context=case.id_,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        dl.create(case_manager_participant)
        case.case_participants.append(case_manager_participant.id_)
        case.actor_participant_index[case_actor_id] = (
            case_manager_participant.id_
        )
        dl.save(case)
        dl.create(invite)

        _seed_ledger_entry(
            dl,
            case_id=case.id_,
            object_id=f"{case.id_}/events/0",
            event_type="submit_report",
            actor_id=case_actor_id,
            payload_snapshot={"index": 0},
        )
        _seed_ledger_entry(
            dl,
            case_id=case.id_,
            object_id=f"{case.id_}/events/1",
            event_type="add_participant_status",
            actor_id=case_actor_id,
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
        # Backfill sends entries 0 and 1; CommitCaseLedgerEntryNode fans out
        # the new accept_invite entry (2) to all participants via sync_port.
        # This holds even when trigger_activity (announce port) is missing.
        assert [entry.log_index for entry in announced_entries] == [0, 1, 2]

        state_id = VultronReplicationState(
            case_id=case.id_, peer_id=invitee_id
        ).id_
        state = cast(Any, dl.read(state_id))
        assert state is not None
        assert state.join_backfill_complete is True


class TestAcceptInviteRolesAC4:
    """AC-4: CreateInviteeParticipantAtReceivedNode reads roles from Invite."""

    def test_roles_from_invite_set_on_participant(self, make_payload):
        """AC-4: Accept(Invite) causes new participant to inherit roles from Invite."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        invitee_id = "https://example.org/users/vendor2"
        invitee = as_Organization(id_=invitee_id)
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/ac4-test",
            name="AC-4 roles test",
        )
        invite = rm_invite_to_case_activity(
            invitee,
            target=VulnerabilityCaseStub(id_=case.id_),
            actor="https://example.org/users/owner",
            id_="https://example.org/cases/ac4-test/invitations/1",
            roles=["vendor"],
        )
        dl.create(invitee)
        dl.create(case)
        dl.create(invite)

        accept = rm_accept_invite_to_case_activity(invite, actor=invitee_id)
        event = make_payload(accept)
        AcceptInviteActorToCaseReceivedUseCase(
            dl, event, sync_port=MagicMock()
        ).execute()

        reloaded_case = cast(Any, dl.read(case.id_))
        participant_id = reloaded_case.actor_participant_index.get(invitee_id)
        assert (
            participant_id is not None
        ), "invitee must be registered as participant"
        participant = cast(Any, dl.get(id_=participant_id))
        assert participant is not None
        assert (
            CVDRole.VENDOR in participant.case_roles
        ), "AC-4: participant case_roles must include VENDOR from Invite"

    def test_no_roles_invite_gives_empty_case_roles(self, make_payload):
        """AC-4 negative: Invite without roles gives participant case_roles=[]."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        invitee_id = "https://example.org/users/vendor3"
        invitee = as_Organization(id_=invitee_id)
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/ac4-neg",
            name="AC-4 negative",
        )
        invite = rm_invite_to_case_activity(
            invitee,
            target=VulnerabilityCaseStub(id_=case.id_),
            actor="https://example.org/users/owner",
            id_="https://example.org/cases/ac4-neg/invitations/1",
        )
        dl.create(invitee)
        dl.create(case)
        dl.create(invite)

        accept = rm_accept_invite_to_case_activity(invite, actor=invitee_id)
        event = make_payload(accept)
        AcceptInviteActorToCaseReceivedUseCase(
            dl, event, sync_port=MagicMock()
        ).execute()

        reloaded_case = cast(Any, dl.read(case.id_))
        participant_id = reloaded_case.actor_participant_index.get(invitee_id)
        participant = cast(Any, dl.get(id_=participant_id))
        assert participant is not None
        assert (
            participant.case_roles == []
        ), "Participant with no-roles invite must have empty case_roles"
