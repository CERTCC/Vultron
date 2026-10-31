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

"""RCV embargo demo (Reporter + Coordinator + Vendor, deliberate termination).

A three-party case across four containers (Reporter, Coordinator, Vendor and
CaseActor) that exercises the embargo lifecycle on its own: a post-submission
embargo negotiation and a deliberate early termination (DEMOMA-20, issue #2071).

The Coordinator creates the case and holds CASE_OWNER; the CaseActor holds
CASE_MANAGER.  Case creation activates the default embargo (EP-04-001), so the
case is at ``EM.ACTIVE`` before anyone proposes anything.  The Reporter's
proposal therefore **revises** that embargo (``ACTIVE → REVISE → ACTIVE``): the
CASE_MANAGER relays it, the Vendor consents, and the Coordinator, as owner,
activates the revision (EP-09).  After the fix is ready the Coordinator ends the
embargo deliberately (``ACTIVE → EXITED``); publication and closure follow.

The story is assembled, not written out: it starts with
:data:`~vultron.demo.helpers.coordinated_embargo_story\
.REPORTER_PROPOSES_EMBARGO`, the opening it shares with ``rcvv-embargo``, and
continues with the Vendor reporting the fix ready (:data:`STORY`,
DEMOCI-11-019).  Its steps run in the order DEMOMA-20-007 gives, and each
asserts the expected EM state before the next starts (DEMOMA-20-008).  The
assertions read the CASE_MANAGER's canonical case, or wait for the fan-out;
none reads a triggering actor's replica straight after its trigger
(DEMOMA-20-011).

Spec: DEMOMA-20, DEMOCI-07 (GitHub issue #2071).
"""

import logging

from vultron.demo.helpers.actor_roles import (
    ActorRole,
    case_actor_role,
    resolved_actor_ids,
    role_map,
)
from vultron.demo.helpers.cast import (
    COORDINATOR_SLOT,
    REPORTER_SLOT,
    VENDOR_SLOT,
)
from vultron.demo.helpers.coordinated_embargo_story import (
    REPORTER_PROPOSES_EMBARGO,
    coordinator_ends_the_embargo,
    embargo_stays_ended_through_closure,
    embargo_stays_ended_through_publication,
    embargo_survives_the_fix,
)
from vultron.demo.helpers.coordinated_story import (
    CASE_ACTOR_NAME,
    COORDINATOR,
    COORDINATOR_LABEL,
    REPORTER,
    REPORTER_LABEL,
    VENDOR,
    VENDOR_LABEL,
    coordinated_cast_members,
    coordinated_clients,
    coordinated_open_cast,
    dump_coordinated_ledgers,
    everyone_closes,
    everyone_publishes,
    vendor_reports_the_fix_ready,
)
from vultron.demo.helpers.story import StoryState, choose, run_story, story
from vultron.demo.scenario.registry import scenario
from vultron.demo.utils import DataLayerClient, setup_demo_logging

logger = logging.getLogger(__name__)

# The scenario's actors in main() parameter order, each seated in a container of
# the fixed cast (DEMOCI-11-020).  The demo CLI derives this scenario's
# sub-command options from this list (DEMOCI-11-011).
ROLES: list[ActorRole] = [
    ActorRole(REPORTER, REPORTER_SLOT, REPORTER_LABEL, has_id=True),
    ActorRole(COORDINATOR, COORDINATOR_SLOT, COORDINATOR_LABEL, has_id=True),
    ActorRole(VENDOR, VENDOR_SLOT, VENDOR_LABEL, has_id=True),
    case_actor_role(),
]
#: Indexed for the CLI factory and for ``coordinated_clients()``, which reads
#: each actor's container address off its cast slot — so this module declares
#: no ``*_BASE_URL`` constant of its own (DEMOCI-11-020).
_ROLES = role_map(ROLES)

DEMO_NAME = "rcv-embargo"

#: ``vultron-demo rcv-embargo --help`` text.
CLI_HELP = """Run the RCV embargo demo (DEMOMA-20).

Reporter + Coordinator + Vendor, exercising the embargo lifecycle: the
Reporter revises the default embargo after submitting its report, and the
Coordinator later ends the embargo deliberately, before publication.

\b
Workflow:
  1. Seed the containers; Reporter submits a report to Coordinator;
     Coordinator engages the case (CASE_OWNER); Vendor joins by invitation.
     The default embargo is active (EM.ACTIVE).
  2. Reporter proposes new embargo terms; the CASE_MANAGER relays the proposal;
     Vendor consents; Coordinator, as owner, activates the revision.
  3. Vendor advances to fix ready (VFd).
  4. Coordinator terminates the embargo (EM.EXITED).
  5. All participants report publication.
  6. All participants close the case (every RM.CLOSED in the Case Actor's store).
  7. Case ledgers are dumped for the invariant harness.
"""

#: The RCV-embargo story: the opening it shares with ``rcvv-embargo``, then
#: the Vendor reports the fix ready and the Coordinator ends the embargo
#: deliberately.  The registry reads this scenario's path off the ``choose``
#: items (DEMOCI-11-019), so it declares no ``path=``.
STORY = story(
    REPORTER_PROPOSES_EMBARGO,
    # The Vendor decides once the revised embargo is in force.
    choose("vendor-after-embargo", "report-fix-ready", by=VENDOR),
    vendor_reports_the_fix_ready,
    embargo_survives_the_fix,
    # Termination, publication and closure all presuppose the revised embargo,
    # so the first of them reads it and the story stops there without one.
    coordinator_ends_the_embargo,
    everyone_publishes,
    embargo_stays_ended_through_publication,
    everyone_closes,
    embargo_stays_ended_through_closure,
)


def _dump_ledgers(state: StoryState) -> None:
    """Dump each participant's case ledger (the last step, DEMOMA-20-007).

    Thin wrapper (DEMOMA-23-002): the harness runs it on the way out, whether
    or not an earlier step failed.
    """
    dump_coordinated_ledgers(state, replicas=(REPORTER, COORDINATOR, VENDOR))


def run_rcv_embargo_demo(
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    reporter_id: str | None = None,
    coordinator_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Orchestrate the RCV embargo workflow."""
    logger.info("=" * 80)
    logger.info(
        "RCV EMBARGO DEMO: Reporter + Coordinator(CASE_OWNER) + Vendor"
    )
    logger.info("=" * 80)
    logger.info("Reporter container:    %s", reporter_client.base_url)
    logger.info("Coordinator container: %s", coordinator_client.base_url)
    logger.info("Vendor container:      %s", vendor_client.base_url)
    logger.info("CaseActor container:   %s", case_actor_client.base_url)

    open_cast = coordinated_open_cast(
        reporter_client=reporter_client,
        coordinator_client=coordinator_client,
        vendor_client=vendor_client,
        case_actor_client=case_actor_client,
        dump=_dump_ledgers,
        reporter_id=reporter_id,
        coordinator_id=coordinator_id,
        vendor_id=vendor_id,
    )

    # run_story() owns the failure accumulator through scenario_harness: it
    # resets it, always dumps the case ledgers, and asserts success — so a
    # failure here never costs us the artifacts (ISSUE-2239, DEMOMA-23-001).
    run_story(DEMO_NAME, STORY, open_cast)

    logger.info("=" * 80)
    logger.info(
        "RCV EMBARGO DEMO COMPLETE ✓  (EM: ACTIVE → REVISE → ACTIVE → EXITED)"
    )
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@scenario(
    name=DEMO_NAME,
    label="RCV embargo",
    participants="Reporter + Coordinator + Vendor",
    feature="Embargo revision after submission and deliberate termination",
    in_pr_set=True,
    story=STORY,
)
def main(
    skip_health_check: bool = False,
    reporter_url: str | None = None,
    coordinator_url: str | None = None,
    vendor_url: str | None = None,
    case_actor_url: str | None = None,
    reporter_id: str | None = None,
    coordinator_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Entry point for the RCV embargo demo.

    Args:
        skip_health_check: Skip the server availability check.
        reporter_url: Override base URL for the Reporter container.
        coordinator_url: Override base URL for the Coordinator container.
        vendor_url: Override base URL for the Vendor container.
        case_actor_url: Override base URL for the CaseActor container.
        reporter_id: Optional deterministic URI for the Reporter actor.
        coordinator_id: Optional deterministic URI for the Coordinator actor.
        vendor_id: Optional deterministic URI for the Vendor actor.
    """
    clients = coordinated_clients(
        _ROLES,
        coordinated_cast_members(
            reporter_url=reporter_url,
            coordinator_url=coordinator_url,
            vendor_url=vendor_url,
        ),
        skip_health_check=skip_health_check,
        case_actor_url=case_actor_url,
    )
    run_rcv_embargo_demo(
        reporter_client=clients[REPORTER],
        coordinator_client=clients[COORDINATOR],
        vendor_client=clients[VENDOR],
        case_actor_client=clients[CASE_ACTOR_NAME],
        **resolved_actor_ids(
            _ROLES,
            reporter=(clients[REPORTER], reporter_id),
            coordinator=(clients[COORDINATOR], coordinator_id),
            vendor=(clients[VENDOR], vendor_id),
        ),
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
