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

"""FCV three-actor CVD workflow demo (Finder + Coordinator + Vendor).

Orchestrates the full VFDPxa lifecycle across four containers: Finder,
Coordinator (CASE_OWNER), Vendor, and CaseActor.

Coordinator receives the Finder's report, creates the case (holding
CASE_OWNER), the CaseActor service actor holds CASE_MANAGER.  Coordinator
invites Finder into the case, then directly invites Vendor
(``invite-actor-to-case``).  Vendor accepts the report and embargo, advances
through the fix lifecycle (VFD), and all three participants coordinate to
VFDPxa closure.  Coordinator closes the case.

Spec: DEMOMA-12 (GitHub issue #1593).
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
    as_Offer,
    as_TransitiveActivity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
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
from vultron.demo.helpers.notes import participant_adds_note_to_case
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
    seed_containers_fcv,
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

# Deterministic actor IDs from docker-compose-multi-actor.yml (D5-1-G3).
FINDER_ACTOR_ID = "http://finder:7999/api/v2/actors/finder"
COORDINATOR_ACTOR_ID = "http://coordinator:7999/api/v2/actors/coordinator"
VENDOR_ACTOR_ID = "http://vendor:7999/api/v2/actors/vendor"
CASE_ACTOR_ACTOR_ID = "http://case-actor:7999/api/v2/actors/case-actor"


def reset_containers(
    finder_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient | None = None,
) -> None:
    """Reset FCV containers to a clean baseline."""
    targets: list[tuple[str, DataLayerClient]] = [
        ("Finder", finder_client),
        ("Coordinator", coordinator_client),
        ("Vendor", vendor_client),
    ]
    if case_actor_client is not None:
        targets.append(("CaseActor", case_actor_client))
    _reset_containers(targets, reset_fn=reset_datalayer)


# ---------------------------------------------------------------------------
# Polling helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Phase helpers
# ---------------------------------------------------------------------------


def _phase_report_submission(
    finder_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient | None,
    finder_id: str | None,
    coordinator_id: str | None,
    vendor_id: str | None,
) -> tuple[
    as_Actor,
    as_Actor,
    as_Actor,
    as_Actor,
    as_Actor,
    as_VulnerabilityReport,
    as_Offer,
    as_VulnerabilityCase,
]:
    """Reset, seed, Finder submits report to Coordinator, Coordinator engages case."""
    logger.info("─" * 80)
    logger.info("Phase 1: Report submission — Finder → Coordinator")
    logger.info("─" * 80)

    reset_containers(
        finder_client=finder_client,
        coordinator_client=coordinator_client,
        vendor_client=vendor_client,
        case_actor_client=case_actor_client,
    )

    with demo_step("Seeding Finder, Coordinator, and Vendor containers"):
        finder, coordinator, vendor = seed_containers_fcv(
            finder_client=finder_client,
            coordinator_client=coordinator_client,
            vendor_client=vendor_client,
            reporter_actor_id=finder_id,
            coordinator_actor_id=coordinator_id,
            vendor_actor_id=vendor_id,
        )

    coordinator_in_coordinator = get_actor_by_id(
        coordinator_client, coordinator.id_
    )

    # Finder submits report to Coordinator's inbox.
    report, offer = reporter_submits_report(
        receiver_client=coordinator_client,
        reporter=finder,
        receiver=coordinator_in_coordinator,
        reporter_client=finder_client,
    )
    receiver_validates_report(
        receiver_client=coordinator_client,
        receiver=coordinator_in_coordinator,
        offer_id=offer.id_,
    )

    with demo_check("VulnerabilityCase created in Coordinator's DataLayer"):
        case = find_case_for_offer(coordinator_client, offer.id_)
        if case is None:
            raise AssertionError(
                "Expected VulnerabilityCase after validate-report on Coordinator"
            )
        logger.info("Case created: %s", case.id_)

    # Coordinator engages the case (RM→ACCEPTED), holding CASE_OWNER.
    receiver_engages_case(
        receiver_client=coordinator_client,
        receiver=coordinator_in_coordinator,
        case_id=case.id_,
    )

    # Wait for Coordinator + Finder + CaseActor (3 participants) before
    # inviting Vendor.
    wait_for_case_participants(
        vendor_client=coordinator_client,
        case_id=case.id_,
        expected_count=3,
    )

    with demo_check("M1: ≥3 participants, EM.ACTIVE, Finder has replica"):
        verify_case_active(
            receiver_client=coordinator_client,
            reporter_client=finder_client,
            case_id=case.id_,
            receiver_actor_id=coordinator.id_,
            reporter_actor_id=finder.id_,
        )

    case = as_VulnerabilityCase.model_validate(
        coordinator_client.get(f"/datalayer/{case.id_}")
    )
    finder_in_finder = get_actor_by_id(finder_client, finder.id_)
    return (
        finder,
        finder_in_finder,
        coordinator,
        coordinator_in_coordinator,
        vendor,
        report,
        offer,
        case,
    )


def _phase_invite_vendor(
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_in_coordinator: as_Actor,
    vendor: as_Actor,
    case: as_VulnerabilityCase,
) -> as_Actor:
    """Coordinator invites Vendor directly; Vendor accepts.

    DEMOMA-12-004: Coordinator is CASE_OWNER so uses invite-actor-to-case
    directly (not the ADR-0026 suggest/approve chain).
    """
    logger.info("─" * 80)
    logger.info("Phase 2: Coordinator invites Vendor")
    logger.info("─" * 80)

    with demo_step("Coordinator invites Vendor with CVDRole.VENDOR"):
        invite_result = post_to_trigger(
            client=coordinator_client,
            actor_id=coordinator_in_coordinator.id_,
            behavior="invite-actor-to-case",
            body={
                "case_id": case.id_,
                "invitee_id": vendor.id_,
                "roles": ["vendor"],
            },
        )
    invite = as_TransitiveActivity.model_validate(invite_result["activity"])
    logger.info("Vendor invite created: %s", invite.id_)

    vendor_in_vendor = get_actor_by_id(vendor_client, vendor.id_)

    with demo_step("Delivering invite to Vendor's inbox"):
        post_to_inbox_and_wait(vendor_client, vendor_in_vendor.id_, invite)

    with demo_check("Vendor invite stored in Vendor's DataLayer"):
        verify_object_stored(vendor_client, invite.id_)

    with demo_step("Vendor accepts the case invitation"):
        post_to_trigger(
            client=vendor_client,
            actor_id=vendor_in_vendor.id_,
            behavior="accept-case-invite",
            body={"invite_id": invite.id_},
        )
    logger.info("Vendor sent Accept(Invite) to CaseActor")

    # Vendor's replica is seeded by CaseActor's Announce(VulnerabilityCase).
    with demo_check("Vendor's DataLayer received case replica"):
        wait_for_case_on_container(
            client=vendor_client,
            case_id=case.id_,
            timeout_seconds=20.0,
        )
    logger.info("Vendor received case replica")

    # 4 participants: Finder + Coordinator + Vendor + CaseActor
    wait_for_case_participants(
        vendor_client=coordinator_client,
        case_id=case.id_,
        expected_count=4,
        timeout_seconds=20.0,
    )
    logger.info("✓ M2: Vendor joined case (4 participants)")

    return vendor_in_vendor


def _phase_sync_verification(
    finder_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    finder: as_Actor,
    coordinator: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Verify SYNC-2 replication for Finder and Vendor replicas."""
    logger.info("─" * 80)
    logger.info("Phase 3: Replica synchronization verification")
    logger.info("─" * 80)

    coordinator_entries = _get_log_entries_for_case(
        coordinator_client, case.id_
    )
    if coordinator_entries:
        coord_tail = max(coordinator_entries, key=lambda e: e["log_index"])
        coord_tail_index: int = coord_tail["log_index"]
        coord_tail_hash: str = coord_tail["entry_hash"]
        logger.info(
            "Waiting for replicas to sync Coordinator tail (hash=%s… index=%d)",
            coord_tail_hash[:16],
            coord_tail_index,
        )
        for replica_client, label in [
            (finder_client, "Finder"),
            (vendor_client, "Vendor"),
        ]:
            wait_for_contiguous_ledger_coverage(
                client=replica_client,
                case_id=case.id_,
                expected_tail_index=coord_tail_index,
            )
            logger.info("  %s ledger synchronized", label)

    for replica_client in (finder_client, vendor_client):
        wait_for_case_participants(
            vendor_client=replica_client,
            case_id=case.id_,
            expected_count=4,
        )

    with demo_check("Finder replica matches authoritative Coordinator state"):
        verify_replica_state(
            auth_client=coordinator_client,
            replica_client=finder_client,
            case_id=case.id_,
            vendor_actor_id=coordinator.id_,
            reporter_actor_id=finder.id_,
        )

    with demo_check("Vendor replica matches authoritative Coordinator state"):
        verify_replica_state(
            auth_client=coordinator_client,
            replica_client=vendor_client,
            case_id=case.id_,
            vendor_actor_id=coordinator.id_,
            reporter_actor_id=finder.id_,
        )

    logger.info("✓ M3: All replicas synchronized (SYNC-2 verified)")


def _phase_notes_exchange(
    finder_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    finder_in_finder: as_Actor,
    coordinator_in_coordinator: as_Actor,
    vendor_in_vendor: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Run a three-way note exchange among all participants."""
    logger.info("─" * 80)
    logger.info("Phase 4: Notes exchange")
    logger.info("─" * 80)

    question_note = participant_adds_note_to_case(
        posting_client=finder_client,
        watching_client=coordinator_client,
        poster=finder_in_finder,
        case=case,
        note_name="Question from Finder",
        note_content=(
            "Could you share the timeline for patch availability with Vendor?"
        ),
    )

    vendor_reply = participant_adds_note_to_case(
        posting_client=vendor_client,
        watching_client=coordinator_client,
        poster=vendor_in_vendor,
        case=case,
        note_name="Vendor Status Update",
        note_content=(
            "We have confirmed the issue and are developing a fix. "
            "Estimated patch availability: 14 days."
        ),
        in_reply_to=question_note.id_,
    )

    participant_adds_note_to_case(
        posting_client=coordinator_client,
        watching_client=coordinator_client,
        poster=coordinator_in_coordinator,
        case=case,
        note_name="Coordinator Summary",
        note_content=(
            "All three parties engaged. Vendor fix expected in 14 days. "
            "Embargo holds until patch is deployed."
        ),
        in_reply_to=vendor_reply.id_,
    )

    logger.info(
        "✓ Notes exchange complete (three notes committed to case ledger)"
    )


def _phase_fix_lifecycle(
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator: as_Actor,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Advance Vendor through fix-ready and fix-deployed paths."""
    logger.info("─" * 80)
    logger.info(
        "Phase 5: Fix lifecycle — Vendor: VFd (fix ready) → VFD (fix deployed)"
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

    with demo_check(
        "M4: Coordinator replica shows Vendor CS includes F (fix ready)"
    ):
        wait_for_participant_vfd_state(
            client=coordinator_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vfd.VFd, CS_vfd.VFD},
        )
        verify_fix_ready(
            receiver_client=coordinator_client,
            reporter_client=vendor_client,
            case_id=case.id_,
            receiver_actor_id=coordinator.id_,
        )

    actor_notifies_fix_deployed(
        client=vendor_client,
        actor=vendor_in_vendor,
        case_id=case.id_,
    )

    with demo_check(
        "M5: Coordinator replica shows Vendor CS includes D (fix deployed)"
    ):
        wait_for_participant_vfd_state(
            client=coordinator_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vfd.VFD},
        )
        verify_fix_deployed(
            receiver_client=coordinator_client,
            reporter_client=vendor_client,
            case_id=case.id_,
            receiver_actor_id=coordinator.id_,
        )


def _phase_publication(
    finder_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator: as_Actor,
    coordinator_in_coordinator: as_Actor,
    vendor_in_vendor: as_Actor,
    finder_in_finder: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Run publication notifications and verify public disclosure state.

    Per DEMOMA-07-003(4) the Coordinator (as CASE_OWNER) triggers CS.P.
    """
    logger.info("─" * 80)
    logger.info(
        "Phase 6: Publication — CS.VFDPxa + embargo teardown (EM.EXITED)"
    )
    logger.info("─" * 80)

    # Coordinator announces publication first (CASE_OWNER triggers CS.P).
    actor_notifies_published(
        client=coordinator_client,
        actor=coordinator_in_coordinator,
        case_id=case.id_,
    )

    with demo_check(
        "Embargo terminated (EM.EXITED) after Coordinator reports published"
    ):
        wait_for_case_em_terminated(
            client=coordinator_client,
            case_id=case.id_,
        )

    actor_notifies_published(
        client=vendor_client,
        actor=vendor_in_vendor,
        case_id=case.id_,
    )
    actor_notifies_published(
        client=finder_client,
        actor=finder_in_finder,
        case_id=case.id_,
    )

    with demo_check(
        "M6: all replicas CS.VFDPxa, EM.EXITED, all participants public-aware"
    ):
        wait_for_case_em_terminated(
            client=vendor_client,
            case_id=case.id_,
        )
        verify_publicly_disclosed(
            receiver_client=coordinator_client,
            reporter_client=finder_client,
            case_id=case.id_,
            receiver_actor_id=coordinator.id_,
        )


def _phase_case_closure(
    finder_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_in_coordinator: as_Actor,
    vendor_in_vendor: as_Actor,
    finder_in_finder: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Close the case from all participants and verify terminal state."""
    logger.info("─" * 80)
    logger.info("Phase 7: Case closure — all participants RM.CLOSED")
    logger.info("─" * 80)

    actor_closes_case(
        client=coordinator_client,
        actor=coordinator_in_coordinator,
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

    with demo_check("M7: all participants RM.CLOSED on all replicas"):
        wait_for_all_participants_rm_closed(
            client=coordinator_client,
            case_id=case.id_,
        )
        wait_for_all_participants_rm_closed(
            client=finder_client,
            case_id=case.id_,
        )
        verify_case_closed(
            receiver_client=coordinator_client,
            reporter_client=finder_client,
            case_id=case.id_,
        )

    coordinator_entries = _get_log_entries_for_case(
        coordinator_client, case.id_
    )
    if coordinator_entries:
        coord_tail = max(coordinator_entries, key=lambda e: e["log_index"])
        coord_tail_index: int = coord_tail["log_index"]
        coord_tail_hash: str = coord_tail["entry_hash"]
        logger.info(
            "Waiting for replicas to receive coordinator tail after closure"
            " (hash=%s… index=%d)",
            coord_tail_hash[:16],
            coord_tail_index,
        )
        for replica_client in (finder_client, vendor_client):
            wait_for_contiguous_ledger_coverage(
                client=replica_client,
                case_id=case.id_,
                expected_tail_index=coord_tail_index,
            )


def _phase_dump_case_ledgers(
    finder_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient | None,
    case: as_VulnerabilityCase,
    demo_name: str = "fcv",
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
        ("coordinator", coordinator_client, "coordinator"),
        ("vendor", vendor_client, "vendor"),
    ]
    if case_actor_client is not None and case_actor_sub_actor_key is not None:
        actors.append(
            ("case-actor", case_actor_client, case_actor_sub_actor_key)
        )
    elif case_actor_sub_actor_key is not None:
        actors.append(
            ("case-actor", coordinator_client, case_actor_sub_actor_key)
        )

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


def run_fcv_demo(
    finder_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient | None = None,
    finder_id: str | None = None,
    coordinator_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Orchestrate the FCV CVD workflow."""
    logger.info("=" * 80)
    logger.info("FCV DEMO: Finder + Coordinator(CASE_OWNER) + Vendor")
    logger.info("=" * 80)
    logger.info("Finder container:      %s", finder_client.base_url)
    logger.info("Coordinator container: %s", coordinator_client.base_url)
    logger.info("Vendor container:      %s", vendor_client.base_url)
    if case_actor_client is not None:
        logger.info("CaseActor container:   %s", case_actor_client.base_url)

    (
        finder,
        finder_in_finder,
        coordinator,
        coordinator_in_coordinator,
        vendor_obj,
        _report,
        _offer,
        case,
    ) = _phase_report_submission(
        finder_client=finder_client,
        coordinator_client=coordinator_client,
        vendor_client=vendor_client,
        case_actor_client=case_actor_client,
        finder_id=finder_id,
        coordinator_id=coordinator_id,
        vendor_id=vendor_id,
    )

    vendor_in_vendor = _phase_invite_vendor(
        coordinator_client=coordinator_client,
        vendor_client=vendor_client,
        coordinator_in_coordinator=coordinator_in_coordinator,
        vendor=vendor_obj,
        case=case,
    )

    _phase_sync_verification(
        finder_client=finder_client,
        coordinator_client=coordinator_client,
        vendor_client=vendor_client,
        finder=finder,
        coordinator=coordinator,
        case=case,
    )

    _phase_notes_exchange(
        finder_client=finder_client,
        coordinator_client=coordinator_client,
        vendor_client=vendor_client,
        finder_in_finder=finder_in_finder,
        coordinator_in_coordinator=coordinator_in_coordinator,
        vendor_in_vendor=vendor_in_vendor,
        case=case,
    )

    _phase_fix_lifecycle(
        coordinator_client=coordinator_client,
        vendor_client=vendor_client,
        coordinator=coordinator,
        vendor=vendor_obj,
        vendor_in_vendor=vendor_in_vendor,
        case=case,
    )

    _phase_publication(
        finder_client=finder_client,
        coordinator_client=coordinator_client,
        vendor_client=vendor_client,
        coordinator=coordinator,
        coordinator_in_coordinator=coordinator_in_coordinator,
        vendor_in_vendor=vendor_in_vendor,
        finder_in_finder=finder_in_finder,
        case=case,
    )

    _phase_case_closure(
        finder_client=finder_client,
        coordinator_client=coordinator_client,
        vendor_client=vendor_client,
        coordinator_in_coordinator=coordinator_in_coordinator,
        vendor_in_vendor=vendor_in_vendor,
        finder_in_finder=finder_in_finder,
        case=case,
    )

    _phase_dump_case_ledgers(
        finder_client=finder_client,
        coordinator_client=coordinator_client,
        vendor_client=vendor_client,
        case_actor_client=case_actor_client,
        case=case,
    )

    logger.info("=" * 80)
    logger.info("FCV DEMO COMPLETE ✓  (VFDPxa full lifecycle)")
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(
    skip_health_check: bool = False,
    finder_url: str | None = None,
    coordinator_url: str | None = None,
    vendor_url: str | None = None,
    case_actor_url: str | None = None,
    finder_id: str | None = None,
    coordinator_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Entry point for the FCV CVD workflow demo.

    Args:
        skip_health_check: Skip the server availability check.
        finder_url: Override base URL for the Finder container.
        coordinator_url: Override base URL for the Coordinator container.
        vendor_url: Override base URL for the Vendor container.
        case_actor_url: Override base URL for the CaseActor container.
        finder_id: Optional deterministic URI for the Finder actor.
        coordinator_id: Optional deterministic URI for the Coordinator actor.
        vendor_id: Optional deterministic URI for the Vendor actor.
    """
    reset_demo_failures()

    f_url = finder_url or FINDER_BASE_URL
    c_url = coordinator_url or COORDINATOR_BASE_URL
    v_url = vendor_url or VENDOR_BASE_URL
    ca_url = case_actor_url or CASE_ACTOR_BASE_URL

    finder_client = DataLayerClient(base_url=f_url)
    coordinator_client = DataLayerClient(base_url=c_url)
    vendor_client = DataLayerClient(base_url=v_url)
    case_actor_client = DataLayerClient(base_url=ca_url)

    if not skip_health_check:
        targets: list[tuple[str, DataLayerClient]] = [
            ("Finder", finder_client),
            ("Coordinator", coordinator_client),
            ("Vendor", vendor_client),
            ("CaseActor", case_actor_client),
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
        run_fcv_demo(
            finder_client=finder_client,
            coordinator_client=coordinator_client,
            vendor_client=vendor_client,
            case_actor_client=case_actor_client,
            finder_id=finder_id,
            coordinator_id=coordinator_id,
            vendor_id=vendor_id,
        )
    finally:
        assert_demo_success()


if __name__ == "__main__":
    setup_demo_logging()
    main()
