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

This demo script showcases the end-to-end process of submitting a vulnerability report through
the API, including actor discovery, report creation, submission via the inbox endpoint, and
verification of side effects in the data layer.

When run as a script, this module will:
1. Reset the data layer to a clean state
2. Discover actors (finder, vendor, coordinator) via the API
3. Create a vulnerability report attributed to the finder
4. Submit the report to the vendor's inbox
5. Verify that both the offer and report are stored in the data layer
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


def main():

    client = DataLayerClient()

    # Reset the data layer to a clean state
    reset = reset_datalayer(client=client, init=True)
    logger.info(f"Reset status: {reset}")

    (finder, vendor, coordinator) = discover_actors(client=client)

    init_actor_ios([finder, vendor, coordinator])

    report = build_report(finder)

    report_offer = make_submit_offer(finder, vendor, report)

    submit_to_inbox(
        client=client, vendor_id=vendor.as_id, activity=report_offer
    )

    # check side effects:
    # the offer should be in the datalayer
    verify_object_stored(client=client, obj_id=report_offer.as_id)
    # the report should be in the datalayer
    verify_object_stored(client=client, obj_id=report.as_id)

    # strip vendor.as_id to get the object ID
    vendor_obj_id = parse_id(vendor.as_id)["object_id"]
    report_offer_obj_id = parse_id(report_offer.as_id)["object_id"]

    offer = client.get(
        f"/datalayer/Actors/{vendor_obj_id}/Offers/{report_offer_obj_id}"
    )
    offer = as_Offer(**offer)
    logger.info(f"Retrieved Offer via Actor: {logfmt(offer)}")

    close_offer = RmCloseReport(
        actor=vendor.as_id,
        object=offer.as_id,
        content="Closing the report as invalid.",
    )

    logger.info(f"Closing offer: {logfmt(close_offer)}")
    client.post(f"/actors/{vendor_obj_id}/inbox/", json=postfmt(close_offer))

    invalidate_offer = RmInvalidateReport(
        actor=vendor.as_id,
        object=offer.as_id,
        content="Invalidating the report due to false positive.",
    )
    logger.info(f"Invalidating offer: {logfmt(invalidate_offer)}")

    client.post(
        f"/actors/{vendor_obj_id}/inbox/", json=postfmt(invalidate_offer)
    )

    accept_offer = RmValidateReport(
        actor=vendor.as_id,
        object=offer.as_id,
        content="Validating the report as legitimate.",
    )
    logger.info(f"Validating offer: {logfmt(accept_offer)}")

    client.post(f"/actors/{vendor_obj_id}/inbox/", json=postfmt(accept_offer))

    # verify that the accept_offer got processed correctly
    response = client.get(f"/datalayer/{accept_offer.as_id}")
    logger.info(f"ValidateReport response: {json.dumps(response, indent=2)}")

    # FIXME everything works up to here.

    # verify side effects again
    # this time,
    # the actor's outbox should have a Create activity for the case
    outbox = client.get(f"/actors/{vendor_obj_id}/outbox/")
    outbox = as_OrderedCollection(**outbox)

    logger.info(f"Vendor outbox has {len(outbox.items)} items.")
    if not outbox.items:
        logger.error("Vendor outbox is empty, expected items.")
        raise ValueError("Vendor outbox is empty, expected items.")

    found = None
    for item in outbox.items:
        logger.info(f"Vendor outbox item: {logfmt(item)}")
        if item.as_type == "Create":
            logger.info(f"Found Create activity in outbox: {logfmt(item)}")
            found = item
            break

    if not found:
        logger.error("Create activity not found in vendor outbox.")
        raise ValueError("Create activity not found in vendor outbox.")

    # the object of the Create activity should be the case
    create_id = found["id"]
    logger.info(f"Create activity object ID: {create_id}")
    case_id = found["object"]
    logger.info(f"Create activity case ID: {case_id}")

    create_obj = as_Object(**found)
    logger.info(
        f"Create activity found in vendor outbox: {logfmt(create_obj)}"
    )

    # and a case should exist in the datalayer
    case_id = create_obj.as_object

    case = client.get(f"/datalayer/{found.object}")
    case = VulnerabilityCase(**case)
    logger.info(f"Retrieved VulnerabilityCase: {logfmt(case)}")


def build_report(finder: as_Actor) -> VulnerabilityReport:
    report = VulnerabilityReport(
        attributed_to=finder.as_id,
        content="This is a demo vulnerability report.",
        name="Demo Vulnerability Report",
    )
    return report


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
