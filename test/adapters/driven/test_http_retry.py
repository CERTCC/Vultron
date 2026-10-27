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
"""The shared bounded retry with backoff (SYNC-05-001, AKM-05-008)."""

import asyncio
from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, patch

import pytest

from vultron.adapters.driven.http_retry import (
    Backoff,
    RetriesExhaustedError,
    TerminalAttemptError,
    retry_with_backoff,
)

_BACKOFF = Backoff(
    attempts=3, initial_delay=1.0, multiplier=2.0, max_delay=1.5
)


def _answering(answers: list[object]) -> Callable[[], Awaitable[object]]:
    """An attempt answering from *answers*: a value returns, an error raises."""
    remaining = list(answers)

    async def _attempt() -> object:
        answer = remaining.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    return _attempt


def _run(answers: list[object]) -> tuple[object, AsyncMock, list[float]]:
    """Run the helper over *answers*: a value returns, an exception raises."""
    delays: list[float] = []
    _attempt = _answering(answers)

    with (
        patch("asyncio.sleep", new_callable=AsyncMock) as sleep,
        patch("random.uniform", return_value=0.0),
    ):
        try:
            outcome: object = asyncio.run(
                retry_with_backoff(
                    _attempt,
                    _BACKOFF,
                    lambda _n, _t, _e, delay: delays.append(delay),
                )
            )
        except (TerminalAttemptError, RetriesExhaustedError) as exc:
            outcome = exc
    return outcome, sleep, delays


@pytest.mark.spec("SYNC-05-001")
def test_a_success_after_failures_returns_its_value_and_attempt():
    outcome, sleep, delays = _run([RuntimeError("a"), RuntimeError("b"), "ok"])

    assert outcome == ("ok", 3)
    assert delays == [1.0, 1.5], "the delay grows, capped at max_delay"
    assert sleep.await_count == 2


@pytest.mark.spec("OX-13-005")
def test_a_terminal_failure_is_not_retried():
    terminal = TerminalAttemptError(ValueError("4xx"))

    outcome, sleep, _ = _run([RuntimeError("a"), terminal])

    assert outcome is terminal
    assert terminal.attempt == 2
    sleep.assert_awaited_once()


@pytest.mark.spec("AKM-05-008")
def test_exhausted_retries_carry_the_last_failure():
    last = RuntimeError("c")

    outcome, _, _ = _run([RuntimeError("a"), RuntimeError("b"), last])

    assert isinstance(outcome, RetriesExhaustedError)
    assert outcome.attempts == 3
    assert outcome.last is last


@pytest.mark.spec("SYNC-05-001")
def test_a_retry_without_a_hook_still_backs_off_and_succeeds():
    with (
        patch("asyncio.sleep", new_callable=AsyncMock) as sleep,
        patch("random.uniform", return_value=0.0),
    ):
        outcome = asyncio.run(
            retry_with_backoff(_answering([RuntimeError("a"), "ok"]), _BACKOFF)
        )

    assert outcome == ("ok", 2)
    sleep.assert_awaited_once_with(1.0)


def test_at_least_one_attempt_is_required():
    with pytest.raises(ValueError, match="at least 1"):
        Backoff(attempts=0, initial_delay=0, multiplier=1, max_delay=0)
