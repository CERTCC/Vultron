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
"""The story fragments only ``rcvcv`` tells.

``rcvcv`` shares its opening with ``rcv`` up to C1's decision
(:data:`~vultron.demo.helpers.coordinated_story.REPORTER_ASKS_THE_VENDOR`)
and then tells these fragments, in the order its story lists them
(:mod:`~vultron.demo.scenario.rcvcv_demo.story`): a second Coordinator joins,
suggests a VendorDeployer through ADR-0026, and the five parties run the
lifecycle to closure.  The cast names they read are in
:mod:`~vultron.demo.scenario.rcvcv_demo.cast` (CS-18-005, DEMOMA-19).
"""

import logging

from vultron.core.states.cs import CS_d, CS_vf
from vultron.demo.helpers.coordinated_story import (
    REPORTER,
    REPORTER_LABEL,
    TIMELINE_ANSWER,
    close_the_case,
    invitee_joins_the_case,
    reports_published,
    seat_character_actors,
    vendor_notifies_fix_ready,
)
from vultron.demo.helpers.milestones import (
    verify_case_active,
    verify_fix_deployed,
    verify_fix_ready,
    verify_publicly_disclosed,
    verify_stops_at_fix_ready,
)
from vultron.demo.helpers.notes import NotePost, add_note_thread
from vultron.demo.helpers.owner_decision_story import (
    Part,
    the_owner_approves_a_suggested_actor,
)
from vultron.demo.helpers.polling import (
    LATE_JOINER_TIMEOUT,
    wait_for_case_em_terminated,
    wait_for_participant_d_state,
    wait_for_participant_vf_state,
)
from vultron.demo.helpers.seeding import seed_containers_rcvcv
from vultron.demo.helpers.story import (
    StoryProp,
    StoryState,
)
from vultron.demo.helpers.sync import (
    run_sync_verification_phase,
    wait_for_replica_ledger_coverage,
)
from vultron.demo.scenario.rcvcv_demo.cast import (
    C1,
    C1_LABEL,
    C2,
    C2_LABEL,
    V1,
    V1_LABEL,
    V2,
    V2_LABEL,
)
from vultron.demo.utils import (
    demo_check,
    demo_step,
    ref_id,
)
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)


#: Seconds a wait of this scenario's later, multi-hop joins may take: V2
#: arrives through the ADR-0026 suggest, approve, invite and accept chain.
LATE_JOIN_TIMEOUT = 40.0


def replicas_drain_before_the_second_coordinator(state: StoryState) -> None:
    """Wait for the opening's ledger to reach every replica.

    Added as a workaround for #2819 when the CaseActor queued its ledger
    fan-out ahead of ``Create(VulnerabilityCase)`` and every replica rejected
    and replayed; that ordering is fixed at the source (CP-09-009, CM-17-009,
    #2898), so this is now a plain replication check that also keeps the later
    ledger indices deterministic.  It is the same
    read-authority-tail-then-poll-each-replica loop as the sync-verification
    and closure phases, so it goes through the one shared helper
    (DEMOMA-23-005, #3906); each replica wait is a ``demo_gate`` inside it.
    """
    wait_for_replica_ledger_coverage(
        auth_client=state.client(C1),
        replicas=[
            (state.client(REPORTER), REPORTER_LABEL),
            (state.client(V1), V1_LABEL),
        ],
        case_id=state.case.id_,
        phase_label="opening drain before C2 joins",
    )


def seed_the_second_coordinator_and_vendor(state: StoryState) -> None:
    """Seed and seat C2 and V2, the scenario's two character actors.

    ``seed_containers_rcvcv`` creates both and registers every actor as a peer
    of the other four (DEMOMA-19-002, DEMOMA-19-012, DEMOMA-19-013); the three
    the opening already seeded come back unchanged, because ``POST /actors/``
    and ``POST /actors/{id}/peers/`` are idempotent.  Running it here rather
    than in the shared opening is what lets this scenario's recording match
    ``rcv``'s byte for byte up to C1's decision (DEMOCI-11-018).

    V2 is seated here with C2 although it is invited two fragments later: C2
    suggests it by actor id, which the suggestion needs before V2 has joined
    anything.
    """
    c2_container = state.container(C2)
    v2_container = state.container(V2)
    with demo_step("Seeding the C2 and V2 containers with actor records"):
        seeded = seed_containers_rcvcv(
            reporter_client=state.client(REPORTER),
            c1_client=state.client(C1),
            v1_client=state.client(V1),
            c2_client=c2_container.client,
            v2_client=v2_container.client,
            reporter_actor_id=state.actor_id(REPORTER),
            c1_actor_id=state.actor_id(C1),
            v1_actor_id=state.actor_id(V1),
            c2_actor_id=c2_container.actor_id,
            v2_actor_id=v2_container.actor_id,
            case_actor_client=state.case_actor_client,
        )
        # Seated inside the step that seeded them, and neither seated until
        # both read back: a partly seated cast would let C2's invite run
        # before V2's absence stopped the story (#2308, EDF-06-005).
        seat_character_actors(state, {C2: seeded[3].id_, V2: seeded[4].id_})


#: The case C2 has joined, as its id.  Read by the suggestion C2 makes next,
#: which only a participant may make (DEMOMA-19-009), so a join whose roster
#: never filled stops the story there rather than suggesting into a case C2 is
#: not in (DEMOCI-01-011, #5535).
C2_JOINED: StoryProp[str] = StoryProp("case C2 joined", str)


def c1_invites_the_second_coordinator(state: StoryState) -> None:
    """C1 invites C2 with ``CVDRole.COORDINATOR``; C2 accepts and joins.

    C2 runs no RM triage: it joins to help coordinate, not to judge the
    report, so it engages no case of its own (CM-11-022 applies to the
    invitee that answers over a report it must triage).  The roster is this
    join's gate and keeps :data:`C2_JOINED`, which C2's suggestion reads.
    """
    invitee_joins_the_case(
        state,
        C2,
        C2_LABEL,
        role=CVDRole.COORDINATOR,
        seated=(REPORTER, C1, V1, C2),
        triages=False,
        joined=C2_JOINED,
        cross_container_timeout=LATE_JOIN_TIMEOUT,
    )


def required_participants_are_present(state: StoryState) -> None:
    """The case holds every participant invited so far, and is still embargoed."""
    with demo_check(
        "M1: required participants (≥5), EM.ACTIVE, Reporter + V1 + C2 have"
        " replicas"
    ):
        verify_case_active(
            receiver_client=state.client(C1),
            reporter_client=state.client(REPORTER),
            case_id=state.case.id_,
            receiver_actor_id=state.actor_id(C1),
            reporter_actor_id=state.actor_id(REPORTER),
        )


def c2_suggests_the_vendor_deployer(state: StoryState) -> None:
    """C2 suggests V2 via ADR-0026; C1 approves; V2 joins (DEMOMA-19-009).

    The ADR-0026 suggest-actor flow, which the two-coordinator pair's
    ``owner-keep-case:keep`` continuation also tells, so it is one shared step
    (:func:`~vultron.demo.helpers.owner_decision_story\
    .the_owner_approves_a_suggested_actor`, DEMOMA-17-001).  V2's roles are
    explicit so ``EvaluateDefaultRolesNode`` does not fall back to its
    hardcoded ``[VENDOR]`` default (#1969), which is what makes V2 a Deployer
    as well as a Vendor.
    """
    the_owner_approves_a_suggested_actor(
        state,
        joined=C2_JOINED,
        owner=Part(C1, C1_LABEL),
        suggester=Part(C2, C2_LABEL),
        newcomer=Part(V2, V2_LABEL),
        roles=[CVDRole.VENDOR, CVDRole.DEPLOYER],
        seated=(REPORTER, C1, V1, C2, V2),
        timeout_seconds=LATE_JOIN_TIMEOUT,
        join_timeout=LATE_JOINER_TIMEOUT,
    )


def every_replica_converges(state: StoryState) -> None:
    """Verify LedgerFanout replication for all participant replicas."""
    run_sync_verification_phase(
        auth_client=state.client(C1),
        auth_label=C1_LABEL,
        auth_actor_id=state.actor_id(C1),
        reporter_client=state.client(REPORTER),
        reporter_actor_id=state.actor_id(REPORTER),
        replicas=[
            (state.client(REPORTER), REPORTER_LABEL),
            (state.client(V1), V1_LABEL),
            (state.client(C2), C2_LABEL),
            (state.client(V2), V2_LABEL),
        ],
        case_id=state.case.id_,
        expected_participant_ids={
            state.actor_id(who) for who in (REPORTER, C1, V1, C2, V2)
        },
        # V2 joins after the opening completes and catches up from genesis.
        late_joiners=(state.client(V2),),
        state_checks=[
            (state.client(REPORTER), REPORTER_LABEL),
            (state.client(V2), V2_LABEL),
        ],
    )
    logger.info("✓ M1: All five replicas synchronized (LedgerFanout verified)")


def the_joiners_add_their_notes(state: StoryState) -> None:
    """C2 and V2, once joined, add to the note thread the opening posted.

    They reply to the Coordinator's summary rather than opening a thread of
    their own, so the thread the opening shares with ``rcv`` stays one thread
    (:data:`TIMELINE_ANSWER`).
    """
    add_note_thread(
        state.client(C1),
        state.case,
        [
            NotePost(
                state.actor(C2),
                "C2 Update",
                "C2 confirms V2 is engaged. Target disclosure in 30 days.",
            ),
            NotePost(
                state.actor(V2),
                "V2 Status Update",
                "V2 confirms the issue affects our component. We will align "
                "our fix and deployment timeline with the 30-day target.",
            ),
        ],
        in_reply_to=state.kept(TIMELINE_ANSWER),
    )
    logger.info(
        "✓ Notes exchange complete (C2 and V2 notes added to the thread)"
    )


def both_vendors_run_the_fix_lifecycle(state: StoryState) -> None:
    """Advance V1 to VFd and V2 to VFD (DEMOMA-19-004, DEMOMA-19-026).

    V1 (VENDOR only) stops at VFd — fix-ready, no deploy step.  V2 (VENDOR +
    DEPLOYER) advances to VFD — fix-ready then fix-deployed.  ``rcv``'s own
    fix-ready fragment checks the Coordinator's view twice for its one Vendor;
    this one checks both vendors on both coordinator-side replicas, so it is
    this scenario's own step rather than a reuse of that one.
    """
    for name, label in ((V1, V1_LABEL), (V2, V2_LABEL)):
        vendor_notifies_fix_ready(state, name, label)

    with demo_check("M5: C1 replica shows V1 and V2 CS include F (fix ready)"):
        for fix_ready_watcher in (C1, REPORTER):
            for name in (V1, V2):
                wait_for_participant_vf_state(
                    client=state.client(fix_ready_watcher),
                    case_id=state.case.id_,
                    actor_id=state.actor_id(name),
                    expected_states={CS_vf.VF},
                )
        for name in (V1, V2):
            verify_fix_ready(
                receiver_client=state.client(name),
                reporter_client=state.client(REPORTER),
                case_id=state.case.id_,
                receiver_actor_id=state.actor_id(name),
            )

    v2 = state.actor(V2)
    with demo_step(f"Actor {ref_id(v2.actor)} reports fix deployed"):
        v2.with_case(state.case).quiet().notify_fix_deployed()

    with demo_check("V2 participant d_state transitions to D"):
        wait_for_participant_d_state(
            client=state.client(V2),
            case_id=state.case.id_,
            actor_id=state.actor_id(V2),
            expected_states={CS_d.D},
        )

    with demo_check(
        "M6: C1 replica shows V1=VFd (no deploy), V2=VFD (deployed)"
    ):
        for deployed_watcher in (C1, REPORTER):
            wait_for_participant_vf_state(
                client=state.client(deployed_watcher),
                case_id=state.case.id_,
                actor_id=state.actor_id(V1),
                expected_states={CS_vf.VF},
            )
            wait_for_participant_d_state(
                client=state.client(deployed_watcher),
                case_id=state.case.id_,
                actor_id=state.actor_id(V2),
                expected_states={CS_d.D},
            )
        verify_fix_ready(
            receiver_client=state.client(V1),
            reporter_client=state.client(REPORTER),
            case_id=state.case.id_,
            receiver_actor_id=state.actor_id(V1),
        )
        # "V1=VFd (no deploy)" is a claim about the d→D transition V1 never
        # makes, so the label needs this read as well as the VF one (#5602).
        verify_stops_at_fix_ready(
            receiver_client=state.client(V1),
            reporter_client=state.client(REPORTER),
            case_id=state.case.id_,
            receiver_actor_id=state.actor_id(V1),
        )
        verify_fix_deployed(
            receiver_client=state.client(V2),
            reporter_client=state.client(REPORTER),
            case_id=state.case.id_,
            receiver_actor_id=state.actor_id(V2),
        )

    logger.info(
        "✓ Fix lifecycle: V1=VFd (no deploy path), V2=VFD (full deploy path)"
    )


def v1_publishes_then_the_others(state: StoryState) -> None:
    """V1 publishes first, triggering the embargo teardown.

    DEMOMA-19-005 sets the order and DEMOMA-19-027 the wait for the teardown.

    The scenario waits for the CaseActor to process V1's publication and emit
    ``EM.EXITED`` before V2 publishes, so the ledger order is deterministic.
    """
    reports_published(state, V1)

    with demo_check(
        "Embargo terminated (EM.EXITED) after V1 reports published"
    ):
        wait_for_case_em_terminated(
            client=state.client(V1), case_id=state.case.id_
        )

    for name in (V2, C2, C1):
        reports_published(state, name)

    with demo_check(
        "Embargo terminated (EM.EXITED) propagated to Reporter before"
        " notify-published"
    ):
        wait_for_case_em_terminated(
            client=state.client(REPORTER), case_id=state.case.id_
        )

    reports_published(state, REPORTER)

    with demo_check(
        "M7: all replicas EM.EXITED, all participants public-aware"
    ):
        wait_for_case_em_terminated(
            client=state.client(REPORTER), case_id=state.case.id_
        )
        wait_for_participant_vf_state(
            client=state.client(C1),
            case_id=state.case.id_,
            actor_id=state.actor_id(V1),
            expected_states={CS_vf.VF},
        )
        wait_for_participant_d_state(
            client=state.client(C1),
            case_id=state.case.id_,
            actor_id=state.actor_id(V2),
            expected_states={CS_d.D},
        )
        verify_publicly_disclosed(
            receiver_client=state.client(C1),
            reporter_client=state.client(REPORTER),
            case_id=state.case.id_,
            receiver_actor_id=state.actor_id(C1),
        )


def all_five_close_the_case(state: StoryState) -> None:
    """Close the case from all five participants and verify terminal state.

    V1, V2, C2 and the Reporter leave first; C1, the Case Owner, leaves last,
    once their departures are recorded (CM-23-015) in the CASE_MANAGER's store
    on the dedicated case-actor container.
    """
    close_the_case(
        state, others=(V1, V2, C2, REPORTER), owner=C1, milestone="M8"
    )
