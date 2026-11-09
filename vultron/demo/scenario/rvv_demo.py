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

"""Reporter → Vendor1 → Vendor2 (RVV) three-actor CVD workflow demo.

Three actor containers plus a dedicated CaseActor, and no Coordinator:

- Reporter: the report submitter, seated when the case is created
  (CP-09-002);
- Vendor1 (cast slot 1, the first Vendor): CASE_OWNER throughout, which
  invites Vendor2 directly (DEMOMA-09-002);
- Vendor2 (cast slot 3, a character actor): a second Vendor with a fix path
  of its own (DEMOMA-09-003);
- CaseActor (case-actor container): holds the canonical case and ledger
  (DEMOMA-09-006).

Cast (DEMOCI-11-020): every scenario runs the same containers, so a role's
address and actor id are the same here as in its siblings.  ``ROLES`` below
seats each actor; the cast table is ``vultron/demo/helpers/cast.py``.

The story is assembled, not written out: it starts with
:data:`~vultron.demo.helpers.vendor_story.THE_VENDOR_ANSWERS_THE_REPORTER`,
the opening it shares with ``rv`` and the ``rvcv`` pair, and continues with
Vendor1 inviting a second Vendor (:data:`STORY`, DEMOCI-11-019).  That shared
opening is why this scenario's ledger and its siblings' agree byte for byte up
to Vendor1's decision (DEMOCI-11-018).

Spec: DEMOMA-09 (D5-5, GitHub issue #1265).
"""

import logging

from vultron.demo.helpers.actor_roles import (
    ActorRole,
    case_actor_role,
    resolved_actor_ids,
    role_map,
)
from vultron.demo.helpers.cast import CAST, REPORTER_SLOT, VENDOR_SLOT
from vultron.demo.helpers.coordinated_story import (
    REPORTER,
    REPORTER_LABEL,
    close_the_case,
    invitee_joins_the_case,
    reports_published,
    seat_character_actors,
)
from vultron.demo.helpers.notes import NotePost
from vultron.demo.helpers.seeding import seed_containers_rvv
from vultron.demo.helpers.story import (
    StoryState,
    UnseatedContainer,
    choose,
    run_story,
    story,
)
from vultron.demo.helpers.story_cast import (
    CASE_ACTOR_NAME,
    CastContainer,
    story_clients,
)
from vultron.demo.helpers.sync import run_sync_verification_phase
from vultron.demo.helpers.vendor_story import (
    JOIN_TIMEOUT,
    THE_VENDOR_ANSWERS_THE_REPORTER,
    VENDOR,
    VENDOR2,
    VENDOR2_LABEL,
    VENDOR_LABEL,
    both_vendors_report_the_fix_ready,
    dump_vendor_ledgers,
    required_participants_are_present,
    the_disclosure_reached_every_replica,
    the_embargo_ends_for,
    the_joiners_add_their_notes,
    vendor_open_cast,
)
from vultron.demo.scenario.registry import scenario
from vultron.demo.utils import DataLayerClient, demo_step, setup_demo_logging
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)

DEMO_NAME = "rvv"

# The scenario's actors in main() parameter order, each seated in a container of
# the fixed cast (DEMOCI-11-020).  The demo CLI derives this scenario's
# sub-command options from this list (DEMOCI-11-011).
ROLES: list[ActorRole] = [
    ActorRole(REPORTER, REPORTER_SLOT, REPORTER_LABEL, has_id=True),
    ActorRole(VENDOR, VENDOR_SLOT, VENDOR_LABEL, has_id=True),
    ActorRole(VENDOR2, CAST[3], VENDOR2_LABEL, has_id=True),
    case_actor_role(),
]
#: Indexed for the CLI factory and for ``story_clients()``, which reads
#: each actor's container address off its cast slot — so this module declares
#: no ``*_BASE_URL`` constant of its own (DEMOCI-11-020).
_ROLES = role_map(ROLES)

#: ``vultron-demo rvv --help`` text. Lives here rather than in ``cli.py``
#: because the sub-command is generated from the registry and the scenario
#: module is the only place that knows what its own workflow does.
CLI_HELP = """Run the RVV (Reporter + Vendor1 + Vendor2) multi-container CVD demo (D5-5).

Orchestrates a complete CVD workflow across three separate API server
containers with no coordinator.  Vendor1 creates the case, which seats the
Reporter, and invites Vendor2; each vendor maintains an independent
fix path.

\b
Workflow:
  1. Seed the Reporter and Vendor1 containers (actor records + peer
     registration); Reporter submits a vulnerability report to Vendor1's
     inbox.
  2. Vendor1 validates the report and engages the case.
  3. Reporter asks about a workaround and Vendor1 answers.
  4. Vendor2's container is seeded and Vendor1 invites Vendor2; Vendor2
     accepts and runs its RM triage.
  5. Verify LedgerFanout replication on Reporter and Vendor2.
  6. Both vendors independently advance to fix-ready (VFd).
  7. All participants report publication; embargo terminates.
  8. All participants close the case; the case ledgers are dumped.
"""


# ---------------------------------------------------------------------------
# Fragments this scenario alone tells
# ---------------------------------------------------------------------------


def the_second_vendor_is_seeded(state: StoryState) -> None:
    """Seed and seat Vendor2, this scenario's one character actor.

    ``seed_containers_rvv`` creates Vendor2 and registers every actor as a
    peer of the other two (DEMOMA-09-001); the two the shared opening already
    seeded come back unchanged, because ``POST /actors/`` and
    ``POST /actors/{id}/peers/`` are idempotent.  Running it here rather than
    in the opening is what lets this scenario's recording match ``rv``'s byte
    for byte up to Vendor1's decision (DEMOCI-11-018, #5532).
    """
    vendor2_container = state.container(VENDOR2)
    with demo_step("Seeding the Vendor2 container with an actor record"):
        seeded = seed_containers_rvv(
            reporter_client=state.client(REPORTER),
            vendor_client=state.client(VENDOR),
            vendor2_client=vendor2_container.client,
            reporter_actor_id=state.actor_id(REPORTER),
            vendor_actor_id=state.actor_id(VENDOR),
            vendor2_actor_id=vendor2_container.actor_id,
            case_actor_client=state.case_actor_client,
        )
        # Seated inside the step that seeded it, and only once it reads back:
        # the invite below names Vendor2 by actor id (#2308, EDF-06-005).
        seat_character_actors(state, {VENDOR2: seeded[2].id_})


def vendor1_invites_the_second_vendor(state: StoryState) -> None:
    """Vendor1 invites Vendor2 as a second Vendor; Vendor2 joins.

    Vendor1 is CASE_OWNER, so it invites directly rather than through the
    ADR-0026 suggest/approve chain (DEMOMA-09-002).  Vendor2 joined by
    accepting, so it runs its own RM triage over the report it was invited
    over (CM-11-002).

    ``milestone=None``: this scenario numbers no milestone for the join.  M2
    is its replica synchronization (:func:`every_replica_converges`,
    ``docs/howto/demos/rvv-demo.md``), and the shared step's default would
    log a second ``✓ M2:`` line here that the page's marker table could not
    tell from it.
    """
    invitee_joins_the_case(
        state,
        VENDOR2,
        VENDOR2_LABEL,
        role=CVDRole.VENDOR,
        seated=(REPORTER, VENDOR, VENDOR2),
        inviter=VENDOR,
        inviter_label=VENDOR_LABEL,
        milestone=None,
        join_timeout=JOIN_TIMEOUT,
        cross_container_timeout=JOIN_TIMEOUT,
    )


def the_case_is_active(state: StoryState) -> None:
    """M1: all four participants are seated and the embargo is active."""
    required_participants_are_present(
        state,
        check=(
            "M1: required participants (≥4), EM.ACTIVE, reporter + vendor2"
            " have replicas"
        ),
    )


def every_replica_converges(state: StoryState) -> None:
    """M2: Ledger Fanout reaches the Reporter and Vendor2.

    Thin call to the shared sync helper (DEMOMA-23-007), naming only this
    scenario's authority, replicas and late joiner (DEMOMA-09-004).
    """
    run_sync_verification_phase(
        auth_client=state.client(VENDOR),
        auth_label=VENDOR_LABEL,
        auth_actor_id=state.actor_id(VENDOR),
        reporter_client=state.client(REPORTER),
        reporter_actor_id=state.actor_id(REPORTER),
        replicas=[
            (state.client(REPORTER), REPORTER_LABEL),
            (state.client(VENDOR2), VENDOR2_LABEL),
        ],
        case_id=state.case.id_,
        expected_participant_ids={
            state.actor_id(who) for who in (REPORTER, VENDOR, VENDOR2)
        },
        # Vendor2 joins by invitation after the report is accepted (#2852).
        late_joiners=(state.client(VENDOR2),),
        state_checks=[
            (state.client(REPORTER), REPORTER_LABEL),
            (state.client(VENDOR2), VENDOR2_LABEL),
        ],
    )
    logger.info(
        "✓ M2: Reporter and Vendor2 DataLayers synchronized (LedgerFanout"
        " verified)"
    )


def the_second_vendor_adds_its_note(state: StoryState) -> None:
    """Vendor2, once joined, answers the thread the opening posted."""
    the_joiners_add_their_notes(
        state,
        [
            NotePost(
                state.actor(VENDOR2),
                f"{VENDOR2_LABEL} Status Update",
                "Vendor2 can confirm the issue affects our component. "
                "We will coordinate our fix timeline with Vendor1.",
            )
        ],
    )


def both_vendors_fix_the_vul(state: StoryState) -> None:
    """Both vendors report fix ready; both stop at VFd (CSB-15-002)."""
    both_vendors_report_the_fix_ready(
        state,
        milestones=(
            "M4: Reporter replica shows both vendors CS include F (fix ready)",
            "M5: Reporter replica shows both vendors CS include F (fix ready)"
            " — vendors stop at VFd",
        ),
    )


def everyone_publishes(state: StoryState) -> None:
    """Vendor1, the Case Owner, publishes first; then Vendor2 and the Reporter."""
    reports_published(state, VENDOR)
    the_embargo_ends_for(
        state,
        check=(
            f"Embargo terminated (EM.EXITED) after {VENDOR_LABEL} reports"
            " published"
        ),
        watcher=VENDOR,
    )
    reports_published(state, VENDOR2)
    reports_published(state, REPORTER)
    the_disclosure_reached_every_replica(
        state,
        check=(
            "M6: all replicas CS.VFdPxa, EM.EXITED, all participants"
            " public-aware"
        ),
    )


def everyone_closes(state: StoryState) -> None:
    """Vendor2 and the Reporter leave; Vendor1, the Case Owner, leaves last."""
    close_the_case(
        state, others=(VENDOR2, REPORTER), owner=VENDOR, milestone="M7"
    )


def _dump_ledgers(state: StoryState) -> None:
    """Dump each participant's case ledger, by its devlogs name.

    Thin wrapper (DEMOMA-23-002): the harness runs it on the way out, whether
    or not an earlier step failed.  Vendor2 before it is seated has no replica
    to read, so it is left out rather than 404ing the dump.
    """
    dump_vendor_ledgers(state, (REPORTER, VENDOR, VENDOR2))


#: The RVV story: the opening it shares with ``rv`` and the ``rvcv`` pair,
#: then Vendor1 inviting a second Vendor and the three-party lifecycle to
#: closure.  The registry reads this scenario's path off the ``choose`` items
#: (DEMOCI-11-019), so it declares no ``path=``.
STORY = story(
    THE_VENDOR_ANSWERS_THE_REPORTER,
    # Vendor1 decides once it has answered the Reporter's question.
    choose("vendor-after-answer", "invite-vendor", by=VENDOR),
    the_second_vendor_is_seeded,
    vendor1_invites_the_second_vendor,
    the_case_is_active,
    every_replica_converges,
    the_second_vendor_adds_its_note,
    both_vendors_fix_the_vul,
    everyone_publishes,
    everyone_closes,
)


def run_rvv_demo(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    reporter_id: str | None = None,
    vendor_id: str | None = None,
    vendor2_id: str | None = None,
) -> None:
    """Orchestrate the RVV (Reporter + Vendor1 + Vendor2) CVD workflow."""
    logger.info("=" * 80)
    logger.info("RVV DEMO: Reporter → Vendor1 → Vendor2 CVD Workflow (VFDPxa)")
    logger.info("=" * 80)
    logger.info("Reporter container:  %s", reporter_client.base_url)
    logger.info("Vendor1 container: %s", vendor_client.base_url)
    logger.info("Vendor2 container: %s", vendor2_client.base_url)
    logger.info("CaseActor container: %s", case_actor_client.base_url)

    open_cast = vendor_open_cast(
        reporter_client=reporter_client,
        vendor_client=vendor_client,
        case_actor_client=case_actor_client,
        dump=_dump_ledgers,
        reporter_id=reporter_id,
        vendor_id=vendor_id,
        unseated={
            VENDOR2: UnseatedContainer(
                VENDOR2_LABEL, vendor2_client, vendor2_id
            )
        },
    )

    # run_story() owns the failure accumulator through scenario_harness: it
    # resets it, always dumps the case ledgers, and asserts success — so a
    # failure here never costs us the artifacts (ISSUE-2239, DEMOMA-23-001).
    run_story(DEMO_NAME, STORY, open_cast)

    logger.info("=" * 80)
    logger.info("RVV DEMO COMPLETE ✓  (VFDPxa full lifecycle)")
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@scenario(
    name=DEMO_NAME,
    label="RVV",
    participants="Reporter + Vendor1 + Vendor2",
    feature="Direct invitation of a second vendor",
    in_pr_set=False,
    story=STORY,
)
def main(
    skip_health_check: bool = False,
    reporter_url: str | None = None,
    vendor_url: str | None = None,
    vendor2_url: str | None = None,
    case_actor_url: str | None = None,
    reporter_id: str | None = None,
    vendor_id: str | None = None,
    vendor2_id: str | None = None,
) -> None:
    """Entry point for the RVV (Reporter + Vendor1 + Vendor2) CVD workflow demo.

    Args:
        skip_health_check: Skip the server availability check (useful for
            testing).
        reporter_url: Override base URL for the Reporter container.
        vendor_url: Override base URL for the Vendor1 container.
        vendor2_url: Override base URL for the Vendor2 container.
        case_actor_url: Override base URL for the dedicated CaseActor
            container.
        reporter_id: Optional deterministic URI for the Reporter actor.
        vendor_id: Optional deterministic URI for the Vendor1 actor.
        vendor2_id: Optional deterministic URI for the Vendor2 actor.
    """
    clients = story_clients(
        _ROLES,
        [
            CastContainer(REPORTER, REPORTER_LABEL, reporter_url),
            CastContainer(VENDOR, VENDOR_LABEL, vendor_url),
            CastContainer(VENDOR2, VENDOR2_LABEL, vendor2_url),
        ],
        skip_health_check=skip_health_check,
        case_actor_url=case_actor_url,
    )
    run_rvv_demo(
        reporter_client=clients[REPORTER],
        vendor_client=clients[VENDOR],
        vendor2_client=clients[VENDOR2],
        case_actor_client=clients[CASE_ACTOR_NAME],
        **resolved_actor_ids(
            _ROLES,
            reporter=(clients[REPORTER], reporter_id),
            vendor=(clients[VENDOR], vendor_id),
            vendor2=(clients[VENDOR2], vendor2_id),
        ),
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
