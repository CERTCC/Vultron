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

"""Finder → C1 (CASE_OWNER) → C2 (ownership transfer) → Vendor (FCCV-handoff) demo.

Orchestrates the FCCV-handoff CVD workflow across four separate containers:
Finder, Coordinator1 (C1, initial CASE_OWNER), Coordinator2 (C2, new
CASE_OWNER after handoff), and Vendor.  C1 transfers case ownership to C2 via
the trigger endpoints (TRIG-11-001/TRIG-11-002), then C2 invites Vendor.

Container mapping (reuses docker-compose-multi-actor.yml services):
  VULTRON_VENDOR_BASE_URL      → C1 container
  VULTRON_COORDINATOR_BASE_URL → C2 container
  VULTRON_VENDOR2_BASE_URL     → Vendor container

Spec: GitHub issue #1216 (DEMOMA-14).
"""

import json
import logging
import os
import pathlib
import sys
import time

import httpx2 as httpx

from vultron.adapters.utils import strip_id_prefix
from vultron.core.states.cs import CS_vfd
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Offer,
    as_TransitiveActivity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,  # noqa: F401 — used in type annotation
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

# post_to_inbox_and_wait is retained for self-delivery (CONCERN-1653 exception).
from vultron.demo.helpers.actions import (
    actor_closes_case,
    actor_notifies_fix_ready,
    actor_notifies_published,
)
from vultron.demo.helpers.milestones import (
    verify_case_active,
    verify_case_closed,
    verify_fix_ready,
    verify_publicly_disclosed,
)
from vultron.demo.helpers.notes import participant_adds_note_to_case
from vultron.demo.helpers.polling import (
    find_case_actor_participant_id,
    find_case_invite_for_actor,
    wait_for_all_participants_rm_closed,
    wait_for_case_em_terminated,
    wait_for_case_on_container,
    wait_for_case_participants,
    wait_for_contiguous_ledger_coverage,
    wait_for_event_type_in_ledger,
    wait_for_object_stored,
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
    reporter_submits_report,
    run_direct_path_rm_triage,
    run_invite_path_rm_triage,
)

logger = logging.getLogger(__name__)

# Default container base URLs.
# C1 reuses the docker-compose "vendor" container; C2 reuses "coordinator";
# Vendor reuses "vendor2".  Override via environment variables.
FINDER_BASE_URL = os.environ.get(
    "VULTRON_FINDER_BASE_URL", "http://localhost:7901/api/v2"
)
C1_BASE_URL = os.environ.get(
    "VULTRON_VENDOR_BASE_URL", "http://localhost:7902/api/v2"
)
C2_BASE_URL = os.environ.get(
    "VULTRON_COORDINATOR_BASE_URL", "http://localhost:7903/api/v2"
)
CASE_ACTOR_BASE_URL = os.environ.get(
    "VULTRON_CASE_ACTOR_BASE_URL", "http://localhost:7905/api/v2"
)
VENDOR_BASE_URL = os.environ.get(
    "VULTRON_VENDOR2_BASE_URL", "http://localhost:7904/api/v2"
)

# Deterministic actor IDs — match docker-compose-multi-actor.yml service names
# (D5-1-G3) remapped for FCCV roles.
FINDER_ACTOR_ID = "http://finder:7999/api/v2/actors/finder"
C1_ACTOR_ID = "http://vendor:7999/api/v2/actors/vendor"
C2_ACTOR_ID = "http://coordinator:7999/api/v2/actors/coordinator"
CASE_ACTOR_ACTOR_ID = "http://case-actor:7999/api/v2/actors/case-actor"
VENDOR_ACTOR_ID = "http://actor5:7999/api/v2/actors/vendor2"


def reset_containers(
    finder_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    vendor_client: DataLayerClient,
) -> None:
    """Reset all five FCCV-handoff containers to a clean baseline."""
    targets: list[tuple[str, DataLayerClient]] = [
        ("Finder", finder_client),
        ("C1", c1_client),
        ("C2", c2_client),
        ("CaseActor", case_actor_client),
        ("Vendor", vendor_client),
    ]
    _reset_containers(targets, reset_fn=reset_datalayer)


# ---------------------------------------------------------------------------
# Polling helpers
# ---------------------------------------------------------------------------


def _wait_for_case_attributed_to(
    client: DataLayerClient,
    case_id: str,
    expected_attributed_to: str,
    timeout_seconds: float = 20.0,
    poll_interval: float = 0.5,
) -> None:
    """Poll until *case_id*'s ``attributed_to`` equals *expected_attributed_to*.

    Raises:
        AssertionError: If the field does not match within *timeout_seconds*.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            case_data = client.get(f"/datalayer/{case_id}")
            if isinstance(case_data, dict):
                attributed_to = case_data.get("attributedTo") or case_data.get(
                    "attributed_to"
                )
                if isinstance(attributed_to, dict):
                    attributed_to = attributed_to.get(
                        "id"
                    ) or attributed_to.get("id_")
                if attributed_to == expected_attributed_to:
                    logger.info(
                        "Case %s attributed_to updated to %s",
                        case_id,
                        expected_attributed_to,
                    )
                    return
        except Exception:  # noqa: BLE001
            pass
        time.sleep(poll_interval)

    raise AssertionError(
        f"Timed out waiting for case {case_id!r}"
        f" attributed_to={expected_attributed_to!r}"
        f" on container {client.base_url}"
    )


# ---------------------------------------------------------------------------
# Phase helpers
# ---------------------------------------------------------------------------


def _phase_report_submission(
    finder_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    case_actor_client: DataLayerClient,
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
    as_Actor,
    as_VulnerabilityReport,
    as_Offer,
    as_VulnerabilityCase,
]:
    """Reset, seed, submit report, validate, engage, and wait for initial participants."""
    logger.info("─" * 80)
    logger.info("Phase 1: Report submission and case activation")
    logger.info("─" * 80)

    reset_containers(
        finder_client=finder_client,
        c1_client=c1_client,
        c2_client=c2_client,
        case_actor_client=case_actor_client,
        vendor_client=vendor_client,
    )

    with demo_step("Seeding all five containers with actor records"):
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

    report, offer = reporter_submits_report(
        receiver_client=c1_client,
        reporter=finder,
        receiver=c1_in_c1,
        reporter_client=finder_client,
    )
    case = run_direct_path_rm_triage(
        receiver_client=c1_client,
        receiver=c1_in_c1,
        offer=offer,
    )

    # Wait for initial participants (Finder + C1 + CaseActor).
    wait_for_case_participants(
        vendor_client=c1_client,
        case_id=case.id_,
        expected_count=3,
    )

    case = as_VulnerabilityCase.model_validate(
        c1_client.get(f"/datalayer/{case.id_}")
    )
    return (
        finder,
        c1,
        c1_in_c1,
        c2,
        c2_in_c2,
        vendor,
        report,
        offer,
        case,
    )


def _phase_ownership_handoff(
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    c1: as_Actor,
    c1_in_c1: as_Actor,
    c2: as_Actor,
    c2_in_c2: as_Actor,
    case: as_VulnerabilityCase,
) -> as_VulnerabilityCase:
    """C1 invites C2 then transfers case ownership to C2.

    Returns the updated case (with C2 as attributed_to).
    """
    logger.info("─" * 80)
    logger.info(
        "Phase 2: Ownership handoff — C1 invites C2 then transfers ownership"
    )
    logger.info("─" * 80)

    # C1 invites C2 with COORDINATOR role.
    invite_result = None
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

    with demo_check("C2 invite delivered to C2's DataLayer"):
        find_case_invite_for_actor(
            client=c2_client,
            case_id=case.id_,
            invitee_id=c2.id_,
            timeout_seconds=90.0,
        )

    # C2 accepts the invite.
    with demo_step("C2 accepts the case invitation"):
        post_to_trigger(
            client=c2_client,
            actor_id=c2_in_c2.id_,
            behavior="accept-case-invite",
            body={"invite_id": invite.id_},
        )

    # Wait for C2's case replica.
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
    logger.info("C2 has joined the case")

    # C1 offers ownership transfer to C2 (TRIG-11-001).
    ownership_offer_result = None
    with demo_step("C1 offers case ownership transfer to C2 (TRIG-11-001)"):
        ownership_offer_result = post_to_trigger(
            client=c1_client,
            actor_id=c1_in_c1.id_,
            behavior="offer-case-ownership-transfer",
            body={
                "case_id": case.id_,
                "transferee_id": c2.id_,
                "content": "Transferring case ownership to C2 for CVD management.",
            },
        )
    ownership_offer = as_TransitiveActivity.model_validate(
        ownership_offer_result["activity"]
    )
    logger.info(
        "C1 sent Offer(VulnerabilityCase) ownership transfer: %s",
        ownership_offer.id_,
    )

    with demo_check(
        "Ownership transfer offer delivered to C2's DataLayer (TRIG-11-001)"
    ):
        wait_for_object_stored(
            client=c2_client,
            obj_id=ownership_offer.id_,
            timeout_seconds=90.0,
        )

    ownership_offer_id = ownership_offer.id_
    logger.info("Ownership transfer offer ID: %s", ownership_offer_id)

    # C2 accepts the ownership transfer (TRIG-11-002).
    accept_result = None
    with demo_step("C2 accepts case ownership transfer (TRIG-11-002)"):
        accept_result = post_to_trigger(
            client=c2_client,
            actor_id=c2_in_c2.id_,
            behavior="accept-case-ownership-transfer",
            body={"offer_id": ownership_offer_id},
        )
    accept_ownership = as_TransitiveActivity.model_validate(
        accept_result["activity"]
    )
    logger.info(
        "C2 sent Accept(Offer(VulnerabilityCase)): %s",
        accept_ownership.id_,
    )

    # Deliver the Accept to C2's own inbox so AcceptCaseOwnershipTransfer-
    # ReceivedUseCase runs locally and sets case.attributed_to = C2 on C2's
    # replica.  C1's copy updates when C2's outbox delivers the Accept to C1's
    # inbox (same pattern as FVCV-handoff).
    with demo_step("Delivering ownership Accept to C2's own inbox"):
        post_to_inbox_and_wait(c2_client, c2_in_c2.id_, accept_ownership)
    with demo_check("Ownership Accept stored in C2's DataLayer"):
        verify_object_stored(c2_client, accept_ownership.id_)

    # Verify C1's case now shows C2 as attributed_to.
    with demo_check(
        "Case attributed_to updated to C2 on C1's DataLayer (AC-1)"
    ):
        _wait_for_case_attributed_to(
            client=c1_client,
            case_id=case.id_,
            expected_attributed_to=c2.id_,
        )

    # Also verify on C2's side.
    with demo_check("Case attributed_to updated to C2 on C2's DataLayer"):
        _wait_for_case_attributed_to(
            client=c2_client,
            case_id=case.id_,
            expected_attributed_to=c2.id_,
        )

    logger.info(
        "✓ Ownership transfer complete: C2 is now CASE_OWNER for %s",
        case.id_,
    )

    case = as_VulnerabilityCase.model_validate(
        c1_client.get(f"/datalayer/{case.id_}")
    )
    return case


def _phase_c2_invites_vendor(
    finder_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    vendor_client: DataLayerClient,
    c2: as_Actor,
    c2_in_c2: as_Actor,
    case_actor_id: str,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    case: as_VulnerabilityCase,
    offer: as_Offer,
    report: as_VulnerabilityReport,
    finder: as_Actor,
) -> None:
    """C2 (new CASE_OWNER) invites Vendor and Vendor joins the case (AC-2)."""
    logger.info("─" * 80)
    logger.info("Phase 3: C2 invites Vendor (AC-2)")
    logger.info("─" * 80)

    # Trigger on c1_client (the CaseActor's host container) so the invite is
    # emitted as CaseActor.  Vendor's Accept then routes to CaseActor,
    # enabling AcceptInviteActorToCaseBT to run (PCR-08-008).
    invite_result = None
    with demo_step("C2 invites Vendor to the case"):
        invite_result = post_to_trigger(
            client=c1_client,
            actor_id=c2_in_c2.id_,
            behavior="invite-actor-to-case",
            body={
                "case_id": case.id_,
                "invitee_id": vendor.id_,
                "roles": ["vendor"],
            },
        )
    invite = as_TransitiveActivity.model_validate(invite_result["activity"])
    logger.info("Vendor invite created by C2: %s", invite.id_)

    with demo_check("Vendor invite delivered to Vendor's DataLayer"):
        find_case_invite_for_actor(
            client=vendor_client,
            case_id=case.id_,
            invitee_id=vendor.id_,
            timeout_seconds=90.0,
        )

    # Vendor accepts the invite.
    accept_result = None
    with demo_step("Vendor accepts the case invitation"):
        accept_result = post_to_trigger(
            client=vendor_client,
            actor_id=vendor_in_vendor.id_,
            behavior="accept-case-invite",
            body={"invite_id": invite.id_},
        )
    accept = as_TransitiveActivity.model_validate(accept_result["activity"])
    logger.info("Vendor sent Accept(Invite): %s", accept.id_)

    # HttpDeliveryAdapter delivers Vendor's Accept to the CaseActor inbox
    # via the real HTTP path (PCR-08-008).  Poll for the case replica as proof
    # that CaseActor processed the Accept and fanned out Announce(VulnerabilityCase).
    # Wait for Vendor's case replica.
    with demo_check("Vendor's DataLayer received case replica (AC-2)"):
        wait_for_case_on_container(
            client=vendor_client,
            case_id=case.id_,
            timeout_seconds=90.0,
        )
    logger.info("Vendor received case replica")

    # 5 participants: Finder + C1 + C2 + Vendor + CaseActor
    wait_for_case_participants(
        vendor_client=c1_client,
        case_id=case.id_,
        expected_count=5,
        timeout_seconds=90.0,
    )
    logger.info("✓ Vendor joined case (%d participants)", 5)

    # CLP-08-005: ensure Finder's genesis hash is seeded before Announce(CaseLedgerEntry)
    # is broadcast by the triage cycle below.
    with demo_check(
        "Finder's DataLayer received case replica before Vendor RM triage"
    ):
        wait_for_case_on_container(
            client=finder_client,
            case_id=case.id_,
            timeout_seconds=90.0,
        )

    # CM-11-002: Vendor joined via invite-accept — run standard RM triage cycle.
    run_invite_path_rm_triage(
        invited_client=vendor_client,
        invited_actor=vendor_in_vendor,
        offer=offer,
        report=report,
        finder=finder,
        auth_client=c1_client,
        case=case,
        invited_obj=vendor,
        timeout_seconds=90.0,
    )


def _phase_sync_verification(
    finder_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    vendor_client: DataLayerClient,
    c1: as_Actor,
    finder: as_Actor,
    c2: as_Actor,
    vendor: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Verify replica synchronization for all four actor containers."""
    logger.info("─" * 80)
    logger.info("Phase 4: Replica synchronization verification")
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

    logger.info("✓ All replicas synchronized")


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
    logger.info("Phase 4b: Notes exchange")
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
        note_name="C2 Update (new Case Owner)",
        note_content=(
            "As the new case owner, I confirm Vendor is engaged. "
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
            "Vendor confirms the issue and will align fix timeline with the "
            "coordinated disclosure window."
        ),
        in_reply_to=c2_note.id_,
    )

    logger.info(
        "✓ Notes exchange complete (four notes committed to case ledger)"
    )
    return question_note, c1_reply, c2_note, vendor_note


def _phase_fix_lifecycle(
    finder_client: DataLayerClient,
    c1_client: DataLayerClient,
    vendor_client: DataLayerClient,
    c1: as_Actor,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Advance Vendor through the fix-ready and fix-deployed paths."""
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

    with demo_check("Finder replica shows Vendor CS includes F (fix ready)"):
        wait_for_participant_vfd_state(
            client=c1_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vfd.VFd, CS_vfd.VFD},
        )
        wait_for_participant_vfd_state(
            client=finder_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vfd.VFd, CS_vfd.VFD},
        )
        verify_fix_ready(
            receiver_client=c1_client,
            reporter_client=finder_client,
            case_id=case.id_,
            receiver_actor_id=vendor.id_,
        )

    with demo_check(
        "Finder replica shows Vendor CS includes F (fix ready) — vendor stops at VFd"
    ):
        wait_for_participant_vfd_state(
            client=c1_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vfd.VFd},
        )
        wait_for_participant_vfd_state(
            client=finder_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vfd.VFd},
        )
        verify_fix_ready(
            receiver_client=c1_client,
            reporter_client=finder_client,
            case_id=case.id_,
            receiver_actor_id=vendor.id_,
        )


def _phase_publication(
    finder_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    vendor_client: DataLayerClient,
    c1: as_Actor,
    c1_in_c1: as_Actor,
    c2: as_Actor,
    c2_in_c2: as_Actor,
    finder: as_Actor,
    finder_in_finder: as_Actor,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Run publication notifications and verify public disclosure state."""
    logger.info("─" * 80)
    logger.info(
        "Phase 6: Publication — CS.VFDPxa + embargo teardown (EM.EXITED)"
    )
    logger.info("─" * 80)

    actor_notifies_published(
        client=c2_client,
        actor=c2_in_c2,
        case_id=case.id_,
    )

    with demo_check(
        "Embargo terminated (EM.EXITED) after C2 reports published"
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
        client=c1_client,
        actor=c1_in_c1,
        case_id=case.id_,
    )
    actor_notifies_published(
        client=finder_client,
        actor=finder_in_finder,
        case_id=case.id_,
    )

    with demo_check(
        "All replicas CS.VFdPxa, EM.EXITED, all participants public-aware"
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
        wait_for_participant_vfd_state(
            client=finder_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vfd.VFd},
        )
        verify_publicly_disclosed(
            receiver_client=c1_client,
            reporter_client=finder_client,
            case_id=case.id_,
            receiver_actor_id=vendor.id_,
        )


def _phase_case_closure(
    finder_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    vendor_client: DataLayerClient,
    c1: as_Actor,
    c1_in_c1: as_Actor,
    c2: as_Actor,
    c2_in_c2: as_Actor,
    finder: as_Actor,
    finder_in_finder: as_Actor,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
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
        client=finder_client,
        actor=finder_in_finder,
        case_id=case.id_,
    )
    # C2 is the case owner post-handoff (TRIG-11-002) and closes last.
    actor_closes_case(
        client=c2_client,
        actor=c2_in_c2,
        case_id=case.id_,
    )

    with demo_check("All participants RM.CLOSED on all replicas"):
        wait_for_all_participants_rm_closed(
            client=c2_client,
            case_id=case.id_,
        )
        wait_for_all_participants_rm_closed(
            client=finder_client,
            case_id=case.id_,
        )
        verify_case_closed(
            receiver_client=c2_client,
            reporter_client=finder_client,
            case_id=case.id_,
        )

    with demo_check("close_case entry present on authoritative actor (c2)"):
        wait_for_event_type_in_ledger(
            client=c2_client,
            case_id=case.id_,
            event_type="close_case",
        )
    c2_entries = _get_log_entries_for_case(c2_client, case.id_)
    if c2_entries:
        c2_tail = max(c2_entries, key=lambda e: e["log_index"])
        c2_tail_index: int = c2_tail["log_index"]
        c2_tail_hash: str = c2_tail["entry_hash"]
        logger.info(
            "Waiting for replicas to receive C2 tail after closure"
            " (hash=%s… index=%d)",
            c2_tail_hash[:16],
            c2_tail_index,
        )
        for replica_client, label in [
            (finder_client, "Finder"),
            (c1_client, "C1"),
            (vendor_client, "Vendor"),
        ]:
            with demo_check(f"{label} ledger coverage (close phase)"):
                wait_for_contiguous_ledger_coverage(
                    client=replica_client,
                    case_id=case.id_,
                    expected_tail_index=c2_tail_index,
                )


def _phase_dump_case_ledgers(
    finder_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case: as_VulnerabilityCase,
    demo_name: str = "fccv-handoff",
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
        ("vendor", c1_client, "vendor"),
        ("coordinator", c2_client, "coordinator"),
        ("vendor2", vendor_client, "vendor2"),
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


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def run_fccv_handoff_demo(
    finder_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    vendor_client: DataLayerClient,
    finder_id: str | None = None,
    c1_id: str | None = None,
    c2_id: str | None = None,
    case_actor_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Orchestrate the FCCV-handoff CVD workflow."""
    logger.info("=" * 80)
    logger.info("FCCV-HANDOFF DEMO: Finder + C1 → C2 (ownership) + Vendor")
    logger.info("=" * 80)
    logger.info("Finder container:    %s", finder_client.base_url)
    logger.info("C1 container:        %s", c1_client.base_url)
    logger.info("C2 container:        %s", c2_client.base_url)
    logger.info("CaseActor container: %s", case_actor_client.base_url)
    logger.info("Vendor container:    %s", vendor_client.base_url)

    (
        finder,
        c1,
        c1_in_c1,
        c2,
        c2_in_c2,
        vendor,
        report,
        offer,
        case,
    ) = _phase_report_submission(
        finder_client,
        c1_client,
        c2_client,
        case_actor_client,
        vendor_client,
        finder_id,
        c1_id,
        c2_id,
        vendor_id,
    )

    # Discover the CaseActor's dynamic sub-actor ID before the handoff phase.
    dynamic_case_actor_id = find_case_actor_participant_id(c1_client, case.id_)
    if dynamic_case_actor_id is None:
        raise AssertionError(
            "CaseActor participant not found in case — cannot route Vendor Accept"
        )
    logger.info("CaseActor participant ID: %s", dynamic_case_actor_id)

    vendor_in_vendor = get_actor_by_id(vendor_client, vendor.id_)
    finder_in_finder = get_actor_by_id(finder_client, finder.id_)

    case = _phase_ownership_handoff(
        c1_client=c1_client,
        c2_client=c2_client,
        c1=c1,
        c1_in_c1=c1_in_c1,
        c2=c2,
        c2_in_c2=c2_in_c2,
        case=case,
    )

    _phase_c2_invites_vendor(
        finder_client=finder_client,
        c1_client=c1_client,
        c2_client=c2_client,
        vendor_client=vendor_client,
        c2=c2,
        c2_in_c2=c2_in_c2,
        case_actor_id=dynamic_case_actor_id,
        vendor=vendor,
        vendor_in_vendor=vendor_in_vendor,
        case=case,
        offer=offer,
        report=report,
        finder=finder,
    )

    # Verify case active now that all participants have joined.
    with demo_check(
        "M1: required participants (≥5), EM.ACTIVE, finder + c2 have replicas"
    ):
        verify_case_active(
            receiver_client=c1_client,
            reporter_client=finder_client,
            case_id=case.id_,
            receiver_actor_id=c1.id_,
            reporter_actor_id=finder.id_,
        )

    _phase_sync_verification(
        finder_client,
        c1_client,
        c2_client,
        vendor_client,
        c1,
        finder,
        c2,
        vendor,
        case,
    )
    _phase_notes_exchange(
        finder_client,
        c1_client,
        c2_client,
        vendor_client,
        finder_in_finder,
        c1_in_c1,
        c2_in_c2,
        vendor_in_vendor,
        case,
    )
    _phase_fix_lifecycle(
        finder_client,
        c1_client,
        vendor_client,
        c1,
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
        c2,
        c2_in_c2,
        finder,
        finder_in_finder,
        vendor,
        vendor_in_vendor,
        case,
    )
    _phase_case_closure(
        finder_client,
        c1_client,
        c2_client,
        vendor_client,
        c1,
        c1_in_c1,
        c2,
        c2_in_c2,
        finder,
        finder_in_finder,
        vendor,
        vendor_in_vendor,
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
    logger.info(
        "FCCV-HANDOFF DEMO COMPLETE ✓  (ownership transfer + VFDPxa full lifecycle)"
    )
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(
    skip_health_check: bool = False,
    finder_url: str | None = None,
    c1_url: str | None = None,
    c2_url: str | None = None,
    case_actor_url: str | None = None,
    vendor_url: str | None = None,
    finder_id: str | None = None,
    c1_id: str | None = None,
    c2_id: str | None = None,
    case_actor_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Entry point for the FCCV-handoff CVD workflow demo.

    Args:
        skip_health_check: Skip the server availability check.
        finder_url: Override base URL for the Finder container.
        c1_url: Override base URL for the C1 (Coordinator1) container.
        c2_url: Override base URL for the C2 (Coordinator2) container.
        case_actor_url: Override base URL for the CaseActor container.
        vendor_url: Override base URL for the Vendor container.
        finder_id: Optional deterministic URI for the Finder actor.
        c1_id: Optional deterministic URI for the C1 actor.
        c2_id: Optional deterministic URI for the C2 actor.
        case_actor_id: Optional deterministic URI for the CaseActor actor.
        vendor_id: Optional deterministic URI for the Vendor actor.
    """
    reset_demo_failures()

    f_url = finder_url or FINDER_BASE_URL
    _c1_url = c1_url or C1_BASE_URL
    _c2_url = c2_url or C2_BASE_URL
    ca_url = case_actor_url or CASE_ACTOR_BASE_URL
    v_url = vendor_url or VENDOR_BASE_URL

    finder_client = DataLayerClient(base_url=f_url)
    c1_client = DataLayerClient(base_url=_c1_url)
    c2_client = DataLayerClient(base_url=_c2_url)
    case_actor_client = DataLayerClient(base_url=ca_url)
    vendor_client = DataLayerClient(base_url=v_url)

    if not skip_health_check:
        targets: list[tuple[str, DataLayerClient]] = [
            ("Finder", finder_client),
            ("C1", c1_client),
            ("C2", c2_client),
            ("CaseActor", case_actor_client),
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
        run_fccv_handoff_demo(
            finder_client=finder_client,
            c1_client=c1_client,
            c2_client=c2_client,
            case_actor_client=case_actor_client,
            vendor_client=vendor_client,
            finder_id=finder_id,
            c1_id=c1_id,
            c2_id=c2_id,
            case_actor_id=case_actor_id,
            vendor_id=vendor_id,
        )
    finally:
        assert_demo_success()


if __name__ == "__main__":
    setup_demo_logging()
    main()
