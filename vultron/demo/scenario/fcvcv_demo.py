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

"""Finder + Coordinator1 + Vendor1 + Coordinator2 + VendorDeployer (FCVCV) demo.

Orchestrates the full CVD lifecycle across five actor containers plus a
dedicated CaseActor:
  - Finder: the report submitter
  - C1 (coordinator container): CASE_OWNER throughout; receives the report
  - V1 (vendor container): CVDRole.VENDOR only; advances to VFd (fix-ready,
    no deploy step)
  - C2 (actor5 container): CVDRole.COORDINATOR participant; suggests V2
    via the ADR-0026 suggest-actor flow
  - V2 (actor6 container): CVDRole.VENDOR + CVDRole.DEPLOYER; advances to
    VFD (fix-ready then fix-deployed)

Container mapping (docker-compose-multi-actor.yml services):
  VULTRON_FINDER_BASE_URL           → Finder container
  VULTRON_COORDINATOR_BASE_URL      → C1 container (coordinator)
  VULTRON_VENDOR_BASE_URL           → V1 container (vendor)
  VULTRON_VENDOR2_BASE_URL          → C2 container (actor5)
  VULTRON_VENDOR_DEPLOYER_BASE_URL  → V2 container (actor6)

Spec: DEMOMA-19 (GitHub issue #1925).
"""

import logging
import os
import sys

from vultron.core.states.cs import CS_vfd
from vultron.core.states.rm import RM
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Offer,
    as_TransitiveActivity,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
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
    demo_gate,
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
    verify_fix_deployed,
    verify_fix_ready,
    verify_publicly_disclosed,
)
from vultron.demo.helpers.notes import participant_adds_note_to_case
from vultron.demo.helpers.polling import (
    drain_phase1_ledger,
    find_case_actor_participant_id,
    find_case_invite_for_actor,
    find_cp_offer_for_case,
    LATE_JOINER_TIMEOUT,
    wait_for_all_participants_rm_closed,
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
    seed_containers_fcvcv,
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

# AC-6 audit (#2203): wait_for_case_on_container calls in this module poll for
# VulnerabilityCase object delivery (ADR-0041 seeding path). ADR-0037/ADR-0059
# buffer Announce(CaseLedgerEntry) entries, not VulnerabilityCase objects, so
# all wait_for_case_on_container calls here remain necessary.

# Default container base URLs — override via environment variables.
# C1 uses the "coordinator" container, V1 uses "vendor", C2 uses "actor5",
# and V2 (VendorDeployer) uses "actor6".
FINDER_BASE_URL = os.environ.get(
    "VULTRON_FINDER_BASE_URL", "http://localhost:7901/api/v2"
)
C1_BASE_URL = os.environ.get(
    "VULTRON_COORDINATOR_BASE_URL", "http://localhost:7903/api/v2"
)
V1_BASE_URL = os.environ.get(
    "VULTRON_VENDOR_BASE_URL", "http://localhost:7902/api/v2"
)
C2_BASE_URL = os.environ.get(
    "VULTRON_VENDOR2_BASE_URL", "http://localhost:7904/api/v2"
)
V2_BASE_URL = os.environ.get(
    "VULTRON_VENDOR_DEPLOYER_BASE_URL", "http://localhost:7905/api/v2"
)

# Deterministic actor IDs — match docker-compose-multi-actor.yml service names.
FINDER_ACTOR_ID = "http://finder:7999/api/v2/actors/finder"
C1_ACTOR_ID = "http://coordinator:7999/api/v2/actors/coordinator"
V1_ACTOR_ID = "http://vendor:7999/api/v2/actors/vendor"
C2_ACTOR_ID = "http://actor5:7999/api/v2/actors/vendor2"
V2_ACTOR_ID = "http://actor6:7999/api/v2/actors/vendor-deployer"


def reset_containers(
    finder_client: DataLayerClient,
    c1_client: DataLayerClient,
    v1_client: DataLayerClient,
    c2_client: DataLayerClient,
    v2_client: DataLayerClient,
) -> None:
    """Reset all five FCVCV containers to a clean baseline."""
    targets: list[tuple[str, DataLayerClient]] = [
        ("Finder", finder_client),
        ("C1", c1_client),
        ("V1", v1_client),
        ("C2", c2_client),
        ("V2", v2_client),
    ]
    _reset_containers(targets, reset_fn=reset_datalayer)


# ---------------------------------------------------------------------------
# Phase helpers
# ---------------------------------------------------------------------------


def _phase_report_submission(
    finder_client: DataLayerClient,
    c1_client: DataLayerClient,
    v1_client: DataLayerClient,
    c2_client: DataLayerClient,
    v2_client: DataLayerClient,
    finder_id: str | None,
    c1_id: str | None,
    v1_id: str | None,
    c2_id: str | None,
    v2_id: str | None,
) -> tuple[
    as_Actor,
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
    """Reset, seed, submit report, validate, engage, invite V1 and C2."""
    logger.info("─" * 80)
    logger.info("Phase 1: Report submission and case activation")
    logger.info("─" * 80)

    reset_containers(
        finder_client=finder_client,
        c1_client=c1_client,
        v1_client=v1_client,
        c2_client=c2_client,
        v2_client=v2_client,
    )

    finder = c1 = v1 = c2 = v2 = None
    with demo_step("Seeding all five containers with actor records"):
        finder, c1, v1, c2, v2 = seed_containers_fcvcv(
            finder_client=finder_client,
            c1_client=c1_client,
            v1_client=v1_client,
            c2_client=c2_client,
            v2_client=v2_client,
            reporter_actor_id=finder_id,
            c1_actor_id=c1_id,
            v1_actor_id=v1_id,
            c2_actor_id=c2_id,
            v2_actor_id=v2_id,
        )

    c1_in_c1 = get_actor_by_id(c1_client, c1.id_)
    v1_in_v1 = get_actor_by_id(v1_client, v1.id_)
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
        timeout_seconds=60.0,
    )

    # Wait for the initial participants (Finder + C1 + CaseActor) before
    # inviting V1 and C2.
    wait_for_case_participants(
        vendor_client=c1_client,
        case_id=case.id_,
        expected_actor_ids={finder.id_, c1.id_},
    )

    with demo_check(
        "Finder's DataLayer received case replica (genesis hash available)"
    ):
        wait_for_case_on_container(
            client=finder_client,
            case_id=case.id_,
        )

    # C1 invites V1 with CVDRole.VENDOR.
    invite_v1_result = None
    with demo_step("C1 invites V1 with CVDRole.VENDOR"):
        invite_v1_result = post_to_trigger(
            client=c1_client,
            actor_id=c1_in_c1.id_,
            behavior="invite-actor-to-case",
            body={
                "case_id": case.id_,
                "invitee_id": v1.id_,
                "roles": ["vendor"],
            },
        )
    invite_v1 = as_TransitiveActivity.model_validate(
        invite_v1_result["activity"]
    )
    logger.info("V1 invite created: %s", invite_v1.id_)

    invite_v1_id = None
    with demo_gate("CaseActor-routed Invite for V1 stored in V1's DataLayer"):
        invite_v1_id = find_case_invite_for_actor(
            client=v1_client,
            case_id=case.id_,
            invitee_id=v1.id_,
        )
    logger.info("CaseActor Invite for V1: %s", invite_v1_id)

    with demo_step("V1 accepts the case invitation"):
        post_to_trigger(
            client=v1_client,
            actor_id=v1_in_v1.id_,
            behavior="accept-case-invite",
            body={"invite_id": invite_v1_id},
        )

    with demo_check("V1's DataLayer received case replica"):
        wait_for_case_on_container(
            client=v1_client,
            case_id=case.id_,
        )

    with demo_check(
        "Finder's DataLayer received case replica before V1 RM triage"
    ):
        wait_for_case_on_container(
            client=finder_client,
            case_id=case.id_,
        )

    run_invite_path_rm_triage(
        invited_client=v1_client,
        invited_actor=v1_in_v1,
        offer=offer,
        report=report,
        finder=finder,
        auth_client=c1_client,
        case=case,
        invited_obj=v1,
    )

    # C1 invites C2 with CVDRole.COORDINATOR.
    invite_c2_result = None
    with demo_step("C1 invites C2 with CVDRole.COORDINATOR"):
        invite_c2_result = post_to_trigger(
            client=c1_client,
            actor_id=c1_in_c1.id_,
            behavior="invite-actor-to-case",
            body={
                "case_id": case.id_,
                "invitee_id": c2.id_,
                "roles": ["coordinator"],
            },
        )
    invite_c2 = as_TransitiveActivity.model_validate(
        invite_c2_result["activity"]
    )
    logger.info("C2 invite created: %s", invite_c2.id_)

    with demo_gate("CaseActor-routed Invite for C2 stored in C2's DataLayer"):
        invite_c2_id = find_case_invite_for_actor(
            client=c2_client,
            case_id=case.id_,
            invitee_id=c2.id_,
        )
        logger.info("CaseActor Invite for C2: %s", invite_c2_id)

        with demo_step("C2 accepts the case invitation"):
            post_to_trigger(
                client=c2_client,
                actor_id=c2_in_c2.id_,
                behavior="accept-case-invite",
                body={"invite_id": invite_c2_id},
            )

    with demo_check("C2's DataLayer received case replica"):
        wait_for_case_on_container(
            client=c2_client,
            case_id=case.id_,
        )

    # 5 participants: Finder + C1 + V1 + C2 + CaseActor
    wait_for_case_participants(
        vendor_client=c1_client,
        case_id=case.id_,
        expected_actor_ids={
            finder.id_,
            c1_in_c1.id_,
            v1.id_,
            c2_in_c2.id_,
        },
    )

    with demo_check(
        "M1: required participants (≥5), EM.ACTIVE, Finder + V1 + C2 have replicas"
    ):
        verify_case_active(
            receiver_client=c1_client,
            reporter_client=finder_client,
            case_id=case.id_,
            receiver_actor_id=c1.id_,
            reporter_actor_id=finder.id_,
        )

    # Drain the CaseActor's outbox before Phase 2 starts (ADR-0026, ADR-0058,
    # issue #2819).
    drain_phase1_ledger(
        auth_client=c1_client,
        case_id=case.id_,
        replica_pairs=[
            (finder_client, "Finder"),
            (v1_client, "V1"),
            (c2_client, "C2"),
        ],
    )

    case = as_VulnerabilityCase.model_validate(
        c1_client.get(c1_client.dl_path(case.id_))
    )
    return (
        finder,
        c1,
        c1_in_c1,
        v1,
        v1_in_v1,
        c2_in_c2,
        v2,
        report,
        offer,
        case,
    )


def _phase_c2_suggests_v2(
    finder_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    v2_client: DataLayerClient,
    c1_in_c1: as_Actor,
    c2_in_c2: as_Actor,
    v2: as_Actor,
    case: as_VulnerabilityCase,
    offer: as_Offer,
    report: as_VulnerabilityReport,
    finder: as_Actor,
    v1: as_Actor,
) -> None:
    """C2 suggests V2 via ADR-0026; C1 approves; V2 joins (DEMOMA-19-009)."""
    logger.info("─" * 80)
    logger.info("Phase 2: C2 suggests V2 → C1 approves → V2 joins")
    logger.info("─" * 80)

    # C2 sends suggest-actor-to-case (Offer(Actor, Case) → CaseActor).
    # roles must be explicit so EvaluateDefaultRolesNode doesn't fall back to
    # the hardcoded [VENDOR] default (issue #1969).
    with demo_step("C2 suggests V2 to CaseActor"):
        post_to_trigger(
            client=c2_client,
            actor_id=c2_in_c2.id_,
            behavior="suggest-actor-to-case",
            body={
                "case_id": case.id_,
                "suggested_actor_id": v2.id_,
                "roles": ["vendor", "deployer"],
            },
        )
    logger.info("C2 sent suggest-actor-to-case for V2 (%s)", v2.id_)

    # CaseActor processes Offer(Actor, Case) and forwards
    # Offer(CaseParticipant) to C1.  Poll C1's DataLayer for the offer.
    # All dependent steps (case_actor lookup and approve) are nested inside
    # demo_gate so they are skipped if the offer never arrives (ADR-0058).
    with demo_gate("Offer(CaseParticipant) for V2 arrived in C1's DataLayer"):
        cp_offer_id = find_cp_offer_for_case(
            client=c1_client,
            case_id=case.id_,
            timeout_seconds=40.0,
        )
        logger.info("Offer(CaseParticipant) ID: %s", cp_offer_id)

        # Find the CaseActor's participant ID so we can route the Accept back.
        case_actor_id = find_case_actor_participant_id(c1_client, case.id_)
        if case_actor_id is None:
            raise AssertionError(
                "CaseActor participant not found in case — cannot route Accept"
            )
        logger.info("CaseActor participant ID: %s", case_actor_id)

        # C1 approves the recommendation (CM-16-006).
        with demo_step("C1 approves actor recommendation"):
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

    # CaseActor sends Invite to V2.  Poll V2's DataLayer for the arriving
    # invite, then puppeteer V2's accept (DEMOMA-19-009: polling only).
    v2_in_v2 = get_actor_by_id(v2_client, v2.id_)

    invite_id = None
    with demo_check("V2 received invite from CaseActor (ADR-0026 path)"):
        invite_id = find_case_invite_for_actor(
            client=v2_client,
            case_id=case.id_,
            invitee_id=v2.id_,
            timeout_seconds=40.0,
        )
        logger.info("V2 received CaseActor invite: %s", invite_id)

    with demo_step("V2 accepts the CaseActor invitation"):
        post_to_trigger(
            client=v2_client,
            actor_id=v2_in_v2.id_,
            behavior="accept-case-invite",
            body={"invite_id": invite_id},
        )
    logger.info("V2 sent Accept(Invite) to CaseActor")

    with demo_check("V2's DataLayer received case replica"):
        wait_for_case_on_container(
            client=v2_client,
            case_id=case.id_,
            timeout_seconds=40.0,
        )
    logger.info("V2 received case replica via CaseActor (ADR-0026 path)")

    # 6 participants: Finder + C1 + V1 + C2 + V2 + CaseActor
    wait_for_case_participants(
        vendor_client=c1_client,
        case_id=case.id_,
        expected_actor_ids={
            finder.id_,
            c1_in_c1.id_,
            v1.id_,
            c2_in_c2.id_,
            v2.id_,
        },
        timeout_seconds=LATE_JOINER_TIMEOUT,
    )
    logger.info("✓ V2 joined case (6 participants)")

    with demo_check(
        "Finder's DataLayer received case replica before V2 RM triage"
    ):
        wait_for_case_on_container(
            client=finder_client,
            case_id=case.id_,
            timeout_seconds=40.0,
        )

    run_invite_path_rm_triage(
        invited_client=v2_client,
        invited_actor=v2_in_v2,
        offer=offer,
        report=report,
        finder=finder,
        auth_client=c1_client,
        case=case,
        invited_obj=v2,
        timeout_seconds=40.0,
    )


def _phase_sync_verification(
    finder_client: DataLayerClient,
    c1_client: DataLayerClient,
    v1_client: DataLayerClient,
    c2_client: DataLayerClient,
    v2_client: DataLayerClient,
    c1: as_Actor,
    finder: as_Actor,
    case: as_VulnerabilityCase,
    v1: as_Actor,
    c2_in_c2: as_Actor,
    v2: as_Actor,
) -> None:
    """Verify LedgerFanout replication for all participant replicas."""
    logger.info("─" * 80)
    logger.info("Phase 3: Replica synchronization verification (M1)")
    logger.info("─" * 80)

    with demo_gate("Finder case seeded before ledger coverage wait (SYNC-15)"):
        wait_for_case_on_container(client=finder_client, case_id=case.id_)
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
                (v1_client, "V1"),
                (c2_client, "C2"),
                # V2 is a late joiner that must catch up from genesis; allow extra
                # time for the full history to be delivered (LedgerFanout late-joiner).
                (v2_client, "V2"),
            ]:
                # V2 joins after Phase 1 completes, so it has more entries to sync.
                timeout = 45.0 if label == "V2" else 30.0
                with demo_gate(
                    f"{label} ledger coverage (sync-verification phase)"
                ):
                    wait_for_contiguous_ledger_coverage(
                        client=replica_client,
                        case_id=case.id_,
                        expected_tail_index=c1_tail_index,
                        timeout_seconds=timeout,
                    )
                logger.info("  %s ledger synchronized", label)

    for replica_client in (finder_client, v1_client, c2_client, v2_client):
        # V2 is a late joiner — allow extra time for participant index propagation.
        p_timeout = 30.0 if replica_client is v2_client else 10.0
        wait_for_case_participants(
            vendor_client=replica_client,
            case_id=case.id_,
            expected_actor_ids={
                finder.id_,
                c1.id_,
                v1.id_,
                c2_in_c2.id_,
                v2.id_,
            },
            timeout_seconds=p_timeout,
        )

    with demo_check("Finder replica matches authoritative C1 state"):
        verify_replica_state(
            auth_client=c1_client,
            replica_client=finder_client,
            case_id=case.id_,
            vendor_actor_id=c1.id_,
            reporter_actor_id=finder.id_,
        )

    with demo_check("V2 replica matches authoritative C1 state"):
        verify_replica_state(
            auth_client=c1_client,
            replica_client=v2_client,
            case_id=case.id_,
            vendor_actor_id=c1.id_,
            reporter_actor_id=finder.id_,
        )

    logger.info("✓ M1: All five replicas synchronized (LedgerFanout verified)")


def _phase_notes_exchange(
    finder_client: DataLayerClient,
    c1_client: DataLayerClient,
    v1_client: DataLayerClient,
    c2_client: DataLayerClient,
    v2_client: DataLayerClient,
    finder_in_finder: as_Actor,
    c1_in_c1: as_Actor,
    v1_in_v1: as_Actor,
    c2_in_c2: as_Actor,
    v2_in_v2: as_Actor,
    case: as_VulnerabilityCase,
) -> tuple[
    as_Note | None,
    as_Note | None,
    as_Note | None,
    as_Note | None,
    as_Note | None,
]:
    """Run a five-way note exchange among all participants."""
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
        in_reply_to=question_note.id_ if question_note is not None else None,
    )

    v1_note = participant_adds_note_to_case(
        posting_client=v1_client,
        watching_client=c1_client,
        poster=v1_in_v1,
        case=case,
        note_name="V1 Status Update",
        note_content=(
            "V1 has reproduced the issue. We will have a fix ready within 14 days."
        ),
        in_reply_to=c1_reply.id_ if c1_reply is not None else None,
    )

    c2_note = participant_adds_note_to_case(
        posting_client=c2_client,
        watching_client=c1_client,
        poster=c2_in_c2,
        case=case,
        note_name="C2 Update",
        note_content=(
            "C2 confirms V2 is engaged. Target disclosure in 30 days."
        ),
        in_reply_to=v1_note.id_ if v1_note is not None else None,
    )

    v2_note = participant_adds_note_to_case(
        posting_client=v2_client,
        watching_client=c1_client,
        poster=v2_in_v2,
        case=case,
        note_name="V2 Status Update",
        note_content=(
            "V2 confirms the issue affects our component. "
            "We will align our fix and deployment timeline with the 30-day target."
        ),
        in_reply_to=c2_note.id_ if c2_note is not None else None,
    )

    logger.info(
        "✓ Notes exchange complete (five notes committed to case ledger)"
    )
    return question_note, c1_reply, v1_note, c2_note, v2_note


def _phase_fix_lifecycle(
    c1_client: DataLayerClient,
    v1_client: DataLayerClient,
    v2_client: DataLayerClient,
    finder_client: DataLayerClient,
    v1: as_Actor,
    v1_in_v1: as_Actor,
    v2: as_Actor,
    v2_in_v2: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Advance V1 to VFd and V2 to VFD (DEMOMA-19-004).

    V1 (VENDOR only) stops at VFd — fix-ready, no deploy step.
    V2 (VENDOR + DEPLOYER) advances to VFD — fix-ready then fix-deployed.
    """
    logger.info("─" * 80)
    logger.info(
        "Phase 5: Fix lifecycle — V1: VFd (fix-ready); V2: VFD (fix-ready + fix-deployed)"
    )
    logger.info("─" * 80)

    # V1 advances to fix-ready (VFd).
    with demo_gate(
        "v1 RM ∈ {ACCEPTED,DEFERRED,CLOSED} before notify-fix-ready (CSB-18-001)"
    ):
        wait_for_participant_rm_state(
            client=v1_client,
            case_id=case.id_,
            actor_id=v1.id_,
            expected_states={RM.ACCEPTED, RM.DEFERRED, RM.CLOSED},
        )
        actor_notifies_fix_ready(
            client=v1_client,
            actor=v1_in_v1,
            case_id=case.id_,
        )
        with demo_check("V1 participant vfd_state transitions to VFd"):
            wait_for_participant_vfd_state(
                client=v1_client,
                case_id=case.id_,
                actor_id=v1.id_,
                expected_states={CS_vfd.VFd, CS_vfd.VFD},
            )

    # V2 advances to fix-ready (VFd).
    with demo_gate(
        "v2 RM ∈ {ACCEPTED,DEFERRED,CLOSED} before notify-fix-ready (CSB-18-001)"
    ):
        wait_for_participant_rm_state(
            client=v2_client,
            case_id=case.id_,
            actor_id=v2.id_,
            expected_states={RM.ACCEPTED, RM.DEFERRED, RM.CLOSED},
        )
        actor_notifies_fix_ready(
            client=v2_client,
            actor=v2_in_v2,
            case_id=case.id_,
        )
        with demo_check("V2 participant vfd_state transitions to VFd or VFD"):
            wait_for_participant_vfd_state(
                client=v2_client,
                case_id=case.id_,
                actor_id=v2.id_,
                expected_states={CS_vfd.VFd, CS_vfd.VFD},
            )

    with demo_check("M5: C1 replica shows V1 and V2 CS include F (fix ready)"):
        wait_for_participant_vfd_state(
            client=c1_client,
            case_id=case.id_,
            actor_id=v1.id_,
            expected_states={CS_vfd.VFd, CS_vfd.VFD},
        )
        wait_for_participant_vfd_state(
            client=c1_client,
            case_id=case.id_,
            actor_id=v2.id_,
            expected_states={CS_vfd.VFd, CS_vfd.VFD},
        )
        wait_for_participant_vfd_state(
            client=finder_client,
            case_id=case.id_,
            actor_id=v1.id_,
            expected_states={CS_vfd.VFd, CS_vfd.VFD},
        )
        wait_for_participant_vfd_state(
            client=finder_client,
            case_id=case.id_,
            actor_id=v2.id_,
            expected_states={CS_vfd.VFd, CS_vfd.VFD},
        )
        verify_fix_ready(
            receiver_client=v1_client,
            reporter_client=finder_client,
            case_id=case.id_,
            receiver_actor_id=v1.id_,
        )
        verify_fix_ready(
            receiver_client=v2_client,
            reporter_client=finder_client,
            case_id=case.id_,
            receiver_actor_id=v2.id_,
        )

    # V2 (VENDOR + DEPLOYER) advances to fix-deployed (VFD).
    actor_notifies_fix_deployed(
        client=v2_client,
        actor=v2_in_v2,
        case_id=case.id_,
    )

    with demo_check("V2 participant vfd_state transitions to VFD"):
        wait_for_participant_vfd_state(
            client=v2_client,
            case_id=case.id_,
            actor_id=v2.id_,
            expected_states={CS_vfd.VFD},
        )

    with demo_check(
        "M6: C1 replica shows V1=VFd (no deploy), V2=VFD (deployed)"
    ):
        wait_for_participant_vfd_state(
            client=c1_client,
            case_id=case.id_,
            actor_id=v1.id_,
            expected_states={CS_vfd.VFd},
        )
        wait_for_participant_vfd_state(
            client=c1_client,
            case_id=case.id_,
            actor_id=v2.id_,
            expected_states={CS_vfd.VFD},
        )
        wait_for_participant_vfd_state(
            client=finder_client,
            case_id=case.id_,
            actor_id=v1.id_,
            expected_states={CS_vfd.VFd},
        )
        wait_for_participant_vfd_state(
            client=finder_client,
            case_id=case.id_,
            actor_id=v2.id_,
            expected_states={CS_vfd.VFD},
        )
        verify_fix_ready(
            receiver_client=v1_client,
            reporter_client=finder_client,
            case_id=case.id_,
            receiver_actor_id=v1.id_,
        )
        verify_fix_deployed(
            receiver_client=v2_client,
            reporter_client=finder_client,
            case_id=case.id_,
            receiver_actor_id=v2.id_,
        )

    logger.info(
        "✓ Fix lifecycle: V1=VFd (no deploy path), V2=VFD (full deploy path)"
    )


def _phase_publication(
    finder_client: DataLayerClient,
    c1_client: DataLayerClient,
    v1_client: DataLayerClient,
    c2_client: DataLayerClient,
    v2_client: DataLayerClient,
    c1: as_Actor,
    c1_in_c1: as_Actor,
    c2_in_c2: as_Actor,
    v1: as_Actor,
    v1_in_v1: as_Actor,
    v2: as_Actor,
    v2_in_v2: as_Actor,
    finder_in_finder: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """V1 publishes first (triggering embargo teardown); then V2 publishes (DEMOMA-19-005)."""
    logger.info("─" * 80)
    logger.info(
        "Phase 6: Publication — V1 publishes first → EM.EXITED → V2 + others publish"
    )
    logger.info("─" * 80)

    # V1 (VENDOR only) triggers CS.P and the ThreatTerminationBranchNode
    # embargo teardown path (DEMOMA-19-005).
    actor_notifies_published(
        client=v1_client,
        actor=v1_in_v1,
        case_id=case.id_,
    )

    # Wait for CaseActor to process V1's publication and emit EM.EXITED
    # before V2 publishes to avoid a non-deterministic ledger ordering.
    with demo_check(
        "Embargo terminated (EM.EXITED) after V1 reports published"
    ):
        wait_for_case_em_terminated(
            client=v1_client,
            case_id=case.id_,
        )

    actor_notifies_published(
        client=v2_client,
        actor=v2_in_v2,
        case_id=case.id_,
    )
    actor_notifies_published(
        client=c2_client,
        actor=c2_in_c2,
        case_id=case.id_,
    )
    actor_notifies_published(
        client=c1_client,
        actor=c1_in_c1,
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
        "M7: all replicas EM.EXITED, all participants public-aware"
    ):
        wait_for_case_em_terminated(
            client=finder_client,
            case_id=case.id_,
        )
        wait_for_participant_vfd_state(
            client=c1_client,
            case_id=case.id_,
            actor_id=v1.id_,
            expected_states={CS_vfd.VFd},
        )
        wait_for_participant_vfd_state(
            client=c1_client,
            case_id=case.id_,
            actor_id=v2.id_,
            expected_states={CS_vfd.VFD},
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
    v1_client: DataLayerClient,
    c2_client: DataLayerClient,
    v2_client: DataLayerClient,
    c1_in_c1: as_Actor,
    v1_in_v1: as_Actor,
    c2_in_c2: as_Actor,
    v2_in_v2: as_Actor,
    finder_in_finder: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Close the case from all five participants and verify terminal state."""
    logger.info("─" * 80)
    logger.info("Phase 7: Case closure — all participants RM.CLOSED")
    logger.info("─" * 80)

    actor_closes_case(client=c1_client, actor=c1_in_c1, case_id=case.id_)
    actor_closes_case(client=v1_client, actor=v1_in_v1, case_id=case.id_)
    actor_closes_case(client=v2_client, actor=v2_in_v2, case_id=case.id_)
    actor_closes_case(client=c2_client, actor=c2_in_c2, case_id=case.id_)
    actor_closes_case(
        client=finder_client, actor=finder_in_finder, case_id=case.id_
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
            (v1_client, "V1"),
            (c2_client, "C2"),
            (v2_client, "V2"),
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
    v1_client: DataLayerClient,
    c2_client: DataLayerClient,
    v2_client: DataLayerClient,
    case: as_VulnerabilityCase,
    demo_name: str = "fcvcv",
) -> None:
    """Dump case ledger entries from each actor container to JSONL files.

    Thin scenario-specific wrapper over
    :func:`~vultron.demo.helpers.ledger_dump.dump_case_ledgers`, which owns the
    per-actor export, the 404 handling, and the dump manifest. This function
    only names FCVCV's participants and where each one's ledger lives.
    """
    # Devlog directory names use scenario-role names (DEMOMA-19-007):
    # finder, c1, v1, c2, v2, case-actor.
    # Route keys come from each client's own actor id, not its display name:
    # the key selects the store (ADR-0073), so a literal is right only while
    # the scenario seeds deterministic named ids. The literal passed to
    # replica_route_key() is the docker-compose seed name, kept as the fallback
    # for a client that was never bound.
    targets = [
        LedgerDumpTarget(
            "finder", finder_client, replica_route_key(finder_client, "finder")
        ),
        # C1 is on the coordinator container.
        LedgerDumpTarget(
            "c1", c1_client, replica_route_key(c1_client, "coordinator")
        ),
        # V1 is on the vendor container.
        LedgerDumpTarget(
            "v1", v1_client, replica_route_key(v1_client, "vendor")
        ),
        # C2 is on actor5 (seeded as "vendor2").
        LedgerDumpTarget(
            "c2", c2_client, replica_route_key(c2_client, "vendor2")
        ),
        # V2 is on actor6 (seeded as "vendor-deployer").
        LedgerDumpTarget(
            "v2", v2_client, replica_route_key(v2_client, "vendor-deployer")
        ),
    ]
    # The case-actor is a sub-actor inside the C1 container.
    case_actor_route_key = resolve_case_actor_route_key(case)
    if case_actor_route_key is not None:
        targets.append(
            LedgerDumpTarget("case-actor", c1_client, case_actor_route_key)
        )

    dump_case_ledgers(demo_name=demo_name, case=case, targets=targets)


def run_fcvcv_demo(
    finder_client: DataLayerClient,
    c1_client: DataLayerClient,
    v1_client: DataLayerClient,
    c2_client: DataLayerClient,
    v2_client: DataLayerClient,
    finder_id: str | None = None,
    c1_id: str | None = None,
    v1_id: str | None = None,
    c2_id: str | None = None,
    v2_id: str | None = None,
) -> None:
    """Orchestrate the FCVCV CVD workflow."""
    logger.info("=" * 80)
    logger.info(
        "FCVCV DEMO: Finder + C1(CASE_OWNER) + V1(VENDOR) + C2(COORDINATOR) + V2(VENDOR+DEPLOYER)"
    )
    logger.info("=" * 80)
    logger.info("Finder container: %s", finder_client.base_url)
    logger.info("C1 container:     %s", c1_client.base_url)
    logger.info("V1 container:     %s", v1_client.base_url)
    logger.info("C2 container:     %s", c2_client.base_url)
    logger.info("V2 container:     %s", v2_client.base_url)

    with scenario_harness("fcvcv") as harness:
        (
            finder,
            c1,
            c1_in_c1,
            v1,
            v1_in_v1,
            c2_in_c2,
            v2,
            report,
            offer,
            case,
        ) = _phase_report_submission(
            finder_client,
            c1_client,
            v1_client,
            c2_client,
            v2_client,
            finder_id,
            c1_id,
            v1_id,
            c2_id,
            v2_id,
        )

        # Register the dump as soon as there is a case to dump, so every phase
        # below can fail without costing us the ledgers (ISSUE-2239).
        harness.dump_with(
            lambda: _phase_dump_case_ledgers(
                finder_client=finder_client,
                c1_client=c1_client,
                v1_client=v1_client,
                c2_client=c2_client,
                v2_client=v2_client,
                case=case,
                demo_name=harness.demo_name,
            )
        )

        _phase_c2_suggests_v2(
            finder_client=finder_client,
            c1_client=c1_client,
            c2_client=c2_client,
            v2_client=v2_client,
            c1_in_c1=c1_in_c1,
            c2_in_c2=c2_in_c2,
            v2=v2,
            case=case,
            offer=offer,
            report=report,
            finder=finder,
            v1=v1,
        )

        v2_in_v2 = get_actor_by_id(v2_client, v2.id_)
        finder_in_finder = get_actor_by_id(finder_client, finder.id_)

        _phase_sync_verification(
            finder_client,
            c1_client,
            v1_client,
            c2_client,
            v2_client,
            c1,
            finder,
            case,
            v1,
            c2_in_c2,
            v2,
        )
        _phase_notes_exchange(
            finder_client=finder_client,
            c1_client=c1_client,
            v1_client=v1_client,
            c2_client=c2_client,
            v2_client=v2_client,
            finder_in_finder=finder_in_finder,
            c1_in_c1=c1_in_c1,
            v1_in_v1=v1_in_v1,
            c2_in_c2=c2_in_c2,
            v2_in_v2=v2_in_v2,
            case=case,
        )
        _phase_fix_lifecycle(
            c1_client,
            v1_client,
            v2_client,
            finder_client,
            v1,
            v1_in_v1,
            v2,
            v2_in_v2,
            case,
        )
        _phase_publication(
            finder_client,
            c1_client,
            v1_client,
            c2_client,
            v2_client,
            c1,
            c1_in_c1,
            c2_in_c2,
            v1,
            v1_in_v1,
            v2,
            v2_in_v2,
            finder_in_finder,
            case,
        )
        _phase_case_closure(
            finder_client,
            c1_client,
            v1_client,
            c2_client,
            v2_client,
            c1_in_c1,
            v1_in_v1,
            c2_in_c2,
            v2_in_v2,
            finder_in_finder,
            case,
        )

    logger.info("=" * 80)
    logger.info("FCVCV DEMO COMPLETE ✓  (full 5-actor lifecycle)")
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(
    skip_health_check: bool = False,
    finder_url: str | None = None,
    c1_url: str | None = None,
    v1_url: str | None = None,
    c2_url: str | None = None,
    v2_url: str | None = None,
    finder_id: str | None = None,
    c1_id: str | None = None,
    v1_id: str | None = None,
    c2_id: str | None = None,
    v2_id: str | None = None,
) -> None:
    """Entry point for the FCVCV CVD workflow demo.

    Args:
        skip_health_check: Skip server availability checks.
        finder_url: Override base URL for the Finder container.
        c1_url: Override base URL for the C1 (Coordinator1) container.
        v1_url: Override base URL for the V1 (Vendor1) container.
        c2_url: Override base URL for the C2 (Coordinator2) container.
        v2_url: Override base URL for the V2 (VendorDeployer) container.
        finder_id: Optional deterministic URI for the Finder actor.
        c1_id: Optional deterministic URI for the C1 actor.
        v1_id: Optional deterministic URI for the V1 actor.
        c2_id: Optional deterministic URI for the C2 actor.
        v2_id: Optional deterministic URI for the V2 actor.
    """
    f_url = finder_url or FINDER_BASE_URL
    c1_resolved = c1_url or C1_BASE_URL
    v1_resolved = v1_url or V1_BASE_URL
    c2_resolved = c2_url or C2_BASE_URL
    v2_resolved = v2_url or V2_BASE_URL

    finder_client = DataLayerClient(base_url=f_url)
    c1_client = DataLayerClient(base_url=c1_resolved)
    v1_client = DataLayerClient(base_url=v1_resolved)
    c2_client = DataLayerClient(base_url=c2_resolved)
    v2_client = DataLayerClient(base_url=v2_resolved)

    if not skip_health_check:
        targets: list[tuple[str, DataLayerClient]] = [
            ("Finder", finder_client),
            ("C1", c1_client),
            ("V1", v1_client),
            ("C2", c2_client),
            ("V2", v2_client),
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

    # scenario_harness() inside run_fcvcv_demo() owns the failure accumulator:
    # it resets it, always dumps the case ledgers, and asserts success — so a
    # failure here never costs us the artifacts (ISSUE-2239).
    run_fcvcv_demo(
        finder_client=finder_client,
        c1_client=c1_client,
        v1_client=v1_client,
        c2_client=c2_client,
        v2_client=v2_client,
        finder_id=finder_id or FINDER_ACTOR_ID,
        c1_id=c1_id or C1_ACTOR_ID,
        v1_id=v1_id or V1_ACTOR_ID,
        c2_id=c2_id or C2_ACTOR_ID,
        v2_id=v2_id or V2_ACTOR_ID,
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
