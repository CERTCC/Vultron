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

"""Bounded retry with exponential backoff for one HTTP call to a peer.

Shared by outbound delivery (SYNC-05-001, SYNC-05-002) and object fetch
(AKM-05-008).  An attempt that must not be retried, such as a 4xx answer
(OX-13-005), raises :class:`TerminalAttemptError`; any other exception is
retried until the attempts run out, and then :class:`RetriesExhaustedError`
carries the last one.  Every exception an attempt raises ends in one of the
two, so a caller can always tell its peer's answer from its own fault.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


class TerminalAttemptError(Exception):
    """Raised by an attempt whose failure a retry cannot change.

    Attributes:
        cause: The failure.
        attempt: The attempt it ended on, set by :func:`retry_with_backoff`.
    """

    def __init__(self, cause: Exception) -> None:
        self.cause = cause
        self.attempt = 0
        super().__init__(str(cause))


class RetriesExhaustedError(Exception):
    """Raised when every attempt failed with a retryable failure.

    Attributes:
        attempts: The attempts made.
        last: The last attempt's failure.
    """

    def __init__(self, attempts: int, last: Exception) -> None:
        self.attempts = attempts
        self.last = last
        super().__init__(f"{attempts} attempt(s) failed: {last}")


@dataclass(frozen=True)
class Backoff:
    """How often, and how far apart, an attempt is made.

    Attributes:
        attempts: Attempts in all, the first included; at least 1.
        initial_delay: Seconds before the first retry.
        multiplier: Factor applied to the delay after each failure.
        max_delay: Upper bound on the delay, in seconds.
    """

    attempts: int
    initial_delay: float
    multiplier: float
    max_delay: float

    def __post_init__(self) -> None:
        if self.attempts < 1:
            raise ValueError(f"attempts must be at least 1: {self.attempts}")


#: Called before each retry with the attempt that failed, the attempts in
#: all, its failure and the delay before the next one.
RetryHook = Callable[[int, int, Exception, float], None]


async def retry_with_backoff(
    attempt: Callable[[], Awaitable[T]],
    backoff: Backoff,
    on_retry: RetryHook | None = None,
) -> tuple[T, int]:
    """Run *attempt* until it succeeds, it fails terminally, or retries run out.

    Waits ``delay`` plus up to half a second of jitter between attempts; the
    delay grows by ``multiplier``, capped at ``max_delay``.

    Returns:
        The successful attempt's value and its attempt number.

    Raises:
        TerminalAttemptError: When an attempt raised it, with ``attempt`` set.
        RetriesExhaustedError: When the last attempt failed any other way.
    """
    delay = backoff.initial_delay
    for number in range(1, backoff.attempts + 1):
        try:
            return await attempt(), number
        except TerminalAttemptError as exc:
            exc.attempt = number
            raise
        # Every other failure, whatever its type, is retried or reported:
        # one that escaped would leave its caller's work undecided.
        except Exception as exc:
            if number == backoff.attempts:
                raise RetriesExhaustedError(number, exc) from exc
            if on_retry is not None:
                on_retry(number, backoff.attempts, exc, delay)
            # Retry jitter, not a secret: a PRNG is the correct tool.
            await asyncio.sleep(delay + random.uniform(0, 0.5))  # noqa: S311
            delay = min(delay * backoff.multiplier, backoff.max_delay)
    raise AssertionError("unreachable: Backoff.attempts is at least 1")


__all__ = [
    "Backoff",
    "RetriesExhaustedError",
    "RetryHook",
    "TerminalAttemptError",
    "retry_with_backoff",
]
