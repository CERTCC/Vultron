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

"""Demo for the CaseProposal protocol round-trip (CP-04 through CP-06).

Exercises the full ``Create(as_CaseProposal)`` →
``Accept(as_CaseProposal)`` + ``Create(VulnerabilityCase)`` round-trip
between a vendor actor and the co-located case-actor service, per
ADR-0023 and ``specs/case-proposal.yaml`` CP-07-003.

Workflow
--------
1. Finder submits a vulnerability report to the vendor inbox.
2. The vendor processes the report: ``create_receive_report_case_tree``
   runs, which includes ``ProposeCaseToActorNode`` — this queues
   ``Create(as_CaseProposal)`` addressed to the case-actor service and
   flushes the vendor's outbox.
3. The case-actor service receives ``Create(as_CaseProposal)`` and
   responds with two activities:

   a. ``Accept(as_CaseProposal)`` — acknowledgement to the vendor
   b. ``Create(VulnerabilityCase)`` — case announcement to the vendor

4. Verification:

   - At least one ``Accept`` activity exists in the DataLayer
     (the case-actor's acceptance of the proposal).
   - At least one ``VulnerabilityCase`` exists in the DataLayer
     (the case created by the case-actor service).

Note: In the current prototype the case-actor service is co-located on
the same server as the vendor actor.  Inter-actor delivery happens via
the in-process ASGI emitter, so the full chain completes within a single
inbox-POST request cycle.

Per ``specs/case-proposal.yaml`` CP-04-001, CP-04-002, CP-05-001 through
CP-05-004, CP-06-001 through CP-06-003.
"""

import logging
import sys
from typing import Callable, Optional, Sequence

from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)
from vultron.demo.utils import (  # noqa: F401 — BASE_URL needed for test monkeypatching
    BASE_URL,
    DataLayerClient,
    check_server_availability,
    demo_check,
    demo_environment,
    demo_step,
    post_to_inbox_and_wait,
    setup_demo_logging,
    verify_object_stored,
)
from vultron.wire.as2.factories import rm_submit_report_activity

logger = logging.getLogger(__name__)


def demo_case_proposal_round_trip(
    client: DataLayerClient, finder: as_Actor, vendor: as_Actor
) -> None:
    """Exercise the full CaseProposal round-trip (CP-07-003).

    Finder submits a report to vendor's inbox.  The vendor's BT tree
    includes ``ProposeCaseToActorNode``, which queues
    ``Create(as_CaseProposal)`` to the case-actor service.  The
    case-actor responds with ``Accept(as_CaseProposal)`` and
    ``Create(VulnerabilityCase)``.

    Args:
        client: DataLayerClient pointing at the demo server.
        finder: The finder actor (report originator).
        vendor: The vendor actor (receives the report, hosts the
            case-actor service).
    """
    with demo_step("Step 1: Finder submits vulnerability report to vendor"):
        report = VulnerabilityReport(
            attributed_to=finder.id_,
            name="CP-07-003 demo report",
            content=(
                "A buffer-overflow vulnerability discovered during testing "
                "of the CaseProposal protocol round-trip demo."
            ),
        )
        offer = rm_submit_report_activity(
            report,
            actor=finder.id_,
            to=vendor.id_,
        )
        post_to_inbox_and_wait(client, vendor.id_, offer)
        with demo_check("Report and offer persisted in DataLayer"):
            verify_object_stored(client, report.id_)
            verify_object_stored(client, offer.id_)

    with demo_step(
        "Step 2: Verify ProposeCaseToActorNode sent Create(as_CaseProposal)"
        " and the case-actor responded"
    ):
        with demo_check(
            "Accept(as_CaseProposal) exists — case-actor accepted the proposal"
        ):
            accept_activities = client.get("/Accepts/")
            assert isinstance(accept_activities, dict) and accept_activities, (
                "Expected at least one Accept activity in the DataLayer "
                "after the CaseProposal round-trip (CP-05-003).  "
                "The case-actor may not have processed Create(as_CaseProposal)."
            )
            logger.info("Accept activities found: %d", len(accept_activities))

        with demo_check(
            "VulnerabilityCase exists — case-actor created the case"
        ):
            cases = client.get("/VulnerabilityCases/")
            assert isinstance(cases, dict) and cases, (
                "Expected at least one VulnerabilityCase in the DataLayer "
                "after the CaseProposal round-trip (CP-05-003).  "
                "The case-actor may not have emitted Create(VulnerabilityCase)."
            )
            logger.info("VulnerabilityCase records found: %d", len(cases))


def main(
    skip_health_check: bool = False,
    demos: Optional[Sequence[Callable]] = None,
) -> None:
    """Run the CaseProposal round-trip demo.

    Args:
        skip_health_check: When ``True``, skip the server health check.
            Useful in integration tests where the server is already known
            to be running.
        demos: Optional explicit list of demo callables to run.  Defaults
            to ``[demo_case_proposal_round_trip]``.
    """
    setup_demo_logging()
    client = DataLayerClient(base_url=BASE_URL)
    if not skip_health_check and not check_server_availability(client):
        logger.error("Server is not available at %s", BASE_URL)
        return

    if demos is None:
        demos = [demo_case_proposal_round_trip]

    with demo_environment(client) as (finder, vendor, _coordinator):
        for demo_fn in demos:
            demo_fn(client, finder, vendor)


if __name__ == "__main__":
    main()
    sys.exit(0)
