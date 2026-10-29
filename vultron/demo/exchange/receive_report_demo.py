#!/usr/bin/env python

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""
Demonstrates the workflow for receiving and processing vulnerability reports via the Vultron API.

This demo script showcases three different outcomes when processing vulnerability reports:
1. Validate Report: ``as_Accept`` - creates a case
2. Invalidate Report: ``as_TentativeReject`` - holds for reconsideration
3. Invalidate and Close: ``as_TentativeReject`` + ``as_Leave`` - invalidates the
   report and closes the case opened for it

The reporter submits each report through its own ``submit-report`` trigger, so the
reporter holds the anchor it checks the vendor's case introduction against
(CBT-01-005).  The vendor answers through its own ``validate-report``,
``invalidate-report``, ``terminate-embargo`` and ``leave-case`` triggers, whose outbox sends each answer
to the CASE_MANAGER of the case opened on receipt; the demo posts nothing into an
inbox by hand (#5438).

When run as a script, this module will:
1. Check if the API server is available
2. Reset the data layer to a clean state
3. Discover actors (reporter, vendor, coordinator) via the API
4. Run three separate demo workflows, each with a unique report:
   - demo_validate_report: Submit → Validate → Case introduced to the reporter
   - demo_invalidate_report: Submit → Invalidate → Reporter's replica records it
   - demo_invalidate_and_close_report: Submit → Invalidate → End the embargo →
     Reporter leaves, then the vendor (Case Owner) closes the case
5. Verify side effects in the data layer and the reporter's replica of the case

Note on Behavior Tree Execution:
The validate_report handler uses py_trees behavior tree execution to orchestrate the validation
workflow. BT execution logging is available server-side:
- INFO level: BT execution start, completion status, and feedback
- DEBUG level: Detailed tree structure visualization and execution state

To see BT execution details, run the API server with DEBUG logging enabled:
  LOG_LEVEL=DEBUG uvicorn vultron.api.main:app --port 7999

The BT logs will show tree structure before execution and final state after completion.
"""

# Standard library imports
import logging
from collections.abc import Callable, Sequence

# Vultron imports
from vultron.core.states.rm import RM
from vultron.demo.helpers.runner import run_exchange_demos
from vultron.demo.helpers.workflow import (
    check_report_answer_recorded,
    find_case_by_report_id,
    receiver_invalidates_and_closes,
    receiver_invalidates_report,
    receiver_validates_report,
    reporter_submits_report,
    verify_reporter_trusts_introduction,
)
from vultron.demo.utils import (  # noqa: F401 — BASE_URL needed for test monkeypatching
    BASE_URL,
    DataLayerClient,
    case_actor_id_for_report,
    check_server_availability,  # imported by test_health_check_retry
    demo_check,
    demo_step,
    logfmt,
    setup_demo_logging,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)


def find_case_by_report(
    client: DataLayerClient, report_id: str
) -> as_VulnerabilityCase | None:
    """Find the ``as_VulnerabilityCase`` that references *report_id*.

    Public name kept for backward compatibility — imported by
    ``test/demo/test_find_case_by_report.py``.

    Args:
        client: DataLayerClient instance
        report_id: Full URI of the vulnerability report

    Returns:
        The matching case, or ``None`` if not found.
    """
    # The CaseActor's store: under ADR-0041 it authors the canonical case, so the
    # case a report produced lives there, not in the vendor's replica — the
    # vendor only gets one once Create(VulnerabilityCase) has been delivered.
    return find_case_by_report_id(
        client, report_id, actor_id=case_actor_id_for_report(report_id)
    )


def demo_validate_report(
    client: DataLayerClient,
    reporter: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor | None = None,
):
    """
    Demonstrates the workflow where a vendor validates a report and creates a case.

    Uses VultronActivity (Accept) activity.  The vendor's own
    ``Create(VulnerabilityCase)`` then introduces the case to the reporter
    (CBT-01-001), and the demo checks the reporter took it on the trusted route.

    This follows the "Receiver Accepts Offered Report" sequence diagram from
    docs/howto/activitypub/activities/report_vulnerability.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO 1: Validate Report and Create Case")
    logger.info("=" * 80)

    report = report_offer = None
    with demo_step("Step 1: Reporter submits vulnerability report to vendor"):
        # Through the reporter's own submit-report trigger, which writes the
        # anchor the vendor's case introduction is checked against
        # (CBT-01-005, #4675).
        report, report_offer = reporter_submits_report(
            client,
            reporter,
            vendor,
            reporter_client=client,
            report_name="Authentication Bypass Vulnerability",
            report_content="This is a legitimate vulnerability in the authentication module.",
        )
        logger.info("Submitted report: %s", logfmt(report))

    with demo_step("Step 2: Vendor validates report"):
        # Through the vendor's validate-report trigger, which sends the Report
        # Valid to the CASE_MANAGER of the case opened on receipt (#5438).
        receiver_validates_report(
            client,
            vendor,
            report_offer.id_,
            note="Validating the report as legitimate.",
        )
        check_report_answer_recorded(
            client, reporter, vendor, report_offer.id_, {RM.VALID}
        )

    with demo_step(
        "Step 3: Vendor creates case and introduces it to reporter"
    ):
        case_data = None
        with demo_check("Case created for report"):
            case_data = find_case_by_report(client, report.id_)
            if not case_data:
                logger.error("Could not find case related to this report.")
                raise ValueError("Could not find case related to this report.")
        # The vendor's own Create(VulnerabilityCase) introduces the case to
        # the reporter (CBT-01-001); the demo builds and posts none (#4675).
        verify_reporter_trusts_introduction(
            client,
            reporter,
            vendor,
            report,
            case_id=case_data.id_ if case_data else None,
        )

    logger.info(
        "✅ DEMO 1 COMPLETE: Report validated, case created, and introduced to the reporter."
    )


def demo_invalidate_report(
    client: DataLayerClient,
    reporter: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor | None = None,
):
    """
    Demonstrates the workflow where a vendor invalidates a report.

    The vendor's ``invalidate-report`` trigger sends the TentativeReject to
    the CASE_MANAGER of the case opened on receipt, and the reporter learns
    of it from its replica of that case.

    This follows the "Receiver Invalidates and Holds Offered Report" sequence diagram from
    docs/howto/activitypub/activities/report_vulnerability.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO 2: Invalidate Report (Hold for Reconsideration)")
    logger.info("=" * 80)

    report = report_offer = None
    with demo_step("Step 1: Reporter submits vulnerability report to vendor"):
        # Through the reporter's own submit-report trigger, which writes the
        # anchor the vendor's case introduction is checked against
        # (CBT-01-005, #4675).
        report, report_offer = reporter_submits_report(
            client,
            reporter,
            vendor,
            reporter_client=client,
            report_name="Potential Payment Processing Issue",
            report_content="Possible vulnerability in payment processing, needs more investigation.",
        )
        logger.info("Submitted report: %s", logfmt(report))

    with demo_step(
        "Step 2: Vendor invalidates report (holds for reconsideration)"
    ):
        # Through the vendor's invalidate-report trigger, which sends the
        # Report Invalid to the CASE_MANAGER of the case opened on receipt
        # (#5438).
        receiver_invalidates_report(
            client,
            vendor,
            report_offer.id_,
            note="Needs more investigation before accepting.",
        )

    with demo_step("Step 3: Reporter learns of the invalidation"):
        # The CASE_MANAGER records the Report Invalid and the ledger carries
        # it to the reporter's replica; nothing is posted to its inbox.
        check_report_answer_recorded(
            client, reporter, vendor, report_offer.id_, {RM.INVALID}
        )

    # The vendor created the case on receipt (auto_create_case), so its
    # introduction reaches the reporter whatever the RM outcome (CBT-01-001).
    verify_reporter_trusts_introduction(client, reporter, vendor, report)

    logger.info(
        "✅ DEMO 2 COMPLETE: Report invalidated and the reporter's replica records it."
    )


def demo_invalidate_and_close_report(
    client: DataLayerClient,
    reporter: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor | None = None,
):
    """
    Demonstrates the workflow where a vendor invalidates a report and closes it.

    Uses VultronActivity (TentativeReject) followed by a Leave(VulnerabilityCase):
    the vendor opened a case for the report on receipt, and once a case holds
    the report its owner closes the case by Leave, never by ``Close(Report)``
    (CM-23-019).  The Case Owner first ends the case's embargo, which blocks
    its Leave (TRIG-13-003), and leaves after the reporter (CM-23-015).  Each
    act goes through the actor's own trigger to the case's CASE_MANAGER.

    This follows the "Receiver Invalidates and Closes Offered Report" sequence diagram from
    docs/howto/activitypub/activities/report_vulnerability.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO 3: Invalidate and Close Report")
    logger.info("=" * 80)

    report = report_offer = None
    with demo_step("Step 1: Reporter submits vulnerability report to vendor"):
        # Through the reporter's own submit-report trigger, which writes the
        # anchor the vendor's case introduction is checked against
        # (CBT-01-005, #4675).
        report, report_offer = reporter_submits_report(
            client,
            reporter,
            vendor,
            reporter_client=client,
            report_name="False Positive Report",
            report_content="This is a false positive - not a real vulnerability.",
        )
        logger.info("Submitted report: %s", logfmt(report))

    with demo_step(
        "Step 2: Vendor invalidates the report and closes the case"
    ):
        receiver_invalidates_and_closes(
            client,
            reporter,
            vendor,
            report_offer.id_,
            note="This is a false positive.",
        )

    # The vendor created the case on receipt (auto_create_case), so its
    # introduction reaches the reporter whatever the RM outcome (CBT-01-001).
    verify_reporter_trusts_introduction(client, reporter, vendor, report)

    logger.info(
        "✅ DEMO 3 COMPLETE: Report invalidated, case left, and the reporter's replica records it."
    )


_ALL_DEMOS: Sequence[tuple[str, Callable[..., None]]] = [
    ("Demo 1: Validate Report", demo_validate_report),
    ("Demo 2: Invalidate Report", demo_invalidate_report),
    ("Demo 3: Invalidate and Close Report", demo_invalidate_and_close_report),
]


def main(
    skip_health_check: bool = False,
    demos: Sequence | None = None,
):
    """Main entry point for the receive_report demo script."""
    run_exchange_demos(
        _ALL_DEMOS, skip_health_check=skip_health_check, demos=demos
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
