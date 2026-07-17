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
"""Tests for CaseLedgerEntry cascade on embargo received-side handlers (AC-3)."""

from typing import cast

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
from vultron.core.models.protocols import is_log_entry_model
from vultron.core.states.em import EM
from vultron.core.use_cases.received.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
    AddEmbargoEventToCaseReceivedUseCase,
    InviteToEmbargoOnCaseReceivedUseCase,
    RejectInviteToEmbargoOnCaseReceivedUseCase,
    RemoveEmbargoEventFromCaseReceivedUseCase,
)
from vultron.wire.as2.factories import (
    add_embargo_to_case_activity,
    em_accept_embargo_activity,
    em_propose_embargo_activity,
    em_reject_embargo_activity,
    remove_embargo_from_case_activity,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)


def _make_embargo_case_with_actor(
    case_id: str,
    author_id: str,
    extra_participants: list[str] | None = None,
    case_manager_actor_id: str | None = None,
) -> tuple[
    SqliteDataLayer, VultronCaseActor, as_VulnerabilityCase, as_EmbargoEvent
]:
    """Return (dl, case_actor, case, embargo) ready for cascade tests.

    Also creates ``as_CaseParticipant`` objects so actor → participant lookups
    in the embargo handlers succeed.
    """
    from vultron.enums.roles import CVDRole
    from vultron.wire.as2.vocab.objects.case_participant import (
        as_CaseParticipant,
    )

    dl = SqliteDataLayer("sqlite:///:memory:")
    case_actor_id = f"{case_id}/actor"

    case_actor = VultronCaseActor(
        id_=case_actor_id,
        name=f"CaseActor for {case_id}",
        attributed_to=author_id,
        context=case_id,
    )
    dl.create(case_actor)

    case = as_VulnerabilityCase(
        id_=case_id,
        name="Embargo Cascade Case",
        attributed_to=author_id,
    )
    p1_id = f"{case_id}/participants/p1"
    case.actor_participant_index[author_id] = p1_id
    p1 = as_CaseParticipant(
        id_=p1_id, context=case_id, attributed_to=author_id
    )
    dl.create(p1)

    for pid in extra_participants or []:
        short = pid.rsplit("/", 1)[-1]
        pn_id = f"{case_id}/participants/{short}"
        case.actor_participant_index[pid] = pn_id
        pn = as_CaseParticipant(id_=pn_id, context=case_id, attributed_to=pid)
        dl.create(pn)

    dl.create(case)
    case_manager_participant = as_CaseParticipant(
        id_=f"{case_id}/participants/case-actor-p",
        attributed_to=case_manager_actor_id or case_actor_id,
        context=case_id,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    dl.create(case_manager_participant)
    case.case_participants.append(case_manager_participant.id_)
    case.actor_participant_index[case_manager_actor_id or case_actor_id] = (
        case_manager_participant.id_
    )
    dl.save(case)

    embargo = as_EmbargoEvent(
        id_=f"{case_id}/embargo_events/e1",
        content="Cascade test embargo",
        context=case_id,
    )
    dl.create(embargo)

    return dl, case_actor, case, embargo


class TestEmbargoLogEntryCascade:
    """CaseLedgerEntry cascade for each embargo received-side handler (AC-3)."""

    def test_add_embargo_event_commits_log_entry(self, make_payload):
        """AddEmbargoEventToCaseReceivedUseCase commits a CaseLedgerEntry."""
        author_id = "https://example.org/users/coord"
        case_id = "https://example.org/cases/em_cas_add"
        dl, case_actor, case, embargo = _make_embargo_case_with_actor(
            case_id, author_id, case_manager_actor_id=author_id
        )
        case_read = cast(as_VulnerabilityCase, dl.read(case.id_))
        assert case_read is not None
        case_read.current_status.em_state = EM.PROPOSED
        dl.save(case_read)

        case_ref = as_VulnerabilityCase(id_=case_id)
        activity = add_embargo_to_case_activity(
            embargo, target=case_ref, actor=author_id
        )
        event = make_payload(activity, receiving_actor_id=case_actor.id_)
        sync_port = SyncActivityAdapter(dl)
        AddEmbargoEventToCaseReceivedUseCase(
            dl, event, sync_port=sync_port
        ).execute()

        entries = [
            obj
            for obj in dl.list_objects("CaseLedgerEntry")
            if is_log_entry_model(obj)
            and cast(VultronCaseLedgerEntry, obj).case_id == case_id
        ]
        assert len(entries) == 1
        assert cast(VultronCaseLedgerEntry, entries[0]).event_type == (
            "add_embargo_event_to_case"
        )

    def test_remove_embargo_event_commits_log_entry(self, make_payload):
        """RemoveEmbargoEventFromCaseReceivedUseCase commits a CaseLedgerEntry."""
        import py_trees

        py_trees.blackboard.Blackboard.enable_activity_stream()
        py_trees.blackboard.Blackboard.storage.clear()

        author_id = "https://example.org/users/coord"
        case_id = "https://example.org/cases/em_cas_rem"
        dl, case_actor, case, embargo = _make_embargo_case_with_actor(
            case_id, author_id
        )
        case = cast(as_VulnerabilityCase, dl.read(case.id_))
        assert case is not None
        case.current_status.em_state = EM.ACTIVE
        case.proposed_embargoes.append(embargo.id_)
        case.active_embargo = embargo.id_  # type: ignore[assignment]
        dl.save(case)

        activity = remove_embargo_from_case_activity(
            embargo, origin=case.id_, actor=author_id
        )
        event = make_payload(activity, receiving_actor_id=case_actor.id_)
        sync_port = SyncActivityAdapter(dl)
        RemoveEmbargoEventFromCaseReceivedUseCase(
            dl, event, sync_port=sync_port
        ).execute()

        entries = [
            obj
            for obj in dl.list_objects("CaseLedgerEntry")
            if is_log_entry_model(obj)
            and cast(VultronCaseLedgerEntry, obj).case_id == case_id
        ]
        assert len(entries) == 1
        assert cast(VultronCaseLedgerEntry, entries[0]).event_type == (
            "remove_embargo_event_from_case"
        )

    def test_remove_embargo_commits_log_entry_on_bt_failure(
        self, make_payload
    ):
        """RemoveEmbargoEventFromCaseReceivedUseCase cascades even when BT fails.

        BT FAILURE means "embargo already cleared" — it is not an error. The
        CaseLedgerEntry MUST be committed regardless so participants learn the
        current state.
        """
        import py_trees

        py_trees.blackboard.Blackboard.enable_activity_stream()
        py_trees.blackboard.Blackboard.storage.clear()

        author_id = "https://example.org/users/coord"
        case_id = "https://example.org/cases/em_cas_rem_fail"
        dl, case_actor, case, embargo = _make_embargo_case_with_actor(
            case_id, author_id
        )
        # EM.NONE: no active embargo — BT will FAIL (IsActiveEmbargoNode)
        case = cast(as_VulnerabilityCase, dl.read(case.id_))
        assert case is not None
        case.current_status.em_state = EM.NONE
        dl.save(case)

        activity = remove_embargo_from_case_activity(
            embargo, origin=case.id_, actor=author_id
        )
        event = make_payload(activity, receiving_actor_id=case_actor.id_)
        sync_port = SyncActivityAdapter(dl)
        RemoveEmbargoEventFromCaseReceivedUseCase(
            dl, event, sync_port=sync_port
        ).execute()

        entries = [
            obj
            for obj in dl.list_objects("CaseLedgerEntry")
            if is_log_entry_model(obj)
            and cast(VultronCaseLedgerEntry, obj).case_id == case_id
        ]
        # Cascade must fire even on BT FAILURE.
        assert len(entries) == 1

    def test_invite_to_embargo_skips_commit_for_invitee_receiver(
        self, make_payload
    ):
        """InviteToEmbargoOnCaseReceivedUseCase does NOT commit a ledger entry.

        When the invitee receives the invite, the CASE_MANAGER gate inside the
        guarded-commit subtree of invite_to_embargo_on_case_tree correctly
        blocks the commit: the invitee is not the Case Manager.  The canonical
        ledger entry for the invite-sent event is committed by the CaseActor on
        the trigger side (when the invite is sent), not on the invitee's receive
        side.
        """
        author_id = "https://example.org/users/coord"
        case_id = "https://example.org/cases/em_cas_invite"
        invitee_id = "https://example.org/users/vendor"
        dl, case_actor, case, embargo = _make_embargo_case_with_actor(
            case_id,
            author_id,
            extra_participants=[invitee_id],
            case_manager_actor_id=author_id,
        )

        proposal = em_propose_embargo_activity(
            embargo,
            context=case_id,
            actor=author_id,
            id_=f"{case_id}/embargo_proposals/1",
        )
        dl.create(proposal)

        # receiving_actor_id is the invitee — not the CaseActor/Case Manager.
        event = make_payload(proposal, receiving_actor_id=invitee_id)
        sync_port = SyncActivityAdapter(dl)
        InviteToEmbargoOnCaseReceivedUseCase(
            dl, event, sync_port=sync_port
        ).execute()

        # No canonical ledger entry should be committed on the invitee side.
        entries = [
            obj
            for obj in dl.list_objects("CaseLedgerEntry")
            if is_log_entry_model(obj)
            and cast(VultronCaseLedgerEntry, obj).case_id == case_id
        ]
        assert len(entries) == 0, (
            "Invitee-side receipt must not commit a canonical ledger entry; "
            "only the CaseActor commits (on the trigger/send side)."
        )

    def test_accept_invite_to_embargo_commits_log_entry(self, make_payload):
        """AcceptInviteToEmbargoOnCaseReceivedUseCase commits a CaseLedgerEntry."""
        coordinator_id = "https://example.org/users/coordinator"
        case_id = "https://example.org/cases/em_cas_accept"
        dl, case_actor, case, embargo = _make_embargo_case_with_actor(
            case_id, coordinator_id, case_manager_actor_id=coordinator_id
        )
        case = cast(as_VulnerabilityCase, dl.read(case.id_))
        assert case is not None
        case.current_status.em_state = EM.PROPOSED
        dl.save(case)

        proposal = em_propose_embargo_activity(
            embargo,
            context=case.id_,
            actor="https://example.org/users/vendor",
            id_=f"{case_id}/embargo_proposals/1",
        )
        dl.create(proposal)

        accept = em_accept_embargo_activity(
            proposal,
            context=case.id_,
            actor=coordinator_id,
        )
        # Per ADR-0022 / CLP-10-005: the guarded commit fires when
        # receiving_actor_id holds CVDRole.CASE_MANAGER.  coordinator_id is
        # the CASE_MANAGER in this fixture (case_manager_actor_id=coordinator_id).
        event = make_payload(accept, receiving_actor_id=coordinator_id)
        sync_port = SyncActivityAdapter(dl)
        AcceptInviteToEmbargoOnCaseReceivedUseCase(
            dl, event, sync_port=sync_port
        ).execute()

        entries = [
            obj
            for obj in dl.list_objects("CaseLedgerEntry")
            if is_log_entry_model(obj)
            and cast(VultronCaseLedgerEntry, obj).case_id == case_id
        ]
        assert len(entries) == 1
        assert cast(VultronCaseLedgerEntry, entries[0]).event_type == (
            "accept_invite_to_embargo_on_case"
        )

    def test_reject_invite_to_embargo_commits_log_entry(self, make_payload):
        """RejectInviteToEmbargoOnCaseReceivedUseCase commits a CaseLedgerEntry."""
        coordinator_id = "https://example.org/users/coordinator"
        case_id = "https://example.org/cases/em_cas_reject"
        dl, case_actor, case, embargo = _make_embargo_case_with_actor(
            case_id, coordinator_id, case_manager_actor_id=coordinator_id
        )

        proposal = em_propose_embargo_activity(
            embargo,
            context=case_id,
            actor="https://example.org/users/vendor",
            id_=f"{case_id}/embargo_proposals/1",
        )
        dl.create(proposal)

        reject = em_reject_embargo_activity(
            proposal,
            context=case_id,
            actor=coordinator_id,
        )
        event = make_payload(reject, receiving_actor_id=case_actor.id_)
        sync_port = SyncActivityAdapter(dl)
        RejectInviteToEmbargoOnCaseReceivedUseCase(
            dl, event, sync_port=sync_port
        ).execute()

        entries = [
            obj
            for obj in dl.list_objects("CaseLedgerEntry")
            if is_log_entry_model(obj)
            and cast(VultronCaseLedgerEntry, obj).case_id == case_id
        ]
        assert len(entries) == 1
        assert cast(VultronCaseLedgerEntry, entries[0]).event_type == (
            "reject_invite_to_embargo_on_case"
        )
