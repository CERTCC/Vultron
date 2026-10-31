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

"""Reporter → C1 (CASE_OWNER) + C2 (Coordinator) + Vendor (RCCV-extension) demo.

Four actor containers plus a dedicated CaseActor:

- Reporter: the report submitter;
- C1 (cast slot 2, the first Coordinator): CASE_OWNER throughout — ownership
  never moves (DEMOMA-13-002);
- C2 (cast slot 3, a character actor): a participant holding
  ``CVDRole.COORDINATOR`` and **not** ``CVDRole.CASE_MANAGER``, which suggests
  the Vendor through the ADR-0026 suggest-actor flow;
- Vendor (cast slot 1, the first Vendor): joins on C1's approval and runs the
  fix path;
- CaseActor (case-actor container): holds the canonical case and ledger.

Cast (DEMOCI-11-020): every scenario runs the same containers, so a role's
address and actor id are the same here as in its siblings.  ``ROLES`` below
seats each actor; the cast table is ``vultron/demo/helpers/cast.py``.

The story is assembled, not written out: it starts with
:data:`~vultron.demo.helpers.two_coordinator_story.C1_INVITES_C2`, the opening
it shares with ``rccv-handoff`` — itself continuing the rcv family's
``REPORTER_TELLS_THE_COORDINATOR`` — and continues with C1 keeping the case
(:data:`STORY`, DEMOCI-11-019).  C1 and the Vendor are the family's
Coordinator and Vendor, so the story reaches them under those names; ``c1``
and ``vendor`` remain their names on the command line and in the devlogs the
invariant harness reads.

Spec: DEMOMA-13 (GitHub issue #1620).
"""

import logging

from vultron.demo.helpers.actor_roles import (
    case_actor_role,
    resolved_actor_ids,
    role_map,
)
from vultron.demo.helpers.coordinated_story import (
    CASE_ACTOR_NAME,
    REPORTER,
    REPORTER_LABEL,
    VENDOR,
    VENDOR_LABEL,
    close_the_case,
    coordinated_clients,
    coordinated_open_cast,
    vendor_reports_the_fix_ready,
)
from vultron.demo.helpers.notes import NotePost
from vultron.demo.helpers.owner_decision_story import (
    the_owner_approves_a_suggested_actor,
)
from vultron.demo.helpers.story import StoryState, choose, run_story, story
from vultron.demo.helpers.sync import wait_for_replica_ledger_coverage
from vultron.demo.helpers.two_coordinator_story import (
    C1,
    C1_INVITES_C2,
    C1_PART,
    C1_ROLE,
    C2,
    C2_LABEL,
    C2_PART,
    SECOND_COORDINATOR_JOINED,
    VENDOR_PART,
    all_four_publish,
    dump_two_coordinator_ledgers,
    every_replica_converges,
    four_way_note_thread,
    required_participants_are_present,
    two_coordinator_cast_members,
    two_coordinator_roles,
    unseated_second_coordinator,
)
from vultron.demo.scenario.registry import scenario
from vultron.demo.utils import DataLayerClient, setup_demo_logging
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)

DEMO_NAME = "rccv-extension"

# The scenario's actors in main() parameter order, each seated in a container of
# the fixed cast (DEMOCI-11-020).  The demo CLI derives this scenario's
# sub-command options from this list (DEMOCI-11-011).
ROLES = two_coordinator_roles(case_actor=case_actor_role())
#: Indexed for the CLI factory and for ``coordinated_clients()``, which reads
#: each actor's container address off its cast slot — so this module declares
#: no ``*_BASE_URL`` constant of its own (DEMOCI-11-020).
_ROLES = role_map(ROLES)

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
  1. Seed the Reporter, C1 and Vendor containers; Reporter submits a report
     to C1's inbox; C1 validates and engages the case (CASE_OWNER).
  2. C2's container is seeded and C1 invites C2 with CVDRole.COORDINATOR;
     C2 accepts.
  3. C1, the case owner, keeps the case: C2 suggests Vendor (ADR-0026) and
     C1 approves the actor recommendation.
  4. CaseActor invites Vendor; Vendor accepts and runs its RM triage.
  5. Verify LedgerFanout replication on all replicas.
  6. All four exchange case notes.
  7. Vendor advances to fix ready (VFd).
  8. C1 (CASE_OWNER) triggers publication; the embargo terminates; all
     participants report publication.
  9. All participants close the case; the case ledgers are dumped.
"""


# ---------------------------------------------------------------------------
# Fragments this scenario alone tells
# ---------------------------------------------------------------------------


def replicas_drain_before_the_vendor(state: StoryState) -> None:
    """Wait for the opening's ledger to reach the Reporter's and C2's replicas.

    This scenario's own step: ``rccv-handoff`` never drained here, and a
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
        auth_client=state.client(C1),
        replicas=[
            (state.client(REPORTER), REPORTER_LABEL),
            (state.client(C2), C2_LABEL),
        ],
        case_id=state.case.id_,
        phase_label="opening drain before the Vendor joins",
    )


def c2_suggests_the_vendor(state: StoryState) -> None:
    """C2 suggests the Vendor via ADR-0026; C1 approves; the Vendor joins.

    C1 keeping the case is what makes the suggestion the route in: it is C1,
    the owner, that converts C2's ``Offer(Actor, Case)`` into an invitation
    (DEMOMA-13-004, DEMOMA-13-005).  C2 must be a participant to suggest
    anyone, so the shared continuation reads the join the opening's roster
    gate kept (DEMOMA-13-003).
    """
    the_owner_approves_a_suggested_actor(
        state,
        joined=SECOND_COORDINATOR_JOINED,
        owner=C1_PART,
        suggester=C2_PART,
        newcomer=VENDOR_PART,
        roles=[CVDRole.VENDOR],
        seated=(REPORTER, C1, C2, VENDOR),
    )


def the_four_exchange_notes(state: StoryState) -> None:
    """C2 and the Vendor answer the thread the Reporter and C1 opened."""
    four_way_note_thread(
        state,
        [
            NotePost(
                state.actor(C2),
                "C2 Update",
                "We have confirmed that C2 and Vendor are engaged. "
                "Target disclosure in 30 days.",
            ),
            NotePost(
                state.actor(VENDOR),
                f"{VENDOR_LABEL} Status Update",
                "Vendor can confirm the issue affects our component. "
                "We will align our fix timeline with the 30-day target.",
            ),
        ],
    )


def everyone_publishes(state: StoryState) -> None:
    """C1, still the Case Owner, publishes first (DEMOMA-13-006)."""
    all_four_publish(state, owner=C1_PART, other=C2_PART)


def everyone_closes(state: StoryState) -> None:
    """The Vendor, C2 and the Reporter leave; C1, the Case Owner, leaves last."""
    close_the_case(
        state, others=(VENDOR, C2, REPORTER), owner=C1, milestone="M8"
    )


#: The RCCV-extension story: the opening it shares with ``rccv-handoff``, then
#: C1 keeping the case, the ADR-0026 suggestion that brings the Vendor in, and
#: the four-party lifecycle to closure.  The registry reads this scenario's
#: path off the ``choose`` items (DEMOCI-11-019), so it declares no ``path=``.
STORY = story(
    C1_INVITES_C2,
    # C1, the case owner, decides once C2 has joined, and before the
    # suggestion it then accepts (another role's step falls in between).
    choose("owner-keep-case", "keep", by=C1),
    required_participants_are_present,
    replicas_drain_before_the_vendor,
    c2_suggests_the_vendor,
    every_replica_converges,
    the_four_exchange_notes,
    vendor_reports_the_fix_ready,
    everyone_publishes,
    everyone_closes,
)


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
        "RCCV-EXTENSION DEMO: Reporter + C1(CASE_OWNER) + C2(COORDINATOR)"
        " + Vendor"
    )
    logger.info("=" * 80)
    logger.info("Reporter container:  %s", reporter_client.base_url)
    logger.info("C1 container:        %s", c1_client.base_url)
    logger.info("C2 container:        %s", c2_client.base_url)
    logger.info("Vendor container:    %s", vendor_client.base_url)
    logger.info("CaseActor container: %s", case_actor_client.base_url)

    open_cast = coordinated_open_cast(
        reporter_client=reporter_client,
        coordinator_client=c1_client,
        vendor_client=vendor_client,
        case_actor_client=case_actor_client,
        dump=dump_two_coordinator_ledgers,
        reporter_id=reporter_id,
        coordinator_id=c1_id,
        vendor_id=vendor_id,
        unseated=unseated_second_coordinator(c2_client, c2_id),
    )

    # run_story() owns the failure accumulator through scenario_harness: it
    # resets it, always dumps the case ledgers, and asserts success — so a
    # failure here never costs us the artifacts (ISSUE-2239, DEMOMA-23-001).
    run_story(DEMO_NAME, STORY, open_cast)

    logger.info("=" * 80)
    logger.info("RCCV-EXTENSION DEMO COMPLETE ✓  (VFDPxa full lifecycle)")
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@scenario(
    name=DEMO_NAME,
    label="RCCV-extension",
    participants="Reporter + C1 + C2 + Vendor",
    feature="Second coordinator suggests vendor",
    in_pr_set=False,
    story=STORY,
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
    clients = coordinated_clients(
        _ROLES,
        two_coordinator_cast_members(
            reporter_url=reporter_url,
            c1_url=c1_url,
            c2_url=c2_url,
            vendor_url=vendor_url,
        ),
        skip_health_check=skip_health_check,
        case_actor_url=case_actor_url,
    )
    run_rccv_extension_demo(
        reporter_client=clients[REPORTER],
        c1_client=clients[C1_ROLE],
        c2_client=clients[C2],
        vendor_client=clients[VENDOR],
        case_actor_client=clients[CASE_ACTOR_NAME],
        **resolved_actor_ids(
            _ROLES,
            reporter=(clients[REPORTER], reporter_id),
            c1=(clients[C1_ROLE], c1_id),
            c2=(clients[C2], c2_id),
            vendor=(clients[VENDOR], vendor_id),
        ),
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
