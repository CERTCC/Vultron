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
"""

import json
import logging
import sys
from http import HTTPMethod
from typing import Tuple, Sequence

import requests
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from vultron.api.v2.data.actor_io import init_actor_io
from vultron.api.v2.data.utils import parse_id
from vultron.as_vocab.activities.case import CreateCase
from vultron.as_vocab.activities.report import (
    RmSubmitReport,
    RmCloseReport,
    RmInvalidateReport,
    RmValidateReport,
)
from vultron.as_vocab.base.objects.activities.base import as_Activity
from vultron.as_vocab.base.objects.activities.transitive import as_Offer
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.base.objects.base import as_Object
from vultron.as_vocab.base.objects.collections import as_OrderedCollection
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport

logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:7999/api/v2"


def logfmt(obj):
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

    # Create a unique report for this demo
    report = VulnerabilityReport(
        attributed_to=finder.as_id,
        content="This is a legitimate vulnerability in the authentication module.",
        name="Authentication Bypass Vulnerability",
    )
    logger.info(f"Created report: {logfmt(report)}")

    # Submit the report offer
    report_offer = make_submit_offer(finder, vendor, report)
    submit_to_inbox(
        client=client, vendor_id=vendor.as_id, activity=report_offer
    )

    # Verify initial side effects
    verify_object_stored(client=client, obj_id=report_offer.as_id)
    verify_object_stored(client=client, obj_id=report.as_id)

    # Get the offer back from the data layer
    vendor_obj_id = parse_id(vendor.as_id)["object_id"]
    report_offer_obj_id = parse_id(report_offer.as_id)["object_id"]
    offer = client.get(
        f"/datalayer/Actors/{vendor_obj_id}/Offers/{report_offer_obj_id}"
    )
    offer = as_Offer(**offer)
    logger.info(f"Retrieved Offer: {logfmt(offer)}")

    # Vendor validates the report (Accept workflow)
    validate_activity = RmValidateReport(
        actor=vendor.as_id,
        object=offer.as_id,
        content="Validating the report as legitimate. Creating case.",
    )
    logger.info(
        f"Vendor posting validation to own inbox: {logfmt(validate_activity)}"
    )
    client.post(
        f"/actors/{vendor_obj_id}/inbox/", json=postfmt(validate_activity)
    )

    # Give the background handler time to process the activity
    import time

    time.sleep(1)  # Brief delay for async processing

    # Verify the validation was processed
    response = client.get(f"/datalayer/{validate_activity.as_id}")
    logger.info(f"ValidateReport stored: {json.dumps(response, indent=2)}")

    # Now vendor creates a case and posts CreateCase activity to finder's inbox
    # First, find the case that was created
    cases = client.get("/datalayer/VulnerabilityCases/")
    if not cases:
        logger.error("No cases found after validation.")
        raise ValueError("No cases found after validation.")

    # Find the case related to this report
    case_data = None
    for c in cases:
        case_obj = VulnerabilityCase(**c)
        # Check if this case references our report
        if report.as_id in [str(r) for r in (case_obj.content or [])]:
            case_data = case_obj
            break

    if not case_data:
        logger.error("Could not find case related to this report.")
        raise ValueError("Could not find case related to this report.")

    logger.info(f"Found created case: {logfmt(case_data)}")

    # Vendor posts CreateCase activity to finder's inbox
    create_case_activity = CreateCase(
        actor=vendor.as_id,
        as_object=case_data.as_id,
        to=[finder.as_id],
        content="Case created for your vulnerability report.",
    )
    logger.info(
        f"Vendor posting CreateCase to finder's inbox: {logfmt(create_case_activity)}"
    )

    finder_obj_id = parse_id(finder.as_id)["object_id"]
    client.post(
        f"/actors/{finder_obj_id}/inbox/", json=postfmt(create_case_activity)
    )

    time.sleep(1)  # Brief delay for async processing

    # Verify the CreateCase activity appears in finder's inbox
    finder_refreshed_data = client.get("/actors/")
    finder_refreshed = None
    for actor_data in finder_refreshed_data:
        actor = as_Actor(**actor_data)
        if actor.as_id == finder.as_id:
            finder_refreshed = actor
            break

    if not finder_refreshed or not finder_refreshed.inbox:
        logger.error("Could not verify finder's inbox.")
        raise ValueError("Could not verify finder's inbox.")

    logger.info(f"Finder inbox has {len(finder_refreshed.inbox.items)} items.")

    # Look for the CreateCase activity in finder's inbox
    create_case_found = False
    for item in finder_refreshed.inbox.items:
        if item.as_id == create_case_activity.as_id:
            create_case_found = True
            logger.info(
                f"✓ Found CreateCase activity in finder's inbox: {logfmt(item)}"
            )
            break

    if not create_case_found:
        logger.error("CreateCase activity not found in finder's inbox.")
        raise ValueError("CreateCase activity not found in finder's inbox.")

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

    # Create a unique report for this demo
    report = VulnerabilityReport(
        attributed_to=finder.as_id,
        content="Possible vulnerability in payment processing, needs more investigation.",
        name="Potential Payment Processing Issue",
    )
    logger.info(f"Created report: {logfmt(report)}")

    # Submit the report offer
    report_offer = make_submit_offer(finder, vendor, report)
    submit_to_inbox(
        client=client, vendor_id=vendor.as_id, activity=report_offer
    )

    # Verify initial side effects
    verify_object_stored(client=client, obj_id=report_offer.as_id)
    verify_object_stored(client=client, obj_id=report.as_id)

    # Get the offer back from the data layer
    vendor_obj_id = parse_id(vendor.as_id)["object_id"]
    report_offer_obj_id = parse_id(report_offer.as_id)["object_id"]
    offer = client.get(
        f"/datalayer/Actors/{vendor_obj_id}/Offers/{report_offer_obj_id}"
    )
    offer = as_Offer(**offer)
    logger.info(f"Retrieved Offer: {logfmt(offer)}")

    # Vendor invalidates the report (TentativeReject workflow)
    # This is posted to vendor's own inbox for internal processing
    invalidate_activity = RmInvalidateReport(
        actor=vendor.as_id,
        object=offer.as_id,
        content="Invalidating the report - needs more investigation before accepting.",
    )
    logger.info(
        f"Vendor posting invalidation to own inbox: {logfmt(invalidate_activity)}"
    )
    client.post(
        f"/actors/{vendor_obj_id}/inbox/", json=postfmt(invalidate_activity)
    )

    import time

    time.sleep(1)  # Brief delay for async processing

    # Verify the invalidation was processed
    invalidate_response = client.get(f"/datalayer/{invalidate_activity.as_id}")
    logger.info(
        f"InvalidateReport stored: {json.dumps(invalidate_response, indent=2)}"
    )

    # Now vendor posts the invalidation response to finder's inbox
    invalidate_response_to_finder = RmInvalidateReport(
        actor=vendor.as_id,
        object=offer.as_id,
        to=[finder.as_id],
        content="We are holding this report for further investigation.",
    )
    logger.info(
        f"Vendor posting TentativeReject response to finder's inbox: {logfmt(invalidate_response_to_finder)}"
    )

    finder_obj_id = parse_id(finder.as_id)["object_id"]
    client.post(
        f"/actors/{finder_obj_id}/inbox/",
        json=postfmt(invalidate_response_to_finder),
    )

    time.sleep(1)  # Brief delay for async processing

    # Verify the response appears in finder's inbox
    finder_refreshed_data = client.get("/actors/")
    finder_refreshed = None
    for actor_data in finder_refreshed_data:
        actor = as_Actor(**actor_data)
        if actor.as_id == finder.as_id:
            finder_refreshed = actor
            break

    if not finder_refreshed or not finder_refreshed.inbox:
        logger.error("Could not verify finder's inbox.")
        raise ValueError("Could not verify finder's inbox.")

    logger.info(f"Finder inbox has {len(finder_refreshed.inbox.items)} items.")

    # Look for the TentativeReject activity in finder's inbox
    response_found = False
    for item in finder_refreshed.inbox.items:
        if item.as_id == invalidate_response_to_finder.as_id:
            response_found = True
            logger.info(
                f"✓ Found TentativeReject activity in finder's inbox: {logfmt(item)}"
            )
            break

    if not response_found:
        logger.error("TentativeReject activity not found in finder's inbox.")
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

    # Create a unique report for this demo
    report = VulnerabilityReport(
        attributed_to=finder.as_id,
        content="This is a false positive - not a real vulnerability.",
        name="False Positive Report",
    )
    logger.info(f"Created report: {logfmt(report)}")

    # Submit the report offer
    report_offer = make_submit_offer(finder, vendor, report)
    submit_to_inbox(
        client=client, vendor_id=vendor.as_id, activity=report_offer
    )

    # Verify initial side effects
    verify_object_stored(client=client, obj_id=report_offer.as_id)
    verify_object_stored(client=client, obj_id=report.as_id)

    # Get the offer back from the data layer
    vendor_obj_id = parse_id(vendor.as_id)["object_id"]
    report_offer_obj_id = parse_id(report_offer.as_id)["object_id"]
    offer = client.get(
        f"/datalayer/Actors/{vendor_obj_id}/Offers/{report_offer_obj_id}"
    )
    offer = as_Offer(**offer)
    logger.info(f"Retrieved Offer: {logfmt(offer)}")

    import time

    # Vendor invalidates the report (posts to own inbox for processing)
    invalidate_activity = RmInvalidateReport(
        actor=vendor.as_id,
        object=offer.as_id,
        content="Invalidating the report - this is a false positive.",
    )
    logger.info(
        f"Vendor posting invalidation to own inbox: {logfmt(invalidate_activity)}"
    )
    client.post(
        f"/actors/{vendor_obj_id}/inbox/", json=postfmt(invalidate_activity)
    )

    time.sleep(1)  # Brief delay for async processing

    # Vendor closes the report (posts to own inbox for processing)
    close_activity = RmCloseReport(
        actor=vendor.as_id,
        object=offer.as_id,
        content="Closing the report as invalid.",
    )
    logger.info(f"Vendor posting close to own inbox: {logfmt(close_activity)}")
    client.post(
        f"/actors/{vendor_obj_id}/inbox/", json=postfmt(close_activity)
    )

    time.sleep(1)  # Brief delay for async processing

    # Verify both activities were processed
    invalidate_response = client.get(f"/datalayer/{invalidate_activity.as_id}")
    logger.info(
        f"InvalidateReport stored: {json.dumps(invalidate_response, indent=2)}"
    )

    close_response = client.get(f"/datalayer/{close_activity.as_id}")
    logger.info(f"CloseReport stored: {json.dumps(close_response, indent=2)}")

    # Now vendor posts responses to finder's inbox
    finder_obj_id = parse_id(finder.as_id)["object_id"]

    # Post TentativeReject response to finder
    invalidate_response_to_finder = RmInvalidateReport(
        actor=vendor.as_id,
        object=offer.as_id,
        to=[finder.as_id],
        content="This report has been invalidated as a false positive.",
    )
    logger.info(
        f"Vendor posting TentativeReject response to finder's inbox: {logfmt(invalidate_response_to_finder)}"
    )
    client.post(
        f"/actors/{finder_obj_id}/inbox/",
        json=postfmt(invalidate_response_to_finder),
    )

    time.sleep(1)  # Brief delay for async processing

    # Post Reject response to finder
    close_response_to_finder = RmCloseReport(
        actor=vendor.as_id,
        object=offer.as_id,
        to=[finder.as_id],
        content="This report has been closed.",
    )
    logger.info(
        f"Vendor posting Reject response to finder's inbox: {logfmt(close_response_to_finder)}"
    )
    client.post(
        f"/actors/{finder_obj_id}/inbox/",
        json=postfmt(close_response_to_finder),
    )

    time.sleep(1)  # Brief delay for async processing

    # Verify both responses appear in finder's inbox
    finder_refreshed_data = client.get("/actors/")
    finder_refreshed = None
    for actor_data in finder_refreshed_data:
        actor = as_Actor(**actor_data)
        if actor.as_id == finder.as_id:
            finder_refreshed = actor
            break

    if not finder_refreshed or not finder_refreshed.inbox:
        logger.error("Could not verify finder's inbox.")
        raise ValueError("Could not verify finder's inbox.")

    logger.info(f"Finder inbox has {len(finder_refreshed.inbox.items)} items.")

    # Look for both response activities in finder's inbox
    invalidate_found = False
    close_found = False
    for item in finder_refreshed.inbox.items:
        if item.as_id == invalidate_response_to_finder.as_id:
            invalidate_found = True
            logger.info(
                f"✓ Found TentativeReject activity in finder's inbox: {logfmt(item)}"
            )
        if item.as_id == close_response_to_finder.as_id:
            close_found = True
            logger.info(
                f"✓ Found Reject activity in finder's inbox: {logfmt(item)}"
            )

    if not invalidate_found:
        logger.error("TentativeReject activity not found in finder's inbox.")
        raise ValueError(
            "TentativeReject activity not found in finder's inbox."
        )

    if not close_found:
        logger.error("Reject activity not found in finder's inbox.")
        raise ValueError("Reject activity not found in finder's inbox.")

    logger.info(
        "✅ DEMO 3 COMPLETE: Report invalidated, closed, and finder notified via inbox."
    )


def check_server_availability(client: DataLayerClient) -> bool:
    """
    Checks if the API server is available.

    Args:
        client: DataLayerClient instance

    Returns:
        bool: True if server is available, False otherwise
    """
    try:
        # Try to access the actors endpoint as a simple health check
        # Use the client's base_url but make a direct request to avoid
        # the client's error handling
        url = f"{client.base_url}/actors/"
        logger.debug(f"Checking server availability at: {url}")
        response = requests.get(url, timeout=2)
        available = response.status_code < 500
        logger.debug(
            f"Server availability check: {available} (status: {response.status_code})"
        )
        return available
    except requests.exceptions.ConnectionError as e:
        logger.debug(f"Connection error during availability check: {e}")
        return False
    except requests.exceptions.Timeout as e:
        logger.debug(f"Timeout during availability check: {e}")
        return False
    except Exception as e:
        logger.debug(f"Unexpected error checking server: {e}")
        return False


def main(skip_health_check: bool = False):
    """
    Main entry point for the demo script.

    Args:
        skip_health_check: Skip the server availability check (useful for testing)

    Runs all three demonstration workflows to showcase the different outcomes
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
            "  uvicorn vultron.api.main:app --host localhost --port 7999"
        )
        logger.error("=" * 80)
        sys.exit(1)

    # Reset the data layer to a clean state
    reset = reset_datalayer(client=client, init=True)
    logger.info(f"Reset status: {reset}")

    # Discover actors once at the beginning
    (finder, vendor, coordinator) = discover_actors(client=client)
    init_actor_ios([finder, vendor, coordinator])

    # Run all three demos with different reports
    try:
        demo_validate_report(client, finder, vendor)
    except Exception as e:
        logger.error(f"Demo 1 failed: {e}", exc_info=True)

    try:
        demo_invalidate_report(client, finder, vendor)
    except Exception as e:
        logger.error(f"Demo 2 failed: {e}", exc_info=True)

    try:
        demo_invalidate_and_close_report(client, finder, vendor)
    except Exception as e:
        logger.error(f"Demo 3 failed: {e}", exc_info=True)

    logger.info("=" * 80)
    logger.info("ALL DEMOS COMPLETE")
    logger.info("=" * 80)


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
