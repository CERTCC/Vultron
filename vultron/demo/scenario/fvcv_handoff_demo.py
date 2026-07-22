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
    as_TransitiveActivity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
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
from vultron.demo.helpers.actions import (
    actor_closes_case,
    actor_notifies_fix_deployed,
    actor_notifies_fix_ready,
    actor_notifies_published,
)
from vultron.demo.helpers.milestones import (
    verify_case_active,
    verify_case_closed,
    verify_fix_deployed,
    verify_fix_ready,
    verify_publicly_disclosed,
)
from vultron.demo.helpers.polling import (
    wait_for_all_participants_rm_closed,
    wait_for_case_em_terminated,
    wait_for_case_on_container,
    wait_for_case_participants,
    wait_for_contiguous_ledger_coverage,
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
    find_case_for_offer,
    receiver_engages_case,
    receiver_validates_report,
    reporter_submits_report,
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
VENDOR2_ACTOR_ID = "http://vendor2:7999/api/v2/actors/vendor2"


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
# Polling helpers
# ---------------------------------------------------------------------------


def _wait_for_case_attributed_to(
    client: DataLayerClient,
    case_id: str,
    expected_attributed_to: str,
    timeout_seconds: float = 20.0,
    poll_interval: float = 0.5,
) -> None:
    """Poll until *case_id*'s ``attributed_to`` field equals *expected_attributed_to*.

    Raises:
        AssertionError: If the field does not match within *timeout_seconds*.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            case_data = client.get(f"/datalayer/{case_id}")
            if isinstance(case_data, dict):
                attributed_to = case_data.get("attributed_to")
                if isinstance(attributed_to, dict):
                    attributed_to = attributed_to.get("id")
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
        f"Timed out waiting for case {case_id!r} attributed_to={expected_attributed_to!r}"
        f" on container {client.base_url}"
    )


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
    receiver_validates_report(
        receiver_client=vendor_client,
        receiver=vendor_in_vendor,
        offer_id=offer.id_,
    )

    with demo_check("VulnerabilityCase exists in Vendor1's DataLayer"):
        case = find_case_for_offer(vendor_client, offer.id_)
        if case is None:
            raise AssertionError(
                "Expected VulnerabilityCase to be created after validate-report"
            )
        logger.info("Case created: %s", case.id_)

    receiver_engages_case(
        receiver_client=vendor_client,
        receiver=vendor_in_vendor,
        case_id=case.id_,
    )

    # Wait for initial participants (Finder + Vendor1 + CaseActor).
    wait_for_case_participants(
        vendor_client=vendor_client,
        case_id=case.id_,
        expected_count=3,
    )

    case = as_VulnerabilityCase.model_validate(
        vendor_client.get(f"/datalayer/{case.id_}")
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

    # Deliver the invite to Coordinator's inbox.
    with demo_step("Delivering invite to Coordinator's inbox"):
        post_to_inbox_and_wait(
            coordinator_client, coordinator_in_coordinator.id_, invite
        )

    with demo_check("Coordinator invite stored in Coordinator's DataLayer"):
        verify_object_stored(coordinator_client, invite.id_)

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
        expected_count=4,
    )
    logger.info("Coordinator has joined the case")

    # Vendor1 offers ownership transfer to Coordinator (TRIG-11-001).
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

    # Deliver the ownership transfer offer to Coordinator's inbox.
    with demo_step(
        "Delivering ownership transfer offer to Coordinator's inbox"
    ):
        post_to_inbox_and_wait(
            coordinator_client, coordinator_in_coordinator.id_, ownership_offer
        )

    with demo_check(
        "Ownership transfer offer arrived in Coordinator's DataLayer (TRIG-11-001)"
    ):
        verify_object_stored(coordinator_client, ownership_offer.id_)

    ownership_offer_id = ownership_offer.id_
    logger.info("Ownership transfer offer ID: %s", ownership_offer_id)

    # Coordinator accepts the ownership transfer (TRIG-11-002).
    with demo_step(
        "Coordinator accepts case ownership transfer (TRIG-11-002)"
    ):
        post_to_trigger(
            client=coordinator_client,
            actor_id=coordinator_in_coordinator.id_,
            behavior="accept-case-ownership-transfer",
            body={"offer_id": ownership_offer_id},
        )
    logger.info("Coordinator sent Accept(Offer(VulnerabilityCase))")

    # Verify Vendor1's case now shows Coordinator as attributed_to.
    with demo_check(
        "Case attributed_to updated to Coordinator on Vendor1's DataLayer (AC-1)"
    ):
        _wait_for_case_attributed_to(
            client=vendor_client,
            case_id=case.id_,
            expected_attributed_to=coordinator.id_,
        )

    # Also verify on Coordinator's side.
    with demo_check(
        "Case attributed_to updated to Coordinator on Coordinator's DataLayer"
    ):
        _wait_for_case_attributed_to(
            client=coordinator_client,
            case_id=case.id_,
            expected_attributed_to=coordinator.id_,
        )

    logger.info(
        "✓ Ownership transfer complete: Coordinator is now CASE_OWNER for %s",
        case.id_,
    )

    case = as_VulnerabilityCase.model_validate(
        vendor_client.get(f"/datalayer/{case.id_}")
    )
    return case


def _phase_coordinator_invites_vendor2(
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    coordinator: as_Actor,
    coordinator_in_coordinator: as_Actor,
    case_actor: as_Actor,
    vendor2: as_Actor,
    vendor2_in_vendor2: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Coordinator (new CASE_OWNER) invites Vendor2 and Vendor2 joins the case."""
    logger.info("─" * 80)
    logger.info("Phase 3: Coordinator invites Vendor2 (AC-2)")
    logger.info("─" * 80)

    # Coordinator directly invites Vendor2 as the new CASE_OWNER (AC-2).
    with demo_step("Coordinator invites Vendor2 to the case"):
        invite_result = post_to_trigger(
            client=coordinator_client,
            actor_id=coordinator_in_coordinator.id_,
            behavior="invite-actor-to-case",
            body={
                "case_id": case.id_,
                "invitee_id": vendor2.id_,
            },
        )
    invite = as_TransitiveActivity.model_validate(invite_result["activity"])
    logger.info("Vendor2 invite created by Coordinator: %s", invite.id_)

    # Deliver the invite to Vendor2's inbox.
    with demo_step("Delivering invite to Vendor2's inbox"):
        post_to_inbox_and_wait(vendor2_client, vendor2_in_vendor2.id_, invite)

    with demo_check("Vendor2 invite stored in Vendor2's DataLayer"):
        verify_object_stored(vendor2_client, invite.id_)

    # Vendor2 accepts the invite.
    with demo_step("Vendor2 accepts the case invitation"):
        accept_result = post_to_trigger(
            client=vendor2_client,
            actor_id=vendor2_in_vendor2.id_,
            behavior="accept-case-invite",
            body={"invite_id": invite.id_},
        )
    accept = as_TransitiveActivity.model_validate(accept_result["activity"])
    logger.info("Vendor2 sent Accept(Invite): %s", accept.id_)

    # Deliver Accept to CaseActor so it can commit the join ledger entry
    # and fan out to all existing participants (including Vendor1/Finder).
    # The invite.actor is Coordinator which lacks trusted_case_actor_id, so
    # we explicitly route the Accept to the CaseActor container (PCR-08-008).
    with demo_step("Delivering Vendor2 accept to CaseActor inbox"):
        post_to_inbox_and_wait(case_actor_client, case_actor.id_, accept)
    with demo_check("Accept activity stored in CaseActor DataLayer"):
        verify_object_stored(case_actor_client, accept.id_)
    logger.info("Vendor2 Accept delivered to CaseActor")

    # Wait for Vendor2's case replica.
    with demo_check("Vendor2's DataLayer received case replica (AC-2)"):
        wait_for_case_on_container(
            client=vendor2_client,
            case_id=case.id_,
            timeout_seconds=20.0,
        )
    logger.info("Vendor2 received case replica")

    # 5 participants: Finder + Vendor1 + Coordinator + Vendor2 + CaseActor
    wait_for_case_participants(
        vendor_client=vendor_client,
        case_id=case.id_,
        expected_count=5,
        timeout_seconds=20.0,
    )
    logger.info("✓ Vendor2 joined case (%d participants)", 5)


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
            wait_for_contiguous_ledger_coverage(
                client=replica_client,
                case_id=case.id_,
                expected_tail_index=vendor_tail_index,
            )
            logger.info("  %s ledger synchronized", label)

    for replica_client in (finder_client, coordinator_client, vendor2_client):
        wait_for_case_participants(
            vendor_client=replica_client,
            case_id=case.id_,
            expected_count=5,
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
        "Phase 5: Fix lifecycle — both vendors: VFd (fix ready) → VFD (fix deployed)"
    )
    logger.info("─" * 80)

    actor_notifies_fix_ready(
        client=vendor_client,
        actor=vendor_in_vendor,
        case_id=case.id_,
    )

    with demo_check("Vendor1 participant vfd_state transitions to VFd or VFD"):
        wait_for_participant_vfd_state(
            client=vendor_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vfd.VFd, CS_vfd.VFD},
        )

    actor_notifies_fix_ready(
        client=vendor2_client,
        actor=vendor2_in_vendor2,
        case_id=case.id_,
    )

    with demo_check("Vendor2 participant vfd_state transitions to VFd or VFD"):
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

    actor_notifies_fix_deployed(
        client=vendor_client,
        actor=vendor_in_vendor,
        case_id=case.id_,
    )
    actor_notifies_fix_deployed(
        client=vendor2_client,
        actor=vendor2_in_vendor2,
        case_id=case.id_,
    )

    with demo_check(
        "Finder replica shows both vendors CS include D (fix deployed)"
    ):
        wait_for_participant_vfd_state(
            client=finder_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vfd.VFD},
        )
        verify_fix_deployed(
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

    actor_notifies_published(
        client=vendor_client,
        actor=vendor_in_vendor,
        case_id=case.id_,
    )

    with demo_check(
        "Embargo terminated (EM.EXITED) after Vendor1 reports published"
    ):
        wait_for_case_em_terminated(
            client=vendor_client,
            case_id=case.id_,
        )

    actor_notifies_published(
        client=vendor2_client,
        actor=vendor2_in_vendor2,
        case_id=case.id_,
    )
    actor_notifies_published(
        client=coordinator_client,
        actor=coordinator_in_coordinator,
        case_id=case.id_,
    )
    actor_notifies_published(
        client=finder_client,
        actor=finder_in_finder,
        case_id=case.id_,
    )

    with demo_check(
        "All replicas CS.VFDPxa, EM.EXITED, all participants public-aware"
    ):
        wait_for_case_em_terminated(
            client=finder_client,
            case_id=case.id_,
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
        client=coordinator_client,
        actor=coordinator_in_coordinator,
        case_id=case.id_,
    )
    actor_closes_case(
        client=finder_client,
        actor=finder_in_finder,
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
        for replica_client in (
            finder_client,
            coordinator_client,
            vendor2_client,
        ):
            wait_for_contiguous_ledger_coverage(
                client=replica_client,
                case_id=case.id_,
                expected_tail_index=vendor_tail_index,
            )


def _phase_dump_case_ledgers(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
    vendor2: as_Actor,
    case: as_VulnerabilityCase,
    demo_name: str = "fvcv-handoff",
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
        ("vendor", vendor_client, "vendor"),
        ("coordinator", coordinator_client, "coordinator"),
        ("vendor2", vendor2_client, "vendor2"),
    ]
    if case_actor_sub_actor_key is not None:
        actors.append(("case-actor", vendor_client, case_actor_sub_actor_key))

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

    case_actor = get_actor_by_id(
        case_actor_client, case_actor_id or CASE_ACTOR_ACTOR_ID
    )
    vendor2_in_vendor2 = get_actor_by_id(vendor2_client, vendor2.id_)
    finder_in_finder = get_actor_by_id(finder_client, finder.id_)

    case = _phase_ownership_handoff(
        vendor_client=vendor_client,
        coordinator_client=coordinator_client,
        vendor=vendor,
        vendor_in_vendor=vendor_in_vendor,
        coordinator=coordinator,
        coordinator_in_coordinator=coordinator_in_coordinator,
        case=case,
    )

    _phase_coordinator_invites_vendor2(
        vendor_client=vendor_client,
        coordinator_client=coordinator_client,
        case_actor_client=case_actor_client,
        vendor2_client=vendor2_client,
        coordinator=coordinator,
        coordinator_in_coordinator=coordinator_in_coordinator,
        case_actor=case_actor,
        vendor2=vendor2,
        vendor2_in_vendor2=vendor2_in_vendor2,
        case=case,
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
    _phase_dump_case_ledgers(
        finder_client=finder_client,
        vendor_client=vendor_client,
        coordinator_client=coordinator_client,
        vendor2_client=vendor2_client,
        finder=finder,
        vendor=vendor,
        coordinator=coordinator,
        vendor2=vendor2_in_vendor2,
        case=case,
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
    reset_demo_failures()

    f_url = finder_url or FINDER_BASE_URL
    v_url = vendor_url or VENDOR_BASE_URL
    c_url = coordinator_url or COORDINATOR_BASE_URL
    ca_url = case_actor_url or CASE_ACTOR_BASE_URL
    v2_url = vendor2_url or VENDOR2_BASE_URL

    finder_client = DataLayerClient(base_url=f_url)
    vendor_client = DataLayerClient(base_url=v_url)
    coordinator_client = DataLayerClient(base_url=c_url)
    case_actor_client = DataLayerClient(base_url=ca_url)
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

    try:
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
    finally:
        assert_demo_success()


if __name__ == "__main__":
    setup_demo_logging()
    main()
