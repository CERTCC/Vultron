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

1. The Case Actor's direct receive path (``create_close_case_received_tree``),
   which commits ``close_case`` and then one status entry per RM step it
   writes for each closing actor (CM-23-001, CM-23-002, CM-23-005).
2. The replica path: the announce tree applies those status entries, and the
   ``close_case`` entry alone changes no RM state (CM-23-001, CM-23-016).
"""

from __future__ import annotations

import json
import logging
from typing import cast
from unittest.mock import MagicMock

import py_trees
import pytest

from test.core.use_cases.received._archived_redelivery import (
    archived_redelivery,
)
from test.support.embargo_register import (
    activate,
    propose,
    reject,
    terminate,
    write_consent_rows,
)
from test.support.ledger import fail_commits
from test.support.received import received_event, with_evidence
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.adapters.outbox_sealed_body import read_sealed_body
from vultron.config.actor import ActorConfig, PostCloseReply
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sync.announce_tree import (
    create_announce_log_entry_tree,
)
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.activity import VultronActivity
from vultron.core.models.actor import VultronService
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.embargo_consent_semantic_types import (
    UPDATE_EMBARGO_CONSENT_SEMANTIC_TYPE,
)
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.events.case import CloseCaseReceivedEvent
from vultron.core.models.events.sync import AnnounceLogEntryReceivedEvent
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.rsvp_deadline import INVITE_EXPIRED_SEMANTIC_TYPE
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import EmbargoRegisterStatus
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
    PEC_Trigger,
)
from vultron.core.states.rm import RM
from vultron.core.use_cases.received.case.lifecycle import (
    CloseCaseReceivedUseCase,
)
from vultron.core.use_cases.received.sync import (
    AnnounceLedgerEntryReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronBTInternalError
from vultron.wire.as2.factories import announce_log_entry_activity
from vultron.wire.as2.vocab.objects.case_ledger_entry import (
    as_CaseLedgerEntry as WireCaseLedgerEntry,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
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

    ca_svc = VultronService(id_=CASE_ACTOR_ID, context=CASE_ID)
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
        case_roles=[CVDRole.CASE_OWNER, CVDRole.REPORTER],
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
        to=[receiving_actor_id],
        object_=case_obj,
    )
    return with_evidence(
        CloseCaseReceivedEvent(
            semantic_type=MessageSemantics.CLOSE_CASE,
            activity_id=activity.id_,
            actor_id=sender_actor_id,
            object_=case_obj,
            activity=activity,
            receiving_actor_id=receiving_actor_id,
        )
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


def _participant_id_for(dl: SqliteDataLayer, actor_id: str) -> str:
    case = dl.read(CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    return case.actor_participant_index[actor_id]


def _announced(
    sync_mock: MagicMock,
) -> list[tuple[CaseLedgerEntry, list[str]]]:
    """``(entry, to)`` for each ``send_announce_log_entry`` call, in order."""
    return [
        (c.kwargs["entry"], list(c.kwargs["to"]))
        for c in sync_mock.send_announce_log_entry.call_args_list
    ]


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


def _case_file(dl: SqliteDataLayer, actor_id: str) -> tuple[object, ...]:
    """What a closure writes for *actor_id*: its record and every status.

    The participant record in full and the ids of the actor's
    ``ParticipantStatus`` records in the store, so a test can assert a failed
    closure left both as they were (CLP-07-013).
    """
    participant = dl.read(_participant_id_for(dl, actor_id))
    assert isinstance(participant, CaseParticipant)
    return (
        participant.model_dump(mode="json"),
        sorted(
            o.id_
            for o in dl.list_objects("ParticipantStatus")
            if isinstance(o, ParticipantStatus) and o.attributed_to == actor_id
        ),
    )


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
            trigger_activity=TriggerActivityAdapter(dl),
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
            trigger_activity=TriggerActivityAdapter(dl),
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
            trigger_activity=TriggerActivityAdapter(dl),
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
            trigger_activity=TriggerActivityAdapter(dl),
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
        semantic_types = [getattr(e, "semantic_type", None) for e in entries]
        assert "case_fully_closed" in semantic_types, (
            f"Owner Leave must create a case_fully_closed ledger entry (CM-23-002 step 3);"
            f" found semantic_types={semantic_types}"
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
            trigger_activity=TriggerActivityAdapter(dl),
            request=_make_close_case_event(sender_actor_id=OWNER_ID),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        status_entries = [
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry)
            and getattr(e, "case_id", None) == CASE_ID
            and getattr(e, "semantic_type", None)
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
        ``case_fully_closed`` is the write boundary that must follow it
        (CM-23-013), which is precisely why this is
        committed synchronously in the receive tree rather than emitted as a
        self-addressed ``Add(ParticipantStatus)`` through the CLP-10-001
        loopback — that is an outbox background task and could not honour the
        ordering.
        """

        dl = _make_full_dl()
        CloseCaseReceivedUseCase(
            dl=dl,
            trigger_activity=TriggerActivityAdapter(dl),
            request=_make_close_case_event(sender_actor_id=OWNER_ID),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        by_index = _case_ledger(dl)
        case_actor_idx = [
            i
            for i, e in enumerate(by_index)
            if getattr(e, "semantic_type", None)
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
            if getattr(e, "semantic_type", None) == "case_fully_closed"
        ]
        assert case_actor_idx, "no CASE_MANAGER RM.CLOSED entry was committed"
        assert fully_closed_idx, "no case_fully_closed entry was committed"
        assert max(case_actor_idx) < min(fully_closed_idx), (
            "the CASE_MANAGER's RM.CLOSED entry must precede"
            " case_fully_closed (CM-23-002 steps 2 then 3); got"
            f" case-actor at {case_actor_idx}, case_fully_closed at"
            f" {fully_closed_idx}"
        )

    @pytest.mark.spec("CM-23-002", "CM-23-004")
    def test_owner_leave_case_fully_closed_fanout_skips_closed_participants(
        self,
    ):
        """Owner Leave: case_fully_closed reaches only participants not CLOSED.

        The Case Owner is at ``RM.CLOSED`` once its own status entries are
        committed, so it is not sent ``case_fully_closed`` (CM-23-004).  The
        Vendor, still open, is; the sending CaseActor never is.
        """
        dl = _make_full_dl()
        sync_mock = MagicMock(spec=SyncActivityPort)
        CloseCaseReceivedUseCase(
            dl=dl,
            trigger_activity=TriggerActivityAdapter(dl),
            request=_make_close_case_event(sender_actor_id=OWNER_ID),
            sync_port=sync_mock,
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        recipients = [
            to
            for entry, to in _announced(sync_mock)
            if entry.semantic_type == "case_fully_closed"
        ]
        assert recipients == [[VENDOR_ID]], (
            "case_fully_closed must reach exactly the open Vendor"
            f" (CM-23-004); sends: {recipients}"
        )

    @pytest.mark.spec("CM-23-004", "CM-23-001")
    def test_closed_owner_receives_its_own_closure_and_nothing_after(self):
        """The owner gets close_case and its own steps, then nothing.

        Ledger order: close_case(owner) → owner steps → CASE_MANAGER steps →
        case_fully_closed (CM-23-002).  The owner's replica stops at its own
        steps.
        """
        dl = _make_full_dl()
        sync_mock = MagicMock(spec=SyncActivityPort)
        CloseCaseReceivedUseCase(
            dl=dl,
            trigger_activity=TriggerActivityAdapter(dl),
            request=_make_close_case_event(sender_actor_id=OWNER_ID),
            sync_port=sync_mock,
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        owner = dl.read(_participant_id_for(dl, OWNER_ID))
        assert isinstance(owner, CaseParticipant)
        owner_status_ids = {s.id_ for s in owner.participant_statuses}
        sent = _announced(sync_mock)
        to_owner = [entry for entry, to in sent if OWNER_ID in to]

        assert to_owner[0].semantic_type == "close_case"
        own_steps = to_owner[1:]
        assert own_steps, "the owner must receive its own closure steps"
        assert all(
            e.semantic_type == "add_participant_status_to_participant"
            and e.log_object_id in owner_status_ids
            for e in own_steps
        ), [(e.semantic_type, e.log_object_id) for e in own_steps]
        last_own = max(e.log_index for e in to_owner)
        later = [entry for entry, _ in sent if entry.log_index > last_own]
        assert {e.semantic_type for e in later} >= {
            "add_participant_status_to_participant",
            "case_fully_closed",
        }, "CASE_MANAGER steps and case_fully_closed follow the owner's"


class TestNonOwnerLeaveReceivePath:
    """CM-23-003: Non-owner Leave advances only the leaving participant."""

    @pytest.mark.spec("CM-23-003")
    def test_non_owner_leave_advances_only_leaving_participant(self):
        """Non-owner Leave: the leaving vendor actor is advanced to RM.CLOSED."""
        dl = _make_full_dl()
        result = CloseCaseReceivedUseCase(
            dl=dl,
            trigger_activity=TriggerActivityAdapter(dl),
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
            trigger_activity=TriggerActivityAdapter(dl),
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
            trigger_activity=TriggerActivityAdapter(dl),
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


def _redeliver_close(dl: SqliteDataLayer, activity_id: str) -> HandlerResult:
    """A redelivery of the Leave *activity_id*, routed as the inbox routes it:
    the copy intake archived (IE-10-001), not the resent body."""
    event = archived_redelivery(
        dl, activity_id, receiving_actor_id=CASE_ACTOR_ID
    )
    assert isinstance(event, CloseCaseReceivedEvent)
    return CloseCaseReceivedUseCase(
        dl=dl,
        request=event,
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
        trigger_activity=TriggerActivityAdapter(dl),
    ).execute()


def _seed_pending_invite(
    dl: SqliteDataLayer,
    suffix: str = "proposed",
    invitee_id: str = VENDOR_ID,
) -> str:
    """Propose an embargo and leave *invitee_id*'s Invite to it unanswered.

    The RSVP deadline is a year away, so only a settle step expires it before
    close.  Returns the embargo's id.
    """
    case = dl.read_case(CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    embargo = as_EmbargoEvent(
        id_=f"{CASE_ID}/embargo_events/{suffix}",
        context=CASE_ID,
        end_time=days_from_now_utc(45),
    )
    dl.create(embargo)
    propose(case, embargo.id_)
    dl.save(case)
    write_consent_rows(dl, case)
    invitee = dl.read(case.actor_participant_index[invitee_id])
    assert isinstance(invitee, CaseParticipant)
    invitee.apply_pec_transition(
        embargo.id_,
        PEC_Trigger.INVITE,
        entry_status=EmbargoRegisterStatus.PROPOSED,
        rsvp_deadline=days_from_now_utc(365),
    )
    dl.save(invitee)
    return embargo.id_


def _consent(dl: SqliteDataLayer, actor_id: str, embargo_id: str):
    case = dl.read_case(CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    participant = dl.read(case.actor_participant_index[actor_id])
    assert isinstance(participant, CaseParticipant)
    return participant.consent_for(embargo_id)


def _expiry_entries(dl: SqliteDataLayer) -> list[CaseLedgerEntry]:
    return [
        e
        for e in _case_ledger(dl)
        if e.semantic_type == INVITE_EXPIRED_SEMANTIC_TYPE
    ]


class TestPostCloseBoundary:
    """CM-23-013/014: nothing a participant does lands after case_fully_closed."""

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
        assert ledger and ledger[-1].semantic_type == "case_fully_closed", (
            "precondition: the owner close must have committed"
            f" case_fully_closed; tail={[e.semantic_type for e in ledger]}"
        )
        entries_at_close = len(ledger)
        rm_before = _participant_rm_states(dl, VENDOR_ID)
        outbox_before = set(dl.outbox_list())

        result = _close(
            dl, VENDOR_ID, "https://example.org/activities/leave-vendor"
        )

        assert len(_case_ledger(dl)) == entries_at_close, (
            "a post-close bystander Leave must commit no ledger entry"
            f" (CM-23-013); tail={[e.semantic_type for e in _case_ledger(dl)]}"
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

    @pytest.mark.spec("CM-23-014")
    def test_owner_close_expires_pending_invite_before_boundary(self):
        """An unanswered Invite is expired at close, not left waiting on its deadline."""
        dl = _make_full_dl()
        embargo_id = _seed_pending_invite(dl)
        case = dl.read_case(CASE_ID)
        assert isinstance(case, VulnerabilityCase)

        _close(dl, OWNER_ID, "https://example.org/activities/leave-owner")

        vendor = dl.read(case.actor_participant_index[VENDOR_ID])
        assert isinstance(vendor, CaseParticipant)
        assert (
            vendor.consent_for(embargo_id) == EmbargoConsentState.TIMED_OUT
        ), "owner close must expire a pending Invite immediately (CM-23-014)"
        ledger = _case_ledger(dl)
        types = [e.semantic_type for e in ledger]
        rm_closed_ids = {e.id_ for e in _case_actor_rm_closed_entries(dl)}
        rm_closed_idx = [
            i for i, e in enumerate(ledger) if e.id_ in rm_closed_ids
        ]
        lapse_idx = [
            i for i, t in enumerate(types) if t == INVITE_EXPIRED_SEMANTIC_TYPE
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


class TestOwnerCloseSettlesPendingInvites:
    """CM-23-014: the settle step between RM.CLOSED and case_fully_closed."""

    @pytest.mark.spec("CM-23-014")
    def test_close_without_pending_invite_commits_no_expiry_entry(self):
        """A case with no pending Invite closes exactly as before (AC-4)."""
        dl = _make_full_dl()

        _close(dl, OWNER_ID, "https://example.org/activities/leave-owner")

        assert _case_ledger(dl)[-1].semantic_type == "case_fully_closed"
        assert _expiry_entries(dl) == []

    @pytest.mark.spec("CM-23-014")
    def test_every_pending_invite_gets_one_entry(self):
        """Two pending Invites, two expiry entries, both before the boundary."""
        dl = _make_full_dl()
        first = _seed_pending_invite(dl, "first")
        second = _seed_pending_invite(dl, "second")

        _close(dl, OWNER_ID, "https://example.org/activities/leave-owner")

        expired = _expiry_entries(dl)
        named = {e.payload_snapshot["object"]["object"]["id"] for e in expired}
        assert named == {first, second}
        assert len(expired) == 2
        assert all(e.payload_snapshot["actor"] == VENDOR_ID for e in expired)
        assert _consent(dl, VENDOR_ID, first) == EmbargoConsentState.TIMED_OUT
        assert _consent(dl, VENDOR_ID, second) == EmbargoConsentState.TIMED_OUT
        ledger = _case_ledger(dl)
        assert ledger[-1].semantic_type == "case_fully_closed"
        assert all(e.log_index < ledger[-1].log_index for e in expired)

    @pytest.mark.spec("CM-23-014")
    def test_row_on_a_final_entry_is_not_settled(self):
        """A row frozen by a final register entry is not pending (ADR-0122)."""
        dl = _make_full_dl()
        embargo_id = _seed_pending_invite(dl)
        case = dl.read_case(CASE_ID)
        assert isinstance(case, VulnerabilityCase)
        reject(case, embargo_id)
        dl.save(case)

        _close(dl, OWNER_ID, "https://example.org/activities/leave-owner")

        assert _case_ledger(dl)[-1].semantic_type == "case_fully_closed"
        assert _expiry_entries(dl) == []
        assert (
            _consent(dl, VENDOR_ID, embargo_id) == EmbargoConsentState.INVITED
        )

    @pytest.mark.spec("CM-23-014")
    def test_stub_invitee_row_on_the_ended_embargo_is_not_settled(self):
        """A stub Invite's INVITED row needs no settling (CM-23-014, CM-11-006).

        A stub Invite leaves its invitee ``INVITED`` on the embargo in force.
        The close requires that embargo to end first (CM-23-011), which
        freezes the row, so the settle step leaves it and commits nothing.
        """
        dl = _make_full_dl()
        case = dl.read_case(CASE_ID)
        assert isinstance(case, VulnerabilityCase)
        embargo = as_EmbargoEvent(
            id_=f"{CASE_ID}/embargo_events/in-force",
            context=CASE_ID,
            end_time=days_from_now_utc(45),
        )
        dl.create(embargo)
        activate(case, embargo.id_)
        dl.save(case)
        write_consent_rows(dl, case)
        invitee = dl.read(case.actor_participant_index[VENDOR_ID])
        assert isinstance(invitee, CaseParticipant)
        invitee.apply_pec_transition(
            embargo.id_,
            PEC_Trigger.INVITE,
            entry_status=EmbargoRegisterStatus.ACTIVE,
            rsvp_deadline=days_from_now_utc(365),
        )
        dl.save(invitee)
        case = dl.read_case(CASE_ID)
        assert isinstance(case, VulnerabilityCase)
        terminate(case)
        dl.save(case)

        _close(dl, OWNER_ID, "https://example.org/activities/leave-owner")

        assert _case_ledger(dl)[-1].semantic_type == "case_fully_closed"
        assert _expiry_entries(dl) == []
        assert (
            _consent(dl, VENDOR_ID, embargo.id_) == EmbargoConsentState.INVITED
        )

    @pytest.mark.spec("CM-23-014")
    def test_failed_expiry_commit_still_closes_the_case(
        self, monkeypatch, caplog
    ):
        """A refused expiry commit is logged, and the case still closes."""
        dl = _make_full_dl()
        embargo_id = _seed_pending_invite(dl)
        monkeypatch.setattr(
            "vultron.core.behaviors.embargo.nodes.invitation_expiry"
            ".create_commit_and_record_expiry_tree",
            lambda *a, **kw: py_trees.behaviours.Failure(name="ForcedFailure"),
        )

        with caplog.at_level(logging.WARNING):
            _close(dl, OWNER_ID, "https://example.org/activities/leave-owner")

        assert _expiry_entries(dl) == []
        assert (
            _consent(dl, VENDOR_ID, embargo_id) == EmbargoConsentState.INVITED
        )
        assert _case_ledger(dl)[-1].semantic_type == "case_fully_closed"
        assert any(
            "could not expire the Invite" in r.getMessage()
            for r in caplog.records
        )

    @pytest.mark.spec("CM-23-014")
    def test_entry_names_the_invite_the_ledger_recorded(self):
        """The expiry entry's object is the last Invite sent to that invitee."""
        from vultron.core.behaviors.case.nodes.leave.settle import (
            latest_invite_id,
        )
        from vultron.core.behaviors.embargo.nodes.relay import (
            EMBARGO_INVITE_SEMANTIC_TYPE,
        )
        from vultron.core.models.rsvp_deadline import (
            EMBARGO_REINVITE_SEMANTIC_TYPE,
        )

        embargo_id = f"{CASE_ID}/embargo_events/proposed"

        def entry(index: int, semantic_type: str, to: str, invite: str):
            return _to_persistable_entry(
                HashChainLedgerRecord(
                    case_id=CASE_ID,
                    log_index=index,
                    object_id=invite,
                    semantic_type=semantic_type,
                    payload_snapshot={
                        "type": "Invite",
                        "actor": CASE_ACTOR_ID,
                        "to": [to],
                        "object": {"type": "EmbargoEvent", "id": embargo_id},
                    },
                    prev_log_hash=_ZERO_HASH,
                )
            )

        entries = [
            entry(0, EMBARGO_INVITE_SEMANTIC_TYPE, VENDOR_ID, "urn:invite:1"),
            entry(1, EMBARGO_INVITE_SEMANTIC_TYPE, OWNER_ID, "urn:invite:2"),
            entry(
                2, EMBARGO_REINVITE_SEMANTIC_TYPE, VENDOR_ID, "urn:invite:3"
            ),
            entry(3, "close_case", VENDOR_ID, "urn:leave:4"),
        ]

        assert latest_invite_id(entries, VENDOR_ID, embargo_id) == (
            "urn:invite:3"
        )
        assert latest_invite_id(entries, OWNER_ID, embargo_id) == (
            "urn:invite:2"
        )
        assert latest_invite_id(entries, VENDOR_ID, "urn:other") is None

    @pytest.mark.spec("CM-23-014")
    def test_a_replica_applies_the_settled_expiry(self):
        """The settle entry replays on a replica through the announce tree (AC-2)."""
        manager = _make_full_dl()
        embargo_id = _seed_pending_invite(manager)
        _close(manager, OWNER_ID, "https://example.org/activities/leave-owner")
        (settled,) = _expiry_entries(manager)
        ledger = _case_ledger(manager)
        # The expiry, then the CASE_MANAGER's Update carrying the row.
        row_entry = ledger[ledger.index(settled) + 1]
        assert row_entry.semantic_type == UPDATE_EMBARGO_CONSENT_SEMANTIC_TYPE

        replica = _make_full_dl(store_owner_id=VENDOR_ID)
        assert _seed_pending_invite(replica) == embargo_id
        case = replica.read(CASE_ID)
        prev_hash = getattr(case, "genesis_hash", _ZERO_HASH) or _ZERO_HASH
        # The two entries, as the first of the replica's chain.
        for log_index, source in enumerate((settled, row_entry)):
            entry = _to_persistable_entry(
                HashChainLedgerRecord(
                    case_id=CASE_ID,
                    log_index=log_index,
                    object_id=source.log_object_id,
                    semantic_type=source.semantic_type,
                    payload_snapshot=source.payload_snapshot,
                    prev_log_hash=prev_hash,
                )
            )
            prev_hash = entry.entry_hash
            result = BTBridge(
                datalayer=replica, wire_render_port=As2WireRenderAdapter()
            ).execute_with_setup(
                tree=create_announce_log_entry_tree(
                    sender_rule=AnnounceLedgerEntryReceivedUseCase.sender_entitlement
                ),
                actor_id=VENDOR_ID,
                activity=_make_announce_event(
                    entry=entry, sender_actor_id=CASE_ACTOR_ID
                ),
                sync_port=MagicMock(spec=SyncActivityPort),
            )
            assert result.status.name == "SUCCESS", result.feedback_message

        assert (
            _consent(replica, VENDOR_ID, embargo_id)
            == EmbargoConsentState.TIMED_OUT
        )


def _close_with_policy(
    dl: SqliteDataLayer,
    sender_actor_id: str,
    activity_id: str,
    policy: PostCloseReply,
) -> HandlerResult:
    return CloseCaseReceivedUseCase(
        dl=dl,
        request=_make_close_case_event(
            sender_actor_id=sender_actor_id, activity_id=activity_id
        ),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
        trigger_activity=TriggerActivityAdapter(dl),
        actor_config=ActorConfig(post_close_reply=policy),
    ).execute()


def _closed_dl() -> SqliteDataLayer:
    """The CaseActor's store after the Case Owner has closed the case."""
    dl = _make_full_dl()
    _close(dl, OWNER_ID, "https://example.org/activities/leave-owner")
    assert _case_ledger(dl)[-1].semantic_type == "case_fully_closed"
    return dl


def _add_note_event(note_id: str, sender_id: str = VENDOR_ID):
    from vultron.core.models.events.note import AddNoteToCaseReceivedEvent
    from vultron.wire.as2.factories import add_note_to_case_activity
    from vultron.wire.as2.vocab.base.objects.object_types import as_Note

    note = as_Note(id_=note_id, content="late note", context=CASE_ID)
    activity = add_note_to_case_activity(
        note,
        target=as_VulnerabilityCase(id_=CASE_ID),
        actor=sender_id,
        to=[CASE_ACTOR_ID],
    )
    event = received_event(activity).model_copy(
        update={"receiving_actor_id": CASE_ACTOR_ID}
    )
    assert isinstance(event, AddNoteToCaseReceivedEvent)
    return note, event


def _add_note(dl: SqliteDataLayer, note_id: str, sync_port=None):
    from vultron.core.use_cases.received.note import (
        AddNoteToCaseReceivedUseCase,
    )

    _, event = _add_note_event(note_id)
    return AddNoteToCaseReceivedUseCase(
        dl,
        event,
        wire_render_port=As2WireRenderAdapter(),
        sync_port=sync_port or SyncActivityAdapter(dl),
    ).execute()


class TestPostCloseWriteBoundary:
    """CM-23-013 / ADR-0085: after case_fully_closed, nothing is recorded."""

    @pytest.mark.spec("CM-23-013")
    @pytest.mark.parametrize(
        ("policy", "replies"),
        [(PostCloseReply.DROP, 0), (PostCloseReply.REJECT, 1)],
    )
    def test_late_leave_follows_the_reply_policy(self, policy, replies):
        """A late Leave is REFUSED and records nothing; only REJECT replies."""
        dl = _closed_dl()
        entries_at_close = len(_case_ledger(dl))
        rm_before = _participant_rm_states(dl, VENDOR_ID)
        outbox_before = set(dl.outbox_list())

        result = _close_with_policy(
            dl, VENDOR_ID, "https://example.org/activities/leave-late", policy
        )

        assert result.disposition is HandlerDisposition.REFUSED
        assert "CM-23-013" in (result.reason or "")
        assert len(_case_ledger(dl)) == entries_at_close
        assert _participant_rm_states(dl, VENDOR_ID) == rm_before
        queued = [i for i in dl.outbox_list() if i not in outbox_before]
        assert len(queued) == replies, queued
        if replies:
            reject = dl.read(queued[0])
            assert getattr(reject, "type_", None) == "Reject"
            assert VENDOR_ID in (getattr(reject, "to", None) or [])
            inner = getattr(reject, "object_", None)
            assert getattr(inner, "type_", None) == "Leave"

    @pytest.mark.spec("CM-23-013")
    def test_default_policy_drops_a_late_leave(self):
        """The default ActorConfig drops a late Leave with no reply (ADR-0131)."""
        assert ActorConfig().post_close_reply is PostCloseReply.DROP
        dl = _closed_dl()
        outbox_before = set(dl.outbox_list())

        result = _close(
            dl, VENDOR_ID, "https://example.org/activities/leave-late"
        )

        assert result.disposition is HandlerDisposition.REFUSED
        assert set(dl.outbox_list()) == outbox_before

    @pytest.mark.spec("CM-23-013")
    @pytest.mark.spec("CM-23-018")
    def test_a_repeat_owner_leave_after_full_close_is_refused(self):
        """After case_fully_closed, a repeat owner Leave with a new id is
        REFUSED and changes nothing (CM-23-018 owner exception ends here)."""
        dl = _closed_dl()
        entries_at_close = len(_case_ledger(dl))
        owner_rm_before = _participant_rm_states(dl, OWNER_ID)
        actor_rm_before = _participant_rm_states(dl, CASE_ACTOR_ID)
        outbox_before = set(dl.outbox_list())

        result = _close(
            dl, OWNER_ID, "https://example.org/activities/leave-owner-again"
        )

        assert result.disposition is HandlerDisposition.REFUSED
        assert "CM-23-013" in (result.reason or "")
        assert len(_case_ledger(dl)) == entries_at_close
        assert _participant_rm_states(dl, OWNER_ID) == owner_rm_before
        assert _participant_rm_states(dl, CASE_ACTOR_ID) == actor_rm_before
        assert set(dl.outbox_list()) == outbox_before

    @pytest.mark.spec("CM-23-013")
    def test_late_leave_drop_is_logged_with_activity_and_actor(self, caplog):
        """The drop names the activity id and the sender at INFO (SL-01)."""
        dl = _closed_dl()
        activity_id = "https://example.org/activities/leave-late-logged"
        with caplog.at_level(logging.INFO):
            _close(dl, VENDOR_ID, activity_id)
        dropped = [
            r.getMessage()
            for r in caplog.records
            if "dropped activity_id" in r.getMessage()
        ]
        assert dropped, "the post-close drop must be logged at INFO"
        assert activity_id in dropped[0]
        assert VENDOR_ID in dropped[0]

    @pytest.mark.spec("CM-23-013")
    def test_a_late_reply_is_answered_at_most_once(self):
        """A redelivered late Leave is not answered again under REJECT."""
        dl = _closed_dl()
        outbox_before = set(dl.outbox_list())
        activity_id = "https://example.org/activities/leave-late-twice"
        for _ in range(2):
            _close_with_policy(
                dl, VENDOR_ID, activity_id, PostCloseReply.REJECT
            )
        queued = [i for i in dl.outbox_list() if i not in outbox_before]
        assert len(queued) == 1, queued

    @pytest.mark.spec("CM-23-013")
    @pytest.mark.spec("VP-03-013")
    def test_post_close_add_note_is_refused_with_no_ledger_append(self):
        """#3060 AC-1: a post-close Add(Note, target=Case) appends nothing.

        The note is not attached to the case and no entry is committed or
        announced; the CASE_MANAGER sends nothing back (non-Leave traffic
        after close is never answered, ADR-0131).
        """
        dl = _closed_dl()
        entries_at_close = len(_case_ledger(dl))
        outbox_before = set(dl.outbox_list())

        result = _add_note(dl, "https://example.org/notes/late-note")

        assert result.disposition is HandlerDisposition.REFUSED
        assert "CM-23-013" in (result.reason or "")
        assert len(_case_ledger(dl)) == entries_at_close
        case = dl.read_case(CASE_ID)
        assert case is not None
        assert "https://example.org/notes/late-note" not in case.notes
        assert set(dl.outbox_list()) == outbox_before

    @pytest.mark.spec("CM-23-013")
    def test_add_note_before_close_is_still_recorded(self):
        """Control: the same Add(Note) on an open case is committed."""
        dl = _make_full_dl()
        entries_before = len(_case_ledger(dl))

        result = _add_note(dl, "https://example.org/notes/open-note")

        assert result.disposition is HandlerDisposition.APPLIED
        assert len(_case_ledger(dl)) == entries_before + 1

    @pytest.mark.spec("CM-23-002")
    @pytest.mark.spec("CM-23-013")
    def test_closure_announce_is_emitted_before_external_writes_cease(self):
        """#3060 AC-4: case_fully_closed is announced, then nothing more is."""
        dl = _make_full_dl()
        sync = MagicMock(wraps=SyncActivityAdapter(dl))
        CloseCaseReceivedUseCase(
            dl=dl,
            trigger_activity=TriggerActivityAdapter(dl),
            request=_make_close_case_event(sender_actor_id=OWNER_ID),
            sync_port=sync,
            wire_render_port=As2WireRenderAdapter(),
        ).execute()
        announced = [
            (c.kwargs.get("entry") or c.args[0]).semantic_type
            for c in sync.send_announce_log_entry.call_args_list
        ]
        assert "case_fully_closed" in announced, announced
        calls_at_close = sync.send_announce_log_entry.call_count

        result = _add_note(
            dl, "https://example.org/notes/after-announce", sync_port=sync
        )

        assert result.disposition is HandlerDisposition.REFUSED
        assert sync.send_announce_log_entry.call_count == calls_at_close

    @pytest.mark.spec("CM-23-013")
    def test_a_replica_still_processes_after_close(self):
        """The guard binds only the CASE_MANAGER: a replica's store passes it."""
        from vultron.core.behaviors.case.nodes.post_close import (
            CaseOpenToExternalWritesNode,
        )

        dl = _closed_dl()
        node = CaseOpenToExternalWritesNode(case_id=CASE_ID)
        node.datalayer = dl
        node.actor_id = VENDOR_ID
        assert node.update() == py_trees.common.Status.SUCCESS
        node.actor_id = CASE_ACTOR_ID
        assert node.update() == py_trees.common.Status.FAILURE

    @pytest.mark.spec("CM-23-013")
    @pytest.mark.spec("CM-23-017")
    def test_a_late_participant_status_gets_no_processing_fault(self):
        """A refused status claim is normally answered; after close it is not."""
        from vultron.core.models.events.status import (
            AddParticipantStatusToParticipantReceivedEvent,
        )
        from vultron.core.use_cases.received.status import (
            AddParticipantStatusToParticipantReceivedUseCase,
        )
        from vultron.wire.as2.factories import (
            add_status_to_participant_activity,
        )
        from vultron.wire.as2.vocab.objects.case_status import (
            as_ParticipantStatus,
        )

        dl = _closed_dl()
        case = dl.read_case(CASE_ID)
        assert case is not None
        participant = dl.read(case.actor_participant_index[VENDOR_ID])
        assert isinstance(participant, CaseParticipant)
        status = as_ParticipantStatus(
            id_=f"{CASE_ID}/participants/vendor/statuses/late",
            context=CASE_ID,
            attributed_to=VENDOR_ID,
            rm=RmDimension(state=RM.VALID),
        )
        activity = add_status_to_participant_activity(
            status,
            target=participant,
            actor=VENDOR_ID,
            to=[CASE_ACTOR_ID],
            context=as_VulnerabilityCase(id_=CASE_ID),
        )
        event = received_event(activity).model_copy(
            update={"receiving_actor_id": CASE_ACTOR_ID}
        )
        assert isinstance(
            event, AddParticipantStatusToParticipantReceivedEvent
        )
        entries_at_close = len(_case_ledger(dl))
        outbox_before = set(dl.outbox_list())

        result = AddParticipantStatusToParticipantReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        assert "CM-23-013" in (result.reason or "")
        assert len(_case_ledger(dl)) == entries_at_close
        assert set(dl.outbox_list()) == outbox_before

    @pytest.mark.spec("CM-23-013")
    @pytest.mark.parametrize("policy", ["drop", "reject"])
    def test_dispatcher_wires_the_policy_point(self, policy):
        """End to end: the configured policy reaches the late-Leave reply.

        Through the inbox dispatcher, a late Leave is answered only under
        ``reject``; a late Add(Note) is dropped under both settings.
        """
        from vultron.adapters.driving.fastapi.inbox_handler import (
            make_dispatcher,
        )
        from vultron.config.app import config_override

        dl = _closed_dl()
        with config_override(VULTRON_ACTOR__POST_CLOSE_REPLY=policy):
            dispatcher = make_dispatcher()
            outbox_before = set(dl.outbox_list())
            _, note_event = _add_note_event(
                "https://example.org/notes/dispatched-late-note"
            )
            note_result = dispatcher.dispatch(note_event, dl)
            assert note_result.disposition is HandlerDisposition.REFUSED
            assert set(dl.outbox_list()) == outbox_before

            leave_result = dispatcher.dispatch(
                _make_close_case_event(
                    sender_actor_id=VENDOR_ID,
                    activity_id="https://example.org/activities/leave-disp",
                ),
                dl,
            )
            assert leave_result.disposition is HandlerDisposition.REFUSED
            queued = [i for i in dl.outbox_list() if i not in outbox_before]
            assert len(queued) == (1 if policy == "reject" else 0), queued


# ---------------------------------------------------------------------------
# Replica path: the announce tree applies the closure step entries
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
            semantic_type="close_case",
            payload_snapshot={"actor": departing_actor_id},
            prev_log_hash=genesis_hash,
        )
    )


def _make_announce_event(
    entry: CaseLedgerEntry,
    sender_actor_id: str,
    receiver_id: str = VENDOR_ID,
) -> AnnounceLogEntryReceivedEvent:
    from typing import cast

    wire_entry = WireCaseLedgerEntry.model_validate(
        entry.model_dump(mode="json")
    )
    activity = announce_log_entry_activity(
        entry=wire_entry, actor=sender_actor_id, to=[receiver_id]
    )
    return cast(AnnounceLogEntryReceivedEvent, received_event(activity))


def _replica_of(manager: SqliteDataLayer, actor_id: str = VENDOR_ID):
    """*actor_id*'s replica, seeded with the case exactly as *manager* holds it.

    A replica is the case as seeded plus the ledger entries since
    (CM-23-016), so the seed copies every case record with its ids: the
    status entries name the participant and status ids the CASE_MANAGER
    holds.
    """
    replica = _make_dl(actor_id)
    for type_key in (
        "VulnerabilityCase",
        "CaseParticipant",
        "ParticipantStatus",
    ):
        for obj in manager.list_objects(type_key):
            replica.create(obj)
    return replica


def _replay(manager: SqliteDataLayer, replica: SqliteDataLayer) -> None:
    """Announce every entry of *manager*'s ledger to *replica*, in order."""
    _deliver(replica, _case_ledger(manager))


def _deliver(replica: SqliteDataLayer, entries) -> None:
    """Announce each of *entries* to *replica*, in order."""
    for entry in entries:
        result = BTBridge(
            datalayer=replica, wire_render_port=As2WireRenderAdapter()
        ).execute_with_setup(
            tree=create_announce_log_entry_tree(
                sender_rule=AnnounceLedgerEntryReceivedUseCase.sender_entitlement
            ),
            actor_id=replica.actor_id,
            activity=_make_announce_event(
                entry=entry,
                sender_actor_id=CASE_ACTOR_ID,
                receiver_id=replica.actor_id,
            ),
            sync_port=MagicMock(spec=SyncActivityPort),
        )
        assert result.status == py_trees.common.Status.SUCCESS, (
            f"replica refused {entry.semantic_type} at logIndex"
            f" {entry.log_index}: {result.feedback_message}"
        )


def _status_history(
    dl: SqliteDataLayer, actor_id: str
) -> list[tuple[str, RM]]:
    """The actor's ``(status id, RM state)`` history in *dl*, in order."""
    case = dl.read(CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    participant = dl.read(case.actor_participant_index[actor_id])
    assert isinstance(participant, CaseParticipant)
    return [
        (ps.id_, ps.rm.state)
        for ps in participant.participant_statuses
        if isinstance(ps, ParticipantStatus)
    ]


def _ledger_rm_steps(dl: SqliteDataLayer, actor_id: str) -> list[str]:
    """The status ids the ledger records for *actor_id*, in ledger order."""
    return [
        e.log_object_id
        for e in _case_ledger(dl)
        if e.semantic_type == "add_participant_status_to_participant"
        and e.payload_snapshot["object"].get("attributedTo") == actor_id
    ]


def _ledger_shape(
    dl: SqliteDataLayer,
) -> list[tuple[str, str | None, str | None]]:
    """``(semantic type, subject, rm state)`` per ledger entry, in ledger order.

    The subject of a status entry is the actor its status is attributed to;
    of every other entry, the snapshot's ``actor``.
    """
    shape: list[tuple[str, str | None, str | None]] = []
    for e in _case_ledger(dl):
        snapshot = e.payload_snapshot or {}
        status = snapshot.get("object")
        if e.semantic_type == "add_participant_status_to_participant":
            assert isinstance(status, dict)
            shape.append(
                (
                    e.semantic_type,
                    status.get("attributedTo"),
                    status.get("rmState"),
                )
            )
        else:
            shape.append((e.semantic_type, snapshot.get("actor"), None))
    return shape


_STATUS = "add_participant_status_to_participant"


class TestLeaveCommitsEachClosureStep:
    """CM-23-001/002/003: close_case first, then one status entry per RM step."""

    @pytest.mark.spec("CM-23-001")
    @pytest.mark.spec("CM-23-003")
    @pytest.mark.spec("RMB-14-005")
    def test_non_owner_leave_from_valid_commits_two_steps(self):
        """A non-owner Leave from Valid commits close_case, V → D, D → C."""
        dl = _make_full_dl()
        _seed_rm(dl, VENDOR_ID, RM.VALID)

        _close(dl, VENDOR_ID, "https://example.org/activities/leave-vendor")

        assert _ledger_shape(dl) == [
            ("close_case", VENDOR_ID, None),
            (_STATUS, VENDOR_ID, RM.DEFERRED.value),
            (_STATUS, VENDOR_ID, RM.CLOSED.value),
        ]

    @pytest.mark.spec("CM-23-001")
    @pytest.mark.spec("CM-23-002")
    @pytest.mark.spec("CM-23-005")
    @pytest.mark.spec("CM-23-014")
    def test_owner_leave_orders_every_entry_before_the_boundary(self):
        """Owner Leave: close_case, owner steps, CASE_MANAGER steps, settle, boundary.

        The owner leaves from Valid (V → D → C) with an embargo Invite still
        pending, so every kind of entry the owner-close sequence commits
        appears once, in the order CM-23-002 and CM-23-014 give.
        """
        dl = _make_full_dl()
        _seed_rm(dl, OWNER_ID, RM.VALID)
        _seed_rm(dl, CASE_ACTOR_ID, RM.ACCEPTED)
        _seed_pending_invite(dl)

        _close(dl, OWNER_ID, "https://example.org/activities/leave-owner")

        shape = _ledger_shape(dl)
        assert shape[:4] == [
            ("close_case", OWNER_ID, None),
            (_STATUS, OWNER_ID, RM.DEFERRED.value),
            (_STATUS, OWNER_ID, RM.CLOSED.value),
            (_STATUS, CASE_ACTOR_ID, RM.CLOSED.value),
        ]
        assert shape[4][0] == INVITE_EXPIRED_SEMANTIC_TYPE
        # The TIMED_OUT row is the CASE_MANAGER's own entry (ADR-0124).
        assert shape[5][0] == UPDATE_EMBARGO_CONSENT_SEMANTIC_TYPE
        assert shape[6:] == [("case_fully_closed", CASE_ACTOR_ID, None)]

    @pytest.mark.spec("CM-23-004")
    @pytest.mark.parametrize(
        "leaver_id", [OWNER_ID, VENDOR_ID], ids=["owner", "non-owner"]
    )
    def test_the_leaver_receives_every_step_entry(self, leaver_id: str):
        """Each of the leaver's status entries is announced to the leaver.

        The step that reaches RM.CLOSED included: the leaver is already
        closed when that entry fans out, and it still receives it (AC-4).
        """
        dl = _make_full_dl()
        _seed_rm(dl, leaver_id, RM.VALID)
        sync_port = MagicMock(spec=SyncActivityPort)

        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=leaver_id),
            sync_port=sync_port,
            wire_render_port=As2WireRenderAdapter(),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        sent_to_leaver = {
            call.kwargs["entry"].log_object_id
            for call in sync_port.send_announce_log_entry.call_args_list
            if call.kwargs["to"] == [leaver_id]
        }
        steps = _ledger_rm_steps(dl, leaver_id)
        assert len(steps) == 2, steps
        assert set(steps) <= sent_to_leaver, (
            f"the leaver's replica must receive every step entry (CM-23-004);"
            f" steps={steps}, sent={sent_to_leaver}"
        )

    @pytest.mark.spec("CM-23-001")
    @pytest.mark.spec("CLP-07-015")
    @pytest.mark.spec("RMB-14-005")
    def test_a_refused_step_keeps_none_of_the_closure(self, monkeypatch):
        """V → D written, D → C refused: the act keeps nothing (CLP-07-015).

        The Leave's own entry and every closure step are one act, so a step
        that will not write takes back the D step and the close_case entry.
        """
        from vultron.core.behaviors.case.nodes.participant.status import (
            CreateParticipantStatusNode,
        )

        original = CreateParticipantStatusNode.update

        def _refuse_closed(node):
            if node._rm_state is RM.CLOSED:
                return py_trees.common.Status.FAILURE
            return original(node)

        monkeypatch.setattr(
            CreateParticipantStatusNode, "update", _refuse_closed
        )
        dl = _make_full_dl()
        _seed_rm(dl, VENDOR_ID, RM.VALID)
        before = _case_file(dl, VENDOR_ID)

        result = _close(
            dl, VENDOR_ID, "https://example.org/activities/leave-vendor"
        )

        assert result.disposition != HandlerDisposition.APPLIED
        assert _latest_rm(dl, VENDOR_ID) == RM.VALID
        assert _case_file(dl, VENDOR_ID) == before
        assert _ledger_shape(dl) == []

    @pytest.mark.spec("CM-23-001")
    @pytest.mark.spec("CLP-07-013")
    def test_failed_step_commit_leaves_the_case_file_unchanged(
        self, monkeypatch
    ):
        """A step entry that cannot be committed takes the act back (AC-3).

        The leaver's participant record and the store's statuses are exactly
        what they were before the Leave, the Leave is not applied, and not
        even its close_case entry is kept: a change with no committed entry
        is not made (CLP-07-013, CLP-07-015).
        """
        dl = _make_full_dl()
        _seed_rm(dl, VENDOR_ID, RM.VALID)
        before = _case_file(dl, VENDOR_ID)
        monkeypatch.setattr(
            "vultron.core.behaviors.case.nodes.participant.status_entries"
            ".create_commit_log_entry_tree",
            lambda *a, **kw: py_trees.behaviours.Failure(name="ForcedFailure"),
        )

        result = _close(
            dl, VENDOR_ID, "https://example.org/activities/leave-vendor"
        )

        assert result.disposition != HandlerDisposition.APPLIED
        assert _case_file(dl, VENDOR_ID) == before
        assert _latest_rm(dl, VENDOR_ID) == RM.VALID
        assert _case_ledger(dl) == []

    @pytest.mark.spec("CM-23-001")
    @pytest.mark.spec("CLP-07-015")
    def test_a_later_step_failing_takes_back_the_committed_one(
        self, monkeypatch
    ):
        """V → D commits, D → C does not: the act keeps neither step."""
        from vultron.core.behaviors.case.nodes.participant import (
            status_entries,
        )

        calls = fail_commits(monkeypatch, status_entries, allowed=1)
        dl = _make_full_dl()
        _seed_rm(dl, VENDOR_ID, RM.VALID)
        before = _participant_rm_states(dl, VENDOR_ID)

        _close(dl, VENDOR_ID, "https://example.org/activities/leave-vendor")

        assert _participant_rm_states(dl, VENDOR_ID) == before
        assert _ledger_shape(dl) == []
        assert all(dl.read(status_id) is None for status_id in calls)

    @pytest.mark.spec("CM-23-001")
    def test_a_redelivered_leave_completes_the_withdrawn_closure(
        self, monkeypatch
    ):
        """The Leave is not lost: a redelivery walks the closure again."""
        dl = _make_full_dl()
        with monkeypatch.context() as patch:
            patch.setattr(
                "vultron.core.behaviors.case.nodes.participant.status_entries"
                ".create_commit_log_entry_tree",
                lambda *a, **kw: py_trees.behaviours.Failure(name="Forced"),
            )
            _close(
                dl, VENDOR_ID, "https://example.org/activities/leave-vendor"
            )

        result = _redeliver_close(
            dl, "https://example.org/activities/leave-vendor"
        )

        assert result.disposition == HandlerDisposition.APPLIED
        assert _latest_rm(dl, VENDOR_ID) == RM.CLOSED
        assert _ledger_rm_steps(dl, VENDOR_ID)

    @pytest.mark.spec("CM-23-001")
    def test_crash_in_step_commit_is_an_internal_error_not_a_warning(
        self, monkeypatch
    ):
        """A refused commit fails the node; a bug in the commit raises.

        A crash inside the nested commit tree is carried across the hop as
        an internal error, so the received verdict does not log it as a
        WARNING and report the closure as applied (CONCERN-3019, #4113).
        """

        class _Crash(py_trees.behaviour.Behaviour):
            def update(self) -> py_trees.common.Status:
                raise RuntimeError("simulated crash in the step commit")

        dl = _make_full_dl()
        monkeypatch.setattr(
            "vultron.core.behaviors.case.nodes.participant.status_entries"
            ".create_commit_log_entry_tree",
            lambda *a, **kw: _Crash(name="CrashingCommit"),
        )

        before = _case_file(dl, VENDOR_ID)
        with pytest.raises(VultronBTInternalError, match="nested commit"):
            _close(
                dl, VENDOR_ID, "https://example.org/activities/leave-vendor"
            )

        assert _case_file(dl, VENDOR_ID) == before, (
            "a crashed commit records nothing, so its step is taken back too"
        )

    @pytest.mark.spec("CM-23-001")
    @pytest.mark.spec("CLP-07-013")
    def test_a_raise_while_building_a_step_entry_takes_the_steps_back(
        self, monkeypatch
    ):
        """Any raise part-way through the commits takes the act back.

        The V -> D entry commits; building the D -> C activity then raises.
        The fault propagates, and the act keeps neither step nor any entry
        (CLP-07-015), rather than leave a step the ledger lacks.
        """
        original = TriggerActivityAdapter.record_participant_status_added
        built: list[str] = []

        def _raise_on_second(self, *args, **kwargs):
            built.append(kwargs["status"].id_)
            if len(built) == 2:
                raise RuntimeError("simulated factory fault")
            return original(self, *args, **kwargs)

        monkeypatch.setattr(
            TriggerActivityAdapter,
            "record_participant_status_added",
            _raise_on_second,
        )
        dl = _make_full_dl()
        _seed_rm(dl, VENDOR_ID, RM.VALID)
        before = _participant_rm_states(dl, VENDOR_ID)

        with pytest.raises(Exception, match="simulated factory fault"):
            _close(
                dl, VENDOR_ID, "https://example.org/activities/leave-vendor"
            )

        assert _participant_rm_states(dl, VENDOR_ID) == before
        assert _ledger_shape(dl) == []
        assert all(dl.read(status_id) is None for status_id in built)


class TestCaseFullyClosedIsTheCaseManagersOwnAct:
    """CM-23-002 step 3: closure is the CASE_MANAGER's own activity (#3743).

    The ``Leave`` is recorded as received (``close_case``); the closure that
    follows is the CASE_MANAGER's factory-built ``Update(VulnerabilityCase)``
    carrying the closed case, recorded from its sealed blob (CLP-07-013,
    VM-08-003).  No entry poses as an act the Case Owner did not send.
    """

    @staticmethod
    def _closure(dl: SqliteDataLayer) -> CaseLedgerEntry:
        (entry,) = [
            e
            for e in _case_ledger(dl)
            if e.semantic_type == "case_fully_closed"
        ]
        return entry

    @pytest.mark.spec("CLP-07-013")
    @pytest.mark.spec("CM-23-002")
    def test_the_closure_is_the_case_managers_update_of_the_case(self):
        dl = _make_full_dl()
        _close(dl, OWNER_ID, "https://example.org/activities/leave-owner")

        snapshot = self._closure(dl).payload_snapshot
        assert snapshot["type"] == "Update"
        assert snapshot["actor"] == CASE_ACTOR_ID
        assert snapshot["context"] == CASE_ID
        case = snapshot["object"]
        assert case["type"] == "VulnerabilityCase"
        assert case["id"] == CASE_ID
        # Carried in full: the participants are objects, not ids (CLP-07-006).
        assert case["caseParticipants"]
        assert all(isinstance(p, dict) for p in case["caseParticipants"])

    @pytest.mark.spec("VM-08-003")
    def test_the_entry_is_the_sealed_blob(self):
        dl = _make_full_dl()
        _close(dl, OWNER_ID, "https://example.org/activities/leave-owner")

        entry = self._closure(dl)
        sealed = read_sealed_body(dl, entry.log_object_id)
        assert sealed is not None, "the closure activity was not sealed"
        assert entry.payload_snapshot == json.loads(sealed.body)

    @pytest.mark.spec("CLP-07-013")
    def test_the_closure_follows_the_leaves_own_entry(self):
        dl = _make_full_dl()
        _close(dl, OWNER_ID, "https://example.org/activities/leave-owner")

        types = [e.semantic_type for e in _case_ledger(dl)]
        assert types.index("close_case") < types.index("case_fully_closed")
        assert types[-1] == "case_fully_closed"

    @pytest.mark.spec("CM-23-016")
    @pytest.mark.spec("RSH-08-004")
    def test_a_replica_stores_the_closure_and_changes_nothing(self):
        """The replica stores the entry; the case it carries is already held.

        Every RM step arrived as its own entry before it, so applying the
        closure writes nothing (CM-23-016): the replica's case is the same
        before and after it.
        """
        manager = _make_full_dl()
        replica = _replica_of(manager)
        _close(manager, OWNER_ID, "https://example.org/activities/leave-owner")
        *before, closure = _case_ledger(manager)
        assert closure.semantic_type == "case_fully_closed"
        _deliver(replica, before)
        case_before = replica.read_case(CASE_ID)

        _deliver(replica, [closure])

        assert replica.read(closure.id_) is not None
        assert replica.read_case(CASE_ID) == case_before

    @pytest.mark.spec("CM-23-002")
    def test_a_close_with_no_factory_raises_rather_than_half_closing(self):
        """No trigger-activity factory is a wiring fault, not a non-owner Leave.

        A FAILURE would send the owner arm's Selector down the non-owner path
        and report a half-closed case as SUCCESS.
        """
        dl = _make_full_dl()
        with pytest.raises(VultronBTInternalError):
            CloseCaseReceivedUseCase(
                dl=dl,
                request=_make_close_case_event(sender_actor_id=OWNER_ID),
                sync_port=SyncActivityAdapter(dl),
                wire_render_port=As2WireRenderAdapter(),
            ).execute()
        assert not _case_fully_closed_present(dl)


class TestReplicaAppliesTheClosureSteps:
    """A replica advances the leaver only by applying the status entries.

    CM-23-001, CM-23-016: the CASE_MANAGER commits one status entry per RM
    transition it writes for the leaver; the ``close_case`` entry changes no
    RM state; a replica never walks the RM table from its own view (#4091).
    """

    @pytest.mark.spec("CM-23-001")
    @pytest.mark.spec("CM-23-003")
    @pytest.mark.parametrize(
        "leaver_id", [OWNER_ID, VENDOR_ID], ids=["owner", "non-owner"]
    )
    def test_replica_closes_the_leaver_from_the_ledger(self, leaver_id: str):
        """Replaying the CASE_MANAGER's ledger closes the leaver on a replica."""
        manager = _make_full_dl()
        _seed_rm(manager, leaver_id, RM.ACCEPTED)
        replica = _replica_of(manager)
        _close(manager, leaver_id, "https://example.org/activities/leave")

        _replay(manager, replica)

        assert _latest_rm(replica, leaver_id) == RM.CLOSED

    @pytest.mark.spec("CM-23-004")
    @pytest.mark.spec("CM-23-001")
    @pytest.mark.parametrize(
        "leaver_id", [OWNER_ID, VENDOR_ID], ids=["owner", "non-owner"]
    )
    def test_leavers_replica_closes_only_from_what_it_is_sent(
        self, leaver_id: str
    ):
        """The leaver's own replica closes on the CASE_MANAGER's entries only.

        It writes no ``CLOSED`` of its own when it leaves (the sender side
        does not, AC-4 of #4212), so it is still open until the entries the
        CASE_MANAGER sends it arrive.  Those are its ``close_case`` entry and
        its own closure steps; nothing after them, ``case_fully_closed``
        included, is sent to it (CM-23-004).
        """
        manager = _make_full_dl()
        _seed_rm(manager, leaver_id, RM.VALID)
        replica = _replica_of(manager, leaver_id)
        sync_port = MagicMock(spec=SyncActivityPort)

        CloseCaseReceivedUseCase(
            dl=manager,
            request=_make_close_case_event(sender_actor_id=leaver_id),
            sync_port=sync_port,
            wire_render_port=As2WireRenderAdapter(),
            trigger_activity=TriggerActivityAdapter(manager),
        ).execute()
        assert _latest_rm(replica, leaver_id) == RM.VALID

        sent = [e for e, to in _announced(sync_port) if leaver_id in to]
        _deliver(replica, sent)

        assert _latest_rm(replica, leaver_id) == RM.CLOSED
        assert _status_history(replica, leaver_id) == _status_history(
            manager, leaver_id
        )
        own_steps = set(_ledger_rm_steps(manager, leaver_id))
        assert sent[0].semantic_type == "close_case"
        assert {e.log_object_id for e in sent[1:]} == own_steps
        last_sent = sent[-1].log_index
        assert _case_ledger(manager)[-1].log_index >= last_sent
        if leaver_id == OWNER_ID:
            # The CASE_MANAGER's steps and the boundary follow, unsent.
            assert "case_fully_closed" not in {e.semantic_type for e in sent}
            assert _case_ledger(manager)[-1].log_index > last_sent

    @pytest.mark.spec("CM-23-004")
    def test_an_earlier_leaver_is_sent_nothing_of_the_owner_close(self):
        """A participant that left first receives no entry of the owner close."""
        manager = _make_full_dl()
        _close(manager, VENDOR_ID, "https://example.org/activities/leave-v")
        sync_port = MagicMock(spec=SyncActivityPort)

        CloseCaseReceivedUseCase(
            dl=manager,
            request=_make_close_case_event(
                sender_actor_id=OWNER_ID,
                activity_id="https://example.org/activities/leave-o",
            ),
            sync_port=sync_port,
            wire_render_port=As2WireRenderAdapter(),
            trigger_activity=TriggerActivityAdapter(manager),
        ).execute()

        sent = _announced(sync_port)
        assert _case_ledger(manager)[-1].semantic_type == "case_fully_closed"
        # Every participant is closed by then, so the boundary goes to nobody.
        assert "case_fully_closed" not in {e.semantic_type for e, _ in sent}
        assert all(VENDOR_ID not in to for _, to in sent), [
            (e.semantic_type, to) for e, to in sent
        ]

    @pytest.mark.spec("CM-23-001")
    @pytest.mark.spec("CM-23-016")
    def test_close_case_entry_alone_changes_no_rm_state(self):
        """Applying only the close_case entry leaves every RM state as it was."""
        dl = _make_full_dl(store_owner_id=VENDOR_ID)
        _seed_rm(dl, OWNER_ID, RM.VALID)
        before = {a: _status_history(dl, a) for a in (OWNER_ID, VENDOR_ID)}
        entry = _make_close_case_ledger_entry(dl, departing_actor_id=OWNER_ID)

        BTBridge(
            datalayer=dl, wire_render_port=As2WireRenderAdapter()
        ).execute_with_setup(
            tree=create_announce_log_entry_tree(
                sender_rule=AnnounceLedgerEntryReceivedUseCase.sender_entitlement
            ),
            actor_id=VENDOR_ID,
            activity=_make_announce_event(
                entry=entry, sender_actor_id=CASE_ACTOR_ID
            ),
            sync_port=MagicMock(spec=SyncActivityPort),
        )

        assert dl.read(entry.id_) is not None, "the entry is still stored"
        after = {a: _status_history(dl, a) for a in (OWNER_ID, VENDOR_ID)}
        assert after == before, (
            "a close_case entry must change no participant's RM state"
            " (CM-23-001)"
        )

    @pytest.mark.spec("CM-23-001")
    @pytest.mark.spec("CM-23-012")
    @pytest.mark.spec("CM-23-016")
    @pytest.mark.spec("RMB-14-005")
    @pytest.mark.parametrize(
        "leaver_id", [OWNER_ID, VENDOR_ID], ids=["owner", "non-owner"]
    )
    @pytest.mark.parametrize(
        "source",
        [None, RM.RECEIVED, RM.ACCEPTED, RM.VALID],
        ids=["START", "RECEIVED", "ACCEPTED", "VALID"],
    )
    def test_replica_history_equals_the_case_managers(
        self, leaver_id: str, source: RM | None
    ):
        """Every closure step the CASE_MANAGER wrote reaches the replica.

        The replica's per-actor status history ends identical to the
        CASE_MANAGER's, status ids included, for every closing actor: a Leave
        from Valid is V → D → C and from Start S → R → C on both (AC-3).
        """
        manager = _make_full_dl()
        if source is not None:
            _seed_rm(manager, leaver_id, source)
        replica = _replica_of(manager)
        _close(manager, leaver_id, "https://example.org/activities/leave")

        _replay(manager, replica)

        closing = [leaver_id] + (
            [CASE_ACTOR_ID] if leaver_id == OWNER_ID else []
        )
        for actor_id in closing:
            assert _status_history(replica, actor_id) == _status_history(
                manager, actor_id
            ), actor_id

    @pytest.mark.spec("CM-23-001")
    @pytest.mark.spec("RSH-09-006")
    def test_replica_refusing_a_step_writes_no_step_of_its_own(
        self, monkeypatch, caplog
    ):
        """A refused step entry is logged and the replica invents nothing.

        The replica's participant-status effect refuses the CLOSED entry (a
        stand-in for an impossible composite state, RSH-09-006).  It logs a
        WARNING, keeps the steps it did apply, and writes no CLOSED of its
        own: nothing else on the ledger moves the leaver (CM-23-001).
        """
        from types import SimpleNamespace

        from vultron.core.behaviors.sync.nodes import participant_status_effect

        manager = _make_full_dl()
        _seed_rm(manager, VENDOR_ID, RM.VALID)
        replica = _replica_of(manager)
        before = _status_history(replica, VENDOR_ID)
        _close(manager, VENDOR_ID, "https://example.org/activities/leave")
        monkeypatch.setattr(
            participant_status_effect,
            "composite_state_violations",
            lambda rm, _vf, _d: (
                [SimpleNamespace(message="refused for the test")]
                if rm is RM.CLOSED
                else []
            ),
        )

        with caplog.at_level(logging.WARNING):
            for entry in _case_ledger(manager):
                BTBridge(
                    datalayer=replica, wire_render_port=As2WireRenderAdapter()
                ).execute_with_setup(
                    tree=create_announce_log_entry_tree(
                        sender_rule=AnnounceLedgerEntryReceivedUseCase.sender_entitlement
                    ),
                    actor_id=VENDOR_ID,
                    activity=_make_announce_event(
                        entry=entry, sender_actor_id=CASE_ACTOR_ID
                    ),
                    sync_port=MagicMock(spec=SyncActivityPort),
                )

        added = [rm for _id, rm in _status_history(replica, VENDOR_ID)][
            len(before) :
        ]
        assert added == [RM.DEFERRED], added
        assert any(
            "impossible composite state" in r.getMessage()
            and r.levelno == logging.WARNING
            for r in caplog.records
        )

    @pytest.mark.spec("CM-23-016")
    @pytest.mark.spec("CM-23-001")
    def test_lagging_replica_writes_no_step_the_ledger_lacks(self):
        """The #4091 case: the replica still has the leaver at VALID.

        The CASE_MANAGER has the leaver at DEFERRED, so it writes and records
        only D → C.  A replica holding the older VALID status applies that one
        entry: it ends at CLOSED with no DEFERRED step of its own, where a
        table walk from its own view would have written V → D → C.
        """
        manager = _make_full_dl()
        _seed_rm(manager, VENDOR_ID, RM.VALID)
        replica = _replica_of(manager)
        _seed_rm(manager, VENDOR_ID, RM.DEFERRED)
        before = _status_history(replica, VENDOR_ID)
        _close(manager, VENDOR_ID, "https://example.org/activities/leave")

        _replay(manager, replica)

        after = _status_history(replica, VENDOR_ID)
        assert after[: len(before)] == before
        added = after[len(before) :]
        assert [status_id for status_id, _rm in added] == _ledger_rm_steps(
            manager, VENDOR_ID
        )
        assert [rm for _id, rm in added] == [RM.CLOSED], (
            "the replica must write only the step the ledger records,"
            f" not a DEFERRED of its own (#4091); got {added}"
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
            trigger_activity=TriggerActivityAdapter(dl),
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
            trigger_activity=TriggerActivityAdapter(dl),
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
            trigger_activity=TriggerActivityAdapter(dl),
            request=_make_close_case_event(sender_actor_id=VENDOR_ID),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        after = _participant_rm_states(dl, VENDOR_ID)
        assert after == [*before, RM.RECEIVED, RM.CLOSED], after

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
            trigger_activity=TriggerActivityAdapter(dl),
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
            trigger_activity=TriggerActivityAdapter(dl),
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

        tree = create_announce_log_entry_tree(
            sender_rule=AnnounceLedgerEntryReceivedUseCase.sender_entitlement
        )
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
    write_consent_rows(dl, case)


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
        and getattr(obj, "semantic_type", None) == "case_fully_closed"
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
    @pytest.mark.spec("CLP-05-001")
    def test_owner_leave_during_embargo_emits_reject_to_owner(self):
        """The decline is surfaced as an as:Reject of the Leave, addressed back
        to the owner (AC-2, MSM-05-001).

        The decline is the refusal's answer: the close arm adds no refusal
        notice, so exactly one Reject is queued (CLP-05-001, #4756)."""
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
        emitted a ``Reject(Leave)``; it must now emit nothing.  The replica's
        sender guard admits only the CASE_MANAGER, so it refuses this copy
        before the gate; the gate itself is pinned by
        ``test_non_manager_replica_refuses_a_leave_from_the_case_manager``.
        """
        dl = _make_full_dl(store_owner_id=VENDOR_ID)
        _seed_active_embargo(dl, em_state=EM.ACTIVE)

        result = CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(
                sender_actor_id=OWNER_ID, receiving_actor_id=VENDOR_ID
            ),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.REFUSED
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

    @pytest.mark.spec("HP-01-005")
    def test_non_manager_replica_refuses_a_leave_from_the_case_manager(self):
        """A Leave the sender guard admits at a replica is still refused.

        The Case Owner's Leave above never reaches the gate: the replica's
        sender guard admits only the CASE_MANAGER.  A Leave from the
        CASE_MANAGER passes that guard, and the gated close-or-decline step
        then does nothing at a replica, so the replica reports the
        misaddressed Leave as a refusal, never as applied (HP-01-005).
        """
        dl = _make_full_dl(store_owner_id=VENDOR_ID)
        rm_before = _participant_rm_states(dl, CASE_ACTOR_ID)

        result = CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(
                sender_actor_id=CASE_ACTOR_ID, receiving_actor_id=VENDOR_ID
            ),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None
        assert "not the CASE_MANAGER" in result.reason
        assert dl.outbox_list() == []
        assert dl.list_objects("CaseLedgerEntry") == []
        assert _participant_rm_states(dl, CASE_ACTOR_ID) == rm_before


def _case_actor_rm_entry_states(dl: SqliteDataLayer) -> list[RM]:
    """Return the CaseActor's RM states as recorded on the ledger, in order."""
    entries = sorted(
        (
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry)
            and e.case_id == CASE_ID
            and e.semantic_type == "add_participant_status_to_participant"
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
        and getattr(e, "semantic_type", None)
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


class TestCaseActorRMClosedRecordingFailsClosed:
    """The CaseActor's own RM.CLOSED is not written unless it is recorded.

    ``CommitRMClosureEntriesNode`` sits between CM-23-002 step 2 (advance the
    CASE_MANAGER) and step 3 (``case_fully_closed``).  A step whose entry does
    not commit fails the node and the act, which keeps none of the closure,
    so the CASE_MANAGER's store never holds a closure its ledger lacks
    (CLP-07-013, CLP-07-015).  The owner arm stops before
    ``case_fully_closed``, and the non-owner arm's own role check keeps the
    enclosing Selector from closing the owner as an ordinary leaver.
    """

    @staticmethod
    def _fail_case_actor_commits(monkeypatch, dl: SqliteDataLayer) -> None:
        """Fail only the commits of the CaseActor's own closure steps."""
        from vultron.core.behaviors.case.nodes.participant import (
            status_entries,
        )

        def _case_actors(kwargs: dict) -> bool:
            status = dl.read(kwargs["object_id"])
            return (
                isinstance(status, ParticipantStatus)
                and status.attributed_to == CASE_ACTOR_ID
            )

        fail_commits(monkeypatch, status_entries, when=_case_actors)

    @pytest.fixture
    def rm_closed_node_without_port(self, monkeypatch):
        """Blind only the RM closure recording nodes to the trigger port."""
        from vultron.core.behaviors.case.nodes.leave.record import (
            CommitRMClosureEntriesNode,
        )

        original = CommitRMClosureEntriesNode.initialise

        def _initialise_without_port(node) -> None:
            original(node)
            node.trigger_activity_factory = None

        monkeypatch.setattr(
            CommitRMClosureEntriesNode,
            "initialise",
            _initialise_without_port,
        )

    @pytest.mark.spec("CM-23-005")
    @pytest.mark.spec("CLP-07-013")
    def test_failed_commit_leaves_the_case_actor_unchanged(self, monkeypatch):
        """AC-3: the CaseActor's record is as it was, and the case stays open."""
        dl = _make_full_dl()
        before = _case_file(dl, CASE_ACTOR_ID)
        self._fail_case_actor_commits(monkeypatch, dl)

        result = _close(
            dl, OWNER_ID, "https://example.org/activities/leave-owner"
        )

        assert result.disposition != HandlerDisposition.APPLIED, (
            "a closure the ledger cannot record is not reported as applied"
        )
        assert "could not commit" in (result.reason or ""), (
            "the verdict names the failed commit, not the role check"
            f" (got {result.reason!r})"
        )
        assert _case_file(dl, CASE_ACTOR_ID) == before
        assert RM.CLOSED not in _participant_rm_states(dl, CASE_ACTOR_ID)
        assert not _case_actor_rm_closed_entries(dl)
        assert not _case_fully_closed_present(dl), (
            "the owner arm stops before case_fully_closed (CM-23-002)"
        )

    @pytest.mark.spec("CM-23-005")
    @pytest.mark.spec("CLP-07-015")
    def test_failed_commit_keeps_none_of_the_owners_steps(self, monkeypatch):
        """The owner's steps and the CaseActor's are one act: none stays."""
        dl = _make_full_dl()
        self._fail_case_actor_commits(monkeypatch, dl)

        _close(dl, OWNER_ID, "https://example.org/activities/leave-owner")

        assert _latest_rm(dl, OWNER_ID) != RM.CLOSED
        assert not _ledger_rm_steps(dl, OWNER_ID)
        assert _case_ledger(dl) == []

    @pytest.mark.spec("CM-23-002")
    def test_a_redelivered_owner_leave_completes_the_closure(
        self, monkeypatch
    ):
        """The failed closure heals on redelivery, through the owner arm."""
        dl = _make_full_dl()
        with monkeypatch.context() as patch:
            self._fail_case_actor_commits(patch, dl)
            _close(dl, OWNER_ID, "https://example.org/activities/leave-owner")

        result = _redeliver_close(
            dl, "https://example.org/activities/leave-owner"
        )

        assert result.disposition == HandlerDisposition.APPLIED
        assert _case_actor_rm_closed_entries(dl)
        assert _case_fully_closed_present(dl)

    @pytest.mark.spec("CM-23-002")
    @pytest.mark.spec("CM-23-018")
    def test_a_closed_owners_leave_closes_the_open_case(self):
        """A Case Owner whose own closure is recorded on a case that is not
        fully closed is not repeating its Leave: the Leave closes the case
        (CM-23-018 exception), committing only the steps still owed."""
        dl = _make_full_dl()
        _seed_rm(dl, OWNER_ID, RM.CLOSED)

        result = _close(
            dl, OWNER_ID, "https://example.org/activities/leave-owner"
        )

        assert result.disposition == HandlerDisposition.APPLIED
        assert not _ledger_rm_steps(dl, OWNER_ID), (
            "the owner already holds RM.CLOSED, so no step of its is owed"
        )
        assert _case_actor_rm_closed_entries(dl)
        assert _case_fully_closed_present(dl)

    @pytest.mark.spec("CM-23-005")
    @pytest.mark.spec("ARCH-15-001")
    def test_missing_port_raises_and_writes_nothing(
        self, rm_closed_node_without_port
    ):
        """No TriggerActivityPort is a wiring fault: raise, keep no step."""
        dl = _make_full_dl()
        before = _case_file(dl, OWNER_ID)

        with pytest.raises(VultronBTInternalError):
            _close(dl, OWNER_ID, "https://example.org/activities/leave-owner")

        assert _case_file(dl, OWNER_ID) == before
        assert not _case_fully_closed_present(dl)


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
    @pytest.mark.spec("VP-17-001")
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
            trigger_activity=TriggerActivityAdapter(dl),
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
            trigger_activity=TriggerActivityAdapter(dl),
            request=_make_close_case_event(sender_actor_id=OWNER_ID),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert _case_actor_rm_closed_entries(dl), (
            "the CASE_MANAGER must still record its own RM.CLOSED (CM-23-005)"
            " — the role gate must not suppress the entry it exists to protect"
        )
