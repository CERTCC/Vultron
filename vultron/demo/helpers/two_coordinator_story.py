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
"""Story fragments of the two-coordinator pair, ``rccv-extension``/``-handoff``.

Both scenarios tell one story up to a single decision: the Reporter tells a
Coordinator, that Coordinator engages the case and invites a **second**
Coordinator, and then the owner decides whether to keep the case.  Keep it and
the joiner's suggestion brings the Vendor in (``rccv-extension``, DEMOMA-13);
hand it over and the new owner invites the Vendor itself (``rccv-handoff``,
DEMOMA-14).  Everything before that decision is :data:`C1_INVITES_C2`, written
here once, and everything after it that both tell is written here once too
(DEMOMA-17-001, DEMOCI-11-018).

The opening up to the first Coordinator's own decision is the **rcv family's**
(:data:`~vultron.demo.helpers.coordinated_story\
.REPORTER_TELLS_THE_COORDINATOR`): this pair parts from ``rcv`` and its
siblings at ``coordinator-invite-whom``, where they invite the Vendor and this
pair invites a Coordinator.  So all four coordinator-first scenarios share one
copy of the report submission and the owner's triage, and their recordings
agree byte for byte up to that branch point.

C1 is seated as the family's :data:`~vultron.demo.helpers.coordinated_story\
.COORDINATOR` and the Vendor as its
:data:`~vultron.demo.helpers.coordinated_story.VENDOR`, whatever each
scenario's ``ROLES`` calls them, so the shared opening's fragments reach them
unchanged.  C2 is a **character actor**: its container is reset with the rest
and its actor is seeded by :func:`c2_is_seeded`, the fragment that brings it
in, never by the shared opening — every actor and peer record written before
the case exists is one more read of the recording clock and would move the
first ledger entry away from the siblings this opening must match
(DEMOCI-11-018, #5532).

The two continuations of the owner's decision are **not** here: that decision
appears in the vendor-first half too, so both of its continuations live in
:mod:`vultron.demo.helpers.owner_decision_story` and this module only names
the parts each plays (:data:`C1_PART`, :data:`C2_PART`, :data:`VENDOR_PART`).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence

from vultron.core.states.cs import CS_vf
from vultron.demo.helpers.actor_roles import ActorRole
from vultron.demo.helpers.cast import (
    CAST,
    COORDINATOR_SLOT,
    REPORTER_SLOT,
    VENDOR_SLOT,
)
from vultron.demo.helpers.coordinated_story import (
    COORDINATOR,
    REPORTER,
    REPORTER_LABEL,
    REPORTER_TELLS_THE_COORDINATOR,
    VENDOR,
    VENDOR_LABEL,
    CastContainer,
    dump_coordinated_ledgers,
    invitee_joins_the_case,
    reports_published,
    seat_character_actors,
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
from vultron.demo.helpers.owner_decision_story import (
    OWNER_DECISION_TIMEOUT,
    Part,
)
from vultron.demo.helpers.polling import (
    wait_for_case_em_terminated,
    wait_for_participant_vf_state,
)
from vultron.demo.helpers.seeding import seed_containers_rccv
from vultron.demo.helpers.story import (
    StoryProp,
    StoryState,
    UnseatedContainer,
    choose,
    story,
)
from vultron.demo.helpers.sync import run_sync_verification_phase
from vultron.demo.utils import DataLayerClient, demo_check, demo_step
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)

#: This pair's names for the family's Coordinator and Vendor, and for its own
#: second Coordinator.  C1 receives the report and starts as CASE_OWNER; C2 is
#: the character actor it invites; the Vendor joins last, by whichever route
#: the owner's decision takes.  ``c1``, ``c2`` and ``vendor`` stay their names
#: on the command line, in ``ROLES`` and as the devlogs directories the
#: invariant harness loads (:data:`DEVLOG_REPLICAS`).
C1 = COORDINATOR
C1_LABEL = "C1"
C2 = "c2"
C2_LABEL = "C2"

#: C1's own name on the command line, in ``ROLES`` and as its devlogs
#: directory.  Its cast name is the family's :data:`COORDINATOR`, which is how
#: one copy of the shared opening serves ``rcv`` and this pair alike, so the
#: two names are both needed and neither may be a literal in two places.
C1_ROLE = "c1"

#: The parts the shared continuations of ``owner-keep-case`` act on
#: (:mod:`vultron.demo.helpers.owner_decision_story`).
C1_PART = Part(C1, C1_LABEL)
C2_PART = Part(C2, C2_LABEL)
VENDOR_PART = Part(VENDOR, VENDOR_LABEL)

#: The devlogs directory each replica's ledger is dumped under: the name this
#: pair's invariant harnesses load, which follows the RVCV convention rather
#: than the part each actor plays — ``vendor`` is C1 on cast slot 2,
#: ``coordinator`` is C2 on slot 3, and ``vendor2`` is the Vendor on slot 1
#: (``test/ci/invariants/test_rccv_extension_invariants.py``).
DEVLOG_REPLICAS: tuple[tuple[str, str], ...] = (
    ("reporter", REPORTER),
    ("vendor", C1),
    ("coordinator", C2),
    ("vendor2", VENDOR),
)

#: The case C2 has joined, as its id.  Read by whichever continuation the
#: owner's decision takes: both presuppose C2 being an active participant —
#: the extension has it suggest the Vendor (DEMOMA-13-003), the handoff
#: transfers ownership to it (DEMOMA-14-010) — so a join that never landed
#: stops the story there rather than suggesting or offering into a case C2 is
#: not in (DEMOCI-01-011).
SECOND_COORDINATOR_JOINED: StoryProp[str] = StoryProp(
    "case the second Coordinator joined", str
)


def two_coordinator_roles(*, case_actor: ActorRole) -> list[ActorRole]:
    """This pair's four actor containers, in ``ROLES`` order, plus *case_actor*.

    One list for both scenarios, because the CLI options and the devlogs
    directories they generate are the same four (DEMOCI-11-011); the CaseActor
    role is the caller's, because only ``rccv-handoff`` exposes a
    ``--case-actor-id`` option (DEMOMA-14-008).

    Args:
        case_actor: The scenario's :func:`~vultron.demo.helpers.actor_roles\
            .case_actor_role`, appended last.
    """
    return [
        ActorRole(REPORTER, REPORTER_SLOT, REPORTER_LABEL, has_id=True),
        ActorRole(C1_ROLE, COORDINATOR_SLOT, "C1 (Coordinator1)", has_id=True),
        ActorRole(C2, CAST[3], "C2 (Coordinator2)", has_id=True),
        ActorRole(VENDOR, VENDOR_SLOT, VENDOR_LABEL, has_id=True),
        case_actor,
    ]


def two_coordinator_cast_members(
    *,
    reporter_url: str | None = None,
    c1_url: str | None = None,
    c2_url: str | None = None,
    vendor_url: str | None = None,
) -> list[CastContainer]:
    """The four containers both scenarios of this pair drive.

    The same four lines in both ``main()`` functions otherwise, which is how a
    cast drifts (DEMOMA-17-001).  Each URL falls back to the cast slot's own
    address (DEMOCI-11-020).
    """
    return [
        CastContainer(REPORTER, REPORTER_LABEL, reporter_url),
        CastContainer(C1_ROLE, C1_LABEL, c1_url),
        CastContainer(C2, C2_LABEL, c2_url),
        CastContainer(VENDOR, VENDOR_LABEL, vendor_url),
    ]


def unseated_second_coordinator(
    c2_client: DataLayerClient, c2_id: str | None
) -> Mapping[str, UnseatedContainer]:
    """C2's container, reset with the rest and seeded by :func:`c2_is_seeded`."""
    return {C2: UnseatedContainer(C2_LABEL, c2_client, c2_id)}


def dump_two_coordinator_ledgers(state: StoryState) -> None:
    """Dump each participant's case ledger, by its devlogs name.

    Thin wrapper (DEMOMA-23-002): the harness runs it on the way out, whether
    or not an earlier step failed.  C2 before it is seated has no replica to
    read, so it is left out rather than 404ing the dump.
    """
    dump_coordinated_ledgers(
        state,
        replicas=[
            entry for entry in DEVLOG_REPLICAS if entry[1] in state.cast
        ],
    )


# ---------------------------------------------------------------------------
# The shared opening, up to the owner's decision
# ---------------------------------------------------------------------------


def c2_is_seeded(state: StoryState) -> None:
    """Seed and seat C2, this pair's one character actor.

    ``seed_containers_rccv`` creates C2 and registers every actor as a peer of
    the other three (DEMOMA-13-001, DEMOMA-14-001); the three the shared
    opening already seeded come back unchanged, because ``POST /actors/`` and
    ``POST /actors/{id}/peers/`` are idempotent.  Running it here rather than
    in the opening is what lets this pair's recordings match ``rcv``'s byte
    for byte up to the Coordinator's decision (DEMOCI-11-018, #5532).
    """
    c2_container = state.container(C2)
    with demo_step("Seeding the C2 container with an actor record"):
        seeded = seed_containers_rccv(
            reporter_client=state.client(REPORTER),
            c1_client=state.client(C1),
            c2_client=c2_container.client,
            vendor_client=state.client(VENDOR),
            reporter_actor_id=state.actor_id(REPORTER),
            c1_actor_id=state.actor_id(C1),
            c2_actor_id=c2_container.actor_id,
            vendor_actor_id=state.actor_id(VENDOR),
            case_actor_client=state.case_actor_client,
        )
        # Seated inside the step that seeded it, and only once it reads back:
        # the invite below names C2 by actor id (#2308, EDF-06-005).
        seat_character_actors(state, {C2: seeded[2].id_})


def c1_invites_c2(state: StoryState) -> None:
    """C1 invites C2 with ``CVDRole.COORDINATOR``; C2 accepts and joins.

    C2 holds ``CVDRole.COORDINATOR`` and **not** ``CVDRole.CASE_MANAGER``,
    which stays with the CaseActor (DEMOMA-13-003).  It runs no RM triage: it
    joins to help coordinate, not to judge the report, so it engages no case
    of its own (CM-11-002 applies to the invitee that answers over a report it
    must triage) and giving it one would put an ``engage_case`` act in the
    ledger neither scenario's semantic-type list claims (DEMOMA-17-002).

    The roster is this join's gate and keeps
    :data:`SECOND_COORDINATOR_JOINED`, because the owner's decision — either
    one — presupposes C2 being a participant (DEMOMA-13-003, DEMOMA-14-010).
    """
    invitee_joins_the_case(
        state,
        C2,
        C2_LABEL,
        role=CVDRole.COORDINATOR,
        seated=(REPORTER, C1, C2),
        triages=False,
        joined=SECOND_COORDINATOR_JOINED,
        join_timeout=OWNER_DECISION_TIMEOUT,
        cross_container_timeout=OWNER_DECISION_TIMEOUT,
    )


#: Everything both scenarios of the pair tell before the owner decides: the
#: rcv family's opening, the Coordinator's choice to invite a Coordinator, and
#: C2 being seeded, invited and joined.  Named rather than assembled from the
#: fragments at each call site, because assembling siblings from fragments
#: alone lets one of them slip a step in before the branch point
#: (``notes/demo-scenario-tree.md`` § "Composition").
C1_INVITES_C2 = story(
    REPORTER_TELLS_THE_COORDINATOR,
    choose("coordinator-invite-whom", "coordinator", by=COORDINATOR),
    c2_is_seeded,
    c1_invites_c2,
)


# ---------------------------------------------------------------------------
# Continuations both scenarios tell, whichever way the owner decided
# ---------------------------------------------------------------------------


def required_participants_are_present(state: StoryState) -> None:
    """The case holds every participant invited so far, and is still embargoed.

    Read from C1's replica, which holds the case from the moment it engaged it
    whether or not it is still the owner.
    """
    with demo_check(
        "M1: required participants, EM.ACTIVE, Reporter + C2 have replicas"
    ):
        verify_case_active(
            receiver_client=state.client(C1),
            reporter_client=state.client(REPORTER),
            case_id=state.case.id_,
            receiver_actor_id=state.actor_id(C1),
            reporter_actor_id=state.actor_id(REPORTER),
        )


def every_replica_converges(state: StoryState) -> None:
    """Verify LedgerFanout replication for the Reporter, C2 and Vendor replicas.

    Thin call to the shared sync helper (DEMOMA-23-007), naming only this
    pair's authority, replicas and late joiner.  C1 is the authority in both
    scenarios: it holds the case from its own triage onward, so its replica is
    complete whether or not the ownership moved (DEMOMA-13-007, DEMOMA-14-006).
    """
    run_sync_verification_phase(
        auth_client=state.client(C1),
        auth_label=C1_LABEL,
        auth_actor_id=state.actor_id(C1),
        reporter_client=state.client(REPORTER),
        reporter_actor_id=state.actor_id(REPORTER),
        replicas=[
            (state.client(REPORTER), REPORTER_LABEL),
            (state.client(C2), C2_LABEL),
            (state.client(VENDOR), VENDOR_LABEL),
        ],
        case_id=state.case.id_,
        expected_participant_ids={
            state.actor_id(who) for who in (REPORTER, C1, C2, VENDOR)
        },
        # The Vendor joins by invitation after the early replicas exist
        # (#2202) and catches up from genesis.
        late_joiners=(state.client(VENDOR),),
        state_checks=[
            (state.client(REPORTER), REPORTER_LABEL),
            (state.client(VENDOR), VENDOR_LABEL),
        ],
    )
    logger.info("✓ All four replicas synchronized (LedgerFanout verified)")


def four_way_note_thread(
    state: StoryState, updates: Sequence[NotePost]
) -> None:
    """The Reporter asks about a workaround, C1 answers, then *updates* reply.

    One thread, posted through C1's replica, which both scenarios watch.  The
    Reporter's question and C1's answer are the same in both; what C2 and the
    Vendor add differs with who owns the case by then, so each scenario passes
    its own two posts.

    Args:
        state: The running story's state.
        updates: The posts that follow C1's answer, in order.
    """
    add_note_thread(
        state.client(C1),
        state.case,
        [
            NotePost(
                state.actor(REPORTER),
                "Question from Reporter",
                WORKAROUND_QUESTION,
            ),
            NotePost(
                state.actor(C1), f"{C1_LABEL} Response", WORKAROUND_ANSWER
            ),
            *updates,
        ],
    )
    logger.info(
        "✓ Notes exchange complete (four notes committed to case ledger)"
    )


def all_four_publish(state: StoryState, *, owner: Part, other: Part) -> None:
    """Each participant reports public disclosure, the Case Owner first.

    Per DEMOMA-07-003(4) the Case Owner triggers CS.P, which is C1 in the
    extension and C2 after the handoff; the embargo reads ``EM.EXITED`` once
    it has (DEMOMA-13-006, DEMOMA-14-014).  Then the Vendor, the other
    Coordinator and the Reporter report, the Reporter last and only once the
    termination has reached its own replica.

    Args:
        state: The running story's state.
        owner: The Case Owner as of this step.
        other: The Coordinator that is not the owner.
    """
    reports_published(state, owner.name)

    # Read on C1's replica in both scenarios: it is a participant throughout
    # and holds the case from its own triage, so one copy of this step serves
    # the owner it kept and the owner it handed over to.
    with demo_check(
        f"Embargo terminated (EM.EXITED) after {owner.label} reports published"
    ):
        wait_for_case_em_terminated(
            client=state.client(C1), case_id=state.case.id_
        )

    reports_published(state, VENDOR)
    reports_published(state, other.name)

    with demo_check(
        "Embargo terminated (EM.EXITED) propagated to Reporter before"
        " notify-published"
    ):
        wait_for_case_em_terminated(
            client=state.client(REPORTER), case_id=state.case.id_
        )

    reports_published(state, REPORTER)

    with demo_check(
        "M7: all replicas CS.VFdPxa, EM.EXITED, all participants public-aware"
    ):
        wait_for_case_em_terminated(
            client=state.client(REPORTER), case_id=state.case.id_
        )
        for watcher in (C1, REPORTER):
            wait_for_participant_vf_state(
                client=state.client(watcher),
                case_id=state.case.id_,
                actor_id=state.actor_id(VENDOR),
                expected_states={CS_vf.VF},
            )
        verify_publicly_disclosed(
            receiver_client=state.client(C1),
            reporter_client=state.client(REPORTER),
            case_id=state.case.id_,
            receiver_actor_id=state.actor_id(VENDOR),
        )


__all__ = [
    "C1",
    "C1_INVITES_C2",
    "C1_LABEL",
    "C1_PART",
    "C1_ROLE",
    "C2",
    "C2_LABEL",
    "C2_PART",
    "DEVLOG_REPLICAS",
    "SECOND_COORDINATOR_JOINED",
    "VENDOR_PART",
    "all_four_publish",
    "c1_invites_c2",
    "c2_is_seeded",
    "dump_two_coordinator_ledgers",
    "every_replica_converges",
    "four_way_note_thread",
    "required_participants_are_present",
    "two_coordinator_cast_members",
    "two_coordinator_roles",
    "unseated_second_coordinator",
]
