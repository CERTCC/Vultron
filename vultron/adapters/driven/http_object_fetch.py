#!/usr/bin/env python

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

"""Fetch an object a received activity names, over HTTP (AKM-05-003).

One ``GET`` per attempt, to the object's source
(:class:`~vultron.core.models.object_fetch.ObjectFetchSource`):

- a case object, from the case host's case-scoped read,
  ``{host}/cases/{case key}/objects?object_id=…`` (AKM-05-006), the case
  named by its surrogate key, the last segment of its id;
- an actor's profile, from ``{actor}/profile`` (AR-10-001).

The request names the fetching actor in the :data:`REQUESTER_HEADER` header.
That is a claim, not a proof: unlike a delivery, whose proof the inbox
verifies (SIG-03-002), a fetch request carries none, and the case host trusts
the claim (HTTP-level request authentication is #509).

Attempts are bounded and back off exponentially; a 4xx answer ends the fetch
at once, since the same request will never succeed (AKM-05-008, OX-13-005).
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.parse
from dataclasses import dataclass
from typing import Any, Protocol

import httpx2 as httpx

from vultron.adapters.driven.http_delivery import (
    DEFAULT_BACKOFF_MULTIPLIER,
    DEFAULT_DELIVERY_TIMEOUT,
    DEFAULT_INITIAL_DELAY,
    DEFAULT_MAX_DELAY,
)
from vultron.adapters.driven.http_retry import (
    Backoff,
    RetriesExhaustedError,
    TerminalAttemptError,
    retry_with_backoff,
)
from vultron.adapters.utils import strip_id_prefix
from vultron.config import get_config
from vultron.core.models.base import CoreObject
from vultron.core.models.object_fetch import ObjectFetchSource, ObjectReference
from vultron.errors import VultronValidationError
from vultron.primitives import same_actor_id

# parse_fetched_object types a body by WIRE_TYPE_MAP, which these packages
# fill on import.  Without them a fetched ``Person`` is unknown, or parses as
# the plain wire actor without its assertionMethod.
from vultron.wire.as2.vocab import (
    activities as _activities,  # noqa: F401
    objects as _objects,  # noqa: F401
)
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.base.registry import find_in_vocabulary

logger = logging.getLogger(__name__)

#: The header a fetch names its requesting actor in (AKM-05-006).
REQUESTER_HEADER = "X-Vultron-Actor"

#: Default maximum attempts per fetch (AKM-05-008).
DEFAULT_MAX_ATTEMPTS: int = 3

#: Retry delays and the per-attempt timeout are the delivery adapter's
#: (SYNC-05-002, SYNC-05-004): a fetch is the same kind of call to a peer.
DEFAULT_FETCH_TIMEOUT: float = DEFAULT_DELIVERY_TIMEOUT


@dataclass(frozen=True)
class ObjectFetchResult:
    """What one fetch came to.

    Attributes:
        body: The fetched JSON object, or ``None`` when the fetch failed.
        failure: Why the fetch failed, or ``None`` when it succeeded.
        attempts: The attempts made.
    """

    body: dict[str, Any] | None
    failure: str | None
    attempts: int


class ObjectFetcher(Protocol):
    """Fetches the object a reference names."""

    async def fetch(
        self, reference: ObjectReference, requester_id: str
    ) -> ObjectFetchResult:
        """Fetch *reference*'s object on behalf of *requester_id*."""
        ...  # pragma: no cover


def fetch_url(reference: ObjectReference) -> str:
    """The URL a fetch of *reference* is sent to.

    A case is named in the path by its surrogate key (``strip_id_prefix``),
    since a full case id may carry slashes no path segment can; the object
    id, any URI, travels as a query parameter.
    """
    host = reference.host_actor_id.rstrip("/")
    if reference.source is ObjectFetchSource.ACTOR_PROFILE:
        return f"{host}/profile"
    case_key = urllib.parse.quote(
        strip_id_prefix(reference.case_id or ""), safe=""
    )
    query = urllib.parse.urlencode({"object_id": reference.object_id})
    return f"{host}/cases/{case_key}/objects?{query}"


class HttpObjectFetcher:
    """:class:`ObjectFetcher` over HTTP ``GET``, with bounded retry.

    Args:
        max_attempts: Attempts per fetch, the first included.
        initial_delay: Seconds before the first retry.
        backoff_multiplier: Multiplier applied to the delay after each
            failed attempt.
        max_delay: Upper bound on the retry delay, in seconds.
        timeout: Timeout of one attempt, in seconds: of each network
            operation, and of the whole attempt, so a peer that answers a
            byte at a time still ends the attempt.
        max_body_bytes: The largest body read, in bytes, or ``None`` for no
            limit; a longer body ends the fetch at once.
    """

    def __init__(
        self,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        initial_delay: float = DEFAULT_INITIAL_DELAY,
        backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
        max_delay: float = DEFAULT_MAX_DELAY,
        timeout: float = DEFAULT_FETCH_TIMEOUT,
        max_body_bytes: int | None = None,
    ) -> None:
        self._backoff = Backoff(
            attempts=max_attempts,
            initial_delay=initial_delay,
            multiplier=backoff_multiplier,
            max_delay=max_delay,
        )
        self._max_attempts = max_attempts
        self._timeout = timeout
        self._max_body_bytes = max_body_bytes

    async def fetch(
        self, reference: ObjectReference, requester_id: str
    ) -> ObjectFetchResult:
        """Fetch *reference*'s object, retrying a retryable failure.

        Never raises for a failed fetch: the failure is the result.  A 4xx
        answer, or a 2xx that is not a JSON object, ends the fetch at once;
        any other failure, a URL the client refuses included, is retried up
        to the cap (AKM-05-008).
        """
        url = fetch_url(reference)

        def _log_retry(
            number: int, attempts: int, exc: Exception, delay: float
        ) -> None:
            logger.info(
                "Fetch attempt %d/%d of '%s' failed (%s); retrying in %.1fs",
                number,
                attempts,
                reference.object_id,
                _describe(url, exc),
                delay,
            )

        try:
            async with httpx.AsyncClient() as client:
                body, attempts = await retry_with_backoff(
                    lambda: self._get(client, url, requester_id),
                    self._backoff,
                    _log_retry,
                )
        except TerminalAttemptError as exc:
            return ObjectFetchResult(
                None, _describe(url, exc.cause), exc.attempt
            )
        except RetriesExhaustedError as exc:
            return ObjectFetchResult(
                None, _describe(url, exc.last), exc.attempts
            )
        logger.info(
            "Fetched '%s' from %s for actor_id=%s (attempt %d)",
            reference.object_id,
            url,
            requester_id,
            attempts,
        )
        return ObjectFetchResult(body, None, attempts)

    async def _get(
        self, client: httpx.AsyncClient, url: str, requester_id: str
    ) -> dict[str, Any]:
        """One attempt: the fetched JSON object, or the failure raised."""
        try:
            async with asyncio.timeout(self._timeout):
                async with client.stream(
                    "GET",
                    url,
                    headers={
                        REQUESTER_HEADER: requester_id,
                        "Accept": "application/activity+json",
                    },
                    timeout=self._timeout,
                ) as response:
                    response.raise_for_status()
                    content = await self._read_body(response)
        except httpx.HTTPStatusError as exc:
            if 400 <= exc.response.status_code < 500:
                # The same request will never succeed (OX-13-005).
                raise TerminalAttemptError(exc) from exc
            raise
        try:
            body = json.loads(content)
        except ValueError as exc:
            # A 2xx whose body is not JSON: a retry gets the same.
            raise TerminalAttemptError(
                ValueError(f"answered with no JSON: {exc}")
            ) from exc
        if not isinstance(body, dict):
            raise TerminalAttemptError(
                ValueError(
                    f"answered with a JSON {type(body).__name__}, not an"
                    " object"
                )
            )
        return body

    async def _read_body(self, response: httpx.Response) -> bytes:
        """The body of *response*, read no further than the byte limit."""
        limit = self._max_body_bytes
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if limit is not None and size > limit:
                # A retry gets the same body.
                raise TerminalAttemptError(
                    ValueError(f"answered with a body over {limit} bytes")
                )
            chunks.append(chunk)
        return b"".join(chunks)


def default_object_fetcher() -> HttpObjectFetcher:
    """The HTTP fetcher, bounded by the configured attempts (AKM-05-008)."""
    config = get_config()
    return HttpObjectFetcher(
        max_attempts=config.max_object_fetch_attempts,
        timeout=config.object_fetch_timeout_seconds,
    )


def parse_fetched_object(
    document: dict[str, Any], object_id: str
) -> CoreObject | as_Base:
    """The object a fetch answered with, typed by its ``type``.

    *document* is what the object's holder served, not a received body: the
    receive path's parsed activity stays the authority for what arrived
    (MV-11-005).

    Raises:
        VultronValidationError: When the body names no type the vocabulary
            knows, does not validate as that type, or is not the object
            *object_id* names.
    """
    type_name = document.get("type")
    if not isinstance(type_name, str) or not type_name:
        raise VultronValidationError(
            f"the fetched body for {object_id!r} names no type"
        )
    try:
        cls = find_in_vocabulary(type_name)
        parsed = cls.model_validate(document)
    except (KeyError, ValueError) as exc:
        raise VultronValidationError(
            f"the fetched body for {object_id!r} is not a valid"
            f" {type_name!r}: {exc}"
        ) from exc
    if not isinstance(parsed, (CoreObject, as_Base)):
        raise VultronValidationError(
            f"the fetched body for {object_id!r} is a {type_name!r}, which"
            " is not an object"
        )
    parsed_id = getattr(parsed, "id_", None)
    if not isinstance(parsed_id, str) or not same_actor_id(
        parsed_id, object_id
    ):
        raise VultronValidationError(
            f"the fetched object {parsed_id!r} is not the {object_id!r}"
            " that was asked for"
        )
    return parsed


def _describe(url: str, exc: Exception) -> str:
    """One line naming why a fetch of *url* failed."""
    if isinstance(exc, httpx.HTTPStatusError):
        return f"GET {url} answered HTTP {exc.response.status_code}"
    if isinstance(exc, ValueError):
        return f"GET {url} {exc}"
    return f"GET {url} failed: {exc!r}"


__all__ = [
    "DEFAULT_MAX_ATTEMPTS",
    "REQUESTER_HEADER",
    "HttpObjectFetcher",
    "ObjectFetchResult",
    "ObjectFetcher",
    "default_object_fetcher",
    "fetch_url",
    "parse_fetched_object",
]
