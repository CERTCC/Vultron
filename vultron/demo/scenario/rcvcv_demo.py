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

The story is assembled, not written out: it starts with
:data:`~vultron.demo.helpers.coordinated_story.REPORTER_ASKS_THE_VENDOR`, the
opening it shares with ``rcv`` up to C1's decision, and continues with C1
inviting a second Coordinator (:data:`STORY`, DEMOCI-11-019).  C1 and V1 are
the family's Coordinator and Vendor, so the story reaches them under those
names; ``c1`` and ``v1`` remain their names on the command line and in the
devlogs the invariant harness reads (DEMOMA-19-018).

C2 and V2 are **character actors**: their containers are reset with the rest,
and their actors are seeded by the fragment that brings them in rather than by
the shared opening, because every record the opening writes before the case
exists moves the first ledger entry's timestamp away from the sibling it must
match byte for byte (DEMOCI-11-018).

Spec: DEMOMA-19 (GitHub issue #1925).
"""

import logging

from vultron.core.states.cs import CS_d, CS_vf
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
from vultron.demo.helpers.coordinated_story import (
    CASE_ACTOR_NAME,
    COORDINATOR,
    REPORTER,
    REPORTER_ASKS_THE_VENDOR,
    REPORTER_LABEL,
    TIMELINE_ANSWER,
    VENDOR,
    CastContainer,
    await_reporter_case_replica,
    close_the_case,
    coordinated_clients,
    dump_coordinated_ledgers,
    invitee_joins_the_case,
    invitee_triages_after_joining,
    open_coordinated_cast,
    reports_published,
    seat_character_actor,
    vendor_notifies_fix_ready,
)
from vultron.demo.helpers.harness import ScenarioHarness
from vultron.demo.helpers.invite_chain import run_case_invite_chain
from vultron.demo.helpers.milestones import (
    verify_case_active,
    verify_fix_deployed,
    verify_fix_ready,
    verify_publicly_disclosed,
)
from vultron.demo.helpers.notes import NotePost, add_note_thread
from vultron.demo.helpers.polling import (
    LATE_JOINER_TIMEOUT,
    find_case_actor_participant_id,
    find_cp_offer_for_case,
    wait_for_case_em_terminated,
    wait_for_participant_d_state,
    wait_for_participant_vf_state,
)
from vultron.demo.helpers.seeding import seed_containers_rcvcv
from vultron.demo.helpers.story import (
    StoryState,
    UnseatedContainer,
    choose,
    run_story,
    story,
)
from vultron.demo.helpers.sync import (
    run_sync_verification_phase,
    wait_for_replica_ledger_coverage,
)
from vultron.demo.scenario.registry import scenario
from vultron.demo.utils import (
    DataLayerClient,
    demo_check,
    demo_gate,
    demo_step,
    ref_id,
    setup_demo_logging,
)
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)

# AC-6 audit (#2203): the case-replica waits this module reaches through poll
# for VulnerabilityCase object delivery (ADR-0041 seeding path). ADR-0037 and
# ADR-0059 buffer Announce(CaseLedgerEntry) entries, not VulnerabilityCase
# objects, so each of those waits remains necessary.

#: This scenario's names for the family's Coordinator and Vendor.  C1 is the
#: Coordinator that receives the report and holds CASE_OWNER, V1 the first
#: Vendor; the story seats them under the family's role names, so one copy of
#: the shared opening serves ``rcv`` and ``rcvcv`` alike (DEMOCI-11-018).
C1 = COORDINATOR
C1_LABEL = "C1"
V1 = VENDOR
V1_LABEL = "V1"
C2 = "c2"
C2_LABEL = "C2"
V2 = "v2"
V2_LABEL = "V2"

#: The devlogs directory each replica's ledger is dumped under: the scenario's
#: own name for the actor, which is what its invariant harness loads
#: (DEMOMA-19-018, DEMOMA-19-020).
DEVLOG_REPLICAS: tuple[tuple[str, str], ...] = (
    (REPORTER, REPORTER),
    ("c1", C1),
    ("v1", V1),
    (C2, C2),
    (V2, V2),
)

#: Seconds a wait of this scenario's later, multi-hop joins may take: V2
#: arrives through the ADR-0026 suggest, approve, invite and accept chain.
LATE_JOIN_TIMEOUT = 40.0

# The scenario's actors in main() parameter order, each seated in a container of
# the fixed cast (DEMOCI-11-020).  The demo CLI derives this scenario's
# sub-command options from this list (DEMOCI-11-011).
ROLES: list[ActorRole] = [
    ActorRole(REPORTER, REPORTER_SLOT, REPORTER_LABEL, has_id=True),
    ActorRole(
        "c1", COORDINATOR_SLOT, "C1 (Coordinator1/CASE_OWNER)", has_id=True
    ),
    ActorRole("v1", VENDOR_SLOT, "V1 (Vendor1)", has_id=True),
    ActorRole(C2, CAST[3], "C2 (Coordinator2)", has_id=True),
    ActorRole(V2, CAST[4], "V2 (VendorDeployer)", has_id=True),
    case_actor_role(),
]
_ROLES = role_map(ROLES)

#: ``vultron-demo rcvcv --help`` text. Lives here rather than in ``cli.py``
#: because the sub-command is generated from the registry and the scenario
#: module is the only place that knows what its own workflow does.
CLI_HELP = """Run the RCVCV 5-party CVD demo (DEMOMA-19).

Five actors coordinate a full CVD lifecycle:
Reporter + C1 (CASE_OWNER) + V1 (VENDOR) + C2 (COORDINATOR) + V2
(VENDOR+DEPLOYER).

\b
Workflow:
  1. Reset all five containers and seed Reporter, C1 and V1.
  2. Reporter submits a report to C1; C1 validates and engages.
  3. C1 invites V1 (VENDOR); the Reporter asks, V1 and C1 answer in case
     notes; then C1 invites C2 (COORDINATOR).
  4. C2 suggests V2 via ADR-0026; C1 approves; V2 joins via CaseActor.
  5. Verify LedgerFanout replication across all five replicas.
  6. C2 and V2 add their notes to the thread.
  7. Fix lifecycle: V1 → VFd (no deploy); V2 → VFD (fix-deployed).
  8. Publication: V1 publishes first → embargo terminates; all publish.
  9. All actors close the case.
 10. Export case ledger JSONL for each actor (devlogs).
"""


# ---------------------------------------------------------------------------
# Fragments this scenario alone tells
# ---------------------------------------------------------------------------


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
        # Seated inside the step that seeded them: a seeding failure then
        # leaves the cast short, and the fragments that reach for C2 or V2
        # stop the story rather than acting on a stand-in (#2308).
        seat_character_actor(state, C2, seeded[3].id_)
        seat_character_actor(state, V2, seeded[4].id_)


def c1_invites_the_second_coordinator(state: StoryState) -> None:
    """C1 invites C2 with ``CVDRole.COORDINATOR``; C2 accepts and joins.

    C2 runs no RM triage: it joins to help coordinate, not to judge the
    report, so it engages no case of its own (CM-11-002 applies to the
    invitee that answers over a report it must triage).  The roster check
    therefore runs inside the invite chain's gate.
    """
    invitee_joins_the_case(
        state,
        C2,
        C2_LABEL,
        role=CVDRole.COORDINATOR,
        seated=(REPORTER, C1, V1, C2),
        triages=False,
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

    C2 posts ``suggest-actor-to-case``, the CaseActor forwards an
    ``Offer(CaseParticipant)`` to C1, C1 posts ``accept-actor-recommendation``,
    the CaseActor sends the Invite to V2, and V2 accepts.  The invite chain
    polls V2's DataLayer for the Invite and puppeteers the accept
    (DEMOMA-19-022: polling only, no mail-carrying), nesting the accept and
    the replica wait inside the Invite's gate (EDF-06-005, #3038).
    """
    v2 = state.actor(V2).actor

    # Roles must be explicit so EvaluateDefaultRolesNode does not fall back to
    # the hardcoded [VENDOR] default (issue #1969).
    with demo_step("C2 suggests V2 to CaseActor"):
        state.actor(C2).with_case(state.case).quiet().suggest_actor_to_case(
            suggested_actor_id=v2.id_,
            roles=[CVDRole.VENDOR, CVDRole.DEPLOYER],
        )
    logger.info("C2 sent suggest-actor-to-case for V2 (%s)", v2.id_)

    # Every dependent step is nested inside the gate, so a recommendation that
    # never arrives skips the lookup and the approval (ADR-0058).
    with demo_gate("Offer(CaseParticipant) for V2 arrived in C1's DataLayer"):
        cp_offer_id = find_cp_offer_for_case(
            client=state.client(C1),
            case_id=state.case.id_,
            timeout_seconds=LATE_JOIN_TIMEOUT,
        )
        logger.info("Offer(CaseParticipant) ID: %s", cp_offer_id)

        # The CaseActor's participant id is where the Accept is routed back.
        case_actor_id = find_case_actor_participant_id(
            state.client(C1), state.case.id_
        )
        if case_actor_id is None:
            raise AssertionError(
                "CaseActor participant not found in case — cannot route Accept"
            )
        logger.info("CaseActor participant ID: %s", case_actor_id)

        with demo_step("C1 approves actor recommendation"):
            state.actor(C1).quiet().accept_actor_recommendation(
                cp_offer_id=cp_offer_id,
                case_actor_id=case_actor_id,
            )
    logger.info("C1 sent Accept(Offer(CaseParticipant)) to CaseActor")

    run_case_invite_chain(
        case=state.case,
        invitee_name=V2_LABEL,
        invitee_client=state.client(V2),
        invitee=v2,
        invitee_in_own_container=v2,
        invite_timeout=LATE_JOIN_TIMEOUT,
        replica_timeout=LATE_JOIN_TIMEOUT,
        ledger_client=state.case_actor_client,
        reply_timeout=LATE_JOIN_TIMEOUT,
    )

    await_reporter_case_replica(state, LATE_JOIN_TIMEOUT)
    invitee_triages_after_joining(
        state,
        V2,
        V2_LABEL,
        seated=(REPORTER, C1, V1, C2, V2),
        join_timeout=LATE_JOINER_TIMEOUT,
        triage_timeout=LATE_JOIN_TIMEOUT,
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
    """Advance V1 to VFd and V2 to VFD (DEMOMA-19-004).

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
    """V1 publishes first, triggering the embargo teardown (DEMOMA-19-005).

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


#: The RCVCV story: the opening it shares with ``rcv`` up to C1's decision,
#: then the second Coordinator, the ADR-0026 suggestion that brings V2 in, and
#: the five-party lifecycle to closure.  The registry reads this scenario's
#: path off the ``choose`` items (DEMOCI-11-019), so it declares no ``path=``.
STORY = story(
    REPORTER_ASKS_THE_VENDOR,
    # C1 decides once the note thread is answered.
    choose("coordinator-after-answer", "invite-coordinator", by=C1),
    replicas_drain_before_the_second_coordinator,
    seed_the_second_coordinator_and_vendor,
    c1_invites_the_second_coordinator,
    required_participants_are_present,
    c2_suggests_the_vendor_deployer,
    every_replica_converges,
    the_joiners_add_their_notes,
    both_vendors_run_the_fix_lifecycle,
    v1_publishes_then_the_others,
    all_five_close_the_case,
)


def _dump_ledgers(state: StoryState) -> None:
    """Dump each participant's case ledger, by its devlogs name.

    Thin wrapper (DEMOMA-23-002): the harness runs it on the way out, whether
    or not an earlier step failed.  A character actor the run never seated has
    no replica to read, so it is left out rather than 404ing the dump.
    """
    dump_coordinated_ledgers(
        state,
        replicas=[
            entry for entry in DEVLOG_REPLICAS if entry[1] in state.cast
        ],
    )


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

    def open_cast(harness: ScenarioHarness) -> StoryState:
        return open_coordinated_cast(
            harness,
            reporter_client=reporter_client,
            coordinator_client=c1_client,
            vendor_client=v1_client,
            case_actor_client=case_actor_client,
            dump=_dump_ledgers,
            reporter_id=reporter_id,
            coordinator_id=c1_id,
            vendor_id=v1_id,
            unseated={
                C2: UnseatedContainer(C2_LABEL, c2_client, c2_id),
                V2: UnseatedContainer(V2_LABEL, v2_client, v2_id),
            },
        )

    # run_story() owns the failure accumulator through scenario_harness: it
    # resets it, always dumps the case ledgers, and asserts success — so a
    # failure here never costs us the artifacts (ISSUE-2239, DEMOMA-23-001).
    run_story("rcvcv", STORY, open_cast)

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
    story=STORY,
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
    clients = coordinated_clients(
        _ROLES,
        [
            CastContainer(REPORTER, REPORTER_LABEL, reporter_url),
            CastContainer("c1", C1_LABEL, c1_url),
            CastContainer("v1", V1_LABEL, v1_url),
            CastContainer(C2, C2_LABEL, c2_url),
            CastContainer(V2, V2_LABEL, v2_url),
        ],
        skip_health_check=skip_health_check,
        case_actor_url=case_actor_url,
    )
    run_rcvcv_demo(
        reporter_client=clients[REPORTER],
        c1_client=clients["c1"],
        v1_client=clients["v1"],
        c2_client=clients[C2],
        v2_client=clients[V2],
        case_actor_client=clients[CASE_ACTOR_NAME],
        **resolved_actor_ids(
            _ROLES,
            reporter=(clients[REPORTER], reporter_id),
            c1=(clients["c1"], c1_id),
            v1=(clients["v1"], v1_id),
            c2=(clients[C2], c2_id),
            v2=(clients[V2], v2_id),
        ),
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
