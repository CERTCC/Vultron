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
Shared utilities for Vultron demo scripts.

Provides context managers, HTTP client helpers, and common setup/teardown
functions used across all demo scripts (DC-02-001).
"""

# Standard library imports
import json
import logging
import os
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
from vultron.as_vocab.base.objects.activities.base import as_Activity
from vultron.as_vocab.base.objects.activities.transitive import as_Offer
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.base.objects.base import as_Object
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase

logger = logging.getLogger(__name__)

BASE_URL = os.environ.get(
    "VULTRON_API_BASE_URL", "http://localhost:7999/api/v2"
)

# Default wait time (seconds) after posting to an inbox, to allow background
# tasks to complete before checking state. Set to 0 in test environments.
DEFAULT_WAIT_SECONDS: float = 1.0


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


def logfmt(obj) -> str:
    """Format object for logging. Handles both Pydantic models and strings."""
    if isinstance(obj, str):
        return obj
    return obj.model_dump_json(indent=2, exclude_none=True, by_alias=True)


def postfmt(obj) -> dict:
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


def reset_datalayer(client: DataLayerClient, init: bool = True) -> dict:
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
    wait_seconds: float | None = None,
) -> None:
    actor_obj_id = parse_id(actor_id)["object_id"]
    logger.info(
        f"Posting activity to {actor_obj_id}'s inbox: {logfmt(activity)}"
    )
    client.post(f"/actors/{actor_obj_id}/inbox/", json=postfmt(activity))
    delay = DEFAULT_WAIT_SECONDS if wait_seconds is None else wait_seconds
    time.sleep(delay)


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


@contextmanager
def demo_environment(client: DataLayerClient):
    """Context manager providing an isolated, clean DataLayer environment.

    Sets up a clean environment on entry and tears it down on exit, even
    when the demo raises an exception (DC-03-001, DC-03-003).

    Yields:
        Tuple of (finder, vendor, coordinator) actors.
    """
    finder, vendor, coordinator = setup_clean_environment(client)
    try:
        yield finder, vendor, coordinator
    finally:
        logger.info("Tearing down demo environment...")
        reset_datalayer(client=client, init=False)
        clear_all_actor_ios()
        logger.info("Demo environment torn down.")


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
