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
1. Validate Report: RmValidateReport (Accept) - creates a case
2. Invalidate Report: RmInvalidateReport (TentativeReject) - holds for reconsideration
3. Invalidate and Close Report: RmInvalidateReport + RmCloseReport - rejects and closes

This demo uses direct inbox-to-inbox communication between actors, per the Vultron prototype
design (see docs/reference/inbox_handler.md). Actors post activities directly to each other's
inboxes rather than relying on outbox processing.

When run as a script, this module will:
1. Check if the API server is available
2. Reset the data layer to a clean state
3. Discover actors (finder, vendor, coordinator) via the API
4. Run three separate demo workflows, each with a unique report:
   - demo_validate_report: Submit → Validate → Create Case → Notify finder via inbox
   - demo_invalidate_report: Submit → Invalidate → Notify finder via inbox
   - demo_invalidate_and_close_report: Submit → Invalidate → Close → Notify finder via inbox
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
import json
import logging
import sys
from typing import Optional, Sequence, Tuple

# Vultron imports
from vultron.api.v2.data.utils import parse_id
from vultron.as_vocab.activities.case import CreateCase
from vultron.as_vocab.activities.report import (
    RmCloseReport,
    RmInvalidateReport,
    RmSubmitReport,
    RmValidateReport,
)
from vultron.as_vocab.base.objects.activities.base import as_Activity
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
from vultron.demo.utils import (
    BASE_URL,
    DataLayerClient,
    check_server_availability,
    demo_check,
    demo_step,
    get_offer_from_datalayer,
    logfmt,
    post_to_inbox_and_wait,
    postfmt,
    reset_datalayer,
    setup_clean_environment,
    verify_object_stored,
)

logger = logging.getLogger(__name__)


def make_submit_offer(finder, vendor, report) -> RmSubmitReport:
    offer = RmSubmitReport(
        actor=finder.as_id,
        as_object=report,
        to=[vendor.as_id],
    )
    logger.info(f"Created SubmitReport activity: {logfmt(offer)}")
    return offer


def submit_to_inbox(
    client: DataLayerClient, vendor_id: str, activity: as_Activity
) -> dict:
    vendor_id = parse_id(vendor_id)["object_id"]

    logger.info(
        f"Submitting activity to {vendor_id}'s inbox: {logfmt(activity)}"
    )

    return client.post(f"/actors/{vendor_id}/inbox/", json=postfmt(activity))


def get_actor_by_id(
    client: DataLayerClient, actor_id: str
) -> Optional[as_Actor]:
    """
    Retrieves an actor by ID from the API.

    Args:
        client: DataLayerClient instance
        actor_id: Full URI of the actor

    Returns:
        as_Actor or None: The actor if found, None otherwise
    """
    actors_data = client.get("/actors/")
    for actor_data in actors_data:
        actor = as_Actor(**actor_data)
        if actor.as_id == actor_id:
            return actor
    return None


def get_item_id(item):
    """
    Extract ID from an ActivityStreams collection item.

    Per ActivityStreams spec, collection items can be:
    - Full objects (with as_id attribute)
    - Links (with as_id attribute)
    - String URIs (the string IS the ID)
    - None (for optional fields)

    Args:
        item: Collection item (object, link, string, or None)

    Returns:
        str: The ID of the item, or None if item is None
    """
    if item is None:
        return None
    if isinstance(item, str):
        return item  # String IS the ID
    return getattr(item, "as_id", None)


def verify_activity_in_inbox(
    client: DataLayerClient, actor_id: str, activity_id: str
) -> bool:
    """
    Verifies that an activity appears in an actor's inbox.

    Args:
        client: DataLayerClient instance
        actor_id: Full URI of the actor
        activity_id: Full URI of the activity to find

    Returns:
        bool: True if activity found in inbox, False otherwise

    Raises:
        ValueError: If actor not found or has no inbox
    """
    actor = get_actor_by_id(client, actor_id)
    if not actor or not actor.inbox:
        raise ValueError(f"Actor {actor_id} not found or has no inbox")

    logger.info(
        f"Actor {parse_id(actor_id)['object_id']} inbox has {len(actor.inbox.items)} items"
    )

    # Log all inbox items for debugging
    logger.debug(f"Looking for activity ID: {activity_id}")
    for item in actor.inbox.items:
        item_id = get_item_id(item)
        logger.debug(f"Inbox item ID: {item_id}")
        if item_id == activity_id:
            logger.info(f"✓ Found activity in inbox: {logfmt(item)}")
            return True

    # If not found, log what we have for debugging
    logger.warning(f"Activity {activity_id} not found in inbox")
    logger.warning(f"Inbox contains {len(actor.inbox.items)} items:")
    for item in actor.inbox.items:
        item_id = get_item_id(item)
        # Handle both string items and object items for logging
        if isinstance(item, str):
            logger.warning(f"  - {item_id} (type: string URI)")
        else:
            item_type = getattr(item, "as_type", "unknown")
            logger.warning(f"  - {item_id} (type: {item_type})")

    return False


def find_case_by_report(
    client: DataLayerClient, report_id: str
) -> Optional[VulnerabilityCase]:
    """
    Finds a VulnerabilityCase that references a specific report.

    Args:
        client: DataLayerClient instance
        report_id: Full URI of the vulnerability report

    Returns:
        VulnerabilityCase or None: The case if found, None otherwise
    """
    cases = client.get("/datalayer/VulnerabilityCases/")
    if not cases:
        return None

    for case_data in cases:
        # Handle case where API returns list of IDs instead of full objects
        if isinstance(case_data, str):
            # Fetch the full case object
            try:
                case_obj_data = client.get(f"/datalayer/{case_data}")
                case_obj = VulnerabilityCase(**case_obj_data)
            except Exception as e:
                logger.warning(f"Failed to fetch case {case_data}: {e}")
                continue
        else:
            # API returned full object
            case_obj = VulnerabilityCase(**case_data)

        # Check if this case references our report
        if case_obj.vulnerability_reports:
            # Extract IDs from reports (handle both string IDs and full objects)
            report_ids = []
            for r in case_obj.vulnerability_reports:
                if isinstance(r, str):
                    report_ids.append(r)
                elif hasattr(r, "as_id"):
                    report_ids.append(r.as_id)
                else:
                    # Fallback: try str() conversion
                    report_ids.append(str(r))

            if report_id in report_ids:
                logger.info(f"Found case for report: {logfmt(case_obj)}")
                return case_obj

    return None


def demo_validate_report(
    client: DataLayerClient, finder: as_Actor, vendor: as_Actor
):
    """
    Demonstrates the workflow where a vendor validates a report and creates a case.

    Uses RmValidateReport (Accept) activity, followed by vendor posting
    a CreateCase activity to the finder's inbox.

    This follows the "Receiver Accepts Offered Report" sequence diagram from
    docs/howto/activitypub/activities/report_vulnerability.md.

    Note: This demo uses direct inbox-to-inbox communication. The vendor posts
    the CreateCase activity directly to the finder's inbox rather than using outbox
    processing, per the Vultron prototype design (see docs/reference/inbox_handler.md).
    """
    logger.info("=" * 80)
    logger.info("DEMO 1: Validate Report and Create Case")
    logger.info("=" * 80)

    with demo_step("Step 1: Finder submits vulnerability report to vendor"):
        report = VulnerabilityReport(
            attributed_to=finder.as_id,
            content="This is a legitimate vulnerability in the authentication module.",
            name="Authentication Bypass Vulnerability",
        )
        logger.info(f"Created report: {logfmt(report)}")
        report_offer = make_submit_offer(finder, vendor, report)
        submit_to_inbox(
            client=client, vendor_id=vendor.as_id, activity=report_offer
        )
        with demo_check("Report offer and report stored"):
            verify_object_stored(client=client, obj_id=report_offer.as_id)
            verify_object_stored(client=client, obj_id=report.as_id)

    with demo_step("Step 2: Vendor validates report"):
        offer = get_offer_from_datalayer(
            client, vendor.as_id, report_offer.as_id
        )
        validate_activity = RmValidateReport(
            actor=vendor.as_id,
            object=offer.as_id,
            content="Validating the report as legitimate. Creating case.",
        )
        post_to_inbox_and_wait(client, vendor.as_id, validate_activity)
        with demo_check("ValidateReport activity stored"):
            response = client.get(f"/datalayer/{validate_activity.as_id}")
            logger.info(
                f"ValidateReport stored: {json.dumps(response, indent=2)}"
            )

    with demo_step("Step 3: Vendor creates case and notifies finder"):
        with demo_check("Case created for report"):
            case_data = find_case_by_report(client, report.as_id)
            if not case_data:
                logger.error("Could not find case related to this report.")
                raise ValueError("Could not find case related to this report.")
        create_case_activity = CreateCase(
            actor=vendor.as_id,
            as_object=case_data.as_id,
            to=[finder.as_id],
            content="Case created for your vulnerability report.",
        )
        post_to_inbox_and_wait(client, finder.as_id, create_case_activity)
        with demo_check("CreateCase activity in finder's inbox"):
            if not verify_activity_in_inbox(
                client, finder.as_id, create_case_activity.as_id
            ):
                logger.error(
                    "CreateCase activity not found in finder's inbox."
                )
                raise ValueError(
                    "CreateCase activity not found in finder's inbox."
                )

    logger.info(
        "✅ DEMO 1 COMPLETE: Report validated, case created, and finder notified via inbox."
    )


def demo_invalidate_report(
    client: DataLayerClient, finder: as_Actor, vendor: as_Actor
):
    """
    Demonstrates the workflow where a vendor invalidates a report.

    Uses RmInvalidateReport (TentativeReject) activity, followed by vendor posting
    the response directly to the finder's inbox.

    This follows the "Receiver Invalidates and Holds Offered Report" sequence diagram from
    docs/howto/activitypub/activities/report_vulnerability.md.

    Note: This demo uses direct inbox-to-inbox communication. The vendor posts
    the invalidation response directly to the finder's inbox, per the Vultron
    prototype design (see docs/reference/inbox_handler.md).
    """
    logger.info("=" * 80)
    logger.info("DEMO 2: Invalidate Report (Hold for Reconsideration)")
    logger.info("=" * 80)

    with demo_step("Step 1: Finder submits vulnerability report to vendor"):
        report = VulnerabilityReport(
            attributed_to=finder.as_id,
            content="Possible vulnerability in payment processing, needs more investigation.",
            name="Potential Payment Processing Issue",
        )
        logger.info(f"Created report: {logfmt(report)}")
        report_offer = make_submit_offer(finder, vendor, report)
        submit_to_inbox(
            client=client, vendor_id=vendor.as_id, activity=report_offer
        )
        with demo_check("Report offer and report stored"):
            verify_object_stored(client=client, obj_id=report_offer.as_id)
            verify_object_stored(client=client, obj_id=report.as_id)

    with demo_step(
        "Step 2: Vendor invalidates report (holds for reconsideration)"
    ):
        offer = get_offer_from_datalayer(
            client, vendor.as_id, report_offer.as_id
        )
        invalidate_activity = RmInvalidateReport(
            actor=vendor.as_id,
            object=offer.as_id,
            content="Invalidating the report - needs more investigation before accepting.",
        )
        post_to_inbox_and_wait(client, vendor.as_id, invalidate_activity)
        with demo_check("InvalidateReport activity stored"):
            invalidate_response = client.get(
                f"/datalayer/{invalidate_activity.as_id}"
            )
            logger.info(
                f"InvalidateReport stored: {json.dumps(invalidate_response, indent=2)}"
            )

    with demo_step("Step 3: Vendor notifies finder of invalidation"):
        invalidate_response_to_finder = RmInvalidateReport(
            actor=vendor.as_id,
            object=offer.as_id,
            to=[finder.as_id],
            content="We are holding this report for further investigation.",
        )
        post_to_inbox_and_wait(
            client, finder.as_id, invalidate_response_to_finder
        )
        with demo_check("InvalidateReport response in finder's inbox"):
            if not verify_activity_in_inbox(
                client, finder.as_id, invalidate_response_to_finder.as_id
            ):
                logger.error(
                    "TentativeReject activity not found in finder's inbox."
                )
                raise ValueError(
                    "TentativeReject activity not found in finder's inbox."
                )

    logger.info(
        "✅ DEMO 2 COMPLETE: Report invalidated and finder notified via inbox."
    )


def demo_invalidate_and_close_report(
    client: DataLayerClient, finder: as_Actor, vendor: as_Actor
):
    """
    Demonstrates the workflow where a vendor invalidates a report and closes it.

    Uses RmInvalidateReport (TentativeReject) followed by RmCloseReport (Reject) activities,
    with responses posted directly to the finder's inbox.

    This follows the "Receiver Invalidates and Closes Offered Report" sequence diagram from
    docs/howto/activitypub/activities/report_vulnerability.md.

    Note: This demo uses direct inbox-to-inbox communication. The vendor posts
    response activities directly to the finder's inbox, per the Vultron
    prototype design (see docs/reference/inbox_handler.md).
    """
    logger.info("=" * 80)
    logger.info("DEMO 3: Invalidate and Close Report")
    logger.info("=" * 80)

    with demo_step("Step 1: Finder submits vulnerability report to vendor"):
        report = VulnerabilityReport(
            attributed_to=finder.as_id,
            content="This is a false positive - not a real vulnerability.",
            name="False Positive Report",
        )
        logger.info(f"Created report: {logfmt(report)}")
        report_offer = make_submit_offer(finder, vendor, report)
        submit_to_inbox(
            client=client, vendor_id=vendor.as_id, activity=report_offer
        )
        with demo_check("Report offer and report stored"):
            verify_object_stored(client=client, obj_id=report_offer.as_id)
            verify_object_stored(client=client, obj_id=report.as_id)

    with demo_step("Step 2: Vendor invalidates and closes report"):
        offer = get_offer_from_datalayer(
            client, vendor.as_id, report_offer.as_id
        )
        invalidate_activity = RmInvalidateReport(
            actor=vendor.as_id,
            object=offer.as_id,
            content="Invalidating the report - this is a false positive.",
        )
        post_to_inbox_and_wait(client, vendor.as_id, invalidate_activity)
        close_activity = RmCloseReport(
            actor=vendor.as_id,
            object=offer.as_id,
            content="Closing the report as invalid.",
        )
        post_to_inbox_and_wait(client, vendor.as_id, close_activity)
        with demo_check("InvalidateReport and CloseReport activities stored"):
            invalidate_response = client.get(
                f"/datalayer/{invalidate_activity.as_id}"
            )
            logger.info(
                f"InvalidateReport stored: {json.dumps(invalidate_response, indent=2)}"
            )
            close_response = client.get(f"/datalayer/{close_activity.as_id}")
            logger.info(
                f"CloseReport stored: {json.dumps(close_response, indent=2)}"
            )

    with demo_step(
        "Step 3: Vendor notifies finder of invalidation and closure"
    ):
        invalidate_response_to_finder = RmInvalidateReport(
            actor=vendor.as_id,
            object=offer.as_id,
            to=[finder.as_id],
            content="This report has been invalidated as a false positive.",
        )
        post_to_inbox_and_wait(
            client,
            finder.as_id,
            invalidate_response_to_finder,
            wait_seconds=2.0,
        )
        close_response_to_finder = RmCloseReport(
            actor=vendor.as_id,
            object=offer.as_id,
            to=[finder.as_id],
            content="This report has been closed.",
        )
        post_to_inbox_and_wait(
            client, finder.as_id, close_response_to_finder, wait_seconds=2.0
        )
        with demo_check("InvalidateReport response in finder's inbox"):
            if not verify_activity_in_inbox(
                client, finder.as_id, invalidate_response_to_finder.as_id
            ):
                logger.error(
                    "TentativeReject activity not found in finder's inbox."
                )
                raise ValueError(
                    "TentativeReject activity not found in finder's inbox."
                )
        with demo_check("CloseReport response in finder's inbox"):
            if not verify_activity_in_inbox(
                client, finder.as_id, close_response_to_finder.as_id
            ):
                logger.error("Reject activity not found in finder's inbox.")
                raise ValueError(
                    "Reject activity not found in finder's inbox."
                )

    logger.info(
        "✅ DEMO 3 COMPLETE: Report invalidated, closed, and finder notified via inbox."
    )


_ALL_DEMOS: Sequence[Tuple[str, object]] = [
    ("Demo 1: Validate Report", demo_validate_report),
    ("Demo 2: Invalidate Report", demo_invalidate_report),
    ("Demo 3: Invalidate and Close Report", demo_invalidate_and_close_report),
]


def main(
    skip_health_check: bool = False,
    demos: Optional[Sequence] = None,
):
    """
    Main entry point for the demo script.

    Args:
        skip_health_check: Skip the server availability check (useful for testing)
        demos: Optional sequence of demo functions to run. Defaults to all three.
            Pass a subset (e.g. ``[demo_validate_report]``) to run only those demos.

    Runs demonstration workflows to showcase the different outcomes
    when processing vulnerability reports.
    """
    client = DataLayerClient()

    # Check if server is available before proceeding
    if not skip_health_check and not check_server_availability(client):
        logger.error("=" * 80)
        logger.error("ERROR: API server is not available")
        logger.error("=" * 80)
        logger.error(f"Cannot connect to: {client.base_url}")
        logger.error("")
        logger.error("Please ensure the Vultron API server is running.")
        logger.error("You can start it with:")
        logger.error(
            "  uv run uvicorn vultron.api.main:app --host localhost --port 7999"
        )
        logger.error("=" * 80)
        sys.exit(1)

    selected = (
        _ALL_DEMOS
        if demos is None
        else [(name, fn) for name, fn in _ALL_DEMOS if fn in demos]
    )
    total = len(selected)

    # Track errors for summary
    errors = []

    # Run selected demos with different reports, each with clean environment
    for demo_name, demo_fn in selected:
        try:
            finder, vendor, coordinator = setup_clean_environment(client)
            demo_fn(client, finder, vendor)
        except Exception as e:
            logger.error(f"{demo_name} failed: {e}", exc_info=True)
            errors.append((demo_name, str(e)))

    logger.info("=" * 80)
    logger.info("ALL DEMOS COMPLETE")
    logger.info("=" * 80)

    # Display error summary
    if errors:
        logger.error("")
        logger.error("=" * 80)
        logger.error("ERROR SUMMARY")
        logger.error("=" * 80)
        logger.error(f"Total demos: {total}")
        logger.error(f"Failed demos: {len(errors)}")
        logger.error(f"Successful demos: {total - len(errors)}")
        logger.error("")
        for demo_name, error in errors:
            logger.error(f"{demo_name}:")
            logger.error(f"  {error}")
            logger.error("")
        logger.error("=" * 80)
    else:
        logger.info("")
        logger.info(f"✓ All {total} demos completed successfully!")
        logger.info("")


def _setup_logging():
    # turn down requests logging
    logging.getLogger("requests").setLevel(logging.WARNING)

    logger = logging.getLogger()
    hdlr = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)
    logger.setLevel(logging.DEBUG)


if __name__ == "__main__":
    _setup_logging()
    main()
