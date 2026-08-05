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

"""Finder → C1 (CASE_OWNER, Coordinator) + C2 (Coordinator) + Vendor (FCCV-extension) demo.

Orchestrates the full CVD lifecycle across four actor containers plus a
dedicated CaseActor:
  - Finder: the report submitter
  - C1 (coordinator container): CASE_OWNER throughout; receives the report
    and retains ownership
  - C2 (actor5 container, Coordinator2): participant with CVDRole.COORDINATOR;
    NOT CASE_MANAGER; C2 suggests Vendor via the ADR-0026 suggest-actor flow
  - Vendor (vendor container): joins via C1 approval; holds the VFD fix path
  - CaseActor (case-actor container): manages the canonical case ledger

Container mapping (reuses docker-compose-multi-actor.yml services):
  VULTRON_FINDER_BASE_URL       → Finder container
  VULTRON_COORDINATOR_BASE_URL  → C1 container (coordinator)
  VULTRON_VENDOR2_BASE_URL      → C2 container (actor5 seeded as coordinator2)
  VULTRON_VENDOR_BASE_URL       → Vendor container

Spec: DEMOMA-13 (GitHub issue #1620).
"""

import json
import logging
import os
import pathlib
import sys

import httpx2 as httpx

from vultron.adapters.utils import strip_id_prefix
from vultron.core.states.cs import CS_vfd
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_TransitiveActivity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

from vultron.demo.utils import (  # noqa: F401 — re-exported for test monkeypatching
    DataLayerClient,
    assert_demo_success,
    check_server_availability,
    demo_check,
    demo_step,
    post_to_inbox_and_wait,
    post_to_trigger,
    reset_datalayer,
    reset_demo_failures,
    setup_demo_logging,
    verify_object_stored,
)
from vultron.demo.helpers.actions import (
    actor_closes_case,
    actor_notifies_fix_ready,
    actor_notifies_published,
)
from vultron.demo.helpers.milestones import (
    verify_case_active,
    verify_case_closed,
    verify_publicly_disclosed,
)
from vultron.demo.helpers.verification import _check_participant_vfd_state_in
from vultron.demo.helpers.notes import participant_adds_note_to_case
from vultron.demo.helpers.polling import (
    find_case_actor_participant_id,
    find_case_invite_for_actor,
    find_cp_offer_for_case,
    wait_for_all_participants_rm_closed,
    wait_for_case_em_terminated,
    wait_for_case_on_container,
    wait_for_case_participants,
    wait_for_contiguous_ledger_coverage,
    wait_for_event_type_in_ledger,
    wait_for_participant_vfd_state,
)
from vultron.demo.helpers.seeding import (
    get_actor_by_id,
    reset_containers as _reset_containers,
    seed_containers_fccv,
)
from vultron.demo.helpers.sync import (
    _get_log_entries_for_case,
    verify_replica_state,
)
from vultron.demo.helpers.workflow import (
    find_case_for_offer,
    receiver_engages_case,
    receiver_validates_report,
    reporter_submits_report,
)

logger = logging.getLogger(__name__)

# Default container base URLs.
# C1 uses the docker-compose "coordinator" container; C2 uses "actor5"
# (seeded as coordinator2 for this scenario).  Vendor uses "vendor".
# Override via environment variables.
FINDER_BASE_URL = os.environ.get(
    "VULTRON_FINDER_BASE_URL", "http://localhost:7901/api/v2"
)
C1_BASE_URL = os.environ.get(
    "VULTRON_COORDINATOR_BASE_URL", "http://localhost:7903/api/v2"
)
C2_BASE_URL = os.environ.get(
    "VULTRON_VENDOR2_BASE_URL", "http://localhost:7904/api/v2"
)
VENDOR_BASE_URL = os.environ.get(
    "VULTRON_VENDOR_BASE_URL", "http://localhost:7902/api/v2"
)

# Deterministic actor IDs — match docker-compose-multi-actor.yml service names
# (D5-1-G3) with role remapping for FCCV-extension:
#   coordinator container → C1 (Coordinator1, CASE_OWNER)
#   actor5 container      → C2 (Coordinator2, participant)
#   vendor container      → Vendor
FINDER_ACTOR_ID = "http://finder:7999/api/v2/actors/finder"
C1_ACTOR_ID = "http://coordinator:7999/api/v2/actors/coordinator"
C2_ACTOR_ID = "http://actor5:7999/api/v2/actors/coordinator2"
VENDOR_ACTOR_ID = "http://vendor:7999/api/v2/actors/vendor"


def reset_containers(
    finder_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    vendor_client: DataLayerClient,
) -> None:
    """Reset all four FCCV-extension containers to a clean baseline."""
    targets: list[tuple[str, DataLayerClient]] = [
        ("Finder", finder_client),
        ("C1", c1_client),
        ("C2", c2_client),
        ("Vendor", vendor_client),
    ]
    _reset_containers(targets, reset_fn=reset_datalayer)


# ---------------------------------------------------------------------------
# Polling helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Phase helpers
# ---------------------------------------------------------------------------


def _phase_report_submission(
    finder_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    vendor_client: DataLayerClient,
    finder_id: str | None,
    c1_id: str | None,
    c2_id: str | None,
    vendor_id: str | None,
) -> tuple[
    as_Actor,
    as_Actor,
    as_Actor,
    as_Actor,
    as_Actor,
    as_VulnerabilityCase,
]:
    """Reset, seed, submit report, validate, engage, invite C2, M1 check."""
    logger.info("─" * 80)
    logger.info("Phase 1: Report submission and case activation")
    logger.info("─" * 80)

    reset_containers(
        finder_client=finder_client,
        c1_client=c1_client,
        c2_client=c2_client,
        vendor_client=vendor_client,
    )

    with demo_step("Seeding all four containers with actor records"):
        finder, c1, c2, vendor = seed_containers_fccv(
            finder_client=finder_client,
            c1_client=c1_client,
            c2_client=c2_client,
            vendor_client=vendor_client,
            reporter_actor_id=finder_id,
            c1_actor_id=c1_id,
            c2_actor_id=c2_id,
            vendor_actor_id=vendor_id,
        )

    c1_in_c1 = get_actor_by_id(c1_client, c1.id_)
    c2_in_c2 = get_actor_by_id(c2_client, c2.id_)

    _, offer = reporter_submits_report(
        receiver_client=c1_client,
        reporter=finder,
        receiver=c1_in_c1,
        reporter_client=finder_client,
    )
    receiver_validates_report(
        receiver_client=c1_client,
        receiver=c1_in_c1,
        offer_id=offer.id_,
    )

    with demo_check("as_VulnerabilityCase exists in C1's DataLayer"):
        case = find_case_for_offer(c1_client, offer.id_)
        if case is None:
            raise AssertionError(
                "Expected as_VulnerabilityCase to be created after validate-report"
            )
        logger.info("Case created: %s", case.id_)

    receiver_engages_case(
        receiver_client=c1_client,
        receiver=c1_in_c1,
        case_id=case.id_,
    )

    # Wait for the initial participants (Finder + C1 + CaseActor) before
    # inviting C2.
    wait_for_case_participants(
        vendor_client=c1_client,
        case_id=case.id_,
        expected_count=3,
    )

    # C1 invites C2 with CVDRole.COORDINATOR (not CASE_MANAGER).
    with demo_step("C1 invites C2 with CVDRole.COORDINATOR"):
        invite_result = post_to_trigger(
            client=c1_client,
            actor_id=c1_in_c1.id_,
            behavior="invite-actor-to-case",
            body={
                "case_id": case.id_,
                "invitee_id": c2.id_,
                "roles": ["coordinator"],
            },
        )
    invite = as_TransitiveActivity.model_validate(invite_result["activity"])
    logger.info("C2 invite created: %s", invite.id_)

    # Deliver the invite to C2's inbox.
    with demo_step("Delivering invite to C2's inbox"):
        post_to_inbox_and_wait(c2_client, c2_in_c2.id_, invite)

    with demo_check("C2 invite stored in C2's DataLayer"):
        verify_object_stored(c2_client, invite.id_)

    # C2 accepts the invite.
    with demo_step("C2 accepts the case invitation"):
        post_to_trigger(
            client=c2_client,
            actor_id=c2_in_c2.id_,
            behavior="accept-case-invite",
            body={"invite_id": invite.id_},
        )

    # Wait for C2's container to replicate the case.
    with demo_check("C2's DataLayer received case replica"):
        wait_for_case_on_container(
            client=c2_client,
            case_id=case.id_,
        )

    # 4 participants: Finder + C1 + C2 + CaseActor
    wait_for_case_participants(
        vendor_client=c1_client,
        case_id=case.id_,
        expected_count=4,
    )

    with demo_check(
        "M1: required participants (≥4), EM.ACTIVE, finder + c2 have replicas"
    ):
        verify_case_active(
            receiver_client=c1_client,
            reporter_client=finder_client,
            case_id=case.id_,
            receiver_actor_id=c1.id_,
            reporter_actor_id=finder.id_,
        )

    case = as_VulnerabilityCase.model_validate(
        c1_client.get(f"/datalayer/{case.id_}")
    )
    return (
        finder,
        c1,
        c1_in_c1,
        c2_in_c2,
        vendor,
        case,
    )


def _phase_c2_suggests_vendor(
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    vendor_client: DataLayerClient,
    c1_in_c1: as_Actor,
    c2_in_c2: as_Actor,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """C2 suggests Vendor via ADR-0026; C1 approves; Vendor joins."""
    logger.info("─" * 80)
    logger.info("Phase 2: C2 suggests Vendor → C1 approves → Vendor joins")
    logger.info("─" * 80)

    # Step M3: C2 sends suggest-actor-to-case (Offer(Actor, Case) → CaseActor).
    with demo_step("C2 suggests Vendor to CaseActor"):
        post_to_trigger(
            client=c2_client,
            actor_id=c2_in_c2.id_,
            behavior="suggest-actor-to-case",
            body={
                "case_id": case.id_,
                "suggested_actor_id": vendor.id_,
            },
        )
    logger.info("C2 sent suggest-actor-to-case for Vendor (%s)", vendor.id_)

    # CaseActor processes Offer(Actor, Case) and forwards Offer(CaseParticipant)
    # to C1 (CASE_OWNER).  Poll C1's DataLayer for the offer.
    with demo_check(
        "Offer(CaseParticipant) for Vendor arrived in C1's DataLayer"
    ):
        cp_offer_id = find_cp_offer_for_case(
            client=c1_client,
            case_id=case.id_,
        )
    logger.info("Offer(CaseParticipant) ID: %s", cp_offer_id)

    # Find the CaseActor's participant ID so we can route the Accept back.
    case_actor_id = find_case_actor_participant_id(c1_client, case.id_)
    if case_actor_id is None:
        raise AssertionError(
            "CaseActor participant not found in case — cannot route Accept"
        )
    logger.info("CaseActor participant ID: %s", case_actor_id)

    # Step M4 (ADR-0026 CM-16-006): C1 approves the recommendation.
    with demo_step(
        "C1 approves actor recommendation (accept-actor-recommendation)"
    ):
        post_to_trigger(
            client=c1_client,
            actor_id=c1_in_c1.id_,
            behavior="accept-actor-recommendation",
            body={
                "cp_offer_id": cp_offer_id,
                "case_actor_id": case_actor_id,
            },
        )
    logger.info("C1 sent Accept(Offer(CaseParticipant)) to CaseActor")

    # CaseActor receives Accept → emits Invite(Actor, Case) to Vendor.  Poll
    # Vendor's DataLayer for the arriving Invite, then puppeteer Vendor's accept.
    with demo_check("Vendor received invite from CaseActor (ADR-0026 path)"):
        invite_id = find_case_invite_for_actor(
            client=vendor_client,
            case_id=case.id_,
            invitee_id=vendor.id_,
            timeout_seconds=20.0,
        )
    logger.info("Vendor received CaseActor invite: %s", invite_id)

    with demo_step("Vendor accepts the CaseActor invitation"):
        post_to_trigger(
            client=vendor_client,
            actor_id=vendor_in_vendor.id_,
            behavior="accept-case-invite",
            body={"invite_id": invite_id},
        )
    logger.info("Vendor sent Accept(Invite) to CaseActor")

    # Vendor's replica is seeded by the CaseActor's Announce(VulnerabilityCase)
    # sent in response to the Accept above.
    with demo_check("Vendor's DataLayer received case replica"):
        wait_for_case_on_container(
            client=vendor_client,
            case_id=case.id_,
            timeout_seconds=20.0,
        )
    logger.info(
        "Vendor received case replica via CaseActor Announce (ADR-0026 path)"
    )

    # 5 participants: Finder + C1 + C2 + Vendor + CaseActor
    wait_for_case_participants(
        vendor_client=c1_client,
        case_id=case.id_,
        expected_count=5,
        timeout_seconds=20.0,
    )
    logger.info("✓ M3: Vendor joined case (%d participants)", 5)


def _phase_sync_verification(
    finder_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    vendor_client: DataLayerClient,
    c1: as_Actor,
    finder: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Verify SYNC-2 replication for Finder, C2, and Vendor replicas."""
    logger.info("─" * 80)
    logger.info("Phase 3: Replica synchronization verification")
    logger.info("─" * 80)

    c1_entries = _get_log_entries_for_case(c1_client, case.id_)
    if c1_entries:
        c1_tail = max(c1_entries, key=lambda e: e["log_index"])
        c1_tail_index: int = c1_tail["log_index"]
        c1_tail_hash: str = c1_tail["entry_hash"]
        logger.info(
            "Waiting for replicas to sync C1 tail (hash=%s… index=%d)",
            c1_tail_hash[:16],
            c1_tail_index,
        )
        for replica_client, label in [
            (finder_client, "Finder"),
            (c2_client, "C2"),
            (vendor_client, "Vendor"),
        ]:
            with demo_check(
                f"{label} ledger coverage (sync-verification phase)"
            ):
                wait_for_contiguous_ledger_coverage(
                    client=replica_client,
                    case_id=case.id_,
                    expected_tail_index=c1_tail_index,
                )
            logger.info("  %s ledger synchronized", label)

    for replica_client in (finder_client, c2_client, vendor_client):
        wait_for_case_participants(
            vendor_client=replica_client,
            case_id=case.id_,
            expected_count=5,
        )

    with demo_check("Finder replica matches authoritative C1 state"):
        verify_replica_state(
            auth_client=c1_client,
            replica_client=finder_client,
            case_id=case.id_,
            vendor_actor_id=c1.id_,
            reporter_actor_id=finder.id_,
        )

    with demo_check("Vendor replica matches authoritative C1 state"):
        verify_replica_state(
            auth_client=c1_client,
            replica_client=vendor_client,
            case_id=case.id_,
            vendor_actor_id=c1.id_,
            reporter_actor_id=finder.id_,
        )

    logger.info("✓ M4: All replicas synchronized (SYNC-2 verified)")


def _phase_notes_exchange(
    finder_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    vendor_client: DataLayerClient,
    finder_in_finder: as_Actor,
    c1_in_c1: as_Actor,
    c2_in_c2: as_Actor,
    vendor_in_vendor: as_Actor,
    case: as_VulnerabilityCase,
) -> tuple[as_Note, as_Note, as_Note, as_Note]:
    """Run a four-way note exchange among all participants."""
    logger.info("─" * 80)
    logger.info("Phase 4: Notes exchange")
    logger.info("─" * 80)

    question_note = participant_adds_note_to_case(
        posting_client=finder_client,
        watching_client=c1_client,
        poster=finder_in_finder,
        case=case,
        note_name="Question from Finder",
        note_content=(
            "Is there a workaround available while the patch is being developed?"
        ),
    )

    c1_reply = participant_adds_note_to_case(
        posting_client=c1_client,
        watching_client=c1_client,
        poster=c1_in_c1,
        case=case,
        note_name="C1 Response",
        note_content=(
            "Yes, disabling the affected module is an effective interim workaround."
        ),
        in_reply_to=question_note.id_,
    )

    c2_note = participant_adds_note_to_case(
        posting_client=c2_client,
        watching_client=c1_client,
        poster=c2_in_c2,
        case=case,
        note_name="C2 Update",
        note_content=(
            "We have confirmed that C2 and Vendor are engaged. "
            "Target disclosure in 30 days."
        ),
        in_reply_to=c1_reply.id_,
    )

    vendor_note = participant_adds_note_to_case(
        posting_client=vendor_client,
        watching_client=c1_client,
        poster=vendor_in_vendor,
        case=case,
        note_name="Vendor Status Update",
        note_content=(
            "Vendor can confirm the issue affects our component. "
            "We will align our fix timeline with the 30-day target."
        ),
        in_reply_to=c2_note.id_,
    )

    logger.info(
        "✓ Notes exchange complete (four notes committed to case ledger)"
    )
    return question_note, c1_reply, c2_note, vendor_note


def _phase_fix_lifecycle(
    c1_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Advance Vendor through the fix-ready and fix-deployed path (VFD only)."""
    logger.info("─" * 80)
    logger.info(
        "Phase 5: Fix lifecycle — Vendor: VFd (fix ready); vendor stops at VFd (CSB-15-002)"
    )
    logger.info("─" * 80)

    actor_notifies_fix_ready(
        client=vendor_client,
        actor=vendor_in_vendor,
        case_id=case.id_,
    )

    with demo_check("Vendor participant vfd_state transitions to VFd or VFD"):
        wait_for_participant_vfd_state(
            client=vendor_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vfd.VFd, CS_vfd.VFD},
        )

    with demo_check("M5: C1 replica shows Vendor CS includes F (fix ready)"):
        wait_for_participant_vfd_state(
            client=c1_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vfd.VFd, CS_vfd.VFD},
        )
        _check_participant_vfd_state_in(
            c1_client,
            case.id_,
            vendor.id_,
            {CS_vfd.VFd, CS_vfd.VFD},
            "M5: C1 replica fix ready",
        )
        _check_participant_vfd_state_in(
            vendor_client,
            case.id_,
            vendor.id_,
            {CS_vfd.VFd, CS_vfd.VFD},
            "M5: Vendor replica fix ready",
        )

    with demo_check(
        "M6: C1 replica shows Vendor CS includes F (fix ready) — vendor stops at VFd"
    ):
        wait_for_participant_vfd_state(
            client=c1_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vfd.VFd},
        )
        _check_participant_vfd_state_in(
            c1_client,
            case.id_,
            vendor.id_,
            {CS_vfd.VFd},
            "M6: C1 replica fix ready",
        )
        _check_participant_vfd_state_in(
            vendor_client,
            case.id_,
            vendor.id_,
            {CS_vfd.VFd},
            "M6: Vendor replica fix ready",
        )


def _phase_publication(
    finder_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    vendor_client: DataLayerClient,
    c1: as_Actor,
    c1_in_c1: as_Actor,
    c2_in_c2: as_Actor,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    finder_in_finder: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Run publication notifications and verify public disclosure state."""
    logger.info("─" * 80)
    logger.info(
        "Phase 6: Publication — CS.VFDPxa + embargo teardown (EM.EXITED)"
    )
    logger.info("─" * 80)

    # C1 (CASE_OWNER) triggers CS.P per DEMOMA-13-006 / DEMOMA-07-003(4).
    actor_notifies_published(
        client=c1_client,
        actor=c1_in_c1,
        case_id=case.id_,
    )

    with demo_check(
        "Embargo terminated (EM.EXITED) after C1 reports published"
    ):
        wait_for_case_em_terminated(
            client=c1_client,
            case_id=case.id_,
        )

    actor_notifies_published(
        client=vendor_client,
        actor=vendor_in_vendor,
        case_id=case.id_,
    )
    actor_notifies_published(
        client=c2_client,
        actor=c2_in_c2,
        case_id=case.id_,
    )

    with demo_check(
        "Embargo terminated (EM.EXITED) propagated to Finder before notify-published"
    ):
        wait_for_case_em_terminated(
            client=finder_client,
            case_id=case.id_,
        )

    actor_notifies_published(
        client=finder_client,
        actor=finder_in_finder,
        case_id=case.id_,
    )

    with demo_check(
        "M7: all replicas CS.VFdPxa, EM.EXITED, all participants public-aware"
    ):
        wait_for_case_em_terminated(
            client=finder_client,
            case_id=case.id_,
        )
        wait_for_participant_vfd_state(
            client=c1_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vfd.VFd},
        )
        verify_publicly_disclosed(
            receiver_client=c1_client,
            reporter_client=finder_client,
            case_id=case.id_,
            receiver_actor_id=c1.id_,
        )


def _phase_case_closure(
    finder_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    vendor_client: DataLayerClient,
    c1_in_c1: as_Actor,
    c2_in_c2: as_Actor,
    vendor_in_vendor: as_Actor,
    finder_in_finder: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Close the case from all four participants and verify terminal state."""
    logger.info("─" * 80)
    logger.info("Phase 7: Case closure — all participants RM.CLOSED")
    logger.info("─" * 80)

    actor_closes_case(
        client=c1_client,
        actor=c1_in_c1,
        case_id=case.id_,
    )
    actor_closes_case(
        client=vendor_client,
        actor=vendor_in_vendor,
        case_id=case.id_,
    )
    actor_closes_case(
        client=c2_client,
        actor=c2_in_c2,
        case_id=case.id_,
    )
    actor_closes_case(
        client=finder_client,
        actor=finder_in_finder,
        case_id=case.id_,
    )

    with demo_check("M8: all participants RM.CLOSED on all replicas"):
        wait_for_all_participants_rm_closed(
            client=c1_client,
            case_id=case.id_,
        )
        wait_for_all_participants_rm_closed(
            client=finder_client,
            case_id=case.id_,
        )
        verify_case_closed(
            receiver_client=c1_client,
            reporter_client=finder_client,
            case_id=case.id_,
        )

    with demo_check("close_case entry present on authoritative actor (c1)"):
        wait_for_event_type_in_ledger(
            client=c1_client,
            case_id=case.id_,
            event_type="close_case",
        )
    c1_entries = _get_log_entries_for_case(c1_client, case.id_)
    if c1_entries:
        c1_tail = max(c1_entries, key=lambda e: e["log_index"])
        c1_tail_index: int = c1_tail["log_index"]
        c1_tail_hash: str = c1_tail["entry_hash"]
        logger.info(
            "Waiting for replicas to receive C1 tail after closure"
            " (hash=%s… index=%d)",
            c1_tail_hash[:16],
            c1_tail_index,
        )
        for replica_client, label in [
            (finder_client, "Finder"),
            (c2_client, "C2"),
            (vendor_client, "Vendor"),
        ]:
            with demo_check(f"{label} ledger coverage (close phase)"):
                wait_for_contiguous_ledger_coverage(
                    client=replica_client,
                    case_id=case.id_,
                    expected_tail_index=c1_tail_index,
                )


def _phase_dump_case_ledgers(
    finder_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case: as_VulnerabilityCase,
    demo_name: str = "fccv-extension",
) -> None:
    """Dump case ledger entries from each actor container to JSONL files."""
    logger.info("─" * 80)
    logger.info("Phase: Case log JSONL export")
    logger.info("─" * 80)

    output_root = pathlib.Path(os.environ.get("DEVLOGS_DIR", "/app/devlogs"))
    case_id = case.id_ or ""
    case_id_slug = (
        case_id.replace("://", "_")
        .replace("/", "_")
        .replace(":", "_")
        .strip("_")
    )

    case_actor_sub_actor_key = next(
        (
            strip_id_prefix(actor_id)
            for actor_id in case.actor_participant_index
            if strip_id_prefix(actor_id).startswith("case-actor")
        ),
        None,
    )

    actors: list[tuple[str, DataLayerClient, str]] = [
        ("finder", finder_client, "finder"),
        # C1 is on the coordinator container; route key is "coordinator".
        ("vendor", c1_client, "coordinator"),
        # C2 is on actor5; route key is "coordinator2".
        ("coordinator", c2_client, "coordinator2"),
        # Vendor is on the vendor container.
        ("vendor2", vendor_client, "vendor"),
    ]
    if case_actor_sub_actor_key is not None:
        actors.append(("case-actor", c1_client, case_actor_sub_actor_key))

    for actor_name, client, actor_route_key in actors:
        with demo_step(f"Dumping case ledger for {actor_name}"):
            case_key = strip_id_prefix(case_id)
            log_path = f"/actors/{actor_route_key}/demo/cases/{case_key}/log"
            try:
                entries = client.get_list(log_path)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 404:
                    raise
                logger.info(
                    "Case not found on %s container (HTTP 404); skipping.",
                    actor_name,
                )
                entries = []
            if not entries:
                raise ValueError(
                    f"No case ledger entries for actor={actor_name!r}, "
                    f"case_id={case_id!r}"
                )

            out_dir = output_root / demo_name / actor_name
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / f"{case_id_slug}-case-ledger.jsonl"

            with out_file.open("w", encoding="utf-8") as fh:
                for entry in entries:
                    fh.write(json.dumps(entry) + "\n")

            logger.info("Wrote %d log entries → %s", len(entries), out_file)


def run_fccv_extension_demo(
    finder_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    vendor_client: DataLayerClient,
    finder_id: str | None = None,
    c1_id: str | None = None,
    c2_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Orchestrate the FCCV-extension CVD workflow."""
    logger.info("=" * 80)
    logger.info(
        "FCCV-EXTENSION DEMO: Finder + C1(CASE_OWNER) + C2(COORDINATOR) + Vendor"
    )
    logger.info("=" * 80)
    logger.info("Finder container: %s", finder_client.base_url)
    logger.info("C1 container:     %s", c1_client.base_url)
    logger.info("C2 container:     %s", c2_client.base_url)
    logger.info("Vendor container: %s", vendor_client.base_url)

    (
        finder,
        c1,
        c1_in_c1,
        c2_in_c2,
        vendor,
        case,
    ) = _phase_report_submission(
        finder_client,
        c1_client,
        c2_client,
        vendor_client,
        finder_id,
        c1_id,
        c2_id,
        vendor_id,
    )

    vendor_in_vendor = get_actor_by_id(vendor_client, vendor.id_)

    _phase_c2_suggests_vendor(
        c1_client=c1_client,
        c2_client=c2_client,
        vendor_client=vendor_client,
        c1_in_c1=c1_in_c1,
        c2_in_c2=c2_in_c2,
        vendor=vendor,
        vendor_in_vendor=vendor_in_vendor,
        case=case,
    )

    finder_in_finder = get_actor_by_id(finder_client, finder.id_)

    _phase_sync_verification(
        finder_client,
        c1_client,
        c2_client,
        vendor_client,
        c1,
        finder,
        case,
    )
    _phase_notes_exchange(
        finder_client=finder_client,
        c1_client=c1_client,
        c2_client=c2_client,
        vendor_client=vendor_client,
        finder_in_finder=finder_in_finder,
        c1_in_c1=c1_in_c1,
        c2_in_c2=c2_in_c2,
        vendor_in_vendor=vendor_in_vendor,
        case=case,
    )
    _phase_fix_lifecycle(
        c1_client,
        vendor_client,
        vendor,
        vendor_in_vendor,
        case,
    )
    _phase_publication(
        finder_client,
        c1_client,
        c2_client,
        vendor_client,
        c1,
        c1_in_c1,
        c2_in_c2,
        vendor,
        vendor_in_vendor,
        finder_in_finder,
        case,
    )
    _phase_case_closure(
        finder_client,
        c1_client,
        c2_client,
        vendor_client,
        c1_in_c1,
        c2_in_c2,
        vendor_in_vendor,
        finder_in_finder,
        case,
    )
    _phase_dump_case_ledgers(
        finder_client=finder_client,
        c1_client=c1_client,
        c2_client=c2_client,
        vendor_client=vendor_client,
        case=case,
    )

    logger.info("=" * 80)
    logger.info("FCCV-EXTENSION DEMO COMPLETE ✓  (VFDPxa full lifecycle)")
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(
    skip_health_check: bool = False,
    finder_url: str | None = None,
    c1_url: str | None = None,
    c2_url: str | None = None,
    vendor_url: str | None = None,
    finder_id: str | None = None,
    c1_id: str | None = None,
    c2_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Entry point for the FCCV-extension CVD workflow demo.

    Args:
        skip_health_check: Skip the server availability check.
        finder_url: Override base URL for the Finder container.
        c1_url: Override base URL for the C1 (Coordinator1) container.
        c2_url: Override base URL for the C2 (Coordinator2) container.
        vendor_url: Override base URL for the Vendor container.
        finder_id: Optional deterministic URI for the Finder actor.
        c1_id: Optional deterministic URI for the C1 actor.
        c2_id: Optional deterministic URI for the C2 actor.
        vendor_id: Optional deterministic URI for the Vendor actor.
    """
    reset_demo_failures()

    f_url = finder_url or FINDER_BASE_URL
    c1_resolved = c1_url or C1_BASE_URL
    c2_resolved = c2_url or C2_BASE_URL
    v_url = vendor_url or VENDOR_BASE_URL

    finder_client = DataLayerClient(base_url=f_url)
    c1_client = DataLayerClient(base_url=c1_resolved)
    c2_client = DataLayerClient(base_url=c2_resolved)
    vendor_client = DataLayerClient(base_url=v_url)

    if not skip_health_check:
        targets: list[tuple[str, DataLayerClient]] = [
            ("Finder", finder_client),
            ("C1", c1_client),
            ("C2", c2_client),
            ("Vendor", vendor_client),
        ]
        for label, client in targets:
            if not check_server_availability(client):
                logger.error("=" * 80)
                logger.error("ERROR: %s API server is not available", label)
                logger.error("=" * 80)
                logger.error("Cannot connect to: %s", client.base_url)
                logger.error(
                    "Ensure the %s container is running and healthy.", label
                )
                logger.error("=" * 80)
                sys.exit(1)

    try:
        run_fccv_extension_demo(
            finder_client=finder_client,
            c1_client=c1_client,
            c2_client=c2_client,
            vendor_client=vendor_client,
            finder_id=finder_id,
            c1_id=c1_id,
            c2_id=c2_id,
            vendor_id=vendor_id,
        )
    finally:
        assert_demo_success()


if __name__ == "__main__":
    setup_demo_logging()
    main()
