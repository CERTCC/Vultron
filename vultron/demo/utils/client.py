"""HTTP client for the DataLayer REST API, plus reference and format helpers."""

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

import json
import logging
import os
from http import HTTPMethod
from typing import Any, cast

import httpx2 as httpx
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from vultron.adapters.utils import parse_id
from vultron.core.models.base import NonEmptyString
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

# One logger for the whole package, so log records keep its name.
logger = logging.getLogger(__package__)


BASE_URL = os.environ.get(
    "VULTRON_API_BASE_URL", "http://localhost:7999/api/v2"
)


def ref_id(value: object) -> str | None:
    """Return the ID of a string-or-AS2 reference, if present."""
    if isinstance(value, str):
        return value
    if value is None:
        return None
    return getattr(value, "id_", None)


def case_references_report(case: as_VulnerabilityCase, report_id: str) -> bool:
    """Return whether *case* lists the report *report_id*.

    The single membership test behind every "which case did this report
    produce?" lookup, so a store holding several cases is never read as
    "the case".
    """
    return any(
        ref_id(report) == report_id
        for report in (case.vulnerability_reports or [])
    )


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
    ADR-0073: a container may host more than one actor (a CaseActor co-hosted
    in a single-container exchange demo, say), so ``/datalayer/{case_id}``
    alone no longer says whose replica to read.  Use :meth:`dl_path` to build inspection paths rather than
    hand-writing ``/datalayer/...``.
    """

    base_url: str = BASE_URL
    #: Canonical URI of the actor whose store this client inspects.  Optional so
    #: that clients used only for non-DataLayer endpoints (health, info, inbox)
    #: keep working unchanged; :meth:`dl_path` raises when it is needed and
    #: absent, rather than silently reading some other actor's replica.
    #: ``NonEmptyString`` rather than ``str`` so that ``actor_id=""`` is rejected
    #: at construction instead of reaching :meth:`dl_path` and being reported
    #: there as a missing id (AGENTS.md: no bare ``str`` for required text).
    actor_id: NonEmptyString | None = None
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
            URI from its own base URL (ADR-0073), which is why the short segment
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
                "are per-actor (ADR-0073). Set actor_id on the client or pass "
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
            An empty body, such as the inbox's 202 (IE-08-001), returns ``{}``.

        Raises:
            httpx.HTTPStatusError: When the response status is not OK.
        """
        if method.upper() not in HTTPMethod.__members__:
            raise ValueError(f"Unsupported HTTP method: {method}")

        url = f"{self.base_url}{path}"
        logger.debug("Calling %s %s", method.upper(), url)
        kwargs.setdefault("timeout", self.timeout)
        response = httpx.request(method, url, **kwargs)
        logger.debug("Response status: %s", response.status_code)

        data: Any = {}
        # An empty body is a valid answer, not a parse failure: the inbox's
        # 202 carries none (IE-08-001).
        if response.content:
            try:
                data = response.json()
                logger.debug("Response JSON: %s", json.dumps(data, indent=2))
            except ValueError as e:
                logger.error("Exception: %s", e)  # noqa: TRY400  # ruff-baseline #3353
                logger.error("Response text: %s", response.text)  # noqa: TRY400  # ruff-baseline #3353

        if response.status_code == 404:
            logger.error(
                "HTTP 404 from %s (%s %s)", response.url, method.upper(), path
            )

        if not response.is_success:
            logger.error("Error response: %s", response.text)
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
            raise ValueError(  # noqa: TRY004  # ruff-baseline #3353
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
    # *not* go through `dl_path` (ADR-0073 moved it to /admin/).
    return client.delete("/admin/datalayer/reset/")
