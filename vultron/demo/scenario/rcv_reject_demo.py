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

"""RCV-Reject three-actor CVD workflow demo (Reporter + Coordinator + Vendor rejection).

Orchestrates a CVD workflow where Coordinator receives the Reporter's report,
creates the case (CASE_OWNER), the CaseActor service manages the ledger.
Coordinator invites Vendor (``invite-actor-to-case``), but Vendor rejects the
invitation (``reject-case-invite``).  Vendor is therefore NOT added to the case
as a participant.  Reporter and Coordinator continue to close out the case through
publication and closure.

Key difference from the RCV scenario: Vendor rejects the case invitation
(RM-layer rejection via ``Reject(Invite(actor, case))``) so Vendor never
becomes a case participant and has no case ledger replica.  That difference is
now where the two stories part: both start from the same
:data:`~vultron.demo.helpers.coordinated_story.COORDINATOR_INVITES_VENDOR`
opening, and this module states only the rejection continuation
(:data:`STORY`, DEMOCI-11-019).

Spec: GitHub issue #2047 (rcv-reject demo scenario).
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
    COORDINATOR,
    COORDINATOR_INVITES_VENDOR,
    REPORTER,
    VENDOR,
    coordinated_clients,
    coordinator_and_reporter_publish,
    open_coordinated_cast,
    reporter_asks_about_the_rejection,
    reporter_replica_converges,
    reporter_then_coordinator_close,
    vendor_rejects_invite,
)
from vultron.demo.helpers.harness import ScenarioHarness
from vultron.demo.helpers.ledger_dump import (
    LedgerDumpTarget,
    case_actor_dump_target,
    dump_case_ledgers,
    replica_route_key,
)
from vultron.demo.helpers.story import StoryState, choose, run_story, story
from vultron.demo.scenario.registry import scenario
from vultron.demo.utils import DataLayerClient, setup_demo_logging
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

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

#: ``vultron-demo rcv-reject --help`` text. Lives here rather than in ``cli.py``
#: because the sub-command is generated from the registry and the scenario
#: module is the only place that knows what its own workflow does.
CLI_HELP = """Run the RCV-Reject (Reporter + Coordinator + Vendor rejection) CVD demo (#2047).

Coordinator receives the Reporter's report, creates the authoritative case
(CASE_OWNER), and the CaseActor service manages the case ledger.  Coordinator
invites Vendor, but Vendor rejects the invitation via ``reject-case-invite``.
Vendor is NOT added as a case participant.  Reporter and Coordinator proceed to
publication and closure.

\b
Workflow:
  1. Seed Reporter, Coordinator, and Vendor containers.
  2. Reporter submits a vulnerability report to Coordinator's inbox.
  3. Coordinator validates the report and engages the case (CASE_OWNER).
  4. Coordinator invites Vendor directly (invite-actor-to-case).
  5. Vendor rejects the case invitation (reject-case-invite).
  6. Verify participant count stable at 3 (Vendor not added).
  7. Two-way notes exchange between Reporter and Coordinator.
  8. Coordinator and Reporter publish; embargo terminates (EM.EXITED).
  9. The Reporter closes the case, then the Coordinator, the Case Owner,
     closes it last (every RM.CLOSED in the Case Actor's store).
"""

#: The RCV-reject story: the shared opening, then the Vendor declines and the
#: Reporter and Coordinator close the case without it.  The registry reads
#: this scenario's path off the ``choose`` items (DEMOCI-11-019), so it
#: declares no ``path=``.
STORY = story(
    COORDINATOR_INVITES_VENDOR,
    choose("vendor-join", "reject", by=VENDOR),
    vendor_rejects_invite,
    reporter_replica_converges,
    reporter_asks_about_the_rejection,
    coordinator_and_reporter_publish,
    reporter_then_coordinator_close,
)


def _phase_dump_case_ledgers(
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    case: as_VulnerabilityCase,
    demo_name: str = "rcv-reject",
    vendor_client: DataLayerClient | None = None,
) -> None:
    """Dump case ledger entries from Reporter, Coordinator, and CaseActor to JSONL.

    Vendor is intentionally excluded from the dump targets: it rejected the
    invitation and was never added as a case participant, so it has no case
    ledger replica.  Its identity is still recorded in the manifest, because
    the Case Actor's ``reject_invite_actor_to_case`` entry names it as the
    recorded actor and a narrative tag must resolve to it (#4248).

    Thin scenario-specific wrapper over
    :func:`~vultron.demo.helpers.ledger_dump.dump_case_ledgers`, which owns the
    per-actor export, the 404 handling, and the dump manifest.
    """
    # Route keys come from each client's own actor id, not its display
    # name: the key selects the store (ADR-0073), so a literal is right
    # only while the scenario seeds deterministic named ids.
    targets = [
        LedgerDumpTarget(
            REPORTER,
            reporter_client,
            replica_route_key(reporter_client),
        ),
        LedgerDumpTarget(
            COORDINATOR,
            coordinator_client,
            replica_route_key(coordinator_client),
        ),
        # The canonical ledger, on the dedicated case-actor container
        # (DEMOMA-06-005).
        case_actor_dump_target(case_actor_client),
    ]

    unreplicated = (
        {VENDOR: replica_route_key(vendor_client)}
        if vendor_client is not None
        else None
    )
    dump_case_ledgers(
        demo_name=demo_name,
        case=case,
        targets=targets,
        unreplicated=unreplicated,
    )


def _dump_ledgers(state: StoryState) -> None:
    """Dump this run's ledgers, named by the story state's cast."""
    _phase_dump_case_ledgers(
        reporter_client=state.client(REPORTER),
        coordinator_client=state.client(COORDINATOR),
        case_actor_client=state.case_actor_client,
        case=state.case,
        demo_name=state.harness.demo_name,
        vendor_client=state.client(VENDOR),
    )


def run_rcv_reject_demo(
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    reporter_id: str | None = None,
    coordinator_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Orchestrate the RCV-Reject CVD workflow."""
    logger.info("=" * 80)
    logger.info(
        "RCV-REJECT DEMO: Reporter + Coordinator(CASE_OWNER) + Vendor(rejects)"
    )
    logger.info("=" * 80)
    logger.info("Reporter container:      %s", reporter_client.base_url)
    logger.info("Coordinator container: %s", coordinator_client.base_url)
    logger.info("Vendor container:      %s", vendor_client.base_url)
    logger.info("CaseActor container:   %s", case_actor_client.base_url)

    def open_cast(harness: ScenarioHarness) -> StoryState:
        return open_coordinated_cast(
            harness,
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
    run_story("rcv-reject", STORY, open_cast)

    logger.info("=" * 80)
    logger.info(
        "RCV-REJECT DEMO COMPLETE ✓  (Vendor rejected — Reporter+Coordinator closed)"
    )
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@scenario(
    name="rcv-reject",
    label="RCV-reject",
    participants="Reporter + Coordinator + Vendor (Vendor rejects)",
    feature="Invite rejection path",
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
    """Entry point for the RCV-Reject CVD workflow demo.

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
        skip_health_check=skip_health_check,
        reporter_url=reporter_url,
        coordinator_url=coordinator_url,
        vendor_url=vendor_url,
        case_actor_url=case_actor_url,
    )
    run_rcv_reject_demo(
        reporter_client=clients.reporter,
        coordinator_client=clients.coordinator,
        vendor_client=clients.vendor,
        case_actor_client=clients.case_actor,
        **resolved_actor_ids(
            _ROLES,
            reporter=(clients.reporter, reporter_id),
            coordinator=(clients.coordinator, coordinator_id),
            vendor=(clients.vendor, vendor_id),
        ),
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
