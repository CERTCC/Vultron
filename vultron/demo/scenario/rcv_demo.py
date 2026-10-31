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

"""RCV three-actor CVD workflow demo (Reporter + Coordinator + Vendor).

Orchestrates the CVD lifecycle to VFdPxa closure across four containers:
Reporter, Coordinator (CASE_OWNER), Vendor, and CaseActor.

Coordinator receives the Reporter's report and proposes the case to the
CaseActor in the dedicated case-actor container, which creates it and holds
CASE_MANAGER; the Coordinator holds CASE_OWNER.  The Reporter is
seated as reporter when the case is created (CM-22-002), so it is never
invited; the Coordinator directly invites Vendor (``invite-actor-to-case``).
Vendor accepts the report and embargo, advances through the fix lifecycle
to fix ready (VFd; Vendor stops at VFd), and all three participants
coordinate to VFdPxa closure.

The story is assembled, not written out: it starts with
:data:`~vultron.demo.helpers.coordinated_story.REPORTER_ASKS_THE_VENDOR` —
the opening it shares with ``rcvcv``, which nests the shorter one
``rcv-reject`` starts with — and continues from the Coordinator's decision to
publish (:data:`STORY`, DEMOCI-11-019).

Spec: DEMOMA-12 (GitHub issue #1593).
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
from vultron.demo.helpers.coordinated_story import (
    CASE_ACTOR_NAME,
    COORDINATOR,
    COORDINATOR_LABEL,
    REPORTER,
    REPORTER_ASKS_THE_VENDOR,
    REPORTER_LABEL,
    VENDOR,
    VENDOR_LABEL,
    CastContainer,
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
    ActorRole(REPORTER, REPORTER_SLOT, "Reporter", has_id=True),
    ActorRole(COORDINATOR, COORDINATOR_SLOT, "Coordinator", has_id=True),
    ActorRole(VENDOR, VENDOR_SLOT, "Vendor", has_id=True),
    case_actor_role(),
]
#: Indexed for the CLI factory and for ``coordinated_clients()``, which reads
#: each actor's container address off its cast slot — so this module declares
#: no ``*_BASE_URL`` constant of its own (DEMOCI-11-020).
_ROLES = role_map(ROLES)

#: ``vultron-demo rcv --help`` text. Lives here rather than in ``cli.py``
#: because the sub-command is generated from the registry and the scenario
#: module is the only place that knows what its own workflow does.
CLI_HELP = """Run the RCV (Reporter + Coordinator + Vendor) CVD demo (DEMOMA-12).

Coordinator receives the Reporter's report, creates the authoritative case
(holding CASE_OWNER), and the CaseActor service manages the case ledger.
The Reporter is seated at case creation; the Coordinator directly
invites Vendor.  Vendor accepts as a late joiner and receives the full ledger
backfill (LedgerFanout).  All participants advance through the fix lifecycle
(Vendor stops at VFd) to VFdPxa closure.

\b
Workflow:
  1. Seed Reporter, Coordinator, and Vendor containers.
  2. Reporter submits a vulnerability report to Coordinator's inbox.
  3. Coordinator validates the report and engages the case (CASE_OWNER).
  4. Coordinator invites Vendor directly (invite-actor-to-case).
  5. Vendor accepts the case invitation; case replica seeded (LedgerFanout).
  6. Verify all replica ledgers synchronized.
  7. Three-way notes exchange among all participants.
  8. Vendor advances to VF (fix ready); Vendor stops at VFd.
  9. All participants report publication; embargo terminates (EM.EXITED).
 10. All participants close the case (every RM.CLOSED in the Case Actor's store).
"""

#: The RCV story: the opening it shares with ``rcvcv`` up to the Coordinator's
#: decision, then the three participants run the case to VFdPxa closure.  The
#: registry reads this scenario's path off the ``choose`` items
#: (DEMOCI-11-019), so it declares no ``path=``.
STORY = story(
    REPORTER_ASKS_THE_VENDOR,
    # The Coordinator decides once the thread is answered.
    choose("coordinator-after-answer", "publish", by=COORDINATOR),
    vendor_reports_the_fix_ready,
    everyone_publishes,
    everyone_closes,
)


def _dump_ledgers(state: StoryState) -> None:
    """Dump this run's ledgers, named by the story state's cast.

    The ``case-actor`` ledger is read from the dedicated case-actor container,
    which holds the canonical ledger (DEMOMA-06-005).
    """
    dump_coordinated_ledgers(state, replicas=(REPORTER, COORDINATOR, VENDOR))


def run_rcv_demo(
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    reporter_id: str | None = None,
    coordinator_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Orchestrate the RCV CVD workflow."""
    logger.info("=" * 80)
    logger.info("RCV DEMO: Reporter + Coordinator(CASE_OWNER) + Vendor")
    logger.info("=" * 80)
    logger.info("Reporter container:      %s", reporter_client.base_url)
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
    run_story("rcv", STORY, open_cast)

    logger.info("=" * 80)
    logger.info("RCV DEMO COMPLETE ✓  (VFDPxa full lifecycle)")
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@scenario(
    name="rcv",
    label="RCV",
    participants="Reporter + Coordinator + Vendor",
    feature="Coordinator-mediated report and vendor onboarding",
    in_pr_set=False,
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
    """Entry point for the RCV CVD workflow demo.

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
        [
            CastContainer(REPORTER, REPORTER_LABEL, reporter_url),
            CastContainer(COORDINATOR, COORDINATOR_LABEL, coordinator_url),
            CastContainer(VENDOR, VENDOR_LABEL, vendor_url),
        ],
        skip_health_check=skip_health_check,
        case_actor_url=case_actor_url,
    )
    run_rcv_demo(
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
