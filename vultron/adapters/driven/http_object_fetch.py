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

import asyncio
import logging
import random
import urllib.parse
from dataclasses import dataclass
from typing import Any, Protocol

import httpx2 as httpx

from vultron.core.models.object_fetch import ObjectFetchSource, ObjectReference

logger = logging.getLogger(__name__)

#: The header a fetch names its requesting actor in (AKM-05-006).
REQUESTER_HEADER = "X-Vultron-Actor"

#: Default maximum attempts per fetch (AKM-05-008).
DEFAULT_MAX_ATTEMPTS: int = 3

#: Default delay before the first retry, in seconds.
DEFAULT_INITIAL_DELAY: float = 0.5

#: Default multiplier applied to the delay after each failed attempt.
DEFAULT_BACKOFF_MULTIPLIER: float = 2.0

#: Default upper bound on the retry delay, in seconds.
DEFAULT_MAX_DELAY: float = 30.0

#: Default timeout of one attempt, in seconds (SYNC-05-004).
DEFAULT_FETCH_TIMEOUT: float = 30.0


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
        if max_attempts < 1:
            raise ValueError(
                f"max_attempts must be at least 1: {max_attempts}"
            )
        self._max_attempts = max_attempts
        self._initial_delay = initial_delay
        self._backoff_multiplier = backoff_multiplier
        self._max_delay = max_delay
        self._timeout = timeout

    async def fetch(
        self, reference: ObjectReference, requester_id: str
    ) -> ObjectFetchResult:
        """Fetch *reference*'s object, retrying a retryable failure.

        Never raises for a failed fetch: the failure is the result.
        """
        url = fetch_url(reference)
        delay = self._initial_delay
        last_error = "no attempt made"
        async with httpx.AsyncClient() as client:
            for attempt in range(1, self._max_attempts + 1):
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
                    body = response.json()
                    if not isinstance(body, dict):
                        return ObjectFetchResult(
                            None,
                            f"GET {url} answered with a JSON"
                            f" {type(body).__name__}, not an object",
                            attempt,
                        )
                    logger.info(
                        "Fetched '%s' from %s for actor_id=%s (attempt %d)",
                        reference.object_id,
                        url,
                        requester_id,
                        attempt,
                    )
                    return ObjectFetchResult(body, None, attempt)
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code
                    if 400 <= status < 500:
                        # The same request will never succeed (OX-13-005).
                        return ObjectFetchResult(
                            None, f"GET {url} answered HTTP {status}", attempt
                        )
                    last_error = f"GET {url} answered HTTP {status}"
                except ValueError as exc:
                    # A 2xx whose body is not JSON: retrying gets the same.
                    return ObjectFetchResult(
                        None,
                        f"GET {url} answered with no JSON: {exc}",
                        attempt,
                    )
                except httpx.HTTPError as exc:
                    last_error = f"GET {url} failed: {exc!r}"
                if attempt < self._max_attempts:
                    logger.info(
                        "Fetch attempt %d/%d of '%s' failed (%s); retrying"
                        " in %.1fs",
                        attempt,
                        self._max_attempts,
                        reference.object_id,
                        last_error,
                        delay,
                    )
                    # Retry jitter, not a secret: a PRNG is the right tool.
                    await asyncio.sleep(delay + random.uniform(0, 0.5))  # noqa: S311
                    delay = min(
                        delay * self._backoff_multiplier, self._max_delay
                    )
        return ObjectFetchResult(None, last_error, self._max_attempts)


__all__ = [
    "DEFAULT_MAX_ATTEMPTS",
    "REQUESTER_HEADER",
    "HttpObjectFetcher",
    "ObjectFetchResult",
    "ObjectFetcher",
    "fetch_url",
]
