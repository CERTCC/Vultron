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
Provides TODO writeme
"""

import json
import logging
import sys

import requests
from fastapi.encoders import jsonable_encoder

from vultron.api.v2.data.utils import parse_id
from vultron.as_vocab.activities.report import RmSubmitReport
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
    reset = call("POST", "/datalayer/reset/")
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


def _setup_logging():
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
