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
import os
import sys
import time
from http import HTTPMethod
from typing import Optional, Sequence, Tuple

# Third-party imports
import requests
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

# Vultron imports
from vultron.api.v2.data.actor_io import clear_all_actor_ios, init_actor_io
from vultron.api.v2.data.utils import parse_id
from vultron.as_vocab.activities.case import CreateCase
from vultron.as_vocab.activities.report import (
    RmCloseReport,
    RmInvalidateReport,
    RmSubmitReport,
    RmValidateReport,
)
from vultron.as_vocab.base.objects.activities.base import as_Activity
from vultron.as_vocab.base.objects.activities.transitive import as_Offer
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.base.objects.base import as_Object
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
from vultron.scripts.initialize_case_demo import demo_check, demo_step

logger = logging.getLogger(__name__)

# Allow BASE_URL to be overridden via environment variable for Docker deployment
BASE_URL = os.environ.get(
    "VULTRON_API_BASE_URL", "http://localhost:7999/api/v2"
)


def logfmt(obj):
    """Format object for logging. Handles both Pydantic models and strings."""
    if isinstance(obj, str):
        return obj  # String URIs are already formatted
    return obj.model_dump_json(indent=2, exclude_none=True, by_alias=True)


def postfmt(obj):
    return jsonable_encoder(obj, by_alias=True, exclude_none=True)


class DataLayerClient(BaseModel):
    base_url: str = BASE_URL

    def call(self, method: HTTPMethod, path: str, **kwargs) -> dict:
        """
        Calls the API.

        Args:
            method (HTTP_METHODS): The HTTP method to use.
            path (str): The API path.
            **kwargs (dict): Additional arguments to pass to requests.

        Returns:
            dict: The JSON response.

        Raises:
            ValueError: If an unsupported HTTP method is provided.


        """
        if method.upper() not in HTTPMethod.__members__:
            raise ValueError(f"Unsupported HTTP method: {method}")

        url = f"{self.base_url}{path}"
        logger.info(f"Calling {method.upper()} {url}")
        response = requests.request(method, url, **kwargs)
        logger.info(f"Response status: {response.status_code}")

        data = {}

        try:
            data = response.json()
            logger.debug(f"Response JSON: {json.dumps(data, indent=2)}")
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            logger.error(f"Error response: {response.text}")
        except Exception as e:
            logger.error(f"Exception: {e}")
            logger.error(f"Response text: {response.text}")

        if not response.ok:
            logger.error(f"Error response: {response.text}")
            response.raise_for_status()

        return data

    def get(self, path: str, **kwargs) -> dict:
        return self.call(HTTPMethod.GET, path, **kwargs)

    def put(self, path: str, **kwargs) -> dict:
        return self.call(HTTPMethod.PUT, path, **kwargs)

    def post(self, path: str, **kwargs) -> dict:
        return self.call(HTTPMethod.POST, path, **kwargs)

    def delete(self, path: str, **kwargs) -> dict:
        return self.call(HTTPMethod.DELETE, path, **kwargs)


def reset_datalayer(client: DataLayerClient, init: bool = True):
    """
    Reset the data layer via the API.

    Args:
        client (DataLayerClient): The data layer client.
        init (bool): Whether to initialize after reset.

    Returns:
        dict: The response from the reset operation.
    """
    logger.info("Resetting data layer...")
    return client.delete("/datalayer/reset/", params={"init": init})


def discover_actors(
    client: DataLayerClient,
) -> Tuple[as_Actor, as_Actor, as_Actor]:
    finder = vendor = coordinator = None
    logger.info("Discovering actors in the data layer...")
    actors = client.get("/actors/")

    for actor_json in actors:
        actor = as_Actor(**actor_json)
        if actor.name.startswith("Finn"):
            finder = actor
            logger.info(f"Found finder actor: {logfmt(finder)}")
        elif actor.name.startswith("Vendor"):
            vendor = actor
            logger.info(f"Found vendor actor: {logfmt(vendor)}")
        elif actor.name.startswith("Coordinator"):
            coordinator = actor
            logger.info(f"Found coordinator actor: {logfmt(coordinator)}")
        else:
            logger.info(f"Unrecognized actor: {logfmt(actor)}")

    if finder is None:
        logger.error("Finder actor not found.")
        raise ValueError("Finder actor not found.")

    if vendor is None:
        logger.error("Vendor actor not found.")
        raise ValueError("Vendor actor not found.")

    if coordinator is None:
        logger.error("Coordinator actor not found.")
        raise ValueError("Coordinator actor not found.")

    return finder, vendor, coordinator


def init_actor_ios(actors: Sequence[as_Actor]) -> None:
    logger.info("Initializing inboxes and outboxes for actors...")
    for actor in actors:
        if actor is None:
            continue
        init_actor_io(actor.as_id)


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


def verify_object_stored(client: DataLayerClient, obj_id: str) -> as_Object:
    obj = client.get(f"/datalayer/{obj_id}")
    reconstructed_obj = as_Object(**obj)
    logger.info(f"Verified object stored {logfmt(reconstructed_obj)}")
    return reconstructed_obj


def get_offer_from_datalayer(
    client: DataLayerClient, vendor_id: str, offer_id: str
) -> as_Offer:
    """
    Retrieves an offer from the data layer for a specific vendor.

    Args:
        client: DataLayerClient instance
        vendor_id: Full URI of the vendor actor
        offer_id: Full URI of the offer activity

    Returns:
        as_Offer: The retrieved offer activity
    """
    vendor_obj_id = parse_id(vendor_id)["object_id"]
    offer_obj_id = parse_id(offer_id)["object_id"]
    offer_data = client.get(
        f"/datalayer/Actors/{vendor_obj_id}/Offers/{offer_obj_id}"
    )
    offer = as_Offer(**offer_data)
    logger.info(f"Retrieved Offer: {logfmt(offer)}")
    return offer


def post_to_inbox_and_wait(
    client: DataLayerClient,
    actor_id: str,
    activity: as_Activity,
    wait_seconds: float = 1.0,
) -> None:
    """
    Posts an activity to an actor's inbox and waits for async processing.

    Args:
        client: DataLayerClient instance
        actor_id: Full URI of the actor
        activity: Activity to post
        wait_seconds: Time to wait for background processing (default: 1.0)
    """
    actor_obj_id = parse_id(actor_id)["object_id"]
    logger.info(
        f"Posting activity to {actor_obj_id}'s inbox: {logfmt(activity)}"
    )
    client.post(f"/actors/{actor_obj_id}/inbox/", json=postfmt(activity))
    time.sleep(wait_seconds)


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


def check_server_availability(
    client: DataLayerClient, max_retries: int = 30, retry_delay: float = 1.0
) -> bool:
    """
    Checks if the API server is available, with retry logic for startup delays.

    Uses the /health/ready endpoint per OB-05-002 from specs/observability.md.

    Args:
        client: DataLayerClient instance
        max_retries: Maximum number of retry attempts (default: 30)
        retry_delay: Delay in seconds between retries (default: 1.0)

    Returns:
        bool: True if server is available, False otherwise
    """
    url = f"{client.base_url}/health/ready"

    for attempt in range(max_retries):
        try:
            logger.debug(
                f"Checking server availability at: {url} (attempt {attempt + 1}/{max_retries})"
            )
            response = requests.get(url, timeout=2)
            available = response.status_code == 200
            if available:
                logger.debug(
                    f"Server availability check: SUCCESS (status: {response.status_code})"
                )
                return True
            logger.debug(
                f"Server returned error status: {response.status_code}"
            )
        except requests.exceptions.ConnectionError as e:
            logger.debug(f"Connection error during availability check: {e}")
        except requests.exceptions.Timeout as e:
            logger.debug(f"Timeout during availability check: {e}")
        except Exception as e:
            logger.debug(f"Unexpected error checking server: {e}")

        if attempt < max_retries - 1:
            logger.debug(f"Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)

    logger.debug(
        f"Server availability check: FAILED after {max_retries} attempts"
    )
    return False


def setup_clean_environment(
    client: DataLayerClient,
) -> Tuple[as_Actor, as_Actor, as_Actor]:
    """
    Sets up a clean environment for a demo by resetting data layer and discovering actors.

    This method ensures each demo starts with a known clean state, preventing
    duplicate object errors and other side effects from previous demos.

    Args:
        client: DataLayerClient instance

    Returns:
        Tuple[as_Actor, as_Actor, as_Actor]: finder, vendor, coordinator actors
    """
    logger.info("Setting up clean environment...")

    # Reset the data layer to a clean state
    reset = reset_datalayer(client=client, init=True)
    logger.info(f"Reset status: {reset}")

    # Clear in-memory actor I/O state from any previous runs
    clear_all_actor_ios()

    # Discover actors
    finder, vendor, coordinator = discover_actors(client=client)

    # Initialize actor I/O
    init_actor_ios([finder, vendor, coordinator])

    logger.info("Clean environment setup complete.")
    return finder, vendor, coordinator


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
