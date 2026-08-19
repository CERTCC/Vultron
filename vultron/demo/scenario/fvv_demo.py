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

"""Finder → Vendor1 → Vendor2 (FVV) three-actor CVD workflow demo.

Orchestrates the full VFDPxa lifecycle across separate Finder, Vendor1,
and Vendor2 containers with no coordinator.  Vendor1 creates the case and
invites both Finder and Vendor2; each vendor has an independent fix path
(CS_vfd).  Vendor2's DataLayer is verified as a LedgerFanout replica of the
authoritative Vendor1 state.

Spec: D5-5 (GitHub issue #1265).
"""

import logging
import os
import sys

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
    as_VulnerabilityReport,
)

from vultron.demo.utils import (  # noqa: F401 — re-exported for test monkeypatching
    BASE_URL,
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
    actor_notifies_fix_ready,
    actor_notifies_published,
)
from vultron.demo.helpers.harness import scenario_harness
from vultron.demo.helpers.ledger_dump import (
    LedgerDumpTarget,
    dump_case_ledgers,
    resolve_case_actor_route_key,
)
from vultron.demo.helpers.milestones import (
    verify_case_active,
    verify_case_closed,
    verify_fix_ready,
    verify_publicly_disclosed,
)
from vultron.demo.helpers.polling import (
    find_case_invite_for_actor,
    wait_for_all_participants_rm_closed,
    wait_for_case_em_terminated,
    wait_for_case_on_container,
    wait_for_case_participants,
    wait_for_contiguous_ledger_coverage,
    wait_for_event_type_in_ledger,
    wait_for_finder_case,
    wait_for_participant_vfd_state,
)
from vultron.demo.helpers.seeding import (
    get_actor_by_id,
    reset_containers as _reset_containers,
    seed_containers_fvv,
)
from vultron.demo.helpers.notes import participant_adds_note_to_case
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
VENDOR2_BASE_URL = os.environ.get(
    "VULTRON_VENDOR2_BASE_URL", "http://localhost:7904/api/v2"
)

# Deterministic actor IDs from docker-compose-multi-actor.yml (D5-1-G3).
FINDER_ACTOR_ID = "http://finder:7999/api/v2/actors/finder"
VENDOR_ACTOR_ID = "http://vendor:7999/api/v2/actors/vendor"
VENDOR2_ACTOR_ID = "http://actor5:7999/api/v2/actors/vendor2"


def reset_containers(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
) -> None:
    """Reset all three FVV containers to a clean baseline."""
    targets: list[tuple[str, DataLayerClient]] = [
        ("Finder", finder_client),
        ("Vendor1", vendor_client),
        ("Vendor2", vendor2_client),
    ]
    _reset_containers(targets, reset_fn=reset_datalayer)


# ---------------------------------------------------------------------------
# Phase helpers
# ---------------------------------------------------------------------------


def _phase_report_submission(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    finder_id: str | None,
    vendor_id: str | None,
    vendor2_id: str | None,
) -> tuple[
    as_Actor,
    as_Actor,
    as_Actor,
    as_Actor,
    as_VulnerabilityReport,
    as_Offer,
    as_VulnerabilityCase,
]:
    """Reset, seed, submit report, validate, engage, invite Vendor2, M1 check."""
    logger.info("─" * 80)
    logger.info("Phase 1: Report submission and case activation")
    logger.info("─" * 80)

    reset_containers(
        finder_client=finder_client,
        vendor_client=vendor_client,
        vendor2_client=vendor2_client,
    )

    finder = vendor = vendor2 = None
    with demo_step("Seeding all three containers with actor records"):
        finder, vendor, vendor2 = seed_containers_fvv(
            finder_client=finder_client,
            vendor_client=vendor_client,
            vendor2_client=vendor2_client,
            reporter_actor_id=finder_id,
            vendor_actor_id=vendor_id,
            vendor2_actor_id=vendor2_id,
        )

    vendor_in_vendor = get_actor_by_id(vendor_client, vendor.id_)
    vendor2_in_vendor2 = get_actor_by_id(vendor2_client, vendor2.id_)

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

    # Wait for the initial participants (Finder + Vendor1 + CaseActor) before
    # inviting Vendor2.
    wait_for_case_participants(
        vendor_client=vendor_client,
        case_id=case.id_,
        expected_count=3,
    )

    with demo_check(
        "Finder's DataLayer received case via Vendor1 outbox delivery"
    ):
        wait_for_finder_case(
            finder_client=finder_client,
            case_id=case.id_,
        )

    # Vendor1 invites Vendor2 to the case.
    invite_result = None
    with demo_step("Vendor1 invites Vendor2 to the case"):
        invite_result = post_to_trigger(
            client=vendor_client,
            actor_id=vendor_in_vendor.id_,
            behavior="invite-actor-to-case",
            body={
                "case_id": case.id_,
                "invitee_id": vendor2.id_,
                "roles": ["vendor"],
            },
        )
    invite = as_TransitiveActivity.model_validate(invite_result["activity"])
    logger.info("Invite created: %s", invite.id_)

    with demo_check("Vendor2 invite delivered to Vendor2's DataLayer"):
        find_case_invite_for_actor(
            client=vendor2_client,
            case_id=case.id_,
            invitee_id=vendor2.id_,
            timeout_seconds=20.0,
        )

    # Vendor2 accepts the invite.
    with demo_step("Vendor2 accepts the case invitation"):
        post_to_trigger(
            client=vendor2_client,
            actor_id=vendor2_in_vendor2.id_,
            behavior="accept-case-invite",
            body={"invite_id": invite.id_},
        )

    # Wait for Vendor2's container to replicate the case.
    with demo_check("Vendor2's DataLayer received case replica"):
        wait_for_case_on_container(
            client=vendor2_client,
            case_id=case.id_,
        )

    # 4 participants: Finder + Vendor1 + Vendor2 + CaseActor
    wait_for_case_participants(
        vendor_client=vendor_client,
        case_id=case.id_,
        expected_count=4,
    )

    # CLP-08-005: ensure Finder's genesis hash is seeded before Announce(CaseLedgerEntry)
    # is broadcast by the triage cycle below.
    with demo_check(
        "Finder's DataLayer received case replica before Vendor2 RM triage"
    ):
        wait_for_case_on_container(
            client=finder_client,
            case_id=case.id_,
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
    )

    with demo_check(
        "M1: required participants (≥4), EM.ACTIVE, finder + vendor2 have replicas"
    ):
        verify_case_active(
            receiver_client=vendor_client,
            reporter_client=finder_client,
            case_id=case.id_,
            receiver_actor_id=vendor.id_,
            reporter_actor_id=finder.id_,
        )

    case = as_VulnerabilityCase.model_validate(
        vendor_client.get(vendor_client.dl_path(case.id_))
    )
    return finder, vendor, vendor_in_vendor, vendor2, report, offer, case


def _phase_sync_verification(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    vendor: as_Actor,
    finder: as_Actor,
    vendor2: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Verify LedgerFanout replication for both Finder and Vendor2 replicas."""
    logger.info("─" * 80)
    logger.info("Phase 2: Replica synchronization verification")
    logger.info("─" * 80)

    vendor_entries = _get_log_entries_for_case(vendor_client, case.id_)
    if vendor_entries:
        vendor_tail = max(vendor_entries, key=lambda e: e["log_index"])
        vendor_tail_index: int = vendor_tail["log_index"]
        vendor_tail_hash: str = vendor_tail["entry_hash"]
        logger.info(
            "Waiting for Finder to replicate Vendor1 tail (hash=%s… index=%d)",
            vendor_tail_hash[:16],
            vendor_tail_index,
        )
        with demo_check("Finder ledger coverage (sync-verification phase)"):
            wait_for_contiguous_ledger_coverage(
                client=finder_client,
                case_id=case.id_,
                expected_tail_index=vendor_tail_index,
            )
        logger.info(
            "Waiting for Vendor2 to replicate Vendor1 tail (hash=%s… index=%d)",
            vendor_tail_hash[:16],
            vendor_tail_index,
        )
        with demo_check("Vendor2 ledger coverage (sync-verification phase)"):
            wait_for_contiguous_ledger_coverage(
                client=vendor2_client,
                case_id=case.id_,
                expected_tail_index=vendor_tail_index,
            )

    wait_for_case_participants(
        vendor_client=finder_client,
        case_id=case.id_,
        expected_count=4,
    )
    wait_for_case_participants(
        vendor_client=vendor2_client,
        case_id=case.id_,
        expected_count=4,
    )

    with demo_check(
        "Finder replica state matches authoritative Vendor1 state"
    ):
        verify_replica_state(
            auth_client=vendor_client,
            replica_client=finder_client,
            case_id=case.id_,
            vendor_actor_id=vendor.id_,
            reporter_actor_id=finder.id_,
        )

    with demo_check(
        "Vendor2 replica state matches authoritative Vendor1 state"
    ):
        verify_replica_state(
            auth_client=vendor_client,
            replica_client=vendor2_client,
            case_id=case.id_,
            vendor_actor_id=vendor.id_,
            reporter_actor_id=finder.id_,
        )

    logger.info(
        "✓ M2: Finder and Vendor2 DataLayers synchronized (LedgerFanout verified)"
    )


def _phase_notes_exchange(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    finder_in_finder: as_Actor,
    vendor_in_vendor: as_Actor,
    vendor2_in_vendor2: as_Actor,
    case: as_VulnerabilityCase,
) -> tuple[as_Note, as_Note, as_Note]:
    """Run a three-way note exchange among Finder, Vendor1, and Vendor2."""
    logger.info("─" * 80)
    logger.info("Phase 3: Notes exchange")
    logger.info("─" * 80)

    question_note = participant_adds_note_to_case(
        posting_client=finder_client,
        watching_client=vendor_client,
        poster=finder_in_finder,
        case=case,
        note_name="Question from Finder",
        note_content=(
            "Is there a workaround available while waiting for the patch? "
            "Our security team needs to provide interim guidance to users."
        ),
    )

    reply_note = participant_adds_note_to_case(
        posting_client=vendor_client,
        watching_client=vendor_client,
        poster=vendor_in_vendor,
        case=case,
        note_name="Vendor1 Response",
        note_content=(
            "Yes, disabling the affected component is an effective workaround. "
            "A patched version is expected within 30 days."
        ),
        in_reply_to=question_note.id_,
    )

    vendor2_note = participant_adds_note_to_case(
        posting_client=vendor2_client,
        watching_client=vendor_client,
        poster=vendor2_in_vendor2,
        case=case,
        note_name="Vendor2 Status Update",
        note_content=(
            "Vendor2 can confirm the issue affects our component. "
            "We will coordinate our fix timeline with Vendor1."
        ),
        in_reply_to=reply_note.id_,
    )

    logger.info(
        "✓ Notes exchange complete (question + two replies committed to case ledger)"
    )
    return question_note, reply_note, vendor2_note


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
    """Advance both vendors through independent fix-ready and fix-deployed paths."""
    logger.info("─" * 80)
    logger.info(
        "Phase 4: Fix lifecycle — both vendors: VFd (fix ready); vendors stop at VFd (CSB-15-002)"
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
        "M4: Finder replica shows both vendors CS include F (fix ready)"
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
        "M5: Finder replica shows both vendors CS include F (fix ready) — vendors stop at VFd"
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
    vendor2_client: DataLayerClient,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    vendor2: as_Actor,
    vendor2_in_vendor2: as_Actor,
    finder: as_Actor,
    finder_in_finder: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Run publication notifications and verify public disclosure state."""
    logger.info("─" * 80)
    logger.info(
        "Phase 5: Publication — CS.VFDPxa + embargo teardown (EM.EXITED)"
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
        client=finder_client,
        actor=finder_in_finder,
        case_id=case.id_,
    )

    with demo_check(
        "M6: all replicas CS.VFdPxa, EM.EXITED, all participants public-aware"
    ):
        wait_for_case_em_terminated(
            client=finder_client,
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
    vendor2_client: DataLayerClient,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    vendor2: as_Actor,
    vendor2_in_vendor2: as_Actor,
    finder: as_Actor,
    finder_in_finder: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Close the case from all three participants and verify terminal state."""
    logger.info("─" * 80)
    logger.info("Phase 6: Case closure — all participants RM.CLOSED")
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

    with demo_check("M7: all participants RM.CLOSED on all replicas"):
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

    # Wait for all replicas to receive every canonical ledger entry including
    # the close_case tail.  Waiting only for the tail hash is insufficient:
    # Announce(CaseLedgerEntry) activities are delivered independently and an
    # intermediate entry can arrive after the tail (issue #1363).  We therefore
    # verify full contiguous coverage (0…tail_index) before dumping logs.
    #
    # Bug B fix: wait for the async close_case entry on the authoritative actor
    # before reading the tail index, so we don't snapshot a stale tail that
    # excludes the close_case entry itself.
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
        with demo_check("Finder ledger coverage (close phase)"):
            wait_for_contiguous_ledger_coverage(
                client=finder_client,
                case_id=case.id_,
                expected_tail_index=vendor_tail_index,
            )
        with demo_check("Vendor2 ledger coverage (close phase)"):
            wait_for_contiguous_ledger_coverage(
                client=vendor2_client,
                case_id=case.id_,
                expected_tail_index=vendor_tail_index,
            )


def _phase_dump_case_ledgers(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    vendor2: as_Actor,
    case: as_VulnerabilityCase,
    demo_name: str = "fvv",
) -> None:
    """Dump case ledger entries from each actor container to JSONL files.

    Thin scenario-specific wrapper over
    :func:`~vultron.demo.helpers.ledger_dump.dump_case_ledgers`, which owns the
    per-actor export, the 404 handling, and the dump manifest. This function
    only names FVV's participants and where each one's ledger lives.
    """
    targets = [
        LedgerDumpTarget("finder", finder_client, "finder"),
        LedgerDumpTarget("vendor", vendor_client, "vendor"),
        LedgerDumpTarget("vendor2", vendor2_client, "vendor2"),
    ]
    # The case-actor is a sub-actor inside the vendor1 container.
    case_actor_route_key = resolve_case_actor_route_key(case)
    if case_actor_route_key is not None:
        targets.append(
            LedgerDumpTarget("case-actor", vendor_client, case_actor_route_key)
        )

    dump_case_ledgers(demo_name=demo_name, case=case, targets=targets)


def run_fvv_demo(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    finder_id: str | None = None,
    vendor_id: str | None = None,
    vendor2_id: str | None = None,
) -> None:
    """Orchestrate the FVV (Finder + Vendor1 + Vendor2) CVD workflow."""
    logger.info("=" * 80)
    logger.info("FVV DEMO: Finder → Vendor1 → Vendor2 CVD Workflow (VFDPxa)")
    logger.info("=" * 80)
    logger.info("Finder container:  %s", finder_client.base_url)
    logger.info("Vendor1 container: %s", vendor_client.base_url)
    logger.info("Vendor2 container: %s", vendor2_client.base_url)

    with scenario_harness("fvv") as harness:
        finder, vendor, vendor_in_vendor, vendor2, report, offer, case = (
            _phase_report_submission(
                finder_client,
                vendor_client,
                vendor2_client,
                finder_id,
                vendor_id,
                vendor2_id,
            )
        )

        # Register the dump as soon as there is a case to dump, so every phase
        # below can fail without costing us the ledgers (ISSUE-2239).
        harness.dump_with(
            lambda: _phase_dump_case_ledgers(
                finder_client=finder_client,
                vendor_client=vendor_client,
                vendor2_client=vendor2_client,
                finder=finder,
                vendor=vendor,
                vendor2=vendor2,
                case=case,
                demo_name=harness.demo_name,
            )
        )

        vendor2_in_vendor2 = get_actor_by_id(vendor2_client, vendor2.id_)
        finder_in_finder = get_actor_by_id(finder_client, finder.id_)

        _phase_sync_verification(
            finder_client,
            vendor_client,
            vendor2_client,
            vendor,
            finder,
            vendor2,
            case,
        )
        _phase_notes_exchange(
            finder_client=finder_client,
            vendor_client=vendor_client,
            vendor2_client=vendor2_client,
            finder_in_finder=finder_in_finder,
            vendor_in_vendor=vendor_in_vendor,
            vendor2_in_vendor2=vendor2_in_vendor2,
            case=case,
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
            vendor2_client,
            vendor,
            vendor_in_vendor,
            vendor2,
            vendor2_in_vendor2,
            finder,
            finder_in_finder,
            case,
        )
        _phase_case_closure(
            finder_client,
            vendor_client,
            vendor2_client,
            vendor,
            vendor_in_vendor,
            vendor2,
            vendor2_in_vendor2,
            finder,
            finder_in_finder,
            case,
        )

    logger.info("=" * 80)
    logger.info("FVV DEMO COMPLETE ✓  (VFDPxa full lifecycle)")
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(
    skip_health_check: bool = False,
    finder_url: str | None = None,
    vendor_url: str | None = None,
    vendor2_url: str | None = None,
    finder_id: str | None = None,
    vendor_id: str | None = None,
    vendor2_id: str | None = None,
) -> None:
    """Entry point for the FVV (Finder + Vendor1 + Vendor2) CVD workflow demo.

    Args:
        skip_health_check: Skip the server availability check (useful for
            testing).
        finder_url: Override base URL for the Finder container.
        vendor_url: Override base URL for the Vendor1 container.
        vendor2_url: Override base URL for the Vendor2 container.
        finder_id: Optional deterministic URI for the Finder actor.
        vendor_id: Optional deterministic URI for the Vendor1 actor.
        vendor2_id: Optional deterministic URI for the Vendor2 actor.
    """
    f_url = finder_url or FINDER_BASE_URL
    v_url = vendor_url or VENDOR_BASE_URL
    v2_url = vendor2_url or VENDOR2_BASE_URL

    finder_client = DataLayerClient(base_url=f_url)
    vendor_client = DataLayerClient(base_url=v_url)
    vendor2_client = DataLayerClient(base_url=v2_url)

    if not skip_health_check:
        targets: list[tuple[str, DataLayerClient]] = [
            ("Finder", finder_client),
            ("Vendor1", vendor_client),
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

    # scenario_harness() inside run_fvv_demo() owns the failure accumulator: it
    # resets it, always dumps the case ledgers, and asserts success — so a
    # failure here never costs us the artifacts (ISSUE-2239).
    run_fvv_demo(
        finder_client=finder_client,
        vendor_client=vendor_client,
        vendor2_client=vendor2_client,
        finder_id=finder_id,
        vendor_id=vendor_id,
        vendor2_id=vendor2_id,
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
