#!/usr/bin/env python

#  Copyright (c) 2025 Carnegie Mellon University and Contributors.
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

import requests
from fastapi.encoders import jsonable_encoder

from vultron.api.v2.data.utils import parse_id
from vultron.as_vocab.activities.report import (
    RmSubmitReport,
    RmCloseReport,
    RmInvalidateReport,
    RmValidateReport,
)
from vultron.as_vocab.base.objects.activities.transitive import as_Offer
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport

logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:7999/api/v2"


def call(method, path, **kwargs):
    url = f"{BASE_URL}{path}"
    logger.info(f"Calling {method.upper()} {url}")

    response = requests.request(method, url, **kwargs)

    logger.info(f"Response status: {response.status_code}")

    try:
        data = response.json()
        logger.debug(f"Response JSON: {json.dumps(data, indent=2)}")
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error: {e}", file=sys.stderr)
        print(f"Response content: {response.text}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Exception: {e}")
        logger.error(f"Response text: {response.text}")

    if not response.ok:
        logger.error(f"Error response: {response.text}")
        response.raise_for_status()

    return data


def logfmt(obj):
    return obj.model_dump_json(indent=2, exclude_none=True, by_alias=True)


def postfmt(obj):
    return jsonable_encoder(obj, by_alias=True, exclude_none=True)


def main():
    # Reset the data layer to a clean state
    reset = call("DELETE", "/datalayer/reset/", params={"init": True})
    logger.info(f"Reset status: {reset}")

    # find the finder
    finder = None
    vendor = None
    coordinator = None
    for actor in call("GET", "/actors/"):
        if actor["name"].startswith("Finn"):
            finder = as_Actor(**actor)
            logger.info(f"Found finder actor: {logfmt(finder)}")
        elif actor["name"].startswith("Vendor"):
            vendor = as_Actor(**actor)
            logger.info(f"Found vendor actor: {logfmt(vendor)}" "")
        elif actor["name"].startswith("Coordinator"):
            coordinator = as_Actor(**actor)
            logger.info(f"Found coordinator actor: {logfmt(coordinator)}")
        else:
            logger.info(f"Unrecognized actor: {logfmt(as_Actor(**actor))}")

    if finder is None:
        logger.error("Finder actor not found.")
        return

    if vendor is None:
        logger.error("Vendor actor not found.")
        return

    report = VulnerabilityReport(
        attributed_to=finder.as_id,
        content="This is a demo vulnerability report.",
        name="Demo Vulnerability Report",
    )

    # create an offer
    report_offer = RmSubmitReport(
        actor=finder.as_id,
        as_object=report,
        to=[vendor.as_id],
    )
    logger.info(f"Created report offer: {logfmt(report_offer)}")

    vendor_id = parse_id(vendor.as_id)["object_id"]

    call(
        "POST",
        f"/actors/{vendor_id}/inbox/",
        json=postfmt(report_offer),
    )

    # check side effects:
    # the offer should be in the datalayer
    _obj = call("GET", f"/datalayer/{report_offer.as_id}")
    logger.info(f"Datalayer Stored: {_obj["type"]} {_obj["id"]}")
    # the report should be in the datalayer
    _obj = call("GET", f"/datalayer/{report.as_id}")
    logger.info(f"Datalayer Stored: {_obj["type"]} {_obj["id"]}")

    offer = call(
        "GET", f"/datalayer/Actors/{vendor_id}/Offers/{report_offer.as_id}"
    )
    offer = as_Offer(**offer)
    logger.info(f"Retrieved Offer via Actor: {logfmt(offer)}")

    close_offer = RmCloseReport(
        actor=vendor.as_id,
        object=offer.as_id,
        content="Closing the report as invalid.",
    )

    logger.info(f"Closing offer: {logfmt(close_offer)}")
    call("POST", f"/actors/{vendor_id}/inbox/", json=postfmt(close_offer))

    invalidate_offer = RmInvalidateReport(
        actor=vendor.as_id,
        object=offer.as_id,
        content="Invalidating the report due to false positive.",
    )
    logger.info(f"Invalidating offer: {logfmt(invalidate_offer)}")

    call(
        "POST",
        f"/actors/{vendor_id}/inbox/",
        json=postfmt(invalidate_offer),
    )

    accept_offer = RmValidateReport(
        actor=vendor.as_id,
        object=offer.as_id,
        content="Validating the report as legitimate.",
    )
    logger.info(f"Validating offer: {logfmt(accept_offer)}")

    call(
        "POST",
        f"/actors/{vendor_id}/inbox/",
        json=postfmt(accept_offer),
    )

    # verify side effects again
    # this time,
    # the actor's outbox should have a Create activity for the case
    vendor_actor = call("GET", f"/datalayer/Actors/{vendor_id}/outbox/")
    vendor_actor = as_Actor(**vendor_actor)
    if vendor_actor.outbox is None or len(vendor_actor.outbox.items) == 0:
        logger.error("Vendor actor outbox is empty, expected Create activity.")
        return
    else:
        for item in vendor_actor.outbox.items:
            logger.info(f"Vendor outbox item: {logfmt(item)}")
    # and a case should exist


def _setup_logging():
    # turn down requests logging
    logging.getLogger("requests").setLevel(logging.WARNING)

    logger = logging.getLogger()
    hdlr = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)
    logger.setLevel(logging.INFO)


if __name__ == "__main__":
    _setup_logging()
    main()
