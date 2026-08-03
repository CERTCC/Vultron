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

import pytest
import py_trees

from unittest.mock import MagicMock

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sync.announce_tree import (
    create_announce_log_entry_tree,
)
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.events.case import CloseCaseReceivedEvent
from vultron.core.models.events.sync import AnnounceLogEntryReceivedEvent
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.states.rm import RM
from vultron.core.use_cases.received.case.lifecycle import (
    CloseCaseReceivedUseCase,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
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


@pytest.fixture(autouse=True)
def _clear_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


def _make_dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:")


def _make_full_dl(
    owner_id: str = OWNER_ID,
    extra_participant_id: str | None = VENDOR_ID,
) -> SqliteDataLayer:
    """DataLayer as seen by the CaseActor, with all participants set up.

    Participants:
    - CaseActor: CASE_MANAGER role
    - owner_id: CASE_OWNER role
    - extra_participant_id (optional): VENDOR role
    """
    dl = _make_dl()

    ca_svc = VultronCaseActor(id_=CASE_ACTOR_ID, context=CASE_ID)
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
) -> CloseCaseReceivedEvent:
    case_obj = as_VulnerabilityCase(id_=CASE_ID)
    activity = VultronActivity(
        id_="https://example.org/activities/leave-role-test",
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


class TestOwnerLeaveReceivePath:
    """CM-23-002: Owner Leave advances leaving participant + CaseActor to RM.CLOSED."""

    def test_owner_leave_advances_owner_to_rm_closed(self):
        """Owner Leave: the leaving owner actor is advanced to RM.CLOSED."""
        dl = _make_full_dl()
        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=OWNER_ID),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        rm_states = _participant_rm_states(dl, OWNER_ID)
        assert RM.CLOSED in rm_states, (
            f"Owner participant must be at RM.CLOSED after owner Leave;"
            f" rm_states={rm_states}"
        )

    def test_owner_leave_advances_case_actor_to_rm_closed(self):
        """Owner Leave: the CaseActor is also advanced to RM.CLOSED (CM-23-002 step 2)."""
        dl = _make_full_dl()
        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=OWNER_ID),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        rm_states = _participant_rm_states(dl, CASE_ACTOR_ID)
        assert RM.CLOSED in rm_states, (
            f"CaseActor must be at RM.CLOSED after owner Leave (CM-23-002);"
            f" rm_states={rm_states}"
        )

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
        ).execute()

        rm_states = _participant_rm_states(dl, VENDOR_ID)
        assert RM.CLOSED not in rm_states, (
            f"Vendor participant must NOT be at RM.CLOSED after owner Leave"
            f" — fan-out handles that; rm_states={rm_states}"
        )


class TestNonOwnerLeaveReceivePath:
    """CM-23-003: Non-owner Leave advances only the leaving participant."""

    def test_non_owner_leave_advances_only_leaving_participant(self):
        """Non-owner Leave: the leaving vendor actor is advanced to RM.CLOSED."""
        dl = _make_full_dl()
        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=VENDOR_ID),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        rm_states = _participant_rm_states(dl, VENDOR_ID)
        assert RM.CLOSED in rm_states, (
            f"Non-owner leaving participant must be at RM.CLOSED (CM-23-003);"
            f" rm_states={rm_states}"
        )

    def test_non_owner_leave_does_not_close_owner(self):
        """Non-owner Leave: the case owner remains open (CM-23-003)."""
        dl = _make_full_dl()
        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=VENDOR_ID),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        rm_states = _participant_rm_states(dl, OWNER_ID)
        assert RM.CLOSED not in rm_states, (
            f"Owner participant must NOT be at RM.CLOSED after non-owner Leave;"
            f" rm_states={rm_states}"
        )

    def test_non_owner_leave_does_not_close_case_actor(self):
        """Non-owner Leave: the CaseActor remains open (CM-23-003)."""
        dl = _make_full_dl()
        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(sender_actor_id=VENDOR_ID),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        rm_states = _participant_rm_states(dl, CASE_ACTOR_ID)
        assert RM.CLOSED not in rm_states, (
            f"CaseActor must NOT be at RM.CLOSED after non-owner Leave;"
            f" rm_states={rm_states}"
        )


# ---------------------------------------------------------------------------
# Fan-out path (ApplyCloseCaseFromLedgerNode via announce tree)
# ---------------------------------------------------------------------------


def _make_close_case_ledger_entry(
    dl: SqliteDataLayer,
    departing_actor_id: str,
) -> VultronCaseLedgerEntry:
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
    entry: VultronCaseLedgerEntry,
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
        dl = _make_full_dl()
        entry = _make_close_case_ledger_entry(dl, departing_actor_id=OWNER_ID)

        event = _make_announce_event(
            entry=entry, sender_actor_id=CASE_ACTOR_ID
        )

        tree = create_announce_log_entry_tree()
        BTBridge(datalayer=dl).execute_with_setup(
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
        dl = _make_full_dl()
        entry = _make_close_case_ledger_entry(dl, departing_actor_id=OWNER_ID)

        event = _make_announce_event(
            entry=entry, sender_actor_id=CASE_ACTOR_ID
        )

        tree = create_announce_log_entry_tree()
        BTBridge(datalayer=dl).execute_with_setup(
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
