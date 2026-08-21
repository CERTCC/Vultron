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
import sys
import time
from contextlib import contextmanager
from http import HTTPMethod
from typing import Any, Generator, Optional, Sequence, Tuple, cast

# Third-party imports
import httpx2 as httpx
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

# Vultron imports
from vultron.adapters.utils import parse_id
from vultron.errors import DemoFailureError
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)

# Module-level failure accumulator.  reset_demo_failures() clears it at the
# start of each scenario; assert_demo_success() raises DemoFailureError if
# any failures were recorded.  See specs/demo-ci.yaml DEMOCI-01-003.
_demo_failures: list[str] = []


def reset_demo_failures() -> None:
    """Clear the demo failure accumulator.

    Call at the start of each scenario entry point to ensure failures from a
    previous run do not pollute the current one.  See DEMOCI-01-003.
    """
    _demo_failures.clear()


def assert_demo_success() -> None:
    """Raise DemoFailureError if any demo step or check failures were recorded.

    Call at the end of each scenario entry point.  Raises with the full list
    of accumulated failure messages so that ``docker compose --exit-code-from``
    can surface the non-zero exit to CI.  See DEMOCI-01-001, DEMOCI-01-003.
    """
    if _demo_failures:
        raise DemoFailureError(
            f"{len(_demo_failures)} demo failure(s)",
            failures=list(_demo_failures),
        )


def _note_accumulated_failures(exc: BaseException) -> None:
    """Attach any accumulated demo failures to *exc* as notes.

    On the failing path the caller lets the original exception propagate
    rather than calling ``assert_demo_success()``, which would replace the
    real cause with a generic ``DemoFailureError``.  The accumulated soft
    failures are still worth reporting, so they ride along as exception notes.
    """
    try:
        assert_demo_success()
    except DemoFailureError as accumulated:
        for failure in accumulated.failures:
            exc.add_note(failure)


BASE_URL = os.environ.get(
    "VULTRON_API_BASE_URL", "http://localhost:7999/api/v2"
)

# Default wait time (seconds) after posting to an inbox, to allow background
# tasks to complete before checking state. Set to 0 in test environments.
DEFAULT_WAIT_SECONDS: float = 1.0


def ref_id(value: object) -> str | None:
    """Return the ID of a string-or-AS2 reference, if present."""
    if isinstance(value, str):
        return value
    if value is None:
        return None
    return getattr(value, "id_", None)


@contextmanager
def _demo_accumulate(
    description: str,
    start: str,
    on_pass: str,
    on_fail: str,
    prefix: str,
) -> Generator[None, None, None]:
    """Shared try/except/log backbone for demo context managers.

    Logs *start* on entry, *on_pass* on clean exit, *on_fail* + exc on
    exception.  Exceptions are caught, logged, appended to
    ``_demo_failures`` as ``"<prefix>: <description> — <exc>"``, and
    suppressed so callers continue after the block.
    """
    logger.info(f"{start} {description}")
    try:
        yield
        logger.info(f"{on_pass} {description}")
    except Exception as exc:
        logger.error(f"{on_fail} {description}: {exc}", exc_info=True)
        _demo_failures.append(f"{prefix}: {description} — {exc}")


@contextmanager
def demo_step(description: str) -> Generator[None, None, None]:
    """Context manager for declaring workflow steps in demo logs.

    Logs 🚥 at INFO on entry, 🟢 at INFO on clean exit, 🔴 at ERROR on
    exception.  On exception the failure is appended to the module-level
    ``_demo_failures`` accumulator and execution continues (no re-raise).
    Call ``assert_demo_success()`` at the end of the scenario to surface
    accumulated failures.  See DEMOCI-01-003, DEMOCI-01-004.
    """
    with _demo_accumulate(description, "🚥", "🟢", "🔴", "STEP FAILED"):
        yield


@contextmanager
def demo_check(description: str) -> Generator[None, None, None]:
    """Context manager for declaring side-effect checks in demo logs.

    Logs 📋 at INFO on entry, ✅ at INFO on clean exit, ❌ at ERROR on
    exception.  On exception the failure is appended to the module-level
    ``_demo_failures`` accumulator and execution continues (no re-raise).
    Call ``assert_demo_success()`` at the end of the scenario to surface
    accumulated failures.  See DEMOCI-01-003, DEMOCI-01-004.
    """
    with _demo_accumulate(description, "📋", "✅", "❌", "CHECK FAILED"):
        yield


@contextmanager
def demo_gate(description: str) -> Generator[None, None, None]:
    """Context manager for causal preconditions in demo scripts.

    Place the precondition check **and the steps that depend on it** inside
    this block.  If the precondition raises, Python immediately exits the
    ``with`` body — the remaining dependent steps are skipped.  The failure
    is recorded in the accumulator exactly as ``demo_check`` does
    (DEMOCI-01-003 is preserved), and the exception is suppressed so that
    execution continues *after* the block.

    **Scoping model — nested block**:

    Put the gating assertion at the top of the body, followed directly by
    the dependent steps:

    ```python
    with demo_gate("vendor has reached RM.VALID"):
        assert vendor_rm_state == "VALID"    # precondition: raises on fail
        with demo_step("5. Engage case"):    # skipped when gate fails
            engage_case(...)
        with demo_step("6. Do next thing"):  # also skipped when gate fails
            do_next(...)
    # code here always runs — gate accumulates and suppresses the failure
    ```

    Use ``demo_check`` for a standalone verification assertion that should
    *not* block subsequent steps.  Use ``demo_gate`` when continuing after a
    failed precondition would produce meaningless secondary failures that bury
    the real cause.

    See DEMOCI-01-007, EDF-06-005, ADR-0058.
    """
    with _demo_accumulate(description, "🚧", "🔓", "🔒", "GATE FAILED"):
        yield


def logfmt(obj: object) -> str:
    """Format object for logging. Handles both Pydantic models and strings."""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, BaseModel):
        return obj.model_dump_json(indent=2, exclude_none=True, by_alias=True)
    return str(obj)


def postfmt(obj: object) -> dict[str, object]:
    """Serialize a Pydantic model (or plain object) to a JSON-encodable dict for POST bodies."""
    return cast(
        dict[str, object],
        jsonable_encoder(obj, by_alias=True, exclude_none=True),
    )


class DataLayerClient(BaseModel):
    """HTTP client for the Vultron DataLayer REST API.

    Wraps ``httpx`` with convenience methods for GET, PUT, POST, and DELETE
    calls to the DataLayer endpoint, with automatic JSON parsing and error logging.

    ``base_url`` addresses a *container*; ``actor_id`` names which of the actors
    that container hosts a DataLayer read is about.  Both are needed under
    ADR-0070: a container hosts an actor plus the CaseActors it self-hosts
    (CP-08-003), so ``/datalayer/{case_id}`` alone no longer says whose replica
    to read.  Use :meth:`dl_path` to build inspection paths rather than
    hand-writing ``/datalayer/...``.
    """

    base_url: str = BASE_URL
    #: Canonical URI of the actor whose store this client inspects.  Optional so
    #: that clients used only for non-DataLayer endpoints (health, info, inbox)
    #: keep working unchanged; :meth:`dl_path` raises when it is needed and
    #: absent, rather than silently reading some other actor's replica.
    actor_id: str | None = None
    #: Per-request HTTP timeout (seconds).  Generous relative to httpx's 5s
    #: default so a single GET against a container that is busy draining its
    #: outbox (delivery retry/backoff can add several seconds under CI load)
    #: does not fail with a bare read timeout.  Callers may override per-call
    #: by passing ``timeout=`` in kwargs.
    timeout: float = 30.0

    def dl_path(self, key: str = "", actor_id: str | None = None) -> str:
        """Return the actor-scoped DataLayer inspection path for *key*.

        Args:
            key: Path suffix after ``/datalayer/`` — an object id, a
                ``VulnerabilityCases/`` style collection, or ``""`` for the
                whole-store view.
            actor_id: Override the client's own ``actor_id``.  Needed when a
                container hosts more than one actor and the read is about a
                non-primary one — typically a self-hosted CaseActor.

        Returns:
            ``/actors/{segment}/datalayer/{key}``, where *segment* is the
            actor's final URI path segment.  The server recomputes the canonical
            URI from its own base URL (ADR-0070), which is why the short segment
            is what travels — the same convention already used for inbox and
            trigger paths.

        Raises:
            ValueError: When no actor is available.  Failing here is deliberate:
                defaulting to *some* actor would silently report another
                replica's state and could let an ADR-0058 causal gate pass on
                the wrong actor's committed state.
        """
        actor = actor_id or self.actor_id
        if not actor:
            raise ValueError(
                "DataLayerClient.dl_path requires an actor_id: DataLayer reads "
                "are per-actor (ADR-0070). Set actor_id on the client or pass "
                "it explicitly."
            )
        segment = parse_id(actor)["object_id"]
        return f"/actors/{segment}/datalayer/{key}"

    def call(self, method: HTTPMethod, path: str, **kwargs: Any) -> Any:
        """Make an HTTP request to the DataLayer API.

        Args:
            method: HTTP method (GET, PUT, POST, DELETE).
            path: API path relative to ``base_url``.
            **kwargs: Additional keyword arguments forwarded to ``httpx.request``.

        Returns:
            Parsed JSON response body.  Most endpoints return a ``dict``, but
            list endpoints (e.g. the case-ledger endpoint) return a ``list``.

        Raises:
            httpx.HTTPStatusError: When the response status is not OK.
        """
        if method.upper() not in HTTPMethod.__members__:
            raise ValueError(f"Unsupported HTTP method: {method}")

        url = f"{self.base_url}{path}"
        logger.debug(f"Calling {method.upper()} {url}")
        kwargs.setdefault("timeout", self.timeout)
        response = httpx.request(method, url, **kwargs)
        logger.debug(f"Response status: {response.status_code}")

        data: Any = {}
        try:
            data = response.json()
            logger.debug(f"Response JSON: {json.dumps(data, indent=2)}")
        except ValueError as e:
            logger.error(f"Exception: {e}")
            logger.error(f"Response text: {response.text}")

        if response.status_code == 404:
            logger.error(
                f"HTTP 404 from {response.url} ({method.upper()} {path})"
            )

        if not response.is_success:
            logger.error(f"Error response: {response.text}")
            response.raise_for_status()

        return data

    def get(self, path: str, **kwargs: Any) -> dict:
        """Send an HTTP GET request."""
        return cast(dict, self.call(HTTPMethod.GET, path, **kwargs))

    def get_list(self, path: str, **kwargs: Any) -> list[Any]:
        """Send an HTTP GET request that expects a JSON array response.

        Args:
            path: API path relative to ``base_url``.
            **kwargs: Additional keyword arguments forwarded to ``httpx.request``.

        Returns:
            Parsed JSON response body as a list.

        Raises:
            ValueError: When the response body is not a JSON array.
            httpx.HTTPStatusError: When the response status is not OK.
        """
        data = self.call(HTTPMethod.GET, path, **kwargs)
        if not isinstance(data, list):
            raise ValueError(
                f"Expected JSON array from GET {path}, "
                f"got {type(data).__name__}"
            )
        return data

    def put(self, path: str, **kwargs: Any) -> dict:
        """Send an HTTP PUT request."""
        return cast(dict, self.call(HTTPMethod.PUT, path, **kwargs))

    def post(self, path: str, **kwargs: Any) -> dict:
        """Send an HTTP POST request."""
        return cast(dict, self.call(HTTPMethod.POST, path, **kwargs))

    def delete(self, path: str, **kwargs: Any) -> dict:
        """Send an HTTP DELETE request."""
        return cast(dict, self.call(HTTPMethod.DELETE, path, **kwargs))


def reset_datalayer(client: DataLayerClient) -> dict:
    """Clear every store on the node *client* addresses, via the API.

    Clearing only clears.  The former ``init`` flag asked the server to seed
    default actors as part of the reset; provisioning is now the caller's job,
    via :func:`seed_exchange_actors` or :func:`seed_actor` (see the route
    docstring for why per-actor storage made the server-side seed unworkable).

    Args:
        client: DataLayerClient instance.
    """
    logger.debug("Resetting data layer...")
    # Node-level, not actor-scoped: resetting is an operation on the node's
    # storage rather than a read of one actor's replica, so it deliberately does
    # *not* go through `dl_path` (ADR-0070 moved it to /admin/).
    return client.delete("/admin/datalayer/reset/")


def _log_discovered_actor(role: str, actor: as_Actor) -> None:
    """Log a discovered demo actor: ID at INFO, full object at DEBUG.

    The full ``logfmt()`` dump is DEBUG-only per SL-04-007; only the actor ID
    carries narrative value at INFO.
    """
    logger.info("Found %s actor: %s", role, actor.id_ or "<unknown>")
    logger.debug("Found %s actor: %s", role, logfmt(actor))


def discover_actors(
    client: DataLayerClient,
) -> Tuple[as_Actor, as_Actor, as_Actor]:
    """Retrieve the Finder, Vendor, and Coordinator actors from the DataLayer.

    Returns:
        A tuple of ``(finder, vendor, coordinator)`` actor objects.

    Raises:
        ValueError: If any of the three expected actors are not found.
    """
    finder = vendor = coordinator = None
    logger.info("Discovering actors in the data layer...")
    actors = client.get("/actors/")

    for actor_json in actors:
        actor = as_Actor(**actor_json)
        if actor.name and actor.name.startswith("Finn"):
            finder = actor
            _log_discovered_actor("finder", finder)
        elif actor.name and actor.name.startswith("Vendor"):
            vendor = actor
            _log_discovered_actor("vendor", vendor)
        elif actor.name and actor.name.startswith("Coordinator"):
            coordinator = actor
            _log_discovered_actor("coordinator", coordinator)

    if finder is None:
        raise ValueError("Finder actor not found.")
    if vendor is None:
        raise ValueError("Vendor actor not found.")
    if coordinator is None:
        raise ValueError("Coordinator actor not found.")

    return finder, vendor, coordinator


def init_actor_ios(actors: Sequence[as_Actor]) -> None:
    """No-op retained for backward compatibility.

    Inbox and outbox queues are now managed by the per-actor DataLayer
    (ADR-0012 ACT-2). No explicit initialization is required.
    """
    pass


def post_to_inbox_and_wait(
    client: DataLayerClient,
    actor_id: str,
    activity: as_Activity,
    wait_seconds: float | None = None,
) -> None:
    """POST an activity to an actor's inbox and pause to let background tasks complete.

    Args:
        client: DataLayerClient instance.
        actor_id: ID of the target actor.
        activity: ActivityStreams activity to deliver.
        wait_seconds: Seconds to sleep after posting; defaults to ``DEFAULT_WAIT_SECONDS``.
    """
    actor_obj_id = parse_id(actor_id)["object_id"]
    logger.debug(
        f"Posting activity to {actor_obj_id}'s inbox: {logfmt(activity)}"
    )
    client.post(f"/actors/{actor_obj_id}/inbox/", json=postfmt(activity))
    delay = DEFAULT_WAIT_SECONDS if wait_seconds is None else wait_seconds
    time.sleep(delay)


def post_to_trigger(
    client: DataLayerClient,
    actor_id: str,
    behavior: str,
    body: dict,
    path_prefix: str = "trigger",
) -> dict:
    """POST to a trigger endpoint and return the response body.
    proactively (e.g. validate-report, engage-case) rather than
    reacting to an inbound activity.

    Args:
        client: DataLayerClient instance.
        actor_id: Full URI of the actor initiating the behavior.
        behavior: Kebab-case behavior name (e.g. ``"validate-report"``).
        body: Request body dict (e.g. ``{"offer_id": "..."}``).
        path_prefix: URL segment before the behavior name.  Use
            ``"trigger"`` (default) for standard trigger endpoints and
            ``"demo"`` for demo-only endpoints such as
            ``add-note-to-case`` and ``sync-log-entry``.

    Returns:
        Response dict from the trigger endpoint.
    """
    actor_obj_id = parse_id(actor_id)["object_id"]
    logger.info(
        "Posting trigger '%s' for actor '%s': %s",
        behavior,
        actor_obj_id,
        body,
    )
    return client.post(
        f"/actors/{actor_obj_id}/{path_prefix}/{behavior}", json=body
    )


def verify_object_stored(
    client: DataLayerClient, obj_id: str, actor_id: str | None = None
) -> as_Object:
    """Fetch an object from the DataLayer by ID and verify it is present.

    Logs the stored representation so all fields are visible. Nested objects
    are stored as ID-string references (not inline copies); the log therefore
    shows ID strings for nested fields such as ``object_``, ``target``, etc.
    To inspect a nested object, call ``verify_object_stored`` again with the
    nested object's own ID.

    Args:
        client: DataLayerClient for the container to read from.
        obj_id: Id of the object to fetch.
        actor_id: Whose replica to look in.  Defaults to *client*'s own actor.
            "Is this object stored?" has no answer under ADR-0070 without naming
            an actor, so pass this whenever the read is about an actor other than
            the one the client is bound to — typically because the activity was
            delivered to a different recipient's inbox.

    Returns:
        The retrieved ``as_Object``.

    Raises:
        httpx.HTTPStatusError: If the object is not found.
    """

    def _drop_nulls(value: object) -> object:
        if isinstance(value, dict):
            return {
                k: _drop_nulls(v) for k, v in value.items() if v is not None
            }
        if isinstance(value, list):
            return [_drop_nulls(item) for item in value]
        return value

    obj = client.get(client.dl_path(obj_id, actor_id=actor_id))
    filtered = _drop_nulls(obj)
    logger.info(
        "Stored record (nested objects shown as ID references): %s",
        json.dumps(filtered, indent=2, default=str),
    )
    return as_Object(**obj)


def get_offer_from_datalayer(
    client: DataLayerClient, vendor_id: str, offer_id: str
) -> as_Offer:
    """Retrieve a specific Offer from a vendor's DataLayer store.

    Args:
        client: DataLayerClient instance.
        vendor_id: ID of the vendor actor that owns the offer.  Names the store
            to read, so the lookup does not depend on *client*'s own binding.
        offer_id: ID of the offer to retrieve.

    Returns:
        The retrieved offer as :class:`as_Offer`.
    """
    offer_obj_id = parse_id(offer_id)["object_id"]
    # `Offers/{id}` sits under the actor-scoped prefix, so the owning actor is
    # already in the path.  The old key nested a second `Actors/{segment}/`
    # inside it, which addressed nothing once `dl_path` supplied the prefix.
    offer_data = client.get(
        client.dl_path(f"Offers/{offer_obj_id}", actor_id=vendor_id)
    )
    raw = as_Offer(**offer_data)
    logger.info(f"Retrieved Offer: {logfmt(raw)}")
    return raw


def log_case_state(
    client: DataLayerClient,
    case_id: str,
    label: str,
    actor_id: str | None = None,
) -> Optional[as_VulnerabilityCase]:
    """Fetch and log the current state of a case.

    Args:
        client: DataLayerClient for the container to read from.
        case_id: Id of the case to read.
        label: Short description of the point in the flow, for the log line.
        actor_id: Whose replica to read.  Defaults to *client*'s own actor.
            Participants hold their own replicas of a case (PCR), so the state
            logged is always some named actor's view of it, never "the" state.
    """
    try:
        case_data = client.get(client.dl_path(case_id, actor_id=actor_id))
        case = as_VulnerabilityCase(**case_data)
        logger.info(
            f"Case state [{label}]: reports={len(case.vulnerability_reports)}, "
            f"participants={len(case.case_participants)}"
        )
        logger.debug(f"Case detail [{label}]: {logfmt(case)}")
        return case
    except Exception as e:
        logger.warning(f"Could not fetch case state [{label}]: {e}")
        return None


#: The three actors every exchange demo runs with, as
#: ``(slug, name, actor_type)``.
#:
#: Slugs, not absolute URIs: ``POST /actors/`` canonicalizes a bare slug into
#: ``{base_url}actors/{slug}`` (ADR-0070 decision 2), so the id names the very
#: endpoint this node serves.  A hard-coded absolute id would instead name an
#: actor on some *other* node — the mistake the retired example actors made, and
#: the reason they could not be addressed here.
#:
#: The names retain the prefixes :func:`discover_actors` matches on, so a node
#: seeded this way is still introspectable by role.
_EXCHANGE_ACTORS: Tuple[Tuple[str, str, str], ...] = (
    ("finndervul", "Finn der Vul", "Person"),
    ("vendorco", "VendorCo", "Organization"),
    ("coordinator", "Coordinator LLC", "Organization"),
)


def seed_exchange_actors(
    client: DataLayerClient,
) -> Tuple[as_Actor, as_Actor, as_Actor]:
    """Create the Finder, Vendor and Coordinator actors on *client*'s node.

    Each gets its own store, holding its own record, which is the whole of what
    a single-container exchange demo needs: the three actors reach each other by
    URL, and delivery derives a recipient's inbox from its URI alone
    (``http_delivery``), so no actor needs a stored copy of another's record.

    Idempotent, because ``POST /actors/`` is.

    Returns:
        A tuple of ``(finder, vendor, coordinator)`` actors as created.
    """
    seeded = tuple(
        seed_actor(
            client=client, name=name, actor_type=actor_type, actor_id=slug
        )
        for slug, name, actor_type in _EXCHANGE_ACTORS
    )
    for actor in seeded:
        logger.info("Seeded exchange actor: %s", actor.id_)
    finder, vendor, coordinator = seeded

    # One client serves a node hosting three actors, so it cannot infer whose
    # replica a `dl_path` read is about.  Bind it to the vendor: the exchange
    # demos are receiver-side stories and the vendor is the recipient in the
    # large majority of them.  Reads about the finder's or coordinator's replica
    # pass `actor_id=` explicitly at the call site, which is what makes those
    # reads legible as cross-actor rather than silently answering from the wrong
    # store (ADR-0070 decision 7).
    client.actor_id = vendor.id_
    logger.debug("Exchange demo reads bound to vendor replica: %s", vendor.id_)

    return finder, vendor, coordinator


def setup_clean_environment(
    client: DataLayerClient,
) -> Tuple[as_Actor, as_Actor, as_Actor]:
    """Reset the node and provision the three default demo actors.

    Clears every store on the node, then creates the Finder, Vendor and
    Coordinator actors.  The seeding step is explicit because clearing a node
    leaves it hosting nothing at all: under ADR-0070 there is no store that
    outlives the reset for a server-side ``init`` to populate.

    Returns:
        A tuple of ``(finder, vendor, coordinator)`` actors.
    """
    logger.info("Setting up clean environment...")
    reset = reset_datalayer(client=client)
    logger.info(f"Reset status: {reset}")
    finder, vendor, coordinator = seed_exchange_actors(client=client)
    logger.info("Clean environment setup complete.")
    return finder, vendor, coordinator


@contextmanager
def demo_environment(
    client: DataLayerClient,
) -> Generator[Tuple[as_Actor, as_Actor, as_Actor], None, None]:
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
            derives one from ``VULTRON_SERVER__BASE_URL``.

    Returns:
        The created (or pre-existing) ``as_Actor`` object.
    """
    payload: dict = {"name": name, "actor_type": actor_type}
    if actor_id is not None:
        payload["id"] = actor_id

    response_data = client.post("/actors/", json=payload)
    return as_Actor.model_validate(response_data)


def case_actor_id_for_report(report_id: str) -> str:
    """Return the CaseActor URI that a report's CaseProposal will be sent to.

    Mirrors ``ResolveCaseActorUrlsNode`` / ``ProposeReportCaseToActorNode``: the
    id is *derived*, not looked up, so a demo can compute it before the proposal
    exists and provision the actor that must receive it.
    """
    from vultron.config import get_config
    from vultron.core.behaviors.case.nodes.conditions import _derive_case_slug

    cfg = get_config()
    base = (
        str(cfg.actor.case_actor_service_url).rstrip("/")
        if cfg.actor.case_actor_service_url
        else str(cfg.server.base_url).rstrip("/")
    )
    return f"{base}/actors/case-actor-{_derive_case_slug(report_id)}"


def seed_case_actor_for_report(
    client: DataLayerClient, report_id: str
) -> as_Actor:
    """Provision the CaseActor that *report_id*'s CaseProposal is addressed to.

    ``ProposeReportCaseToActorNode`` sends ``Create(CaseProposal)`` to a CaseActor
    whose URI it derives from the report, and delivery is an ordinary HTTP POST to
    that actor's inbox (ADR-0042).  The inbox route resolves the actor from the
    store its URI names, so the CaseActor has to be a *hosted actor* before the
    proposal is delivered or the round-trip never starts.

    In the exchange demos one container plays both the participant node and the
    CaseActor service, so that container is the one that must host it.  Going
    through ``POST /actors/`` is what puts the record in the CaseActor's own
    store, since the route opens the store the id names (ADR-0070).

    Spawning a CaseActor on demand for an unknown-in-advance case is a separate
    protocol question (CP-08-003, #1700); this helper deliberately only does what
    a demo can do — provision an actor whose id it can compute.

    Returns:
        The created (or pre-existing) CaseActor as an ``as_Actor``.
    """
    case_actor_id = case_actor_id_for_report(report_id)
    actor = seed_actor(
        client=client,
        name=f"CaseActor for report {report_id}",
        actor_type="Service",
        actor_id=case_actor_id,
    )
    logger.info("Provisioned CaseActor for report: %s", case_actor_id)
    return actor


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
                f"Checking server at: {url} (attempt {attempt + 1}/{max_retries})"
            )
            response = httpx.get(url, timeout=2)
            if response.status_code == 200:
                return True
        except httpx.ConnectError:
            pass
        except httpx.TimeoutException:
            pass
        except Exception:
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
