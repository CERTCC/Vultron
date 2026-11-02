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
"""Story fragments of the ``rvcv`` pair, ``rvcv-extension``/``rvcv-handoff``.

Both scenarios tell one story up to a single decision: the Reporter tells
Vendor1, Vendor1 engages the case and answers the Reporter's question, and
then invites a **Coordinator**, which joins — and Vendor1, the Case Owner,
decides whether to keep the case.  Keep it and the Coordinator's suggestion
brings Vendor2 in (``rvcv-extension``, DEMOMA-10); hand it over and the new
owner invites Vendor2 itself (``rvcv-handoff``, DEMOMA-11).  Everything before
that decision is :data:`THE_VENDOR_INVITES_A_COORDINATOR`, written here once,
and everything after it that both tell is written here once too
(DEMOMA-17-001, DEMOCI-11-018).

The opening up to Vendor1's own decision is the **vendor-first family's**
(:data:`~vultron.demo.helpers.vendor_story.THE_VENDOR_ANSWERS_THE_REPORTER`):
this pair parts from ``rv`` and ``rvv`` at ``vendor-after-answer``, where they
report the fix ready or invite a second Vendor and this pair invites a
Coordinator.  So all four vendor-first scenarios share one copy of the report
submission, the Vendor's triage and the note thread, and their recordings
agree byte for byte up to that branch point.

The Coordinator and Vendor2 are both brought in after the branch point, so
neither is seeded by the shared opening: their containers are reset with the
rest and their actors are seeded by :func:`the_coordinator_and_vendor2_are_seeded`,
because every actor and peer record written before the case exists is one more
read of the recording clock and would move the first ledger entry away from
the siblings this opening must match (DEMOCI-11-018, #5532).

The two continuations of the owner's decision are **not** here: that decision
appears in the coordinator-first half too, so both of its continuations live
in :mod:`vultron.demo.helpers.owner_decision_story` and this module only names
the parts each plays (:data:`COORDINATOR_PART`, and
:data:`~vultron.demo.helpers.vendor_story.VENDOR_PART` and
:data:`~vultron.demo.helpers.vendor_story.VENDOR2_PART`).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

from vultron.demo.helpers.coordinated_story import (
    COORDINATOR,
    COORDINATOR_LABEL,
    REPORTER,
    REPORTER_LABEL,
    CastContainer,
    invitee_joins_the_case,
    seat_character_actors,
)
from vultron.demo.helpers.owner_decision_story import Part
from vultron.demo.helpers.seeding import seed_containers_rvcv
from vultron.demo.helpers.story import (
    StoryProp,
    StoryState,
    UnseatedContainer,
    choose,
    story,
)
from vultron.demo.helpers.sync import run_sync_verification_phase
from vultron.demo.helpers.vendor_story import (
    JOIN_TIMEOUT,
    THE_VENDOR_ANSWERS_THE_REPORTER,
    VENDOR,
    VENDOR2,
    VENDOR2_LABEL,
    VENDOR_LABEL,
    dump_vendor_ledgers,
)
from vultron.demo.utils import DataLayerClient, demo_step
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)

#: The part the shared continuations of ``owner-keep-case`` act on: the
#: Coordinator, which suggests Vendor2 in the extension and takes the case
#: over in the handoff.  Its cast name and label are the rcv family's, so one
#: copy of every fragment that reads a Coordinator serves both halves of the
#: tree.
COORDINATOR_PART = Part(COORDINATOR, COORDINATOR_LABEL)

#: The devlogs directory each replica's ledger is dumped under, in dump order.
#: Every actor of this pair is named the same on the command line, in ``ROLES``
#: and in its devlogs, so one cast name serves all three (DEMOMA-19-018).
DEVLOG_REPLICAS: tuple[str, ...] = (REPORTER, VENDOR, COORDINATOR, VENDOR2)

#: The case the Coordinator has joined, as its id.  Read by whichever
#: continuation the owner's decision takes: both presuppose the Coordinator
#: being an active participant — the extension has it suggest Vendor2
#: (DEMOMA-10-004), the handoff transfers ownership to it (CM-21-021) — so a
#: join that never landed stops the story there rather than suggesting or
#: offering into a case the Coordinator is not in (DEMOCI-01-011).
COORDINATOR_JOINED: StoryProp[str] = StoryProp(
    "case the Coordinator joined", str
)


def vendor_coordinator_cast_members(
    *,
    reporter_url: str | None = None,
    vendor_url: str | None = None,
    coordinator_url: str | None = None,
    vendor2_url: str | None = None,
) -> list[CastContainer]:
    """The four containers both scenarios of this pair drive.

    The same four lines in both ``main()`` functions otherwise, which is how a
    cast drifts (DEMOMA-17-001).  Each URL falls back to the cast slot's own
    address (DEMOCI-11-020).
    """
    return [
        CastContainer(REPORTER, REPORTER_LABEL, reporter_url),
        CastContainer(VENDOR, VENDOR_LABEL, vendor_url),
        CastContainer(COORDINATOR, COORDINATOR_LABEL, coordinator_url),
        CastContainer(VENDOR2, VENDOR2_LABEL, vendor2_url),
    ]


def unseated_coordinator_and_vendor2(
    *,
    coordinator_client: DataLayerClient,
    coordinator_id: str | None,
    vendor2_client: DataLayerClient,
    vendor2_id: str | None,
) -> Mapping[str, UnseatedContainer]:
    """The two containers reset with the rest and seeded after the decision.

    Neither actor takes any part until Vendor1 has decided to invite a
    Coordinator, so neither is seeded by the shared opening
    (:func:`the_coordinator_and_vendor2_are_seeded`, DEMOCI-11-018).
    """
    return {
        COORDINATOR: UnseatedContainer(
            COORDINATOR_LABEL, coordinator_client, coordinator_id
        ),
        VENDOR2: UnseatedContainer(VENDOR2_LABEL, vendor2_client, vendor2_id),
    }


# ---------------------------------------------------------------------------
# The shared opening, up to the owner's decision
# ---------------------------------------------------------------------------


def the_coordinator_and_vendor2_are_seeded(state: StoryState) -> None:
    """Seed and seat the Coordinator and Vendor2.

    ``seed_containers_rvcv`` creates both and registers every actor as a peer
    of the other three (DEMOMA-10-001, DEMOMA-11-001); the two the shared
    opening already seeded come back unchanged, because ``POST /actors/`` and
    ``POST /actors/{id}/peers/`` are idempotent.  Running it here rather than
    in the opening is what lets this pair's recordings match ``rv``'s and
    ``rvv``'s byte for byte up to Vendor1's decision (DEMOCI-11-018, #5532).

    Vendor2 is seated here with the Coordinator although it joins later: the
    extension's suggestion names it by actor id before it has joined anything
    (DEMOMA-10-004), and the handoff's invite needs its session too.
    """
    coordinator_container = state.container(COORDINATOR)
    vendor2_container = state.container(VENDOR2)
    with demo_step(
        "Seeding the Coordinator and Vendor2 containers with actor records"
    ):
        seeded = seed_containers_rvcv(
            reporter_client=state.client(REPORTER),
            vendor_client=state.client(VENDOR),
            coordinator_client=coordinator_container.client,
            vendor2_client=vendor2_container.client,
            reporter_actor_id=state.actor_id(REPORTER),
            vendor_actor_id=state.actor_id(VENDOR),
            coordinator_actor_id=coordinator_container.actor_id,
            vendor2_actor_id=vendor2_container.actor_id,
            case_actor_client=state.case_actor_client,
        )
        # Seated inside the step that seeded them, and neither seated until
        # both read back: a partly seated cast would let the Coordinator's
        # invite run before Vendor2's absence stopped the story
        # (#2308, EDF-06-005).
        seat_character_actors(
            state, {COORDINATOR: seeded[2].id_, VENDOR2: seeded[3].id_}
        )


def the_vendor_invites_the_coordinator(state: StoryState) -> None:
    """Vendor1 invites the Coordinator with ``CVDRole.COORDINATOR``.

    The Coordinator holds ``CVDRole.COORDINATOR`` and **not**
    ``CVDRole.CASE_MANAGER``, which stays with the CaseActor (DEMOMA-10-003).
    It runs no RM triage: it joins to help coordinate, not to judge the
    report, so it engages no case of its own (CM-11-002 applies to the invitee
    that answers over a report it must triage) and giving it one would put an
    ``engage_case`` act in the ledger neither scenario's semantic-type list
    claims (DEMOMA-17-002).

    The roster is this join's gate and keeps :data:`COORDINATOR_JOINED`,
    because the owner's decision — either one — presupposes the Coordinator
    being a participant (DEMOMA-10-004, CM-21-021).
    """
    invitee_joins_the_case(
        state,
        COORDINATOR,
        COORDINATOR_LABEL,
        role=CVDRole.COORDINATOR,
        seated=(REPORTER, VENDOR, COORDINATOR),
        triages=False,
        joined=COORDINATOR_JOINED,
        inviter=VENDOR,
        inviter_label=VENDOR_LABEL,
        join_timeout=JOIN_TIMEOUT,
        cross_container_timeout=JOIN_TIMEOUT,
    )


#: Everything both scenarios of the pair tell before the owner decides: the
#: vendor-first family's opening, Vendor1's choice to invite a Coordinator,
#: and the Coordinator and Vendor2 being seeded with the Coordinator invited
#: and joined.  Named rather than assembled from the fragments at each call
#: site, because assembling siblings from fragments alone lets one of them
#: slip a step in before the branch point (``notes/demo-scenario-tree.md``
#: § "Composition").
THE_VENDOR_INVITES_A_COORDINATOR = story(
    THE_VENDOR_ANSWERS_THE_REPORTER,
    choose("vendor-after-answer", "invite-coordinator", by=VENDOR),
    the_coordinator_and_vendor2_are_seeded,
    the_vendor_invites_the_coordinator,
)


# ---------------------------------------------------------------------------
# Continuations both scenarios tell, whichever way the owner decided
# ---------------------------------------------------------------------------


def dump_vendor_coordinator_ledgers(state: StoryState) -> None:
    """Dump each participant's case ledger, by its devlogs name.

    Thin wrapper (DEMOMA-23-002): the harness runs it on the way out, whether
    or not an earlier step failed.  Both scenarios of the pair dump the same
    four replicas in the same order, so it is written here once rather than
    twice (DEMOMA-17-001); an actor the run never seated has no replica to
    read, which :func:`~vultron.demo.helpers.vendor_story\
    .dump_vendor_ledgers` drops rather than 404ing the dump.
    """
    dump_vendor_ledgers(state, DEVLOG_REPLICAS)


def every_replica_converges(state: StoryState) -> None:
    """Verify LedgerFanout replication for the Reporter, Coordinator and Vendor2.

    Thin call to the shared sync helper (DEMOMA-23-007), naming only this
    pair's authority, replicas and late joiner.  Vendor1 is the authority in
    both scenarios: it holds the case from its own triage onward, so its
    replica is complete whether or not the ownership moved (DEMOMA-10-007,
    DEMOMA-11-007).
    """
    run_sync_verification_phase(
        auth_client=state.client(VENDOR),
        auth_label=VENDOR_LABEL,
        auth_actor_id=state.actor_id(VENDOR),
        reporter_client=state.client(REPORTER),
        reporter_actor_id=state.actor_id(REPORTER),
        replicas=[
            (state.client(REPORTER), REPORTER_LABEL),
            (state.client(COORDINATOR), COORDINATOR_LABEL),
            (state.client(VENDOR2), VENDOR2_LABEL),
        ],
        case_id=state.case.id_,
        expected_participant_ids={
            state.actor_id(who)
            for who in (REPORTER, VENDOR, COORDINATOR, VENDOR2)
        },
        # Vendor2 joins by invitation after the early replicas exist (#2202)
        # and catches up from genesis.
        late_joiners=(state.client(VENDOR2),),
        state_checks=[
            (state.client(REPORTER), REPORTER_LABEL),
            (state.client(VENDOR2), VENDOR2_LABEL),
        ],
    )
    logger.info("✓ All four replicas synchronized (LedgerFanout verified)")


__all__ = [
    "COORDINATOR_JOINED",
    "COORDINATOR_PART",
    "DEVLOG_REPLICAS",
    "THE_VENDOR_INVITES_A_COORDINATOR",
    "dump_vendor_coordinator_ledgers",
    "every_replica_converges",
    "the_coordinator_and_vendor2_are_seeded",
    "the_vendor_invites_the_coordinator",
    "unseated_coordinator_and_vendor2",
    "vendor_coordinator_cast_members",
]
