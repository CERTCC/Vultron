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
1. Finder submits a vulnerability report through its own ``submit-report``
   trigger, which writes its pending ``ReportCaseLink`` (CBT-01-005).
2. The vendor processes the report: ``create_receive_report_case_tree``
   runs, which includes ``ProposeReportCaseToActorNode`` — this queues
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
   - The finder accepted the vendor's ``Create(VulnerabilityCase)``
     introduction on the trusted route (CBT-01-001, CBT-01-005).

Note: In the current prototype the case-actor service is co-located on
the same server as the vendor actor.  Inter-actor delivery happens via
the in-process ASGI emitter, so the full chain completes within a single
inbox-POST request cycle.

Per ``specs/case-proposal.yaml`` CP-04-001, CP-04-002, CP-05-001 through
CP-05-004, CP-06-001 through CP-06-003.
"""

import logging
import sys
from collections.abc import Callable, Sequence

from vultron.demo.helpers.polling import wait_for_initialized_case
from vultron.demo.helpers.workflow import (
    reporter_submits_report,
    verify_reporter_trusts_introduction,
)
from vultron.demo.utils import (  # BASE_URL needed for test monkeypatching
    BASE_URL,
    DataLayerClient,
    assert_demo_success,
    check_server_availability,
    demo_check,
    demo_environment,
    demo_step,
    read_received_activities,
    reset_demo_failures,
    setup_demo_logging,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor

logger = logging.getLogger(__name__)


def demo_case_proposal_round_trip(
    client: DataLayerClient, finder: as_Actor, vendor: as_Actor
) -> None:
    """Exercise the full CaseProposal round-trip (CP-07-003).

    Finder submits a report through its own trigger.  The vendor's BT tree
    includes ``ProposeReportCaseToActorNode``, which queues
    ``Create(as_CaseProposal)`` to the case-actor service.  The
    case-actor responds with ``Accept(as_CaseProposal)`` and
    ``Create(VulnerabilityCase)``.

    Args:
        client: DataLayerClient pointing at the demo server.
        finder: The finder actor (report originator).
        vendor: The vendor actor (receives the report, hosts the
            case-actor service).
    """
    # Step 1: through the finder's own submit-report trigger, which writes
    # the anchor the vendor's case introduction is checked against
    # (CBT-01-005, #4675).  The helper records its own steps and raises when
    # the trigger fails, so nothing below runs on a missing report.
    report, _offer = reporter_submits_report(
        client,
        finder,
        vendor,
        reporter_client=client,
        report_name="CP-07-003 demo report",
        report_content=(
            "A buffer-overflow vulnerability discovered during testing "
            "of the CaseProposal protocol round-trip demo."
        ),
    )

    case = None
    with demo_step(
        "Step 2: Verify ProposeReportCaseToActorNode sent Create(as_CaseProposal)"
        " and the case-actor responded"
    ):
        with demo_check(
            "Accept(as_CaseProposal) exists — case-actor accepted the proposal"
        ):
            # The vendor received the Accept, so it is read from the vendor's
            # archive record of it, never a row under the case-actor's id
            # (DL-06-006).
            accept_activities = read_received_activities(
                client, "Accept", actor_id=vendor.id_
            )
            assert accept_activities, (
                "Expected at least one Accept activity in the DataLayer "
                "after the CaseProposal round-trip (CP-05-003).  "
                "The case-actor may not have processed Create(as_CaseProposal)."
            )
            logger.info("Accept activities found: %d", len(accept_activities))

        with demo_check(
            "VulnerabilityCase for this report exists — case-actor created"
            " the case"
        ):
            # Only the introduction check below reads the case, and it
            # checks any bound case when this one is missing, so a timeout
            # cannot leave a later step on unestablished state: demo_check,
            # not demo_gate.
            case = wait_for_initialized_case(client, report.id_)

    with demo_step("Step 3: Vendor introduces the case to the finder"):
        # The vendor's own Create(VulnerabilityCase) introduces the case
        # (CBT-01-001); the finder accepts it on the trusted route.
        verify_reporter_trusts_introduction(
            client,
            finder,
            vendor,
            report,
            case_id=case.id_ if case is not None else None,
        )


def main(
    skip_health_check: bool = False,
    demos: Sequence[Callable] | None = None,
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

    # A failed demo_check only records the failure, so the run must raise
    # on what it recorded (DEMOCI-01-001, DEMOCI-01-003).
    reset_demo_failures()
    with demo_environment(client) as (finder, vendor, _coordinator):
        for demo_fn in demos:
            demo_fn(client, finder, vendor)
    assert_demo_success()


if __name__ == "__main__":
    main()
    sys.exit(0)
