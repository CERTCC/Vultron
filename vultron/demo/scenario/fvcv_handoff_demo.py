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

"""Finder → Vendor1 → Coordinator (ownership transfer) → Vendor2 (FVCV-handoff) demo.

Orchestrates the FVCV-handoff CVD workflow across four separate containers:
Finder, Vendor1 (initial CASE_OWNER), Coordinator (new CASE_OWNER after handoff),
and Vendor2.  Vendor1 transfers case ownership to Coordinator via the new
trigger endpoints (TRIG-11-001/TRIG-11-002), then Coordinator invites Vendor2.

Spec: GitHub issue #1561.
"""

import logging
import os
import sys

from vultron.core.states.cs import CS_vfd
from vultron.core.states.rm import RM
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
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
    case_actor_id_on,
    check_server_availability,
    demo_check,
    demo_gate,
    demo_step,
    post_to_trigger,
    ref_id,
    reset_datalayer,
    reset_demo_failures,
    setup_demo_logging,
)
from vultron.demo.helpers.actions import (
    actor_closes_case,
    actor_notifies_fix_ready,
    actor_notifies_published,
)
from vultron.demo.helpers.notes import (
    participant_adds_note_to_case,
)
from vultron.demo.helpers.harness import scenario_harness
from vultron.demo.helpers.ledger_dump import (
    LedgerDumpTarget,
    dump_case_ledgers,
    replica_route_key,
    resolve_case_actor_route_key,
)
from vultron.demo.helpers.milestones import (
    verify_case_active,
    verify_case_closed,
    verify_fix_ready,
    verify_publicly_disclosed,
)
from vultron.demo.helpers.polling import (
    find_case_actor_participant_id,
    LATE_JOINER_TIMEOUT,
    find_case_invite_for_actor,
    find_ownership_transfer_offer_for_actor,
    wait_for_all_participants_rm_closed,
    wait_for_case_attributed_to,
    wait_for_case_em_terminated,
    wait_for_case_on_container,
    wait_for_case_participants,
    wait_for_contiguous_ledger_coverage,
    wait_for_event_type_in_ledger,
    wait_for_participant_rm_state,
    wait_for_participant_vfd_state,
)
from vultron.demo.helpers.seeding import (
    get_actor_by_id,
    reset_containers as _reset_containers,
    seed_containers_fvcv,
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

# Default container base URLs — override via environment variables.
FINDER_BASE_URL = os.environ.get(
    "VULTRON_FINDER_BASE_URL", "http://localhost:7901/api/v2"
)
VENDOR_BASE_URL = os.environ.get(
    "VULTRON_VENDOR_BASE_URL", "http://localhost:7902/api/v2"
)
COORDINATOR_BASE_URL = os.environ.get(
    "VULTRON_COORDINATOR_BASE_URL", "http://localhost:7903/api/v2"
)
CASE_ACTOR_BASE_URL = os.environ.get(
    "VULTRON_CASE_ACTOR_BASE_URL", "http://localhost:7905/api/v2"
)
VENDOR2_BASE_URL = os.environ.get(
    "VULTRON_VENDOR2_BASE_URL", "http://localhost:7904/api/v2"
)

# Deterministic actor IDs from docker-compose-multi-actor.yml (D5-1-G3).
FINDER_ACTOR_ID = "http://finder:7999/api/v2/actors/finder"
VENDOR_ACTOR_ID = "http://vendor:7999/api/v2/actors/vendor"
COORDINATOR_ACTOR_ID = "http://coordinator:7999/api/v2/actors/coordinator"
CASE_ACTOR_ACTOR_ID = "http://case-actor:7999/api/v2/actors/case-actor"
VENDOR2_ACTOR_ID = "http://actor5:7999/api/v2/actors/vendor2"


def reset_containers(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
) -> None:
    """Reset all five FVCV-handoff containers to a clean baseline."""
    targets: list[tuple[str, DataLayerClient]] = [
        ("Finder", finder_client),
        ("Vendor1", vendor_client),
        ("Coordinator", coordinator_client),
        ("CaseActor", case_actor_client),
        ("Vendor2", vendor2_client),
    ]
    _reset_containers(targets, reset_fn=reset_datalayer)


# ---------------------------------------------------------------------------
# Phase helpers
# ---------------------------------------------------------------------------


def _phase_report_submission(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    finder_id: str | None,
    vendor_id: str | None,
    coordinator_id: str | None,
    vendor2_id: str | None,
) -> tuple[
    as_Actor,
    as_Actor,
    as_Actor,
    as_Actor,
    as_Actor,
    as_Actor,
    as_VulnerabilityReport,
    object,
    as_VulnerabilityCase,
]:
    """Reset, seed, submit report, validate, engage, and wait for initial participants."""
    logger.info("─" * 80)
    logger.info("Phase 1: Report submission and case activation")
    logger.info("─" * 80)

    reset_containers(
        finder_client=finder_client,
        vendor_client=vendor_client,
        coordinator_client=coordinator_client,
        case_actor_client=case_actor_client,
        vendor2_client=vendor2_client,
    )

    finder = vendor = coordinator = vendor2 = None
    with demo_step("Seeding all four containers with actor records"):
        finder, vendor, coordinator, vendor2 = seed_containers_fvcv(
            finder_client=finder_client,
            vendor_client=vendor_client,
            coordinator_client=coordinator_client,
            vendor2_client=vendor2_client,
            reporter_actor_id=finder_id,
            vendor_actor_id=vendor_id,
            coordinator_actor_id=coordinator_id,
            vendor2_actor_id=vendor2_id,
        )

    vendor_in_vendor = get_actor_by_id(vendor_client, vendor.id_)
    coordinator_in_coordinator = get_actor_by_id(
        coordinator_client, coordinator.id_
    )

    report, offer = reporter_submits_report(
        receiver_client=vendor_client,
        reporter=finder,
        receiver=vendor_in_vendor,
        reporter_client=finder_client,
    )
    case = run_direct_path_rm_triage(
        receiver_client=vendor_client,
        receiver=vendor_in_vendor,
        offer=offer,
    )

    # Wait for initial participants (Finder + Vendor1 + CaseActor).
    with demo_gate("participant count ≥3 before M1 verify_case_active"):
        wait_for_case_participants(
            vendor_client=vendor_client,
            case_id=case.id_,
            expected_actor_ids={finder.id_, vendor.id_},
        )

        with demo_check(
            "Finder's DataLayer received case replica (genesis hash available)"
        ):
            wait_for_case_on_container(
                client=finder_client,
                case_id=case.id_,
            )

    case = as_VulnerabilityCase.model_validate(
        vendor_client.get(vendor_client.dl_path(case.id_))
    )
    return (
        finder,
        vendor,
        vendor_in_vendor,
        coordinator,
        coordinator_in_coordinator,
        vendor2,
        report,
        offer,
        case,
    )


def _phase_ownership_handoff(
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    coordinator: as_Actor,
    coordinator_in_coordinator: as_Actor,
    case: as_VulnerabilityCase,
) -> as_VulnerabilityCase:
    """Vendor1 invites Coordinator then transfers case ownership to Coordinator.

    Returns the updated case (with Coordinator as attributed_to).
    """
    logger.info("─" * 80)
    logger.info(
        "Phase 2: Ownership handoff — Vendor1 invites Coordinator then transfers ownership"
    )
    logger.info("─" * 80)

    # Vendor1 invites Coordinator with COORDINATOR role.
    invite_result = None
    with demo_step("Vendor1 invites Coordinator with CVDRole.COORDINATOR"):
        invite_result = post_to_trigger(
            client=vendor_client,
            actor_id=vendor_in_vendor.id_,
            behavior="invite-actor-to-case",
            body={
                "case_id": case.id_,
                "invitee_id": coordinator.id_,
                "roles": ["coordinator"],
            },
        )
    invite = as_TransitiveActivity.model_validate(invite_result["activity"])
    logger.info("Coordinator invite created: %s", invite.id_)

    with demo_check("Coordinator invite delivered to Coordinator's DataLayer"):
        find_case_invite_for_actor(
            client=coordinator_client,
            case_id=case.id_,
            invitee_id=coordinator.id_,
            timeout_seconds=90.0,
        )

    # Coordinator accepts the invite.
    with demo_step("Coordinator accepts the case invitation"):
        post_to_trigger(
            client=coordinator_client,
            actor_id=coordinator_in_coordinator.id_,
            behavior="accept-case-invite",
            body={"invite_id": invite.id_},
        )

    # Wait for Coordinator's case replica.
    with demo_check("Coordinator's DataLayer received case replica"):
        wait_for_case_on_container(
            client=coordinator_client,
            case_id=case.id_,
        )

    # 4 participants: Finder + Vendor1 + Coordinator + CaseActor
    wait_for_case_participants(
        vendor_client=vendor_client,
        case_id=case.id_,
        expected_actor_ids={
            finder.id_,
            vendor.id_,
            coordinator.id_,
        },
    )
    logger.info("Coordinator has joined the case")

    # Vendor1 offers ownership transfer to Coordinator (TRIG-11-001).
    ownership_offer_result = None
    with demo_step(
        "Vendor1 offers case ownership transfer to Coordinator (TRIG-11-001)"
    ):
        ownership_offer_result = post_to_trigger(
            client=vendor_client,
            actor_id=vendor_in_vendor.id_,
            behavior="offer-case-ownership-transfer",
            body={
                "case_id": case.id_,
                "transferee_id": coordinator.id_,
                "content": "Transferring case ownership to Coordinator for CVD management.",
            },
        )
    ownership_offer = as_TransitiveActivity.model_validate(
        ownership_offer_result["activity"]
    )
    logger.info(
        "Vendor1 sent Offer(VulnerabilityCase) ownership transfer: %s",
        ownership_offer.id_,
    )

    # Wait for the FORWARDED offer (CM-21-005).
    # OfferCaseOwnershipTransferReceivedUseCase creates a NEW Offer (forwarded_id)
    # when the CaseActor processes Vendor1's Offer.  The forwarded Offer lands in
    # Coordinator's DataLayer under a different ID; the original Offer only exists
    # in the CaseActor's DataLayer.  Polling for the original ID would never match.
    ownership_offer_id: str = ""
    with demo_check(
        "Forwarded Offer(VulnerabilityCase) delivered to Coordinator's DataLayer (CM-21-005)"
    ):
        ownership_offer_id = find_ownership_transfer_offer_for_actor(
            client=coordinator_client,
            case_id=case.id_,
            transferee_id=coordinator.id_,
            timeout_seconds=90.0,
        )
    logger.info(
        "Forwarded ownership transfer offer ID: %s", ownership_offer_id
    )

    # Coordinator accepts the ownership transfer (TRIG-11-002).
    accept_ownership = None
    with demo_step(
        "Coordinator accepts case ownership transfer (TRIG-11-002)"
    ):
        accept_result = post_to_trigger(
            client=coordinator_client,
            actor_id=coordinator_in_coordinator.id_,
            behavior="accept-case-ownership-transfer",
            body={"offer_id": ownership_offer_id},
        )
        accept_ownership = as_TransitiveActivity.model_validate(
            accept_result["activity"]
        )
        logger.info(
            "Coordinator sent Accept(Offer(VulnerabilityCase)): %s",
            accept_ownership.id_,
        )

    # Verify Vendor1's case now shows Coordinator as attributed_to.
    with demo_check(
        "Case attributed_to updated to Coordinator on Vendor1's DataLayer (AC-1)"
    ):
        wait_for_case_attributed_to(
            client=vendor_client,
            case_id=case.id_,
            expected_attributed_to=coordinator.id_,
        )

    # Also verify on Coordinator's side.
    with demo_check(
        "Case attributed_to updated to Coordinator on Coordinator's DataLayer"
    ):
        wait_for_case_attributed_to(
            client=coordinator_client,
            case_id=case.id_,
            expected_attributed_to=coordinator.id_,
        )

    logger.info(
        "✓ Ownership transfer complete: Coordinator is now CASE_OWNER for %s",
        case.id_,
    )

    case = as_VulnerabilityCase.model_validate(
        vendor_client.get(vendor_client.dl_path(case.id_))
    )
    return case


def _phase_coordinator_invites_vendor2(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
    coordinator_in_coordinator: as_Actor,
    case_actor_id: str,
    vendor2: as_Actor,
    vendor2_in_vendor2: as_Actor,
    case: as_VulnerabilityCase,
    offer: object,
    report: as_VulnerabilityReport,
) -> None:
    """Coordinator (new CASE_OWNER) invites Vendor2; Vendor2 runs RM triage."""
    logger.info("─" * 80)
    logger.info("Phase 3: Coordinator invites Vendor2 (AC-2)")
    logger.info("─" * 80)

    # Post to the Coordinator's OWN container.  A trigger URL is built from the
    # named actor's bare ID against the client's base_url, so naming an actor a
    # container does not host 404s — which is exactly what posting Coordinator's
    # trigger to vendor_client did.
    #
    # Emitting as the CaseActor needs no cross-container hack:
    # ``SvcInviteActorToCaseUseCase._prepare`` resolves the case's CaseActor and
    # sets ``self._actor_id`` to it, so the Invite goes out attributed to the
    # CaseActor and Vendor2's Accept routes back to the CaseActor rather than to
    # the Coordinator, letting AcceptInviteActorToCaseBT run (PCR-08-007,
    # PCR-08-008).  The assertion below is what holds that property honest.
    invite_result = None
    with demo_step("Coordinator invites Vendor2 to the case"):
        invite_result = post_to_trigger(
            client=coordinator_client,
            actor_id=coordinator_in_coordinator.id_,
            behavior="invite-actor-to-case",
            body={
                "case_id": case.id_,
                "invitee_id": vendor2.id_,
                "roles": ["vendor"],
            },
        )
    invite = as_TransitiveActivity.model_validate(invite_result["activity"])
    logger.info("Vendor2 invite created by Coordinator: %s", invite.id_)

    with demo_check(
        "Vendor2 invite was emitted as the CaseActor (PCR-08-008)"
    ):
        emitting_actor = ref_id(invite.actor)
        assert emitting_actor == case_actor_id, (
            f"Invite '{invite.id_}' was emitted as '{emitting_actor}', not as"
            f" the CaseActor '{case_actor_id}' — Vendor2's Accept would route"
            " to the Coordinator and AcceptInviteActorToCaseBT would not run"
        )

    with demo_check("Vendor2 invite delivered to Vendor2's DataLayer"):
        find_case_invite_for_actor(
            client=vendor2_client,
            case_id=case.id_,
            invitee_id=vendor2.id_,
            timeout_seconds=90.0,
        )

    # Vendor2 accepts the invite.
    with demo_step("Vendor2 accepts the case invitation"):
        accept_result = post_to_trigger(
            client=vendor2_client,
            actor_id=vendor2_in_vendor2.id_,
            behavior="accept-case-invite",
            body={"invite_id": invite.id_},
        )
        accept = as_TransitiveActivity.model_validate(
            accept_result["activity"]
        )
        logger.info("Vendor2 sent Accept(Invite): %s", accept.id_)

    # HttpDeliveryAdapter delivers Vendor2's Accept to the CaseActor inbox
    # via the real HTTP path (PCR-08-008).  Poll for the case replica as proof
    # that CaseActor processed the Accept and fanned out Announce(VulnerabilityCase).
    # Wait for Vendor2's case replica.
    with demo_check("Vendor2's DataLayer received case replica (AC-2)"):
        wait_for_case_on_container(
            client=vendor2_client,
            case_id=case.id_,
            timeout_seconds=90.0,
        )
    logger.info("Vendor2 received case replica")

    # 5 participants: Finder + Vendor1 + Coordinator + Vendor2 + CaseActor
    wait_for_case_participants(
        vendor_client=vendor_client,
        case_id=case.id_,
        expected_actor_ids={
            finder.id_,
            vendor.id_,
            coordinator.id_,
            vendor2.id_,
        },
        timeout_seconds=LATE_JOINER_TIMEOUT,
    )
    logger.info("✓ Vendor2 joined case (%d participants)", 5)

    with demo_check(
        "Finder's DataLayer received case replica before Vendor2 RM triage"
    ):
        wait_for_case_on_container(
            client=finder_client,
            case_id=case.id_,
            timeout_seconds=90.0,
        )

    # CM-11-002: Vendor2 joined via invite-accept — run standard RM triage cycle.
    run_invite_path_rm_triage(
        invited_client=vendor2_client,
        invited_actor=vendor2_in_vendor2,
        offer=offer,
        report=report,
        finder=finder,
        auth_client=vendor_client,
        case=case,
        invited_obj=vendor2,
        timeout_seconds=90.0,
    )


def _phase_sync_verification(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    vendor: as_Actor,
    finder: as_Actor,
    coordinator: as_Actor,
    vendor2: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Verify replica synchronization for all four containers."""
    logger.info("─" * 80)
    logger.info("Phase 4: Replica synchronization verification")
    logger.info("─" * 80)

    with demo_gate("Finder case seeded before ledger coverage wait (SYNC-15)"):
        wait_for_case_on_container(client=finder_client, case_id=case.id_)
        vendor_entries = _get_log_entries_for_case(vendor_client, case.id_)
        if vendor_entries:
            vendor_tail = max(vendor_entries, key=lambda e: e["log_index"])
            vendor_tail_index: int = vendor_tail["log_index"]
            vendor_tail_hash: str = vendor_tail["entry_hash"]
            logger.info(
                "Waiting for replicas to sync Vendor1 tail (hash=%s… index=%d)",
                vendor_tail_hash[:16],
                vendor_tail_index,
            )
            for replica_client, label in [
                (finder_client, "Finder"),
                (coordinator_client, "Coordinator"),
                (vendor2_client, "Vendor2"),
            ]:
                with demo_gate(
                    f"{label} ledger coverage (sync-verification phase)"
                ):
                    timeout = 45.0 if label == "Vendor2" else 15.0
                    wait_for_contiguous_ledger_coverage(
                        client=replica_client,
                        case_id=case.id_,
                        expected_tail_index=vendor_tail_index,
                        timeout_seconds=timeout,
                    )
                logger.info("  %s ledger synchronized", label)

    for replica_client in (finder_client, coordinator_client, vendor2_client):
        # Temporal (EDF-06-006): Vendor2 is a late joiner — allow extra time
        # for participant-index propagation; causal-gate migration in #2202.
        p_timeout = 30.0 if replica_client is vendor2_client else 10.0
        wait_for_case_participants(
            vendor_client=replica_client,
            case_id=case.id_,
            expected_actor_ids={
                finder.id_,
                vendor.id_,
                coordinator.id_,
                vendor2.id_,
            },
            timeout_seconds=p_timeout,
        )

    with demo_check("Finder replica matches authoritative Vendor1 state"):
        verify_replica_state(
            auth_client=vendor_client,
            replica_client=finder_client,
            case_id=case.id_,
            vendor_actor_id=vendor.id_,
            reporter_actor_id=finder.id_,
        )

    with demo_check("Vendor2 replica matches authoritative Vendor1 state"):
        verify_replica_state(
            auth_client=vendor_client,
            replica_client=vendor2_client,
            case_id=case.id_,
            vendor_actor_id=vendor.id_,
            reporter_actor_id=finder.id_,
        )

    logger.info("✓ All replicas synchronized")


def _phase_notes_exchange(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    finder_in_finder: as_Actor,
    vendor_in_vendor: as_Actor,
    coordinator_in_coordinator: as_Actor,
    vendor2_in_vendor2: as_Actor,
    case: as_VulnerabilityCase,
) -> tuple[as_Note | None, as_Note | None, as_Note | None, as_Note | None]:
    """Run a four-way note exchange among all participants.

    Emits ``add_note_to_case`` events into the canonical case ledger,
    exercising the note-threading path and satisfying the universal
    ``add_note_to_case`` invariant asserted by the case-ledger harness.
    """
    logger.info("─" * 80)
    logger.info("Phase 4b: Notes exchange")
    logger.info("─" * 80)

    question_note = participant_adds_note_to_case(
        posting_client=finder_client,
        watching_client=vendor_client,
        poster=finder_in_finder,
        case=case,
        note_name="Question from Finder",
        note_content=(
            "Is there a workaround available while the patch is being developed?"
        ),
    )

    vendor_reply = participant_adds_note_to_case(
        posting_client=vendor_client,
        watching_client=vendor_client,
        poster=vendor_in_vendor,
        case=case,
        note_name="Vendor1 Response",
        note_content=(
            "Yes, disabling the affected module is an effective interim workaround."
        ),
        in_reply_to=question_note.id_ if question_note is not None else None,
    )

    coordinator_note = participant_adds_note_to_case(
        posting_client=coordinator_client,
        watching_client=vendor_client,
        poster=coordinator_in_coordinator,
        case=case,
        note_name="Coordinator Update",
        note_content=(
            "As the new case owner, I confirm both Vendor1 and Vendor2 are "
            "engaged. Target disclosure in 30 days."
        ),
        in_reply_to=vendor_reply.id_ if vendor_reply is not None else None,
    )

    vendor2_note = participant_adds_note_to_case(
        posting_client=vendor2_client,
        watching_client=vendor_client,
        poster=vendor2_in_vendor2,
        case=case,
        note_name="Vendor2 Status Update",
        note_content=(
            "Vendor2 confirms the issue affects our component as well. "
            "We will align our fix timeline with Vendor1."
        ),
        in_reply_to=(
            coordinator_note.id_ if coordinator_note is not None else None
        ),
    )

    logger.info(
        "✓ Notes exchange complete (four notes committed to case ledger)"
    )
    return question_note, vendor_reply, coordinator_note, vendor2_note


def _phase_fix_lifecycle(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    vendor2: as_Actor,
    vendor2_in_vendor2: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Advance both vendors through fix-ready and fix-deployed paths."""
    logger.info("─" * 80)
    logger.info(
        "Phase 5: Fix lifecycle — both vendors: VFd (fix ready); vendors stop at VFd (CSB-15-002)"
    )
    logger.info("─" * 80)

    with demo_gate(
        "vendor RM ∈ {ACCEPTED,DEFERRED,CLOSED} before notify-fix-ready (CSB-18-001)"
    ):
        wait_for_participant_rm_state(
            client=vendor_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={RM.ACCEPTED, RM.DEFERRED, RM.CLOSED},
        )
        actor_notifies_fix_ready(
            client=vendor_client,
            actor=vendor_in_vendor,
            case_id=case.id_,
        )
        with demo_check(
            "Vendor1 participant vfd_state transitions to VFd or VFD"
        ):
            wait_for_participant_vfd_state(
                client=vendor_client,
                case_id=case.id_,
                actor_id=vendor.id_,
                expected_states={CS_vfd.VFd, CS_vfd.VFD},
            )

    with demo_gate(
        "vendor2 RM ∈ {ACCEPTED,DEFERRED,CLOSED} before notify-fix-ready (CSB-18-001)"
    ):
        wait_for_participant_rm_state(
            client=vendor2_client,
            case_id=case.id_,
            actor_id=vendor2.id_,
            expected_states={RM.ACCEPTED, RM.DEFERRED, RM.CLOSED},
        )
        actor_notifies_fix_ready(
            client=vendor2_client,
            actor=vendor2_in_vendor2,
            case_id=case.id_,
        )
        with demo_check(
            "Vendor2 participant vfd_state transitions to VFd or VFD"
        ):
            wait_for_participant_vfd_state(
                client=vendor2_client,
                case_id=case.id_,
                actor_id=vendor2.id_,
                expected_states={CS_vfd.VFd, CS_vfd.VFD},
            )

    with demo_check(
        "Finder replica shows both vendors CS include F (fix ready)"
    ):
        wait_for_participant_vfd_state(
            client=vendor_client,
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
            receiver_client=vendor_client,
            reporter_client=finder_client,
            case_id=case.id_,
            receiver_actor_id=vendor.id_,
        )

    with demo_check(
        "Finder replica shows both vendors CS include F (fix ready) — vendors stop at VFd"
    ):
        wait_for_participant_vfd_state(
            client=vendor_client,
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
            receiver_client=vendor_client,
            reporter_client=finder_client,
            case_id=case.id_,
            receiver_actor_id=vendor.id_,
        )


def _phase_publication(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    vendor2: as_Actor,
    vendor2_in_vendor2: as_Actor,
    finder: as_Actor,
    finder_in_finder: as_Actor,
    coordinator: as_Actor,
    coordinator_in_coordinator: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Run publication notifications and verify public disclosure state."""
    logger.info("─" * 80)
    logger.info(
        "Phase 6: Publication — CS.VFDPxa + embargo teardown (EM.EXITED)"
    )
    logger.info("─" * 80)

    # Realistic CVD publication order: vendors publish their advisories first,
    # then Finder may publish an independent writeup, then Coordinator publishes
    # last as the CASE_OWNER whose notify-published triggers embargo teardown
    # (DEMOMA-07-003 step 4).
    actor_notifies_published(
        client=vendor_client,
        actor=vendor_in_vendor,
        case_id=case.id_,
    )
    actor_notifies_published(
        client=vendor2_client,
        actor=vendor2_in_vendor2,
        case_id=case.id_,
    )
    actor_notifies_published(
        client=finder_client,
        actor=finder_in_finder,
        case_id=case.id_,
    )

    # Coordinator publishes last — as CASE_OWNER this triggers embargo teardown.
    actor_notifies_published(
        client=coordinator_client,
        actor=coordinator_in_coordinator,
        case_id=case.id_,
    )

    with demo_check(
        "Embargo terminated (EM.EXITED) after Coordinator (CASE_OWNER) reports published"
    ):
        wait_for_case_em_terminated(
            client=coordinator_client,
            case_id=case.id_,
        )

    with demo_check(
        "All replicas CS.VFdPxa, EM.EXITED, all participants public-aware"
    ):
        for _label, client in [
            ("coordinator", coordinator_client),
            ("vendor", vendor_client),
            ("vendor2", vendor2_client),
            ("finder", finder_client),
        ]:
            wait_for_case_em_terminated(
                client=client,
                case_id=case.id_,
            )
        wait_for_participant_vfd_state(
            client=vendor_client,
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
            receiver_client=vendor_client,
            reporter_client=finder_client,
            case_id=case.id_,
            receiver_actor_id=vendor.id_,
        )


def _phase_case_closure(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    vendor2: as_Actor,
    vendor2_in_vendor2: as_Actor,
    finder: as_Actor,
    finder_in_finder: as_Actor,
    coordinator: as_Actor,
    coordinator_in_coordinator: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Close the case from all four participants and verify terminal state."""
    logger.info("─" * 80)
    logger.info("Phase 7: Case closure — all participants RM.CLOSED")
    logger.info("─" * 80)

    actor_closes_case(
        client=vendor_client,
        actor=vendor_in_vendor,
        case_id=case.id_,
    )
    actor_closes_case(
        client=vendor2_client,
        actor=vendor2_in_vendor2,
        case_id=case.id_,
    )
    actor_closes_case(
        client=finder_client,
        actor=finder_in_finder,
        case_id=case.id_,
    )
    # Coordinator is the case owner and closes last (case owner closes last).
    actor_closes_case(
        client=coordinator_client,
        actor=coordinator_in_coordinator,
        case_id=case.id_,
    )

    with demo_check("All participants RM.CLOSED on all replicas"):
        wait_for_all_participants_rm_closed(
            client=vendor_client,
            case_id=case.id_,
        )
        wait_for_all_participants_rm_closed(
            client=finder_client,
            case_id=case.id_,
        )
        verify_case_closed(
            receiver_client=vendor_client,
            reporter_client=finder_client,
            case_id=case.id_,
        )

    with demo_check(
        "close_case entry present on authoritative actor (vendor1)"
    ):
        wait_for_event_type_in_ledger(
            client=vendor_client,
            case_id=case.id_,
            event_type="close_case",
        )
    vendor_entries = _get_log_entries_for_case(vendor_client, case.id_)
    if vendor_entries:
        vendor_tail = max(vendor_entries, key=lambda e: e["log_index"])
        vendor_tail_index: int = vendor_tail["log_index"]
        vendor_tail_hash: str = vendor_tail["entry_hash"]
        logger.info(
            "Waiting for replicas to receive vendor1 tail after closure"
            " (hash=%s… index=%d)",
            vendor_tail_hash[:16],
            vendor_tail_index,
        )
        for replica_client, label in [
            (finder_client, "Finder"),
            (coordinator_client, "Coordinator"),
            (vendor2_client, "Vendor2"),
        ]:
            with demo_check(f"{label} ledger coverage (close phase)"):
                # Temporal (EDF-06-006): Vendor2 joined Phase 3 so may still
                # lag; causal-gate migration in #2202.
                timeout = 45.0 if label == "Vendor2" else 15.0
                wait_for_contiguous_ledger_coverage(
                    client=replica_client,
                    case_id=case.id_,
                    expected_tail_index=vendor_tail_index,
                    timeout_seconds=timeout,
                )


def _phase_dump_case_ledgers(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    case: as_VulnerabilityCase,
    demo_name: str = "fvcv-handoff",
) -> None:
    """Dump case ledger entries from each actor container to JSONL files.

    Thin scenario-specific wrapper over
    :func:`~vultron.demo.helpers.ledger_dump.dump_case_ledgers`, which owns the
    per-actor export, the 404 handling, and the dump manifest. This function
    only names FVCV-handoff's participants and where each ledger lives.
    """
    # Route keys come from each client's own actor id, not its display
    # name: the key selects the store (ADR-0073), so a literal is right
    # only while the scenario seeds deterministic named ids.
    targets = [
        LedgerDumpTarget(
            "finder", finder_client, replica_route_key(finder_client, "finder")
        ),
        LedgerDumpTarget(
            "vendor", vendor_client, replica_route_key(vendor_client, "vendor")
        ),
        LedgerDumpTarget(
            "coordinator",
            coordinator_client,
            replica_route_key(coordinator_client, "coordinator"),
        ),
        LedgerDumpTarget(
            "vendor2",
            vendor2_client,
            replica_route_key(vendor2_client, "vendor2"),
        ),
    ]
    # The case-actor is a sub-actor inside the vendor1 container.
    case_actor_route_key = resolve_case_actor_route_key(case)
    if case_actor_route_key is not None:
        targets.append(
            LedgerDumpTarget("case-actor", vendor_client, case_actor_route_key)
        )

    dump_case_ledgers(demo_name=demo_name, case=case, targets=targets)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def run_fvcv_handoff_demo(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    finder_id: str | None = None,
    vendor_id: str | None = None,
    coordinator_id: str | None = None,
    case_actor_id: str | None = None,
    vendor2_id: str | None = None,
) -> None:
    """Orchestrate the FVCV-handoff CVD workflow."""
    with scenario_harness("fvcv-handoff") as harness:
        logger.info("=" * 80)
        logger.info(
            "FVCV-HANDOFF DEMO: Finder + Vendor1 → Coordinator (ownership) + Vendor2"
        )
        logger.info("=" * 80)
        logger.info("Finder container:      %s", finder_client.base_url)
        logger.info("Vendor1 container:     %s", vendor_client.base_url)
        logger.info("Coordinator container: %s", coordinator_client.base_url)
        logger.info("CaseActor container:   %s", case_actor_client.base_url)
        logger.info("Vendor2 container:     %s", vendor2_client.base_url)

        (
            finder,
            vendor,
            vendor_in_vendor,
            coordinator,
            coordinator_in_coordinator,
            vendor2,
            report,
            offer,
            case,
        ) = _phase_report_submission(
            finder_client,
            vendor_client,
            coordinator_client,
            case_actor_client,
            vendor2_client,
            finder_id,
            vendor_id,
            coordinator_id,
            vendor2_id,
        )

        # Register the dump as soon as there is a case to dump, so every phase
        # below can fail without costing us the ledgers (ISSUE-2239).
        harness.dump_with(
            lambda: _phase_dump_case_ledgers(
                finder_client=finder_client,
                vendor_client=vendor_client,
                coordinator_client=coordinator_client,
                vendor2_client=vendor2_client,
                case=case,
                demo_name=harness.demo_name,
            )
        )

        # The case's CaseActor is the container-level identity of whichever node
        # first received the report (ADR-0041, CP-08-003) — not a per-case
        # sub-actor, and not necessarily the standalone case-actor service.
        # After a handoff it is on a container that no longer owns the case, so
        # which one it is cannot be assumed or constructed from a slug: read it
        # off the case's own participants.
        dynamic_case_actor_id = find_case_actor_participant_id(
            vendor_client, case.id_
        )
        if dynamic_case_actor_id is None:
            raise AssertionError(
                "CaseActor participant not found in case — cannot route Vendor2 Accept"
            )
        logger.info("CaseActor participant ID: %s", dynamic_case_actor_id)

        vendor2_in_vendor2 = get_actor_by_id(vendor2_client, vendor2.id_)
        finder_in_finder = get_actor_by_id(finder_client, finder.id_)

        case = _phase_ownership_handoff(
            vendor_client=vendor_client,
            coordinator_client=coordinator_client,
            finder=finder,
            vendor=vendor,
            vendor_in_vendor=vendor_in_vendor,
            coordinator=coordinator,
            coordinator_in_coordinator=coordinator_in_coordinator,
            case=case,
        )

        _phase_coordinator_invites_vendor2(
            finder_client=finder_client,
            vendor_client=vendor_client,
            coordinator_client=coordinator_client,
            vendor2_client=vendor2_client,
            finder=finder,
            vendor=vendor,
            coordinator=coordinator,
            coordinator_in_coordinator=coordinator_in_coordinator,
            case_actor_id=dynamic_case_actor_id,
            vendor2=vendor2,
            vendor2_in_vendor2=vendor2_in_vendor2,
            case=case,
            offer=offer,
            report=report,
        )

        # Verify case active now that all participants have joined.
        with demo_check(
            "M1: required participants (≥5), EM.ACTIVE, finder + coordinator have replicas"
        ):
            verify_case_active(
                receiver_client=vendor_client,
                reporter_client=finder_client,
                case_id=case.id_,
                receiver_actor_id=vendor.id_,
                reporter_actor_id=finder.id_,
            )

        _phase_sync_verification(
            finder_client,
            vendor_client,
            coordinator_client,
            vendor2_client,
            vendor,
            finder,
            coordinator,
            vendor2,
            case,
        )
        _phase_notes_exchange(
            finder_client,
            vendor_client,
            coordinator_client,
            vendor2_client,
            finder_in_finder,
            vendor_in_vendor,
            coordinator_in_coordinator,
            vendor2_in_vendor2,
            case,
        )
        _phase_fix_lifecycle(
            finder_client,
            vendor_client,
            vendor2_client,
            vendor,
            vendor_in_vendor,
            vendor2,
            vendor2_in_vendor2,
            case,
        )
        _phase_publication(
            finder_client,
            vendor_client,
            coordinator_client,
            vendor2_client,
            vendor,
            vendor_in_vendor,
            vendor2,
            vendor2_in_vendor2,
            finder,
            finder_in_finder,
            coordinator,
            coordinator_in_coordinator,
            case,
        )
        _phase_case_closure(
            finder_client,
            vendor_client,
            coordinator_client,
            vendor2_client,
            vendor,
            vendor_in_vendor,
            vendor2,
            vendor2_in_vendor2,
            finder,
            finder_in_finder,
            coordinator,
            coordinator_in_coordinator,
            case,
        )

    logger.info("=" * 80)
    logger.info(
        "FVCV-HANDOFF DEMO COMPLETE ✓  (ownership transfer + VFDPxa full lifecycle)"
    )
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(
    skip_health_check: bool = False,
    finder_url: str | None = None,
    vendor_url: str | None = None,
    coordinator_url: str | None = None,
    case_actor_url: str | None = None,
    vendor2_url: str | None = None,
    finder_id: str | None = None,
    vendor_id: str | None = None,
    coordinator_id: str | None = None,
    case_actor_id: str | None = None,
    vendor2_id: str | None = None,
) -> None:
    """Entry point for the FVCV-handoff CVD workflow demo.

    Args:
        skip_health_check: Skip the server availability check.
        finder_url: Override base URL for the Finder container.
        vendor_url: Override base URL for the Vendor1 container.
        coordinator_url: Override base URL for the Coordinator container.
        case_actor_url: Override base URL for the CaseActor container.
        vendor2_url: Override base URL for the Vendor2 container.
        finder_id: Optional deterministic URI for the Finder actor.
        vendor_id: Optional deterministic URI for the Vendor1 actor.
        coordinator_id: Optional deterministic URI for the Coordinator actor.
        case_actor_id: Optional deterministic URI for the CaseActor actor.
        vendor2_id: Optional deterministic URI for the Vendor2 actor.
    """
    f_url = finder_url or FINDER_BASE_URL
    v_url = vendor_url or VENDOR_BASE_URL
    c_url = coordinator_url or COORDINATOR_BASE_URL
    ca_url = case_actor_url or CASE_ACTOR_BASE_URL
    v2_url = vendor2_url or VENDOR2_BASE_URL

    finder_client = DataLayerClient(base_url=f_url)
    vendor_client = DataLayerClient(base_url=v_url)
    coordinator_client = DataLayerClient(base_url=c_url)
    case_actor_client = DataLayerClient(
        base_url=ca_url, actor_id=case_actor_id_on(ca_url)
    )
    vendor2_client = DataLayerClient(base_url=v2_url)

    if not skip_health_check:
        targets: list[tuple[str, DataLayerClient]] = [
            ("Finder", finder_client),
            ("Vendor1", vendor_client),
            ("Coordinator", coordinator_client),
            ("CaseActor", case_actor_client),
            ("Vendor2", vendor2_client),
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

    # scenario_harness() inside run_fvcv_handoff_demo() owns the failure
    # accumulator: it resets it, always dumps the case ledgers, and asserts
    # success — so a failure here never costs us the artifacts (ISSUE-2239).
    run_fvcv_handoff_demo(
        finder_client=finder_client,
        vendor_client=vendor_client,
        coordinator_client=coordinator_client,
        case_actor_client=case_actor_client,
        vendor2_client=vendor2_client,
        finder_id=finder_id,
        vendor_id=vendor_id,
        coordinator_id=coordinator_id,
        case_actor_id=case_actor_id,
        vendor2_id=vendor2_id,
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
