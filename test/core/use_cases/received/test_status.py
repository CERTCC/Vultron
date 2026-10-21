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
"""Tests for status-related use-case classes."""

import json
from typing import cast

import pytest

from test.core.use_cases.received.conftest import (
    queued_bodies,
    seed_case_manager_participant,
    seed_case_participant,
    seed_store_owner_as_case_manager,
)
from test.support.received import received_event
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIIngressAdapter,
)
from vultron.core.behaviors.sender_entitlement import (
    AddresseeSide,
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.models.actor import VultronService
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.dimensions import (
    EmDimension,
    RmDimension,
)
from vultron.core.models.events.status import (
    AddParticipantStatusToParticipantReceivedEvent,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.core.use_cases.received.status import (
    AddCaseStatusToCaseReceivedUseCase,
    AddParticipantStatusToParticipantReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronBTInternalError
from vultron.wire.as2.factories import (
    add_status_to_case_activity,
    add_status_to_participant_activity,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import (
    as_CaseStatus,
    as_ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

#: The CASE_MANAGER of the replica tests below: the one sender a replica
#: admits an Add(CaseStatus) from (RSH-04-005).
_CASE_MANAGER_ID = "https://example.org/users/case-manager"


def _seed_replica(dl: SqliteDataLayer, case: as_VulnerabilityCase) -> None:
    """Make *dl* a participant replica of *case*, whose CASE_MANAGER is
    ``_CASE_MANAGER_ID``, so a received Add(CaseStatus) reaches its guards."""
    seed_case_manager_participant(dl, case, _CASE_MANAGER_ID)
    seed_case_participant(dl, case, cast(str, dl.actor_id))


class TestStatusUseCases:
    """Tests for case status and participant status handlers."""

    def test_add_case_status_from_the_case_manager_writes_nothing(
        self, monkeypatch, make_payload
    ):
        """A replica admits the CASE_MANAGER's Add(CaseStatus) and writes
        nothing on receipt: it takes the status from the ledger fan-out
        (RSH-04-005, RSH-08-003)."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_cs3",
            name="Add Status Case",
            attributed_to=_CASE_MANAGER_ID,
        )
        status = as_CaseStatus(
            id_="https://example.org/cases/case_cs3/statuses/s3",
            context=case.id_,
        )
        seed_case_manager_participant(dl, case, _CASE_MANAGER_ID)
        seed_case_participant(dl, case, dl.actor_id)
        dl.create(case)
        dl.create(status)
        before = [getattr(s, "id_", s) for s in case.case_statuses]

        activity = add_status_to_case_activity(
            status,
            target=case,
            actor=_CASE_MANAGER_ID,
            to=[dl.actor_id],
        )
        event = make_payload(activity)

        result = AddCaseStatusToCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        stored = cast(as_VulnerabilityCase, dl.read(case.id_))
        status_ids = [getattr(s, "id_", s) for s in stored.case_statuses]
        assert status_ids == before
        assert result.disposition == HandlerDisposition.APPLIED
        assert dl.list_objects("CaseLedgerEntry") == []
        assert queued_bodies(dl) == []

        # HP-01-003: an Add of a status the replica already holds (taken
        # from the ledger) is a no-op, not a refusal.
        stored.case_statuses.append(status)  # type: ignore[arg-type]
        dl.save(stored)
        again = AddCaseStatusToCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()
        assert again.disposition == HandlerDisposition.SKIPPED

    @pytest.mark.spec("HP-08-007")
    @pytest.mark.parametrize(
        "stored_for_other_case",
        [False, True],
        ids=["carried-names-other-case", "stored-for-other-case"],
    )
    def test_add_case_status_of_another_case_is_refused(
        self, make_payload, stored_for_other_case
    ):
        """An Add(CaseStatus) whose status belongs to another case is
        refused before the commit: the target case gains no status and no
        entry is written.  The stored-for-other-case arm is what the inbox
        routes when the status id names a status the receiver holds for
        another case, since its rebuild prefers the stored copy (#4831)."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_cs3x",
            name="Add Status Case",
            attributed_to="https://test.example/api/v2/actors/test-actor",
        )
        other_case_id = "https://example.org/cases/case_cs3y"
        status_id = f"{other_case_id}/statuses/s1"
        # A participant replica, the only receiver of an Add(CaseStatus),
        # from its CASE_MANAGER (RSH-04-005).
        _seed_replica(dl, case)
        dl.create(case)
        if stored_for_other_case:
            dl.create(as_CaseStatus(id_=status_id, context=other_case_id))
        carried = as_CaseStatus(
            id_=status_id,
            context=case.id_ if stored_for_other_case else other_case_id,
        )
        entries_before = len(dl.list_objects("CaseLedgerEntry"))

        result = AddCaseStatusToCaseReceivedUseCase(
            dl,
            make_payload(
                add_status_to_case_activity(
                    carried,
                    target=case,
                    actor=_CASE_MANAGER_ID,
                    to=[dl.actor_id],
                )
            ),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition == HandlerDisposition.REFUSED
        # Refused for the status's case, not for its sender (RSH-04-005).
        assert "HP-01-006" not in (result.reason or ""), result.reason
        refreshed = cast(as_VulnerabilityCase, dl.read(case.id_))
        assert status_id not in [
            getattr(s, "id_", s) for s in refreshed.case_statuses
        ]
        assert len(dl.list_objects("CaseLedgerEntry")) == entries_before

    def test_add_case_status_blocks_invalid_em_transition(
        self, monkeypatch, make_payload
    ):
        """Invalid EM transition is blocked; status is not appended."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_em_guard",
            name="EM Guard Test Case",
        )
        # Seed an existing status with EM.NONE (the initial embargo state)
        initial_status = as_CaseStatus(
            id_="https://example.org/cases/case_em_guard/statuses/s_init",
            context=case.id_,
            em=EmDimension(state=EM.NONE),
        )
        case.case_statuses.append(initial_status)  # type: ignore[arg-type]
        _seed_replica(dl, case)
        dl.create(case)

        # Try to add a status with EM.ACTIVE — invalid: NONE → ACTIVE
        # skips the required PROPOSED intermediate state
        bad_status = as_CaseStatus(
            id_="https://example.org/cases/case_em_guard/statuses/s_bad",
            context=case.id_,
            em=EmDimension(state=EM.ACTIVE),
        )
        dl.create(bad_status)

        activity = add_status_to_case_activity(
            bad_status,
            target=case,
            actor=_CASE_MANAGER_ID,
            to=[dl.actor_id],
        )
        event = make_payload(activity)

        result = AddCaseStatusToCaseReceivedUseCase(
            dl, event, wire_render_port=As2WireRenderAdapter()
        ).execute()

        updated_case = dl.read(case.id_)
        assert updated_case is not None
        updated_case = cast(as_VulnerabilityCase, updated_case)
        status_ids = [getattr(s, "id_", s) for s in updated_case.case_statuses]
        assert bad_status.id_ not in status_ids, (
            "Bad status should not have been appended"
        )
        assert result.disposition == HandlerDisposition.REFUSED
        # Refused for its EM claim, not for its sender (RSH-04-005).
        assert "HP-01-006" not in (result.reason or ""), result.reason
        assert result.reason

    @pytest.mark.spec("CLP-05-001")
    def test_refused_case_status_emits_no_processing_fault(self, make_payload):
        """A refused CaseStatus is answered by no ProcessingFault.

        A guard's refusal is "received and understood but declined", so its
        one answer is the refusal notice (CLP-05-001, MSM-05-001); the
        notice itself is driven end to end in ``test_refusal_notice.py``.
        """
        from unittest.mock import MagicMock

        receiver_id = "https://test.example/api/v2/actors/test-actor"
        sender_id = _CASE_MANAGER_ID
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=receiver_id,
        )
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_fault_cs",
            name="Fault Test Case",
        )
        initial_status = as_CaseStatus(
            id_="https://example.org/cases/case_fault_cs/statuses/s_init",
            context=case.id_,
            em=EmDimension(state=EM.NONE),
        )
        case.case_statuses.append(initial_status)  # type: ignore[arg-type]
        # The sender holds standing, so its content is refused, not it.
        _seed_replica(dl, case)
        dl.create(case)

        bad_status = as_CaseStatus(
            id_="https://example.org/cases/case_fault_cs/statuses/s_bad",
            context=case.id_,
            em=EmDimension(state=EM.ACTIVE),
        )
        dl.create(bad_status)

        activity = add_status_to_case_activity(
            bad_status, target=case, actor=sender_id, to=[receiver_id]
        )
        event = make_payload(activity)
        event = event.model_copy(update={"receiving_actor_id": receiver_id})

        mock_trigger = MagicMock()
        mock_trigger.emit_processing_fault.return_value = "urn:uuid:fault-1"

        result = AddCaseStatusToCaseReceivedUseCase(
            dl,
            event,
            trigger_activity=mock_trigger,
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert result.disposition == HandlerDisposition.REFUSED
        # Refused for its EM claim, not for its sender (RSH-04-005).
        assert "HP-01-006" not in (result.reason or ""), result.reason
        mock_trigger.emit_processing_fault.assert_not_called()

    def test_refused_case_status_without_trigger_activity_queues_nothing(
        self, make_payload
    ):
        """With no trigger port the refusal still stands and nothing is queued."""
        receiver_id = "https://test.example/api/v2/actors/test-actor"
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=receiver_id,
        )
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_fault_cs2",
            name="Fault No-Trigger Case",
        )
        initial_status = as_CaseStatus(
            id_="https://example.org/cases/case_fault_cs2/statuses/s_init",
            context=case.id_,
            em=EmDimension(state=EM.NONE),
        )
        case.case_statuses.append(initial_status)  # type: ignore[arg-type]
        _seed_replica(dl, case)
        dl.create(case)

        bad_status = as_CaseStatus(
            id_="https://example.org/cases/case_fault_cs2/statuses/s_bad",
            context=case.id_,
            em=EmDimension(state=EM.ACTIVE),
        )
        dl.create(bad_status)

        activity = add_status_to_case_activity(
            bad_status,
            target=case,
            actor=_CASE_MANAGER_ID,
            to=["https://test.example/api/v2/actors/test-actor"],
        )
        event = make_payload(activity)

        result = AddCaseStatusToCaseReceivedUseCase(
            dl,
            event,
            trigger_activity=None,
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert result.disposition == HandlerDisposition.REFUSED
        # Refused for its EM claim, not for its sender (RSH-04-005).
        assert "HP-01-006" not in (result.reason or ""), result.reason
        assert queued_bodies(dl) == []

    @pytest.mark.spec("CLP-05-001")
    def test_refused_participant_status_emits_no_processing_fault(
        self, make_payload
    ):
        """A refused ParticipantStatus is answered by no ProcessingFault.

        A guard's refusal is "received and understood but declined", so its
        one answer is the refusal notice (CLP-05-001, MSM-05-001).
        """
        from unittest.mock import MagicMock

        receiver_id = "https://example.org/users/vendor-ps-fault"
        sender_id = "https://example.org/users/vendor-ps-fault"
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=receiver_id,
        )

        case_id = "https://example.org/cases/case_ps_fault"
        participant = as_CaseParticipant(
            id_=f"{case_id}/participants/p",
            context=case_id,
            attributed_to=sender_id,
        )
        pstatus = as_ParticipantStatus(
            id_=f"{case_id}/participants/p/statuses/s1",
            context=case_id,
            rm=RmDimension(state=RM.ACCEPTED),
        )
        participant.participant_statuses.append(pstatus)
        dl.create(participant)
        dl.create(pstatus)

        case = as_VulnerabilityCase(
            id_=case_id,
            name="PS Fault Test Case",
        )
        case.case_participants.append(participant.id_)
        case.actor_participant_index[sender_id] = participant.id_
        dl.create(case)

        dup_status = as_ParticipantStatus(
            id_=f"{case_id}/participants/p/statuses/s_dup_closed",
            context=case_id,
            rm=RmDimension(state=RM.VALID),
        )
        dl.create(dup_status)

        activity = add_status_to_participant_activity(
            dup_status,
            target=participant,
            actor=sender_id,
            to=[receiver_id],
            context=case,
        )
        event = make_payload(activity, receiving_actor_id=receiver_id)

        mock_trigger = MagicMock()
        mock_trigger.emit_processing_fault.return_value = "urn:uuid:fault-2"

        result = AddParticipantStatusToParticipantReceivedUseCase(
            dl,
            event,
            trigger_activity=mock_trigger,
            wire_render_port=As2WireRenderAdapter(),
        ).execute()
        assert result.disposition == HandlerDisposition.REFUSED

        mock_trigger.emit_processing_fault.assert_not_called()

    @pytest.mark.spec("HP-01-003")
    @pytest.mark.spec("RSH-09-008")
    def test_wholly_refused_participant_status_returns_refused(
        self, make_payload
    ):
        """A refused status returns REFUSED (AC-2, ISSUE-3199, #2255).

        When CheckParticipantStatusAcceptableNode refuses the status, execute()
        returns ``HandlerResult.refused`` so that the inbox DispatchNode writes
        "rejected" to KEY_OUTCOME_STATUS and surfaces a rejected InboxOutcome
        rather than a silent 202 Accepted / processed (HP-01-003).
        """
        # The guard runs at the CASE_MANAGER: a replica takes the update
        # from the CASE_MANAGER alone and refuses this sender first
        # (PCR-03-001).
        receiver_id = "https://example.org/users/case-manager-ps-ac2"
        sender_id = "https://example.org/users/vendor-ps-ac2"
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=receiver_id)

        case_id = "https://example.org/cases/case_ps_ac2"
        participant = as_CaseParticipant(
            id_=f"{case_id}/participants/p",
            context=case_id,
            attributed_to=sender_id,
        )
        # Seed participant at RM.ACCEPTED: a backward VALID is refused
        pstatus = as_ParticipantStatus(
            id_=f"{case_id}/participants/p/statuses/s1",
            context=case_id,
            rm=RmDimension(state=RM.ACCEPTED),
        )
        participant.participant_statuses.append(pstatus)
        dl.create(participant)
        dl.create(pstatus)

        case = as_VulnerabilityCase(
            id_=case_id,
            name="AC-2 Rejection Test Case",
        )
        case.case_participants.append(participant.id_)
        case.actor_participant_index[sender_id] = participant.id_
        seed_case_manager_participant(dl, case, receiver_id)
        dl.create(case)

        # A backward RM — the guard refuses the whole status
        dup_status = as_ParticipantStatus(
            id_=f"{case_id}/participants/p/statuses/s_dup",
            context=case_id,
            rm=RmDimension(state=RM.VALID),
        )
        dl.create(dup_status)

        activity = add_status_to_participant_activity(
            dup_status,
            target=participant,
            actor=sender_id,
            to=[receiver_id],
            context=case,
        )
        event = make_payload(activity, receiving_actor_id=receiver_id)

        result = AddParticipantStatusToParticipantReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason is not None
        assert "ParticipantStatus refused" in result.reason
        assert "rm: ACCEPTED → VALID moves RM backwards" in result.reason

    def test_add_case_status_refuses_an_em_move_the_register_has_not_made(
        self, monkeypatch, make_payload
    ):
        """A status asserting EM other than the case's derived EM is refused.

        EM is derived from the embargo register and is never moved by a
        status (ADR-0122, RSH-09-005): even ``NONE → PROPOSED``, a move the
        EM machine once allowed, refuses the whole status, and the case's EM
        is unchanged.
        """
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_em_valid",
            name="EM Valid Transition Case",
        )
        initial_status = as_CaseStatus(
            id_="https://example.org/cases/case_em_valid/statuses/s_init",
            context=case.id_,
            em=EmDimension(state=EM.NONE),
        )
        case.case_statuses.append(initial_status)  # type: ignore[arg-type]
        _seed_replica(dl, case)
        dl.create(case)

        # NONE → PROPOSED with no proposal in the register
        asserted_status = as_CaseStatus(
            id_="https://example.org/cases/case_em_valid/statuses/s_asserted",
            context=case.id_,
            em=EmDimension(state=EM.PROPOSED),
        )
        dl.create(asserted_status)

        activity = add_status_to_case_activity(
            asserted_status,
            target=case,
            actor=_CASE_MANAGER_ID,
            to=["https://test.example/api/v2/actors/test-actor"],
        )
        event = make_payload(activity)

        result = AddCaseStatusToCaseReceivedUseCase(
            dl, event, wire_render_port=As2WireRenderAdapter()
        ).execute()

        updated_case = dl.read(case.id_)
        assert updated_case is not None
        updated_case = cast(as_VulnerabilityCase, updated_case)
        status_ids = [getattr(s, "id_", s) for s in updated_case.case_statuses]
        assert asserted_status.id_ not in status_ids
        assert result.disposition == HandlerDisposition.REFUSED
        # Refused for its EM claim, not for its sender (RSH-04-005).
        assert "HP-01-006" not in (result.reason or ""), result.reason
        assert updated_case.em_state == EM.NONE
        assert updated_case.current_status.em.state == EM.NONE

    def test_add_participant_status_to_participant_appends_status(
        self, monkeypatch, make_payload
    ):
        """add_participant_status_to_participant appends status to participant."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://example.org/users/vendor",
        )
        # RSH-08-003/#3814: the append is now CASE_MANAGER-gated.  The subject
        # participant is the store's own actor, so holding CASE_MANAGER lets
        # the gated write run while leaving it a non-owner (so the adoption
        # call-out still withholds, keeping the SKIPPED assertion below).
        participant = as_CaseParticipant(
            id_="https://example.org/cases/case_ps2/participants/p2",
            context="https://example.org/cases/case_ps2",
            attributed_to="https://example.org/users/vendor",
            case_roles=[CVDRole.CASE_MANAGER],
        )
        pstatus = as_ParticipantStatus(
            id_="https://example.org/cases/case_ps2/participants/p2/statuses/s2",
            context="https://example.org/cases/case_ps2",
        )
        case_ps2 = as_VulnerabilityCase(
            id_="https://example.org/cases/case_ps2",
            name="PS Case 2",
            # Genesis anchor for the gated commit (CLP-08-005).
            attributed_to="https://example.org/users/vendor",
        )
        # Register the vendor actor as a participant so step 1 passes
        case_ps2.case_participants.append(participant.id_)
        case_ps2.actor_participant_index[
            "https://example.org/users/vendor"
        ] = participant.id_
        dl.create(participant)
        dl.create(pstatus)
        dl.create(case_ps2)

        activity = add_status_to_participant_activity(
            pstatus,
            target=participant,
            actor="https://example.org/users/vendor",
            context=case_ps2,
        )
        event = make_payload(
            activity,
            receiving_actor_id="https://example.org/users/vendor",
        )

        result = AddParticipantStatusToParticipantReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()
        # The default call-out withholds adoption of a non-owner's claim
        # (RSH-07-001).  The append lands, and a withheld adoption is not a
        # refusal of the assertion (RSH-09-008), so it is SKIPPED (#2255).
        assert result.disposition == HandlerDisposition.SKIPPED
        assert result.reason is not None
        assert "CASE_OWNER approval required" in result.reason

        participant = dl.read(participant.id_)
        assert participant is not None
        participant = cast(as_CaseParticipant, participant)
        status_ids = [
            getattr(s, "id_", s) for s in participant.participant_statuses
        ]
        assert pstatus.id_ in status_ids

    @pytest.mark.spec("HP-08-008")
    @pytest.mark.spec("IO-03-004")
    def test_add_participant_status_through_ingress_naming_another_case_is_refused(
        self,
    ):
        """An Add(ParticipantStatus) whose status names case B but whose
        target participant is case A's is refused before the commit on the
        inbox path: the case is the target participant's own, so neither
        case gains an entry and A's participant gains no status (#4961).

        The sender is a participant of both cases, so the sender guard would
        pass on either; only the case the handler picks decides the outcome.
        """
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        sender = "https://example.org/users/vendor"
        case_a = as_VulnerabilityCase(
            id_="https://example.org/cases/case_ps4a",
            name="Case A",
            attributed_to=dl.actor_id,
        )
        case_b = as_VulnerabilityCase(
            id_="https://example.org/cases/case_ps4b",
            name="Case B",
            attributed_to=dl.actor_id,
        )
        for case in (case_a, case_b):
            seed_store_owner_as_case_manager(dl, case)
        target = seed_case_participant(dl, case_a, sender)
        seed_case_participant(dl, case_b, sender)
        dl.create(case_a)
        dl.create(case_b)
        status_id = f"{case_b.id_}/participants/vendor/statuses/s1"
        entries_before = len(dl.list_objects("CaseLedgerEntry"))

        activity = add_status_to_participant_activity(
            as_ParticipantStatus(id_=status_id, context=case_b.id_),
            target=as_CaseParticipant.model_validate(
                target.model_dump(by_alias=True, mode="json")
            ),
            actor=sender,
            to=[dl.actor_id],
            context=case_b.id_,
        )
        ingress = FastAPIIngressAdapter(dl)
        parsed = ingress.parse(
            activity.model_dump(by_alias=True, mode="json", exclude_none=True)
        )
        assert parsed is not None
        event = received_event(ingress.rehydrate(parsed)).model_copy(
            update={"receiving_actor_id": dl.actor_id}
        )
        assert isinstance(
            event, AddParticipantStatusToParticipantReceivedEvent
        )

        result = AddParticipantStatusToParticipantReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason is not None and "HP-08-007" in result.reason
        assert len(dl.list_objects("CaseLedgerEntry")) == entries_before
        stored = cast(as_CaseParticipant, dl.read(target.id_))
        assert status_id not in [
            getattr(s, "id_", s) for s in stored.participant_statuses
        ]

    @pytest.mark.spec("HP-08-008")
    def test_add_participant_status_to_an_unheld_participant_is_refused(
        self, make_payload
    ):
        """A target participant the receiver does not hold leaves no case to
        act on, whatever case the status and the activity name, so the Add
        is refused with no entry (#4961)."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        sender = "https://example.org/users/vendor"
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_ps5",
            name="Case",
            attributed_to=dl.actor_id,
        )
        seed_store_owner_as_case_manager(dl, case)
        seed_case_participant(dl, case, sender)
        dl.create(case)
        unheld = as_CaseParticipant(
            id_=f"{case.id_}/participants/unheld",
            context=case.id_,
            attributed_to=sender,
        )
        entries_before = len(dl.list_objects("CaseLedgerEntry"))

        result = AddParticipantStatusToParticipantReceivedUseCase(
            dl,
            make_payload(
                add_status_to_participant_activity(
                    as_ParticipantStatus(
                        id_=f"{unheld.id_}/statuses/s1", context=case.id_
                    ),
                    target=unheld,
                    actor=sender,
                    to=[dl.actor_id],
                    context=case.id_,
                ),
                receiving_actor_id=dl.actor_id,
            ),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason is not None and "holds no case" in result.reason
        assert len(dl.list_objects("CaseLedgerEntry")) == entries_before
        assert dl.read(unheld.id_) is None

    @pytest.mark.spec("HP-08-008")
    def test_add_participant_status_to_a_record_naming_no_case_is_refused(
        self, make_payload
    ):
        """A held participant record whose ``context`` names no case leaves
        no case to act on, whatever case the status and the activity name,
        so the Add is refused with no entry and no appended status
        (#4961)."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        sender = "https://example.org/users/vendor"
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_ps6",
            name="Case",
            attributed_to=dl.actor_id,
        )
        seed_store_owner_as_case_manager(dl, case)
        target = seed_case_participant(dl, case, sender)
        dl.create(case)
        target.context = None
        dl.save(target)
        status_id = f"{target.id_}/statuses/s1"
        entries_before = len(dl.list_objects("CaseLedgerEntry"))

        result = AddParticipantStatusToParticipantReceivedUseCase(
            dl,
            make_payload(
                add_status_to_participant_activity(
                    as_ParticipantStatus(id_=status_id, context=case.id_),
                    target=as_CaseParticipant.model_validate(
                        target.model_dump(by_alias=True, mode="json")
                    ),
                    actor=sender,
                    to=[dl.actor_id],
                    context=case.id_,
                ),
                receiving_actor_id=dl.actor_id,
            ),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason is not None and "holds no case" in result.reason
        assert len(dl.list_objects("CaseLedgerEntry")) == entries_before
        stored = cast(as_CaseParticipant, dl.read(target.id_))
        assert status_id not in [
            getattr(s, "id_", s) for s in stored.participant_statuses
        ]

    def test_add_participant_status_uses_store_owner_when_no_receiving_actor(
        self, make_payload
    ):
        """When receiving_actor_id is absent the store owner processes the status.

        Absent-stamp path (CLP-10-005): resolve_receiving_actor_id falls back to
        dl.actor_id (vendor), so the status is appended rather than dropped.
        """

        vendor_id = "https://example.org/users/vendor-nostamp"
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=vendor_id)

        # RSH-08-003/#3814: the append is CASE_MANAGER-gated; the store owner
        # (also the subject) holds the role so the gated write runs.
        participant = as_CaseParticipant(
            id_="https://example.org/cases/case_ps_nostamp/participants/p",
            context="https://example.org/cases/case_ps_nostamp",
            attributed_to=vendor_id,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        pstatus = as_ParticipantStatus(
            id_=(
                "https://example.org/cases/case_ps_nostamp"
                "/participants/p/statuses/s"
            ),
            context="https://example.org/cases/case_ps_nostamp",
        )
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_ps_nostamp",
            name="PS No-Stamp Test",
            # Genesis anchor for the gated commit (CLP-08-005).
            attributed_to=vendor_id,
        )
        case.case_participants.append(participant.id_)
        case.actor_participant_index[vendor_id] = participant.id_
        dl.create(participant)
        dl.create(pstatus)
        dl.create(case)

        activity = add_status_to_participant_activity(
            pstatus,
            target=participant,
            actor=vendor_id,
            to=[vendor_id],
            context=case,
        )
        event = make_payload(activity, receiving_actor_id=None)

        AddParticipantStatusToParticipantReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        refreshed = dl.read(participant.id_)
        assert refreshed is not None
        refreshed = cast(as_CaseParticipant, refreshed)
        status_ids = [
            getattr(s, "id_", s) for s in refreshed.participant_statuses
        ]
        assert pstatus.id_ in status_ids, (
            "Status must be appended even when receiving_actor_id is absent"
            " (store-owner fallback, CLP-10-005)"
        )

    def test_add_case_status_to_case_rejects_empty_status_id(self, caplog):
        """execute() logs a warning and returns early when status_id is empty string."""
        import logging
        from unittest.mock import MagicMock

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        mock_event = MagicMock()
        mock_event.status_id = ""
        mock_event.case_id = "https://example.org/cases/test-empty-id"
        mock_event.receiving_actor_id = None

        with caplog.at_level(logging.WARNING):
            result = AddCaseStatusToCaseReceivedUseCase(
                dl,
                mock_event,
                wire_render_port=As2WireRenderAdapter(),
            ).execute()

        assert "missing status_id or case_id" in caplog.text
        assert result.disposition == HandlerDisposition.REFUSED

    def test_add_participant_status_to_participant_rejects_empty_status_id(
        self, caplog
    ):
        """execute() logs a warning and returns early when status_id is empty string."""
        import logging
        from unittest.mock import MagicMock

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        mock_event = MagicMock()
        mock_event.status_id = ""
        mock_event.participant_id = (
            "https://example.org/cases/test/participants/p"
        )
        mock_event.receiving_actor_id = None

        with caplog.at_level(logging.WARNING):
            result = AddParticipantStatusToParticipantReceivedUseCase(
                dl,
                mock_event,
                wire_render_port=As2WireRenderAdapter(),
            ).execute()

        assert "missing status_id" in caplog.text
        assert result.disposition == HandlerDisposition.REFUSED


# ---------------------------------------------------------------------------
# CaseLedgerEntry cascade tests (PCR-08-003, PCR-08-004) — AC-2
# ---------------------------------------------------------------------------


class TestParticipantStatusLogEntryCascade:
    """CaseLedgerEntry cascade for AddParticipantStatusToParticipantReceivedUseCase."""

    def _make_dl(self, case_id: str, actor_id: str) -> tuple:
        from vultron.enums.roles import CVDRole

        # These tests run the received-side tree as the CaseActor (it is the
        # receiving_actor_id they pass), so this is the CaseActor's own store.
        case_actor_id = f"{case_id}/actor"
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=case_actor_id)
        case_actor = VultronService(
            id_=case_actor_id,
            name=f"CaseActor for {case_id}",
            attributed_to=actor_id,
            context=case_id,
        )
        dl.create(case_actor)

        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        case = as_VulnerabilityCase(
            id_=case_id,
            name="Status Cascade Case",
            attributed_to=actor_id,
        )
        case_manager_participant_id = f"{case_id}/participants/case-actor-p"
        case.case_participants.append(case_manager_participant_id)
        case.actor_participant_index[case_actor_id] = (
            case_manager_participant_id
        )
        case.case_participants.append(f"{case_id}/participants/p1")
        case.actor_participant_index[actor_id] = f"{case_id}/participants/p1"
        # Add Case Manager participant so FindCaseManagerNode can succeed.
        cm_participant_id = f"{case_id}/participants/cm"
        case.case_participants.append(cm_participant_id)
        case.actor_participant_index[case_actor_id] = cm_participant_id
        dl.create(case)

        case_manager_participant = as_CaseParticipant(
            id_=case_manager_participant_id,
            context=case_id,
            attributed_to=case_actor_id,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        dl.create(case_manager_participant)

        participant = as_CaseParticipant(
            id_=f"{case_id}/participants/p1",
            context=case_id,
            attributed_to=actor_id,
        )
        dl.create(participant)

        cm_participant = as_CaseParticipant(
            id_=cm_participant_id,
            context=case_id,
            attributed_to=case_actor_id,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        dl.create(cm_participant)

        pstatus = as_ParticipantStatus(
            id_=f"{case_id}/participants/p1/statuses/s1",
            context=case_id,
        )
        dl.create(pstatus)

        return dl, case_actor_id, participant, pstatus

    def test_cascade_commits_log_entry_on_success(self, make_payload):
        """Cascade commits a CaseLedgerEntry when BT succeeds (AC-2)."""
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        actor_id = "https://example.org/users/vendor"
        case_id = "https://example.org/cases/st_le1"
        dl, case_actor_id, participant, pstatus = self._make_dl(
            case_id, actor_id
        )
        case = cast(as_VulnerabilityCase, dl.read(case_id))
        assert case is not None

        activity = add_status_to_participant_activity(
            pstatus,
            target=participant,
            actor=actor_id,
            to=[case_actor_id],
            context=case,
        )
        event = make_payload(activity, receiving_actor_id=case_actor_id)
        sync_port = SyncActivityAdapter(dl)
        AddParticipantStatusToParticipantReceivedUseCase(
            dl,
            event,
            sync_port=sync_port,
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        entries = [
            obj
            for obj in dl.list_objects("CaseLedgerEntry")
            if isinstance(obj, CaseLedgerEntry)
            and cast(CaseLedgerEntry, obj).case_id == case_id
        ]
        assert len(entries) == 1
        assert cast(CaseLedgerEntry, entries[0]).semantic_type == (
            "add_participant_status_to_participant"
        )

    @pytest.mark.spec("SYNC-02-002")
    @pytest.mark.spec("BT-14-001")
    def test_status_without_sync_port_raises_as_wiring_fault(
        self, make_payload
    ):
        """A missing sync_port fails the commit instead of skipping fan-out.

        ``RequireSyncPortNode`` raises ``VultronWiringError`` before the entry
        is minted (#4113).  ``CommitCaseLedgerEntryNode`` carries the nested
        bridge's ``internal_error`` across the hop, so the handler raises
        ``VultronBTInternalError`` rather than reporting the sender as refused
        (ADR-0095).  The status is not attached and nothing is announced.
        """
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        actor_id = "https://example.org/users/vendor"
        case_id = "https://example.org/cases/st_le2"
        dl, case_actor_id, participant, pstatus = self._make_dl(
            case_id, actor_id
        )
        case = cast(as_VulnerabilityCase, dl.read(case_id))
        assert case is not None

        activity = add_status_to_participant_activity(
            pstatus,
            target=participant,
            actor=actor_id,
            to=[case_actor_id],
            context=case,
        )
        event = make_payload(activity, receiving_actor_id=case_actor_id)
        with pytest.raises(VultronBTInternalError, match="sync_port"):
            AddParticipantStatusToParticipantReceivedUseCase(
                dl,
                event,
                sync_port=None,
                wire_render_port=As2WireRenderAdapter(),
            ).execute()

        stored = dl.read(participant.id_)
        assert stored is not None
        assert pstatus.id_ not in [
            getattr(st, "id_", st) for st in stored.participant_statuses
        ]

        # The port guard refuses before the mint, so no entry is written
        # that no replica would ever receive.
        entries = [
            obj
            for obj in dl.list_objects("CaseLedgerEntry")
            if isinstance(obj, CaseLedgerEntry)
            and cast(CaseLedgerEntry, obj).case_id == case_id
        ]
        assert entries == []

        # Nothing is announced to participants.
        assert dl.outbox_list() == []

    def test_terminal_closed_update_does_not_commit_log_entry(
        self, make_payload
    ) -> None:
        """CLOSED->CLOSED rewrites are rejected before log cascade."""
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        actor_id = "https://example.org/users/vendor"
        case_id = "https://example.org/cases/st_le3"
        dl, case_actor_id, participant, _ = self._make_dl(case_id, actor_id)
        case = cast(as_VulnerabilityCase, dl.read(case_id))
        assert case is not None

        closed_status = as_ParticipantStatus(
            id_=f"{case_id}/participants/p1/statuses/closed-existing",
            context=case_id,
            rm=RmDimension(state=RM.CLOSED),
        )
        participant.participant_statuses.append(closed_status)
        dl.save(participant)
        dl.create(closed_status)

        duplicate_closed_status = as_ParticipantStatus(
            id_=f"{case_id}/participants/p1/statuses/closed-duplicate",
            context=case_id,
            rm=RmDimension(state=RM.CLOSED),
        )
        dl.create(duplicate_closed_status)

        activity = add_status_to_participant_activity(
            duplicate_closed_status,
            target=participant,
            actor=actor_id,
            to=[case_actor_id],
            context=case,
        )
        event = make_payload(activity, receiving_actor_id=case_actor_id)
        sync_port = SyncActivityAdapter(dl)

        before_count = len(participant.participant_statuses)
        result = AddParticipantStatusToParticipantReceivedUseCase(
            dl,
            event,
            sync_port=sync_port,
            wire_render_port=As2WireRenderAdapter(),
        ).execute()
        assert result.disposition == HandlerDisposition.REFUSED

        entries = [
            obj
            for obj in dl.list_objects("CaseLedgerEntry")
            if isinstance(obj, CaseLedgerEntry)
            and cast(CaseLedgerEntry, obj).case_id == case_id
        ]
        assert entries == []

        updated_participant = dl.read(participant.id_)
        assert updated_participant is not None
        assert len(updated_participant.participant_statuses) == before_count

    @pytest.mark.spec("CM-23-018")
    def test_status_update_from_a_closed_sender_is_refused(
        self, make_payload
    ) -> None:
        """A sender at RM CLOSED has left: its update is refused at the guard.

        The same update commits an entry from an open sender
        (``test_cascade_commits_log_entry_on_success``); the reason pins the
        refusal on the sender check, not on a transition guard.
        """
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        actor_id = "https://example.org/users/vendor"
        case_id = "https://example.org/cases/st_closed_sender"
        dl, case_actor_id, participant, pstatus = self._make_dl(
            case_id, actor_id
        )
        case = cast(as_VulnerabilityCase, dl.read(case_id))
        assert case is not None
        closed_status = as_ParticipantStatus(
            id_=f"{case_id}/participants/p1/statuses/closed",
            context=case_id,
            rm=RmDimension(state=RM.CLOSED),
        )
        participant.participant_statuses.append(closed_status)
        dl.save(participant)
        dl.create(closed_status)

        activity = add_status_to_participant_activity(
            pstatus,
            target=participant,
            actor=actor_id,
            to=[case_actor_id],
            context=case,
        )
        event = make_payload(activity, receiving_actor_id=case_actor_id)
        result = AddParticipantStatusToParticipantReceivedUseCase(
            dl,
            event,
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        assert "CM-23-018" in (result.reason or "")
        assert list(dl.list_objects("CaseLedgerEntry")) == []
        assert dl.outbox_list() == []
        stored = dl.read(participant.id_)
        assert stored is not None
        assert pstatus.id_ not in [
            getattr(st, "id_", st) for st in stored.participant_statuses
        ]

    def test_duplicate_assertion_reuses_existing_log_entry(
        self, make_payload
    ) -> None:
        """Two equivalent assertions append only one canonical log entry."""
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        actor_id = "https://example.org/users/vendor"
        case_id = "https://example.org/cases/st_le4"
        dl, case_actor_id, participant, pstatus = self._make_dl(
            case_id, actor_id
        )
        case = cast(as_VulnerabilityCase, dl.read(case_id))
        assert case is not None

        activity = add_status_to_participant_activity(
            pstatus,
            target=participant,
            actor=actor_id,
            to=[case_actor_id],
            context=case,
        )
        event = make_payload(activity, receiving_actor_id=case_actor_id)
        sync_port = SyncActivityAdapter(dl)
        uc = AddParticipantStatusToParticipantReceivedUseCase(
            dl,
            event,
            sync_port=sync_port,
            wire_render_port=As2WireRenderAdapter(),
        )

        uc.execute()
        uc.execute()

        entries = [
            obj
            for obj in dl.list_objects("CaseLedgerEntry")
            if isinstance(obj, CaseLedgerEntry)
            and cast(CaseLedgerEntry, obj).case_id == case_id
        ]
        assert len(entries) == 1

    def test_non_case_actor_receiver_does_not_commit_log_entry(
        self, make_payload
    ) -> None:
        """Peer-side replay of broadcast status must not append canonical entries."""
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        actor_id = "https://example.org/users/vendor"
        non_case_actor_id = "https://example.org/users/finder"
        case_id = "https://example.org/cases/st_le5"
        dl, case_actor_id, participant, pstatus = self._make_dl(
            case_id, actor_id
        )
        case = cast(as_VulnerabilityCase, dl.read(case_id))
        assert case is not None

        peer = as_CaseParticipant(
            id_=f"{case_id}/participants/p2",
            context=case_id,
            attributed_to=non_case_actor_id,
        )
        dl.create(peer)
        case.case_participants.append(peer.id_)
        case.actor_participant_index[non_case_actor_id] = peer.id_
        dl.save(case)

        activity = add_status_to_participant_activity(
            pstatus,
            target=participant,
            actor=case_actor_id,
            to=[non_case_actor_id],
            context=case,
        )
        event = make_payload(activity, receiving_actor_id=non_case_actor_id)
        AddParticipantStatusToParticipantReceivedUseCase(
            dl,
            event,
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        entries = [
            obj
            for obj in dl.list_objects("CaseLedgerEntry")
            if isinstance(obj, CaseLedgerEntry)
            and cast(CaseLedgerEntry, obj).case_id == case_id
        ]
        assert entries == []

    def test_commit_path_preserves_snapshot_actor_and_fanout_payload_identity(
        self, make_payload
    ) -> None:
        """Stored snapshot keeps asserter actor and announce payload is identical."""
        from unittest.mock import MagicMock

        from vultron.wire.as2.enums import as_TransitiveActivityType
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        reporter_actor_id = "https://example.org/users/vendor"
        finder_actor_id = "https://example.org/users/finder"
        case_id = "https://example.org/cases/st_le6"
        dl, case_actor_id, participant, pstatus = self._make_dl(
            case_id, reporter_actor_id
        )
        case = cast(as_VulnerabilityCase, dl.read(case_id))
        assert case is not None

        finder_participant = as_CaseParticipant(
            id_=f"{case_id}/participants/finder",
            context=case_id,
            attributed_to=finder_actor_id,
        )
        dl.create(finder_participant)
        case.case_participants.append(finder_participant.id_)
        case.actor_participant_index[finder_actor_id] = finder_participant.id_
        dl.save(case)

        activity = add_status_to_participant_activity(
            pstatus,
            target=participant,
            actor=reporter_actor_id,
            to=[case_actor_id],
            context=case,
        )
        event = make_payload(activity, receiving_actor_id=case_actor_id)
        # Supply a trigger_activity mock so AutoCloseBranchNode can emit
        # close_case if all participants close (BT step 5).
        mock_trigger = MagicMock()
        mock_trigger.add_participant_status_to_participant.return_value = (
            "urn:uuid:broadcast-1"
        )
        AddParticipantStatusToParticipantReceivedUseCase(
            dl,
            event,
            trigger_activity=mock_trigger,
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        entries = [
            cast(CaseLedgerEntry, obj)
            for obj in dl.list_objects("CaseLedgerEntry")
            if isinstance(obj, CaseLedgerEntry)
            and cast(CaseLedgerEntry, obj).case_id == case_id
        ]
        assert len(entries) == 1
        assert entries[0].payload_snapshot.get("actor") == reporter_actor_id

        announce_ids = []
        announce_payloads = []
        announce_actors = []
        for activity_id in dl.outbox_list():
            queued = dl.read(activity_id)
            if (
                queued is None
                or getattr(queued, "type_", None)
                != as_TransitiveActivityType.ANNOUNCE
            ):
                continue
            queued_object = getattr(queued, "object_", None)
            if (
                queued_object is None
                or getattr(queued_object, "type_", None) != "CaseLedgerEntry"
            ):
                continue
            announce_ids.append(activity_id)
            announce_actors.append(getattr(queued, "actor", None))
            announce_payloads.append(
                json.dumps(
                    queued_object.model_dump(
                        mode="json",
                        by_alias=True,
                        exclude_none=True,
                        serialize_as_any=True,
                    ),
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )

        assert len(announce_ids) == 2
        assert all(actor == case_actor_id for actor in announce_actors)
        assert len(set(announce_payloads)) == 1

    def test_absent_stamp_falls_back_to_store_owner(self, make_payload):
        """Absent receiving_actor_id falls back to dl.actor_id (case_actor_id) and commits.

        Per resolve_receiving_actor_id (CLP-10-005): when receiving_actor_id is
        None the store owner is used.  The store owner holds CASE_MANAGER role,
        so the guarded commit fires and an add_participant_status_to_participant
        ledger entry is written.
        """
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        actor_id = "https://example.org/users/vendor"
        case_id = "https://example.org/cases/st_le_abs"
        dl, _case_actor_id, participant, pstatus = self._make_dl(
            case_id, actor_id
        )
        case = cast(as_VulnerabilityCase, dl.read(case_id))
        assert case is not None

        activity = add_status_to_participant_activity(
            pstatus,
            target=participant,
            actor=actor_id,
            to=[_case_actor_id],
            context=case,
        )
        event = make_payload(activity, receiving_actor_id=None)
        sync_port = SyncActivityAdapter(dl)
        AddParticipantStatusToParticipantReceivedUseCase(
            dl,
            event,
            sync_port=sync_port,
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        entries = [
            obj
            for obj in dl.list_objects("CaseLedgerEntry")
            if isinstance(obj, CaseLedgerEntry)
            and cast(CaseLedgerEntry, obj).case_id == case_id
        ]
        assert len(entries) == 1, (
            "Absent receiving_actor_id must fall back to dl.actor_id (store owner)"
            " and commit an add_participant_status_to_participant ledger entry"
        )
        assert cast(CaseLedgerEntry, entries[0]).semantic_type == (
            "add_participant_status_to_participant"
        )


@pytest.mark.spec("RSH-04-005")
def test_add_case_status_admits_only_the_case_manager_at_a_participant():
    rule = AddCaseStatusToCaseReceivedUseCase.sender_entitlement

    assert isinstance(rule, SenderRule)
    assert rule.side(AddresseeSide.PARTICIPANT) == frozenset(
        {SenderEntitlementKind.CASE_MANAGER}
    )
    assert rule.side(AddresseeSide.CASE_MANAGER) == frozenset()
    assert rule.side(AddresseeSide.OUTSIDE_CASE) == frozenset()
