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

C2 and V2 are **character actors**, seeded by the fragment that brings them
in rather than by the shared opening (DEMOCI-11-018).  The fragments only this
scenario tells are in :mod:`vultron.demo.scenario.rcvcv_fragments`; this
module keeps the story, the cast seating and the CLI and client plumbing, so
it stays the one scenario module the registry derives from the name
(DEMOCI-11-003).

Spec: DEMOMA-19 (GitHub issue #1925).
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
    REPORTER,
    REPORTER_ASKS_THE_VENDOR,
    REPORTER_LABEL,
    coordinated_open_cast,
)
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
    dump_story_ledgers,
    story_clients,
)
from vultron.demo.scenario.rcvcv_fragments import (
    C1,
    C1_LABEL,
    C2,
    C2_LABEL,
    V1,
    V1_LABEL,
    V2,
    V2_LABEL,
    all_five_close_the_case,
    both_vendors_run_the_fix_lifecycle,
    c1_invites_the_second_coordinator,
    c2_suggests_the_vendor_deployer,
    every_replica_converges,
    replicas_drain_before_the_second_coordinator,
    required_participants_are_present,
    seed_the_second_coordinator_and_vendor,
    the_joiners_add_their_notes,
    v1_publishes_then_the_others,
)
from vultron.demo.scenario.registry import scenario
from vultron.demo.utils import DataLayerClient, setup_demo_logging

logger = logging.getLogger(__name__)

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
    dump_story_ledgers(
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

    open_cast = coordinated_open_cast(
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
    clients = story_clients(
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
