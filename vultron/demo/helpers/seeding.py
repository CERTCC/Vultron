#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
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

"""Container-seeding and actor-lookup helpers for demo workflows.

Provides :func:`_dl_key` for safe DataLayer path encoding,
:func:`get_actor_by_id` for actor look-ups, :func:`seed_containers` for
the two-phase seeding sequence used by multi-actor scenarios, and
:func:`reset_containers` for resetting an arbitrary set of containers to
a clean baseline before a demo run.
"""

import logging
from collections.abc import Callable, Sequence
from typing import Any, Tuple
from urllib.parse import quote

from vultron.demo.utils import (
    DataLayerClient,
    demo_check,
    demo_step,
    seed_actor,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor

logger = logging.getLogger(__name__)


def _dl_key(key: str) -> str:
    """URL-encode a DataLayer key for safe embedding in an API path segment.

    Encodes characters that are illegal in URL path segments (e.g., colons in
    URN-style keys like ``urn:uuid:...``) and slashes in HTTP URL keys.
    The DataLayer ``/{key:path}`` route accepts percent-encoded slashes and
    correctly reconstructs the original key before the DataLayer lookup.
    """
    return quote(str(key), safe="")


def get_actor_by_id(client: DataLayerClient, actor_id: str) -> as_Actor:
    """Fetch an actor record from a container by its full URI.

    Args:
        client: DataLayerClient connected to the target container.
        actor_id: Full URI of the actor to fetch.

    Returns:
        The ``as_Actor`` object.

    Raises:
        ValueError: If the actor is not found.
    """
    actors = client.get("/actors/")
    for a in actors:
        actor = as_Actor.model_validate(a)
        if actor.id_ == actor_id:
            return actor
    raise ValueError(f"Actor {actor_id!r} not found in container")


def seed_containers(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    reporter_actor_id: str | None = None,
    vendor_actor_id: str | None = None,
) -> Tuple[as_Actor, as_Actor]:
    """Seed both containers: create actor records and register cross-container peers.

    The seeding is done in two phases to avoid ordering issues:

    1. Create the local actor on each container independently.
    2. Register each actor as a known peer on the other container.

    This function is idempotent: re-running it returns existing actors
    unchanged (the ``POST /actors/`` endpoint is idempotent).

    Args:
        finder_client: DataLayerClient connected to the Finder container.
        vendor_client: DataLayerClient connected to the Vendor container.
        reporter_actor_id: Optional deterministic URI for the Finder actor.
            When absent the server derives one from ``VULTRON_SERVER__BASE_URL``.
        vendor_actor_id: Optional deterministic URI for the Vendor actor.
            When absent the server derives one from ``VULTRON_SERVER__BASE_URL``.

    Returns:
        Tuple of ``(finder, vendor)`` ``as_Actor`` objects as created on their
        respective containers.
    """
    logger.info("Phase 1: creating local actors on each container...")
    finder = seed_actor(
        client=finder_client,
        name="Finder",
        actor_type="Person",
        actor_id=reporter_actor_id,
    )
    logger.info("Finder actor seeded on Finder container: %s", finder.id_)

    vendor = seed_actor(
        client=vendor_client,
        name="Vendor",
        actor_type="Organization",
        actor_id=vendor_actor_id,
    )
    logger.info("Vendor actor seeded on Vendor container: %s", vendor.id_)

    logger.info("Phase 2: registering cross-container peers...")
    seed_actor(
        client=finder_client,
        name="Vendor",
        actor_type="Organization",
        actor_id=vendor.id_,
    )
    logger.info("Vendor peer registered on Finder container: %s", vendor.id_)

    seed_actor(
        client=vendor_client,
        name="Finder",
        actor_type="Person",
        actor_id=finder.id_,
    )
    logger.info("Finder peer registered on Vendor container: %s", finder.id_)

    return finder, vendor


def seed_containers_fvv(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    reporter_actor_id: str | None = None,
    vendor_actor_id: str | None = None,
    vendor2_actor_id: str | None = None,
) -> tuple[as_Actor, as_Actor, as_Actor]:
    """Seed three containers for the FVV scenario: Finder, Vendor1, Vendor2.

    The seeding is done in two phases:

    1. Create the local actor on each container independently.
    2. Register every actor as a known peer on the other two containers.

    This function is idempotent: re-running it returns existing actors
    unchanged (the ``POST /actors/`` endpoint is idempotent).

    Args:
        finder_client: DataLayerClient connected to the Finder container.
        vendor_client: DataLayerClient connected to the Vendor1 container.
        vendor2_client: DataLayerClient connected to the Vendor2 container.
        reporter_actor_id: Optional deterministic URI for the Finder actor.
        vendor_actor_id: Optional deterministic URI for the Vendor1 actor.
        vendor2_actor_id: Optional deterministic URI for the Vendor2 actor.

    Returns:
        Tuple of ``(finder, vendor, vendor2)`` ``as_Actor`` objects as
        created on their respective containers.
    """
    logger.info("Phase 1: creating local actors on each container...")
    finder = seed_actor(
        client=finder_client,
        name="Finder",
        actor_type="Person",
        actor_id=reporter_actor_id,
    )
    logger.info("Finder actor seeded: %s", finder.id_)

    vendor = seed_actor(
        client=vendor_client,
        name="Vendor",
        actor_type="Organization",
        actor_id=vendor_actor_id,
    )
    logger.info("Vendor1 actor seeded: %s", vendor.id_)

    vendor2 = seed_actor(
        client=vendor2_client,
        name="Vendor2",
        actor_type="Organization",
        actor_id=vendor2_actor_id,
    )
    logger.info("Vendor2 actor seeded: %s", vendor2.id_)

    logger.info("Phase 2: registering cross-container peers...")

    # Register Vendor1 and Vendor2 as peers on Finder's container.
    seed_actor(
        client=finder_client,
        name="Vendor",
        actor_type="Organization",
        actor_id=vendor.id_,
    )
    seed_actor(
        client=finder_client,
        name="Vendor2",
        actor_type="Organization",
        actor_id=vendor2.id_,
    )
    logger.info("Vendor1 and Vendor2 registered as peers on Finder container")

    # Register Finder and Vendor2 as peers on Vendor1's container.
    seed_actor(
        client=vendor_client,
        name="Finder",
        actor_type="Person",
        actor_id=finder.id_,
    )
    seed_actor(
        client=vendor_client,
        name="Vendor2",
        actor_type="Organization",
        actor_id=vendor2.id_,
    )
    logger.info("Finder and Vendor2 registered as peers on Vendor1 container")

    # Register Finder and Vendor1 as peers on Vendor2's container.
    seed_actor(
        client=vendor2_client,
        name="Finder",
        actor_type="Person",
        actor_id=finder.id_,
    )
    seed_actor(
        client=vendor2_client,
        name="Vendor",
        actor_type="Organization",
        actor_id=vendor.id_,
    )
    logger.info("Finder and Vendor1 registered as peers on Vendor2 container")

    return finder, vendor, vendor2


def reset_containers(
    labeled_clients: Sequence[tuple[str, DataLayerClient]],
    reset_fn: Callable[..., Any],
) -> None:
    """Reset a set of labeled containers to a clean baseline.

    This generic helper iterates over *labeled_clients*, calling *reset_fn*
    on each, then verifies that no ``VulnerabilityCase`` records remain.

    Keeping the reset loop here (rather than in a scenario module) allows any
    multi-container scenario to reuse it without importing from
    ``two_actor_demo``.  Callers are responsible for supplying the concrete
    ``reset_fn`` (typically ``reset_datalayer`` from their own module namespace
    so that test-suite mock patches continue to intercept the call).

    Args:
        labeled_clients: Sequence of ``(label, client)`` pairs, one per
            container.  *label* is used only in log and assertion messages.
        reset_fn: Callable with the signature
            ``reset_fn(client: DataLayerClient, init: bool) -> Any``.
            Pass the module-local reference so test patches take effect.

    Raises:
        AssertionError: If any container still has ``VulnerabilityCase``
            records after the reset.

    Spec: D5-2.
    """
    with demo_step("Resetting actor containers to a clean baseline"):
        for label, client in labeled_clients:
            result = reset_fn(client=client, init=False)
            logger.debug("%s reset result: %s", label, result)

    with demo_check("All actor containers start with no persisted cases"):
        for label, client in labeled_clients:
            cases = client.get("/datalayer/VulnerabilityCases/")
            if cases:
                raise AssertionError(
                    f"{label} container was not reset cleanly: {cases}"
                )
