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
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""
Demonstrates the workflow for initializing a vulnerability case via the Vultron API.

This demo script showcases the case initialization process:

1. Setup: submit a vulnerability report (precondition for case creation)
2. Create Case: vendor explicitly creates a VulnerabilityCase
3. Add Vendor as Participant: vendor adds themselves as case creator/owner
4. Add Report to Case: vendor links the submitted report to the case
5. Create Participant: vendor creates a CaseParticipant for the finder
6. Add Participant to Case: vendor adds the finder participant to the case
7. Show final case state

This corresponds to the workflow documented in:
    docs/howto/activitypub/activities/initialize_case.md

When run as a script, this module will:
1. Check if the API server is available
2. Reset the data layer to a clean state
3. Discover actors (finder, vendor, coordinator) via the API
4. Run the initialize_case demo workflow
5. Verify side effects in the data layer

Note on direct inbox communication:
This demo uses direct inbox-to-inbox communication between actors, per the Vultron
prototype design. Actors post activities directly to each other's inboxes.
"""

# Standard library imports
import json
import logging
import os
import sys
import time
from contextlib import contextmanager
from http import HTTPMethod
from typing import Optional, Sequence, Tuple

# Third-party imports
import requests
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

# Vultron imports
from vultron.api.v2.data.actor_io import clear_all_actor_ios, init_actor_io
from vultron.api.v2.data.utils import parse_id
from vultron.as_vocab.activities.case import AddReportToCase, CreateCase
from vultron.as_vocab.activities.case_participant import AddParticipantToCase
from vultron.as_vocab.activities.report import RmSubmitReport, RmValidateReport
from vultron.as_vocab.base.objects.activities.base import as_Activity
from vultron.as_vocab.base.objects.activities.transitive import (
    as_Create,
    as_Offer,
)
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.base.objects.base import as_Object
from vultron.as_vocab.objects.case_participant import (
    FinderReporterParticipant,
    VendorParticipant,
)
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport

logger = logging.getLogger(__name__)

# Allow BASE_URL to be overridden via environment variable for Docker deployment
BASE_URL = os.environ.get(
    "VULTRON_API_BASE_URL", "http://localhost:7999/api/v2"
)


@contextmanager
def demo_step(description: str):
    """Context manager for declaring workflow steps in demo logs.

    Logs 🚥 at INFO on entry, 🟢 at INFO on clean exit, 🔴 at ERROR on exception.
    """
    logger.info(f"🚥 {description}")
    try:
        yield
        logger.info(f"🟢 {description}")
    except Exception:
        logger.error(f"🔴 {description}")
        raise


@contextmanager
def demo_check(description: str):
    """Context manager for declaring side-effect checks in demo logs.

    Logs 📋 at INFO on entry, ✅ at INFO on clean exit, ❌ at ERROR on exception.
    """
    logger.info(f"📋 {description}")
    try:
        yield
        logger.info(f"✅ {description}")
    except Exception:
        logger.error(f"❌ {description}")
        raise


def logfmt(obj):
    """Format object for logging. Handles both Pydantic models and strings."""
    if isinstance(obj, str):
        return obj
    return obj.model_dump_json(indent=2, exclude_none=True, by_alias=True)


def postfmt(obj):
    return jsonable_encoder(obj, by_alias=True, exclude_none=True)


class DataLayerClient(BaseModel):
    base_url: str = BASE_URL

    def call(self, method: HTTPMethod, path: str, **kwargs) -> dict:
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

    if finder is None:
        raise ValueError("Finder actor not found.")
    if vendor is None:
        raise ValueError("Vendor actor not found.")
    if coordinator is None:
        raise ValueError("Coordinator actor not found.")

    return finder, vendor, coordinator


def init_actor_ios(actors: Sequence[as_Actor]) -> None:
    logger.info("Initializing inboxes and outboxes for actors...")
    for actor in actors:
        if actor is None:
            continue
        init_actor_io(actor.as_id)


def post_to_inbox_and_wait(
    client: DataLayerClient,
    actor_id: str,
    activity: as_Activity,
    wait_seconds: float = 1.0,
) -> None:
    actor_obj_id = parse_id(actor_id)["object_id"]
    logger.info(
        f"Posting activity to {actor_obj_id}'s inbox: {logfmt(activity)}"
    )
    client.post(f"/actors/{actor_obj_id}/inbox/", json=postfmt(activity))
    time.sleep(wait_seconds)


def verify_object_stored(client: DataLayerClient, obj_id: str) -> as_Object:
    obj = client.get(f"/datalayer/{obj_id}")
    reconstructed_obj = as_Object(**obj)
    logger.info(f"Verified object stored: {logfmt(reconstructed_obj)}")
    return reconstructed_obj


def get_offer_from_datalayer(
    client: DataLayerClient, vendor_id: str, offer_id: str
) -> as_Offer:
    vendor_obj_id = parse_id(vendor_id)["object_id"]
    offer_obj_id = parse_id(offer_id)["object_id"]
    offer_data = client.get(
        f"/datalayer/Actors/{vendor_obj_id}/Offers/{offer_obj_id}"
    )
    offer = as_Offer(**offer_data)
    logger.info(f"Retrieved Offer: {logfmt(offer)}")
    return offer


def log_case_state(
    client: DataLayerClient, case_id: str, label: str
) -> Optional[VulnerabilityCase]:
    """Fetch and log the current state of a case."""
    try:
        case_data = client.get(f"/datalayer/{case_id}")
        case = VulnerabilityCase(**case_data)
        logger.info(
            f"Case state [{label}]: reports={len(case.vulnerability_reports)}, "
            f"participants={len(case.case_participants)}"
        )
        logger.debug(f"Case detail [{label}]: {logfmt(case)}")
        return case
    except Exception as e:
        logger.warning(f"Could not fetch case state [{label}]: {e}")
        return None


def setup_clean_environment(
    client: DataLayerClient,
) -> Tuple[as_Actor, as_Actor, as_Actor]:
    logger.info("Setting up clean environment...")
    reset = reset_datalayer(client=client, init=True)
    logger.info(f"Reset status: {reset}")
    clear_all_actor_ios()
    finder, vendor, coordinator = discover_actors(client=client)
    init_actor_ios([finder, vendor, coordinator])
    logger.info("Clean environment setup complete.")
    return finder, vendor, coordinator


def demo_initialize_case(
    client: DataLayerClient, finder: as_Actor, vendor: as_Actor
):
    """
    Demonstrates the full case initialization workflow.

    Steps:
    1. Finder submits a vulnerability report to vendor inbox
    2. Vendor validates the report (RmValidateReport)
    3. Vendor explicitly creates a VulnerabilityCase (CreateCase)
    4. Vendor adds themselves as VendorParticipant (case creator/owner)
    5. Vendor adds the report to the case (AddReportToCase)
    6. Vendor creates a FinderReporterParticipant for the finder
    7. Vendor adds the finder participant to the case (AddParticipantToCase)
    8. Final case state is logged

    This follows the workflow in docs/howto/activitypub/activities/initialize_case.md.
    The case creator (vendor) must be added as a participant before any other
    participants, as they need to be a case participant to act on the case.
    The vendor is also the case owner, indicated by attributed_to on the case.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Initialize Case")
    logger.info("=" * 80)

    with demo_step("Step 1: Finder submits vulnerability report to vendor"):
        report = VulnerabilityReport(
            attributed_to=finder.as_id,
            content="A remote code execution vulnerability in the web framework.",
            name="Remote Code Execution Vulnerability",
        )
        logger.info(f"Created report: {logfmt(report)}")
        report_offer = RmSubmitReport(
            actor=finder.as_id,
            as_object=report,
            to=[vendor.as_id],
        )
        post_to_inbox_and_wait(client, vendor.as_id, report_offer)
        with demo_check("Report stored in data layer"):
            verify_object_stored(client, report.as_id)

    with demo_step("Step 2: Vendor validates report"):
        offer = get_offer_from_datalayer(
            client, vendor.as_id, report_offer.as_id
        )
        validate_activity = RmValidateReport(
            actor=vendor.as_id,
            object=offer.as_id,
            content="Confirmed — remote code execution via unsanitized input.",
        )
        post_to_inbox_and_wait(client, vendor.as_id, validate_activity)

    with demo_step("Step 3: Vendor creates vulnerability case"):
        case = VulnerabilityCase(
            attributed_to=vendor.as_id,
            name="RCE Case — Web Framework",
            content="Tracking the RCE vulnerability in the web framework.",
        )
        logger.info(f"Created case object: {logfmt(case)}")
        create_case_activity = CreateCase(
            actor=vendor.as_id,
            as_object=case,
        )
        post_to_inbox_and_wait(client, vendor.as_id, create_case_activity)
        with demo_check("Case stored in data layer"):
            verify_object_stored(client, case.as_id)
        with demo_check("Case state after CreateCase"):
            log_case_state(client, case.as_id, "after CreateCase")

    with demo_step("Step 4: Vendor adds themselves as case participant"):
        vendor_participant = VendorParticipant(
            attributed_to=vendor.as_id,
            context=case.as_id,
        )
        logger.info(
            f"Created vendor participant: {logfmt(vendor_participant)}"
        )
        create_vendor_participant_activity = as_Create(
            actor=vendor.as_id,
            as_object=vendor_participant,
            context=case.as_id,
        )
        post_to_inbox_and_wait(
            client, vendor.as_id, create_vendor_participant_activity
        )
        with demo_check("Vendor participant stored"):
            verify_object_stored(client, vendor_participant.as_id)

        add_vendor_participant_activity = AddParticipantToCase(
            actor=vendor.as_id,
            as_object=vendor_participant.as_id,
            target=case.as_id,
        )
        post_to_inbox_and_wait(
            client, vendor.as_id, add_vendor_participant_activity
        )
        with demo_check("Vendor added to case participant list"):
            vendor_case = log_case_state(
                client, case.as_id, "after vendor AddParticipantToCase"
            )
            if vendor_case and vendor_participant.as_id not in [
                (p.as_id if hasattr(p, "as_id") else p)
                for p in vendor_case.case_participants
            ]:
                raise ValueError(
                    f"Vendor participant '{vendor_participant.as_id}' not found in"
                    " case after AddParticipantToCase"
                )
        logger.info("Vendor added as participant to case")

    with demo_step("Step 5: Vendor links report to case"):
        add_report_activity = AddReportToCase(
            actor=vendor.as_id,
            as_object=report.as_id,
            target=case.as_id,
        )
        post_to_inbox_and_wait(client, vendor.as_id, add_report_activity)
        with demo_check("Report linked to case"):
            updated_case = log_case_state(
                client, case.as_id, "after AddReportToCase"
            )
            if updated_case and report.as_id not in [
                (r.as_id if hasattr(r, "as_id") else r)
                for r in updated_case.vulnerability_reports
            ]:
                raise ValueError(
                    f"Report '{report.as_id}' not found in case after AddReportToCase"
                )

    with demo_step("Step 6: Vendor creates finder participant"):
        participant = FinderReporterParticipant(
            attributed_to=finder.as_id,
            context=case.as_id,
        )
        logger.info(f"Created participant: {logfmt(participant)}")
        create_participant_activity = as_Create(
            actor=vendor.as_id,
            as_object=participant,
            context=case.as_id,
        )
        post_to_inbox_and_wait(
            client, vendor.as_id, create_participant_activity
        )
        with demo_check("Finder participant stored"):
            verify_object_stored(client, participant.as_id)

    with demo_step("Step 7: Vendor adds finder participant to case"):
        add_participant_activity = AddParticipantToCase(
            actor=vendor.as_id,
            as_object=participant.as_id,
            target=case.as_id,
        )
        post_to_inbox_and_wait(client, vendor.as_id, add_participant_activity)
        with demo_check("Finder participant in case participant list"):
            final_case = log_case_state(
                client, case.as_id, "after AddParticipantToCase"
            )
            if final_case and participant.as_id not in [
                (p.as_id if hasattr(p, "as_id") else p)
                for p in final_case.case_participants
            ]:
                raise ValueError(
                    f"Participant '{participant.as_id}' not found in case "
                    "after AddParticipantToCase"
                )

    logger.info(
        "✅ DEMO COMPLETE: Case initialized with vendor and finder participants."
    )


def check_server_availability(
    client: DataLayerClient, max_retries: int = 30, retry_delay: float = 1.0
) -> bool:
    url = f"{client.base_url}/health/ready"
    for attempt in range(max_retries):
        try:
            logger.debug(
                f"Checking server at: {url} (attempt {attempt + 1}/{max_retries})"
            )
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                return True
        except requests.exceptions.ConnectionError:
            pass
        except requests.exceptions.Timeout:
            pass
        except Exception:
            pass
        if attempt < max_retries - 1:
            time.sleep(retry_delay)
    return False


_ALL_DEMOS: Sequence[Tuple[str, object]] = [
    ("Demo: Initialize Case", demo_initialize_case),
]


def main(
    skip_health_check: bool = False,
    demos: Optional[Sequence] = None,
):
    """
    Main entry point for the initialize_case demo script.

    Args:
        skip_health_check: Skip server availability check (useful for testing)
        demos: Optional sequence of demo functions to run. Defaults to all.
    """
    client = DataLayerClient()

    if not skip_health_check and not check_server_availability(client):
        logger.error("=" * 80)
        logger.error("ERROR: API server is not available")
        logger.error("=" * 80)
        logger.error(f"Cannot connect to: {client.base_url}")
        logger.error("")
        logger.error("Please ensure the Vultron API server is running:")
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
    errors = []

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
    logging.getLogger("requests").setLevel(logging.WARNING)
    logger_ = logging.getLogger()
    hdlr = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    hdlr.setFormatter(formatter)
    logger_.addHandler(hdlr)
    logger_.setLevel(logging.DEBUG)


if __name__ == "__main__":
    _setup_logging()
    main()
