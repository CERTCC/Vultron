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

import pytest

from test.core.use_cases.received.conftest import (
    seed_store_owner_as_case_manager,
)
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.use_case_result import HandlerDisposition
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


def _outbound_blob(activity) -> str:
    """The sealed body the real adapter returns alongside the activity id."""
    return str(
        activity.model_dump_json(
            by_alias=True, exclude_none=True, serialize_as_any=True
        )
    )


def _add_participant_result(case, case_actor_id: str, invitee_id: str):
    """``(id, blob)`` as ``TriggerActivityPort.add_participant_to_case`` returns.

    The node records the blob verbatim as the ledger snapshot (VM-08-003), so
    it has to be a real, complete ``Add(CaseParticipant, Case)``.
    """
    from vultron.wire.as2.factories import add_participant_to_case_activity
    from vultron.wire.as2.vocab.objects.case_participant import (
        as_CaseParticipant,
    )

    activity = add_participant_to_case_activity(
        participant=as_CaseParticipant(
            id_=f"{invitee_id}#participant",
            attributed_to=invitee_id,
            context=case.id_,
        ),
        target=case.id_,
        actor=case_actor_id,
        id_=f"{case.id_}/activities/add-participant-1",
    )
    return activity.id_, _outbound_blob(activity)


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
    from vultron.core.models.case_ledger_entry import CaseLedgerEntry
    from vultron.core.sync_helpers import _reconstruct_tail_hash

    tail_hash, tail_index = _reconstruct_tail_hash(case_id, dl)
    chain_entry = HashChainLedgerRecord(
        case_id=case_id,
        log_index=tail_index + 1,
        object_id=object_id,
        event_type=event_type,
        payload_snapshot=payload_snapshot or {},
        prev_log_hash=tail_hash,
    )
    entry = CaseLedgerEntry(
        case_id=chain_entry.case_id,
        log_index=chain_entry.log_index,
        term=chain_entry.term,
        log_object_id=chain_entry.object_id,
        event_type=chain_entry.event_type,
        payload_snapshot=dict(chain_entry.payload_snapshot),
        prev_log_hash=chain_entry.prev_log_hash,
        entry_hash=chain_entry.entry_hash,
    )
    dl.save(entry)
    return entry


def _seed_late_joiner_case() -> dict[str, Any]:
    """Case-actor store with a CASE_MANAGER, a two-entry ledger, and an Invite.

    Shared by the late-joiner tests: the invitee is not yet a participant, so
    ``Accept(Invite)`` drives the full admission sequence (CM-17-004).  Returns
    the store and the objects the assertions need, plus a ``trigger_activity``
    mock whose ``add_participant_to_case`` side effect stores a real
    ``Add(CaseParticipant)`` so ``EmitAddCaseParticipantNode`` can snapshot it.
    """
    from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
    from vultron.enums.roles import CVDRole
    from vultron.wire.as2.factories import add_participant_to_case_activity
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
    invitee = as_Organization(id_=invitee_id)
    case_actor = as_Service(id_=case_actor_id, context="unused")
    case = as_VulnerabilityCase(
        id_="https://example.org/cases/caseLJ1",
        name="TEST-LATE-JOIN-BACKFILL",
        attributed_to=case_actor_id,
    )
    object.__setattr__(case_actor, "context", case.id_)
    invite = rm_invite_to_case_activity(
        invitee,
        target=case.id_,
        actor=case_actor_id,
        id_=f"{case.id_}/invitations/1",
    )
    dl.create(invitee)
    dl.create(case_actor)
    dl.create(case)

    case_manager_participant = as_CaseParticipant(
        id_=f"{case.id_}/participants/case-actor-p",
        attributed_to=case_actor_id,
        context=case.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    dl.create(case_manager_participant)
    case.case_participants.append(case_manager_participant.id_)
    case.actor_participant_index[case_actor_id] = case_manager_participant.id_
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

    add_activity_id = f"{case.id_}/activities/add-participant-1"

    def _store_add_participant(**kwargs):
        participant_id = kwargs.get("participant_id", invitee_id)
        wire_p = as_CaseParticipant(
            id_=participant_id,
            attributed_to=invitee_id,
            context=kwargs.get("case_id", case.id_),
        )
        activity = add_participant_to_case_activity(
            participant=wire_p,
            target=kwargs.get("case_id", case.id_),
            actor=kwargs.get("actor", case_actor_id),
            id_=add_activity_id,
        )
        dl.create(activity)
        return add_activity_id, _outbound_blob(activity)

    trigger_activity = MagicMock()
    trigger_activity.announce_vulnerability_case.return_value = (
        f"{case.id_}/announce/1"
    )
    trigger_activity.add_participant_to_case.side_effect = (
        _store_add_participant
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


class TestInviteActorUseCases:
    """Tests for invite_actor_to_case, accept_invite_actor_to_case,
    and reject_invite_actor_to_case."""

    @pytest.mark.spec("CLP-10-017")
    def test_invite_actor_to_case_archives_invite(self, make_payload):
        """The invitee's use case stores the Invite only through intake.

        Intake is the use case's only store of a received activity
        (CLP-10-019): the Invite is archived as a ``ReceivedActivityRecord``
        and the use case writes nothing under the sender's id (CLP-10-017).

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
            as_Actor(id_=invitee_id),
            target="https://example.org/cases/case1",
            actor="https://example.org/users/owner",
            id_="https://example.org/cases/case1/invitations/1",
        )

        event = make_payload(invite)

        result = InviteActorToCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.APPLIED
        record = dl.read(ReceivedActivityRecord.build_id(invite.id_))
        assert isinstance(record, ReceivedActivityRecord)
        assert record.activity.id_ == invite.id_
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
            as_Actor(id_=invitee_id),
            target=case_id,
            actor=sender_id,
            id_=f"{case_id}/invitations/narrative-1",
        )
        event = make_payload(invite)

        with caplog.at_level(logging.INFO):
            InviteActorToCaseReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            ).execute()

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
            as_Actor(id_=invitee_id),
            target="https://example.org/cases/case1",
            actor="https://example.org/users/owner",
            id_="https://example.org/cases/case1/invitations/narrative-2",
        )
        event = make_payload(invite)

        with caplog.at_level(logging.DEBUG):
            InviteActorToCaseReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            ).execute()

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
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.models.pending_case_inbox import (
            VultronPendingCaseInbox,
        )

        case_id = "https://example.org/cases/case-trust-1"
        invitee_id = "https://example.org/actors/invitee"
        case_manager_id = "https://example.org/actors/case-actor"

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=invitee_id,
        )
        invite = rm_invite_to_case_activity(
            as_Actor(id_=invitee_id),
            target=case_id,
            actor=case_manager_id,
            id_=f"{case_id}/invitations/trust-anchor-1",
        )
        event = make_payload(invite)
        InviteActorToCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        pending_id = VultronPendingCaseInbox.build_id(case_id)
        pending = dl.read(pending_id)
        assert isinstance(pending, VultronPendingCaseInbox), (
            "VultronPendingCaseInbox trust anchor must be written on the invitee path"
        )
        assert pending.case_actor_id == case_manager_id, (
            "Trust anchor case_actor_id must equal the invite sender (the CASE_MANAGER)"
        )

    @pytest.mark.spec("PCR-03-004")
    def test_invite_trust_anchor_is_first_invite_wins(self, make_payload):
        """A second invite naming a different CaseActor is refused; anchor unchanged.

        AC-3 (PCR-03-004 path b): the existing anchor is never overwritten.
        The second Invite disposition is REFUSED, naming both CaseActor ids.
        """
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.models.pending_case_inbox import (
            VultronPendingCaseInbox,
        )

        case_id = "https://example.org/cases/case-trust-2"
        invitee_id = "https://example.org/actors/invitee"
        first_sender = "https://example.org/actors/case-actor-a"
        second_sender = "https://example.org/actors/case-actor-b"

        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=invitee_id)

        invite1 = rm_invite_to_case_activity(
            as_Actor(id_=invitee_id),
            target=case_id,
            actor=first_sender,
            id_=f"{case_id}/invitations/a",
        )
        invite2 = rm_invite_to_case_activity(
            as_Actor(id_=invitee_id),
            target=case_id,
            actor=second_sender,
            id_=f"{case_id}/invitations/b",
        )

        first_result = InviteActorToCaseReceivedUseCase(
            dl,
            make_payload(invite1),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()
        second_result = InviteActorToCaseReceivedUseCase(
            dl,
            make_payload(invite2),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert first_result.disposition is HandlerDisposition.APPLIED, (
            "First Invite must be APPLIED"
        )
        # AC-3: conflicting second Invite is refused, not silently ignored.
        assert second_result.disposition is HandlerDisposition.REFUSED, (
            "Second Invite naming a different CaseActor MUST be REFUSED (PCR-03-004 path b)"
        )

        pending = dl.read(VultronPendingCaseInbox.build_id(case_id))
        assert isinstance(pending, VultronPendingCaseInbox)
        assert pending.case_actor_id == first_sender, (
            "First-invite-wins: trust anchor MUST NOT be overwritten by a second invite"
        )

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
            as_Actor(id_=invitee_id),
            target=case_id,
            actor="https://example.org/users/owner",
            id_=f"{case_id}/invitations/2",
        )
        event = make_payload(invite)

        first = InviteActorToCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()
        anchor = dl.read(VultronPendingCaseInbox.build_id(case_id))
        second = InviteActorToCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert first.disposition is HandlerDisposition.APPLIED
        assert second.disposition is HandlerDisposition.SKIPPED
        assert dl.read(VultronPendingCaseInbox.build_id(case_id)) == anchor

    @pytest.mark.spec("PCR-03-004")
    def test_invite_misaddressed_to_different_actor_is_refused(
        self, make_payload
    ):
        """An Invite whose object is not the receiving actor is REFUSED; no anchor.

        AC-1 (PCR-03-004 path b): the trust anchor node refuses to record a
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
            as_Actor(id_=named_invitee_id),  # object ≠ receiving actor
            target=case_id,
            actor=case_manager_id,
            id_=f"{case_id}/invitations/misaddressed-1",
        )
        result = InviteActorToCaseReceivedUseCase(
            dl,
            make_payload(invite),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

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
            as_Actor(id_="https://example.org/users/coordinator"),
            target="https://example.org/cases/case1",
            actor="https://example.org/users/owner",
            id_="https://example.org/cases/case1/invitations/missing",
        )
        field = "target" if missing == "target" else "object_"
        event = make_payload(invite).model_copy(update={field: None})

        result = InviteActorToCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

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
            as_Actor(id_=owner_id),
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

        InviteActorToCaseReceivedUseCase(
            dl,
            make_payload(invite),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

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
        case = as_VulnerabilityCase(
            id_=case_id, name="TEST-REDELIVER", attributed_to=case_actor_id
        )
        manager = as_CaseParticipant(
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
            as_Actor(id_="https://example.org/users/coordinator"),
            target=case_id,
            actor=case_actor_id,
            id_=f"{case_id}/invitations/1",
        )
        event = make_payload(invite).model_copy(
            update={"receiving_actor_id": case_actor_id}
        )

        first = InviteActorToCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()
        second = InviteActorToCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

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

        case_id = "https://example.org/cases/case-reject-ri1"
        case_actor_id = f"{case_id}/actor"
        # The ledger commit is role-gated to the CASE_MANAGER, which here is
        # the case actor — so the tree runs in the case actor's store.
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=case_actor_id)
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
            target=case_id,
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

        assert event.target_id is None, (
            "Precondition: Reject(Invite) has no top-level target"
        )
        assert event.case_id == case_id, (
            "Precondition: case_id resolves via inner_target_id"
        )

        RejectInviteActorToCaseReceivedUseCase(
            dl,
            event.model_copy(update={"receiving_actor_id": case_actor_id}),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        entries = [
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, WireCaseLedgerEntry) and e.case_id == case_id
        ]
        assert len(entries) >= 1, (
            "Expected at least one CaseLedgerEntry after reject-invite"
        )
        assert any("reject" in e.event_type for e in entries), (
            f"Expected a reject-invite ledger entry; got: {[e.event_type for e in entries]}"
        )

    def test_accept_invite_actor_to_case_adds_participant(
        self, monkeypatch, make_payload
    ):
        """AcceptInviteActorToCaseReceivedUseCase creates a as_CaseParticipant and adds them to the case."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        invitee_id = "https://example.org/users/coordinator"
        invitee = as_Organization(id_=invitee_id)
        case = VulnerabilityCase(
            id_="https://example.org/cases/caseIA1",
            name="TEST-ACCEPT-INVITE",
            attributed_to="https://example.org/users/owner",
        )
        seed_store_owner_as_case_manager(dl, case)
        invite = rm_invite_to_case_activity(
            invitee,
            target=case.id_,
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
            dl,
            event,
            sync_port=MagicMock(),
            wire_render_port=As2WireRenderAdapter(),
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
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.states.em import EM
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization
        from vultron.wire.as2.vocab.objects.embargo_event import (
            as_EmbargoEvent,
        )

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        invitee_id = "https://example.org/users/coordinator"
        invitee = as_Organization(id_=invitee_id)
        case = VulnerabilityCase(
            id_="https://example.org/cases/caseIA2",
            name="TEST-ACCEPT-INVITE-EMBARGO",
            attributed_to="https://example.org/users/owner",
        )
        embargo = as_EmbargoEvent(
            id_="https://example.org/cases/caseIA2/embargo_events/e1",
            content="Active embargo",
            context=case.id_,
            end_time=days_from_now_utc(45),
        )
        case.active_embargo = embargo.id_
        case.append_case_status(em_state=EM.ACTIVE)
        seed_store_owner_as_case_manager(dl, case)
        invite = rm_invite_to_case_activity(
            invitee,
            target=case.id_,
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
            dl,
            event,
            sync_port=MagicMock(),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        case = dl.read(case.id_)
        assert case is not None
        case = cast(VulnerabilityCase, case)
        participant_id = case.actor_participant_index.get(invitee_id)
        assert participant_id is not None
        participant_obj = dl.get(id_=participant_id)
        assert participant_obj is not None
        participant_obj = cast(Any, participant_obj)
        assert participant_obj.consent_for(embargo.id_) == "ACCEPTED"

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
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        invitee_id = "https://example.org/users/coordinator_rm1"
        invitee = as_Organization(id_=invitee_id)
        owner_id = "https://example.org/users/owner"
        case = VulnerabilityCase(
            id_="https://example.org/cases/caseRM001",
            name="TEST-RM-LIFECYCLE",
            attributed_to=owner_id,
        )
        seed_store_owner_as_case_manager(dl, case)
        invite = rm_invite_to_case_activity(
            invitee,
            target=case.id_,
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
            dl,
            event,
            sync_port=MagicMock(),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

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

    def test_accept_invite_no_identity_spoofing(self, make_payload):
        """PCR-07-008: AcceptInviteActorToCaseReceivedUseCase MUST NOT emit
        RmEngageCaseActivity (Join) with actor=invitee_id from the Case Actor
        context.  The BT records RM.RECEIVED for the invitee without spoofing
        the invitee's identity (CM-11-001, PCR-08-010).
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
        invitee = as_Organization(id_=invitee_id)
        owner_id = "https://example.org/users/owner"
        case_manager_participant_id = (
            "https://example.org/cases/caseRM002/participants/case-manager"
        )
        # The receiving store's owner is the CASE_MANAGER: the role holder,
        # the receiving actor and the store owner must be one actor
        # (BT-05-006, BT-17-006).
        store_owner_id = "https://test.example/api/v2/actors/test-actor"
        case_manager_participant = CaseParticipant(
            id_=case_manager_participant_id,
            attributed_to=store_owner_id,
            context="https://example.org/cases/caseRM002",
            name="CaseManager",
            case_roles=[CVDRole.CASE_MANAGER],
        )
        case = VulnerabilityCase(
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
            target=case.id_,
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
            dl,
            event,
            sync_port=MagicMock(),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        # PCR-07-008: no RmEngageCaseActivity (Join) with actor=invitee_id
        # should be queued — the BT records RM.RECEIVED for the invitee
        # without spoofing the invitee's identity.
        outbox_items = dl.clone_for_actor(invitee_id).outbox_list()
        for item_id in outbox_items:
            candidate = cast(Any, dl.read(item_id))
            if candidate is not None and str(candidate.type_) == "Join":
                raise AssertionError(
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
        as_CaseLedgerEntry with event_type 'accept_invite_actor_to_case'
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
        invitee = as_Organization(id_=invitee_id)
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/caseIA3",
            name="TEST-ACCEPT-INVITE-EVENT",
            attributed_to=case_actor_id,
        )
        invite = rm_invite_to_case_activity(
            invitee,
            target=case.id_,
            actor="https://example.org/users/owner",
            id_="https://example.org/cases/caseIA3/invitations/1",
        )
        dl.create(invitee)
        dl.create(case)
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.base.objects.actors import as_Service
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

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
            dl,
            event,
            sync_port=MagicMock(),
            wire_render_port=As2WireRenderAdapter(),
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
        from vultron.core.models.replication_state import (
            VultronReplicationState,
        )

        lj = _seed_late_joiner_case()
        dl, case, invitee_id = lj["dl"], lj["case"], lj["invitee_id"]
        invite, first, second = lj["invite"], lj["first"], lj["second"]
        trigger_activity = lj["trigger_activity"]
        sync_port = MagicMock()

        accept = rm_accept_invite_to_case_activity(invite, actor=invitee_id)
        event = make_payload(accept)
        AcceptInviteActorToCaseReceivedUseCase(
            dl,
            event,
            sync_port=sync_port,
            trigger_activity=trigger_activity,
            wire_render_port=As2WireRenderAdapter(),
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
        # Backfill: runs BEFORE the add-participant commit (CM-17-004 steps 5
        #   and 6 precede any further fan-out to the invitee), so its target is
        #   the receipt entry (2) and it sends entries 0, 1, 2 in log order.
        # Entry 3 (add_case_participant): committed after the invitee is
        #   persisted AND after the backfill — its fan-out INCLUDES the invitee,
        #   who receives it as the next entry in chain order, not out of order
        #   ahead of genesis (#2898).
        # So invitee receives: [0, 1, 2 (backfill), 3 (fan-out)].
        assert announced_log_indices == [0, 1, 2, 3]
        assert announced_entries[0].entry_hash == first.entry_hash
        assert announced_entries[1].entry_hash == second.entry_hash

        state_id = VultronReplicationState(
            case_id=case.id_, peer_id=invitee_id
        ).id_
        state = cast(Any, dl.read(state_id))
        assert state is not None
        # The backfill target is the ledger tail when the backfill ran: the
        # accept_invite receipt (2).  add_case_participant (3) is committed
        # afterwards and reaches the invitee by fan-out, not by backfill.
        assert state.join_backfill_target_index == 2
        assert state.join_backfill_last_sent_index == 2
        assert state.join_backfill_complete is True

    @pytest.mark.spec("CM-17-009")
    def test_accept_invite_seeds_the_case_before_any_ledger_entry_reaches_the_invitee(
        self, make_payload
    ):
        """CM-17-004 (5) then (6): Announce(VulnerabilityCase) precedes every
        Announce(CaseLedgerEntry) addressed to the invitee.

        A late joiner that receives a ledger entry before its case seed enters
        the SYNC-15 pre-genesis path — Reject, then a from-genesis replay that
        interleaves with the join backfill (fcvcv V2/C2, #2898).  The two
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

        accept = rm_accept_invite_to_case_activity(invite, actor=invitee_id)
        event = make_payload(accept)
        AcceptInviteActorToCaseReceivedUseCase(
            dl,
            event,
            sync_port=sync_port,
            trigger_activity=trigger_activity,
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

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

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            # The canonical ledger belongs to the case actor, so the backfill
            # runs in the case actor's store.
            actor_id="https://example.org/actors/case-actor-lj2",
        )
        invitee_id = "https://example.org/users/late-joiner-retry"
        case_actor_id = "https://example.org/actors/case-actor-lj2"
        invitee = as_Organization(id_=invitee_id)
        case_actor = as_Service(id_=case_actor_id, context="unused")
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/caseLJ2",
            name="TEST-LATE-JOIN-RESUME",
            attributed_to=case_actor_id,
        )
        object.__setattr__(case_actor, "context", case.id_)
        invite = rm_invite_to_case_activity(
            invitee,
            target=case.id_,
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
            from vultron.core.models.case_participant import CaseParticipant

            participant = CaseParticipant(
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
            _add_participant_result(case, case_actor_id, invitee_id)
        )
        sync_port = MagicMock()

        accept = rm_accept_invite_to_case_activity(invite, actor=invitee_id)
        event = make_payload(accept)
        AcceptInviteActorToCaseReceivedUseCase(
            dl,
            event,
            sync_port=sync_port,
            trigger_activity=trigger_activity,
            wire_render_port=As2WireRenderAdapter(),
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
        from vultron.core.models.case_participant import CaseParticipant
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
            actor_id="https://example.org/actors/case-actor-lj3",
        )
        invitee_id = "https://example.org/users/late-joiner-nomarker"
        case_actor_id = "https://example.org/actors/case-actor-lj3"
        invitee = as_Organization(id_=invitee_id)
        case_actor = as_Service(id_=case_actor_id, context="unused")
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/caseLJ3",
            name="TEST-LATE-JOIN-NO-MARKER",
            attributed_to=case_actor_id,
        )
        object.__setattr__(case_actor, "context", case.id_)
        participant = CaseParticipant(
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
        object.__setattr__(
            case,
            "case_participants",
            [
                participant.id_,
                case_manager_participant.id_,
            ],
        )
        object.__setattr__(
            case,
            "actor_participant_index",
            {
                invitee_id: participant.id_,
                case_actor_id: case_manager_participant.id_,
            },
        )
        invite = rm_invite_to_case_activity(
            invitee,
            target=case.id_,
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
            _add_participant_result(case, case_actor_id, invitee_id)
        )
        sync_port = MagicMock()

        accept = rm_accept_invite_to_case_activity(invite, actor=invitee_id)
        event = make_payload(accept)
        AcceptInviteActorToCaseReceivedUseCase(
            dl,
            event,
            sync_port=sync_port,
            trigger_activity=trigger_activity,
            wire_render_port=As2WireRenderAdapter(),
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

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            # The canonical ledger belongs to the case actor, so the backfill
            # runs in the case actor's store.
            actor_id="https://example.org/actors/case-actor-lj4",
        )
        invitee_id = "https://example.org/users/late-joiner-noannounce"
        case_actor_id = "https://example.org/actors/case-actor-lj4"
        invitee = as_Organization(id_=invitee_id)
        case_actor = as_Service(id_=case_actor_id, context="unused")
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/caseLJ4",
            name="TEST-LATE-JOIN-NO-ANNOUNCE",
            attributed_to=case_actor_id,
        )
        object.__setattr__(case_actor, "context", case.id_)
        invite = rm_invite_to_case_activity(
            invitee,
            target=case.id_,
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
            wire_render_port=As2WireRenderAdapter(),
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
    """AC-4: CreateInviteeParticipantNode reads roles from Invite."""

    def test_roles_from_invite_set_on_participant(self, make_payload):
        """AC-4: Accept(Invite) causes new participant to inherit roles from Invite."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        invitee_id = "https://example.org/users/vendor2"
        invitee = as_Organization(id_=invitee_id)
        case = VulnerabilityCase(
            id_="https://example.org/cases/ac4-test",
            name="AC-4 roles test",
            attributed_to="https://example.org/users/owner",
        )
        seed_store_owner_as_case_manager(dl, case)
        invite = rm_invite_to_case_activity(
            invitee,
            target=case.id_,
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
            dl,
            event,
            sync_port=MagicMock(),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        reloaded_case = cast(Any, dl.read(case.id_))
        participant_id = reloaded_case.actor_participant_index.get(invitee_id)
        assert participant_id is not None, (
            "invitee must be registered as participant"
        )
        participant = cast(Any, dl.get(id_=participant_id))
        assert participant is not None
        assert CVDRole.VENDOR in participant.case_roles, (
            "AC-4: participant case_roles must include VENDOR from Invite"
        )

    def test_no_roles_invite_gives_empty_case_roles(self, make_payload):
        """AC-4 negative: Invite without roles gives participant case_roles=[]."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        invitee_id = "https://example.org/users/vendor3"
        invitee = as_Organization(id_=invitee_id)
        case = VulnerabilityCase(
            id_="https://example.org/cases/ac4-neg",
            name="AC-4 negative",
            attributed_to="https://example.org/users/owner",
        )
        seed_store_owner_as_case_manager(dl, case)
        invite = rm_invite_to_case_activity(
            invitee,
            target=case.id_,
            actor="https://example.org/users/owner",
            id_="https://example.org/cases/ac4-neg/invitations/1",
        )
        dl.create(invitee)
        dl.create(case)
        dl.create(invite)

        accept = rm_accept_invite_to_case_activity(invite, actor=invitee_id)
        event = make_payload(accept)
        AcceptInviteActorToCaseReceivedUseCase(
            dl,
            event,
            sync_port=MagicMock(),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        reloaded_case = cast(Any, dl.read(case.id_))
        participant_id = reloaded_case.actor_participant_index.get(invitee_id)
        participant = cast(Any, dl.get(id_=participant_id))
        assert participant is not None
        assert participant.case_roles == [], (
            "Participant with no-roles invite must have empty case_roles"
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

    def _invite(self, case_id: str):
        return rm_invite_to_case_activity(
            as_Actor(id_=self._INVITEE),
            target=case_id,
            actor=self._OWNER,
            id_=f"{case_id}/invitations/1",
        )

    def _seed_case(self, dl, case_id: str, manager_id: str | None = None):
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        case = as_VulnerabilityCase(
            id_=case_id, name="DISPOSITION", attributed_to=self._OWNER
        )
        if manager_id is not None:
            manager = as_CaseParticipant(
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
        event = make_payload(self._invite("https://example.org/cases/d-inv1"))

        first = InviteActorToCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()
        second = InviteActorToCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert first.disposition == HandlerDisposition.APPLIED
        assert second.disposition == HandlerDisposition.SKIPPED

    @pytest.mark.spec("HP-01-003")
    def test_reject_invite_without_case_is_refused(self):
        dl = self._dl()
        event = MagicMock(case_id=None, receiving_actor_id=None)

        result = RejectInviteActorToCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition == HandlerDisposition.REFUSED

    @pytest.mark.spec("HP-01-003")
    @pytest.mark.spec("HP-01-005")
    def test_reject_invite_at_non_case_manager_is_refused(self, make_payload):
        """Only the CASE_MANAGER records a declined invite; others refuse (#3752)."""
        case_id = "https://example.org/cases/d-rj1"
        dl = self._dl()
        self._seed_case(dl, case_id, manager_id=self._OWNER)
        event = make_payload(
            rm_reject_invite_to_case_activity(
                self._invite(case_id), actor=self._INVITEE
            )
        )

        result = RejectInviteActorToCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

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
        event = make_payload(
            rm_accept_invite_to_case_activity(invite, actor=self._INVITEE)
        )

        result = AcceptInviteActorToCaseReceivedUseCase(
            dl,
            event,
            sync_port=MagicMock(),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason is not None and "CASE_MANAGER" in result.reason
        reloaded = cast(Any, dl.read(case.id_))
        assert self._INVITEE not in reloaded.actor_participant_index
        assert dl.outbox_list() == []

    @pytest.mark.spec("HP-01-003")
    def test_reject_invite_for_unknown_case_is_refused(self, make_payload):
        dl = self._dl()
        event = make_payload(
            rm_reject_invite_to_case_activity(
                self._invite("https://example.org/cases/d-rj-missing"),
                actor=self._INVITEE,
            )
        )

        result = RejectInviteActorToCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason is not None and "unknown case" in result.reason

    @pytest.mark.spec("HP-01-003")
    def test_reject_invite_at_case_manager_is_applied(self, make_payload):
        case_id = "https://example.org/cases/d-rj2"
        dl = self._dl(actor_id=self._OWNER)
        self._seed_case(dl, case_id, manager_id=self._OWNER)
        event = make_payload(
            rm_reject_invite_to_case_activity(
                self._invite(case_id), actor=self._INVITEE
            ),
            receiving_actor_id=self._OWNER,
        )

        result = RejectInviteActorToCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition == HandlerDisposition.APPLIED

    @pytest.mark.spec("HP-01-003")
    def test_accept_invite_without_invitee_is_refused(self):
        dl = self._dl()
        event = MagicMock(
            case_id="https://example.org/cases/d-ac0",
            invitee_id=None,
            receiving_actor_id=None,
        )

        result = AcceptInviteActorToCaseReceivedUseCase(
            dl,
            event,
            sync_port=MagicMock(),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert result.disposition == HandlerDisposition.REFUSED

    @pytest.mark.spec("HP-01-003")
    def test_accept_invite_for_unknown_case_is_refused(self, make_payload):
        dl = self._dl()
        event = make_payload(
            rm_accept_invite_to_case_activity(
                self._invite("https://example.org/cases/d-ac-missing"),
                actor=self._INVITEE,
            )
        )

        result = AcceptInviteActorToCaseReceivedUseCase(
            dl,
            event,
            sync_port=MagicMock(),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason is not None and "unknown case" in result.reason

    @pytest.mark.spec("HP-01-003")
    def test_accept_invite_redelivery_is_skipped(self, make_payload):
        """A second Accept once the invitee has fully joined is a duplicate."""
        case_id = "https://example.org/cases/d-ac1"
        dl = self._dl()
        # The store owner admits the invitee: it must hold CASE_MANAGER.
        self._seed_case(dl, case_id, manager_id=dl.actor_id)
        invite = self._invite(case_id)
        dl.create(invite)
        event = make_payload(
            rm_accept_invite_to_case_activity(invite, actor=self._INVITEE)
        )

        first = AcceptInviteActorToCaseReceivedUseCase(
            dl,
            event,
            sync_port=MagicMock(),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()
        second = AcceptInviteActorToCaseReceivedUseCase(
            dl,
            event,
            sync_port=MagicMock(),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert first.disposition == HandlerDisposition.APPLIED
        assert second.disposition == HandlerDisposition.SKIPPED
