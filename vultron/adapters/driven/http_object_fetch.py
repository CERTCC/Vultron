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
  ``{host}/case-object?case_id=…&object_id=…`` (AKM-05-006);
- an actor's profile, from ``{actor}/profile`` (AR-10-001).

The request names the fetching actor in the :data:`REQUESTER_HEADER` header.
That is a claim, not a proof: the prototype authenticates nobody, and the
case host trusts the claim as its inbox trusts a claimed sender (#509).

Attempts are bounded and back off exponentially; a 4xx answer ends the fetch
at once, since the same request will never succeed (AKM-05-008, OX-13-005).
"""

from __future__ import annotations

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
from vultron.core.models.object_fetch import ObjectFetchSource, ObjectReference

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
    """The URL a fetch of *reference* is sent to."""
    host = reference.host_actor_id.rstrip("/")
    if reference.source is ObjectFetchSource.ACTOR_PROFILE:
        return f"{host}/profile"
    query = urllib.parse.urlencode(
        {"case_id": reference.case_id, "object_id": reference.object_id}
    )
    return f"{host}/case-object?{query}"


class HttpObjectFetcher:
    """:class:`ObjectFetcher` over HTTP ``GET``, with bounded retry.

    Args:
        max_attempts: Attempts per fetch, the first included.
        initial_delay: Seconds before the first retry.
        backoff_multiplier: Multiplier applied to the delay after each
            failed attempt.
        max_delay: Upper bound on the retry delay, in seconds.
        timeout: Timeout of one attempt, in seconds.
    """

    def __init__(
        self,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        initial_delay: float = DEFAULT_INITIAL_DELAY,
        backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
        max_delay: float = DEFAULT_MAX_DELAY,
        timeout: float = DEFAULT_FETCH_TIMEOUT,
    ) -> None:
        self._backoff = Backoff(
            attempts=max_attempts,
            initial_delay=initial_delay,
            multiplier=backoff_multiplier,
            max_delay=max_delay,
        )
        self._max_attempts = max_attempts
        self._timeout = timeout

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
            response = await client.get(
                url,
                headers={
                    REQUESTER_HEADER: requester_id,
                    "Accept": "application/activity+json",
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if 400 <= exc.response.status_code < 500:
                # The same request will never succeed (OX-13-005).
                raise TerminalAttemptError(exc) from exc
            raise
        try:
            body = response.json()
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
    "fetch_url",
]
