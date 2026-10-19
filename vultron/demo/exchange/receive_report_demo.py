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

The finder submits each report through its own ``submit-report`` trigger, so the
finder holds the anchor it checks the vendor's case introduction against
(CBT-01-005).  The vendor's responses are posted directly to inboxes rather than
relying on outbox processing. For the inbox pipeline those posts enter, see the
"From HTTP delivery to behavior tree: the inbox pipeline" section of
docs/topics/reference_architecture.md.

When run as a script, this module will:
1. Check if the API server is available
2. Reset the data layer to a clean state
3. Discover actors (finder, vendor, coordinator) via the API
4. Run three separate demo workflows, each with a unique report:
   - demo_validate_report: Submit → Validate → Case introduced to the finder
   - demo_invalidate_report: Submit → Invalidate → Notify finder via inbox
   - demo_invalidate_and_close_report: Submit → Invalidate → Close the case →
     Notify finder via inbox
5. Verify side effects in the data layer and finder's inbox for each workflow

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
from vultron.demo.helpers.runner import run_exchange_demos
from vultron.demo.helpers.verification import (
    verify_activity_in_inbox,
)
from vultron.demo.helpers.workflow import (
    find_case_by_report_id,
    reporter_submits_report,
    verify_reporter_trusts_introduction,
    wait_for_case_for_offer,
)
from vultron.demo.utils import (  # noqa: F401 — BASE_URL needed for test monkeypatching
    BASE_URL,
    DataLayerClient,
    case_actor_id_for_report,
    check_server_availability,  # imported by test_health_check_retry
    demo_check,
    demo_step,
    get_offer_from_datalayer,
    logfmt,
    post_to_inbox_and_wait,
    setup_demo_logging,
    verify_received_activity_stored,
)
from vultron.wire.as2.factories import (
    rm_close_case_activity,
    rm_invalidate_report_activity,
    rm_validate_report_activity,
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
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor | None = None,
):
    """
    Demonstrates the workflow where a vendor validates a report and creates a case.

    Uses VultronActivity (Accept) activity.  The vendor's own
    ``Create(VulnerabilityCase)`` then introduces the case to the finder
    (CBT-01-001), and the demo checks the finder took it on the trusted route.

    This follows the "Receiver Accepts Offered Report" sequence diagram from
    docs/howto/activitypub/activities/report_vulnerability.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO 1: Validate Report and Create Case")
    logger.info("=" * 80)

    report = report_offer = None
    with demo_step("Step 1: Finder submits vulnerability report to vendor"):
        # Through the finder's own submit-report trigger, which writes the
        # anchor the vendor's case introduction is checked against
        # (CBT-01-005, #4675).
        report, report_offer = reporter_submits_report(
            client,
            finder,
            vendor,
            reporter_client=client,
            report_name="Authentication Bypass Vulnerability",
            report_content="This is a legitimate vulnerability in the authentication module.",
        )
        logger.info("Submitted report: %s", logfmt(report))

    with demo_step("Step 2: Vendor validates report"):
        offer = get_offer_from_datalayer(client, vendor.id_, report_offer.id_)
        validate_activity = rm_validate_report_activity(
            offer,
            actor=vendor.id_,
            content="Validating the report as legitimate. Creating case.",
        )
        post_to_inbox_and_wait(client, vendor.id_, validate_activity)
        with demo_check("ValidateReport activity stored"):
            verify_received_activity_stored(client, validate_activity.id_)

    with demo_step("Step 3: Vendor creates case and introduces it to finder"):
        case_data = None
        with demo_check("Case created for report"):
            case_data = find_case_by_report(client, report.id_)
            if not case_data:
                logger.error("Could not find case related to this report.")
                raise ValueError("Could not find case related to this report.")
        # The vendor's own Create(VulnerabilityCase) introduces the case to
        # the finder (CBT-01-001); the demo builds and posts none (#4675).
        verify_reporter_trusts_introduction(
            client,
            finder,
            vendor,
            report,
            case_id=case_data.id_ if case_data else None,
        )

    logger.info(
        "✅ DEMO 1 COMPLETE: Report validated, case created, and introduced to the finder."
    )


def demo_invalidate_report(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor | None = None,
):
    """
    Demonstrates the workflow where a vendor invalidates a report.

    Uses VultronActivity (TentativeReject) activity, followed by vendor posting
    the response directly to the finder's inbox.

    This follows the "Receiver Invalidates and Holds Offered Report" sequence diagram from
    docs/howto/activitypub/activities/report_vulnerability.md.

    Note: This demo uses direct inbox-to-inbox communication. The vendor posts
    the invalidation response directly to the finder's inbox (see the inbox
    pipeline section of docs/topics/reference_architecture.md).
    """
    logger.info("=" * 80)
    logger.info("DEMO 2: Invalidate Report (Hold for Reconsideration)")
    logger.info("=" * 80)

    report = report_offer = offer = None
    with demo_step("Step 1: Finder submits vulnerability report to vendor"):
        # Through the finder's own submit-report trigger, which writes the
        # anchor the vendor's case introduction is checked against
        # (CBT-01-005, #4675).
        report, report_offer = reporter_submits_report(
            client,
            finder,
            vendor,
            reporter_client=client,
            report_name="Potential Payment Processing Issue",
            report_content="Possible vulnerability in payment processing, needs more investigation.",
        )
        logger.info("Submitted report: %s", logfmt(report))

    with demo_step(
        "Step 2: Vendor invalidates report (holds for reconsideration)"
    ):
        offer = get_offer_from_datalayer(client, vendor.id_, report_offer.id_)
        invalidate_activity = rm_invalidate_report_activity(
            offer,
            actor=vendor.id_,
            content="Invalidating the report - needs more investigation before accepting.",
        )
        post_to_inbox_and_wait(client, vendor.id_, invalidate_activity)
        with demo_check("InvalidateReport activity stored"):
            verify_received_activity_stored(client, invalidate_activity.id_)

    with demo_step("Step 3: Vendor notifies finder of invalidation"):
        invalidate_response_to_finder = rm_invalidate_report_activity(
            offer,
            actor=vendor.id_,
            to=[finder.id_],
            content="We are holding this report for further investigation.",
        )
        post_to_inbox_and_wait(
            client, finder.id_, invalidate_response_to_finder
        )
        with demo_check("InvalidateReport response in finder's inbox"):
            if not verify_activity_in_inbox(
                client, finder.id_, invalidate_response_to_finder.id_
            ):
                logger.error(
                    "TentativeReject activity not found in finder's inbox."
                )
                raise ValueError(
                    "TentativeReject activity not found in finder's inbox."
                )

    # The vendor created the case on receipt (auto_create_case), so its
    # introduction reaches the finder whatever the RM outcome (CBT-01-001).
    verify_reporter_trusts_introduction(client, finder, vendor, report)

    logger.info(
        "✅ DEMO 2 COMPLETE: Report invalidated and finder notified via inbox."
    )


def demo_invalidate_and_close_report(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor | None = None,
):
    """
    Demonstrates the workflow where a vendor invalidates a report and closes it.

    Uses VultronActivity (TentativeReject) followed by a Leave(VulnerabilityCase):
    the vendor opened a case for the report on receipt, and once a case holds
    the report its owner closes the case by Leave, never by ``Close(Report)``
    (CM-23-019).  The invalidation notice is posted directly to the finder's
    inbox; the finder learns of the closure from the case.

    This follows the "Receiver Invalidates and Closes Offered Report" sequence diagram from
    docs/howto/activitypub/activities/report_vulnerability.md.

    Note: This demo uses direct inbox-to-inbox communication. The vendor posts
    response activities directly to the finder's inbox (see the inbox pipeline
    section of docs/topics/reference_architecture.md).
    """
    logger.info("=" * 80)
    logger.info("DEMO 3: Invalidate and Close Report")
    logger.info("=" * 80)

    report = report_offer = offer = None
    with demo_step("Step 1: Finder submits vulnerability report to vendor"):
        # Through the finder's own submit-report trigger, which writes the
        # anchor the vendor's case introduction is checked against
        # (CBT-01-005, #4675).
        report, report_offer = reporter_submits_report(
            client,
            finder,
            vendor,
            reporter_client=client,
            report_name="False Positive Report",
            report_content="This is a false positive - not a real vulnerability.",
        )
        logger.info("Submitted report: %s", logfmt(report))

    with demo_step(
        "Step 2: Vendor invalidates the report and closes the case"
    ):
        offer = get_offer_from_datalayer(client, vendor.id_, report_offer.id_)
        invalidate_activity = rm_invalidate_report_activity(
            offer,
            actor=vendor.id_,
            content="Invalidating the report - this is a false positive.",
        )
        post_to_inbox_and_wait(client, vendor.id_, invalidate_activity)
        case = wait_for_case_for_offer(client, offer.id_)
        close_activity = rm_close_case_activity(case, actor=vendor.id_)
        post_to_inbox_and_wait(client, vendor.id_, close_activity)
        with demo_check("InvalidateReport and CloseCase activities stored"):
            verify_received_activity_stored(client, invalidate_activity.id_)
            verify_received_activity_stored(client, close_activity.id_)

    with demo_step("Step 3: Vendor notifies finder of invalidation"):
        invalidate_response_to_finder = rm_invalidate_report_activity(
            offer,
            actor=vendor.id_,
            to=[finder.id_],
            content="This report has been invalidated as a false positive.",
        )
        post_to_inbox_and_wait(
            client,
            finder.id_,
            invalidate_response_to_finder,
        )
        with demo_check("InvalidateReport response in finder's inbox"):
            if not verify_activity_in_inbox(
                client, finder.id_, invalidate_response_to_finder.id_
            ):
                logger.error(
                    "TentativeReject activity not found in finder's inbox."
                )
                raise ValueError(
                    "TentativeReject activity not found in finder's inbox."
                )

    # The vendor created the case on receipt (auto_create_case), so its
    # introduction reaches the finder whatever the RM outcome (CBT-01-001).
    verify_reporter_trusts_introduction(client, finder, vendor, report)

    logger.info(
        "✅ DEMO 3 COMPLETE: Report invalidated, case closed, and finder notified via inbox."
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
