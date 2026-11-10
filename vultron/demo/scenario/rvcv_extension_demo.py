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

Four actor containers plus a dedicated CaseActor:

- Reporter: the report submitter, seated when the case is created
  (CP-09-002);
- Vendor1 (cast slot 1, the first Vendor): CASE_OWNER throughout — ownership
  never moves (DEMOMA-10-002);
- Coordinator (cast slot 2): a participant holding ``CVDRole.COORDINATOR``
  and **not** ``CVDRole.CASE_MANAGER``, which suggests Vendor2 through the
  ADR-0026 suggest-actor flow (DEMOMA-10-003, DEMOMA-10-004);
- Vendor2 (cast slot 3, a character actor): joins on Vendor1's approval and
  runs a fix path of its own;
- CaseActor (case-actor container): holds the canonical case and ledger.

Cast (DEMOCI-11-020): every scenario runs the same containers, so a role's
address and actor id are the same here as in its siblings.  ``ROLES`` below
seats each actor; the cast table is ``vultron/demo/helpers/cast.py``.

The story is assembled, not written out: it starts with
:data:`~vultron.demo.helpers.vendor_coordinator_story\
.THE_VENDOR_INVITES_A_COORDINATOR`, the opening it shares with
``rvcv-handoff`` — itself continuing the vendor-first family's
``THE_VENDOR_ANSWERS_THE_REPORTER`` — and continues with Vendor1 keeping the
case (:data:`STORY`, DEMOCI-11-019).

Spec: DEMOMA-10 (D5-6, GitHub issue #1535).
"""

import logging

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
    COORDINATOR,
    COORDINATOR_LABEL,
    REPORTER,
    REPORTER_LABEL,
    close_the_case,
    reports_published,
)
from vultron.demo.helpers.notes import NotePost
from vultron.demo.helpers.owner_decision_story import (
    the_owner_approves_a_suggested_actor,
)
from vultron.demo.helpers.story import StoryState, choose, run_story, story
from vultron.demo.helpers.story_cast import CASE_ACTOR_NAME, story_clients
from vultron.demo.helpers.sync import wait_for_replica_ledger_coverage
from vultron.demo.helpers.vendor_coordinator_story import (
    COORDINATOR_JOINED,
    COORDINATOR_PART,
    THE_VENDOR_INVITES_A_COORDINATOR,
    dump_vendor_coordinator_ledgers,
    every_replica_converges,
    unseated_coordinator_and_vendor2,
    vendor_coordinator_cast_members,
)
from vultron.demo.helpers.vendor_story import (
    VENDOR,
    VENDOR2,
    VENDOR2_LABEL,
    VENDOR2_PART,
    VENDOR_LABEL,
    VENDOR_PART,
    both_vendors_report_the_fix_ready,
    required_participants_are_present,
    the_disclosure_reached_every_replica,
    the_embargo_ends_for,
    the_joiners_add_their_notes,
    vendor_open_cast,
)
from vultron.demo.scenario.registry import scenario
from vultron.demo.utils import DataLayerClient, setup_demo_logging
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)

DEMO_NAME = "rvcv-extension"

# The scenario's actors in main() parameter order, each seated in a container of
# the fixed cast (DEMOCI-11-020).  The demo CLI derives this scenario's
# sub-command options from this list (DEMOCI-11-011).
ROLES: list[ActorRole] = [
    ActorRole(REPORTER, REPORTER_SLOT, REPORTER_LABEL, has_id=True),
    ActorRole(VENDOR, VENDOR_SLOT, VENDOR_LABEL, has_id=True),
    ActorRole(COORDINATOR, COORDINATOR_SLOT, COORDINATOR_LABEL, has_id=True),
    ActorRole(VENDOR2, CAST[3], VENDOR2_LABEL, has_id=True),
    case_actor_role(),
]
#: Indexed for the CLI factory and for ``story_clients()``, which reads
#: each actor's container address off its cast slot — so this module declares
#: no ``*_BASE_URL`` constant of its own (DEMOCI-11-020).
_ROLES = role_map(ROLES)

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
  1. Seed the Reporter and Vendor1 containers; Reporter submits a
     vulnerability report to Vendor1's inbox.
  2. Vendor1 validates and engages the case; Reporter asks about a
     workaround and Vendor1 answers.
  3. The Coordinator's and Vendor2's containers are seeded and Vendor1
     invites the Coordinator with CVDRole.COORDINATOR; it accepts.
  4. Vendor1, the case owner, keeps the case: Coordinator suggests Vendor2
     (ADR-0026) and Vendor1 approves the actor recommendation.
  5. CaseActor invites Vendor2; Vendor2 accepts and runs its RM triage.
  6. Verify LedgerFanout replication on all replicas.
  7. All four exchange case notes.
  8. Both vendors independently advance to fix-ready (VFd).
  9. All participants report publication; embargo terminates.
 10. All participants close the case; the case ledgers are dumped.
"""


# ---------------------------------------------------------------------------
# Fragments this scenario alone tells
# ---------------------------------------------------------------------------


def the_case_is_active(state: StoryState) -> None:
    """The Coordinator has joined and the embargo is still active.

    Milestone M1 of the scenario's spec group.
    """
    required_participants_are_present(
        state,
        check=(
            "M1: required participants (≥4), EM.ACTIVE, reporter +"
            " coordinator have replicas"
        ),
    )


def replicas_drain_before_the_second_vendor(state: StoryState) -> None:
    """Everything the opening recorded has reached the Reporter's and the
    Coordinator's replicas of the case.

    This scenario's own step: ``rvcv-handoff`` never drained here, and a
    fragment only one scenario tells belongs in its own module
    (``notes/demo-scenario-tree.md`` § "Composition").

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
        auth_client=state.client(VENDOR),
        replicas=[
            (state.client(REPORTER), REPORTER_LABEL),
            (state.client(COORDINATOR), COORDINATOR_LABEL),
        ],
        case_id=state.case.id_,
        phase_label="opening drain before Vendor2 joins",
    )


def the_coordinator_suggests_the_second_vendor(state: StoryState) -> None:
    """The Coordinator suggests Vendor2 via ADR-0026; Vendor1 approves.

    Vendor1 keeping the case is what makes the suggestion the route in: it is
    Vendor1, the owner, that converts the Coordinator's
    ``Offer(Actor)[target=VulnerabilityCase]`` into an invitation
    (DEMOMA-10-004, DEMOMA-10-005, DEMOMA-10-014).  The Coordinator must
    be a participant to suggest anyone, so the shared continuation reads the
    join the opening's roster gate kept (DEMOMA-10-003).
    """
    the_owner_approves_a_suggested_actor(
        state,
        joined=COORDINATOR_JOINED,
        owner=VENDOR_PART,
        suggester=COORDINATOR_PART,
        newcomer=VENDOR2_PART,
        roles=[CVDRole.VENDOR],
        seated=(REPORTER, VENDOR, COORDINATOR, VENDOR2),
    )


def the_four_exchange_notes(state: StoryState) -> None:
    """The Coordinator and Vendor2 answer the thread the opening posted."""
    the_joiners_add_their_notes(
        state,
        [
            NotePost(
                state.actor(COORDINATOR),
                f"{COORDINATOR_LABEL} Update",
                "We have confirmed that both Vendor1 and Vendor2 are engaged. "
                "Target disclosure in 30 days.",
            ),
            NotePost(
                state.actor(VENDOR2),
                f"{VENDOR2_LABEL} Status Update",
                "Vendor2 can confirm the issue affects our component as well. "
                "We will align our fix timeline with Vendor1.",
            ),
        ],
    )


def both_vendors_fix_the_vul(state: StoryState) -> None:
    """Both vendors report fix ready; both stop at VFd (CSB-15-002)."""
    both_vendors_report_the_fix_ready(
        state,
        reached="M5: the Reporter and each vendor's own replica show that"
        " vendor's CS includes F (fix ready), for both vendors",
        stopped="M6: both vendors stopped at VFd — no fix-deployed transition",
    )


def everyone_publishes(state: StoryState) -> None:
    """Vendor1, the Case Owner, publishes first; the Reporter reports last."""
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
    reports_published(state, COORDINATOR)
    the_embargo_ends_for(
        state,
        check=(
            "Embargo terminated (EM.EXITED) propagated to Reporter before"
            " notify-published"
        ),
        watcher=REPORTER,
    )
    reports_published(state, REPORTER)
    the_disclosure_reached_every_replica(
        state,
        check=(
            "M7: all replicas CS.VFdPxa, EM.EXITED, all participants"
            " public-aware"
        ),
    )


def everyone_closes(state: StoryState) -> None:
    """Vendor2, the Coordinator and the Reporter leave; Vendor1 leaves last."""
    close_the_case(
        state,
        others=(VENDOR2, COORDINATOR, REPORTER),
        owner=VENDOR,
        milestone="M8",
    )


#: The RVCV-extension story: the opening it shares with ``rvcv-handoff``, then
#: Vendor1 keeping the case, the ADR-0026 suggestion that brings Vendor2 in,
#: and the four-party lifecycle to closure.  The registry reads this
#: scenario's path off the ``choose`` items (DEMOCI-11-019), so it declares no
#: ``path=``.
STORY = story(
    THE_VENDOR_INVITES_A_COORDINATOR,
    the_case_is_active,
    replicas_drain_before_the_second_vendor,
    # Vendor1, the case owner, decides once the Coordinator has joined, and
    # before the suggestion it then accepts (another role's step falls in
    # between).
    choose("owner-keep-case", "keep", by=VENDOR),
    the_coordinator_suggests_the_second_vendor,
    every_replica_converges,
    the_four_exchange_notes,
    both_vendors_fix_the_vul,
    everyone_publishes,
    everyone_closes,
)


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
        "RVCV-EXTENSION DEMO: Reporter + Vendor1(CASE_OWNER) + Coordinator +"
        " Vendor2"
    )
    logger.info("=" * 80)
    logger.info("Reporter container:    %s", reporter_client.base_url)
    logger.info("Vendor1 container:     %s", vendor_client.base_url)
    logger.info("Coordinator container: %s", coordinator_client.base_url)
    logger.info("Vendor2 container:     %s", vendor2_client.base_url)
    logger.info("CaseActor container:   %s", case_actor_client.base_url)

    open_cast = vendor_open_cast(
        reporter_client=reporter_client,
        vendor_client=vendor_client,
        case_actor_client=case_actor_client,
        dump=dump_vendor_coordinator_ledgers,
        reporter_id=reporter_id,
        vendor_id=vendor_id,
        unseated=unseated_coordinator_and_vendor2(
            coordinator_client=coordinator_client,
            coordinator_id=coordinator_id,
            vendor2_client=vendor2_client,
            vendor2_id=vendor2_id,
        ),
    )

    # run_story() owns the failure accumulator through scenario_harness: it
    # resets it, always dumps the case ledgers, and asserts success — so a
    # failure here never costs us the artifacts (ISSUE-2239, DEMOMA-23-001).
    run_story(DEMO_NAME, STORY, open_cast)

    logger.info("=" * 80)
    logger.info("RVCV-EXTENSION DEMO COMPLETE ✓  (VFDPxa full lifecycle)")
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@scenario(
    name=DEMO_NAME,
    label="RVCV-extension",
    participants="Reporter + Vendor1 + Coordinator + Vendor2",
    feature="Coordinator-suggested second vendor",
    in_pr_set=False,
    story=STORY,
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
    clients = story_clients(
        _ROLES,
        vendor_coordinator_cast_members(
            reporter_url=reporter_url,
            vendor_url=vendor_url,
            coordinator_url=coordinator_url,
            vendor2_url=vendor2_url,
        ),
        skip_health_check=skip_health_check,
        case_actor_url=case_actor_url,
    )
    run_rvcv_extension_demo(
        reporter_client=clients[REPORTER],
        vendor_client=clients[VENDOR],
        coordinator_client=clients[COORDINATOR],
        vendor2_client=clients[VENDOR2],
        case_actor_client=clients[CASE_ACTOR_NAME],
        **resolved_actor_ids(
            _ROLES,
            reporter=(clients[REPORTER], reporter_id),
            vendor=(clients[VENDOR], vendor_id),
            coordinator=(clients[COORDINATOR], coordinator_id),
            vendor2=(clients[VENDOR2], vendor2_id),
        ),
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
