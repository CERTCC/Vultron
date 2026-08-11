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

"""FCV-Reject three-actor CVD workflow demo (Finder + Coordinator + Vendor rejection).

Orchestrates a CVD workflow where Coordinator receives the Finder's report,
creates the case (CASE_OWNER), the CaseActor service manages the ledger.
Coordinator invites Vendor (``invite-actor-to-case``), but Vendor rejects the
invitation (``reject-case-invite``).  Vendor is therefore NOT added to the case
as a participant.  Finder and Coordinator continue to close out the case through
publication and closure.

Key difference from the FCV scenario: Vendor rejects the case invitation
(RM-layer rejection via ``Reject(Invite(actor, case))``) so Vendor never
becomes a case participant and has no case ledger replica.

Spec: GitHub issue #2047 (fcv-reject demo scenario).
"""

import json
import logging
import os
import pathlib
import sys

import httpx2 as httpx

from vultron.adapters.utils import strip_id_prefix
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_TransitiveActivity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer

from vultron.demo.utils import (  # noqa: F401 — re-exported for test monkeypatching
    DataLayerClient,
    assert_demo_success,
    check_server_availability,
    demo_check,
    demo_step,
    post_to_trigger,
    reset_datalayer,
    reset_demo_failures,
    setup_demo_logging,
    verify_object_stored,
)
from vultron.demo.helpers.actions import (
    actor_closes_case,
    actor_notifies_published,
)
from vultron.demo.helpers.milestones import (
    verify_case_active,
    verify_case_closed,
    verify_publicly_disclosed,
)
from vultron.demo.helpers.notes import participant_adds_note_to_case
from vultron.demo.helpers.polling import (
    find_case_invite_for_actor,
    wait_for_all_participants_rm_closed,
    wait_for_case_em_terminated,
    wait_for_case_participants,
    wait_for_contiguous_ledger_coverage,
    wait_for_event_type_in_ledger,
)
from vultron.demo.helpers.seeding import (
    get_actor_by_id,
    reset_containers as _reset_containers,
    seed_containers_fcv,
)
from vultron.demo.helpers.sync import (
    _get_log_entries_for_case,
)
from vultron.demo.helpers.workflow import (
    reporter_submits_report,
    run_direct_path_rm_triage,
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
    """Reset FCV-Reject containers to a clean baseline."""
    targets: list[tuple[str, DataLayerClient]] = [
        ("Finder", finder_client),
        ("Coordinator", coordinator_client),
        ("Vendor", vendor_client),
    ]
    if case_actor_client is not None:
        targets.append(("CaseActor", case_actor_client))
    _reset_containers(targets, reset_fn=reset_datalayer)


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

    report, offer = reporter_submits_report(
        receiver_client=coordinator_client,
        reporter=finder,
        receiver=coordinator_in_coordinator,
        reporter_client=finder_client,
    )
    case = run_direct_path_rm_triage(
        receiver_client=coordinator_client,
        receiver=coordinator_in_coordinator,
        offer=offer,
    )

    # Wait for Coordinator + Finder + CaseActor (3 participants).
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


def _phase_invite_vendor_reject(
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_in_coordinator: as_Actor,
    vendor: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Coordinator invites Vendor; Vendor rejects the invitation.

    Vendor sends Reject(Invite(actor, case)) back to the CaseActor via the
    ``reject-case-invite`` trigger.  The CaseActor records a
    ``reject_invite_actor_to_case`` ledger entry and does NOT add Vendor as a
    participant.  Vendor's participant count stays at 3 (Finder + Coordinator +
    CaseActor).
    """
    logger.info("─" * 80)
    logger.info("Phase 2: Coordinator invites Vendor; Vendor rejects")
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

    with demo_check("Vendor invite delivered to Vendor's DataLayer"):
        find_case_invite_for_actor(
            client=vendor_client,
            case_id=case.id_,
            invitee_id=vendor.id_,
            timeout_seconds=20.0,
        )

    with demo_step("Vendor rejects the case invitation"):
        post_to_trigger(
            client=vendor_client,
            actor_id=vendor_in_vendor.id_,
            behavior="reject-case-invite",
            body={"invite_id": invite.id_},
        )
    logger.info("Vendor sent Reject(Invite) to CaseActor")

    # Participant count remains 3: Coordinator + Finder + CaseActor.
    # Vendor must NOT appear as a 4th participant.
    with demo_check(
        "Participant count stays at 3 (Vendor not added after rejection)"
    ):
        # Give the CaseActor time to process the Reject then confirm stability.
        wait_for_event_type_in_ledger(
            client=coordinator_client,
            case_id=case.id_,
            event_type="reject_invite_actor_to_case",
        )
        wait_for_case_participants(
            vendor_client=coordinator_client,
            case_id=case.id_,
            expected_count=3,
        )
    logger.info("✓ M2: Vendor rejected invite — participant count stable at 3")


def _phase_notes_exchange(
    finder_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    finder_in_finder: as_Actor,
    coordinator_in_coordinator: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Run a two-way note exchange between Finder and Coordinator."""
    logger.info("─" * 80)
    logger.info("Phase 3: Notes exchange (Finder + Coordinator)")
    logger.info("─" * 80)

    question_note = participant_adds_note_to_case(
        posting_client=finder_client,
        watching_client=coordinator_client,
        poster=finder_in_finder,
        case=case,
        note_name="Question from Finder",
        note_content=(
            "Vendor rejected the invitation. "
            "What is the plan for coordinated disclosure?"
        ),
    )

    participant_adds_note_to_case(
        posting_client=coordinator_client,
        watching_client=coordinator_client,
        poster=coordinator_in_coordinator,
        case=case,
        note_name="Coordinator Response",
        note_content=(
            "Vendor declined to participate. "
            "We will proceed with Finder-only disclosure. "
            "Embargo will be terminated and we will publish."
        ),
        in_reply_to=question_note.id_,
    )

    logger.info(
        "✓ Notes exchange complete (two notes committed to case ledger)"
    )


def _phase_publication(
    finder_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    coordinator_in_coordinator: as_Actor,
    finder_in_finder: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Coordinator and Finder publish; embargo terminates (EM.EXITED)."""
    logger.info("─" * 80)
    logger.info("Phase 4: Publication — embargo teardown (EM.EXITED)")
    logger.info("─" * 80)

    # Coordinator (as CASE_OWNER) triggers CS.P.
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
        client=finder_client,
        actor=finder_in_finder,
        case_id=case.id_,
    )

    with demo_check("M3: EM.EXITED, Coordinator and Finder public-aware"):
        wait_for_case_em_terminated(
            client=finder_client,
            case_id=case.id_,
        )
        verify_publicly_disclosed(
            receiver_client=coordinator_client,
            reporter_client=finder_client,
            case_id=case.id_,
            receiver_actor_id=coordinator_in_coordinator.id_,
        )


def _phase_case_closure(
    finder_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    coordinator_in_coordinator: as_Actor,
    finder_in_finder: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Close the case from Finder and Coordinator; verify terminal state."""
    logger.info("─" * 80)
    logger.info("Phase 5: Case closure — Finder and Coordinator RM.CLOSED")
    logger.info("─" * 80)

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

    with demo_check("M4: all participants RM.CLOSED on all replicas"):
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

    with demo_check(
        "close_case entry present on authoritative actor (coordinator)"
    ):
        wait_for_event_type_in_ledger(
            client=coordinator_client,
            case_id=case.id_,
            event_type="close_case",
        )
    coordinator_entries = _get_log_entries_for_case(
        coordinator_client, case.id_
    )
    if coordinator_entries:
        coord_tail = max(coordinator_entries, key=lambda e: e["log_index"])
        coord_tail_index: int = coord_tail["log_index"]
        coord_tail_hash: str = coord_tail["entry_hash"]
        logger.info(
            "Waiting for Finder replica to receive coordinator tail after closure"
            " (hash=%s… index=%d)",
            coord_tail_hash[:16],
            coord_tail_index,
        )
        with demo_check("Finder ledger coverage (close phase)"):
            wait_for_contiguous_ledger_coverage(
                client=finder_client,
                case_id=case.id_,
                expected_tail_index=coord_tail_index,
            )


def _phase_dump_case_ledgers(
    finder_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    case: as_VulnerabilityCase,
    demo_name: str = "fcv-reject",
) -> None:
    """Dump case ledger entries from Finder, Coordinator, and CaseActor to JSONL.

    Vendor is intentionally excluded: it rejected the invitation and was never
    added as a case participant, so it has no case ledger replica.
    """
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
    ]
    if case_actor_sub_actor_key is not None:
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


def run_fcv_reject_demo(
    finder_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient | None = None,
    finder_id: str | None = None,
    coordinator_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Orchestrate the FCV-Reject CVD workflow."""
    logger.info("=" * 80)
    logger.info(
        "FCV-REJECT DEMO: Finder + Coordinator(CASE_OWNER) + Vendor(rejects)"
    )
    logger.info("=" * 80)
    logger.info("Finder container:      %s", finder_client.base_url)
    logger.info("Coordinator container: %s", coordinator_client.base_url)
    logger.info("Vendor container:      %s", vendor_client.base_url)
    if case_actor_client is not None:
        logger.info("CaseActor container:   %s", case_actor_client.base_url)

    (
        _finder,
        finder_in_finder,
        _coordinator,
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

    _phase_invite_vendor_reject(
        coordinator_client=coordinator_client,
        vendor_client=vendor_client,
        coordinator_in_coordinator=coordinator_in_coordinator,
        vendor=vendor_obj,
        case=case,
    )

    _phase_notes_exchange(
        finder_client=finder_client,
        coordinator_client=coordinator_client,
        finder_in_finder=finder_in_finder,
        coordinator_in_coordinator=coordinator_in_coordinator,
        case=case,
    )

    _phase_publication(
        finder_client=finder_client,
        coordinator_client=coordinator_client,
        coordinator_in_coordinator=coordinator_in_coordinator,
        finder_in_finder=finder_in_finder,
        case=case,
    )

    _phase_case_closure(
        finder_client=finder_client,
        coordinator_client=coordinator_client,
        coordinator_in_coordinator=coordinator_in_coordinator,
        finder_in_finder=finder_in_finder,
        case=case,
    )

    _phase_dump_case_ledgers(
        finder_client=finder_client,
        coordinator_client=coordinator_client,
        case=case,
    )

    logger.info("=" * 80)
    logger.info(
        "FCV-REJECT DEMO COMPLETE ✓  (Vendor rejected — Finder+Coordinator closed)"
    )
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
    """Entry point for the FCV-Reject CVD workflow demo.

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
        run_fcv_reject_demo(
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
