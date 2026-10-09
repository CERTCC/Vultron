#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
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

"""Receiver-side role semantics tests for Leave(VulnerabilityCase).

Covers CM-23-002 (owner Leave) and CM-23-003 (non-owner Leave) across:

1. The Case Actor's direct receive path (``create_close_case_received_tree``).
2. The fan-out replica path (``ApplyCloseCaseFromLedgerNode`` via announce tree).
"""

from __future__ import annotations

import logging
from typing import cast
from unittest.mock import MagicMock

import py_trees
import pytest

from test.support.embargo_register import activate, propose, terminate
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sync.announce_tree import (
    create_announce_log_entry_tree,
)
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_actor import CaseActor
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.events.case import CloseCaseReceivedEvent
from vultron.core.models.events.sync import AnnounceLogEntryReceivedEvent
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.rsvp_deadline import INVITE_EXPIRED_EVENT_TYPE
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.core.use_cases.received.case.lifecycle import (
    CloseCaseReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import announce_log_entry_activity
from vultron.wire.as2.vocab.objects.case_ledger_entry import (
    as_CaseLedgerEntry as WireCaseLedgerEntry,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CASE_ACTOR_ID = "https://example.org/actors/case-actor-roles"
OWNER_ID = "https://example.org/actors/owner-roles"
VENDOR_ID = "https://example.org/actors/vendor-roles"
CASE_ID = "https://example.org/cases/c-role-test"

_ZERO_HASH = "0" * 64


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_dl(actor_id: str = CASE_ACTOR_ID) -> SqliteDataLayer:
    """The store of *actor_id*, defaulting to the CaseActor.

    ``_make_full_dl`` below is documented as "DataLayer as seen by the CaseActor",
    so the CaseActor is the right default: it holds the canonical ledger these
    tests commit to.
    """
    return SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)


def _make_full_dl(
    owner_id: str = OWNER_ID,
    extra_participant_id: str | None = VENDOR_ID,
    store_owner_id: str = CASE_ACTOR_ID,
) -> SqliteDataLayer:
    """*store_owner_id*'s replica of the case, with all participants set up.

    Participants:
    - CaseActor: CASE_MANAGER role
    - owner_id: CASE_OWNER role
    - extra_participant_id (optional): VENDOR role

    *store_owner_id* defaults to the CaseActor, which holds the canonical ledger
    the Leave-side tests commit to.  The fan-out tests override it: they simulate
    a *replica* receiving the CaseActor's broadcast, so the tree executes as that
    replica's actor and therefore reads and writes that actor's store (ADR-0073).
    Leaving it as the CaseActor's left those trees running against an empty store,
    where nothing advances — which reads as a passing test when the assertion is
    that a participant was *not* advanced.
    """
    dl = _make_dl(store_owner_id)

    ca_svc = CaseActor(id_=CASE_ACTOR_ID, context=CASE_ID)
    dl.save(ca_svc)

    case = as_VulnerabilityCase(
        id_=CASE_ID,
        name="Role Semantics Test",
        attributed_to=CASE_ACTOR_ID,
    )

    cm_participant = as_CaseParticipant(
        attributed_to=CASE_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    dl.create(cm_participant)
    case.case_participants.append(cm_participant.id_)
    case.actor_participant_index[CASE_ACTOR_ID] = cm_participant.id_

    owner_participant = as_CaseParticipant(
        attributed_to=owner_id,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_OWNER, CVDRole.FINDER],
    )
    dl.create(owner_participant)
    case.case_participants.append(owner_participant.id_)
    case.actor_participant_index[owner_id] = owner_participant.id_

    if extra_participant_id is not None:
        vendor_participant = as_CaseParticipant(
            attributed_to=extra_participant_id,
            context=CASE_ID,
            case_roles=[CVDRole.VENDOR],
        )
        dl.create(vendor_participant)
        case.case_participants.append(vendor_participant.id_)
        case.actor_participant_index[extra_participant_id] = (
            vendor_participant.id_
        )

    dl.save(case)
    return dl


def _make_close_case_event(
    sender_actor_id: str,
    receiving_actor_id: str = CASE_ACTOR_ID,
    activity_id: str = "https://example.org/activities/leave-role-test",
) -> CloseCaseReceivedEvent:
    case_obj = as_VulnerabilityCase(id_=CASE_ID)
    activity = VultronActivity(
        id_=activity_id,
        type_="Leave",
        actor=sender_actor_id,
        object_=case_obj,
    )
    return CloseCaseReceivedEvent(
        semantic_type=MessageSemantics.CLOSE_CASE,
        activity_id=activity.id_,
        actor_id=sender_actor_id,
        object_=case_obj,
        activity=activity,
        receiving_actor_id=receiving_actor_id,
    )


def _seed_rm(dl: SqliteDataLayer, actor_id: str, rm_state: RM) -> None:
    """Append a ParticipantStatus at *rm_state* to *actor_id*'s participant.

    Uses the core append API so the seeded rung round-trips through
    ``_participant_rm_states`` exactly as a protocol-written status would. Lets a
    test start a participant at a specific RM rung (e.g. RECEIVED/VALID) before a
    Leave, which is what CM-23-012 is about: the leaver advances regardless of
    rung, and a bystander retains whatever rung it was seeded at.
    """
    case = dl.read(CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    participant_id = case.actor_participant_index[actor_id]
    participant = dl.read(participant_id)
    assert isinstance(participant, CaseParticipant)
    participant.add_participant_status(
        ParticipantStatus(
            attributed_to=actor_id,
            context=CASE_ID,
            rm=RmDimension(state=rm_state),
        )
    )
    dl.save(participant)


def _latest_rm(dl: SqliteDataLayer, actor_id: str) -> RM | None:
    """Return the actor's most-recent RM state, or None if it has no status."""
    states = _participant_rm_states(dl, actor_id)
    return states[-1] if states else None


def _participant_rm_states(dl: SqliteDataLayer, actor_id: str) -> list[RM]:
    """Return list of RM states from participant_statuses for actor_id in CASE_ID."""
    case = dl.read(CASE_ID)
    if not isinstance(case, VulnerabilityCase):
        return []
    participant_id = case.actor_participant_index.get(actor_id)
    if participant_id is None:
        return []
    participant = dl.read(participant_id)
    if not isinstance(participant, CaseParticipant):
        return []
    return [
        ps.rm.state
        for ps in participant.participant_statuses
        if hasattr(ps, "rm") and ps.rm is not None
    ]


# ---------------------------------------------------------------------------
# Case Actor receive path (create_close_case_received_tree)
# ---------------------------------------------------------------------------


def _case_ledger(dl: SqliteDataLayer) -> list[CaseLedgerEntry]:
    """The case's ledger entries in ``log_index`` order."""
    return sorted(
        (
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry) and e.case_id == CASE_ID
        ),
        key=lambda e: e.log_index,
    )


class TestOwnerLeaveReceivePath:
    """CM-23-002: Owner Leave advances leaving participant + CaseActor to RM.CLOSED."""

    @pytest.mark.spec("CM-23-002")
    def test_owner_leave_advances_owner_to_rm_closed(self):
        """Owner Leave: the leaving owner actor is advanced to RM.CLOSED."""
        dl = _make_full_dl()
        result = CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=OWNER_ID),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()
        assert result.disposition == HandlerDisposition.APPLIED

        rm_states = _participant_rm_states(dl, OWNER_ID)
        assert RM.CLOSED in rm_states, (
            f"Owner participant must be at RM.CLOSED after owner Leave;"
            f" rm_states={rm_states}"
        )

    @pytest.mark.spec("CM-23-002")
    def test_owner_leave_advances_case_actor_to_rm_closed(self):
        """Owner Leave: the CaseActor is also advanced to RM.CLOSED (CM-23-002 step 2)."""
        dl = _make_full_dl()
        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=OWNER_ID),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        rm_states = _participant_rm_states(dl, CASE_ACTOR_ID)
        assert RM.CLOSED in rm_states, (
            f"CaseActor must be at RM.CLOSED after owner Leave (CM-23-002);"
            f" rm_states={rm_states}"
        )

    @pytest.mark.spec("CM-23-002")
    def test_owner_leave_does_not_close_non_departed_participants(self):
        """Owner Leave: the remaining non-leaving vendor participant is NOT changed.

        The Case Actor only closes the owner + itself in the receive path.
        Non-leaving participants learn via Announce(CaseLedgerEntry) fan-out.
        """
        dl = _make_full_dl()
        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=OWNER_ID),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        rm_states = _participant_rm_states(dl, VENDOR_ID)
        assert RM.CLOSED not in rm_states, (
            f"Vendor participant must NOT be at RM.CLOSED after owner Leave"
            f" — fan-out handles that; rm_states={rm_states}"
        )

    @pytest.mark.spec("CM-23-002")
    def test_owner_leave_creates_case_fully_closed_ledger_entry(self):
        """Owner Leave: a case_fully_closed CaseLedgerEntry is written (CM-23-002 step 3)."""
        from vultron.core.models.case_ledger_entry import CaseLedgerEntry

        dl = _make_full_dl()
        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=OWNER_ID),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        entries = [
            obj
            for obj in dl.list_objects("CaseLedgerEntry")
            if isinstance(obj, CaseLedgerEntry)
            and getattr(obj, "case_id", None) == CASE_ID
        ]
        event_types = [getattr(e, "event_type", None) for e in entries]
        assert "case_fully_closed" in event_types, (
            f"Owner Leave must create a case_fully_closed ledger entry (CM-23-002 step 3);"
            f" found event_types={event_types}"
        )

    @pytest.mark.spec("CM-23-005")
    def test_owner_leave_records_case_actor_rm_closed_as_ledger_entry(self):
        """Owner Leave: the CaseActor's own RM.CLOSED becomes a ledger entry.

        Regression test for ISSUE-2505. ``AdvanceCaseActorToRMClosedNode`` wrote
        the transition to the CaseActor's own store only. Nothing recorded it,
        and nothing could derive it: ``close_case`` names the *departing* actor
        and the CaseActor never sends itself a Leave, while
        ``case_fully_closed`` is attributed to the owner and has no effect node.
        So every replica read the CASE_MANAGER as permanently ``RM.ACCEPTED``,
        which is what CM-23-005 forbids by requiring each CASE_MANAGER RM
        transition to be recorded as a ``CaseLedgerEntry``.

        Asserts the entry exists *and* is about the CaseActor — an
        ``add_participant_status_to_participant`` entry alone proves nothing,
        since the bootstrap path emits several for other participants.
        """
        from vultron.core.models.case_ledger_entry import CaseLedgerEntry

        dl = _make_full_dl()
        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=OWNER_ID),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        status_entries = [
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry)
            and getattr(e, "case_id", None) == CASE_ID
            and getattr(e, "event_type", None)
            == "add_participant_status_to_participant"
        ]
        case_actor_closed = [
            e
            for e in status_entries
            if (e.payload_snapshot or {}).get("object", {}).get("attributedTo")
            == CASE_ACTOR_ID
            and str(
                (e.payload_snapshot or {}).get("object", {}).get("rmState", "")
            ).endswith("CLOSED")
        ]
        assert case_actor_closed, (
            "Owner Leave must record the CASE_MANAGER's own RM.CLOSED as an"
            " add_participant_status_to_participant CaseLedgerEntry"
            " (CM-23-005); found"
            f" {[(e.payload_snapshot or {}).get('object', {}).get('attributedTo') for e in status_entries]}"
        )

    @pytest.mark.spec("CM-23-002")
    def test_case_actor_rm_closed_entry_precedes_case_fully_closed(self):
        """The CaseActor's RM.CLOSED entry is committed before case_fully_closed.

        CM-23-002 orders the sequence: advancing the CASE_MANAGER is step 2 and
        ``case_fully_closed`` is the final entry, which is precisely why this is
        committed synchronously in the receive tree rather than emitted as a
        self-addressed ``Add(ParticipantStatus)`` through the CLP-10-001
        loopback — that is an outbox background task and could not honour the
        ordering.
        """

        dl = _make_full_dl()
        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=OWNER_ID),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        by_index = _case_ledger(dl)
        case_actor_idx = [
            i
            for i, e in enumerate(by_index)
            if getattr(e, "event_type", None)
            == "add_participant_status_to_participant"
            and (e.payload_snapshot or {})
            .get("object", {})
            .get("attributedTo")
            == CASE_ACTOR_ID
            and str(
                (e.payload_snapshot or {}).get("object", {}).get("rmState", "")
            ).endswith("CLOSED")
        ]
        fully_closed_idx = [
            i
            for i, e in enumerate(by_index)
            if getattr(e, "event_type", None) == "case_fully_closed"
        ]
        assert case_actor_idx, "no CASE_MANAGER RM.CLOSED entry was committed"
        assert fully_closed_idx, "no case_fully_closed entry was committed"
        assert max(case_actor_idx) < min(fully_closed_idx), (
            "the CASE_MANAGER's RM.CLOSED entry must precede"
            " case_fully_closed (CM-23-002 steps 2 then 3); got"
            f" case-actor at {case_actor_idx}, case_fully_closed at"
            f" {fully_closed_idx}"
        )

    @pytest.mark.spec("CM-23-002")
    def test_owner_leave_case_fully_closed_fanout_includes_all_non_case_actor(
        self,
    ):
        """Owner Leave: case_fully_closed fan-out reaches all participants except the sending CaseActor.

        ``FanOutLogEntryNode`` excludes only ``self.actor_id`` (the CaseActor); it does NOT
        filter by RM state.  The ``case_fully_closed`` entry is the replica-completeness
        termination signal and must reach all replicas regardless of their RM state so every
        participant learns the case is fully closed.
        """
        from vultron.core.models.case_ledger_entry import CaseLedgerEntry

        dl = _make_full_dl()
        sync_mock = MagicMock(spec=SyncActivityPort)
        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=OWNER_ID),
            sync_port=sync_mock,
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert sync_mock.send_announce_log_entry.called, (
            "Fan-out must call sync_port.send_announce_log_entry after owner Leave (CM-23-002)"
        )

        # Identify calls for the case_fully_closed entry specifically
        case_fully_closed_recipients: list[str] = []
        for c in sync_mock.send_announce_log_entry.call_args_list:
            entry = c.kwargs.get("entry") or (c.args[0] if c.args else None)
            if (
                isinstance(entry, CaseLedgerEntry)
                and getattr(entry, "event_type", None) == "case_fully_closed"
            ):
                recipients = c.kwargs.get("to") or (
                    c.args[2] if len(c.args) > 2 else []
                )
                case_fully_closed_recipients.extend(recipients)

        assert VENDOR_ID in case_fully_closed_recipients, (
            f"case_fully_closed fan-out must include VENDOR_ID;"
            f" actual recipients: {case_fully_closed_recipients}"
        )
        assert OWNER_ID in case_fully_closed_recipients, (
            f"case_fully_closed fan-out must include OWNER_ID (replica-completeness signal);"
            f" actual recipients: {case_fully_closed_recipients}"
        )
        assert CASE_ACTOR_ID not in case_fully_closed_recipients, (
            f"case_fully_closed fan-out must NOT include CASE_ACTOR_ID (excluded as self.actor_id);"
            f" actual recipients: {case_fully_closed_recipients}"
        )


class TestNonOwnerLeaveReceivePath:
    """CM-23-003: Non-owner Leave advances only the leaving participant."""

    @pytest.mark.spec("CM-23-003")
    def test_non_owner_leave_advances_only_leaving_participant(self):
        """Non-owner Leave: the leaving vendor actor is advanced to RM.CLOSED."""
        dl = _make_full_dl()
        result = CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=VENDOR_ID),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()
        assert result.disposition == HandlerDisposition.APPLIED

        rm_states = _participant_rm_states(dl, VENDOR_ID)
        assert RM.CLOSED in rm_states, (
            f"Non-owner leaving participant must be at RM.CLOSED (CM-23-003);"
            f" rm_states={rm_states}"
        )

    @pytest.mark.spec("CM-23-003")
    def test_non_owner_leave_does_not_close_owner(self):
        """Non-owner Leave: the case owner remains open (CM-23-003)."""
        dl = _make_full_dl()
        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=VENDOR_ID),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        rm_states = _participant_rm_states(dl, OWNER_ID)
        assert RM.CLOSED not in rm_states, (
            f"Owner participant must NOT be at RM.CLOSED after non-owner Leave;"
            f" rm_states={rm_states}"
        )

    @pytest.mark.spec("CM-23-003")
    def test_non_owner_leave_does_not_close_case_actor(self):
        """Non-owner Leave: the CaseActor remains open (CM-23-003)."""
        dl = _make_full_dl()
        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=VENDOR_ID),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        rm_states = _participant_rm_states(dl, CASE_ACTOR_ID)
        assert RM.CLOSED not in rm_states, (
            f"CaseActor must NOT be at RM.CLOSED after non-owner Leave;"
            f" rm_states={rm_states}"
        )


def _close(
    dl: SqliteDataLayer, sender_actor_id: str, activity_id: str
) -> HandlerResult:
    return CloseCaseReceivedUseCase(
        dl=dl,
        request=_make_close_case_event(
            sender_actor_id=sender_actor_id, activity_id=activity_id
        ),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
        trigger_activity=TriggerActivityAdapter(dl),
    ).execute()


class TestPostCloseBoundary:
    """CM-23-013/014: nothing a participant does lands after case_fully_closed."""

    @pytest.mark.xfail(
        strict=True,
        reason="CM-23-013: a bystander Leave after owner close is still"
        " committed as close_case. Tracked by #4162 (record nothing, reply"
        " optional) and #4065 (refusal and demo closure order).",
    )
    @pytest.mark.spec("CM-23-013")
    def test_bystander_leave_after_owner_close_is_refused(self):
        """A bystander Leave after owner close commits nothing and closes no one.

        Regression for CONCERN-3400: every demo closed the owner first, so a
        bystander's ``close_case`` landed after ``case_fully_closed``, an
        external append past the ADR-0085 write boundary.  The CASE_MANAGER
        MAY decline with one ``as:Reject`` or MAY drop the Leave with no
        reply (CM-23-013); either is accepted, but nothing is recorded.
        """
        dl = _make_full_dl()
        _close(dl, OWNER_ID, "https://example.org/activities/leave-owner")
        ledger = _case_ledger(dl)
        assert ledger and ledger[-1].event_type == "case_fully_closed", (
            "precondition: the owner close must have committed"
            f" case_fully_closed; tail={[e.event_type for e in ledger]}"
        )
        entries_at_close = len(ledger)
        rm_before = _participant_rm_states(dl, VENDOR_ID)
        outbox_before = set(dl.outbox_list())

        result = _close(
            dl, VENDOR_ID, "https://example.org/activities/leave-vendor"
        )

        assert len(_case_ledger(dl)) == entries_at_close, (
            "a post-close bystander Leave must commit no ledger entry"
            f" (CM-23-013); tail={[e.event_type for e in _case_ledger(dl)]}"
        )
        assert _participant_rm_states(dl, VENDOR_ID) == rm_before
        assert result.disposition != HandlerDisposition.APPLIED
        queued = [i for i in dl.outbox_list() if i not in outbox_before]
        assert len(queued) <= 1, (
            "a post-close bystander Leave gets at most one reply, the"
            f" optional as:Reject (CM-23-013); queued={queued}"
        )
        if not queued:
            return
        reject = dl.read(queued[0])
        assert getattr(reject, "type_", None) == "Reject", (
            "a reply to a post-close Leave must be an as:Reject (MSM-05-001);"
            f" got type_={getattr(reject, 'type_', None)}"
        )
        assert VENDOR_ID in (getattr(reject, "to", None) or [])
        inner = getattr(reject, "object_", None)
        assert getattr(inner, "type_", None) == "Leave", (
            "the as:Reject must decline the Leave activity itself"
        )

    @pytest.mark.xfail(
        strict=True,
        reason="CM-23-014: owner close does not yet expire pending Invites"
        " before case_fully_closed. Tracked by #4066.",
    )
    @pytest.mark.spec("CM-23-014")
    def test_owner_close_expires_pending_invite_before_boundary(self):
        """An unanswered Invite is expired at close, not left waiting on its deadline."""
        from datetime import UTC, datetime, timedelta

        from vultron.core.states.participant_embargo_consent import (
            EmbargoConsentState,
            PEC_Trigger,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import (
            as_EmbargoEvent,
        )

        dl = _make_full_dl()
        case = dl.read_case(CASE_ID)
        assert isinstance(case, VulnerabilityCase)
        embargo = as_EmbargoEvent(
            id_=f"{CASE_ID}/embargo_events/proposed",
            context=CASE_ID,
            end_time=datetime.now(tz=UTC) + timedelta(days=45),
        )
        dl.create(embargo)
        propose(case, embargo.id_)
        dl.save(case)
        vendor = dl.read(case.actor_participant_index[VENDOR_ID])
        assert isinstance(vendor, CaseParticipant)
        vendor.apply_pec_transition(embargo.id_, PEC_Trigger.INVITE)
        vendor.invite_rsvp_deadline = datetime.now(tz=UTC) + timedelta(
            days=365
        )
        dl.save(vendor)

        _close(dl, OWNER_ID, "https://example.org/activities/leave-owner")

        vendor = dl.read(case.actor_participant_index[VENDOR_ID])
        assert isinstance(vendor, CaseParticipant)
        assert (
            vendor.consent_for(embargo.id_) == EmbargoConsentState.EXPIRED
        ), "owner close must expire a pending Invite immediately (CM-23-014)"
        ledger = _case_ledger(dl)
        types = [e.event_type for e in ledger]
        rm_closed_ids = {e.id_ for e in _case_actor_rm_closed_entries(dl)}
        rm_closed_idx = [
            i for i, e in enumerate(ledger) if e.id_ in rm_closed_ids
        ]
        lapse_idx = [
            i for i, t in enumerate(types) if t == INVITE_EXPIRED_EVENT_TYPE
        ]
        assert types[-1] == "case_fully_closed", types
        assert rm_closed_idx and lapse_idx, (
            "owner close must commit the CASE_MANAGER's RM.CLOSED entry and"
            f" an expired-invitation entry (CM-23-014); got {types}"
        )
        assert max(rm_closed_idx) < min(lapse_idx), (
            "the expired-invitation entry must follow the CASE_MANAGER's"
            f" RM.CLOSED entry (CM-23-014); got {types}"
        )


# ---------------------------------------------------------------------------
# Fan-out path (ApplyCloseCaseFromLedgerNode via announce tree)
# ---------------------------------------------------------------------------


def _make_close_case_ledger_entry(
    dl: SqliteDataLayer,
    departing_actor_id: str,
) -> CaseLedgerEntry:
    """Build a close_case CaseLedgerEntry with the correct genesis hash.

    Uses the case's ``genesis_hash`` as ``prev_log_hash`` so that
    ``ReconstructChainTailNode`` accepts it as the first entry in a fresh chain.
    """
    case = dl.read(CASE_ID)
    genesis_hash = getattr(case, "genesis_hash", _ZERO_HASH) or _ZERO_HASH
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=0,
            object_id="https://example.org/activities/leave-for-fanout",
            event_type="close_case",
            payload_snapshot={"actor": departing_actor_id},
            prev_log_hash=genesis_hash,
        )
    )


def _make_announce_event(
    entry: CaseLedgerEntry,
    sender_actor_id: str,
) -> AnnounceLogEntryReceivedEvent:
    from typing import cast

    wire_entry = WireCaseLedgerEntry.model_validate(
        entry.model_dump(mode="json")
    )
    activity = announce_log_entry_activity(
        entry=wire_entry, actor=sender_actor_id
    )
    return cast(AnnounceLogEntryReceivedEvent, extract_event(activity))


class TestCloseCaseFanOut:
    """Fan-out: ApplyCloseCaseFromLedgerNode advances departing participant on replicas."""

    @pytest.mark.spec("CM-23-003")
    def test_fan_out_advances_departing_participant_to_rm_closed(self):
        """Announce(close_case entry) advances the departing participant on a non-CaseActor replica.

        This simulates the VENDOR actor's local DataLayer receiving the
        ``Announce(CaseLedgerEntry)`` that the Case Actor broadcast after
        processing the owner's Leave.  The vendor replica must advance the
        OWNER participant to RM.CLOSED (CM-23-003).

        The entry is NOT pre-stored: ``CheckLedgerEntryAlreadyStoredNode`` in
        the announce tree short-circuits with SUCCESS (skips effects) when the
        entry is already present.  The fan-out scenario is: entry arrives fresh.
        """
        dl = _make_full_dl(store_owner_id=VENDOR_ID)
        entry = _make_close_case_ledger_entry(dl, departing_actor_id=OWNER_ID)

        event = _make_announce_event(
            entry=entry, sender_actor_id=CASE_ACTOR_ID
        )

        tree = create_announce_log_entry_tree()
        BTBridge(
            datalayer=dl, wire_render_port=As2WireRenderAdapter()
        ).execute_with_setup(
            tree=tree,
            actor_id=VENDOR_ID,
            activity=event,
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        rm_states = _participant_rm_states(dl, OWNER_ID)
        assert RM.CLOSED in rm_states, (
            f"Announce(close_case) fan-out must advance departing participant"
            f" to RM.CLOSED on vendor replica (CM-23-003);"
            f" rm_states={rm_states}"
        )

    def test_fan_out_does_not_advance_non_departing_participant(self):
        """Announce(close_case entry for OWNER) must not advance VENDOR to RM.CLOSED."""
        dl = _make_full_dl(store_owner_id=VENDOR_ID)
        entry = _make_close_case_ledger_entry(dl, departing_actor_id=OWNER_ID)

        event = _make_announce_event(
            entry=entry, sender_actor_id=CASE_ACTOR_ID
        )

        tree = create_announce_log_entry_tree()
        BTBridge(
            datalayer=dl, wire_render_port=As2WireRenderAdapter()
        ).execute_with_setup(
            tree=tree,
            actor_id=VENDOR_ID,
            activity=event,
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        rm_states = _participant_rm_states(dl, VENDOR_ID)
        assert RM.CLOSED not in rm_states, (
            f"Announce(close_case for OWNER) must NOT advance VENDOR to RM.CLOSED;"
            f" rm_states={rm_states}"
        )


# ---------------------------------------------------------------------------
# CM-23-012: closure is a per-leaver RM write, never a bystander cascade
# ---------------------------------------------------------------------------


class TestClosureRMBoundary:
    """CM-23-012: a Leave advances only the leaver's RM, through ordinary RM
    transitions (RMB-14-005); owner-close leaves every bystander at its prior
    RM rung."""

    @pytest.mark.spec("CM-23-012")
    @pytest.mark.spec("RMB-14-004")
    @pytest.mark.spec("RMB-14-005")
    @pytest.mark.parametrize(
        "leaver_id", [OWNER_ID, VENDOR_ID], ids=["owner", "non-owner"]
    )
    @pytest.mark.parametrize(
        "source",
        [RM.RECEIVED, RM.INVALID, RM.ACCEPTED, RM.DEFERRED],
        ids=lambda s: s.name,
    )
    def test_leave_from_closable_rung_records_one_transition(
        self, leaver_id: str, source: RM
    ):
        """A Leave from R, I, A or D records the single transition to CLOSED.

        ``R → C`` is an ordinary RM transition (RMB-14-004), as are ``I → C``,
        ``A → C`` and ``D → C``, so the leaver's history gains exactly one
        CLOSED record and no forced write (RMB-14-005).
        """
        dl = _make_full_dl()
        _seed_rm(dl, leaver_id, source)
        before = _participant_rm_states(dl, leaver_id)

        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=leaver_id),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        after = _participant_rm_states(dl, leaver_id)
        assert after == [*before, RM.CLOSED], (
            f"Leave from RM.{source.name} must record {source.name} -> CLOSED"
            f" and nothing else (RMB-14-005); rm_states={after}"
        )

    @pytest.mark.spec("CM-23-012")
    @pytest.mark.spec("RMB-14-005")
    @pytest.mark.spec("VP-02-004")
    @pytest.mark.parametrize(
        "leaver_id", [OWNER_ID, VENDOR_ID], ids=["owner", "non-owner"]
    )
    def test_leave_from_valid_is_recorded_through_deferred(
        self, leaver_id: str
    ):
        """A Leave from VALID records VALID → DEFERRED, then DEFERRED → CLOSED.

        *Valid* has no close edge (VP-02-004), so the closure walks the RM
        table through *Deferred* instead of forcing past it (RMB-14-005).
        """
        dl = _make_full_dl()
        _seed_rm(dl, leaver_id, RM.VALID)
        before = _participant_rm_states(dl, leaver_id)

        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=leaver_id),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        after = _participant_rm_states(dl, leaver_id)
        assert after == [*before, RM.DEFERRED, RM.CLOSED], (
            "Leave from RM.VALID must be recorded as V -> D -> C"
            f" (RMB-14-005); rm_states={after}"
        )

    @pytest.mark.spec("CM-23-012")
    @pytest.mark.spec("RMB-14-005")
    def test_leave_from_start_receives_then_closes(self):
        """A leaver still at RM.START records START → RECEIVED → CLOSED.

        ``S → C`` is not in the RM table; the leaver has received the case it
        is leaving, so the closure records the receipt first (RMB-14-005).
        """
        dl = _make_full_dl()
        assert _latest_rm(dl, VENDOR_ID) == RM.START
        before = _participant_rm_states(dl, VENDOR_ID)

        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=VENDOR_ID),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        after = _participant_rm_states(dl, VENDOR_ID)
        assert after == [*before, RM.RECEIVED, RM.CLOSED], after

    @pytest.mark.spec("CM-23-012")
    @pytest.mark.spec("RMB-14-005")
    @pytest.mark.parametrize(
        ("source", "path"),
        [
            (RM.RECEIVED, [RM.CLOSED]),
            (RM.ACCEPTED, [RM.CLOSED]),
            (RM.VALID, [RM.DEFERRED, RM.CLOSED]),
        ],
        ids=lambda v: v.name if isinstance(v, RM) else None,
    )
    def test_fanout_records_the_same_closure_path(
        self, source: RM, path: list[RM]
    ):
        """A replica applying a close_case entry records the same RM path.

        ``ApplyCloseCaseFromLedgerNode`` walks the RM table exactly as the
        CASE_MANAGER does, so a departing participant at VALID passes through
        DEFERRED on every replica too (RMB-14-005).
        """
        dl = _make_full_dl(store_owner_id=VENDOR_ID)
        _seed_rm(dl, OWNER_ID, source)
        before = _participant_rm_states(dl, OWNER_ID)
        entry = _make_close_case_ledger_entry(dl, departing_actor_id=OWNER_ID)
        event = _make_announce_event(
            entry=entry, sender_actor_id=CASE_ACTOR_ID
        )

        BTBridge(
            datalayer=dl, wire_render_port=As2WireRenderAdapter()
        ).execute_with_setup(
            tree=create_announce_log_entry_tree(),
            actor_id=VENDOR_ID,
            activity=event,
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        after = _participant_rm_states(dl, OWNER_ID)
        assert after == [*before, *path], after

    @pytest.mark.spec("CM-23-005")
    @pytest.mark.spec("RMB-14-005")
    @pytest.mark.parametrize(
        ("source", "path"),
        [
            (RM.ACCEPTED, [RM.CLOSED]),
            (RM.VALID, [RM.DEFERRED, RM.CLOSED]),
        ],
        ids=lambda v: v.name if isinstance(v, RM) else None,
    )
    def test_case_manager_closure_records_every_rung(
        self, source: RM, path: list[RM]
    ):
        """Owner Leave records each CASE_MANAGER closure rung on the ledger.

        CM-23-005 requires every CASE_MANAGER RM transition to be a
        ``CaseLedgerEntry``.  A CASE_MANAGER at VALID closes ``V → D → C``
        (RMB-14-005), so both the DEFERRED and the CLOSED status are
        committed, in that order, and both before ``case_fully_closed``.
        """
        dl = _make_full_dl()
        _seed_rm(dl, CASE_ACTOR_ID, source)
        before = _case_actor_rm_entry_states(dl)

        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=OWNER_ID),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        after = _case_actor_rm_entry_states(dl)
        assert after[: len(before)] == before
        assert after[len(before) :] == path, (
            f"CASE_MANAGER closure from RM.{source.name} must record"
            f" {[rm.name for rm in path]} (CM-23-005); got {after}"
        )

    @pytest.mark.spec("CM-23-012")
    def test_owner_leave_leaves_bystander_at_prior_rung(self):
        """Owner Leave must leave a bystander at exactly its prior RM rung.

        Stronger than 'not CLOSED': a vendor seeded at RM.VALID must remain at
        RM.VALID after owner-close — closure does not touch its RM at all.
        """
        dl = _make_full_dl()
        _seed_rm(dl, VENDOR_ID, RM.VALID)

        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=OWNER_ID),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert _latest_rm(dl, VENDOR_ID) == RM.VALID, (
            "Bystander seeded at RM.VALID must retain RM.VALID after owner-close"
            f" (CM-23-012); rm_states={_participant_rm_states(dl, VENDOR_ID)}"
        )

    @pytest.mark.spec("CM-23-012")
    def test_fanout_leaves_bystander_at_prior_rung(self):
        """Fan-out of a close_case entry for OWNER must leave the replica's own
        VENDOR participant at its prior rung (RM.ACCEPTED), not advance it."""
        dl = _make_full_dl(store_owner_id=VENDOR_ID)
        _seed_rm(dl, VENDOR_ID, RM.ACCEPTED)
        entry = _make_close_case_ledger_entry(dl, departing_actor_id=OWNER_ID)

        event = _make_announce_event(
            entry=entry, sender_actor_id=CASE_ACTOR_ID
        )

        tree = create_announce_log_entry_tree()
        BTBridge(
            datalayer=dl, wire_render_port=As2WireRenderAdapter()
        ).execute_with_setup(
            tree=tree,
            actor_id=VENDOR_ID,
            activity=event,
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        assert _latest_rm(dl, VENDOR_ID) == RM.ACCEPTED, (
            "Fan-out of OWNER's close must leave VENDOR at RM.ACCEPTED"
            f" (CM-23-012); rm_states={_participant_rm_states(dl, VENDOR_ID)}"
        )


# ---------------------------------------------------------------------------
# CM-23-011: owner close is declined via as:Reject while an embargo is live
# ---------------------------------------------------------------------------


def _seed_active_embargo(
    dl: SqliteDataLayer, em_state: EM = EM.ACTIVE
) -> None:
    """Give CASE_ID a live embargo whose register derives EM *em_state*.

    ``EM.ACTIVE`` holds one embargo in force; ``EM.REVISE`` adds an open
    revision proposal on top of it.
    """
    case = dl.read_case(CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    # Hold the record too: a case never names an embargo its own store
    # cannot read (EMB-18-003).
    embargo = EmbargoEvent(
        id_=f"{CASE_ID}/embargo_events/e1",
        context=CASE_ID,
        end_time=days_from_now_utc(45),
    )
    dl.save(embargo)
    activate(case, embargo.id_)
    if em_state == EM.REVISE:
        revision = EmbargoEvent(
            id_=f"{CASE_ID}/embargo_events/e2",
            context=CASE_ID,
            end_time=days_from_now_utc(60),
        )
        dl.save(revision)
        propose(case, revision.id_)
    assert case.em_state == em_state
    dl.save(case)


def _terminate_embargo(dl: SqliteDataLayer) -> None:
    """Terminate the active embargo, so EM derives EXITED (normal teardown)."""
    case = dl.read_case(CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    terminate(case)
    dl.save(case)


def _case_fully_closed_present(dl: SqliteDataLayer) -> bool:
    from vultron.core.models.case_ledger_entry import CaseLedgerEntry

    return any(
        isinstance(obj, CaseLedgerEntry)
        and getattr(obj, "case_id", None) == CASE_ID
        and getattr(obj, "event_type", None) == "case_fully_closed"
        for obj in dl.list_objects("CaseLedgerEntry")
    )


class TestOwnerLeaveDuringActiveEmbargo:
    """CM-23-011: owner Leave while an embargo is live is declined, not closed."""

    @pytest.mark.spec("CM-23-011")
    @pytest.mark.parametrize("em_state", [EM.ACTIVE, EM.REVISE])
    def test_owner_leave_during_embargo_runs_no_closure(self, em_state):
        """Owner Leave under an active/revise embargo advances no one to
        RM.CLOSED and writes no case_fully_closed entry (AC-1)."""
        dl = _make_full_dl()
        _seed_active_embargo(dl, em_state=em_state)

        result = CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=OWNER_ID),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        # HP-01-003: answering with a Reject is a refusal, not "processed".
        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason is not None and "embargo" in result.reason

        assert RM.CLOSED not in _participant_rm_states(dl, OWNER_ID), (
            "Owner must NOT reach RM.CLOSED while an embargo is live"
            f" (CM-23-011); rm_states={_participant_rm_states(dl, OWNER_ID)}"
        )
        assert RM.CLOSED not in _participant_rm_states(dl, CASE_ACTOR_ID), (
            "CaseActor must NOT reach RM.CLOSED while an embargo is live"
            " (CM-23-011)"
        )
        assert not _case_fully_closed_present(dl), (
            "No case_fully_closed entry may be written while embargoed"
            " (CM-23-011)"
        )

    @pytest.mark.spec("CM-23-011")
    def test_owner_leave_during_embargo_emits_reject_to_owner(self):
        """The decline is surfaced as an as:Reject of the Leave, addressed back
        to the owner (AC-2, MSM-05-001)."""
        dl = _make_full_dl()
        _seed_active_embargo(dl, em_state=EM.ACTIVE)

        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=OWNER_ID),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        outbox = dl.outbox_list()
        assert len(outbox) == 1, (
            f"Exactly one activity (the as:Reject) must be queued; outbox={outbox}"
        )
        reject = dl.read(outbox[0])
        assert reject is not None, "as:Reject must be readable from the outbox"
        assert getattr(reject, "type_", None) == "Reject", (
            f"Declined close must be an as:Reject (MSM-05-001);"
            f" got type_={getattr(reject, 'type_', None)}"
        )
        assert OWNER_ID in (getattr(reject, "to", None) or []), (
            f"as:Reject must be addressed to the owner; to={getattr(reject, 'to', None)}"
        )
        inner = getattr(reject, "object_", None)
        assert getattr(inner, "type_", None) == "Leave", (
            "as:Reject must decline the Leave activity itself"
        )

    @pytest.mark.spec("CM-23-011")
    def test_close_proceeds_after_embargo_terminated(self):
        """After the embargo is terminated, re-issuing the owner Leave runs the
        full CM-23-002 closure sequence (AC-3)."""
        dl = _make_full_dl()
        _seed_active_embargo(dl, em_state=EM.ACTIVE)

        # First close: declined while embargoed.
        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=OWNER_ID),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()
        assert RM.CLOSED not in _participant_rm_states(dl, OWNER_ID)
        assert not _case_fully_closed_present(dl)

        # Terminate the embargo, then re-issue the same close.
        _terminate_embargo(dl)
        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=OWNER_ID),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        assert RM.CLOSED in _participant_rm_states(dl, OWNER_ID), (
            "After embargo termination the owner close must proceed to"
            f" RM.CLOSED (CM-23-011/CM-23-002);"
            f" rm_states={_participant_rm_states(dl, OWNER_ID)}"
        )
        assert RM.CLOSED in _participant_rm_states(dl, CASE_ACTOR_ID), (
            "After embargo termination the CaseActor must reach RM.CLOSED"
        )
        assert _case_fully_closed_present(dl), (
            "After embargo termination a case_fully_closed entry must be written"
        )

    @pytest.mark.spec("CM-23-011")
    def test_owner_close_not_closed_when_reject_emit_cannot_run(self):
        """If the as:Reject emit cannot run (no trigger_activity port), the
        embargoed owner close must still NOT close the case.

        Guards the structural invariant: the decline decision gates the close
        arm, so an emit failure can never fall through into closing an
        embargoed case (CM-23-011).
        """
        dl = _make_full_dl()
        _seed_active_embargo(dl, em_state=EM.ACTIVE)

        # No trigger_activity port → EmitRejectCloseCaseNode fails.
        result = CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=OWNER_ID),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            trigger_activity=None,
        ).execute()
        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason is not None and "embargo" in result.reason

        assert RM.CLOSED not in _participant_rm_states(dl, OWNER_ID), (
            "Owner must NOT reach RM.CLOSED when the decline emit could not run"
            f" (CM-23-011); rm_states={_participant_rm_states(dl, OWNER_ID)}"
        )
        assert RM.CLOSED not in _participant_rm_states(dl, CASE_ACTOR_ID), (
            "CaseActor must NOT reach RM.CLOSED when the decline emit fails"
        )
        assert not _case_fully_closed_present(dl), (
            "No case_fully_closed entry may be written when the decline emit fails"
        )


class TestDeclineArmIsCaseManagerGated:
    """CM-23-011 decline emits only at the CASE_MANAGER (BT-17-001, #3825).

    The decline arm's ``EmitRejectCloseCaseNode`` used to run at every replica
    that received a copy of the owner's Leave.  A participant cc'd on that
    Leave while an embargo was live therefore emitted a ``Reject(Leave)`` to
    the owner as itself — the same ungated-emit defect as #3752 / #3751.  The
    emit is now gated on the receiver holding ``CVDRole.CASE_MANAGER``.
    """

    @pytest.mark.spec("BT-17-001")
    @pytest.mark.spec("CM-23-011")
    @pytest.mark.spec("HP-01-005")
    def test_non_manager_replica_emits_no_reject_during_embargo(self):
        """A non-manager replica declines nothing: no as:Reject is queued.

        Runs the receive tree in the VENDOR's own store (``store_owner_id``)
        and as the VENDOR actor (``receiving_actor_id``), so the executing
        actor does not hold ``CVDRole.CASE_MANAGER``.  A copy of the Case
        Owner's Leave arrives while an embargo is live.  Before #3825 this
        emitted a ``Reject(Leave)``; it must now emit nothing.
        """
        dl = _make_full_dl(store_owner_id=VENDOR_ID)
        _seed_active_embargo(dl, em_state=EM.ACTIVE)

        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(
                sender_actor_id=OWNER_ID, receiving_actor_id=VENDOR_ID
            ),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        assert dl.outbox_list() == [], (
            "a non-CASE_MANAGER replica must emit no as:Reject when it"
            " receives a copy of the owner's Leave during a live embargo"
            f" (BT-17-001, CM-23-011, #3825); outbox={dl.outbox_list()}"
        )

    @pytest.mark.spec("BT-17-001")
    @pytest.mark.spec("CM-23-011")
    def test_non_manager_replica_closes_nothing_during_embargo(self):
        """The replica also writes no closure state and no case_fully_closed.

        The whole close/decline decision is CASE_MANAGER business; a replica
        archives the Leave and takes any resulting closure from the ledger
        fan-out (RSH-08-003, CLP-10-001).
        """
        dl = _make_full_dl(store_owner_id=VENDOR_ID)
        _seed_active_embargo(dl, em_state=EM.ACTIVE)

        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(
                sender_actor_id=OWNER_ID, receiving_actor_id=VENDOR_ID
            ),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        assert RM.CLOSED not in _participant_rm_states(dl, OWNER_ID)
        assert not _case_fully_closed_present(dl)


def _case_actor_rm_entry_states(dl: SqliteDataLayer) -> list[RM]:
    """Return the CaseActor's RM states as recorded on the ledger, in order."""
    entries = sorted(
        (
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry)
            and e.case_id == CASE_ID
            and e.event_type == "add_participant_status_to_participant"
            and (e.payload_snapshot or {})
            .get("object", {})
            .get("attributedTo")
            == CASE_ACTOR_ID
        ),
        key=lambda e: e.log_index,
    )
    return [
        RM(e.payload_snapshot["object"]["rmState"])
        for e in entries
        if e.payload_snapshot["object"].get("rmState")
    ]


def _case_actor_rm_closed_entries(dl: SqliteDataLayer) -> list:
    """Return the ledger entries recording the CaseActor's own RM.CLOSED."""
    from vultron.core.models.case_ledger_entry import CaseLedgerEntry

    return [
        e
        for e in dl.list_objects("CaseLedgerEntry")
        if isinstance(e, CaseLedgerEntry)
        and getattr(e, "case_id", None) == CASE_ID
        and getattr(e, "event_type", None)
        == "add_participant_status_to_participant"
        and (e.payload_snapshot or {}).get("object", {}).get("attributedTo")
        == CASE_ACTOR_ID
        and str(
            (e.payload_snapshot or {}).get("object", {}).get("rmState", "")
        ).endswith("CLOSED")
    ]


@pytest.mark.spec("HP-01-003")
def test_close_without_case_id_is_refused():
    """A Leave with no case id is malformed, so REFUSED (#2255)."""
    result = CloseCaseReceivedUseCase(
        dl=_make_full_dl(),
        request=cast(CloseCaseReceivedEvent, MagicMock(case_id=None)),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()

    assert result.disposition == HandlerDisposition.REFUSED


class TestCaseActorRMClosedRecordingIsBestEffort:
    """Recording the CaseActor's own RM.CLOSED must never cost the case its closure.

    ``CommitCaseActorRMClosedEntryNode`` sits between CM-23-002 step 2 (advance
    the CASE_MANAGER) and step 3 (``case_fully_closed``) in a single Sequence.
    If it returned FAILURE, steps 3 and 4 would be skipped — and because the
    enclosing ``OwnerOrNonOwnerEffects`` Selector reads a failed owner arm as
    "the sender is not the Case Owner", the tree would then succeed down the
    non-owner path and report SUCCESS with an empty failure reason. The result
    is a permanently half-closed case with no diagnostic: no
    ``case_fully_closed``, no fan-out, nothing logged.

    So the node warns and returns SUCCESS on every path where it cannot produce
    the entry. These tests pin that: closure completes, the owner arm is the arm
    that ran, and the only thing lost is the one entry.
    """

    @pytest.fixture
    def rm_closed_node_without_port(self, monkeypatch):
        """Blind only the RM.CLOSED recording node to the render port.

        The rest of the tree keeps the port: the Leave's own guarded commit
        needs it and fails closed without it (ARCH-20-001).  This isolates the
        one entry the node skips when it cannot render its snapshot.
        """
        from vultron.core.behaviors.case.nodes.leave.record import (
            CommitCaseActorRMClosedEntryNode,
        )

        original = CommitCaseActorRMClosedEntryNode.initialise

        def _initialise_without_port(node) -> None:
            original(node)
            node.wire_render_port = None

        monkeypatch.setattr(
            CommitCaseActorRMClosedEntryNode,
            "initialise",
            _initialise_without_port,
        )

    @pytest.mark.spec("CM-23-002")
    def test_missing_port_still_commits_case_fully_closed(
        self, rm_closed_node_without_port
    ):
        """No WireRenderPort: the entry is skipped, the case still fully closes."""
        dl = _make_full_dl()
        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=OWNER_ID),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert _case_fully_closed_present(dl), (
            "case_fully_closed must still be committed when the CASE_MANAGER's"
            " own RM.CLOSED cannot be recorded — a missing WireRenderPort must"
            " not strand the case half-closed (CM-23-002 steps 3-4)"
        )

    @pytest.mark.spec("CM-23-002")
    def test_missing_port_still_takes_the_owner_arm(
        self, rm_closed_node_without_port
    ):
        """No WireRenderPort: the owner arm ran, not the non-owner fallback.

        The distinguishing effect is the CaseActor's own advance to RM.CLOSED
        (step 2), which only the owner arm performs. If a failed recording had
        bumped the tree onto ``NonOwnerLeaveFallbackSeq``, only the departing
        owner would have advanced.
        """
        dl = _make_full_dl()
        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=OWNER_ID),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert _latest_rm(dl, OWNER_ID) == RM.CLOSED, (
            "the departing owner must reach RM.CLOSED (CM-23-002 step 1)"
        )
        assert RM.CLOSED in _participant_rm_states(dl, CASE_ACTOR_ID), (
            "the CaseActor must still advance itself to RM.CLOSED (CM-23-002"
            " step 2) — a failed *recording* must not divert the tree onto the"
            " non-owner path"
        )

    @pytest.mark.spec("CM-23-005")
    def test_missing_port_skips_only_the_case_actor_entry(
        self, rm_closed_node_without_port
    ):
        """No WireRenderPort: the ledger entry is the only casualty.

        The honest cost of best-effort recording. This is ISSUE-2505 in
        miniature — replicas cannot see the CASE_MANAGER's closure on this run —
        and it is the trade accepted to keep the case's terminal anchor.
        """
        dl = _make_full_dl()
        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=OWNER_ID),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert not _case_actor_rm_closed_entries(dl), (
            "without a WireRenderPort no snapshot can be rendered, so no entry"
            " should be committed — an empty payload would be worse"
        )

    @pytest.mark.spec("CM-23-002")
    def test_failed_commit_still_commits_case_fully_closed(self, monkeypatch):
        """A failing commit tree does not take case closure down with it.

        This is the path reachable without any wiring regression:
        ``create_commit_log_entry_tree`` opens with ``CheckLedgerFreshnessNode``,
        which returns FAILURE on a gapped local prefix by design
        (SYNC-10-001/002). Stand-in for that here is a tree that always fails.
        """
        dl = _make_full_dl()
        monkeypatch.setattr(
            "vultron.core.behaviors.case.nodes.leave.record"
            ".create_commit_log_entry_tree",
            lambda *a, **kw: py_trees.behaviours.Failure(name="ForcedFailure"),
        )

        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=OWNER_ID),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert not _case_actor_rm_closed_entries(dl), (
            "sanity: the forced failure must actually have suppressed the entry"
        )
        assert _case_fully_closed_present(dl), (
            "case_fully_closed must still be committed when the CASE_MANAGER's"
            " RM.CLOSED entry cannot be committed — a gapped local ledger must"
            " not block case closure (SYNC-10-001/002)"
        )

    @pytest.mark.spec("CM-23-005")
    def test_failed_recording_is_logged_to_the_stdlib_logger(
        self, caplog, rm_closed_node_without_port
    ):
        """A skipped entry is announced where deployment logs can see it.

        Best-effort is only defensible if the miss is observable.
        ``py_trees.behaviour.Behaviour.logger`` writes to the console and never
        reaches the stdlib ``logging`` tree, so the node must also log through
        its module logger — otherwise this degrades into the silent drop that
        ISSUE-2505 already was.
        """
        dl = _make_full_dl()
        with caplog.at_level(
            logging.WARNING,
            logger="vultron.core.behaviors.case.nodes.leave.record",
        ):
            CloseCaseReceivedUseCase(
                dl=dl,
                request=_make_close_case_event(sender_actor_id=OWNER_ID),
                sync_port=SyncActivityAdapter(dl),
                wire_render_port=As2WireRenderAdapter(),
            ).execute()

        assert any(
            "WireRenderPort" in r.getMessage() for r in caplog.records
        ), (
            "the skipped entry must be logged via the stdlib logger; got"
            f" {[r.getMessage() for r in caplog.records]}"
        )


class TestCaseActorRMClosedRecordingIsRoleGated:
    """Only the CASE_MANAGER authors the canonical RM.CLOSED entry (CLP-09-001).

    The receive tree passes ``receiving_actor_id`` straight through as the
    node's ``case_actor_id``, so without a role check the node's authority would
    rest on addressing alone — ``SvcLeaveCaseUseCase`` happening to address the
    Leave only to ``case_manager_id``. ``DeclineForeignLedgerCommitNode`` inside
    the commit tree does not close that gap: it is a store-consistency guard,
    not an authority check (ARCH-24-005), and on a container co-hosting the
    CaseActor with another actor it resolves a store for the co-hosted actor and
    reports "not foreign".
    """

    @pytest.mark.spec("CLP-09-001")
    def test_non_case_manager_receiver_commits_no_canonical_entry(self):
        """A receiver without the CASE_MANAGER role authors nothing."""
        dl = _make_full_dl()
        case = dl.read(CASE_ID)
        assert isinstance(case, VulnerabilityCase)
        participant = dl.read(case.actor_participant_index[CASE_ACTOR_ID])
        assert isinstance(participant, CaseParticipant)
        participant.case_roles = [CVDRole.VENDOR]
        dl.save(participant)

        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=OWNER_ID),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert not _case_actor_rm_closed_entries(dl), (
            "a receiver that does not hold CVDRole.CASE_MANAGER must not mint a"
            " canonical add_participant_status_to_participant entry (CLP-09-001,"
            " BT-17-005/006)"
        )

    @pytest.mark.spec("CM-23-005")
    def test_case_manager_receiver_still_commits_the_entry(self):
        """Control: the gate does not block the CASE_MANAGER itself."""
        dl = _make_full_dl()
        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=OWNER_ID),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert _case_actor_rm_closed_entries(dl), (
            "the CASE_MANAGER must still record its own RM.CLOSED (CM-23-005)"
            " — the role gate must not suppress the entry it exists to protect"
        )


class TestCaseActorClosureStatusSelection:
    """Which statuses ``CommitCaseActorRMClosedEntryNode`` reads as a closure."""

    @staticmethod
    def _closure_rms(rms: list[RM]) -> list[RM]:
        from vultron.core.behaviors.case.nodes.leave.record import (
            CommitCaseActorRMClosedEntryNode,
        )
        from vultron.core.models.participant_status import (
            participant_status_rm_state,
        )

        participant = as_CaseParticipant(
            attributed_to=CASE_ACTOR_ID,
            context=CASE_ID,
            case_roles=[CVDRole.CASE_MANAGER],
            participant_statuses=[],
        )
        for rm_state in rms:
            participant.participant_statuses.append(
                ParticipantStatus(
                    attributed_to=CASE_ACTOR_ID,
                    context=CASE_ID,
                    rm=RmDimension(state=rm_state),
                )
            )
        node = CommitCaseActorRMClosedEntryNode(
            case_actor_id=CASE_ACTOR_ID, case_id=CASE_ID
        )
        return [
            participant_status_rm_state(status)
            for status in node._closure_statuses(participant)
        ]

    @pytest.mark.spec("CM-23-005")
    def test_bootstrap_status_is_not_a_closure_rung(self):
        """A bootstrap RECEIVED status is not read as the R of S → R → C.

        The first status is the bootstrap write (``owner.py`` may seed
        RECEIVED), so an R → C closure records only the CLOSED status.
        """
        assert self._closure_rms([RM.RECEIVED, RM.CLOSED]) == [RM.CLOSED]

    @pytest.mark.spec("CM-23-005")
    @pytest.mark.spec("RMB-14-005")
    @pytest.mark.parametrize(
        ("rms", "expected"),
        [
            ([RM.START, RM.RECEIVED, RM.CLOSED], [RM.RECEIVED, RM.CLOSED]),
            (
                [RM.RECEIVED, RM.VALID, RM.DEFERRED, RM.CLOSED],
                [RM.DEFERRED, RM.CLOSED],
            ),
            ([RM.RECEIVED, RM.VALID, RM.ACCEPTED, RM.CLOSED], [RM.CLOSED]),
            ([RM.CLOSED], [RM.CLOSED]),
            ([RM.RECEIVED, RM.VALID], []),
        ],
    )
    def test_closure_rungs_follow_the_closure_path(
        self, rms: list[RM], expected: list[RM]
    ):
        """The closure is the rungs after the bootstrap that match the path."""
        assert self._closure_rms(rms) == expected
