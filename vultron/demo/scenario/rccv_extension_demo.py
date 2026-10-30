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

"""Reporter → C1 (CASE_OWNER, Coordinator) + C2 (Coordinator) + Vendor (RCCV-extension) demo.

Orchestrates the full CVD lifecycle across four actor containers plus a
dedicated CaseActor:
  - Reporter: the report submitter
  - C1 (cast slot 2, the first Coordinator): CASE_OWNER throughout; receives
    the report and retains ownership
  - C2 (cast slot 3, a character actor): participant with CVDRole.COORDINATOR
    from the Invite that seats it; NOT CASE_MANAGER; C2 suggests Vendor via
    the ADR-0026 suggest-actor flow
  - Vendor (cast slot 1, the first Vendor): joins via C1 approval; holds the
    VFD fix path
  - CaseActor (case-actor container): manages the canonical case ledger

Cast (DEMOCI-11-020): every scenario runs the same containers, so a role's
address and actor id are the same here as in its siblings.  ``ROLES`` below
seats each actor; the cast table is ``vultron/demo/helpers/cast.py``.

Spec: DEMOMA-13 (GitHub issue #1620).
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
    verify_publicly_disclosed,
)
from vultron.demo.helpers.notes import (
    WORKAROUND_ANSWER,
    WORKAROUND_QUESTION,
    NotePost,
    add_note_thread,
)
from vultron.demo.helpers.polling import (
    PARTICIPANT_JOIN_TIMEOUT,
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
    seed_containers_rccv,
)
from vultron.demo.helpers.sync import (
    run_sync_verification_phase,
    wait_for_replica_ledger_coverage,
)
from vultron.demo.helpers.verification import _check_participant_vf_state_in
from vultron.demo.helpers.workflow import (
    reporter_submits_report,
    run_direct_path_rm_triage,
    run_invite_path_rm_triage,
)
from vultron.demo.scenario.registry import scenario
from vultron.demo.utils import (  # noqa: F401 — re-exported for test monkeypatching
    DataLayerClient,
    assert_demo_success,
    bound_case_actor_client,
    check_server_availability,
    demo_check,
    demo_gate,
    demo_step,
    post_to_inbox_and_wait,
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

# AC-6 audit (#2203): wait_for_case_on_container calls in this module poll for
# VulnerabilityCase object delivery (ADR-0041 seeding path). ADR-0037/ADR-0059
# buffer Announce(CaseLedgerEntry) entries, not VulnerabilityCase objects, so
# all wait_for_case_on_container calls here remain necessary.

# The scenario's actors in main() parameter order, each seated in a container of
# the fixed cast (DEMOCI-11-020).  The demo CLI derives this scenario's
# sub-command options from this list (DEMOCI-11-011).
ROLES: list[ActorRole] = [
    ActorRole("reporter", REPORTER_SLOT, "Reporter", has_id=True),
    ActorRole("c1", COORDINATOR_SLOT, "C1 (Coordinator1)", has_id=True),
    ActorRole("c2", CAST[3], "C2 (Coordinator2)", has_id=True),
    ActorRole("vendor", VENDOR_SLOT, "Vendor", has_id=True),
    case_actor_role(),
]
_ROLES = role_map(ROLES)

REPORTER_BASE_URL = _ROLES["reporter"].url
C1_BASE_URL = _ROLES["c1"].url
C2_BASE_URL = _ROLES["c2"].url
VENDOR_BASE_URL = _ROLES["vendor"].url
CASE_ACTOR_BASE_URL = _ROLES["case-actor"].url

#: ``vultron-demo rccv-extension --help`` text. Lives here rather than in
#: ``cli.py`` because the sub-command is generated from the registry and the
#: scenario module is the only place that knows what its own workflow does.
CLI_HELP = """Run the RCCV-extension (Reporter + C1/CASE_OWNER + C2/Coordinator + Vendor) demo.

C1 (Coordinator1) retains CASE_OWNER throughout.  C2 (Coordinator2) joins
as a participant with CVDRole.COORDINATOR (not CASE_MANAGER), then suggests
Vendor via the ADR-0026 CaseActor-routed suggest-actor flow.  C1 approves;
CaseActor invites Vendor.  Only Vendor advances through the fix and
publication lifecycle.

\b
Workflow:
  1. Seed all four containers (actor records + peer registration).
  2. Reporter submits a vulnerability report to C1's inbox.
  3. C1 validates and engages the case; invites C2 with CVDRole.COORDINATOR.
  4. C2 accepts; C2 suggests Vendor (ADR-0026 suggest-actor flow).
  5. C1 approves the actor recommendation.
  6. CaseActor invites Vendor; Vendor accepts.
  7. Verify LedgerFanout replication on all replicas.
  8. Vendor advances through fix-ready → fix-deployed.
  9. C1 (CASE_OWNER) triggers publication; embargo terminates.
 10. All participants report publication; all participants close the case.
"""

# The cast's parts in RCCV-extension (see ROLES above):
#   cast slot 2 (first Coordinator) → C1 (Coordinator1, CASE_OWNER)
#   cast slot 3 (character actor)   → C2 (Coordinator2, participant)
#   cast slot 1 (first Vendor)      → Vendor


def reset_containers(
    reporter_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient,
) -> None:
    """Reset the four RCCV-extension containers and the case-actor container.

    The CaseActor identity is re-seeded after the reset, since C1 proposes
    the case to it (DEMOMA-06-004).
    """
    targets: list[tuple[str, DataLayerClient]] = [
        ("Reporter", reporter_client),
        ("C1", c1_client),
        ("C2", c2_client),
        ("Vendor", vendor_client),
    ]
    _reset_containers(
        targets,
        reset_fn=reset_datalayer,
        case_actor_client=case_actor_client,
    )


# ---------------------------------------------------------------------------
# Polling helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Phase helpers
# ---------------------------------------------------------------------------


def _phase_report_submission(
    reporter_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    reporter_id: str | None,
    c1_id: str | None,
    c2_id: str | None,
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
    """Reset, seed, submit report, validate, engage, invite C2, M1 check."""
    logger.info("─" * 80)
    logger.info("Phase 1: Report submission and case activation")
    logger.info("─" * 80)

    reset_containers(
        reporter_client=reporter_client,
        c1_client=c1_client,
        c2_client=c2_client,
        vendor_client=vendor_client,
        case_actor_client=case_actor_client,
    )

    reporter = c1 = c2 = vendor = None
    with demo_step("Seeding all four containers with actor records"):
        reporter, c1, c2, vendor = seed_containers_rccv(
            reporter_client=reporter_client,
            c1_client=c1_client,
            c2_client=c2_client,
            vendor_client=vendor_client,
            reporter_actor_id=reporter_id,
            c1_actor_id=c1_id,
            c2_actor_id=c2_id,
            vendor_actor_id=vendor_id,
            case_actor_client=case_actor_client,
        )

    c1_in_c1 = get_actor_by_id(c1_client, c1.id_)
    c2_in_c2 = get_actor_by_id(c2_client, c2.id_)

    # The Reporter's decision; its role comes from submitting the report.
    reach_step("reporter-whom-to-tell", "coordinator", by=reporter.id_)
    report, offer = reporter_submits_report(
        receiver_client=c1_client,
        reporter=reporter,
        receiver=c1_in_c1,
        reporter_client=reporter_client,
    )
    case = run_direct_path_rm_triage(
        receiver_client=c1_client,
        receiver=c1_in_c1,
        offer=offer,
        timeout_seconds=60.0,
    )

    # Causal precondition: the initial case (Reporter + C1 present on C1's
    # replica) must exist before C2 is invited.  A demo_gate — not demo_check —
    # so a timeout skips the doomed invite/admit steps rather than cascading
    # (DEMOCI-01-011, vultron/demo/AGENTS.md § "Never Wrap a Causal Wait in
    # demo_check").
    with demo_gate("C1 case has Reporter + C1 before inviting C2"):
        wait_for_case_participants(
            vendor_client=c1_client,
            case_id=case.id_,
            expected_actor_ids={reporter.id_, c1.id_},
        )

        follow_ledger(case_actor_client, case.id_)
        reach_step("coordinator-invite-whom", "coordinator", by=c1.id_)

        # C1 invites C2 with CVDRole.COORDINATOR (not CASE_MANAGER).  The chain
        # nests the delivery gate, the accept and the replica wait inside the
        # invite step, so a failed trigger or lookup skips its dependents
        # (ADR-0058 nested-block model, EDF-06-005, #3038).
        def _check_c2_joined() -> None:
            # 4 participants: Reporter + C1 + C2 + CaseActor
            with demo_check(
                "C1 case reflects Reporter + C1 + C2 participants"
            ):
                wait_for_case_participants(
                    vendor_client=c1_client,
                    case_id=case.id_,
                    expected_actor_ids={reporter.id_, c1.id_, c2.id_},
                )

        run_case_invite_chain(
            case=case,
            case_manager_client=case_actor_client,
            invitee_name="C2",
            invitee_client=c2_client,
            invitee=c2,
            invitee_in_own_container=c2_in_c2,
            inviter=CaseInviter(
                name="C1",
                client=c1_client,
                actor=c1_in_c1,
                role=CVDRole.COORDINATOR,
            ),
            then=_check_c2_joined,
        )

    with demo_check(
        "M1: required participants (≥4), EM.ACTIVE, reporter + c2 have replicas"
    ):
        verify_case_active(
            receiver_client=c1_client,
            reporter_client=reporter_client,
            case_id=case.id_,
            receiver_actor_id=c1.id_,
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
        auth_client=c1_client,
        replicas=[
            (reporter_client, "Reporter"),
            (c2_client, "C2"),
        ],
        case_id=case.id_,
        phase_label="Phase 1 drain before Phase 2",
    )

    case = as_VulnerabilityCase.model_validate(
        c1_client.get(c1_client.dl_path(case.id_))
    )
    return (
        reporter,
        c1,
        c1_in_c1,
        c2_in_c2,
        vendor,
        report,
        offer,
        case,
    )


def _phase_c2_suggests_vendor(
    reporter_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    c1_in_c1: as_Actor,
    c2_in_c2: as_Actor,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    case: as_VulnerabilityCase,
    offer: as_Offer,
    report: as_VulnerabilityReport,
    reporter: as_Actor,
) -> None:
    """C2 suggests Vendor via ADR-0026; C1 approves; Vendor joins."""
    logger.info("─" * 80)
    logger.info("Phase 2: C2 suggests Vendor → C1 approves → Vendor joins")
    logger.info("─" * 80)

    # Step M3: C2 sends suggest-actor-to-case (Offer(Actor, Case) → CaseActor).
    with demo_step("C2 suggests Vendor to CaseActor"):
        ActorSession(client=c2_client, actor=c2_in_c2).with_case(
            case
        ).quiet().suggest_actor_to_case(
            suggested_actor_id=vendor.id_,
            roles=[CVDRole.VENDOR],
        )
    logger.info("C2 sent suggest-actor-to-case for Vendor (%s)", vendor.id_)

    # CaseActor processes Offer(Actor, Case) and forwards Offer(CaseParticipant)
    # to C1 (CASE_OWNER).  Poll C1's DataLayer for the offer.
    # All dependent steps (case_actor lookup and approve) are nested inside
    # demo_gate so they are skipped if the offer never arrives (ADR-0058).
    with demo_gate(
        "Offer(CaseParticipant) for Vendor arrived in C1's DataLayer"
    ):
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

        # Step M4 (ADR-0026 CM-16-006): C1 approves the recommendation.
        with demo_step(
            "C1 approves actor recommendation (accept-actor-recommendation)"
        ):
            ActorSession(
                client=c1_client, actor=c1_in_c1
            ).quiet().accept_actor_recommendation(
                cp_offer_id=cp_offer_id,
                case_actor_id=case_actor_id,
            )
    logger.info("C1 sent Accept(Offer(CaseParticipant)) to CaseActor")

    # CaseActor receives Accept → emits Invite(Actor, CaseStub) to Vendor; the
    # chain polls Vendor's DataLayer for it and puppeteers Vendor's accept
    # (ADR-0026).  Everything after the invite nests inside its gate
    # (EDF-06-005, #3038).
    run_case_invite_chain(
        case=case,
        invitee_name="Vendor",
        invitee_client=vendor_client,
        invitee=vendor,
        invitee_in_own_container=vendor_in_vendor,
        invite_timeout=20.0,
        replica_timeout=20.0,
        ledger_client=case_actor_client,
        reply_timeout=20.0,
    )

    # All 5 participants (Reporter + C1 + C2 + Vendor + CaseActor) present is the
    # causal precondition for Vendor's RM triage below: a demo_gate — not
    # demo_check — so a timeout skips the doomed triage rather than cascading
    # (DEMOCI-01-011, vultron/demo/AGENTS.md § "Never Wrap a Causal Wait in
    # demo_check").
    with demo_gate("C1 case has all 5 participants before Vendor RM triage"):
        wait_for_case_participants(
            vendor_client=c1_client,
            case_id=case.id_,
            expected_actor_ids={
                reporter.id_,
                c1_in_c1.id_,
                c2_in_c2.id_,
                vendor.id_,
            },
            timeout_seconds=PARTICIPANT_JOIN_TIMEOUT,
        )
        logger.info("✓ M3: Vendor joined case (%d participants)", 5)

        # CLP-08-005: ensure Reporter's genesis hash is seeded before
        # Announce(CaseLedgerEntry) is broadcast by the triage cycle below.
        with demo_check(
            "Reporter's DataLayer received case replica before Vendor RM triage"
        ):
            wait_for_case_on_container(
                client=reporter_client,
                case_id=case.id_,
                timeout_seconds=20.0,
            )

        run_invite_path_rm_triage(
            invited_client=vendor_client,
            invited_actor=vendor_in_vendor,
            offer=offer,
            report=report,
            reporter=reporter,
            auth_client=case_actor_client,
            case=case,
            invited_obj=vendor,
            timeout_seconds=20.0,
        )


def _phase_sync_verification(
    reporter_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    vendor_client: DataLayerClient,
    c1: as_Actor,
    reporter: as_Actor,
    case: as_VulnerabilityCase,
    c2_in_c2: as_Actor,
    vendor: as_Actor,
) -> None:
    """Verify LedgerFanout replication for Reporter, C2, and Vendor replicas."""
    logger.info("─" * 80)
    logger.info("Phase 3: Replica synchronization verification")
    logger.info("─" * 80)

    run_sync_verification_phase(
        auth_client=c1_client,
        auth_label="C1",
        auth_actor_id=c1.id_,
        reporter_client=reporter_client,
        reporter_actor_id=reporter.id_,
        replicas=[
            (reporter_client, "Reporter"),
            (c2_client, "C2"),
            (vendor_client, "Vendor"),
        ],
        case_id=case.id_,
        expected_participant_ids={
            reporter.id_,
            c1.id_,
            c2_in_c2.id_,
            vendor.id_,
        },
        # Vendor joins by invitation after the early replicas exist (#2202).
        late_joiners=(vendor_client,),
        state_checks=[
            (reporter_client, "Reporter"),
            (vendor_client, "Vendor"),
        ],
    )

    logger.info("✓ M4: All replicas synchronized (LedgerFanout verified)")


def _phase_notes_exchange(
    reporter_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    vendor_client: DataLayerClient,
    reporter_in_reporter: as_Actor,
    c1_in_c1: as_Actor,
    c2_in_c2: as_Actor,
    vendor_in_vendor: as_Actor,
    case: as_VulnerabilityCase,
) -> as_Note | None:
    """Run a four-way note exchange among all participants.

    Returns:
        The Vendor's note, or ``None`` when it failed.
    """
    logger.info("─" * 80)
    logger.info("Phase 4: Notes exchange")
    logger.info("─" * 80)

    vendor_note = add_note_thread(
        c1_client,
        case,
        [
            NotePost(
                ActorSession(
                    client=reporter_client, actor=reporter_in_reporter
                ),
                "Question from Reporter",
                WORKAROUND_QUESTION,
            ),
            NotePost(
                ActorSession(client=c1_client, actor=c1_in_c1),
                "C1 Response",
                WORKAROUND_ANSWER,
            ),
            NotePost(
                ActorSession(client=c2_client, actor=c2_in_c2),
                "C2 Update",
                "We have confirmed that C2 and Vendor are engaged. "
                "Target disclosure in 30 days.",
            ),
            NotePost(
                ActorSession(client=vendor_client, actor=vendor_in_vendor),
                "Vendor Status Update",
                "Vendor can confirm the issue affects our component. "
                "We will align our fix timeline with the 30-day target.",
            ),
        ],
    )

    logger.info(
        "✓ Notes exchange complete (four notes committed to case ledger)"
    )
    return vendor_note


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

        with demo_check("Vendor participant vf_state transitions to VF"):
            wait_for_participant_vf_state(
                client=vendor_client,
                case_id=case.id_,
                actor_id=vendor.id_,
                expected_states={CS_vf.VF},
            )

        with demo_check(
            "M5: C1 replica shows Vendor CS includes F (fix ready)"
        ):
            wait_for_participant_vf_state(
                client=c1_client,
                case_id=case.id_,
                actor_id=vendor.id_,
                expected_states={CS_vf.VF},
            )
            _check_participant_vf_state_in(
                c1_client,
                case.id_,
                vendor.id_,
                {CS_vf.VF},
                "M5: C1 replica fix ready",
            )
            _check_participant_vf_state_in(
                vendor_client,
                case.id_,
                vendor.id_,
                {CS_vf.VF},
                "M5: Vendor replica fix ready",
            )

        with demo_check(
            "M6: C1 replica shows Vendor CS includes F (fix ready) — vendor stops at VFd"
        ):
            wait_for_participant_vf_state(
                client=c1_client,
                case_id=case.id_,
                actor_id=vendor.id_,
                expected_states={CS_vf.VF},
            )
            _check_participant_vf_state_in(
                c1_client,
                case.id_,
                vendor.id_,
                {CS_vf.VF},
                "M6: C1 replica fix ready",
            )
            _check_participant_vf_state_in(
                vendor_client,
                case.id_,
                vendor.id_,
                {CS_vf.VF},
                "M6: Vendor replica fix ready",
            )


def _phase_publication(
    reporter_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    vendor_client: DataLayerClient,
    c1: as_Actor,
    c1_in_c1: as_Actor,
    c2_in_c2: as_Actor,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    reporter_in_reporter: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Run publication notifications and verify public disclosure state."""
    logger.info("─" * 80)
    logger.info(
        "Phase 6: Publication — CS.VFDPxa + embargo teardown (EM.EXITED)"
    )
    logger.info("─" * 80)

    # C1 (CASE_OWNER) triggers CS.P per DEMOMA-13-006 / DEMOMA-07-003(4).
    with demo_step(
        f"Actor {ref_id(c1_in_c1)} reports vulnerability publicly disclosed"
    ):
        ActorSession(client=c1_client, actor=c1_in_c1).with_case(
            case
        ).quiet().notify_published()

    with demo_check(
        "Embargo terminated (EM.EXITED) after C1 reports published"
    ):
        wait_for_case_em_terminated(
            client=c1_client,
            case_id=case.id_,
        )

    with demo_step(
        f"Actor {ref_id(vendor_in_vendor)} reports vulnerability publicly disclosed"
    ):
        ActorSession(client=vendor_client, actor=vendor_in_vendor).with_case(
            case
        ).quiet().notify_published()
    with demo_step(
        f"Actor {ref_id(c2_in_c2)} reports vulnerability publicly disclosed"
    ):
        ActorSession(client=c2_client, actor=c2_in_c2).with_case(
            case
        ).quiet().notify_published()

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
            client=c1_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vf.VF},
        )
        verify_publicly_disclosed(
            receiver_client=c1_client,
            reporter_client=reporter_client,
            case_id=case.id_,
            receiver_actor_id=c1.id_,
        )


def _phase_case_closure(
    reporter_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    vendor_client: DataLayerClient,
    c1_in_c1: as_Actor,
    c2_in_c2: as_Actor,
    vendor_in_vendor: as_Actor,
    reporter_in_reporter: as_Actor,
    case: as_VulnerabilityCase,
    case_actor_client: DataLayerClient,
) -> None:
    """Close the case from all four participants and verify terminal state.

    The Vendor, C2 and the Reporter leave first; C1, the Case Owner, leaves
    last, once their departures are recorded (CM-23-015) in the CASE_MANAGER's
    store on the dedicated case-actor container.
    """
    logger.info("─" * 80)
    logger.info("Phase 7: Case closure — all participants RM.CLOSED")
    logger.info("─" * 80)

    close_case_owner_last(
        case=case,
        milestone="M8",
        authority_client=case_actor_client,
        others=[
            CaseLeaver(client=vendor_client, actor=vendor_in_vendor),
            CaseLeaver(client=c2_client, actor=c2_in_c2),
            CaseLeaver(client=reporter_client, actor=reporter_in_reporter),
        ],
        owner=CaseLeaver(client=c1_client, actor=c1_in_c1),
    )


def _phase_dump_case_ledgers(
    reporter_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    case: as_VulnerabilityCase,
    demo_name: str = "rccv-extension",
) -> None:
    """Dump case ledger entries from each actor container to JSONL files.

    Thin scenario-specific wrapper over
    :func:`~vultron.demo.helpers.ledger_dump.dump_case_ledgers`, which owns the
    per-actor export, the 404 handling, and the dump manifest. This function
    only names RCCV-extension's participants and where each ledger lives.
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
        # C1 is the first Coordinator, on cast slot 2.
        LedgerDumpTarget("vendor", c1_client, replica_route_key(c1_client)),
        # C2 is a character actor, on cast slot 3.
        LedgerDumpTarget(
            "coordinator",
            c2_client,
            replica_route_key(c2_client),
        ),
        # Vendor is the first Vendor, on cast slot 1.
        LedgerDumpTarget(
            "vendor2",
            vendor_client,
            replica_route_key(vendor_client),
        ),
        # The canonical ledger lives on the dedicated case-actor container.
        case_actor_dump_target(case_actor_client),
    ]

    dump_case_ledgers(demo_name=demo_name, case=case, targets=targets)


def run_rccv_extension_demo(
    reporter_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    reporter_id: str | None = None,
    c1_id: str | None = None,
    c2_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Orchestrate the RCCV-extension CVD workflow."""
    logger.info("=" * 80)
    logger.info(
        "RCCV-EXTENSION DEMO: Reporter + C1(CASE_OWNER) + C2(COORDINATOR) + Vendor"
    )
    logger.info("=" * 80)
    logger.info("Reporter container: %s", reporter_client.base_url)
    logger.info("C1 container:     %s", c1_client.base_url)
    logger.info("C2 container:     %s", c2_client.base_url)
    logger.info("Vendor container: %s", vendor_client.base_url)
    logger.info("CaseActor container: %s", case_actor_client.base_url)

    with scenario_harness("rccv-extension") as harness:
        (
            reporter,
            c1,
            c1_in_c1,
            c2_in_c2,
            vendor,
            report,
            offer,
            case,
        ) = _phase_report_submission(
            reporter_client,
            c1_client,
            c2_client,
            vendor_client,
            case_actor_client,
            reporter_id,
            c1_id,
            c2_id,
            vendor_id,
        )

        # Register the dump as soon as there is a case to dump, so every phase
        # below can fail without costing us the ledgers (ISSUE-2239).
        harness.dump_with(
            lambda: _phase_dump_case_ledgers(
                reporter_client=reporter_client,
                c1_client=c1_client,
                c2_client=c2_client,
                vendor_client=vendor_client,
                case_actor_client=case_actor_client,
                case=case,
                demo_name=harness.demo_name,
            )
        )

        vendor_in_vendor = get_actor_by_id(vendor_client, vendor.id_)

        # C1, the case owner, decides before C2's suggestion it then accepts
        # (another role's step between decision and trigger).
        harness.reach_step("owner-keep-case", "keep", by=c1.id_)
        _phase_c2_suggests_vendor(
            reporter_client=reporter_client,
            c1_client=c1_client,
            c2_client=c2_client,
            vendor_client=vendor_client,
            case_actor_client=case_actor_client,
            c1_in_c1=c1_in_c1,
            c2_in_c2=c2_in_c2,
            vendor=vendor,
            vendor_in_vendor=vendor_in_vendor,
            case=case,
            offer=offer,
            report=report,
            reporter=reporter,
        )

        reporter_in_reporter = get_actor_by_id(reporter_client, reporter.id_)

        _phase_sync_verification(
            reporter_client,
            c1_client,
            c2_client,
            vendor_client,
            c1,
            reporter,
            case,
            c2_in_c2,
            vendor,
        )
        _phase_notes_exchange(
            reporter_client=reporter_client,
            c1_client=c1_client,
            c2_client=c2_client,
            vendor_client=vendor_client,
            reporter_in_reporter=reporter_in_reporter,
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
            reporter_client,
            c1_client,
            c2_client,
            vendor_client,
            c1,
            c1_in_c1,
            c2_in_c2,
            vendor,
            vendor_in_vendor,
            reporter_in_reporter,
            case,
        )
        _phase_case_closure(
            reporter_client,
            c1_client,
            c2_client,
            vendor_client,
            c1_in_c1,
            c2_in_c2,
            vendor_in_vendor,
            reporter_in_reporter,
            case,
            case_actor_client,
        )

    logger.info("=" * 80)
    logger.info("RCCV-EXTENSION DEMO COMPLETE ✓  (VFDPxa full lifecycle)")
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@scenario(
    name="rccv-extension",
    label="RCCV-extension",
    participants="Reporter + C1 + C2 + Vendor",
    feature="Second coordinator suggests vendor",
    in_pr_set=False,
    path=(
        ("reporter-whom-to-tell", "coordinator"),
        ("coordinator-invite-whom", "coordinator"),
        ("owner-keep-case", "keep"),
    ),
)
def main(
    skip_health_check: bool = False,
    reporter_url: str | None = None,
    c1_url: str | None = None,
    c2_url: str | None = None,
    vendor_url: str | None = None,
    case_actor_url: str | None = None,
    reporter_id: str | None = None,
    c1_id: str | None = None,
    c2_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Entry point for the RCCV-extension CVD workflow demo.

    Args:
        skip_health_check: Skip the server availability check.
        reporter_url: Override base URL for the Reporter container.
        c1_url: Override base URL for the C1 (Coordinator1) container.
        c2_url: Override base URL for the C2 (Coordinator2) container.
        vendor_url: Override base URL for the Vendor container.
        case_actor_url: Override base URL for the dedicated CaseActor
            container.
        reporter_id: Optional deterministic URI for the Reporter actor.
        c1_id: Optional deterministic URI for the C1 actor.
        c2_id: Optional deterministic URI for the C2 actor.
        vendor_id: Optional deterministic URI for the Vendor actor.
    """
    f_url = reporter_url or REPORTER_BASE_URL
    c1_resolved = c1_url or C1_BASE_URL
    c2_resolved = c2_url or C2_BASE_URL
    v_url = vendor_url or VENDOR_BASE_URL
    ca_url = case_actor_url or CASE_ACTOR_BASE_URL

    reporter_client = DataLayerClient(base_url=f_url)
    c1_client = DataLayerClient(base_url=c1_resolved)
    c2_client = DataLayerClient(base_url=c2_resolved)
    vendor_client = DataLayerClient(base_url=v_url)
    # Bound here: a /datalayer/ read names whose store it is about (ADR-0073),
    # and the dedicated container hosts only the CaseActor.
    case_actor_client = bound_case_actor_client(ca_url)

    if not skip_health_check:
        targets: list[tuple[str, DataLayerClient]] = [
            ("Reporter", reporter_client),
            ("C1", c1_client),
            ("C2", c2_client),
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

    # scenario_harness() inside run_rccv_extension_demo() owns the failure
    # accumulator: it resets it, always dumps the case ledgers, and asserts
    # success — so a failure here never costs us the artifacts (ISSUE-2239).
    run_rccv_extension_demo(
        reporter_client=reporter_client,
        c1_client=c1_client,
        c2_client=c2_client,
        vendor_client=vendor_client,
        case_actor_client=case_actor_client,
        **resolved_actor_ids(
            _ROLES,
            reporter=(reporter_client, reporter_id),
            c1=(c1_client, c1_id),
            c2=(c2_client, c2_id),
            vendor=(vendor_client, vendor_id),
        ),
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
