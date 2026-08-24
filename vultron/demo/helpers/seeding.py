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
from typing import Tuple
from urllib.parse import quote

from vultron.demo.utils import (
    DataLayerClient,
    demo_check,
    demo_step,
    seed_actor,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.datalayer import DataLayer
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


def _own_actor(client: DataLayerClient, actor: as_Actor) -> as_Actor:
    """Record on *client* which actor's store its DataLayer reads address.

    Under ADR-0072 ``base_url`` names a *container*, which no longer says whose
    replica a read is about: a container hosts an actor plus any CaseActors it
    self-hosts (CP-08-003).  ``DataLayerClient.dl_path`` refuses to guess, so the
    binding has to happen where the fact is learned — here, as the container's
    *own* actor is created.  The scenario entry points cannot do it, because they
    build their clients for the health check before any actor exists.

    Deliberately not folded into :func:`seed_actor`: that helper also registers
    *peers*, so binding there would leave each client addressing whichever peer
    was seeded last — the store of an actor the container does not host, which is
    the confusion ADR-0072 decision 5 makes easy to fall into.

    Returns *actor* so the call can wrap ``seed_actor(...)`` in place.
    """
    client.actor_id = actor.id_
    logger.debug(
        "DataLayer reads via %s now address actor %s",
        client.base_url,
        actor.id_,
    )
    return actor


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
    finder = _own_actor(
        finder_client,
        seed_actor(
            client=finder_client,
            name="Finder",
            actor_type="Person",
            actor_id=reporter_actor_id,
        ),
    )
    logger.info("Finder actor seeded on Finder container: %s", finder.id_)

    vendor = _own_actor(
        vendor_client,
        seed_actor(
            client=vendor_client,
            name="Vendor",
            actor_type="Organization",
            actor_id=vendor_actor_id,
        ),
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
    finder = _own_actor(
        finder_client,
        seed_actor(
            client=finder_client,
            name="Finder",
            actor_type="Person",
            actor_id=reporter_actor_id,
        ),
    )
    logger.info("Finder actor seeded: %s", finder.id_)

    vendor = _own_actor(
        vendor_client,
        seed_actor(
            client=vendor_client,
            name="Vendor",
            actor_type="Organization",
            actor_id=vendor_actor_id,
        ),
    )
    logger.info("Vendor1 actor seeded: %s", vendor.id_)

    vendor2 = _own_actor(
        vendor2_client,
        seed_actor(
            client=vendor2_client,
            name="Vendor2",
            actor_type="Organization",
            actor_id=vendor2_actor_id,
        ),
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


def seed_containers_fvcv(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    reporter_actor_id: str | None = None,
    vendor_actor_id: str | None = None,
    coordinator_actor_id: str | None = None,
    vendor2_actor_id: str | None = None,
) -> tuple[as_Actor, as_Actor, as_Actor, as_Actor]:
    """Seed four containers for the FVCV-extension scenario.

    Containers: Finder, Vendor1 (CASE_OWNER), Coordinator, Vendor2.

    The seeding is done in two phases:

    1. Create the local actor on each container independently.
    2. Register every actor as a known peer on the other three containers.

    This function is idempotent: re-running it returns existing actors
    unchanged (the ``POST /actors/`` endpoint is idempotent).

    Args:
        finder_client: DataLayerClient connected to the Finder container.
        vendor_client: DataLayerClient connected to the Vendor1 container.
        coordinator_client: DataLayerClient connected to the Coordinator container.
        vendor2_client: DataLayerClient connected to the Vendor2 container.
        reporter_actor_id: Optional deterministic URI for the Finder actor.
        vendor_actor_id: Optional deterministic URI for the Vendor1 actor.
        coordinator_actor_id: Optional deterministic URI for the Coordinator actor.
        vendor2_actor_id: Optional deterministic URI for the Vendor2 actor.

    Returns:
        Tuple of ``(finder, vendor, coordinator, vendor2)`` ``as_Actor`` objects
        as created on their respective containers.
    """
    logger.info("Phase 1: creating local actors on each container...")
    finder = _own_actor(
        finder_client,
        seed_actor(
            client=finder_client,
            name="Finder",
            actor_type="Person",
            actor_id=reporter_actor_id,
        ),
    )
    logger.info("Finder actor seeded: %s", finder.id_)

    vendor = _own_actor(
        vendor_client,
        seed_actor(
            client=vendor_client,
            name="Vendor",
            actor_type="Organization",
            actor_id=vendor_actor_id,
        ),
    )
    logger.info("Vendor1 actor seeded: %s", vendor.id_)

    coordinator = _own_actor(
        coordinator_client,
        seed_actor(
            client=coordinator_client,
            name="Coordinator",
            actor_type="Organization",
            actor_id=coordinator_actor_id,
        ),
    )
    logger.info("Coordinator actor seeded: %s", coordinator.id_)

    vendor2 = _own_actor(
        vendor2_client,
        seed_actor(
            client=vendor2_client,
            name="Vendor2",
            actor_type="Organization",
            actor_id=vendor2_actor_id,
        ),
    )
    logger.info("Vendor2 actor seeded: %s", vendor2.id_)

    logger.info("Phase 2: registering cross-container peers...")

    # Register Vendor1, Coordinator, and Vendor2 as peers on Finder's container.
    seed_actor(
        client=finder_client,
        name="Vendor",
        actor_type="Organization",
        actor_id=vendor.id_,
    )
    seed_actor(
        client=finder_client,
        name="Coordinator",
        actor_type="Organization",
        actor_id=coordinator.id_,
    )
    seed_actor(
        client=finder_client,
        name="Vendor2",
        actor_type="Organization",
        actor_id=vendor2.id_,
    )
    logger.info(
        "Vendor1, Coordinator, and Vendor2 registered as peers on Finder container"
    )

    # Register Finder, Coordinator, and Vendor2 as peers on Vendor1's container.
    seed_actor(
        client=vendor_client,
        name="Finder",
        actor_type="Person",
        actor_id=finder.id_,
    )
    seed_actor(
        client=vendor_client,
        name="Coordinator",
        actor_type="Organization",
        actor_id=coordinator.id_,
    )
    seed_actor(
        client=vendor_client,
        name="Vendor2",
        actor_type="Organization",
        actor_id=vendor2.id_,
    )
    logger.info(
        "Finder, Coordinator, and Vendor2 registered as peers on Vendor1 container"
    )

    # Register Finder, Vendor1, and Vendor2 as peers on Coordinator's container.
    seed_actor(
        client=coordinator_client,
        name="Finder",
        actor_type="Person",
        actor_id=finder.id_,
    )
    seed_actor(
        client=coordinator_client,
        name="Vendor",
        actor_type="Organization",
        actor_id=vendor.id_,
    )
    seed_actor(
        client=coordinator_client,
        name="Vendor2",
        actor_type="Organization",
        actor_id=vendor2.id_,
    )
    logger.info(
        "Finder, Vendor1, and Vendor2 registered as peers on Coordinator container"
    )

    # Register Finder, Vendor1, and Coordinator as peers on Vendor2's container.
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
    seed_actor(
        client=vendor2_client,
        name="Coordinator",
        actor_type="Organization",
        actor_id=coordinator.id_,
    )
    logger.info(
        "Finder, Vendor1, and Coordinator registered as peers on Vendor2 container"
    )

    return finder, vendor, coordinator, vendor2


def seed_containers_fccv(
    finder_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    vendor_client: DataLayerClient,
    reporter_actor_id: str | None = None,
    c1_actor_id: str | None = None,
    c2_actor_id: str | None = None,
    vendor_actor_id: str | None = None,
) -> tuple[as_Actor, as_Actor, as_Actor, as_Actor]:
    """Seed four containers for the FCCV-handoff scenario.

    Containers: Finder (Person), C1 (Organization/Coordinator, initial
    CASE_OWNER), C2 (Organization/Coordinator, new CASE_OWNER after handoff),
    and Vendor (Organization).

    The seeding is done in two phases:

    1. Create the local actor on each container independently.
    2. Register every actor as a known peer on the other three containers.

    This function is idempotent: re-running it returns existing actors
    unchanged (the ``POST /actors/`` endpoint is idempotent).

    Args:
        finder_client: DataLayerClient connected to the Finder container.
        c1_client: DataLayerClient connected to the C1 (Coordinator1) container.
        c2_client: DataLayerClient connected to the C2 (Coordinator2) container.
        vendor_client: DataLayerClient connected to the Vendor container.
        reporter_actor_id: Optional deterministic URI for the Finder actor.
        c1_actor_id: Optional deterministic URI for the C1 actor.
        c2_actor_id: Optional deterministic URI for the C2 actor.
        vendor_actor_id: Optional deterministic URI for the Vendor actor.

    Returns:
        Tuple of ``(finder, c1, c2, vendor)`` ``as_Actor`` objects as
        created on their respective containers.
    """
    logger.info("Phase 1: creating local actors on each container...")
    finder = _own_actor(
        finder_client,
        seed_actor(
            client=finder_client,
            name="Finder",
            actor_type="Person",
            actor_id=reporter_actor_id,
        ),
    )
    logger.info("Finder actor seeded: %s", finder.id_)

    c1 = _own_actor(
        c1_client,
        seed_actor(
            client=c1_client,
            name="Coordinator1",
            actor_type="Organization",
            actor_id=c1_actor_id,
        ),
    )
    logger.info("C1 actor seeded: %s", c1.id_)

    c2 = _own_actor(
        c2_client,
        seed_actor(
            client=c2_client,
            name="Coordinator2",
            actor_type="Organization",
            actor_id=c2_actor_id,
        ),
    )
    logger.info("C2 actor seeded: %s", c2.id_)

    vendor = _own_actor(
        vendor_client,
        seed_actor(
            client=vendor_client,
            name="Vendor",
            actor_type="Organization",
            actor_id=vendor_actor_id,
        ),
    )
    logger.info("Vendor actor seeded: %s", vendor.id_)

    logger.info("Phase 2: registering cross-container peers...")

    # Register C1, C2, and Vendor as peers on Finder's container.
    seed_actor(
        client=finder_client,
        name="Coordinator1",
        actor_type="Organization",
        actor_id=c1.id_,
    )
    seed_actor(
        client=finder_client,
        name="Coordinator2",
        actor_type="Organization",
        actor_id=c2.id_,
    )
    seed_actor(
        client=finder_client,
        name="Vendor",
        actor_type="Organization",
        actor_id=vendor.id_,
    )
    logger.info("C1, C2, and Vendor registered as peers on Finder container")

    # Register Finder, C2, and Vendor as peers on C1's container.
    seed_actor(
        client=c1_client,
        name="Finder",
        actor_type="Person",
        actor_id=finder.id_,
    )
    seed_actor(
        client=c1_client,
        name="Coordinator2",
        actor_type="Organization",
        actor_id=c2.id_,
    )
    seed_actor(
        client=c1_client,
        name="Vendor",
        actor_type="Organization",
        actor_id=vendor.id_,
    )
    logger.info("Finder, C2, and Vendor registered as peers on C1 container")

    # Register Finder, C1, and Vendor as peers on C2's container.
    seed_actor(
        client=c2_client,
        name="Finder",
        actor_type="Person",
        actor_id=finder.id_,
    )
    seed_actor(
        client=c2_client,
        name="Coordinator1",
        actor_type="Organization",
        actor_id=c1.id_,
    )
    seed_actor(
        client=c2_client,
        name="Vendor",
        actor_type="Organization",
        actor_id=vendor.id_,
    )
    logger.info("Finder, C1, and Vendor registered as peers on C2 container")

    # Register Finder, C1, and C2 as peers on Vendor's container.
    seed_actor(
        client=vendor_client,
        name="Finder",
        actor_type="Person",
        actor_id=finder.id_,
    )
    seed_actor(
        client=vendor_client,
        name="Coordinator1",
        actor_type="Organization",
        actor_id=c1.id_,
    )
    seed_actor(
        client=vendor_client,
        name="Coordinator2",
        actor_type="Organization",
        actor_id=c2.id_,
    )
    logger.info("Finder, C1, and C2 registered as peers on Vendor container")

    return finder, c1, c2, vendor


def seed_containers_fcv(
    finder_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    reporter_actor_id: str | None = None,
    coordinator_actor_id: str | None = None,
    vendor_actor_id: str | None = None,
) -> tuple[as_Actor, as_Actor, as_Actor]:
    """Seed three containers for the FCV scenario: Finder, Coordinator, Vendor.

    In FCV the Coordinator receives the Finder's report and holds CASE_OWNER;
    a separate CaseActor container hosts the case-actor service actor. The
    CaseActor container does not need explicit cross-seeding here because the
    demo script registers it via peer records embedded in the Coordinator's
    docker seed-config YAML. All actor-to-actor peer registrations that the
    scenario needs are handled in Phase 2 below.

    The seeding is done in two phases:

    1. Create the local actor on each container independently.
    2. Register every actor as a known peer on the other two containers.

    This function is idempotent: re-running it returns existing actors
    unchanged (the ``POST /actors/`` endpoint is idempotent).

    Args:
        finder_client: DataLayerClient connected to the Finder container.
        coordinator_client: DataLayerClient connected to the Coordinator container.
        vendor_client: DataLayerClient connected to the Vendor container.
        reporter_actor_id: Optional deterministic URI for the Finder actor.
        coordinator_actor_id: Optional deterministic URI for the Coordinator actor.
        vendor_actor_id: Optional deterministic URI for the Vendor actor.

    Returns:
        Tuple of ``(finder, coordinator, vendor)`` ``as_Actor`` objects as
        created on their respective containers.
    """
    logger.info("Phase 1: creating local actors on each container...")
    finder = _own_actor(
        finder_client,
        seed_actor(
            client=finder_client,
            name="Finder",
            actor_type="Person",
            actor_id=reporter_actor_id,
        ),
    )
    logger.info("Finder actor seeded: %s", finder.id_)

    coordinator = _own_actor(
        coordinator_client,
        seed_actor(
            client=coordinator_client,
            name="Coordinator",
            actor_type="Organization",
            actor_id=coordinator_actor_id,
        ),
    )
    logger.info("Coordinator actor seeded: %s", coordinator.id_)

    vendor = _own_actor(
        vendor_client,
        seed_actor(
            client=vendor_client,
            name="Vendor",
            actor_type="Organization",
            actor_id=vendor_actor_id,
        ),
    )
    logger.info("Vendor actor seeded: %s", vendor.id_)

    logger.info("Phase 2: registering cross-container peers...")

    # Register Coordinator and Vendor as peers on Finder's container.
    seed_actor(
        client=finder_client,
        name="Coordinator",
        actor_type="Organization",
        actor_id=coordinator.id_,
    )
    seed_actor(
        client=finder_client,
        name="Vendor",
        actor_type="Organization",
        actor_id=vendor.id_,
    )
    logger.info(
        "Coordinator and Vendor registered as peers on Finder container"
    )

    # Register Finder and Vendor as peers on Coordinator's container.
    seed_actor(
        client=coordinator_client,
        name="Finder",
        actor_type="Person",
        actor_id=finder.id_,
    )
    seed_actor(
        client=coordinator_client,
        name="Vendor",
        actor_type="Organization",
        actor_id=vendor.id_,
    )
    logger.info(
        "Finder and Vendor registered as peers on Coordinator container"
    )

    # Register Finder and Coordinator as peers on Vendor's container.
    seed_actor(
        client=vendor_client,
        name="Finder",
        actor_type="Person",
        actor_id=finder.id_,
    )
    seed_actor(
        client=vendor_client,
        name="Coordinator",
        actor_type="Organization",
        actor_id=coordinator.id_,
    )
    logger.info(
        "Finder and Coordinator registered as peers on Vendor container"
    )

    return finder, coordinator, vendor


def seed_containers_fcvcv(
    finder_client: DataLayerClient,
    c1_client: DataLayerClient,
    v1_client: DataLayerClient,
    c2_client: DataLayerClient,
    v2_client: DataLayerClient,
    reporter_actor_id: str | None = None,
    c1_actor_id: str | None = None,
    v1_actor_id: str | None = None,
    c2_actor_id: str | None = None,
    v2_actor_id: str | None = None,
) -> tuple[as_Actor, as_Actor, as_Actor, as_Actor, as_Actor]:
    """Seed five containers for the FCVCV scenario.

    Containers: Finder (Person), Coordinator1 (Organization), Vendor1
    (Organization), Coordinator2 (Organization), VendorDeployer (Organization).

    The seeding is done in two phases:

    1. Create the local actor on each container independently.
    2. Register every actor as a known peer on the other four containers
       (N×(N-1) = 20 cross-registrations total).

    This function is idempotent: re-running it returns existing actors
    unchanged (the ``POST /actors/`` endpoint is idempotent).

    Args:
        finder_client: DataLayerClient connected to the Finder container.
        c1_client: DataLayerClient connected to the Coordinator1 container.
        v1_client: DataLayerClient connected to the Vendor1 container.
        c2_client: DataLayerClient connected to the Coordinator2 container.
        v2_client: DataLayerClient connected to the VendorDeployer container.
        reporter_actor_id: Optional deterministic URI for the Finder actor.
        c1_actor_id: Optional deterministic URI for the Coordinator1 actor.
        v1_actor_id: Optional deterministic URI for the Vendor1 actor.
        c2_actor_id: Optional deterministic URI for the Coordinator2 actor.
        v2_actor_id: Optional deterministic URI for the VendorDeployer actor.

    Returns:
        Tuple of ``(finder, c1, v1, c2, v2)`` ``as_Actor`` objects as
        created on their respective containers.
    """
    logger.info("Phase 1: creating local actors on each container...")
    finder = _own_actor(
        finder_client,
        seed_actor(
            client=finder_client,
            name="Finder",
            actor_type="Person",
            actor_id=reporter_actor_id,
        ),
    )
    logger.info("Finder actor seeded: %s", finder.id_)

    c1 = _own_actor(
        c1_client,
        seed_actor(
            client=c1_client,
            name="Coordinator1",
            actor_type="Organization",
            actor_id=c1_actor_id,
        ),
    )
    logger.info("C1 actor seeded: %s", c1.id_)

    v1 = _own_actor(
        v1_client,
        seed_actor(
            client=v1_client,
            name="Vendor1",
            actor_type="Organization",
            actor_id=v1_actor_id,
        ),
    )
    logger.info("V1 actor seeded: %s", v1.id_)

    c2 = _own_actor(
        c2_client,
        seed_actor(
            client=c2_client,
            name="Coordinator2",
            actor_type="Organization",
            actor_id=c2_actor_id,
        ),
    )
    logger.info("C2 actor seeded: %s", c2.id_)

    v2 = _own_actor(
        v2_client,
        seed_actor(
            client=v2_client,
            name="VendorDeployer",
            actor_type="Organization",
            actor_id=v2_actor_id,
        ),
    )
    logger.info("V2 actor seeded: %s", v2.id_)

    logger.info("Phase 2: registering cross-container peers...")

    # Register C1, V1, C2, and V2 as peers on Finder's container.
    seed_actor(
        client=finder_client,
        name="Coordinator1",
        actor_type="Organization",
        actor_id=c1.id_,
    )
    seed_actor(
        client=finder_client,
        name="Vendor1",
        actor_type="Organization",
        actor_id=v1.id_,
    )
    seed_actor(
        client=finder_client,
        name="Coordinator2",
        actor_type="Organization",
        actor_id=c2.id_,
    )
    seed_actor(
        client=finder_client,
        name="VendorDeployer",
        actor_type="Organization",
        actor_id=v2.id_,
    )
    logger.info("C1, V1, C2, and V2 registered as peers on Finder container")

    # Register Finder, V1, C2, and V2 as peers on C1's container.
    seed_actor(
        client=c1_client,
        name="Finder",
        actor_type="Person",
        actor_id=finder.id_,
    )
    seed_actor(
        client=c1_client,
        name="Vendor1",
        actor_type="Organization",
        actor_id=v1.id_,
    )
    seed_actor(
        client=c1_client,
        name="Coordinator2",
        actor_type="Organization",
        actor_id=c2.id_,
    )
    seed_actor(
        client=c1_client,
        name="VendorDeployer",
        actor_type="Organization",
        actor_id=v2.id_,
    )
    logger.info("Finder, V1, C2, and V2 registered as peers on C1 container")

    # Register Finder, C1, C2, and V2 as peers on V1's container.
    seed_actor(
        client=v1_client,
        name="Finder",
        actor_type="Person",
        actor_id=finder.id_,
    )
    seed_actor(
        client=v1_client,
        name="Coordinator1",
        actor_type="Organization",
        actor_id=c1.id_,
    )
    seed_actor(
        client=v1_client,
        name="Coordinator2",
        actor_type="Organization",
        actor_id=c2.id_,
    )
    seed_actor(
        client=v1_client,
        name="VendorDeployer",
        actor_type="Organization",
        actor_id=v2.id_,
    )
    logger.info("Finder, C1, C2, and V2 registered as peers on V1 container")

    # Register Finder, C1, V1, and V2 as peers on C2's container.
    seed_actor(
        client=c2_client,
        name="Finder",
        actor_type="Person",
        actor_id=finder.id_,
    )
    seed_actor(
        client=c2_client,
        name="Coordinator1",
        actor_type="Organization",
        actor_id=c1.id_,
    )
    seed_actor(
        client=c2_client,
        name="Vendor1",
        actor_type="Organization",
        actor_id=v1.id_,
    )
    seed_actor(
        client=c2_client,
        name="VendorDeployer",
        actor_type="Organization",
        actor_id=v2.id_,
    )
    logger.info("Finder, C1, V1, and V2 registered as peers on C2 container")

    # Register Finder, C1, V1, and C2 as peers on V2's container.
    seed_actor(
        client=v2_client,
        name="Finder",
        actor_type="Person",
        actor_id=finder.id_,
    )
    seed_actor(
        client=v2_client,
        name="Coordinator1",
        actor_type="Organization",
        actor_id=c1.id_,
    )
    seed_actor(
        client=v2_client,
        name="Vendor1",
        actor_type="Organization",
        actor_id=v1.id_,
    )
    seed_actor(
        client=v2_client,
        name="Coordinator2",
        actor_type="Organization",
        actor_id=c2.id_,
    )
    logger.info("Finder, C1, V1, and C2 registered as peers on V2 container")

    return finder, c1, v1, c2, v2


def reset_containers(
    labeled_clients: Sequence[tuple[str, DataLayerClient]],
    reset_fn: Callable[..., object],
) -> None:
    """Reset a set of labeled containers to a clean baseline.

    This generic helper iterates over *labeled_clients*, calling *reset_fn*
    on each, then verifies that no ``VulnerabilityCase`` records remain.

    Keeping the reset loop here (rather than in a scenario module) allows any
    multi-container scenario to reuse it without importing from
    ``fv_demo``.  Callers are responsible for supplying the concrete
    ``reset_fn`` (typically ``reset_datalayer`` from their own module namespace
    so that test-suite mock patches continue to intercept the call).

    Args:
        labeled_clients: Sequence of ``(label, client)`` pairs, one per
            container.  *label* is used only in log and assertion messages.
        reset_fn: Callable invoked as ``reset_fn(client=<DataLayerClient>)``.
            Its return value is only logged, so the annotation is
            ``Callable[..., object]`` rather than ``Any``: the ellipsis is what
            admits the keyword call, and ``object`` says the result is never
            inspected (CS-11-001).
            Pass the module-local reference so test patches take effect.

    Raises:
        AssertionError: If any container still has ``VulnerabilityCase``
            records after the reset.

    Spec: D5-2.
    """
    label = client = None
    with demo_step("Resetting actor containers to a clean baseline"):
        for label, client in labeled_clients:
            result = reset_fn(client=client)
            logger.debug("%s reset result: %s", label, result)

    with demo_check("All actor containers start with no persisted cases"):
        for label, client in labeled_clients:
            for actor_id in _actors_to_verify(label, client):
                cases = client.get(
                    client.dl_path("VulnerabilityCases/", actor_id=actor_id)
                )
                if cases:
                    raise AssertionError(
                        f"{label} container was not reset cleanly"
                        f" (actor {actor_id}): {cases}"
                    )


def _actors_to_verify(label: str, client: DataLayerClient) -> list[str]:
    """Return the actor ids whose stores must be empty after a reset.

    A DataLayer read names an actor under ADR-0072, so "are there any cases?"
    cannot be asked of a node — only of an actor.  A client bound to an actor
    answers for that actor.

    An *unbound* client used to skip the check entirely, which is exactly the
    case a first run hits: the reset had just cleared every store on the node and
    nothing verified that it worked, so a container that failed to reset started
    the scenario dirty and the failure surfaced later as an unexplained
    pre-existing case.  The node itself knows which actors it hosts, so ask it
    (``/info``) instead of skipping.  An empty list is a legitimate answer on a
    first run — the node hosts nothing yet — and not a silent skip.
    """
    if client.actor_id:
        return [client.actor_id]
    hosted = client.get("/info").get("actors") or []
    logger.debug(
        "%s container not bound to an actor; verifying the %d actor(s) it"
        " reports hosting",
        label,
        len(hosted),
    )
    return list(hosted)


def _seed_vendor_participant(case_obj, vendor_actor_id: str, dl) -> None:
    from vultron.core.models.case_participant import CaseParticipant
    from vultron.core.models.dimensions import RmDimension
    from vultron.core.models.participant_status import ParticipantStatus
    from vultron.core.states.rm import RM
    from vultron.enums.roles import CVDRole

    case_id = case_obj.id_
    if vendor_actor_id in case_obj.actor_participant_index:
        return
    # Seed vendor at RM.RECEIVED — the minimum state needed so that the
    # validate-report trigger can advance RECEIVED → VALID and emit the
    # validate_report eventType to the case-actor ledger.
    #
    # In a multi-server deployment the CaseProposal acceptance round-trip would
    # drive this transition automatically (SubmitReportReceivedUseCase creates
    # the participant at RM.RECEIVED).  In single-server demo mode that
    # round-trip is blocked, so we seed it here as the protocol would have.
    # RM.VALID must NOT be pre-seeded — validate-report must drive that
    # transition so the eventType appears in the case-actor ledger (issue #2273).
    vendor_p = CaseParticipant(
        attributed_to=vendor_actor_id,
        context=case_id,
        name=f"Vendor participant for {case_id}",
        case_roles=[CVDRole.CASE_OWNER, CVDRole.VENDOR],
        participant_statuses=[
            ParticipantStatus(
                rm=RmDimension(state=RM.RECEIVED),
                context=case_id,
                attributed_to=vendor_actor_id,
            ),
        ],
    )
    try:
        dl.create(vendor_p)
    except ValueError:
        pass
    case_obj.add_participant(vendor_p)
    logger.debug(
        "seed_case_participants_for_demo: added vendor '%s' at RM.RECEIVED",
        vendor_actor_id,
    )


def _seed_reporter_participant(
    case_obj, reporter_actor_id: str | None, dl
) -> None:
    from vultron.core.models.case_participant import CaseParticipant
    from vultron.enums.roles import CVDRole

    case_id = case_obj.id_
    if not reporter_actor_id:
        return
    if reporter_actor_id in case_obj.actor_participant_index:
        return
    reporter_p = CaseParticipant(
        attributed_to=reporter_actor_id,
        context=case_id,
        name=f"Reporter participant for {case_id}",
        case_roles=[CVDRole.REPORTER],
    )
    try:
        dl.create(reporter_p)
    except ValueError:
        pass
    case_obj.add_participant(reporter_p)
    logger.debug(
        "seed_case_participants_for_demo: added reporter '%s'",
        reporter_actor_id,
    )


def _store_for_actor(dl: "DataLayer", actor_id: str) -> "DataLayer":
    """Return *actor_id*'s own store, given any actor's *dl*.

    ``clone_for_actor`` is the only sanctioned route to another actor's store
    (ADR-0072 decision 7), so writing a record into a store other than the one
    we were handed reads as the cross-actor act it is.  Falls back to *dl* when
    the port does not offer cloning, which keeps the seeding helpers usable with
    test doubles — hence the ``getattr`` probes below rather than a bare
    attribute access, even though the annotation names the port.
    """
    if getattr(dl, "actor_id", None) == actor_id:
        return dl
    clone_for_actor = getattr(dl, "clone_for_actor", None)
    if not callable(clone_for_actor):
        return dl
    return clone_for_actor(actor_id)


def _seed_case_actor_participant(case_obj, report_id: str | None, dl) -> None:
    import uuid as _uuid

    from vultron.config.app import get_config
    from vultron.core.behaviors.case.case_actor_identity import (
        case_actor_identity,
    )
    from vultron.core.models.case_actor import CaseActor
    from vultron.core.models.case_participant import CaseParticipant
    from vultron.enums.roles import CVDRole

    case_id = case_obj.id_
    del report_id  # the CaseActor identity does not vary by report (#1872)
    case_actor_id = case_actor_identity() or case_actor_identity(
        str(get_config().server.base_url)
    )
    if not case_actor_id:
        return
    if case_actor_id in case_obj.actor_participant_index:
        return

    # Create the CaseActor Service object so that inbox delivery to the
    # CaseActor succeeds.  The record goes in the CaseActor's *own* store,
    # because that is what makes it a hosted actor: the inbox route computes the
    # canonical URI from the path segment and resolves the actor from the store
    # that URI names (ADR-0072 decision 2), so a copy sitting in the seeding
    # actor's store leaves `POST /actors/case-actor-…/inbox/` answering
    # `404 Actor not found` and the CaseProposal round-trip never starts.
    # (Pre-ADR-0072 this wrote to the one shared store, where "some row exists"
    # and "this actor is hosted" were the same thing.)
    actor_obj = CaseActor(
        id_=case_actor_id,
        name=f"CaseActor for {case_id}",
        attributed_to=case_actor_id,
        context=case_id,
    )
    own_store = _store_for_actor(dl, case_actor_id)
    try:
        own_store.create(actor_obj)
    except ValueError:
        pass

    # CaseParticipant needs a distinct ID from the Service object —
    # matching production where RegisterCaseActorParticipantNode creates
    # the participant with a separate UUID attributed to case_actor_id.
    participant_id = (
        f"urn:uuid:{_uuid.uuid5(_uuid.NAMESPACE_URL, case_actor_id)}"
    )
    manager_p = CaseParticipant(
        id_=participant_id,
        attributed_to=case_actor_id,
        context=case_id,
        name=f"CaseActor participant for {case_id}",
        case_roles=[CVDRole.COORDINATOR, CVDRole.CASE_MANAGER],
    )
    try:
        dl.create(manager_p)
    except ValueError:
        pass
    case_obj.add_participant(manager_p)
    logger.debug(
        "seed_case_participants_for_demo: added CaseActor '%s'",
        case_actor_id,
    )


def _seed_active_embargo(case_obj, dl) -> None:
    from vultron.core.models.dimensions import EmDimension
    from vultron.core.models.embargo_event import EmbargoEvent
    from vultron.core.states.em import EM

    case_id = case_obj.id_
    if case_obj.active_embargo:
        return
    embargo = EmbargoEvent(context=case_id)
    try:
        dl.create(embargo)
    except ValueError:
        pass
    case_obj.active_embargo = embargo.id_
    case_obj.current_status.em = EmDimension(state=EM.ACTIVE)
    logger.debug(
        "seed_case_participants_for_demo: seeded active embargo for '%s'",
        case_id,
    )


def seed_case_participants_for_demo(
    case_id: str,
    vendor_actor_id: str,
    reporter_actor_id: str | None,
    report_id: str | None,
    dl: CasePersistence,
) -> None:
    """Seed vendor, reporter, and CaseActor participants on an ADR-0041 case.

    Under ADR-0041, the CaseActor normally creates participants via
    ``case_proposal_received_tree`` when it accepts a ``CaseProposal``.
    This helper compensates by seeding participants directly in the DataLayer
    and setting ``EM.ACTIVE`` so the demo milestone checks pass.

    It is safe to call this multiple times for the same case — idempotency
    guards on ``actor_participant_index`` prevent duplicate records.

    Args:
        case_id: Full URI of the ``VulnerabilityCase``.
        vendor_actor_id: Full URI of the vendor actor (seeded as CASE_OWNER + VENDOR).
        reporter_actor_id: Full URI of the reporter actor, or ``None`` to skip.
        report_id: Report URI used to derive the CaseActor slug; falls back to
            ``case_id`` if ``None``.
        dl: The store to seed — required, and specifically the store of the
            actor whose replica of the case is being set up.  There is no
            default: it used to fall back to ``get_shared_dl()``, which ADR-0072
            deletes, and no defensible default replaced it.  "Which actor's
            replica?" is exactly the question a shared DataLayer let callers skip,
            and the participants seeded here are per-replica state.
    """
    from vultron.core.models.vultron_types import VulnerabilityCase

    case_obj = dl.read(case_id)
    if not isinstance(case_obj, VulnerabilityCase):
        logger.warning(
            "seed_case_participants_for_demo: case '%s' not found", case_id
        )
        return

    _seed_vendor_participant(case_obj, vendor_actor_id, dl)
    _seed_reporter_participant(case_obj, reporter_actor_id, dl)
    _seed_case_actor_participant(case_obj, report_id, dl)
    _seed_active_embargo(case_obj, dl)

    dl.save(case_obj)
