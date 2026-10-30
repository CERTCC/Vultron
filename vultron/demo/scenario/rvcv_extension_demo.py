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

"""Reporter → Vendor1 (CASE_OWNER) + Coordinator + Vendor2 (RVCV-extension) demo.

Orchestrates the full VFDPxa lifecycle across four separate containers:
Reporter, Vendor1 (CASE_OWNER throughout), Coordinator (CVDRole.COORDINATOR),
and Vendor2.  Coordinator suggests Vendor2 via the ADR-0026 CaseActor-routed
suggest-actor flow; Vendor1 approves; CaseActor invites Vendor2.

Spec: D5-6 (GitHub issue #1535).
"""

import logging
import sys

from vultron.core.states.cs import CS_vf
from vultron.core.states.rm import RM
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.actor_roles import (
    ActorRole,
    case_actor_role,
    resolved_actor_ids,
    role_map,
)
from vultron.demo.helpers.cast import (
    CAST,
    COORDINATOR_SLOT,
    REPORTER_SLOT,
    VENDOR_SLOT,
)
from vultron.demo.helpers.closure import CaseLeaver, close_case_owner_last
from vultron.demo.helpers.harness import (
    follow_ledger,
    reach_step,
    scenario_harness,
)
from vultron.demo.helpers.invite_chain import (
    CaseInviter,
    run_case_invite_chain,
)
from vultron.demo.helpers.ledger_dump import (
    LedgerDumpTarget,
    case_actor_dump_target,
    dump_case_ledgers,
    replica_route_key,
)
from vultron.demo.helpers.milestones import (
    verify_case_active,
    verify_fix_ready,
    verify_publicly_disclosed,
)
from vultron.demo.helpers.notes import (
    WORKAROUND_QUESTION,
    NotePost,
    add_note_thread,
    reporter_asks,
    vendor_answers_workaround,
)
from vultron.demo.helpers.polling import (
    LATE_JOINER_TIMEOUT,
    find_case_actor_participant_id,
    find_cp_offer_for_case,
    wait_for_case_em_terminated,
    wait_for_case_on_container,
    wait_for_case_participants,
    wait_for_participant_rm_state,
    wait_for_participant_vf_state,
)
from vultron.demo.helpers.seeding import (
    get_actor_by_id,
    reset_containers as _reset_containers,
    seed_containers_rvcv,
)
from vultron.demo.helpers.sync import (
    run_sync_verification_phase,
    wait_for_replica_ledger_coverage,
)
from vultron.demo.helpers.workflow import (
    reporter_submits_report,
    run_direct_path_rm_triage,
    run_invite_path_rm_triage,
)
from vultron.demo.scenario.registry import scenario
from vultron.demo.utils import (  # noqa: F401 — re-exported for test monkeypatching
    BASE_URL,
    DataLayerClient,
    assert_demo_success,
    bound_case_actor_client,
    check_server_availability,
    demo_check,
    demo_gate,
    demo_step,
    ref_id,
    reset_datalayer,
    reset_demo_failures,
    setup_demo_logging,
    verify_object_stored,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Offer,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

logger = logging.getLogger(__name__)

# The scenario's actors in main() parameter order, each seated in a container of
# the fixed cast (DEMOCI-11-020).  The demo CLI derives this scenario's
# sub-command options from this list (DEMOCI-11-011).
ROLES: list[ActorRole] = [
    ActorRole("reporter", REPORTER_SLOT, "Reporter", has_id=True),
    ActorRole("vendor", VENDOR_SLOT, "Vendor1", has_id=True),
    ActorRole("coordinator", COORDINATOR_SLOT, "Coordinator", has_id=True),
    ActorRole("vendor2", CAST[3], "Vendor2", has_id=True),
    case_actor_role(),
]
_ROLES = role_map(ROLES)

REPORTER_BASE_URL = _ROLES["reporter"].url
VENDOR_BASE_URL = _ROLES["vendor"].url
COORDINATOR_BASE_URL = _ROLES["coordinator"].url
VENDOR2_BASE_URL = _ROLES["vendor2"].url
CASE_ACTOR_BASE_URL = _ROLES["case-actor"].url

#: ``vultron-demo rvcv-extension --help`` text. Lives here rather than in
#: ``cli.py`` because the sub-command is generated from the registry and the
#: scenario module is the only place that knows what its own workflow does.
CLI_HELP = """Run the RVCV-extension (Reporter + Vendor1 + Coordinator + Vendor2) demo (D5-6).

Vendor1 retains CASE_OWNER throughout.  Coordinator holds CVDRole.COORDINATOR
(not CASE_MANAGER).  Coordinator suggests Vendor2 via the ADR-0026
CaseActor-routed suggest-actor flow; Vendor1 approves; CaseActor invites
Vendor2.  Both vendors then independently advance through the full fix and
publication lifecycle.

\b
Workflow:
  1. Seed all four containers (actor records + peer registration).
  2. Reporter submits a vulnerability report to Vendor1's inbox.
  3. Vendor1 validates and engages the case.
  4. Vendor1 invites Coordinator with CVDRole.COORDINATOR.
  5. Coordinator accepts; Coordinator suggests Vendor2 (ADR-0026).
  6. Vendor1 approves the actor recommendation.
  7. CaseActor invites Vendor2; Vendor2 accepts.
  8. Verify LedgerFanout replication on all replicas.
  9. Both vendors independently advance through fix-ready → fix-deployed.
 10. All participants report publication; embargo terminates.
 11. All participants close the case.
"""


def reset_containers(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    case_actor_client: DataLayerClient,
) -> None:
    """Reset the four RVCV containers and the dedicated case-actor container.

    The case-actor container's CaseActor identity is re-seeded after the reset,
    since Vendor1 proposes the case to it (DEMOMA-06-004).
    """
    targets: list[tuple[str, DataLayerClient]] = [
        ("Reporter", reporter_client),
        ("Vendor1", vendor_client),
        ("Coordinator", coordinator_client),
        ("Vendor2", vendor2_client),
    ]
    _reset_containers(
        targets,
        reset_fn=reset_datalayer,
        case_actor_client=case_actor_client,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Phase helpers
# ---------------------------------------------------------------------------


def _phase_report_submission(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    reporter_id: str | None,
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
    as_Offer,
    as_VulnerabilityCase,
    as_Note | None,
]:
    """Reset, seed, submit, validate, engage, exchange notes, invite Coordinator, M1.

    The Reporter's question and Vendor1's answer run before the Coordinator is
    invited, so Vendor1's branch point (invite a Coordinator) follows them on
    the scenario tree (``notes/demo-scenario-tree.md``).

    Returns:
        The cast, the report and offer, the refreshed case, and Vendor1's
        reply note (``None`` when the exchange failed), which the joiners'
        notes answer later.
    """
    logger.info("─" * 80)
    logger.info("Phase 1: Report submission and case activation")
    logger.info("─" * 80)

    reset_containers(
        reporter_client=reporter_client,
        vendor_client=vendor_client,
        coordinator_client=coordinator_client,
        vendor2_client=vendor2_client,
        case_actor_client=case_actor_client,
    )

    reporter = vendor = coordinator = vendor2 = None
    reply_note: as_Note | None = None
    with demo_step("Seeding all four containers with actor records"):
        reporter, vendor, coordinator, vendor2 = seed_containers_rvcv(
            reporter_client=reporter_client,
            vendor_client=vendor_client,
            coordinator_client=coordinator_client,
            vendor2_client=vendor2_client,
            reporter_actor_id=reporter_id,
            vendor_actor_id=vendor_id,
            coordinator_actor_id=coordinator_id,
            vendor2_actor_id=vendor2_id,
            case_actor_client=case_actor_client,
        )

    vendor_in_vendor = get_actor_by_id(vendor_client, vendor.id_)
    coordinator_in_coordinator = get_actor_by_id(
        coordinator_client, coordinator.id_
    )

    # The Reporter's decision; its role comes from submitting the report.
    reach_step("reporter-whom-to-tell", "vendor", by=reporter.id_)
    report, offer = reporter_submits_report(
        receiver_client=vendor_client,
        reporter=reporter,
        receiver=vendor_in_vendor,
        reporter_client=reporter_client,
    )
    case = run_direct_path_rm_triage(
        receiver_client=vendor_client,
        receiver=vendor_in_vendor,
        offer=offer,
        timeout_seconds=60.0,
    )

    # Causal precondition: the initial case (Reporter + Vendor1 present on
    # Vendor1's replica) must exist before Coordinator is invited.  A demo_gate —
    # not demo_check — so a timeout skips the doomed invite/admit steps rather
    # than cascading (DEMOCI-01-011, vultron/demo/AGENTS.md § "Never Wrap a
    # Causal Wait in demo_check").
    with demo_gate(
        "Vendor1 case has Reporter + Vendor1 before inviting Coordinator"
    ):
        wait_for_case_participants(
            vendor_client=vendor_client,
            case_id=case.id_,
            expected_actor_ids={reporter.id_, vendor.id_},
        )

        # The Reporter asks and Vendor1 answers before Vendor1 decides to
        # invite a Coordinator, its branch point on the scenario tree.
        reply_note = _phase_notes_exchange(
            reporter_client=reporter_client,
            vendor_client=vendor_client,
            reporter=reporter,
            vendor_in_vendor=vendor_in_vendor,
            case=case,
        )
        follow_ledger(case_actor_client, case.id_)
        reach_step("vendor-after-answer", "invite-coordinator", by=vendor.id_)

        # Vendor1 invites Coordinator (COORDINATOR role only, not CASE_MANAGER).
        # The chain nests the delivery gate, the accept and the replica wait
        # inside the invite step, so a failed trigger or lookup skips its
        # dependents (ADR-0058 nested-block model, EDF-06-005, #3038).
        def _check_coordinator_joined() -> None:
            # 4 participants: Reporter + Vendor1 + Coordinator + CaseActor
            with demo_check(
                "Vendor1 case reflects Reporter + Vendor1 + Coordinator"
                " participants"
            ):
                wait_for_case_participants(
                    vendor_client=vendor_client,
                    case_id=case.id_,
                    expected_actor_ids={
                        reporter.id_,
                        vendor.id_,
                        coordinator_in_coordinator.id_,
                    },
                )

        run_case_invite_chain(
            case=case,
            case_manager_client=case_actor_client,
            invitee_name="Coordinator",
            invitee_client=coordinator_client,
            invitee=coordinator,
            invitee_in_own_container=coordinator_in_coordinator,
            inviter=CaseInviter(
                name="Vendor1",
                client=vendor_client,
                actor=vendor_in_vendor,
                role=CVDRole.COORDINATOR,
            ),
            invite_timeout=60.0,
            then=_check_coordinator_joined,
        )

    with demo_check(
        "M1: required participants (≥4), EM.ACTIVE, reporter + coordinator have replicas"
    ):
        verify_case_active(
            receiver_client=vendor_client,
            reporter_client=reporter_client,
            case_id=case.id_,
            receiver_actor_id=vendor.id_,
            reporter_actor_id=reporter.id_,
        )

    # Wait for the Phase 1 ledger to reach every replica before Phase 2 starts
    # (ADR-0026, ADR-0058).  Added as a workaround for #2819 when the CaseActor
    # queued its ledger fan-out ahead of Create(VulnerabilityCase) and every
    # replica rejected and replayed; that ordering is fixed at the source
    # (CP-09-009, CM-17-009, #2898), so this is now a plain replication check
    # that also keeps Phase 2's ledger indices deterministic.  It is the same
    # read-authority-tail-then-poll-each-replica loop as the sync-verification
    # and closure phases, so it goes through the one shared helper
    # (DEMOMA-23-005, #3906); each replica wait is a demo_gate inside it.
    wait_for_replica_ledger_coverage(
        auth_client=vendor_client,
        replicas=[
            (reporter_client, "Reporter"),
            (coordinator_client, "Coordinator"),
        ],
        case_id=case.id_,
        phase_label="Phase 1 drain before Phase 2",
    )

    case = as_VulnerabilityCase.model_validate(
        vendor_client.get(vendor_client.dl_path(case.id_))
    )
    return (
        reporter,
        vendor,
        vendor_in_vendor,
        coordinator,
        coordinator_in_coordinator,
        vendor2,
        report,
        offer,
        case,
        reply_note,
    )


def _phase_coordinator_suggests_vendor2(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    coordinator_in_coordinator: as_Actor,
    vendor2: as_Actor,
    vendor2_in_vendor2: as_Actor,
    case: as_VulnerabilityCase,
    offer: as_Offer,
    report: as_VulnerabilityReport,
    reporter: as_Actor,
) -> None:
    """Coordinator suggests Vendor2 via ADR-0026; Vendor1 approves; Vendor2 joins."""
    logger.info("─" * 80)
    logger.info(
        "Phase 2: Coordinator suggests Vendor2 → Vendor1 approves → Vendor2 joins"
    )
    logger.info("─" * 80)

    # Step M3: Coordinator sends suggest-actor-to-case (Offer(Actor, Case) → CaseActor).
    with demo_step("Coordinator suggests Vendor2 to CaseActor"):
        ActorSession(
            client=coordinator_client, actor=coordinator_in_coordinator
        ).with_case(case).quiet().suggest_actor_to_case(
            suggested_actor_id=vendor2.id_,
            roles=[CVDRole.VENDOR],
        )
    logger.info(
        "Coordinator sent suggest-actor-to-case for Vendor2 (%s)", vendor2.id_
    )

    # CaseActor processes Offer(Actor, Case) and forwards Offer(CaseParticipant)
    # to Vendor1 (CASE_OWNER).  Poll Vendor1's DataLayer for the offer.
    # All dependent steps (case_actor lookup and approve) are nested inside
    # demo_gate so they are skipped if the offer never arrives (ADR-0058).
    with demo_gate(
        "Offer(CaseParticipant) for Vendor2 arrived in Vendor1's DataLayer"
    ):
        cp_offer_id = find_cp_offer_for_case(
            client=vendor_client,
            case_id=case.id_,
            timeout_seconds=40.0,
        )
        logger.info("Offer(CaseParticipant) ID: %s", cp_offer_id)

        # Find the CaseActor's participant ID so we can route the Accept back.
        case_actor_id = find_case_actor_participant_id(vendor_client, case.id_)
        if case_actor_id is None:
            raise AssertionError(
                "CaseActor participant not found in case — cannot route Accept"
            )
        logger.info("CaseActor participant ID: %s", case_actor_id)

        # Step M4 (ADR-0026 CM-16-006): Vendor1 approves the recommendation.
        with demo_step(
            "Vendor1 approves actor recommendation (accept-actor-recommendation)"
        ):
            ActorSession(
                client=vendor_client, actor=vendor_in_vendor
            ).quiet().accept_actor_recommendation(
                cp_offer_id=cp_offer_id,
                case_actor_id=case_actor_id,
            )
    logger.info("Vendor1 sent Accept(Offer(CaseParticipant)) to CaseActor")

    # CaseActor receives Accept → emits Invite(Actor, CaseStub) to Vendor2.  Per
    # MV-10-004 the Invite alone does NOT seed Vendor2's case replica; Vendor2
    # must Accept(Invite) so the CaseActor sends the trust-bootstrap
    # Announce(VulnerabilityCase) (MV-10-003).  The chain polls Vendor2's
    # DataLayer for the Invite and puppeteers the accept (ADR-0026
    # invite/accept/bootstrap chain; DEMOMA-10-005 / CM-16-006), nesting
    # everything after the invite inside its gate (EDF-06-005, #3038).
    run_case_invite_chain(
        case=case,
        invitee_name="Vendor2",
        invitee_client=vendor2_client,
        invitee=vendor2,
        invitee_in_own_container=vendor2_in_vendor2,
        invite_timeout=60.0,
        replica_timeout=60.0,
        ledger_client=case_actor_client,
        reply_timeout=60.0,
    )

    # All 5 participants (Reporter + Vendor1 + Coordinator + Vendor2 + CaseActor)
    # present is the causal precondition for Vendor2's RM triage below.  Vendor2
    # joins via the CaseActor→Vendor2 invite path (ADR-0026), which requires an
    # extra propagation hop back to Vendor1; use a longer timeout.  A demo_gate —
    # not demo_check — so a timeout skips the doomed triage rather than cascading
    # (DEMOCI-01-011, vultron/demo/AGENTS.md § "Never Wrap a Causal Wait in
    # demo_check").
    with demo_gate(
        "Vendor1 case has all 5 participants before Vendor2 RM triage"
    ):
        wait_for_case_participants(
            vendor_client=vendor_client,
            case_id=case.id_,
            expected_actor_ids={
                reporter.id_,
                vendor.id_,
                coordinator_in_coordinator.id_,
                vendor2.id_,
            },
            timeout_seconds=LATE_JOINER_TIMEOUT,
        )
        logger.info("✓ M3: Vendor2 joined case (%d participants)", 5)

        # CLP-08-005: ensure Reporter's genesis hash is seeded before
        # Announce(CaseLedgerEntry) is broadcast by the triage cycle below.
        with demo_check(
            "Reporter's DataLayer received case replica before Vendor2 RM triage"
        ):
            wait_for_case_on_container(
                client=reporter_client,
                case_id=case.id_,
                timeout_seconds=60.0,
            )

        run_invite_path_rm_triage(
            invited_client=vendor2_client,
            invited_actor=vendor2_in_vendor2,
            offer=offer,
            report=report,
            reporter=reporter,
            auth_client=case_actor_client,
            case=case,
            invited_obj=vendor2,
            timeout_seconds=60.0,
        )


def _phase_sync_verification(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    vendor: as_Actor,
    reporter: as_Actor,
    coordinator: as_Actor,
    vendor2: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Verify LedgerFanout replication for Reporter, Coordinator, and Vendor2 replicas."""
    logger.info("─" * 80)
    logger.info("Phase 3: Replica synchronization verification")
    logger.info("─" * 80)

    run_sync_verification_phase(
        auth_client=vendor_client,
        auth_label="Vendor1",
        auth_actor_id=vendor.id_,
        reporter_client=reporter_client,
        reporter_actor_id=reporter.id_,
        replicas=[
            (reporter_client, "Reporter"),
            (coordinator_client, "Coordinator"),
            (vendor2_client, "Vendor2"),
        ],
        case_id=case.id_,
        expected_participant_ids={
            reporter.id_,
            vendor.id_,
            coordinator.id_,
            vendor2.id_,
        },
        # Vendor2 joins by invitation after the early replicas exist (#2202).
        late_joiners=(vendor2_client,),
        state_checks=[
            (reporter_client, "Reporter"),
            (vendor2_client, "Vendor2"),
        ],
    )

    logger.info("✓ M4: All replicas synchronized (LedgerFanout verified)")


def _phase_notes_exchange(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    reporter: as_Actor,
    vendor_in_vendor: as_Actor,
    case: as_VulnerabilityCase,
) -> as_Note | None:
    """The Reporter asks a question and Vendor1 answers it.

    Gated on the Reporter's replica holding the case, since the Reporter posts
    from it (DEMOMA-22-001).

    Returns:
        Vendor1's reply note, or ``None`` when the exchange or its gate failed
        (the failure is recorded).
    """
    logger.info("─" * 80)
    logger.info("Notes exchange: Reporter asks, Vendor1 answers")
    logger.info("─" * 80)

    reporter_in_reporter = get_actor_by_id(reporter_client, reporter.id_)
    return reporter_asks(
        ActorSession(client=reporter_client, actor=reporter_in_reporter),
        vendor_client,
        case,
        WORKAROUND_QUESTION,
        [
            vendor_answers_workaround(
                ActorSession(client=vendor_client, actor=vendor_in_vendor)
            ),
        ],
    )


def _phase_joiner_notes(
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    coordinator_in_coordinator: as_Actor,
    vendor2_in_vendor2: as_Actor,
    case: as_VulnerabilityCase,
    reply_note: as_Note | None,
) -> as_Note | None:
    """The Coordinator and Vendor2, once joined, add to the notes thread.

    Returns:
        Vendor2's note, or ``None`` when it failed.
    """
    logger.info("─" * 80)
    logger.info("Phase 4: Coordinator and Vendor2 notes")
    logger.info("─" * 80)

    vendor2_note = add_note_thread(
        vendor_client,
        case,
        [
            NotePost(
                ActorSession(
                    client=coordinator_client, actor=coordinator_in_coordinator
                ),
                "Coordinator Update",
                "We have confirmed that both Vendor1 and Vendor2 are engaged. "
                "Target disclosure in 30 days.",
            ),
            NotePost(
                ActorSession(client=vendor2_client, actor=vendor2_in_vendor2),
                "Vendor2 Status Update",
                "Vendor2 can confirm the issue affects our component as well. "
                "We will align our fix timeline with Vendor1.",
            ),
        ],
        in_reply_to=reply_note,
    )

    logger.info(
        "✓ Notes exchange complete (Coordinator and Vendor2 notes added to the thread)"
    )
    return vendor2_note


def _phase_fix_lifecycle(
    reporter_client: DataLayerClient,
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
        with demo_step(f"Actor {ref_id(vendor_in_vendor)} reports fix ready"):
            ActorSession(
                client=vendor_client, actor=vendor_in_vendor
            ).with_case(case).quiet().notify_fix_ready()
        with demo_check("Vendor1 participant vf_state transitions to VF"):
            wait_for_participant_vf_state(
                client=vendor_client,
                case_id=case.id_,
                actor_id=vendor.id_,
                expected_states={CS_vf.VF},
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
        with demo_step(
            f"Actor {ref_id(vendor2_in_vendor2)} reports fix ready"
        ):
            ActorSession(
                client=vendor2_client, actor=vendor2_in_vendor2
            ).with_case(case).quiet().notify_fix_ready()
        with demo_check("Vendor2 participant vf_state transitions to VF"):
            wait_for_participant_vf_state(
                client=vendor2_client,
                case_id=case.id_,
                actor_id=vendor2.id_,
                expected_states={CS_vf.VF},
            )

    with demo_check(
        "M5: Reporter replica shows both vendors CS include F (fix ready)"
    ):
        wait_for_participant_vf_state(
            client=vendor_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vf.VF},
        )
        wait_for_participant_vf_state(
            client=reporter_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vf.VF},
        )
        verify_fix_ready(
            receiver_client=vendor_client,
            reporter_client=reporter_client,
            case_id=case.id_,
            receiver_actor_id=vendor.id_,
        )

    with demo_check(
        "M6: Reporter replica shows both vendors CS include F (fix ready) — vendors stop at VFd"
    ):
        wait_for_participant_vf_state(
            client=vendor_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vf.VF},
        )
        wait_for_participant_vf_state(
            client=reporter_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vf.VF},
        )
        verify_fix_ready(
            receiver_client=vendor_client,
            reporter_client=reporter_client,
            case_id=case.id_,
            receiver_actor_id=vendor.id_,
        )


def _phase_publication(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    vendor2: as_Actor,
    vendor2_in_vendor2: as_Actor,
    reporter: as_Actor,
    reporter_in_reporter: as_Actor,
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

    with demo_step(
        f"Actor {ref_id(vendor_in_vendor)} reports vulnerability publicly disclosed"
    ):
        ActorSession(client=vendor_client, actor=vendor_in_vendor).with_case(
            case
        ).quiet().notify_published()

    with demo_check(
        "Embargo terminated (EM.EXITED) after Vendor1 reports published"
    ):
        wait_for_case_em_terminated(
            client=vendor_client,
            case_id=case.id_,
        )

    with demo_step(
        f"Actor {ref_id(vendor2_in_vendor2)} reports vulnerability publicly disclosed"
    ):
        ActorSession(
            client=vendor2_client, actor=vendor2_in_vendor2
        ).with_case(case).quiet().notify_published()
    with demo_step(
        f"Actor {ref_id(coordinator_in_coordinator)} reports vulnerability publicly disclosed"
    ):
        ActorSession(
            client=coordinator_client, actor=coordinator_in_coordinator
        ).with_case(case).quiet().notify_published()

    with demo_check(
        "Embargo terminated (EM.EXITED) propagated to Reporter before notify-published"
    ):
        wait_for_case_em_terminated(
            client=reporter_client,
            case_id=case.id_,
        )

    with demo_step(
        f"Actor {ref_id(reporter_in_reporter)} reports vulnerability publicly disclosed"
    ):
        ActorSession(
            client=reporter_client, actor=reporter_in_reporter
        ).with_case(case).quiet().notify_published()

    with demo_check(
        "M7: all replicas CS.VFdPxa, EM.EXITED, all participants public-aware"
    ):
        wait_for_case_em_terminated(
            client=reporter_client,
            case_id=case.id_,
        )
        wait_for_participant_vf_state(
            client=vendor_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vf.VF},
        )
        wait_for_participant_vf_state(
            client=reporter_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vf.VF},
        )
        verify_publicly_disclosed(
            receiver_client=vendor_client,
            reporter_client=reporter_client,
            case_id=case.id_,
            receiver_actor_id=vendor.id_,
        )


def _phase_case_closure(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    vendor2: as_Actor,
    vendor2_in_vendor2: as_Actor,
    reporter: as_Actor,
    reporter_in_reporter: as_Actor,
    coordinator: as_Actor,
    coordinator_in_coordinator: as_Actor,
    case: as_VulnerabilityCase,
    case_actor_client: DataLayerClient,
) -> None:
    """Close the case from all four participants and verify terminal state.

    Vendor2, the Coordinator and the Reporter leave first; Vendor1, the Case
    Owner throughout, leaves last, once their departures are recorded
    (CM-23-015) in the CASE_MANAGER's store on the dedicated case-actor
    container.
    """
    logger.info("─" * 80)
    logger.info("Phase 7: Case closure — all participants RM.CLOSED")
    logger.info("─" * 80)

    close_case_owner_last(
        case=case,
        milestone="M8",
        authority_client=case_actor_client,
        others=[
            CaseLeaver(client=vendor2_client, actor=vendor2_in_vendor2),
            CaseLeaver(
                client=coordinator_client, actor=coordinator_in_coordinator
            ),
            CaseLeaver(client=reporter_client, actor=reporter_in_reporter),
        ],
        owner=CaseLeaver(client=vendor_client, actor=vendor_in_vendor),
    )


def _phase_dump_case_ledgers(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    reporter: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
    vendor2: as_Actor,
    case: as_VulnerabilityCase,
    case_actor_client: DataLayerClient,
    demo_name: str = "rvcv-extension",
) -> None:
    """Dump case ledger entries from each actor container to JSONL files.

    Thin scenario-specific wrapper over
    :func:`~vultron.demo.helpers.ledger_dump.dump_case_ledgers`, which owns the
    per-actor export, the 404 handling, and the dump manifest. This function
    only names RVCV-extension's participants and where each ledger lives.
    """
    # Route keys come from each client's own actor id, not its display
    # name: the key selects the store (ADR-0073), so a literal is right
    # only while the scenario seeds deterministic named ids.
    targets = [
        LedgerDumpTarget(
            "reporter",
            reporter_client,
            replica_route_key(reporter_client),
        ),
        LedgerDumpTarget(
            "vendor", vendor_client, replica_route_key(vendor_client)
        ),
        LedgerDumpTarget(
            "coordinator",
            coordinator_client,
            replica_route_key(coordinator_client),
        ),
        LedgerDumpTarget(
            "vendor2",
            vendor2_client,
            replica_route_key(vendor2_client),
        ),
        # The canonical ledger, from the dedicated case-actor container.
        case_actor_dump_target(case_actor_client),
    ]

    dump_case_ledgers(demo_name=demo_name, case=case, targets=targets)


def run_rvcv_extension_demo(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    reporter_id: str | None = None,
    vendor_id: str | None = None,
    coordinator_id: str | None = None,
    vendor2_id: str | None = None,
) -> None:
    """Orchestrate the RVCV-extension CVD workflow."""
    logger.info("=" * 80)
    logger.info(
        "RVCV-EXTENSION DEMO: Reporter + Vendor1(CASE_OWNER) + Coordinator + Vendor2"
    )
    logger.info("=" * 80)
    logger.info("Reporter container:      %s", reporter_client.base_url)
    logger.info("Vendor1 container:     %s", vendor_client.base_url)
    logger.info("Coordinator container: %s", coordinator_client.base_url)
    logger.info("Vendor2 container:     %s", vendor2_client.base_url)
    logger.info("CaseActor container:   %s", case_actor_client.base_url)

    with scenario_harness("rvcv-extension") as harness:
        (
            reporter,
            vendor,
            vendor_in_vendor,
            coordinator,
            coordinator_in_coordinator,
            vendor2,
            report,
            offer,
            case,
            reply_note,
        ) = _phase_report_submission(
            reporter_client,
            vendor_client,
            coordinator_client,
            vendor2_client,
            case_actor_client,
            reporter_id,
            vendor_id,
            coordinator_id,
            vendor2_id,
        )

        # Register the dump as soon as there is a case to dump, so every phase
        # below can fail without costing us the ledgers (ISSUE-2239,
        # DEMOMA-23-003). This must stay above the get_actor_by_id() lookup
        # below: that is a network call, and if it fails the case already exists
        # with ledgers worth keeping.
        harness.dump_with(
            lambda: _phase_dump_case_ledgers(
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                coordinator_client=coordinator_client,
                vendor2_client=vendor2_client,
                reporter=reporter,
                vendor=vendor,
                coordinator=coordinator,
                vendor2=vendor2,
                case=case,
                case_actor_client=case_actor_client,
                demo_name=harness.demo_name,
            )
        )

        vendor2_in_vendor2 = get_actor_by_id(vendor2_client, vendor2.id_)

        # Vendor1, the case owner, decides before the Coordinator's suggestion
        # it then accepts (another role's step between decision and trigger).
        harness.reach_step("owner-keep-case", "keep", by=vendor.id_)
        _phase_coordinator_suggests_vendor2(
            reporter_client=reporter_client,
            vendor_client=vendor_client,
            coordinator_client=coordinator_client,
            vendor2_client=vendor2_client,
            case_actor_client=case_actor_client,
            vendor=vendor,
            vendor_in_vendor=vendor_in_vendor,
            coordinator_in_coordinator=coordinator_in_coordinator,
            vendor2=vendor2,
            vendor2_in_vendor2=vendor2_in_vendor2,
            case=case,
            offer=offer,
            report=report,
            reporter=reporter,
        )

        reporter_in_reporter = get_actor_by_id(reporter_client, reporter.id_)

        _phase_sync_verification(
            reporter_client,
            vendor_client,
            coordinator_client,
            vendor2_client,
            vendor,
            reporter,
            coordinator,
            vendor2,
            case,
        )
        _phase_joiner_notes(
            vendor_client=vendor_client,
            coordinator_client=coordinator_client,
            vendor2_client=vendor2_client,
            coordinator_in_coordinator=coordinator_in_coordinator,
            vendor2_in_vendor2=vendor2_in_vendor2,
            case=case,
            reply_note=reply_note,
        )
        _phase_fix_lifecycle(
            reporter_client,
            vendor_client,
            vendor2_client,
            vendor,
            vendor_in_vendor,
            vendor2,
            vendor2_in_vendor2,
            case,
        )
        _phase_publication(
            reporter_client,
            vendor_client,
            coordinator_client,
            vendor2_client,
            vendor,
            vendor_in_vendor,
            vendor2,
            vendor2_in_vendor2,
            reporter,
            reporter_in_reporter,
            coordinator,
            coordinator_in_coordinator,
            case,
        )
        _phase_case_closure(
            reporter_client,
            vendor_client,
            coordinator_client,
            vendor2_client,
            vendor,
            vendor_in_vendor,
            vendor2,
            vendor2_in_vendor2,
            reporter,
            reporter_in_reporter,
            coordinator,
            coordinator_in_coordinator,
            case,
            case_actor_client,
        )

    logger.info("=" * 80)
    logger.info("RVCV-EXTENSION DEMO COMPLETE ✓  (VFDPxa full lifecycle)")
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@scenario(
    name="rvcv-extension",
    label="RVCV-extension",
    participants="Reporter + Vendor1 + Coordinator + Vendor2",
    feature="Coordinator-suggested second vendor",
    in_pr_set=False,
    path=(
        ("reporter-whom-to-tell", "vendor"),
        ("vendor-after-answer", "invite-coordinator"),
        ("owner-keep-case", "keep"),
    ),
)
def main(
    skip_health_check: bool = False,
    reporter_url: str | None = None,
    vendor_url: str | None = None,
    coordinator_url: str | None = None,
    vendor2_url: str | None = None,
    case_actor_url: str | None = None,
    reporter_id: str | None = None,
    vendor_id: str | None = None,
    coordinator_id: str | None = None,
    vendor2_id: str | None = None,
) -> None:
    """Entry point for the RVCV-extension CVD workflow demo.

    Args:
        skip_health_check: Skip the server availability check.
        reporter_url: Override base URL for the Reporter container.
        vendor_url: Override base URL for the Vendor1 container.
        coordinator_url: Override base URL for the Coordinator container.
        vendor2_url: Override base URL for the Vendor2 container.
        case_actor_url: Override base URL for the dedicated CaseActor
            container.
        reporter_id: Optional deterministic URI for the Reporter actor.
        vendor_id: Optional deterministic URI for the Vendor1 actor.
        coordinator_id: Optional deterministic URI for the Coordinator actor.
        vendor2_id: Optional deterministic URI for the Vendor2 actor.
    """
    f_url = reporter_url or REPORTER_BASE_URL
    v_url = vendor_url or VENDOR_BASE_URL
    c_url = coordinator_url or COORDINATOR_BASE_URL
    v2_url = vendor2_url or VENDOR2_BASE_URL
    ca_url = case_actor_url or CASE_ACTOR_BASE_URL

    reporter_client = DataLayerClient(base_url=f_url)
    vendor_client = DataLayerClient(base_url=v_url)
    coordinator_client = DataLayerClient(base_url=c_url)
    vendor2_client = DataLayerClient(base_url=v2_url)
    # Bound to the CaseActor: a /datalayer/ read names whose store it is about
    # (ADR-0073).
    case_actor_client = bound_case_actor_client(ca_url)

    if not skip_health_check:
        targets: list[tuple[str, DataLayerClient]] = [
            ("Reporter", reporter_client),
            ("Vendor1", vendor_client),
            ("Coordinator", coordinator_client),
            ("Vendor2", vendor2_client),
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

    # scenario_harness() inside run_rvcv_extension_demo() owns the failure
    # accumulator: it resets it, always dumps the case ledgers, and asserts
    # success — so a failure here never costs us the artifacts (ISSUE-2239).
    run_rvcv_extension_demo(
        reporter_client=reporter_client,
        vendor_client=vendor_client,
        coordinator_client=coordinator_client,
        vendor2_client=vendor2_client,
        case_actor_client=case_actor_client,
        **resolved_actor_ids(
            _ROLES,
            reporter=(reporter_client, reporter_id),
            vendor=(vendor_client, vendor_id),
            coordinator=(coordinator_client, coordinator_id),
            vendor2=(vendor2_client, vendor2_id),
        ),
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
