"""Exchange-demo environment: actor discovery, seeding, reset and logging setup."""

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

import logging
import sys
import time
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from urllib.parse import urlsplit

import httpx2 as httpx

from vultron.demo.utils.client import DataLayerClient, logfmt, reset_datalayer
from vultron.wire.as2.vocab.base.objects.actors import as_Actor

# One logger for the whole package, so log records keep its name.
logger = logging.getLogger(__package__)


def _log_discovered_actor(role: str, actor: as_Actor) -> None:
    """Log a discovered demo actor: ID at INFO, full object at DEBUG.

    The full ``logfmt()`` dump is DEBUG-only per SL-04-007; only the actor ID
    carries narrative value at INFO.
    """
    logger.info("Found %s actor: %s", role, actor.id_ or "<unknown>")
    logger.debug("Found %s actor: %s", role, logfmt(actor))


def discover_actors(
    client: DataLayerClient,
) -> tuple[as_Actor, as_Actor, as_Actor]:
    """Retrieve the Reporter, Vendor, and Coordinator actors from the DataLayer.

    Returns:
        A tuple of ``(reporter, vendor, coordinator)`` actor objects.

    Raises:
        ValueError: If any of the three expected actors are not found.
    """
    reporter = vendor = coordinator = None
    logger.info("Discovering actors in the data layer...")
    actors = client.get("/actors/")

    for actor_json in actors:
        actor = as_Actor(**actor_json)
        if actor.name and actor.name.startswith("Finn"):
            reporter = actor
            _log_discovered_actor("reporter", reporter)
        elif actor.name and actor.name.startswith("Vendor"):
            vendor = actor
            _log_discovered_actor("vendor", vendor)
        elif actor.name and actor.name.startswith("Coordinator"):
            coordinator = actor
            _log_discovered_actor("coordinator", coordinator)

    if reporter is None:
        raise ValueError("Reporter actor not found.")
    if vendor is None:
        raise ValueError("Vendor actor not found.")
    if coordinator is None:
        raise ValueError("Coordinator actor not found.")

    return reporter, vendor, coordinator


def init_actor_ios(actors: Sequence[as_Actor]) -> None:
    """No-op retained for backward compatibility.

    Inbox and outbox queues are now managed by the per-actor DataLayer
    (ADR-0012 ACT-2). No explicit initialization is required.
    """
    pass


#: The three actors every exchange demo runs with, as
#: ``(slug, name, actor_type)``.
#:
#: Slugs, not absolute URIs: ``POST /actors/`` canonicalizes a bare slug into
#: ``{base_url}actors/{slug}`` (ADR-0073#url-segment-computed-not-looked-up), so the id names the very
#: endpoint this node serves.  A hard-coded absolute id would instead name an
#: actor on some *other* node — the mistake the retired example actors made, and
#: the reason they could not be addressed here.
#:
#: The names retain the prefixes :func:`discover_actors` matches on, so a node
#: seeded this way is still introspectable by role.
_EXCHANGE_ACTORS: tuple[tuple[str, str, str], ...] = (
    ("finndervul", "Finn der Vul", "Person"),
    ("vendorco", "VendorCo", "Organization"),
    ("coordinator", "Coordinator LLC", "Organization"),
)


def seed_exchange_actors(
    client: DataLayerClient,
) -> tuple[as_Actor, as_Actor, as_Actor]:
    """Create the Reporter, Vendor and Coordinator actors on *client*'s node.

    Each gets its own store, holding its own record, which is the whole of what
    a single-container exchange demo needs: the three actors reach each other by
    URL, and delivery derives a recipient's inbox from its URI alone
    (``http_delivery``), so no actor needs a stored copy of another's record.

    Idempotent, because ``POST /actors/`` is.

    Returns:
        A tuple of ``(reporter, vendor, coordinator)`` actors as created.
    """
    seeded = tuple(
        seed_actor(
            client=client, name=name, actor_type=actor_type, actor_id=slug
        )
        for slug, name, actor_type in _EXCHANGE_ACTORS
    )
    for actor in seeded:
        logger.info("Seeded exchange actor: %s", actor.id_)
    reporter, vendor, coordinator = seeded

    # One client serves a node hosting three actors, so it cannot infer whose
    # replica a `dl_path` read is about.  Bind it to the vendor: the exchange
    # demos are receiver-side stories and the vendor is the recipient in the
    # large majority of them.  Reads about the reporter's or coordinator's replica
    # pass `actor_id=` explicitly at the call site, which is what makes those
    # reads legible as cross-actor rather than silently answering from the wrong
    # store (ADR-0073#cross-actor-access-must-be-named).
    client.actor_id = vendor.id_
    logger.debug("Exchange demo reads bound to vendor replica: %s", vendor.id_)

    return reporter, vendor, coordinator


def setup_clean_environment(
    client: DataLayerClient,
) -> tuple[as_Actor, as_Actor, as_Actor]:
    """Reset the node and provision the three default demo actors.

    Clears every store on the node, then creates the Reporter, Vendor and
    Coordinator actors.  The seeding step is explicit because clearing a node
    leaves it hosting nothing at all: under ADR-0073 there is no store that
    outlives the reset for a server-side ``init`` to populate.

    Returns:
        A tuple of ``(reporter, vendor, coordinator)`` actors.
    """
    logger.info("Setting up clean environment...")
    reset = reset_datalayer(client=client)
    logger.info("Reset status: %s", reset)
    reporter, vendor, coordinator = seed_exchange_actors(client=client)
    logger.info("Clean environment setup complete.")
    return reporter, vendor, coordinator


@contextmanager
def demo_environment(
    client: DataLayerClient,
) -> Generator[tuple[as_Actor, as_Actor, as_Actor]]:
    """Context manager providing an isolated, clean DataLayer environment.

    Sets up a clean environment on entry and tears it down on exit, even
    when the demo raises an exception (DC-03-001, DC-03-005).

    Yields:
        Tuple of (reporter, vendor, coordinator) actors.
    """
    reporter, vendor, coordinator = setup_clean_environment(client)
    try:
        yield reporter, vendor, coordinator
    finally:
        logger.info("Tearing down demo environment...")
        reset_datalayer(client=client)
        logger.info("Demo environment torn down.")


def seed_actor(
    client: DataLayerClient,
    name: str,
    actor_type: str = "Organization",
    actor_id: str | None = None,
) -> as_Actor:
    """Create or return an actor record in the remote DataLayer.

    Calls ``POST /actors/`` with the supplied parameters.  The endpoint is
    idempotent: if an actor with the same ``actor_id`` already exists it is
    returned unchanged (HTTP 200).

    Args:
        client: DataLayerClient instance pointing at the target API server.
        name: Display name for the actor.
        actor_type: ActivityStreams actor type string (default: ``"Organization"``).
        actor_id: Optional full URI for the actor.  When absent the server
            derives one from ``VULTRON_SERVER__BASE_URL``.  Must be under this
            node's authority; use :func:`seed_peer` for foreign-authority ids.

    Returns:
        The created (or pre-existing) ``as_Actor`` object.
    """
    payload: dict = {"name": name, "actor_type": actor_type}
    if actor_id is not None:
        payload["id"] = actor_id

    response_data = client.post("/actors/", json=payload)
    return as_Actor.model_validate(response_data)


def seed_peer(
    client: DataLayerClient,
    local_actor_id: str,
    peer_id: str,
    name: str,
    actor_type: str = "Organization",
) -> as_Actor:
    """Register a peer in a hosted actor's address book.

    Calls ``POST /actors/{slug}/peers/`` on the target container.  The peer is
    recorded as an address-book entry in *local_actor_id*'s own store — it is not
    created as a hosted actor (ADR-0081).  Idempotent: re-registering an already
    known peer returns the existing record with HTTP 200.

    Args:
        client: DataLayerClient instance pointing at the container that hosts
            *local_actor_id*.
        local_actor_id: Full URI of the hosted actor whose address book to update.
        peer_id: Full absolute URI of the peer actor to register.
        name: Display name for the peer.
        actor_type: ActivityStreams actor type string (default: ``"Organization"``).

    Returns:
        The created (or pre-existing) peer ``as_Actor`` object.
    """
    slug = urlsplit(local_actor_id).path.rstrip("/").rsplit("/", 1)[-1]
    payload: dict = {"id": peer_id, "name": name, "actor_type": actor_type}
    response_data = client.post(f"/actors/{slug}/peers/", json=payload)
    return as_Actor.model_validate(response_data)


def check_server_availability(
    client: DataLayerClient, max_retries: int = 30, retry_delay: float = 1.0
) -> bool:
    """Poll the API health endpoint until the server is ready or retries are exhausted.

    Args:
        client: DataLayerClient whose ``base_url`` is used to build the health URL.
        max_retries: Maximum number of polling attempts (default: 30).
        retry_delay: Seconds to wait between attempts (default: 1.0).

    Returns:
        ``True`` if the server responds with HTTP 200; ``False`` otherwise.
    """
    url = f"{client.base_url}/health/ready"
    for attempt in range(max_retries):
        try:
            logger.debug(
                "Checking server at: %s (attempt %s/%s)",
                url,
                attempt + 1,
                max_retries,
            )
            response = httpx.get(url, timeout=2)
            if response.status_code == 200:
                return True
        except httpx.ConnectError:
            pass
        except httpx.TimeoutException:
            pass
        except Exception:  # noqa: BLE001, S110  # ruff-baseline #3326
            pass
        if attempt < max_retries - 1:
            time.sleep(retry_delay)
    return False


def setup_demo_logging() -> None:
    """Configure console logging for standalone demo script execution."""
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    _logger = logging.getLogger()
    hdlr = logging.StreamHandler(sys.stdout)
    hdlr.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )
    _logger.addHandler(hdlr)
    _logger.setLevel(logging.DEBUG)
