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

"""AC-5 end-to-end round-trip tests for Leave(VulnerabilityCase).

Tests the full path:
  Leave emitted (SvcLeaveCaseUseCase)
  → ledger entry committed (CloseCaseReceivedUseCase on Case Actor)
  → RM.CLOSED applied on each replica

Two SqliteDataLayer replicas are used: the leaving actor's local DL and
the Case Actor's local DL.  The test drives the BT directly via
CloseCaseReceivedUseCase rather than HTTP delivery, which gives a
deterministic round-trip without network noise.

Per specs/case-management.yaml CM-23-002, CM-23-003, ADR-0050.
"""

from __future__ import annotations

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.events.case import CloseCaseReceivedEvent
from vultron.core.states.rm import RM
from vultron.core.use_cases.received.case.lifecycle import (
    CloseCaseReceivedUseCase,
)
from vultron.core.use_cases.triggers.case import (
    LeaveCaseTriggerRequest,
    SvcLeaveCaseUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import (
    as_ParticipantStatus as WireParticipantStatus,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CASE_ACTOR_URL = "https://example.org/actors/case-actor-rt"
VENDOR_URL = "https://example.org/actors/vendor-rt"
FINDER_URL = "https://example.org/actors/finder-rt"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_actor_dl(url: str) -> tuple[as_Service, SqliteDataLayer]:
    actor = as_Service(name=url.split("/")[-1], url=url)
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor.id_)
    dl.clear_all()
    dl.create(actor)
    return actor, dl


def _seed_case(
    dl: SqliteDataLayer,
    case_id: str,
    actor_id: str,
    role: CVDRole,
    case_actor_id: str,
) -> tuple[as_VulnerabilityCase, as_CaseParticipant]:
    """Seed a VulnerabilityCase with one participant + a CASE_MANAGER.

    Returns the case and the seeded participant for ``actor_id``.
    """
    case = as_VulnerabilityCase(
        id_=case_id, name="Round-Trip Test Case", attributed_to=case_actor_id
    )

    participant = as_CaseParticipant(
        attributed_to=actor_id,
        context=case_id,
        case_roles=[role],
    )
    participant.participant_statuses.append(
        WireParticipantStatus(context=case_id, rm_state=RM.RECEIVED)
    )
    participant.participant_statuses.append(
        WireParticipantStatus(context=case_id, rm_state=RM.VALID)
    )
    participant.participant_statuses.append(
        WireParticipantStatus(context=case_id, rm_state=RM.ACCEPTED)
    )
    dl.create(participant)
    case.actor_participant_index[actor_id] = participant.id_
    case.case_participants.append(participant.id_)

    cm_participant = as_CaseParticipant(
        attributed_to=case_actor_id,
        context=case_id,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    # Bootstrap CaseActor with 3 statuses + RM.CLOSED so AllParticipantsRMClosed
    # can succeed after owner Leave (ADR-0051, CM-23-005).
    for state in [RM.RECEIVED, RM.VALID, RM.ACCEPTED, RM.CLOSED]:
        cm_participant.participant_statuses.append(
            WireParticipantStatus(context=case_id, rm_state=state)
        )
    dl.create(cm_participant)
    case.actor_participant_index[case_actor_id] = cm_participant.id_
    case.case_participants.append(cm_participant.id_)

    dl.save(case)
    return case, participant


def _participant_rm_states(
    dl: SqliteDataLayer, case_id: str, actor_id: str
) -> list[RM]:
    case = dl.read(case_id)
    if not isinstance(case, VulnerabilityCase):
        return []
    pid = case.actor_participant_index.get(actor_id)
    if pid is None:
        return []
    participant = dl.read(pid)
    if not isinstance(participant, CaseParticipant):
        return []
    return [
        ps.rm.state
        for ps in participant.participant_statuses
        if hasattr(ps, "rm") and ps.rm is not None
    ]


def _make_close_case_event(
    activity_id: str,
    sender_actor_id: str,
    case_id: str,
    receiving_actor_id: str,
) -> CloseCaseReceivedEvent:
    activity = VultronActivity(
        id_=activity_id,
        type_="Leave",
        actor=sender_actor_id,
        object_=as_VulnerabilityCase(id_=case_id),
    )
    return CloseCaseReceivedEvent(
        semantic_type=MessageSemantics.CLOSE_CASE,
        activity_id=activity.id_,
        actor_id=sender_actor_id,
        object_=activity.object_,
        activity=activity,
        receiving_actor_id=receiving_actor_id,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def vendor_and_dl():
    actor, dl = _make_actor_dl(VENDOR_URL)
    yield actor, dl
    dl.close()


@pytest.fixture
def case_actor_and_dl():
    actor, dl = _make_actor_dl(CASE_ACTOR_URL)
    yield actor, dl
    dl.close()


# ---------------------------------------------------------------------------
# Round-trip tests
# ---------------------------------------------------------------------------


class TestLeaveCaseRoundTrip:
    """AC-5: end-to-end Leave → ledger → RM.CLOSED across two replicas."""

    def test_non_owner_leave_emitted_then_received_sets_rm_closed(
        self,
        vendor_and_dl: tuple[as_Service, SqliteDataLayer],
        case_actor_and_dl: tuple[as_Service, SqliteDataLayer],
    ):
        """Non-owner Leave round-trip: RM.CLOSED applied after ledger receipt (CM-23-003).

        Step 1: SvcLeaveCaseUseCase queues Leave in the vendor's outbox.
        Step 2: CloseCaseReceivedUseCase processes it on the Case Actor's DL.
        Step 3: vendor's RM state on the Case Actor's DL is RM.CLOSED.
        """
        vendor, vendor_dl = vendor_and_dl
        case_actor, ca_dl = case_actor_and_dl

        case, _ = _seed_case(
            vendor_dl,
            case_id="https://example.org/cases/rt-non-owner",
            actor_id=vendor.id_,
            role=CVDRole.VENDOR,
            case_actor_id=case_actor.id_,
        )
        # Mirror case on Case Actor's DL
        _seed_case(
            ca_dl,
            case_id=case.id_,
            actor_id=vendor.id_,
            role=CVDRole.VENDOR,
            case_actor_id=case_actor.id_,
        )

        # Step 1: vendor triggers Leave
        request = LeaveCaseTriggerRequest(
            actor_id=vendor.id_,
            case_id=case.id_,
        )
        before = set(vendor_dl.outbox_list_for_actor(vendor.id_))
        SvcLeaveCaseUseCase(
            vendor_dl,
            request,
            trigger_activity=TriggerActivityAdapter(vendor_dl),
        ).execute()
        after = set(vendor_dl.outbox_list_for_actor(vendor.id_))
        assert after - before, "Leave must be queued in vendor outbox"

        # AC-2: vendor RM is NOT closed immediately at send time
        assert RM.CLOSED not in _participant_rm_states(
            vendor_dl, case.id_, vendor.id_
        ), "RM.CLOSED must not be set at send time (AC-2)"

        # Step 2: Case Actor receives the Leave
        event = _make_close_case_event(
            activity_id="https://example.org/activities/leave-rt-non-owner",
            sender_actor_id=vendor.id_,
            case_id=case.id_,
            receiving_actor_id=case_actor.id_,
        )
        CloseCaseReceivedUseCase(
            dl=ca_dl,
            request=event,
            sync_port=SyncActivityAdapter(ca_dl),
        ).execute()

        # Step 3: vendor is RM.CLOSED on Case Actor replica (CM-23-003)
        rm_states = _participant_rm_states(ca_dl, case.id_, vendor.id_)
        assert RM.CLOSED in rm_states, (
            f"Non-owner Leave must advance vendor to RM.CLOSED on Case Actor replica;"
            f" rm_states={rm_states}"
        )

    def test_ghost_protection_leave_emitted_but_never_delivered(
        self,
        vendor_and_dl: tuple[as_Service, SqliteDataLayer],
        case_actor_and_dl: tuple[as_Service, SqliteDataLayer],
    ):
        """Lost Leave must NOT result in RM.CLOSED — ghosting protection (AC-2).

        The vendor emits Leave, but the message never reaches the Case Actor.
        Both replicas must remain at RM.ACCEPTED, not RM.CLOSED.
        """
        vendor, vendor_dl = vendor_and_dl
        case_actor, ca_dl = case_actor_and_dl

        case, _ = _seed_case(
            vendor_dl,
            case_id="https://example.org/cases/rt-ghost",
            actor_id=vendor.id_,
            role=CVDRole.VENDOR,
            case_actor_id=case_actor.id_,
        )
        _seed_case(
            ca_dl,
            case_id=case.id_,
            actor_id=vendor.id_,
            role=CVDRole.VENDOR,
            case_actor_id=case_actor.id_,
        )

        # Vendor emits Leave — message is lost, never delivered
        request = LeaveCaseTriggerRequest(
            actor_id=vendor.id_,
            case_id=case.id_,
        )
        SvcLeaveCaseUseCase(
            vendor_dl,
            request,
            trigger_activity=TriggerActivityAdapter(vendor_dl),
        ).execute()

        # Neither replica must be at RM.CLOSED
        vendor_rm = _participant_rm_states(vendor_dl, case.id_, vendor.id_)
        assert RM.CLOSED not in vendor_rm, (
            f"Lost Leave must NOT set RM.CLOSED on vendor replica;"
            f" rm_states={vendor_rm}"
        )
        ca_rm = _participant_rm_states(ca_dl, case.id_, vendor.id_)
        assert RM.CLOSED not in ca_rm, (
            f"Lost Leave must NOT set RM.CLOSED on Case Actor replica;"
            f" rm_states={ca_rm}"
        )

    def test_owner_leave_closes_case_actor_rm(
        self,
        vendor_and_dl: tuple[as_Service, SqliteDataLayer],
        case_actor_and_dl: tuple[as_Service, SqliteDataLayer],
    ):
        """Owner Leave round-trip: CaseActor advances to RM.CLOSED (CM-23-002 step 2)."""
        vendor, vendor_dl = vendor_and_dl
        case_actor, ca_dl = case_actor_and_dl
        case_id = "https://example.org/cases/rt-owner"

        case, _ = _seed_case(
            vendor_dl,
            case_id=case_id,
            actor_id=vendor.id_,
            role=CVDRole.CASE_OWNER,
            case_actor_id=case_actor.id_,
        )
        _seed_case(
            ca_dl,
            case_id=case_id,
            actor_id=vendor.id_,
            role=CVDRole.CASE_OWNER,
            case_actor_id=case_actor.id_,
        )

        event = _make_close_case_event(
            activity_id="https://example.org/activities/owner-leave-rt",
            sender_actor_id=vendor.id_,
            case_id=case_id,
            receiving_actor_id=case_actor.id_,
        )
        CloseCaseReceivedUseCase(
            dl=ca_dl,
            request=event,
            sync_port=SyncActivityAdapter(ca_dl),
        ).execute()

        owner_rm = _participant_rm_states(ca_dl, case_id, vendor.id_)
        assert RM.CLOSED in owner_rm, (
            f"Owner Leave must advance owner to RM.CLOSED (CM-23-002);"
            f" rm_states={owner_rm}"
        )
        ca_rm = _participant_rm_states(ca_dl, case_id, case_actor.id_)
        assert RM.CLOSED in ca_rm, (
            f"Owner Leave must advance CaseActor to RM.CLOSED (CM-23-002 step 2);"
            f" rm_states={ca_rm}"
        )
