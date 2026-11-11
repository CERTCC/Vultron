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

"""The RCVCV story and the run that plays it.

The story is assembled, not written out: it starts with
:data:`~vultron.demo.helpers.coordinated_story.REPORTER_ASKS_THE_VENDOR`, the
opening it shares with ``rcv`` up to C1's decision, and continues with C1
inviting a second Coordinator (:data:`STORY`, DEMOCI-11-019).  Each fragment
it continues with is in :mod:`~vultron.demo.scenario.rcvcv_demo.fragments`.

C2 and V2 are **character actors**: their containers are reset with the rest,
and their actors are seeded by the fragment that brings them in rather than by
the shared opening, because every record the opening writes before the case
exists moves the first ledger entry's timestamp away from the sibling it must
match byte for byte (DEMOCI-11-018).
"""

import logging

from vultron.demo.helpers.coordinated_story import (
    REPORTER_ASKS_THE_VENDOR,
    coordinated_open_cast,
)
from vultron.demo.helpers.story import (
    StoryState,
    UnseatedContainer,
    choose,
    run_story,
    story,
)
from vultron.demo.helpers.story_cast import dump_story_ledgers
from vultron.demo.scenario.rcvcv_demo.cast import (
    C1,
    C2,
    C2_LABEL,
    DEVLOG_REPLICAS,
    V2,
    V2_LABEL,
)
from vultron.demo.scenario.rcvcv_demo.fragments import (
    all_five_close_the_case,
    both_vendors_run_the_fix_lifecycle,
    c1_invites_the_second_coordinator,
    c2_asks_who_else_belongs,
    c2_suggests_the_vendor_deployer,
    every_replica_converges,
    replicas_drain_before_the_second_coordinator,
    required_participants_are_present,
    seed_the_second_coordinator_and_vendor,
    the_joiners_add_their_notes,
    v1_publishes_then_the_others,
)
from vultron.demo.utils import DataLayerClient

logger = logging.getLogger(__name__)

# AC-6 audit (#2203): the case-replica waits this scenario reaches through
# poll for VulnerabilityCase object delivery (ADR-0041 seeding path). ADR-0037
# and ADR-0059 buffer Announce(CaseLedgerEntry) entries, not VulnerabilityCase
# objects, so each of those waits remains necessary.

#: The RCVCV story: the opening it shares with ``rcv`` up to C1's decision,
#: then the second Coordinator, the suggestion C2's participant suggester
#: answers with and the ADR-0026 flow that brings V2 in, and
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
    c2_asks_who_else_belongs,
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
