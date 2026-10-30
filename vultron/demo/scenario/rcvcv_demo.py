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

"""Reporter + Coordinator1 + Vendor1 + Coordinator2 + VendorDeployer (RCVCV) demo.

Orchestrates the full CVD lifecycle across five actor containers plus a
dedicated CaseActor:
  - Reporter: the report submitter
  - C1 (cast slot 2, the first Coordinator): CASE_OWNER throughout; receives
    the report
  - V1 (cast slot 1, the first Vendor): CVDRole.VENDOR only; advances to VFd
    (fix-ready, no deploy step)
  - C2 (cast slot 3, a character actor): CVDRole.COORDINATOR participant;
    suggests V2 via the ADR-0026 suggest-actor flow
  - V2 (cast slot 4, a character actor): CVDRole.VENDOR + CVDRole.DEPLOYER;
    advances to VFD (fix-ready then fix-deployed).  Both roles come from the
    Invite that seats it, not from its container (DEMOCI-11-021).

Cast (DEMOCI-11-020): every scenario runs the same containers, so a role's
address and actor id are the same here as in its siblings.  ``ROLES`` below
seats each actor; the cast table is ``vultron/demo/helpers/cast.py``.

Spec: DEMOMA-19 (GitHub issue #1925).
"""

import logging
import sys

from vultron.core.states.cs import CS_d, CS_vf
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
    step_reporter,
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
    verify_fix_deployed,
    verify_fix_ready,
    verify_publicly_disclosed,
)
from vultron.demo.helpers.notes import (
    NotePost,
    add_note_thread,
    gated_note_thread,
    reporter_asks_vendor_timeline,
)
from vultron.demo.helpers.polling import (
    LATE_JOINER_TIMEOUT,
    find_case_actor_participant_id,
    find_cp_offer_for_case,
    wait_for_case_em_terminated,
    wait_for_case_on_container,
    wait_for_case_participants,
    wait_for_participant_d_state,
    wait_for_participant_rm_state,
    wait_for_participant_vf_state,
)
from vultron.demo.helpers.seeding import (
    get_actor_by_id,
    reset_containers as _reset_containers,
    seed_containers_rcvcv,
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
    ActorRole(
        "c1", COORDINATOR_SLOT, "C1 (Coordinator1/CASE_OWNER)", has_id=True
    ),
    ActorRole("v1", VENDOR_SLOT, "V1 (Vendor1)", has_id=True),
    ActorRole("c2", CAST[3], "C2 (Coordinator2)", has_id=True),
    ActorRole("v2", CAST[4], "V2 (VendorDeployer)", has_id=True),
    case_actor_role(),
]
_ROLES = role_map(ROLES)

REPORTER_BASE_URL = _ROLES["reporter"].url
C1_BASE_URL = _ROLES["c1"].url
V1_BASE_URL = _ROLES["v1"].url
C2_BASE_URL = _ROLES["c2"].url
V2_BASE_URL = _ROLES["v2"].url
CASE_ACTOR_BASE_URL = _ROLES["case-actor"].url

#: ``vultron-demo rcvcv --help`` text. Lives here rather than in ``cli.py``
#: because the sub-command is generated from the registry and the scenario
#: module is the only place that knows what its own workflow does.
CLI_HELP = """Run the RCVCV 5-party CVD demo (DEMOMA-19).

Five actors coordinate a full CVD lifecycle:
Reporter + C1 (CASE_OWNER) + V1 (VENDOR) + C2 (COORDINATOR) + V2
(VENDOR+DEPLOYER).

\b
Workflow:
  1. Reset and seed all five containers.
  2. Reporter submits a report to C1; C1 validates and engages.
  3. C1 invites V1 (VENDOR); the Reporter asks, C1 answers and V1 adds
     its status in case notes; then C1 invites C2 (COORDINATOR).
  4. C2 suggests V2 via ADR-0026; C1 approves; V2 joins via CaseActor.
  5. Verify LedgerFanout replication across all six participants.
  6. C2 and V2 add their notes to the thread.
  7. Fix lifecycle: V1 → VFd (no deploy); V2 → VFD (fix-deployed).
  8. Publication: V1 publishes first → embargo terminates; all publish.
  9. All actors close the case.
 10. Export case ledger JSONL for each actor (devlogs).
"""


def reset_containers(
    reporter_client: DataLayerClient,
    c1_client: DataLayerClient,
    v1_client: DataLayerClient,
    c2_client: DataLayerClient,
    v2_client: DataLayerClient,
    case_actor_client: DataLayerClient,
) -> None:
    """Reset the five RCVCV containers and the case-actor container.

    The CaseActor identity is re-seeded after the reset, since C1 proposes
    the case to it (DEMOMA-06-004).
    """
    targets: list[tuple[str, DataLayerClient]] = [
        ("Reporter", reporter_client),
        ("C1", c1_client),
        ("V1", v1_client),
        ("C2", c2_client),
        ("V2", v2_client),
    ]
    _reset_containers(
        targets,
        reset_fn=reset_datalayer,
        case_actor_client=case_actor_client,
    )


# ---------------------------------------------------------------------------
# Phase helpers
# ---------------------------------------------------------------------------


def _phase_report_submission(
    reporter_client: DataLayerClient,
    c1_client: DataLayerClient,
    v1_client: DataLayerClient,
    c2_client: DataLayerClient,
    v2_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    reporter_id: str | None,
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
    as_Note | None,
]:
    """Reset, seed, submit, validate, engage, invite V1, exchange notes, invite C2.

    Returns:
        The cast, the report and offer, the refreshed case, and V1's note
        (``None`` when the exchange failed), which C2's note answers later.
    """
    logger.info("─" * 80)
    logger.info("Phase 1: Report submission and case activation")
    logger.info("─" * 80)

    reset_containers(
        reporter_client=reporter_client,
        c1_client=c1_client,
        v1_client=v1_client,
        c2_client=c2_client,
        v2_client=v2_client,
        case_actor_client=case_actor_client,
    )

    reporter = c1 = v1 = c2 = v2 = None
    v1_note: as_Note | None = None
    with demo_step("Seeding all five containers with actor records"):
        reporter, c1, v1, c2, v2 = seed_containers_rcvcv(
            reporter_client=reporter_client,
            c1_client=c1_client,
            v1_client=v1_client,
            c2_client=c2_client,
            v2_client=v2_client,
            reporter_actor_id=reporter_id,
            c1_actor_id=c1_id,
            v1_actor_id=v1_id,
            c2_actor_id=c2_id,
            v2_actor_id=v2_id,
            case_actor_client=case_actor_client,
        )

    c1_in_c1 = get_actor_by_id(c1_client, c1.id_)
    v1_in_v1 = get_actor_by_id(v1_client, v1.id_)
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
    # replica) must exist before V1 and C2 are invited.  A demo_gate — not
    # demo_check — so a timeout skips the doomed invite/admit chain rather than
    # cascading (DEMOCI-01-011, vultron/demo/AGENTS.md § "Never Wrap a Causal
    # Wait in demo_check").
    with demo_gate("C1 case has Reporter + C1 before inviting V1 and C2"):
        wait_for_case_participants(
            vendor_client=c1_client,
            case_id=case.id_,
            expected_actor_ids={reporter.id_, c1.id_},
        )

        with demo_check(
            "Reporter's DataLayer received case replica (genesis hash available)"
        ):
            wait_for_case_on_container(
                client=reporter_client,
                case_id=case.id_,
            )

        follow_ledger(case_actor_client, case.id_)
        reach_step("coordinator-invite-whom", "vendor", by=c1.id_)

        # C1 invites V1 with CVDRole.VENDOR.  Everything that depends on the
        # invite — the delivery gate, V1's accept, the replica waits and V1's
        # RM triage — is nested inside the block that produces what it needs,
        # so a failed trigger or lookup skips its dependents instead of
        # handing them ``None`` (ADR-0058 nested-block model, EDF-06-005,
        # #3038).
        def _v1_rm_triage() -> None:
            with demo_check(
                "Reporter's DataLayer received case replica before V1 RM triage"
            ):
                wait_for_case_on_container(
                    client=reporter_client,
                    case_id=case.id_,
                )

            run_invite_path_rm_triage(
                invited_client=v1_client,
                invited_actor=v1_in_v1,
                offer=offer,
                report=report,
                reporter=reporter,
                auth_client=case_actor_client,
                case=case,
                invited_obj=v1,
            )

        run_case_invite_chain(
            case=case,
            case_manager_client=case_actor_client,
            invitee_name="V1",
            invitee_client=v1_client,
            invitee=v1,
            invitee_in_own_container=v1_in_v1,
            inviter=CaseInviter(
                name="C1",
                client=c1_client,
                actor=c1_in_c1,
                role=CVDRole.VENDOR,
            ),
            then=_v1_rm_triage,
            before_answer=step_reporter("vendor-join", "accept", by=v1.id_),
        )

        # The Reporter asks and V1 answers before C1 decides to invite a
        # second Coordinator: on the scenario tree that invite is C1's choice
        # after V1's answer.
        reach_step("reporter-after-join", "ask-vendor", by=reporter.id_)
        v1_note = _phase_notes_exchange(
            reporter_client=reporter_client,
            c1_client=c1_client,
            v1_client=v1_client,
            reporter=reporter,
            c1_in_c1=c1_in_c1,
            v1_in_v1=v1_in_v1,
            case=case,
        )

        # C1 invites C2 with CVDRole.COORDINATOR.  Same nesting as V1 above.
        def _check_c2_joined() -> None:
            # 5 participants: Reporter + C1 + V1 + C2 + CaseActor
            with demo_check(
                "C1 case reflects Reporter + C1 + V1 + C2 participants"
            ):
                wait_for_case_participants(
                    vendor_client=c1_client,
                    case_id=case.id_,
                    expected_actor_ids={
                        reporter.id_,
                        c1_in_c1.id_,
                        v1.id_,
                        c2_in_c2.id_,
                    },
                )

        run_case_invite_chain(
            case=case,
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
        "M1: required participants (≥5), EM.ACTIVE, Reporter + V1 + C2 have replicas"
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
            (v1_client, "V1"),
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
        v1,
        v1_in_v1,
        c2_in_c2,
        v2,
        report,
        offer,
        case,
        v1_note,
    )


def _phase_c2_suggests_v2(
    reporter_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    v2_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    c1_in_c1: as_Actor,
    c2_in_c2: as_Actor,
    v2: as_Actor,
    case: as_VulnerabilityCase,
    offer: as_Offer,
    report: as_VulnerabilityReport,
    reporter: as_Actor,
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
        ActorSession(client=c2_client, actor=c2_in_c2).with_case(
            case
        ).quiet().suggest_actor_to_case(
            suggested_actor_id=v2.id_,
            roles=[CVDRole.VENDOR, CVDRole.DEPLOYER],
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
            ActorSession(
                client=c1_client, actor=c1_in_c1
            ).quiet().accept_actor_recommendation(
                cp_offer_id=cp_offer_id,
                case_actor_id=case_actor_id,
            )
    logger.info("C1 sent Accept(Offer(CaseParticipant)) to CaseActor")

    v2_in_v2 = get_actor_by_id(v2_client, v2.id_)

    # CaseActor sends Invite to V2.  The chain polls V2's DataLayer for it and
    # puppeteers V2's accept (DEMOMA-19-009: polling only), nesting the accept
    # and the replica wait inside the invite's gate (EDF-06-005, #3038).
    run_case_invite_chain(
        case=case,
        invitee_name="V2",
        invitee_client=v2_client,
        invitee=v2,
        invitee_in_own_container=v2_in_v2,
        invite_timeout=40.0,
        replica_timeout=40.0,
        ledger_client=case_actor_client,
        reply_timeout=40.0,
    )

    # All 6 participants (Reporter + C1 + V1 + C2 + V2 + CaseActor) present is the
    # causal precondition for V2's RM triage below: a demo_gate — not
    # demo_check — so a timeout skips the doomed triage rather than cascading
    # (DEMOCI-01-011, vultron/demo/AGENTS.md § "Never Wrap a Causal Wait in
    # demo_check").
    with demo_gate("C1 case has all 6 participants before V2 RM triage"):
        wait_for_case_participants(
            vendor_client=c1_client,
            case_id=case.id_,
            expected_actor_ids={
                reporter.id_,
                c1_in_c1.id_,
                v1.id_,
                c2_in_c2.id_,
                v2.id_,
            },
            timeout_seconds=LATE_JOINER_TIMEOUT,
        )
        logger.info("✓ V2 joined case (6 participants)")

        with demo_check(
            "Reporter's DataLayer received case replica before V2 RM triage"
        ):
            wait_for_case_on_container(
                client=reporter_client,
                case_id=case.id_,
                timeout_seconds=40.0,
            )

        run_invite_path_rm_triage(
            invited_client=v2_client,
            invited_actor=v2_in_v2,
            offer=offer,
            report=report,
            reporter=reporter,
            auth_client=case_actor_client,
            case=case,
            invited_obj=v2,
            timeout_seconds=40.0,
        )


def _phase_sync_verification(
    reporter_client: DataLayerClient,
    c1_client: DataLayerClient,
    v1_client: DataLayerClient,
    c2_client: DataLayerClient,
    v2_client: DataLayerClient,
    c1: as_Actor,
    reporter: as_Actor,
    case: as_VulnerabilityCase,
    v1: as_Actor,
    c2_in_c2: as_Actor,
    v2: as_Actor,
) -> None:
    """Verify LedgerFanout replication for all participant replicas."""
    logger.info("─" * 80)
    logger.info("Phase 3: Replica synchronization verification (M1)")
    logger.info("─" * 80)

    run_sync_verification_phase(
        auth_client=c1_client,
        auth_label="C1",
        auth_actor_id=c1.id_,
        reporter_client=reporter_client,
        reporter_actor_id=reporter.id_,
        replicas=[
            (reporter_client, "Reporter"),
            (v1_client, "V1"),
            (c2_client, "C2"),
            (v2_client, "V2"),
        ],
        case_id=case.id_,
        expected_participant_ids={
            reporter.id_,
            c1.id_,
            v1.id_,
            c2_in_c2.id_,
            v2.id_,
        },
        # V2 joins after Phase 1 completes and catches up from genesis.
        late_joiners=(v2_client,),
        state_checks=[(reporter_client, "Reporter"), (v2_client, "V2")],
    )

    logger.info("✓ M1: All five replicas synchronized (LedgerFanout verified)")


def _phase_notes_exchange(
    reporter_client: DataLayerClient,
    c1_client: DataLayerClient,
    v1_client: DataLayerClient,
    reporter: as_Actor,
    c1_in_c1: as_Actor,
    v1_in_v1: as_Actor,
    case: as_VulnerabilityCase,
) -> as_Note | None:
    """The Reporter asks V1 for its timeline; V1 and C1 answer.

    The thread every scenario taking ``reporter-after-join:ask-vendor`` posts
    (``rcv`` too), so the two share their ledger up to C1's decision, which
    follows C1's own note: invite a second Coordinator (DEMOCI-11-017).  Each
    poster acts from its own replica, and V1's holds the case only once V1
    has joined, so the thread waits on it; the Reporter's replica holds the
    case before V1 triages (DEMOMA-22-001).

    Returns:
        C1's note, or ``None`` when it or the gate failed (the failure is
        recorded); the joiners' notes answer it.
    """
    logger.info("─" * 80)
    logger.info("Notes exchange: Reporter asks, V1 and C1 answer")
    logger.info("─" * 80)

    reporter_in_reporter = get_actor_by_id(reporter_client, reporter.id_)
    c1_note = gated_note_thread(
        gate="V1's replica holds the case before the Reporter asks it",
        replica_client=v1_client,
        watching_client=c1_client,
        case=case,
        posts=reporter_asks_vendor_timeline(
            ActorSession(client=reporter_client, actor=reporter_in_reporter),
            ActorSession(client=v1_client, actor=v1_in_v1),
            ActorSession(client=c1_client, actor=c1_in_c1),
        ),
    )
    # C1 decides once the thread is answered.
    reach_step(
        "coordinator-after-answer", "invite-coordinator", by=c1_in_c1.id_
    )
    return c1_note


def _phase_joiner_notes(
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    v2_client: DataLayerClient,
    c2_in_c2: as_Actor,
    v2_in_v2: as_Actor,
    case: as_VulnerabilityCase,
    v1_note: as_Note | None,
) -> as_Note | None:
    """C2 and V2, once joined, add to the notes thread.

    Returns:
        V2's note, or ``None`` when it failed.
    """
    logger.info("─" * 80)
    logger.info("Phase 4: C2 and V2 notes")
    logger.info("─" * 80)

    v2_note = add_note_thread(
        c1_client,
        case,
        [
            NotePost(
                ActorSession(client=c2_client, actor=c2_in_c2),
                "C2 Update",
                "C2 confirms V2 is engaged. Target disclosure in 30 days.",
            ),
            NotePost(
                ActorSession(client=v2_client, actor=v2_in_v2),
                "V2 Status Update",
                "V2 confirms the issue affects our component. We will align "
                "our fix and deployment timeline with the 30-day target.",
            ),
        ],
        in_reply_to=v1_note,
    )

    logger.info(
        "✓ Notes exchange complete (C2 and V2 notes added to the thread)"
    )
    return v2_note


def _phase_fix_lifecycle(
    c1_client: DataLayerClient,
    v1_client: DataLayerClient,
    v2_client: DataLayerClient,
    reporter_client: DataLayerClient,
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
        with demo_step(f"Actor {ref_id(v1_in_v1)} reports fix ready"):
            ActorSession(client=v1_client, actor=v1_in_v1).with_case(
                case
            ).quiet().notify_fix_ready()
        with demo_check("V1 participant vf_state transitions to VF"):
            wait_for_participant_vf_state(
                client=v1_client,
                case_id=case.id_,
                actor_id=v1.id_,
                expected_states={CS_vf.VF},
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
        with demo_step(f"Actor {ref_id(v2_in_v2)} reports fix ready"):
            ActorSession(client=v2_client, actor=v2_in_v2).with_case(
                case
            ).quiet().notify_fix_ready()
        with demo_check("V2 participant vf_state transitions to VF"):
            wait_for_participant_vf_state(
                client=v2_client,
                case_id=case.id_,
                actor_id=v2.id_,
                expected_states={CS_vf.VF},
            )

    with demo_check("M5: C1 replica shows V1 and V2 CS include F (fix ready)"):
        wait_for_participant_vf_state(
            client=c1_client,
            case_id=case.id_,
            actor_id=v1.id_,
            expected_states={CS_vf.VF},
        )
        wait_for_participant_vf_state(
            client=c1_client,
            case_id=case.id_,
            actor_id=v2.id_,
            expected_states={CS_vf.VF},
        )
        wait_for_participant_vf_state(
            client=reporter_client,
            case_id=case.id_,
            actor_id=v1.id_,
            expected_states={CS_vf.VF},
        )
        wait_for_participant_vf_state(
            client=reporter_client,
            case_id=case.id_,
            actor_id=v2.id_,
            expected_states={CS_vf.VF},
        )
        verify_fix_ready(
            receiver_client=v1_client,
            reporter_client=reporter_client,
            case_id=case.id_,
            receiver_actor_id=v1.id_,
        )
        verify_fix_ready(
            receiver_client=v2_client,
            reporter_client=reporter_client,
            case_id=case.id_,
            receiver_actor_id=v2.id_,
        )

    # V2 (VENDOR + DEPLOYER) advances to fix-deployed (VFD).
    with demo_step(f"Actor {ref_id(v2_in_v2)} reports fix deployed"):
        ActorSession(client=v2_client, actor=v2_in_v2).with_case(
            case
        ).quiet().notify_fix_deployed()

    with demo_check("V2 participant d_state transitions to D"):
        wait_for_participant_d_state(
            client=v2_client,
            case_id=case.id_,
            actor_id=v2.id_,
            expected_states={CS_d.D},
        )

    with demo_check(
        "M6: C1 replica shows V1=VFd (no deploy), V2=VFD (deployed)"
    ):
        wait_for_participant_vf_state(
            client=c1_client,
            case_id=case.id_,
            actor_id=v1.id_,
            expected_states={CS_vf.VF},
        )
        wait_for_participant_d_state(
            client=c1_client,
            case_id=case.id_,
            actor_id=v2.id_,
            expected_states={CS_d.D},
        )
        wait_for_participant_vf_state(
            client=reporter_client,
            case_id=case.id_,
            actor_id=v1.id_,
            expected_states={CS_vf.VF},
        )
        wait_for_participant_d_state(
            client=reporter_client,
            case_id=case.id_,
            actor_id=v2.id_,
            expected_states={CS_d.D},
        )
        verify_fix_ready(
            receiver_client=v1_client,
            reporter_client=reporter_client,
            case_id=case.id_,
            receiver_actor_id=v1.id_,
        )
        verify_fix_deployed(
            receiver_client=v2_client,
            reporter_client=reporter_client,
            case_id=case.id_,
            receiver_actor_id=v2.id_,
        )

    logger.info(
        "✓ Fix lifecycle: V1=VFd (no deploy path), V2=VFD (full deploy path)"
    )


def _phase_publication(
    reporter_client: DataLayerClient,
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
    reporter_in_reporter: as_Actor,
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
    with demo_step(
        f"Actor {ref_id(v1_in_v1)} reports vulnerability publicly disclosed"
    ):
        ActorSession(client=v1_client, actor=v1_in_v1).with_case(
            case
        ).quiet().notify_published()

    # Wait for CaseActor to process V1's publication and emit EM.EXITED
    # before V2 publishes to avoid a non-deterministic ledger ordering.
    with demo_check(
        "Embargo terminated (EM.EXITED) after V1 reports published"
    ):
        wait_for_case_em_terminated(
            client=v1_client,
            case_id=case.id_,
        )

    with demo_step(
        f"Actor {ref_id(v2_in_v2)} reports vulnerability publicly disclosed"
    ):
        ActorSession(client=v2_client, actor=v2_in_v2).with_case(
            case
        ).quiet().notify_published()
    with demo_step(
        f"Actor {ref_id(c2_in_c2)} reports vulnerability publicly disclosed"
    ):
        ActorSession(client=c2_client, actor=c2_in_c2).with_case(
            case
        ).quiet().notify_published()
    with demo_step(
        f"Actor {ref_id(c1_in_c1)} reports vulnerability publicly disclosed"
    ):
        ActorSession(client=c1_client, actor=c1_in_c1).with_case(
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
        "M7: all replicas EM.EXITED, all participants public-aware"
    ):
        wait_for_case_em_terminated(
            client=reporter_client,
            case_id=case.id_,
        )
        wait_for_participant_vf_state(
            client=c1_client,
            case_id=case.id_,
            actor_id=v1.id_,
            expected_states={CS_vf.VF},
        )
        wait_for_participant_d_state(
            client=c1_client,
            case_id=case.id_,
            actor_id=v2.id_,
            expected_states={CS_d.D},
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
    v1_client: DataLayerClient,
    c2_client: DataLayerClient,
    v2_client: DataLayerClient,
    c1_in_c1: as_Actor,
    v1_in_v1: as_Actor,
    c2_in_c2: as_Actor,
    v2_in_v2: as_Actor,
    reporter_in_reporter: as_Actor,
    case: as_VulnerabilityCase,
    case_actor_client: DataLayerClient,
) -> None:
    """Close the case from all five participants and verify terminal state.

    V1, V2, C2 and the Reporter leave first; C1, the Case Owner, leaves last,
    once their departures are recorded (CM-23-015) in the CASE_MANAGER's store
    on the dedicated case-actor container.
    """
    logger.info("─" * 80)
    logger.info("Phase 7: Case closure — all participants RM.CLOSED")
    logger.info("─" * 80)

    close_case_owner_last(
        case=case,
        milestone="M8",
        authority_client=case_actor_client,
        others=[
            CaseLeaver(client=v1_client, actor=v1_in_v1),
            CaseLeaver(client=v2_client, actor=v2_in_v2),
            CaseLeaver(client=c2_client, actor=c2_in_c2),
            CaseLeaver(client=reporter_client, actor=reporter_in_reporter),
        ],
        owner=CaseLeaver(client=c1_client, actor=c1_in_c1),
    )


def _phase_dump_case_ledgers(
    reporter_client: DataLayerClient,
    c1_client: DataLayerClient,
    v1_client: DataLayerClient,
    c2_client: DataLayerClient,
    v2_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    case: as_VulnerabilityCase,
    demo_name: str = "rcvcv",
) -> None:
    """Dump case ledger entries from each actor container to JSONL files.

    Thin scenario-specific wrapper over
    :func:`~vultron.demo.helpers.ledger_dump.dump_case_ledgers`, which owns the
    per-actor export, the 404 handling, and the dump manifest. This function
    only names RCVCV's participants and where each one's ledger lives.
    """
    # Devlog directory names use scenario-role names (DEMOMA-19-007):
    # reporter, c1, v1, c2, v2, case-actor.
    # Route keys come from each client's own actor id, not its display name:
    # the key selects the store (ADR-0073), and the display name is the part
    # the actor plays here rather than the actor it is.
    targets = [
        LedgerDumpTarget(
            "reporter",
            reporter_client,
            replica_route_key(reporter_client),
        ),
        # C1 is the first Coordinator, on cast slot 2.
        LedgerDumpTarget("c1", c1_client, replica_route_key(c1_client)),
        # V1 is the first Vendor, on cast slot 1.
        LedgerDumpTarget("v1", v1_client, replica_route_key(v1_client)),
        # C2 is a character actor, on cast slot 3.
        LedgerDumpTarget("c2", c2_client, replica_route_key(c2_client)),
        # V2 is a character actor, on cast slot 4.
        LedgerDumpTarget("v2", v2_client, replica_route_key(v2_client)),
        # The canonical ledger lives on the dedicated case-actor container.
        case_actor_dump_target(case_actor_client),
    ]

    dump_case_ledgers(demo_name=demo_name, case=case, targets=targets)


def run_rcvcv_demo(
    reporter_client: DataLayerClient,
    c1_client: DataLayerClient,
    v1_client: DataLayerClient,
    c2_client: DataLayerClient,
    v2_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    reporter_id: str | None = None,
    c1_id: str | None = None,
    v1_id: str | None = None,
    c2_id: str | None = None,
    v2_id: str | None = None,
) -> None:
    """Orchestrate the RCVCV CVD workflow."""
    logger.info("=" * 80)
    logger.info(
        "RCVCV DEMO: Reporter + C1(CASE_OWNER) + V1(VENDOR) + C2(COORDINATOR) + V2(VENDOR+DEPLOYER)"
    )
    logger.info("=" * 80)
    logger.info("Reporter container: %s", reporter_client.base_url)
    logger.info("C1 container:     %s", c1_client.base_url)
    logger.info("V1 container:     %s", v1_client.base_url)
    logger.info("C2 container:     %s", c2_client.base_url)
    logger.info("V2 container:     %s", v2_client.base_url)
    logger.info("CaseActor container: %s", case_actor_client.base_url)

    with scenario_harness("rcvcv") as harness:
        (
            reporter,
            c1,
            c1_in_c1,
            v1,
            v1_in_v1,
            c2_in_c2,
            v2,
            report,
            offer,
            case,
            v1_note,
        ) = _phase_report_submission(
            reporter_client,
            c1_client,
            v1_client,
            c2_client,
            v2_client,
            case_actor_client,
            reporter_id,
            c1_id,
            v1_id,
            c2_id,
            v2_id,
        )

        # Register the dump as soon as there is a case to dump, so every phase
        # below can fail without costing us the ledgers (ISSUE-2239).
        harness.dump_with(
            lambda: _phase_dump_case_ledgers(
                reporter_client=reporter_client,
                c1_client=c1_client,
                v1_client=v1_client,
                c2_client=c2_client,
                v2_client=v2_client,
                case_actor_client=case_actor_client,
                case=case,
                demo_name=harness.demo_name,
            )
        )

        _phase_c2_suggests_v2(
            reporter_client=reporter_client,
            c1_client=c1_client,
            c2_client=c2_client,
            v2_client=v2_client,
            case_actor_client=case_actor_client,
            c1_in_c1=c1_in_c1,
            c2_in_c2=c2_in_c2,
            v2=v2,
            case=case,
            offer=offer,
            report=report,
            reporter=reporter,
            v1=v1,
        )

        v2_in_v2 = get_actor_by_id(v2_client, v2.id_)
        reporter_in_reporter = get_actor_by_id(reporter_client, reporter.id_)

        _phase_sync_verification(
            reporter_client,
            c1_client,
            v1_client,
            c2_client,
            v2_client,
            c1,
            reporter,
            case,
            v1,
            c2_in_c2,
            v2,
        )
        _phase_joiner_notes(
            c1_client=c1_client,
            c2_client=c2_client,
            v2_client=v2_client,
            c2_in_c2=c2_in_c2,
            v2_in_v2=v2_in_v2,
            case=case,
            v1_note=v1_note,
        )
        _phase_fix_lifecycle(
            c1_client,
            v1_client,
            v2_client,
            reporter_client,
            v1,
            v1_in_v1,
            v2,
            v2_in_v2,
            case,
        )
        _phase_publication(
            reporter_client,
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
            reporter_in_reporter,
            case,
        )
        _phase_case_closure(
            reporter_client,
            c1_client,
            v1_client,
            c2_client,
            v2_client,
            c1_in_c1,
            v1_in_v1,
            c2_in_c2,
            v2_in_v2,
            reporter_in_reporter,
            case,
            case_actor_client,
        )

    logger.info("=" * 80)
    logger.info("RCVCV DEMO COMPLETE ✓  (full 5-actor lifecycle)")
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@scenario(
    name="rcvcv",
    label="RCVCV",
    participants="Reporter + C1 + V1 + C2 + V2",
    feature="Actor-suggestion flow (ADR-0026)",
    in_pr_set=True,
    path=(
        ("reporter-whom-to-tell", "coordinator"),
        ("coordinator-invite-whom", "vendor"),
        ("vendor-join", "accept"),
        ("reporter-after-join", "ask-vendor"),
        ("coordinator-after-answer", "invite-coordinator"),
    ),
)
def main(
    skip_health_check: bool = False,
    reporter_url: str | None = None,
    c1_url: str | None = None,
    v1_url: str | None = None,
    c2_url: str | None = None,
    v2_url: str | None = None,
    case_actor_url: str | None = None,
    reporter_id: str | None = None,
    c1_id: str | None = None,
    v1_id: str | None = None,
    c2_id: str | None = None,
    v2_id: str | None = None,
) -> None:
    """Entry point for the RCVCV CVD workflow demo.

    Args:
        skip_health_check: Skip server availability checks.
        reporter_url: Override base URL for the Reporter container.
        c1_url: Override base URL for the C1 (Coordinator1) container.
        v1_url: Override base URL for the V1 (Vendor1) container.
        c2_url: Override base URL for the C2 (Coordinator2) container.
        v2_url: Override base URL for the V2 (VendorDeployer) container.
        case_actor_url: Override base URL for the dedicated CaseActor
            container.
        reporter_id: Optional deterministic URI for the Reporter actor.
        c1_id: Optional deterministic URI for the C1 actor.
        v1_id: Optional deterministic URI for the V1 actor.
        c2_id: Optional deterministic URI for the C2 actor.
        v2_id: Optional deterministic URI for the V2 actor.
    """
    f_url = reporter_url or REPORTER_BASE_URL
    c1_resolved = c1_url or C1_BASE_URL
    v1_resolved = v1_url or V1_BASE_URL
    c2_resolved = c2_url or C2_BASE_URL
    v2_resolved = v2_url or V2_BASE_URL
    ca_url = case_actor_url or CASE_ACTOR_BASE_URL

    reporter_client = DataLayerClient(base_url=f_url)
    c1_client = DataLayerClient(base_url=c1_resolved)
    v1_client = DataLayerClient(base_url=v1_resolved)
    c2_client = DataLayerClient(base_url=c2_resolved)
    v2_client = DataLayerClient(base_url=v2_resolved)
    # Bound here: a /datalayer/ read names whose store it is about (ADR-0073),
    # and the dedicated container hosts only the CaseActor.
    case_actor_client = bound_case_actor_client(ca_url)

    if not skip_health_check:
        targets: list[tuple[str, DataLayerClient]] = [
            ("Reporter", reporter_client),
            ("C1", c1_client),
            ("V1", v1_client),
            ("C2", c2_client),
            ("V2", v2_client),
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

    # scenario_harness() inside run_rcvcv_demo() owns the failure accumulator:
    # it resets it, always dumps the case ledgers, and asserts success — so a
    # failure here never costs us the artifacts (ISSUE-2239).
    run_rcvcv_demo(
        reporter_client=reporter_client,
        c1_client=c1_client,
        v1_client=v1_client,
        c2_client=c2_client,
        v2_client=v2_client,
        case_actor_client=case_actor_client,
        **resolved_actor_ids(
            _ROLES,
            reporter=(reporter_client, reporter_id),
            c1=(c1_client, c1_id),
            v1=(v1_client, v1_id),
            c2=(c2_client, c2_id),
            v2=(v2_client, v2_id),
        ),
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
