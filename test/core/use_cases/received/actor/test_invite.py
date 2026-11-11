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

import json
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from test.core.use_cases.received._archived_redelivery import (
    archived_redelivery,
)
from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_owner_participant,
    seed_inert_invitee,
    seed_store_owner_as_case_manager,
)
from test.support.act_clock import ACT_AT
from test.support.act_runner import run_in_act
from test.support.broken_ledger_entry import tampered
from test.support.embargo_register import activate
from test.support.future_dates import days_from_now
from test.support.ledger_records import with_ledger_records
from test.support.objects import make
from test.support.received import case_stub, settle_as_the_inbox
from vultron.adapters.driven.clock import SystemClock
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.services.received_activity import sealed_body_of
from vultron.core.use_cases.received.actor.invite import (
    AcceptInviteActorToCaseReceivedUseCase,
    InviteActorToCaseReceivedUseCase,
    RejectInviteActorToCaseReceivedUseCase,
)
from vultron.errors import VultronBTInternalError
from vultron.wire.as2.factories import (
    rm_accept_invite_to_case_activity,
    rm_invite_to_case_activity,
    rm_reject_invite_to_case_activity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor


def _addressed_to_inviter(invite, also_to: tuple[str, ...]) -> list[str]:
    """The answer's ``to``: the inviter, as the trigger adapter derives it.

    ``accept_case_invite`` / ``reject_case_invite`` address the answer to the
    invite's ``actor`` (OX-08-001); *also_to* adds a copy-holder, so a test of
    what a non-CASE_MANAGER does with its copy gets past the addressee door
    (HP-01-005).
    """
    inviter = (
        invite.actor if isinstance(invite.actor, str) else invite.actor.id_
    )
    return [inviter, *also_to]


def _accept_invite(invite, *, actor: str, also_to: tuple[str, ...] = ()):
    """``Accept(Invite)`` addressed as the trigger adapter sends it."""
    return rm_accept_invite_to_case_activity(
        invite, actor=actor, to=_addressed_to_inviter(invite, also_to)
    )


def _reject_invite(invite, *, actor: str, also_to: tuple[str, ...] = ()):
    """``Reject(Invite)`` addressed as the trigger adapter sends it."""
    return rm_reject_invite_to_case_activity(
        invite, actor=actor, to=_addressed_to_inviter(invite, also_to)
    )


def _outbound_blob(activity) -> str:
    """The sealed body the real adapter returns alongside the activity id."""
    return str(
        activity.model_dump_json(
            by_alias=True, exclude_none=True, serialize_as_any=True
        )
    )


def _seed_ledger_entry(
    dl,
    case_id: str,
    object_id: str,
    semantic_type: str,
    actor_id: str,
    payload_snapshot: dict | None = None,
):
    """Test-only helper: commit a ledger entry directly, bypassing BT validation.

    Replicates the chain-building logic from the now-deleted
    ``commit_log_entry_trigger`` for use in test setup fixtures.
    """
    from vultron.core.models.case_ledger import HashChainLedgerRecord
    from vultron.core.sync_helpers import reconstruct_tail_hash

    tail_hash, tail_index = reconstruct_tail_hash(case_id, dl)
    chain_entry = HashChainLedgerRecord(
        case_id=case_id,
        log_index=tail_index + 1,
        object_id=object_id,
        semantic_type=semantic_type,
        payload_snapshot=payload_snapshot or {},
        prev_log_hash=tail_hash,
        received_at=ACT_AT,
    )
    entry = chain_entry.to_ledger_entry()
    dl.save(entry)
    return entry


def _seed_late_joiner_case() -> dict[str, Any]:
    """Case-actor store with a CASE_MANAGER, a two-entry ledger, and an Invite.

    Shared by the late-joiner tests: the invitee is not yet a participant, so
    ``Accept(Invite)`` drives the full admission sequence (CM-17-004).  Returns
    the store and the objects the assertions need, plus a ``trigger_activity``
    mock whose ``invite_actor_to_full_case`` side effect stores a real
    full-case Invite so ``EmitInviteActorToFullCaseNode`` can commit it.
    """
    from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
    from vultron.core.models.ledger_position import LedgerPosition
    from vultron.enums.roles import CVDRole
    from vultron.wire.as2.factories import rm_invite_to_full_case_activity
    from vultron.wire.as2.vocab.base.objects.actors import (
        as_Organization,
        as_Service,
    )
    from vultron.wire.as2.vocab.objects.case_participant import (
        as_CaseParticipant,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

    case_actor_id = "https://example.org/actors/case-actor-lj1"
    # The canonical ledger belongs to the case actor, so the backfill runs in
    # the case actor's store.
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=case_actor_id)
    invitee_id = "https://example.org/users/late-joiner"
    invitee = make(as_Organization, id_=invitee_id)
    case_actor = make(as_Service, id_=case_actor_id, context="unused")
    case = make(
        as_VulnerabilityCase,
        id_="https://example.org/cases/caseLJ1",
        name="TEST-LATE-JOIN-BACKFILL",
        attributed_to=case_actor_id,
    )
    object.__setattr__(case_actor, "context", case.id_)
    invite = rm_invite_to_case_activity(
        invitee,
        to=[invitee.id_],
        target=case_stub(case.id_),
        actor=case_actor_id,
        roles=[CVDRole.VENDOR],
        id_=f"{case.id_}/invitations/1",
    )
    dl.create(invitee)
    dl.create(case_actor)
    dl.create(case)

    case_manager_participant = make(
        as_CaseParticipant,
        id_=f"{case.id_}/participants/case-actor-p",
        attributed_to=case_actor_id,
        context=case.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    dl.create(case_manager_participant)
    case.case_participants.append(case_manager_participant.id_)
    case.actor_participant_index[case_actor_id] = case_manager_participant.id_
    seed_inert_invitee(dl, case, invitee_id)
    dl.save(case)
    dl.create(invite)

    first = _seed_ledger_entry(
        dl,
        case_id=case.id_,
        object_id=f"{case.id_}/events/0",
        semantic_type="submit_report",
        actor_id=case_actor_id,
        payload_snapshot={"index": 0},
    )
    second = _seed_ledger_entry(
        dl,
        case_id=case.id_,
        object_id=f"{case.id_}/events/1",
        semantic_type="add_participant_status",
        actor_id=case_actor_id,
        payload_snapshot={"index": 1},
    )

    def _store_full_case_invite(**kwargs):
        activity = rm_invite_to_full_case_activity(
            invitee=kwargs["invitee_id"],
            case=kwargs["case_id"],
            ledger_tail=LedgerPosition(
                log_index=kwargs["ledger_log_index"],
                entry_hash=kwargs["ledger_entry_hash"],
            ),
            actor=kwargs["actor"],
            to=kwargs.get("to"),
            id_=kwargs.get("id_") or f"{case.id_}/invitations/full-case-1",
        )
        if dl.read(activity.id_) is None:  # a rebuild keeps the first Invite
            dl.create(activity)
        return activity.id_, _outbound_blob(activity)

    trigger_activity = with_ledger_records(MagicMock(), dl)
    trigger_activity.announce_vulnerability_case.return_value = (
        f"{case.id_}/announce/1"
    )
    trigger_activity.invite_actor_to_full_case.side_effect = (
        _store_full_case_invite
    )
    return {
        "dl": dl,
        "case": case,
        "invitee_id": invitee_id,
        "case_actor_id": case_actor_id,
        "invite": invite,
        "first": first,
        "second": second,
        "trigger_activity": trigger_activity,
    }


_INVITEE_ID = "https://example.org/actors/invitee"


def _deliver_invite_to_invitee(
    make_payload: Any,
    *,
    target: Any,
    sender: str,
    invite_id: str,
) -> SqliteDataLayer:
    """Deliver one Invite to a fresh invitee store and return that store."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_INVITEE_ID)
    invite = rm_invite_to_case_activity(
        make(as_Actor, id_=_INVITEE_ID),
        to=[_INVITEE_ID],
        target=target,
        actor=sender,
        id_=invite_id,
    )
    run_in_act(
        InviteActorToCaseReceivedUseCase(
            dl,
            make_payload(invite, at=dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
    )
    return dl


#: PCR-07-008's fixture keeps the Case Owner and the CASE_MANAGER as separate
#: actors, so "which one processed the Accept" has an observable answer.
_PCR708_CASE_ID = "https://example.org/cases/casePCR708"
_PCR708_INVITEE = "https://example.org/actors/invitee-pcr708"
_PCR708_OWNER = "https://example.org/actors/owner-pcr708"
_PCR708_MANAGER = "https://example.org/actors/case-actor-pcr708"


def _seed_pcr708_exchange(*, receiver_id: str) -> tuple[SqliteDataLayer, Any]:
    """Seed the invite exchange in *receiver_id*'s store and return its Accept.

    The case always names :data:`_PCR708_OWNER` as its Case Owner and
    :data:`_PCR708_MANAGER` as its ``CVDRole.CASE_MANAGER`` holder, whichever
    of the two owns the store: the roles are the case's, not the receiver's.
    What *receiver_id* decides is which of them the Accept is delivered to.
    """
    from vultron.enums.roles import CVDRole
    from vultron.wire.as2.vocab.base.objects.actors import as_Organization

    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=receiver_id)
    invitee = make(as_Organization, id_=_PCR708_INVITEE)
    case = make(
        VulnerabilityCase,
        id_=_PCR708_CASE_ID,
        name="TEST-PCR-07-008",
        attributed_to=_PCR708_OWNER,
    )
    seed_case_manager_participant(dl, case, _PCR708_MANAGER)
    seed_case_owner_participant(dl, case, _PCR708_OWNER)
    seed_inert_invitee(dl, case, _PCR708_INVITEE)
    invite = rm_invite_to_case_activity(
        invitee,
        to=[invitee.id_],
        target=case.id_,
        actor=_PCR708_MANAGER,
        roles=[CVDRole.VENDOR],
        id_=f"{_PCR708_CASE_ID}/invitations/1",
    )
    dl.create(invitee)
    dl.create(case)
    dl.create(invite)
    return dl, _accept_invite(invite, actor=_PCR708_INVITEE)


def _run_accept(dl: SqliteDataLayer, event: Any) -> Any:
    """Run ``AcceptInviteActorToCaseReceivedUseCase`` over *event* in *dl*."""
    return run_in_act(
        AcceptInviteActorToCaseReceivedUseCase(
            dl,
            event,
            sync_port=MagicMock(),
            wire_render_port=As2WireRenderAdapter(),
            trigger_activity=TriggerActivityAdapter(dl),
        )
    )


class TestInviteActorUseCases:
    """Tests for invite_actor_to_case, accept_invite_actor_to_case,
    and reject_invite_actor_to_case."""

    @pytest.mark.spec("CLP-10-017")
    def test_invite_actor_to_case_archives_invite(self, make_payload):
        """The invitee's use case stores the Invite only through intake.

        Intake is the use case's only store of a received activity
        (CLP-10-019): the Invite is archived as a ``ReceivedActivityRecord``
        and the use case writes nothing under the sender's id (CLP-10-036).

        The invitee_id matches the dl owner so the AC-1 trust-anchor check
        (PCR-03-004) passes and the Invite is APPLIED, not refused.
        """
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.models.received_activity_record import (
            ReceivedActivityRecord,
        )

        invitee_id = "https://test.example/api/v2/actors/test-actor"
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=invitee_id,
        )

        invite = rm_invite_to_case_activity(
            make(as_Actor, id_=invitee_id),
            to=[invitee_id],
            target="https://example.org/cases/case1",
            actor="https://example.org/users/owner",
            id_="https://example.org/cases/case1/invitations/1",
        )

        event = make_payload(invite, at=dl)

        result = run_in_act(
            InviteActorToCaseReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            )
        )

        assert result.disposition is HandlerDisposition.APPLIED
        record = dl.read(ReceivedActivityRecord.build_id(invite.id_))
        assert isinstance(record, ReceivedActivityRecord)
        assert record.activity_id == invite.id_
        assert json.loads(sealed_body_of(record))["id"] == invite.id_
        assert dl.get(invite.type_.value, invite.id_) is None

    def test_invite_receipt_logged_in_narrative_form(
        self, make_payload, caplog
    ):
        """The invitee logs the invite receipt at INFO (SL-04-001, AC-17)."""
        import logging

        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        invitee_id = "https://example.org/users/coordinator"
        sender_id = "https://example.org/users/owner"
        case_id = "https://example.org/cases/case1"
        # dl owner matches invitee_id so the trust-anchor AC-1 check passes
        # (PCR-03-004) and LogInviteReceivedNode is reached.
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=invitee_id,
        )

        invite = rm_invite_to_case_activity(
            make(as_Actor, id_=invitee_id),
            to=[invitee_id],
            target=case_id,
            actor=sender_id,
            id_=f"{case_id}/invitations/narrative-1",
        )
        event = make_payload(invite, at=dl)

        with caplog.at_level(logging.INFO):
            run_in_act(
                InviteActorToCaseReceivedUseCase(
                    dl,
                    event,
                    wire_render_port=As2WireRenderAdapter(),
                    sync_port=SyncActivityAdapter(dl),
                )
            )

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

        # invitee_id matches dl owner so the AC-1 check passes (PCR-03-004).
        invitee_id = "https://test.example/api/v2/actors/test-actor"
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=invitee_id,
        )
        invite = rm_invite_to_case_activity(
            make(as_Actor, id_=invitee_id),
            to=[invitee_id],
            target="https://example.org/cases/case1",
            actor="https://example.org/users/owner",
            id_="https://example.org/cases/case1/invitations/narrative-2",
        )
        event = make_payload(invite, at=dl)

        with caplog.at_level(logging.DEBUG):
            run_in_act(
                InviteActorToCaseReceivedUseCase(
                    dl,
                    event,
                    wire_render_port=As2WireRenderAdapter(),
                    sync_port=SyncActivityAdapter(dl),
                )
            )

        awaiting = [
            r
            for r in caplog.records
            if "Awaiting AnnounceVulnerabilityCase" in r.getMessage()
        ]
        assert awaiting, "Expected the case-stub awaiting log entry"
        assert all(r.levelno == logging.DEBUG for r in awaiting)

    @pytest.mark.spec("PCR-03-004")
    def test_invite_invitee_path_stores_trust_anchor(self, make_payload):
        """InviteActorToCaseReceivedUseCase invitee path stores a trust anchor.

        PCR-03-004 AC-2: after processing an InviteActorToCase on the invitee
        path, a VultronPendingCaseInbox record with case_actor_id set to the
        invite sender must be present in the DataLayer.  The authority check in
        AnnounceVulnerabilityCaseReceivedUseCase reads this anchor to admit a
        subsequent Announce from the same actor.
        """
        from vultron.core.models.pending_case_inbox import (
            VultronPendingCaseInbox,
        )

        case_id = "https://example.org/cases/case-trust-1"
        case_manager_id = "https://example.org/actors/case-actor"
        dl = _deliver_invite_to_invitee(
            make_payload,
            target=case_id,
            sender=case_manager_id,
            invite_id=f"{case_id}/invitations/trust-anchor-1",
        )

        pending_id = VultronPendingCaseInbox.build_id(case_id)
        pending = dl.read(pending_id)
        assert isinstance(pending, VultronPendingCaseInbox), (
            "VultronPendingCaseInbox trust anchor must be written on the invitee path"
        )
        assert pending.case_actor_id == case_manager_id, (
            "Trust anchor case_actor_id must equal the invite sender (the CASE_MANAGER)"
        )

    @pytest.mark.spec("MV-10-004")
    def test_a_received_stub_invite_stores_no_case(self, make_payload):
        """MV-10-004: the invitee keeps the stub's anchor, never a case from it.

        The stub Invite is processed (its trust anchor is written, so the
        assertion below cannot pass on a refused Invite), yet no
        ``VulnerabilityCase`` record is created from the stub: the case
        arrives later, whole, with the CASE_MANAGER's Announce.
        """
        from vultron.core.models.pending_case_inbox import (
            VultronPendingCaseInbox,
        )

        case_id = "https://example.org/cases/case-stub-only"
        dl = _deliver_invite_to_invitee(
            make_payload,
            target=case_stub(case_id),
            sender="https://example.org/actors/case-actor",
            invite_id=f"{case_id}/invitations/stub-1",
        )

        assert isinstance(
            dl.read(VultronPendingCaseInbox.build_id(case_id)),
            VultronPendingCaseInbox,
        ), "the stub Invite must be processed, not refused"
        assert dl.read(case_id) is None
        assert dl.get_all("VulnerabilityCase") == []

    @pytest.mark.spec("PCR-03-004")
    def test_an_accepted_invite_anchor_refuses_another_case_actor(
        self, make_payload
    ):
        """Once the invitee accepts, an Invite naming another CaseActor is refused.

        AC-3 (PCR-03-010): the accepted anchor is never overwritten.
        The second Invite disposition is REFUSED, naming both CaseActor ids.
        """
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.models.pending_case_inbox import (
            VultronPendingCaseInbox,
        )
        from vultron.core.use_cases.triggers.actor import (
            SvcAcceptCaseInviteUseCase,
        )
        from vultron.core.use_cases.triggers.requests import (
            AcceptCaseInviteTriggerRequest,
        )

        case_id = "https://example.org/cases/case-trust-2"
        invitee_id = "https://example.org/actors/invitee"
        first_sender = "https://example.org/actors/case-actor-a"
        second_sender = "https://example.org/actors/case-actor-b"

        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=invitee_id)

        invite1 = rm_invite_to_case_activity(
            make(as_Actor, id_=invitee_id),
            to=[invitee_id],
            target=case_stub(case_id),
            actor=first_sender,
            id_=f"{case_id}/invitations/a",
        )
        invite2 = rm_invite_to_case_activity(
            make(as_Actor, id_=invitee_id),
            to=[invitee_id],
            target=case_stub(case_id),
            actor=second_sender,
            id_=f"{case_id}/invitations/b",
        )

        first_result = run_in_act(
            InviteActorToCaseReceivedUseCase(
                dl,
                make_payload(invite1, at=dl),
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            )
        )
        dl.create(make(as_Actor, id_=invitee_id, name="invitee"))
        accepted = run_in_act(
            SvcAcceptCaseInviteUseCase(
                dl,
                AcceptCaseInviteTriggerRequest(
                    actor_id=invitee_id, invite_id=invite1.id_
                ),
                trigger_activity=TriggerActivityAdapter(dl),
                sync_port=SyncActivityAdapter(dl),
                wire_render_port=As2WireRenderAdapter(),
                clock=SystemClock(),
            )
        )
        assert accepted.activity is not None
        second_result = run_in_act(
            InviteActorToCaseReceivedUseCase(
                dl,
                make_payload(invite2, at=dl),
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            )
        )

        assert first_result.disposition is HandlerDisposition.APPLIED, (
            "First Invite must be APPLIED"
        )
        # AC-3: conflicting second Invite is refused, not silently ignored.
        assert second_result.disposition is HandlerDisposition.REFUSED, (
            "Second Invite naming a different CaseActor MUST be REFUSED (PCR-03-010)"
        )

        pending = dl.read(VultronPendingCaseInbox.build_id(case_id))
        assert isinstance(pending, VultronPendingCaseInbox)
        assert pending.case_actor_id == first_sender, (
            "An accepted trust anchor MUST NOT be overwritten by a second invite"
        )

    @pytest.mark.spec("HP-01-016")
    @pytest.mark.spec("HP-01-003")
    def test_invite_actor_to_case_redelivery_is_skipped_not_refused(
        self, make_payload
    ):
        """A duplicate Invite reports SKIPPED and writes nothing new."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.models.pending_case_inbox import (
            VultronPendingCaseInbox,
        )

        # invitee_id matches dl owner so the AC-1 check passes (PCR-03-004)
        # and the first delivery is APPLIED, not refused.
        invitee_id = "https://test.example/api/v2/actors/test-actor"
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=invitee_id,
        )
        case_id = "https://example.org/cases/case1"
        invite = rm_invite_to_case_activity(
            make(as_Actor, id_=invitee_id),
            to=[invitee_id],
            target=case_id,
            actor="https://example.org/users/owner",
            id_=f"{case_id}/invitations/2",
        )
        event = make_payload(invite, at=dl)

        first = run_in_act(
            InviteActorToCaseReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            )
        )
        settle_as_the_inbox(dl, event, first)
        anchor = dl.read(VultronPendingCaseInbox.build_id(case_id))
        second = run_in_act(
            InviteActorToCaseReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            )
        )

        assert first.disposition is HandlerDisposition.APPLIED
        assert second.disposition is HandlerDisposition.SKIPPED
        assert dl.read(VultronPendingCaseInbox.build_id(case_id)) == anchor

    @pytest.mark.spec("PCR-03-004")
    def test_invite_misaddressed_to_different_actor_is_refused(
        self, make_payload
    ):
        """An Invite whose object is not the receiving actor is REFUSED; no anchor.

        AC-1 (PCR-03-007): the trust anchor node refuses to record a
        pending expectation when the Invite's ``object`` (the named invitee)
        does not match the receiving actor.  No ``VultronPendingCaseInbox``
        is written.
        """
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.models.pending_case_inbox import (
            VultronPendingCaseInbox,
        )

        case_id = "https://example.org/cases/case-misaddressed-1"
        # The Invite names a different actor as the invitee.
        named_invitee_id = "https://example.org/actors/coordinator"
        receiving_actor_id = "https://example.org/actors/vendor"
        case_manager_id = "https://example.org/actors/case-manager"

        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=receiving_actor_id)

        invite = rm_invite_to_case_activity(
            make(as_Actor, id_=named_invitee_id),  # object ≠ receiving actor
            to=[named_invitee_id],
            target=case_id,
            actor=case_manager_id,
            id_=f"{case_id}/invitations/misaddressed-1",
        )
        result = run_in_act(
            InviteActorToCaseReceivedUseCase(
                dl,
                make_payload(invite, at=dl),
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            )
        )

        assert result.disposition is HandlerDisposition.REFUSED, (
            "An Invite whose object is not the receiving actor MUST be REFUSED"
        )
        assert dl.read(VultronPendingCaseInbox.build_id(case_id)) is None, (
            "No trust anchor MUST be written when invitee != receiving actor"
        )

    @pytest.mark.parametrize("missing", ["target", "object"])
    def test_invite_missing_case_or_invitee_is_refused(
        self, make_payload, missing
    ):
        """An Invite that names no case or no invitee is refused up front."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        invite = rm_invite_to_case_activity(
            make(as_Actor, id_="https://example.org/users/coordinator"),
            to=["https://example.org/users/coordinator"],
            target="https://example.org/cases/case1",
            actor="https://example.org/users/owner",
            id_="https://example.org/cases/case1/invitations/missing",
        )
        field = "target" if missing == "target" else "object_"
        event = make_payload(invite, at=dl).model_copy(update={field: None})

        result = run_in_act(
            InviteActorToCaseReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            )
        )

        assert result.disposition is HandlerDisposition.REFUSED

    @pytest.mark.spec("CLP-10-005")
    @pytest.mark.spec("CLP-10-013")
    def test_invite_runs_one_tree_under_the_resolved_receiver(
        self, make_payload, monkeypatch
    ):
        """``execute()`` runs one tree, once, as the resolved receiving actor."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.behaviors.bridge import BTBridge

        # Invitee matches dl owner so the AC-1 check passes (PCR-03-004).
        owner_id = "https://test.example/api/v2/actors/test-actor"
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=owner_id)
        invite = rm_invite_to_case_activity(
            make(as_Actor, id_=owner_id),
            to=[owner_id],
            target="https://example.org/cases/case1",
            actor="https://example.org/users/owner",
            id_="https://example.org/cases/case1/invitations/one-tree",
        )
        calls: list[dict[str, Any]] = []
        real = BTBridge.execute_with_setup

        def _spy(self, *args, **kwargs):
            calls.append(kwargs)
            return real(self, *args, **kwargs)

        monkeypatch.setattr(BTBridge, "execute_with_setup", _spy)

        run_in_act(
            InviteActorToCaseReceivedUseCase(
                dl,
                make_payload(invite, at=dl),
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            )
        )

        assert len(calls) == 1
        assert calls[0]["actor_id"] == owner_id
        assert calls[0]["tree"].name == "InviteActorToCaseReceivedBT"

    @pytest.mark.spec("HP-01-003")
    @pytest.mark.spec("CLP-10-017")
    def test_case_actor_redelivered_invite_is_skipped(self, make_payload):
        """An Invite reaching the CASE_MANAGER's inbox reports SKIPPED on redelivery.

        The CASE_MANAGER emits and commits its own Invite and is never mailed
        a copy (CM-17-006, ADR-0109).  Should one arrive anyway, the
        invitee-only effects stay behind the replica gate — no trust anchor
        is written — so the first delivery is APPLIED by intake and a
        redelivery is the benign no-op of HP-01-003, never REFUSED.
        """
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.models.received_activity_record import (
            ReceivedActivityRecord,
        )
        from vultron.core.models.use_case_result import HandlerDisposition
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        case_id = "https://example.org/cases/case-redeliver-1"
        case_actor_id = f"{case_id}/actor"
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=case_actor_id)
        case = make(
            as_VulnerabilityCase,
            id_=case_id,
            name="TEST-REDELIVER",
            attributed_to=case_actor_id,
        )
        manager = make(
            as_CaseParticipant,
            id_=f"{case_id}/participants/case-actor-p",
            attributed_to=case_actor_id,
            context=case_id,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        case.case_participants.append(manager.id_)
        case.actor_participant_index[case_actor_id] = manager.id_
        dl.create(manager)
        dl.create(case)

        invite = rm_invite_to_case_activity(
            make(as_Actor, id_="https://example.org/users/coordinator"),
            to=["https://example.org/users/coordinator"],
            target=case_id,
            actor=case_actor_id,
            id_=f"{case_id}/invitations/1",
        )
        event = make_payload(invite, at=dl).model_copy(
            update={"receiving_actor_id": case_actor_id}
        )

        first = run_in_act(
            InviteActorToCaseReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            )
        )
        settle_as_the_inbox(dl, event, first)
        second = run_in_act(
            InviteActorToCaseReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            )
        )

        assert first.disposition is HandlerDisposition.APPLIED
        assert second.disposition is HandlerDisposition.SKIPPED
        from vultron.core.models.pending_case_inbox import (
            VultronPendingCaseInbox,
        )

        assert dl.read(VultronPendingCaseInbox.build_id(case_id)) is None
        archived = dl.read(ReceivedActivityRecord.build_id(invite.id_))
        assert isinstance(archived, ReceivedActivityRecord)
        assert archived.activity_id == invite.id_

    def test_reject_invite_actor_to_case_commits_ledger_entry(
        self, make_payload
    ):
        """RejectInviteActorToCaseReceivedUseCase commits a CaseLedgerEntry (AC-3).

        Reject(Invite(Actor)[target=VulnerabilityCaseStub]) carries the case reference
        in the nested
        Invite's ``target`` field (``inner_target_id``), not the top-level
        ``target`` of the Reject.  CM-11-003: use ``request.case_id`` which
        reads ``inner_target_id``.

        An inert participant record for the invitee must exist (CM-11-018);
        the test seeds one so the reject applies its effects.
        """
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.models.case_ledger_entry import (
            CaseLedgerEntry as WireCaseLedgerEntry,
        )
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.core.models.dimensions import RmDimension
        from vultron.core.models.participant_status import ParticipantStatus
        from vultron.core.states.rm import RM
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        case_id = "https://example.org/cases/case-reject-ri1"
        case_actor_id = f"{case_id}/actor"
        # The ledger commit is role-gated to the CASE_MANAGER, which here is
        # the case actor — so the tree runs in the case actor's store.
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=case_actor_id)
        invitee_id = "https://example.org/users/coordinator"

        case = make(
            as_VulnerabilityCase,
            id_=case_id,
            name="TEST-REJECT-INVITE",
            attributed_to=case_actor_id,
        )
        case_manager_participant = make(
            as_CaseParticipant,
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
            make(as_Actor, id_=invitee_id),
            to=[invitee_id],
            target=case_id,
            actor=case_actor_id,
            id_=f"{case_id}/invitations/1",
        )

        # Seed the inert participant record the reject will close (CM-11-018).
        # CreateInertInviteeParticipantNode would create this at invite-send
        # time; we seed it directly for the received-side test.
        inert_participant_id = f"{case_id}/participants/coordinator"
        inert_status = make(
            ParticipantStatus,
            context=case_id,
            attributed_to=invitee_id,
            rm=RmDimension(state=RM.RECEIVED),
            cvd_role=[CVDRole.VENDOR],
        )
        inert_participant = make(
            CaseParticipant,
            id_=inert_participant_id,
            attributed_to=invitee_id,
            context=case_id,
            case_roles=[CVDRole.VENDOR],
            participant_statuses=[inert_status],
            joined=False,
        )
        case.case_participants.append(inert_participant.id_)
        case.actor_participant_index[invitee_id] = inert_participant.id_

        dl.create(case_manager_participant)
        dl.create(inert_participant)
        dl.create(case)
        dl.create(invite)

        reject = _reject_invite(
            invite,
            actor=invitee_id,
        )
        event = make_payload(reject, at=dl)

        assert event.target_id is None, (
            "Precondition: Reject(Invite) has no top-level target"
        )
        assert event.case_id == case_id, (
            "Precondition: case_id resolves via inner_target_id"
        )

        run_in_act(
            RejectInviteActorToCaseReceivedUseCase(
                dl,
                event.model_copy(update={"receiving_actor_id": case_actor_id}),
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
                trigger_activity=TriggerActivityAdapter(dl),
            )
        )

        entries = [
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, WireCaseLedgerEntry) and e.case_id == case_id
        ]
        assert len(entries) >= 1, (
            "Expected at least one CaseLedgerEntry after reject-invite"
        )
        assert any("reject" in e.semantic_type for e in entries), (
            f"Expected a reject-invite ledger entry; got: {[e.semantic_type for e in entries]}"
        )

    def test_accept_invite_actor_to_case_adds_participant(
        self, monkeypatch, make_payload
    ):
        """AcceptInviteActorToCaseReceivedUseCase creates a as_CaseParticipant and adds them to the case."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        invitee_id = "https://example.org/users/coordinator"
        invitee = make(as_Organization, id_=invitee_id)
        case = make(
            VulnerabilityCase,
            id_="https://example.org/cases/caseIA1",
            name="TEST-ACCEPT-INVITE",
            attributed_to="https://example.org/users/owner",
        )
        seed_store_owner_as_case_manager(dl, case)
        seed_inert_invitee(dl, case, invitee_id)
        invite = rm_invite_to_case_activity(
            invitee,
            to=[invitee.id_],
            target=case.id_,
            actor="https://test.example/api/v2/actors/test-actor",
            roles=[CVDRole.VENDOR],
            id_="https://example.org/cases/caseIA1/invitations/1",
        )
        dl.create(invitee)
        dl.create(case)
        dl.create(invite)

        accept = _accept_invite(
            invite,
            actor=invitee_id,
        )

        event = make_payload(accept, at=dl)

        run_in_act(
            AcceptInviteActorToCaseReceivedUseCase(
                dl,
                event,
                sync_port=MagicMock(),
                wire_render_port=As2WireRenderAdapter(),
                trigger_activity=TriggerActivityAdapter(dl),
            )
        )

        case = dl.read(case.id_)
        assert case is not None
        case = cast(as_VulnerabilityCase, case)
        assert invitee_id in case.actor_participant_index

    @pytest.mark.spec("CM-11-001")
    def test_accept_invite_actor_to_case_records_active_embargo(
        self, monkeypatch, make_payload
    ):
        """AcceptInviteActorToCaseReceivedUseCase records the active embargo ID.

        The ID goes on the new participant (CM-10-001).
        """
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.models.case import VulnerabilityCase
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization
        from vultron.wire.as2.vocab.objects.embargo_event import (
            as_EmbargoEvent,
        )

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        invitee_id = "https://example.org/users/coordinator"
        invitee = make(as_Organization, id_=invitee_id)
        case = make(
            VulnerabilityCase,
            id_="https://example.org/cases/caseIA2",
            name="TEST-ACCEPT-INVITE-EMBARGO",
            attributed_to="https://example.org/users/owner",
        )
        embargo = make(
            as_EmbargoEvent,
            id_="https://example.org/cases/caseIA2/embargo_events/e1",
            content="Active embargo",
            context=case.id_,
            end_time=days_from_now(45),
        )
        activate(case, embargo.id_)
        seed_store_owner_as_case_manager(dl, case)
        seed_inert_invitee(dl, case, invitee_id)
        invite = rm_invite_to_case_activity(
            invitee,
            to=[invitee.id_],
            target=case.id_,
            actor="https://test.example/api/v2/actors/test-actor",
            roles=[CVDRole.VENDOR],
            id_="https://example.org/cases/caseIA2/invitations/1",
        )
        dl.create(invitee)
        dl.create(case)
        dl.create(embargo)
        dl.create(invite)

        accept = _accept_invite(
            invite,
            actor=invitee_id,
        )

        event = make_payload(accept, at=dl)

        run_in_act(
            AcceptInviteActorToCaseReceivedUseCase(
                dl,
                event,
                sync_port=MagicMock(),
                wire_render_port=As2WireRenderAdapter(),
                trigger_activity=TriggerActivityAdapter(dl),
            )
        )

        case = dl.read(case.id_)
        assert case is not None
        case = cast(VulnerabilityCase, case)
        participant_id = case.actor_participant_index.get(invitee_id)
        assert participant_id is not None
        participant_obj = dl.get(id_=participant_id)
        assert participant_obj is not None
        participant_obj = cast(Any, participant_obj)
        assert participant_obj.consent_for(embargo.id_) == "AGREED"

    @pytest.mark.spec("CM-11-001")
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
        from vultron.core.states.rm import RM
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        invitee_id = "https://example.org/users/coordinator_rm1"
        invitee = make(as_Organization, id_=invitee_id)
        owner_id = "https://example.org/users/owner"
        case = make(
            VulnerabilityCase,
            id_="https://example.org/cases/caseRM001",
            name="TEST-RM-LIFECYCLE",
            attributed_to=owner_id,
        )
        seed_store_owner_as_case_manager(dl, case)
        seed_inert_invitee(dl, case, invitee_id)
        invite = rm_invite_to_case_activity(
            invitee,
            to=[invitee.id_],
            target=case.id_,
            actor="https://test.example/api/v2/actors/test-actor",
            roles=[CVDRole.VENDOR],
            id_="https://example.org/cases/caseRM001/invitations/1",
        )
        dl.create(invitee)
        dl.create(case)
        dl.create(invite)

        accept = _accept_invite(
            invite,
            actor=invitee_id,
        )
        event = make_payload(accept, at=dl)

        run_in_act(
            AcceptInviteActorToCaseReceivedUseCase(
                dl,
                event,
                sync_port=MagicMock(),
                wire_render_port=As2WireRenderAdapter(),
                trigger_activity=TriggerActivityAdapter(dl),
            )
        )

        updated_case = cast(Any, dl.read(case.id_))
        participant_id = updated_case.actor_participant_index.get(invitee_id)
        participant_obj = cast(Any, dl.get(id_=participant_id))
        rm_states = [s.rm.state for s in participant_obj.participant_statuses]
        assert RM.VALID not in rm_states, "CM-11-001: no VALID at invite time"
        assert RM.ACCEPTED not in rm_states, (
            "CM-11-001: no ACCEPTED at invite time"
        )
        latest_status = participant_obj.participant_statuses[-1]
        assert latest_status.rm.state == RM.RECEIVED

    @pytest.mark.spec("PCR-07-008")
    def test_the_accept_is_applied_at_the_case_manager(self, make_payload):
        """PCR-07-008: the CASE_MANAGER is the actor that processes the Accept.

        The Case Owner is a *different* actor in this fixture, which is what
        lets the test tell the two apart: with owner and manager collapsed onto
        one actor, "the CASE_MANAGER processed it" is true however the handler
        chose (ISSUE-2789).  The sibling below delivers the same Accept to the
        Case Owner's store and shows it refused there, so "not the Case Owner"
        is asserted rather than assumed.
        """
        dl, accept = _seed_pcr708_exchange(receiver_id=_PCR708_MANAGER)

        result = _run_accept(dl, make_payload(accept, at=dl))

        assert result.disposition is HandlerDisposition.APPLIED, result.reason
        assert dl.outbox_list(), (
            "the CASE_MANAGER answers the join with the Announce and the"
            " full-case Invite (CM-11-008, CM-11-010)"
        )

    @pytest.mark.spec("PCR-07-008")
    @pytest.mark.spec("HP-01-005")
    def test_the_accept_is_refused_at_the_case_owner(self, make_payload):
        """The Case Owner is not the Accept's addressee, so it applies nothing.

        The refusal is pinned to its reason rather than to a bare ``REFUSED``:
        the Accept is addressed to the CASE_MANAGER the Invite named, which is
        the mechanism PCR-07-008 is about (HP-01-005).

        There is deliberately no "and the outbox is empty" assertion here. The
        receive tree runs ``doors`` before ``effects``, so a refusal at the
        addressee door means no emit stage ran at all: an empty outbox is
        entailed by the reason asserted above and could never be the failing
        line. What the Case Owner does with a copy it *is* addressed on is a
        different question, and ``_accept_invite(..., also_to=...)`` is the
        helper for asking it.
        """
        dl, accept = _seed_pcr708_exchange(receiver_id=_PCR708_OWNER)

        result = _run_accept(dl, make_payload(accept, at=dl))

        assert result.disposition is HandlerDisposition.REFUSED, result.reason
        assert "neither the sender nor a recipient" in (result.reason or "")

    @pytest.mark.spec("PCR-07-009")
    @pytest.mark.spec("PCR-08-010")
    def test_accept_invite_no_identity_spoofing(self, make_payload):
        """PCR-07-009: AcceptInviteActorToCaseReceivedUseCase MUST NOT emit
        RmEngageCaseActivity (Join) with actor=invitee_id from the Case Actor
        context.  The BT records RM.RECEIVED for the invitee without spoofing
        the invitee's identity (CM-11-001, PCR-08-010).

        The requirement cited here used to read PCR-07-008; that one is about
        which actor the Invite and its Accept name, and is covered by
        ``test_the_accept_is_applied_at_the_case_manager`` above.  "No
        actor-spoofed RM state-change activity" is PCR-07-009.
        """
        from typing import Any, cast

        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.core.states.rm import RM
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        invitee_id = "https://example.org/users/coordinator_rm2"
        invitee = make(as_Organization, id_=invitee_id)
        owner_id = "https://example.org/users/owner"
        case_manager_participant_id = (
            "https://example.org/cases/caseRM002/participants/case-manager"
        )
        # The receiving store's owner is the CASE_MANAGER: the role holder,
        # the receiving actor and the store owner must be one actor
        # (BT-05-006, BT-17-006).
        store_owner_id = "https://test.example/api/v2/actors/test-actor"
        case_manager_participant = make(
            CaseParticipant,
            id_=case_manager_participant_id,
            attributed_to=store_owner_id,
            context="https://example.org/cases/caseRM002",
            name="CaseManager",
            case_roles=[CVDRole.CASE_MANAGER],
        )
        case = make(
            VulnerabilityCase,
            id_="https://example.org/cases/caseRM002",
            name="TEST-RM-AUTO-ENGAGE",
            attributed_to=owner_id,
            case_participants=[case_manager_participant_id],
            actor_participant_index={
                store_owner_id: case_manager_participant_id
            },
        )
        invite = rm_invite_to_case_activity(
            invitee,
            to=[invitee.id_],
            target=case.id_,
            actor="https://test.example/api/v2/actors/test-actor",
            roles=[CVDRole.VENDOR],
            id_="https://example.org/cases/caseRM002/invitations/1",
        )
        dl.create(invitee)
        dl.create(case_manager_participant)
        seed_inert_invitee(dl, case, invitee_id)
        dl.create(case)
        dl.create(invite)

        accept = _accept_invite(
            invite,
            actor=invitee_id,
        )
        event = make_payload(accept, at=dl)

        run_in_act(
            AcceptInviteActorToCaseReceivedUseCase(
                dl,
                event,
                sync_port=MagicMock(),
                wire_render_port=As2WireRenderAdapter(),
                trigger_activity=TriggerActivityAdapter(dl),
            )
        )

        # PCR-07-009: no RM state-change activity may be emitted with
        # actor=invitee_id from the receiving CASE_MANAGER's context.  The
        # emitted set is read from the *CASE_MANAGER's* outbox, which is the
        # one the run writes to: the invitee's own outbox is empty here, so a
        # scan of it would pass whatever the run emitted (CONCERN-3019).
        queued = dl.outbox_list()
        emitted = [
            cast(Any, activity)
            for activity in (dl.read(item_id) for item_id in queued)
            if activity is not None
        ]
        # Counted, not just truthiness-checked: a list of unreadable rows is
        # truthy, so `assert emitted` alone would pass with every subject
        # silently dropped (#5535).
        assert len(emitted) == len(queued) and emitted, (
            "the Accept must emit the join cascade (CM-11-008, CM-11-010) and"
            f" every queued activity must be readable; {len(emitted)} of"
            f" {len(queued)} read back"
        )
        # The precondition, not a second assertion: "every sender is the
        # processing actor" only excludes the invitee while the two are
        # distinct actors, and both are fixture literals.  Asserting
        # `invitee_id not in senders` after the set equality below could never
        # be the failing line, which is the shape this PR exists to remove.
        assert invitee_id != dl.actor_id, (
            "the fixture must keep the invitee and the processing actor"
            " distinct, or naming the processing actor would not rule out"
            " naming the invitee (PCR-07-009)"
        )
        senders = {_as_id(a.actor) for a in emitted}
        assert senders == {dl.actor_id}, (
            "PCR-07-009/PCR-08-010: every activity emitted while processing"
            f" names the processing actor, never the invitee; got {senders!r}"
        )
        assert "Join" not in {str(a.type_) for a in emitted}, (
            "the invitee's own Join is the invitee's to send (PCR-08-010)"
        )

        # The participant should be at RM.RECEIVED only (CM-11-001).
        updated_case = cast(Any, dl.read(case.id_))
        participant_id = updated_case.actor_participant_index.get(invitee_id)
        assert participant_id is not None
        participant_obj = cast(Any, dl.get(id_=participant_id))
        assert participant_obj is not None
        rm_states = [s.rm.state for s in participant_obj.participant_statuses]
        assert RM.VALID not in rm_states, "CM-11-001: no VALID at invite time"
        assert RM.ACCEPTED not in rm_states, (
            "CM-11-001: no ACCEPTED at invite time"
        )
        latest_status = participant_obj.participant_statuses[-1]
        assert latest_status.rm.state == RM.RECEIVED, (
            f"Expected RM.RECEIVED after Accept(Invite) (CM-11-001), "
            f"got {latest_status.rm.state}"
        )

    def test_accept_invite_actor_to_case_records_case_event(
        self, monkeypatch, make_payload
    ):
        """AcceptInviteActorToCaseReceivedUseCase commits a canonical
        as_CaseLedgerEntry with semantic_type 'accept_invite_actor_to_case'
        (CM-02-009).

        record_event('participant_joined') was removed in #789; the trust
        guarantee now lives in as_CaseLedgerEntry.received_at written by
        CommitCaseLedgerEntryNode.
        """
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.models.case_ledger_entry import (
            CaseLedgerEntry as WireCaseLedgerEntry,
        )
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            # The canonical ledger belongs to the case actor, so the backfill
            # runs in the case actor's store.
            actor_id="https://example.org/cases/caseIA3/actor",
        )
        invitee_id = "https://example.org/users/coordinator"
        case_actor_id = "https://example.org/cases/caseIA3/actor"
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.base.objects.actors import as_Service

        invitee = make(as_Organization, id_=invitee_id)
        case = make(
            as_VulnerabilityCase,
            id_="https://example.org/cases/caseIA3",
            name="TEST-ACCEPT-INVITE-EVENT",
            attributed_to=case_actor_id,
        )
        invite = rm_invite_to_case_activity(
            invitee,
            to=[invitee.id_],
            target=case.id_,
            actor=case_actor_id,
            roles=[CVDRole.VENDOR],
            id_="https://example.org/cases/caseIA3/invitations/1",
        )
        dl.create(invitee)
        seed_inert_invitee(dl, case, invitee_id)
        dl.create(case)
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

        dl.create(make(as_Service, id_=case_actor_id, context=case.id_))
        case_manager_participant = make(
            as_CaseParticipant,
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

        accept = _accept_invite(
            invite,
            actor=invitee_id,
        )

        event = make_payload(accept, at=dl)

        run_in_act(
            AcceptInviteActorToCaseReceivedUseCase(
                dl,
                event,
                sync_port=MagicMock(),
                wire_render_port=As2WireRenderAdapter(),
                trigger_activity=TriggerActivityAdapter(dl),
            )
        )

        entries = [
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, WireCaseLedgerEntry) and e.case_id == case.id_
        ]
        assert len(entries) >= 1
        assert any(
            e.semantic_type == "accept_invite_actor_to_case" for e in entries
        )

    @pytest.mark.spec("CM-17-004")
    @pytest.mark.spec("CM-17-012")
    def test_accept_invite_backfills_canonical_ledger_from_genesis(
        self, make_payload
    ):
        """An inert invitee's first Accept joins it and backfills it."""
        from vultron.core.models.case_participant import CaseParticipant

        lj = _seed_late_joiner_case()
        dl, case, invitee_id = lj["dl"], lj["case"], lj["invitee_id"]
        invite, first, second = lj["invite"], lj["first"], lj["second"]
        trigger_activity = lj["trigger_activity"]
        sync_port = MagicMock()

        accept = _accept_invite(invite, actor=invitee_id)
        event = make_payload(accept, at=dl)
        run_in_act(
            AcceptInviteActorToCaseReceivedUseCase(
                dl,
                event,
                sync_port=sync_port,
                trigger_activity=trigger_activity,
                wire_render_port=As2WireRenderAdapter(),
            )
        )

        announced_log_indices = [
            kwargs["entry"].log_index
            for _, kwargs in sync_port.send_announce_log_entry.call_args_list
        ]
        announced_entries = [
            kwargs["entry"]
            for _, kwargs in sync_port.send_announce_log_entry.call_args_list
        ]
        # Entry 2 (accept_invite): committed while the invitee is inert, so
        #   its fan-out does NOT include the invitee.  It is the invitee's
        #   own Accept message, the entry for its consent and `joined`.
        # Backfill: runs BEFORE any further commit (CM-17-004 step 3 precedes
        #   any further fan-out to the invitee) and sends the ledger as it
        #   stands, entries 0, 1, 2, in log order.
        # Then the vendor's VF status (3), the CASE_MANAGER's own
        #   add_participant_status_to_participant entry, committed after the
        #   backfill so the invitee receives it in chain order, not ahead of
        #   genesis (#2898), and last the full-case Invite (4).  No
        #   add_case_participant entry is committed (CM-31-012).
        assert announced_log_indices == [0, 1, 2, 3, 4]
        assert [e.semantic_type for e in announced_entries[3:]] == [
            "add_participant_status_to_participant",
            "invite_actor_to_full_case",
        ]
        assert "add_case_participant" not in {
            e.semantic_type for e in dl.list_objects("CaseLedgerEntry")
        }
        assert announced_entries[0].entry_hash == first.entry_hash
        assert announced_entries[1].entry_hash == second.entry_hash

        record = dl.read(case.actor_participant_index[invitee_id])
        assert isinstance(record, CaseParticipant)
        assert record.joined is True
        # The backfill keeps no replication state (CM-17-012, #5074).
        assert dl.list_objects("ReplicationState") == []

    @pytest.mark.spec("SYNC-09-002")
    @pytest.mark.spec("CLP-07-013")
    def test_the_full_case_invite_is_recorded_after_the_accepts_entries(
        self, make_payload, monkeypatch
    ):
        """A consequent send follows the act's entries and is its own act (AC-5).

        The invitee's ``Accept`` is the act: its entry comes first, then the
        consequence entries the CASE_MANAGER writes for it (the vendor's VF
        status).  The full-case Invite is sent because of the act, so it comes
        after all of them, and as a send it is queued before its own entry is
        committed (ADR-0119).
        """
        from test.support.ledger import record_sends_and_commits

        lj = _seed_late_joiner_case()
        dl, invitee_id, invite = lj["dl"], lj["invitee_id"], lj["invite"]
        events = record_sends_and_commits(monkeypatch, lj["case_actor_id"])

        accept = _accept_invite(invite, actor=invitee_id)
        run_in_act(
            AcceptInviteActorToCaseReceivedUseCase(
                dl,
                make_payload(accept, at=dl),
                sync_port=MagicMock(),
                trigger_activity=lj["trigger_activity"],
                wire_render_port=As2WireRenderAdapter(),
            )
        )

        commits = [kind for kind, _ in events if kind != "queued"]
        assert commits == [
            "accept_invite_actor_to_case",
            "add_participant_status_to_participant",
            "invite_actor_to_full_case",
        ]
        (full_case_invite_id,) = [
            object_id
            for kind, object_id in events
            if kind == "invite_actor_to_full_case"
        ]
        consequence = events.index(
            next(e for e in events if e[0] == commits[1])
        )
        queued = events.index(("queued", full_case_invite_id))
        recorded = events.index(
            ("invite_actor_to_full_case", full_case_invite_id)
        )
        assert consequence < queued < recorded

    @pytest.mark.spec("CM-11-010")
    @pytest.mark.spec("CLP-07-015")
    def test_a_full_case_invite_whose_commit_failed_keeps_nothing_of_the_join(
        self, make_payload
    ):
        """The join and its full-case Invite are one act (CLP-07-015).

        The first run queues the Invite and its commit fails: the act keeps
        nothing, so no Invite is left queued and no entry of the join is
        recorded.  A redelivery of the Accept runs the join afresh and sends
        and records the Invite once.
        """
        from test.support.ledger import fail_commits
        from vultron.core.behaviors.sync import commit_tree

        lj = _seed_late_joiner_case()
        dl, invitee_id, invite = lj["dl"], lj["invitee_id"], lj["invite"]
        ledger_before = {e.id_ for e in dl.list_objects("CaseLedgerEntry")}
        accept = _accept_invite(invite, actor=invitee_id)

        def _accept(event) -> None:
            run_in_act(
                AcceptInviteActorToCaseReceivedUseCase(
                    dl,
                    event,
                    sync_port=MagicMock(),
                    trigger_activity=lj["trigger_activity"],
                    wire_render_port=As2WireRenderAdapter(),
                )
            )

        with pytest.MonkeyPatch.context() as mp:
            failed = fail_commits(
                mp,
                commit_tree,
                when=lambda kw: (
                    kw["semantic_type"] == "invite_actor_to_full_case"
                ),
            )
            # The Invite is queued, so the failed commit escapes rather than
            # failing the tree (BT-14-001).
            with pytest.raises(VultronBTInternalError, match="commit failed"):
                _accept(make_payload(accept, at=dl))
        (invite_id,) = failed
        assert invite_id not in dl.outbox_list()
        assert {
            e.id_ for e in dl.list_objects("CaseLedgerEntry")
        } == ledger_before

        # The inbox routes the redelivery as the copy intake archived
        # (IE-10-001), not as the resent body.
        _accept(archived_redelivery(dl, accept.id_))

        assert dl.outbox_list().count(invite_id) == 1
        recorded = [
            e.log_object_id
            for e in dl.list_objects("CaseLedgerEntry")
            if getattr(e, "semantic_type", None) == "invite_actor_to_full_case"
        ]
        assert recorded == [invite_id]

    @pytest.mark.spec("CM-17-009")
    def test_accept_invite_seeds_the_case_before_any_ledger_entry_reaches_the_invitee(
        self, make_payload
    ):
        """CM-17-004 (5) then (6): Announce(VulnerabilityCase) precedes every
        Announce(CaseLedgerEntry) addressed to the invitee.

        A late joiner that receives a ledger entry before its case seed enters
        the SYNC-15 pre-genesis path — Reject, then a from-genesis replay that
        interleaves with the join backfill (rcvcv V2/C2, #2898).  The two
        channels are observed on one mock manager so their relative order is
        what is asserted, not each channel alone.
        """
        lj = _seed_late_joiner_case()
        dl, invitee_id, invite = lj["dl"], lj["invitee_id"], lj["invite"]
        trigger_activity = lj["trigger_activity"]
        sync_port = MagicMock()
        manager = MagicMock()
        manager.attach_mock(trigger_activity, "trigger")
        manager.attach_mock(sync_port, "sync")

        accept = _accept_invite(invite, actor=invitee_id)
        event = make_payload(accept, at=dl)
        run_in_act(
            AcceptInviteActorToCaseReceivedUseCase(
                dl,
                event,
                sync_port=sync_port,
                trigger_activity=trigger_activity,
                wire_render_port=As2WireRenderAdapter(),
            )
        )

        ordered = [
            name
            for name, _args, kwargs in manager.mock_calls
            if name == "trigger.announce_vulnerability_case"
            or (
                name == "sync.send_announce_log_entry"
                and invitee_id in kwargs.get("to", [])
            )
        ]
        assert ordered, "neither channel reached the invitee"
        assert ordered[0] == "trigger.announce_vulnerability_case", (
            "the invitee must receive Announce(VulnerabilityCase) before any"
            f" Announce(CaseLedgerEntry); observed order: {ordered}"
        )
        assert ordered.count("trigger.announce_vulnerability_case") == 1

    @pytest.mark.spec("CLP-07-015")
    def test_a_backfill_that_fails_part_way_keeps_nothing_of_the_join(
        self, make_payload
    ):
        """A join backfill commits with its Accept or not at all (CLP-07-015).

        The inert invitee's backfill fails after its second entry: the act's
        own entry is rolled back with it and the record stays inert, so a
        redelivery of the Accept joins it again from the start.
        """
        from vultron.core.models.case_ledger_entry import CaseLedgerEntry
        from vultron.core.models.case_participant import CaseParticipant

        lj = _seed_late_joiner_case()
        dl, case, invitee_id = lj["dl"], lj["case"], lj["invitee_id"]
        first, second = lj["first"], lj["second"]
        sync_port = MagicMock()
        # The backfill sends 0, 1, then the Accept's own entry (2).
        sync_port.send_announce_log_entry.side_effect = [
            None,
            None,
            RuntimeError("delivery refused"),
        ]

        accept = _accept_invite(lj["invite"], actor=invitee_id)
        with pytest.raises(VultronBTInternalError):
            run_in_act(
                AcceptInviteActorToCaseReceivedUseCase(
                    dl,
                    make_payload(accept, at=dl),
                    sync_port=sync_port,
                    trigger_activity=lj["trigger_activity"],
                    wire_render_port=As2WireRenderAdapter(),
                )
            )

        assert sync_port.send_announce_log_entry.call_count == 3
        ledger = [
            e.entry_hash
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry) and e.case_id == case.id_
        ]
        assert ledger == [first.entry_hash, second.entry_hash], (
            "the Accept's own entry is rolled back with the backfill"
        )
        record = dl.read(case.actor_participant_index[invitee_id])
        assert isinstance(record, CaseParticipant)
        assert record.joined is False

        # A redelivery of the same Accept joins from the start.
        sync_port.reset_mock(side_effect=True)
        result = run_in_act(
            AcceptInviteActorToCaseReceivedUseCase(
                dl,
                make_payload(accept, at=dl),
                sync_port=sync_port,
                trigger_activity=lj["trigger_activity"],
                wire_render_port=As2WireRenderAdapter(),
            )
        )

        assert result.disposition is HandlerDisposition.APPLIED, result
        sent = [
            call.kwargs["entry"].log_index
            for call in sync_port.send_announce_log_entry.call_args_list
        ]
        assert sent[:3] == [0, 1, 2]
        record = dl.read(case.actor_participant_index[invitee_id])
        assert isinstance(record, CaseParticipant)
        assert record.joined is True

    @pytest.mark.spec("SYNC-03-009")
    @pytest.mark.spec("CLP-07-015")
    def test_a_backfill_held_back_at_a_broken_entry_keeps_nothing_of_the_join(
        self, make_payload
    ):
        """A join backfill that holds back an entry fails its Accept whole.

        The second stored entry no longer reproduces its hash, so the
        backfill sends the first and stops (SYNC-03-009).  The node returns
        ``FAILURE``, the act keeps nothing (CLP-07-015), and the invitee
        stays inert.
        """
        from vultron.core.models.case_ledger_entry import CaseLedgerEntry
        from vultron.core.models.case_participant import CaseParticipant

        lj = _seed_late_joiner_case()
        dl, case, invitee_id = lj["dl"], lj["case"], lj["invitee_id"]
        first, second = lj["first"], lj["second"]
        dl.save(tampered(second))
        sync_port = MagicMock()

        accept = _accept_invite(lj["invite"], actor=invitee_id)
        result = run_in_act(
            AcceptInviteActorToCaseReceivedUseCase(
                dl,
                make_payload(accept, at=dl),
                sync_port=sync_port,
                trigger_activity=lj["trigger_activity"],
                wire_render_port=As2WireRenderAdapter(),
            )
        )

        assert result.disposition is HandlerDisposition.REFUSED, result
        assert second.id_ in (result.reason or ""), result.reason
        assert dl.outbox_list() == []
        sent_to_invitee = [
            call.kwargs["entry"].log_index
            for call in sync_port.send_announce_log_entry.call_args_list
            if call.kwargs["to"] == [invitee_id]
        ]
        assert sent_to_invitee == [0]
        ledger = [
            e.log_index
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry) and e.case_id == case.id_
        ]
        assert sorted(ledger) == [first.log_index, second.log_index], (
            "the Accept's own entry is rolled back with the backfill"
        )
        record = dl.read(case.actor_participant_index[invitee_id])
        assert isinstance(record, CaseParticipant)
        assert record.joined is False

    def test_accept_invite_backfill_runs_when_the_announce_cannot_be_sent(
        self, make_payload
    ):
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.base.objects.actors import (
            as_Organization,
            as_Service,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            # The canonical ledger belongs to the case actor, so the backfill
            # runs in the case actor's store.
            actor_id="https://example.org/actors/case-actor-lj4",
        )
        invitee_id = "https://example.org/users/late-joiner-noannounce"
        case_actor_id = "https://example.org/actors/case-actor-lj4"
        invitee = make(as_Organization, id_=invitee_id)
        case_actor = make(as_Service, id_=case_actor_id, context="unused")
        case = make(
            as_VulnerabilityCase,
            id_="https://example.org/cases/caseLJ4",
            name="TEST-LATE-JOIN-NO-ANNOUNCE",
            attributed_to=case_actor_id,
        )
        object.__setattr__(case_actor, "context", case.id_)
        from vultron.enums.roles import CVDRole

        invite = rm_invite_to_case_activity(
            invitee,
            to=[invitee.id_],
            target=case.id_,
            actor=case_actor_id,
            roles=[CVDRole.VENDOR],
            id_=f"{case.id_}/invitations/1",
        )
        dl.create(invitee)
        dl.create(case_actor)
        seed_inert_invitee(dl, case, invitee_id)
        dl.create(case)
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

        case_manager_participant = make(
            as_CaseParticipant,
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
            semantic_type="submit_report",
            actor_id=case_actor_id,
            payload_snapshot={"index": 0},
        )
        _seed_ledger_entry(
            dl,
            case_id=case.id_,
            object_id=f"{case.id_}/events/1",
            semantic_type="add_participant_status",
            actor_id=case_actor_id,
            payload_snapshot={"index": 1},
        )

        sync_port = MagicMock()
        # The port builds the CASE_MANAGER's own entries, but the Announce
        # cannot be built: the accept tree logs that and goes on (MV-10-003).
        trigger_activity = with_ledger_records(MagicMock(), dl)
        trigger_activity.announce_vulnerability_case.side_effect = (
            RuntimeError("announce unavailable")
        )
        # The full-case Invite is part of the same act, so it must be built
        # for the act to keep its backfill (CLP-07-015).
        trigger_activity.invite_actor_to_full_case.side_effect = (
            TriggerActivityAdapter(dl).invite_actor_to_full_case
        )
        accept = _accept_invite(invite, actor=invitee_id)
        event = make_payload(accept, at=dl)
        run_in_act(
            AcceptInviteActorToCaseReceivedUseCase(
                dl,
                event,
                sync_port=sync_port,
                trigger_activity=trigger_activity,
                wire_render_port=As2WireRenderAdapter(),
            )
        )

        announced_entries = [
            kwargs["entry"]
            for _, kwargs in sync_port.send_announce_log_entry.call_args_list
        ]
        # The Accept's own entry (2) fans out while the invitee is inert, so
        # it skips the invitee; the backfill then sends 0, 1 and 2, and the
        # vendor's VF status (3) and the full-case Invite (4) follow by
        # fan-out.  This holds even when the Announce could not be sent.
        assert [entry.log_index for entry in announced_entries] == [
            0,
            1,
            2,
            3,
            4,
        ]


def _assert_a_duplicate_answer(
    result,
    dl,
    *,
    case_id: str,
    record_before,
    ledger_before,
    sync_port,
    trigger,
) -> None:
    """The CM-17-012 duplicate answer: SKIPPED, and nothing written or sent."""
    from vultron.core.models.case_ledger_entry import CaseLedgerEntry

    assert result.disposition is HandlerDisposition.SKIPPED, result
    ledger = [
        e.entry_hash
        for e in dl.list_objects("CaseLedgerEntry")
        if isinstance(e, CaseLedgerEntry) and e.case_id == case_id
    ]
    assert ledger == ledger_before, "a duplicate commits no ledger entry"
    stored = dl.read(record_before.id_)
    assert stored is not None
    assert stored.model_dump() == record_before.model_dump(), (
        "a duplicate changes no participant record or consent row"
    )
    assert dl.outbox_list() == []
    sync_port.send_announce_log_entry.assert_not_called()
    trigger.announce_vulnerability_case.assert_not_called()
    trigger.invite_actor_to_full_case.assert_not_called()


@pytest.mark.spec("CM-17-012")
@pytest.mark.spec("CLP-13-001")
class TestJoinedOrRemovedStubAcceptIsADuplicate:
    """A stub-Invite Accept from a joined or removed participant (CM-17-012).

    The duplicate test reads the participant record alone, never the
    replication state the CASE_MANAGER holds for the participant.
    """

    def _accept_over(
        self, make_payload, *, removed: bool, joined: bool = True
    ):
        """Run the Accept over the late-joiner case's invitee record."""
        from vultron.core.models.case_ledger_entry import CaseLedgerEntry
        from vultron.core.models.case_participant import CaseParticipant

        lj = _seed_late_joiner_case()
        dl, case, invitee_id = lj["dl"], lj["case"], lj["invitee_id"]
        record = dl.read(case.actor_participant_index[invitee_id])
        assert isinstance(record, CaseParticipant)
        # Seated at case initialization, or it already accepted: joined.
        record.joined = joined
        if removed:
            record.record_removal(f"{case.id_}/removals/1")
        dl.save(record)
        ledger_before = [
            e.entry_hash
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry)
        ]
        sync_port = MagicMock()
        trigger = lj["trigger_activity"]

        result = run_in_act(
            AcceptInviteActorToCaseReceivedUseCase(
                dl,
                make_payload(
                    _accept_invite(lj["invite"], actor=invitee_id), at=dl
                ),
                sync_port=sync_port,
                trigger_activity=trigger,
                wire_render_port=As2WireRenderAdapter(),
            )
        )

        _assert_a_duplicate_answer(
            result,
            dl,
            case_id=case.id_,
            record_before=record,
            ledger_before=ledger_before,
            sync_port=sync_port,
            trigger=trigger,
        )

    def test_a_joined_participant_with_no_replication_state(
        self, make_payload
    ):
        """A participant seated without a replication state: a duplicate.

        Before #5074 the missing state read as "no join backfill yet", and
        the Accept ran a first join backfill.
        """
        self._accept_over(make_payload, removed=False)

    def test_a_removed_participant(self, make_payload):
        """A removed participant is sent nothing until reinstated (CM-31-013)."""
        self._accept_over(make_payload, removed=True)

    def test_a_participant_removed_before_it_joined(self, make_payload):
        """Removal alone makes the Accept a duplicate, joined or not.

        Before #5074 an inert record that was removed could still join
        through its Accept; CM-17-012 names a removed record a duplicate.
        """
        self._accept_over(make_payload, removed=True, joined=False)

    @pytest.mark.spec("CM-10-005")
    def test_a_joined_participant_with_an_embargo_pause_state(
        self, make_payload
    ):
        """A joined non-signatory paused by the embargo gate: a duplicate.

        The fan-out wrote a pause into its replication state (CM-10-005).
        That state says nothing about a join, and the Accept leaves the
        invitee's ``INVITED`` row as it is: a joined participant consents to
        an embargo only through that embargo's own Invite.
        """
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.core.models.embargo_consent import EmbargoConsent
        from vultron.core.models.embargo_event import EmbargoEvent
        from vultron.core.models.replication_state import (
            VultronReplicationState,
        )
        from vultron.core.states.participant_embargo_consent import (
            EmbargoConsentState,
        )
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.base.objects.actors import (
            as_Organization,
            as_Service,
        )

        case_actor_id = "https://example.org/actors/case-actor-lj4"
        invitee_id = "https://example.org/users/seated-non-signatory"
        case_id = "https://example.org/cases/caseLJ4"
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=case_actor_id)
        invitee = make(as_Organization, id_=invitee_id)
        dl.create(invitee)
        dl.create(make(as_Service, id_=case_actor_id, context=case_id))
        embargo = make(
            EmbargoEvent,
            id_=f"{case_id}/embargoes/1",
            context=case_id,
            end_time=days_from_now(45),
        )
        dl.create(embargo)
        case = make(
            VulnerabilityCase, id_=case_id, attributed_to=case_actor_id
        )
        activate(case, embargo)
        for actor_id, consent, roles in (
            (
                case_actor_id,
                EmbargoConsentState.AGREED,
                [CVDRole.CASE_MANAGER],
            ),
            (invitee_id, EmbargoConsentState.INVITED, []),
        ):
            participant = make(
                CaseParticipant,
                id_=f"{case_id}/participants/{actor_id.rsplit('/', 1)[-1]}",
                attributed_to=actor_id,
                context=case_id,
                case_roles=roles,
                embargo_consents=[
                    EmbargoConsent(embargo_id=embargo.id_, state=consent)
                ],
            )
            dl.create(participant)
            case.add_participant(participant)
        dl.create(case)
        invite = rm_invite_to_case_activity(
            invitee,
            to=[invitee_id],
            target=case_id,
            actor=case_actor_id,
            id_=f"{case_id}/invitations/1",
        )
        dl.create(invite)
        ledger_before = [
            _seed_ledger_entry(
                dl,
                case_id=case_id,
                object_id=f"{case_id}/events/{index}",
                semantic_type="submit_report",
                actor_id=case_actor_id,
                payload_snapshot={"index": index},
            ).entry_hash
            for index in range(2)
        ]
        pause = VultronReplicationState(
            case_id=case_id,
            peer_id=invitee_id,
            embargo_paused_from_index=1,
            updated_at=ACT_AT,
        )
        dl.save(pause)
        record = dl.read(f"{case_id}/participants/seated-non-signatory")
        assert isinstance(record, CaseParticipant)
        assert record.joined is True

        trigger = with_ledger_records(MagicMock(), dl)
        sync_port = MagicMock()
        result = run_in_act(
            AcceptInviteActorToCaseReceivedUseCase(
                dl,
                make_payload(_accept_invite(invite, actor=invitee_id), at=dl),
                sync_port=sync_port,
                trigger_activity=trigger,
                wire_render_port=As2WireRenderAdapter(),
            )
        )

        _assert_a_duplicate_answer(
            result,
            dl,
            case_id=case_id,
            record_before=record,
            ledger_before=ledger_before,
            sync_port=sync_port,
            trigger=trigger,
        )
        assert dl.read(pause.id_) == pause


class TestAcceptInviteRolesAC4:
    """AC-4: the inert record the stub Invite created carries the Invite's roles."""

    def test_roles_from_invite_set_on_participant(self, make_payload):
        """AC-4: Accept(Invite) activates the record, which keeps the Invite's roles."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        invitee_id = "https://example.org/users/vendor2"
        invitee = make(as_Organization, id_=invitee_id)
        case = make(
            VulnerabilityCase,
            id_="https://example.org/cases/ac4-test",
            name="AC-4 roles test",
            attributed_to="https://example.org/users/owner",
        )
        seed_store_owner_as_case_manager(dl, case)
        seed_inert_invitee(
            dl, case, invitee_id, [CVDRole.VENDOR, CVDRole.COORDINATOR]
        )
        invite = rm_invite_to_case_activity(
            invitee,
            to=[invitee.id_],
            target=case.id_,
            actor="https://test.example/api/v2/actors/test-actor",
            id_="https://example.org/cases/ac4-test/invitations/1",
            roles=["vendor"],
        )
        dl.create(invitee)
        dl.create(case)
        dl.create(invite)

        accept = _accept_invite(invite, actor=invitee_id)
        event = make_payload(accept, at=dl)
        run_in_act(
            AcceptInviteActorToCaseReceivedUseCase(
                dl,
                event,
                sync_port=MagicMock(),
                wire_render_port=As2WireRenderAdapter(),
                trigger_activity=TriggerActivityAdapter(dl),
            )
        )

        reloaded_case = cast(Any, dl.read(case.id_))
        participant_id = reloaded_case.actor_participant_index.get(invitee_id)
        assert participant_id is not None, (
            "invitee must be registered as participant"
        )
        participant = cast(Any, dl.get(id_=participant_id))
        assert participant is not None
        # The record keeps the roles it was created with; the Accept applies
        # none of its own (CM-11-021).  Seeding a role the Invite does not
        # name makes a re-applied Invite visible.
        assert set(participant.case_roles) == {
            CVDRole.VENDOR,
            CVDRole.COORDINATOR,
        }

    @pytest.mark.spec("CM-11-049")
    @pytest.mark.spec("CM-11-019")
    def test_no_roles_invite_refused_not_applied(self, make_payload):
        """CM-11-019: Accept of a no-roles Invite is REFUSED, no participant created.

        A stub Invite with no roles is refused at send time, so no inert record
        exists for it; the Accept finds none and is refused (CM-11-021).  A
        participant with empty case_roles is never created.
        """
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        invitee_id = "https://example.org/users/vendor3"
        invitee = make(as_Organization, id_=invitee_id)
        case = make(
            VulnerabilityCase,
            id_="https://example.org/cases/ac4-neg",
            name="AC-4 negative",
            attributed_to="https://example.org/users/owner",
        )
        seed_store_owner_as_case_manager(dl, case)
        invite = rm_invite_to_case_activity(
            invitee,
            to=[invitee.id_],
            target=case.id_,
            actor="https://test.example/api/v2/actors/test-actor",
            id_="https://example.org/cases/ac4-neg/invitations/1",
        )
        dl.create(invitee)
        dl.create(case)
        dl.create(invite)

        accept = _accept_invite(invite, actor=invitee_id)
        event = make_payload(accept, at=dl)
        result = run_in_act(
            AcceptInviteActorToCaseReceivedUseCase(
                dl,
                event,
                sync_port=MagicMock(),
                wire_render_port=As2WireRenderAdapter(),
                trigger_activity=TriggerActivityAdapter(dl),
            )
        )

        assert result.disposition == HandlerDisposition.REFUSED, (
            f"Expected REFUSED for no-roles invite, got {result.disposition}"
        )
        # No participant should have been created
        reloaded_case = cast(Any, dl.read(case.id_))
        participant_id = reloaded_case.actor_participant_index.get(invitee_id)
        assert participant_id is None, (
            "No participant record should be created for a no-roles invite"
        )


class TestInviteDispositions:
    """#2255: each invite exit reports what it did (HP-01-003)."""

    _OWNER = "https://example.org/users/owner"
    _INVITEE = "https://example.org/users/coordinator"

    def _dl(
        self, actor_id: str = "https://test.example/api/v2/actors/test-actor"
    ):
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        return SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)

    def _invite(self, case_id: str, issuer: str | None = None):
        from vultron.enums.roles import CVDRole

        return rm_invite_to_case_activity(
            make(as_Actor, id_=self._INVITEE),
            to=[self._INVITEE],
            target=case_id,
            actor=issuer or self._OWNER,
            id_=f"{case_id}/invitations/1",
            roles=[CVDRole.VENDOR],
        )

    def _recorded_invite(self, dl, case_id: str):
        """The stub Invite the CASE_MANAGER sent and recorded (CM-11-017)."""
        invite = self._invite(case_id, issuer=dl.actor_id)
        dl.create(invite)
        return invite

    def _seed_case(self, dl, case_id: str, manager_id: str | None = None):
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        case = make(
            as_VulnerabilityCase,
            id_=case_id,
            name="DISPOSITION",
            attributed_to=self._OWNER,
        )
        if manager_id is not None:
            manager = make(
                as_CaseParticipant,
                id_=f"{case_id}/participants/manager",
                attributed_to=manager_id,
                context=case_id,
                case_roles=[CVDRole.CASE_MANAGER],
            )
            case.case_participants.append(manager.id_)
            case.actor_participant_index[manager_id] = manager.id_
            dl.create(manager)
        dl.create(case)
        return case

    @pytest.mark.spec("HP-01-003")
    def test_invitee_path_redelivery_is_skipped(self, make_payload):
        # dl owner must match the invitee so the AC-1 trust-anchor check passes.
        dl = self._dl(actor_id=self._INVITEE)
        event = make_payload(
            self._invite("https://example.org/cases/d-inv1"), at=dl
        )

        first = run_in_act(
            InviteActorToCaseReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            )
        )
        settle_as_the_inbox(dl, event, first)
        second = run_in_act(
            InviteActorToCaseReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            )
        )

        assert first.disposition == HandlerDisposition.APPLIED
        assert second.disposition == HandlerDisposition.SKIPPED

    @pytest.mark.spec("HP-01-003")
    def test_reject_invite_without_case_is_refused(self):
        dl = self._dl()
        event = MagicMock(case_id=None, receiving_actor_id=None)

        result = run_in_act(
            RejectInviteActorToCaseReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
                trigger_activity=TriggerActivityAdapter(dl),
            )
        )

        assert result.disposition == HandlerDisposition.REFUSED

    @pytest.mark.spec("HP-01-003")
    @pytest.mark.spec("HP-01-005")
    def test_reject_invite_at_non_case_manager_is_refused(self, make_payload):
        """Only the CASE_MANAGER records a declined invite; others refuse (#3752)."""
        case_id = "https://example.org/cases/d-rj1"
        dl = self._dl()
        self._seed_case(dl, case_id, manager_id=self._OWNER)
        event = make_payload(
            _reject_invite(
                self._recorded_invite(dl, case_id), actor=self._INVITEE
            ),
            at=dl,
        )

        result = run_in_act(
            RejectInviteActorToCaseReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
                trigger_activity=TriggerActivityAdapter(dl),
            )
        )

        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason is not None and "CASE_MANAGER" in result.reason

    @pytest.mark.spec("BT-17-001")
    @pytest.mark.spec("HP-01-005")
    def test_accept_invite_at_non_case_manager_is_refused(self, make_payload):
        """Admitting the invitee is the CASE_MANAGER's; a copy-holder refuses.

        The receiving store's owner is not the case's CASE_MANAGER, so the
        gated effects do not run: no participant is created, nothing is
        queued, and the handler says so (#3752).
        """
        case_id = "https://example.org/cases/d-ac-nm"
        dl = self._dl()
        case = self._seed_case(dl, case_id, manager_id=self._OWNER)
        invite = self._invite(case_id)
        dl.create(invite)
        # The copy names this store too, so the CASE_MANAGER gate, not the
        # addressee door (HP-01-005), is what refuses it.
        event = make_payload(
            _accept_invite(
                invite, actor=self._INVITEE, also_to=(dl.actor_id,)
            ),
            at=dl,
        )

        result = run_in_act(
            AcceptInviteActorToCaseReceivedUseCase(
                dl,
                event,
                sync_port=MagicMock(),
                wire_render_port=As2WireRenderAdapter(),
                trigger_activity=TriggerActivityAdapter(dl),
            )
        )

        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason is not None and "CASE_MANAGER" in result.reason
        reloaded = cast(Any, dl.read(case.id_))
        assert self._INVITEE not in reloaded.actor_participant_index
        assert dl.outbox_list() == []

    @pytest.mark.spec("HP-01-003")
    def test_reject_invite_for_unknown_case_is_refused(self, make_payload):
        dl = self._dl()
        event = make_payload(
            _reject_invite(
                self._recorded_invite(
                    dl, "https://example.org/cases/d-rj-missing"
                ),
                actor=self._INVITEE,
            ),
            at=dl,
        )

        result = run_in_act(
            RejectInviteActorToCaseReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
                trigger_activity=TriggerActivityAdapter(dl),
            )
        )

        assert result.disposition == HandlerDisposition.REFUSED
        # The reply's type declares the manager path alone, so a store that
        # holds no replica of the case is refused at the path stage, with the
        # reason composed from the resolved path (HP-01-039).
        assert result.reason is not None
        assert "holds no replica of case" in result.reason

    @pytest.mark.spec("CM-11-018")
    def test_reject_invite_at_case_manager_refused_when_no_inert_record(
        self, make_payload
    ):
        """CM-11-018: Reject refused when no inert participant record exists.

        The CASE_MANAGER must refuse a Reject(Invite) when it holds no
        participant record for the invitee — a silent no-op is not allowed.
        The refusal must carry a reason naming the missing record.
        """
        case_id = "https://example.org/cases/d-rj2"
        dl = self._dl(actor_id=self._OWNER)
        self._seed_case(dl, case_id, manager_id=self._OWNER)
        event = make_payload(
            _reject_invite(
                self._recorded_invite(dl, case_id), actor=self._INVITEE
            ),
            receiving_actor_id=self._OWNER,
            at=dl,
        )

        result = run_in_act(
            RejectInviteActorToCaseReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
                trigger_activity=TriggerActivityAdapter(dl),
            )
        )

        assert result.disposition == HandlerDisposition.REFUSED, (
            f"Expected REFUSED when no inert record, got {result.disposition}"
        )
        assert result.reason is not None
        assert "participant" in result.reason.lower(), (
            f"Refusal reason should mention participant record, got: {result.reason!r}"
        )

    @pytest.mark.spec("HP-01-003")
    def test_reject_invite_at_case_manager_is_applied_with_inert_record(
        self, make_payload
    ):
        """With an inert record present, Reject(Invite) is APPLIED (CM-11-007).

        This is the normal path: invite was sent → inert record created →
        invitee rejects → record closed to RM.CLOSED.
        """
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.core.models.dimensions import RmDimension
        from vultron.core.models.participant_status import ParticipantStatus
        from vultron.core.states.rm import RM
        from vultron.enums.roles import CVDRole

        case_id = "https://example.org/cases/d-rj2-with-record"
        dl = self._dl(actor_id=self._OWNER)
        self._seed_case(dl, case_id, manager_id=self._OWNER)

        # Seed the inert participant record the reject will close.
        inert_id = f"{case_id}/participants/{self._INVITEE.split('/')[-1]}"
        inert_status = make(
            ParticipantStatus,
            context=case_id,
            attributed_to=self._INVITEE,
            rm=RmDimension(state=RM.RECEIVED),
            cvd_role=[CVDRole.VENDOR],
        )
        inert = make(
            CaseParticipant,
            id_=inert_id,
            attributed_to=self._INVITEE,
            context=case_id,
            case_roles=[CVDRole.VENDOR],
            participant_statuses=[inert_status],
            joined=False,
        )
        _case = dl.read(case_id)
        assert isinstance(_case, VulnerabilityCase)
        _case.case_participants.append(inert.id_)
        _case.actor_participant_index[self._INVITEE] = inert.id_
        dl.create(inert)
        dl.save(_case)

        event = make_payload(
            _reject_invite(
                self._recorded_invite(dl, case_id), actor=self._INVITEE
            ),
            receiving_actor_id=self._OWNER,
            at=dl,
        )

        result = run_in_act(
            RejectInviteActorToCaseReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
                trigger_activity=TriggerActivityAdapter(dl),
            )
        )

        assert result.disposition == HandlerDisposition.APPLIED

    @pytest.mark.spec("HP-01-003")
    def test_accept_invite_without_invitee_is_refused(self):
        dl = self._dl()
        event = MagicMock(
            case_id="https://example.org/cases/d-ac0",
            invitee_id=None,
            receiving_actor_id=None,
        )

        result = run_in_act(
            AcceptInviteActorToCaseReceivedUseCase(
                dl,
                event,
                sync_port=MagicMock(),
                wire_render_port=As2WireRenderAdapter(),
                trigger_activity=TriggerActivityAdapter(dl),
            )
        )

        assert result.disposition == HandlerDisposition.REFUSED

    @pytest.mark.spec("HP-01-003")
    def test_accept_invite_for_unknown_case_is_refused(self, make_payload):
        dl = self._dl()
        event = make_payload(
            _accept_invite(
                self._recorded_invite(
                    dl, "https://example.org/cases/d-ac-missing"
                ),
                actor=self._INVITEE,
            ),
            at=dl,
        )

        result = run_in_act(
            AcceptInviteActorToCaseReceivedUseCase(
                dl,
                event,
                sync_port=MagicMock(),
                wire_render_port=As2WireRenderAdapter(),
                trigger_activity=TriggerActivityAdapter(dl),
            )
        )

        assert result.disposition == HandlerDisposition.REFUSED
        # The reply's type declares the manager path alone, so a store that
        # holds no replica of the case is refused at the path stage, with the
        # reason composed from the resolved path (HP-01-039).
        assert result.reason is not None
        assert "holds no replica of case" in result.reason

    @pytest.mark.spec("CM-11-052")
    @pytest.mark.spec("CM-11-021")
    def test_accept_invite_refused_when_no_participant_record(
        self, make_payload
    ):
        """CM-11-021: an Accept never creates a participant.

        The CASE_MANAGER recorded the stub Invite but holds no participant
        record for the invitee, so the Accept is refused with a reason naming
        the missing record, and nothing is created, committed or queued.
        """
        case_id = "https://example.org/cases/d-ac-norecord"
        dl = self._dl()
        self._seed_case(dl, case_id, manager_id=dl.actor_id)
        invite = self._invite(case_id, issuer=dl.actor_id)
        dl.create(invite)
        event = make_payload(
            _accept_invite(invite, actor=self._INVITEE), at=dl
        )
        sync_port = MagicMock()

        result = run_in_act(
            AcceptInviteActorToCaseReceivedUseCase(
                dl,
                event,
                sync_port=sync_port,
                wire_render_port=As2WireRenderAdapter(),
                trigger_activity=TriggerActivityAdapter(dl),
            )
        )

        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason is not None
        assert "participant record" in result.reason
        stored = dl.read(case_id)
        assert isinstance(stored, VulnerabilityCase)
        assert self._INVITEE not in stored.actor_participant_index
        from vultron.core.models.case_ledger_entry import CaseLedgerEntry

        ledger = [
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry)
        ]
        assert not any(
            e.semantic_type == "accept_invite_actor_to_case" for e in ledger
        )
        sync_port.send_announce_log_entry.assert_not_called()

    @pytest.mark.spec("HP-01-003")
    def test_accept_invite_redelivery_is_skipped(self, make_payload):
        """A second Accept once the invitee has fully joined is a duplicate."""
        case_id = "https://example.org/cases/d-ac1"
        dl = self._dl()
        # The store owner admits the invitee: it must hold CASE_MANAGER.
        self._seed_case(dl, case_id, manager_id=dl.actor_id)
        invite = self._invite(case_id, issuer=dl.actor_id)
        dl.create(invite)
        seeded = dl.read(case_id)
        assert isinstance(seeded, VulnerabilityCase)
        seed_inert_invitee(dl, seeded, self._INVITEE)
        dl.save(seeded)
        event = make_payload(
            _accept_invite(invite, actor=self._INVITEE), at=dl
        )

        first = run_in_act(
            AcceptInviteActorToCaseReceivedUseCase(
                dl,
                event,
                sync_port=MagicMock(),
                wire_render_port=As2WireRenderAdapter(),
                trigger_activity=TriggerActivityAdapter(dl),
            )
        )
        second = run_in_act(
            AcceptInviteActorToCaseReceivedUseCase(
                dl,
                event,
                sync_port=MagicMock(),
                wire_render_port=As2WireRenderAdapter(),
                trigger_activity=TriggerActivityAdapter(dl),
            )
        )

        assert first.disposition == HandlerDisposition.APPLIED
        assert second.disposition == HandlerDisposition.SKIPPED
