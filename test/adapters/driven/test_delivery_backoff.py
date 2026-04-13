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
"""Tests for SYNC-5: DeliveryQueueAdapter retry/backoff behaviour.

Spec: SYNC-05-001, SYNC-05-002.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from vultron.adapters.driven.delivery_queue import (
    DEFAULT_BACKOFF_MULTIPLIER,
    DEFAULT_INITIAL_DELAY,
    DEFAULT_MAX_DELAY,
    DEFAULT_MAX_RETRIES,
    DeliveryQueueAdapter,
)
from vultron.core.models.activity import VultronActivity

RECIPIENT_URI = "https://example.org/actors/alice"


def _make_activity() -> VultronActivity:
    return VultronActivity(
        id_="https://example.org/activities/act1",
        type_="Announce",
        actor="https://example.org/actors/case-actor",
        object_="https://example.org/objects/obj1",
    )


class TestDefaultConstants:
    """Default constants are documented per SYNC-05-002."""

    def test_default_max_retries(self):
        assert DEFAULT_MAX_RETRIES == 3

    def test_default_initial_delay(self):
        assert DEFAULT_INITIAL_DELAY == 0.5

    def test_default_backoff_multiplier(self):
        assert DEFAULT_BACKOFF_MULTIPLIER == 2.0

    def test_default_max_delay(self):
        assert DEFAULT_MAX_DELAY == 30.0


class TestDeliveryQueueAdapterInit:
    """DeliveryQueueAdapter accepts configurable retry parameters (SYNC-05-002)."""

    def test_default_params(self):
        adapter = DeliveryQueueAdapter()
        assert adapter._max_retries == DEFAULT_MAX_RETRIES
        assert adapter._initial_delay == DEFAULT_INITIAL_DELAY
        assert adapter._backoff_multiplier == DEFAULT_BACKOFF_MULTIPLIER
        assert adapter._max_delay == DEFAULT_MAX_DELAY

    def test_custom_params(self):
        adapter = DeliveryQueueAdapter(
            max_retries=5,
            initial_delay=1.0,
            backoff_multiplier=3.0,
            max_delay=60.0,
        )
        assert adapter._max_retries == 5
        assert adapter._initial_delay == 1.0
        assert adapter._backoff_multiplier == 3.0
        assert adapter._max_delay == 60.0

    def test_zero_retries_disables_retry(self):
        adapter = DeliveryQueueAdapter(max_retries=0)
        assert adapter._max_retries == 0


class TestDeliverySuccess:
    """Successful delivery requires no retries."""

    def test_delivers_on_first_attempt(self):
        adapter = DeliveryQueueAdapter(max_retries=2, initial_delay=0.0)
        activity = _make_activity()

        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.raise_for_status = MagicMock()

        with patch(
            "httpx.AsyncClient.post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response
            asyncio.run(adapter.emit(activity, [RECIPIENT_URI]))

        mock_post.assert_called_once()

    def test_delivers_to_all_recipients(self):
        adapter = DeliveryQueueAdapter(max_retries=0, initial_delay=0.0)
        activity = _make_activity()
        recipients = [
            "https://example.org/actors/alice",
            "https://example.org/actors/bob",
        ]

        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.raise_for_status = MagicMock()

        with patch(
            "httpx.AsyncClient.post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response
            asyncio.run(adapter.emit(activity, recipients))

        assert mock_post.call_count == 2


class TestDeliveryRetry:
    """Failed delivery is retried with exponential backoff (SYNC-05-001)."""

    def test_retries_on_failure_then_succeeds(self):
        adapter = DeliveryQueueAdapter(
            max_retries=2, initial_delay=0.0, backoff_multiplier=2.0
        )
        activity = _make_activity()

        success_response = MagicMock()
        success_response.status_code = 202
        success_response.raise_for_status = MagicMock()

        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("connection refused")
            return success_response

        with patch("httpx.AsyncClient.post", side_effect=side_effect):
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                asyncio.run(adapter.emit(activity, [RECIPIENT_URI]))

        assert call_count == 3
        assert mock_sleep.call_count == 2

    def test_exponential_backoff_delay_sequence(self):
        adapter = DeliveryQueueAdapter(
            max_retries=3,
            initial_delay=1.0,
            backoff_multiplier=2.0,
            max_delay=100.0,
        )
        activity = _make_activity()
        sleep_calls: list[float] = []

        async def fail(*args, **kwargs):
            raise httpx.ConnectError("always fails")

        async def fake_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        with patch("httpx.AsyncClient.post", side_effect=fail):
            with patch("asyncio.sleep", side_effect=fake_sleep):
                asyncio.run(adapter.emit(activity, [RECIPIENT_URI]))

        # 3 retries → 3 sleep calls with delays 1.0, 2.0, 4.0
        assert sleep_calls == [1.0, 2.0, 4.0]

    def test_delay_capped_at_max_delay(self):
        adapter = DeliveryQueueAdapter(
            max_retries=5,
            initial_delay=10.0,
            backoff_multiplier=10.0,
            max_delay=30.0,
        )
        activity = _make_activity()
        sleep_calls: list[float] = []

        async def fail(*args, **kwargs):
            raise httpx.ConnectError("always fails")

        async def fake_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        with patch("httpx.AsyncClient.post", side_effect=fail):
            with patch("asyncio.sleep", side_effect=fake_sleep):
                asyncio.run(adapter.emit(activity, [RECIPIENT_URI]))

        # All delays after the first should be capped at max_delay
        for delay in sleep_calls[1:]:
            assert delay <= 30.0

    def test_exhaust_retries_logs_error(self, caplog):
        adapter = DeliveryQueueAdapter(
            max_retries=1, initial_delay=0.0, backoff_multiplier=1.0
        )
        activity = _make_activity()

        async def fail(*args, **kwargs):
            raise httpx.ConnectError("always fails")

        with patch("httpx.AsyncClient.post", side_effect=fail):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with caplog.at_level("ERROR"):
                    asyncio.run(adapter.emit(activity, [RECIPIENT_URI]))

        assert any("Failed to deliver" in r.message for r in caplog.records)

    def test_one_failed_recipient_does_not_block_others(self):
        """Delivery failure for one recipient does not abort others."""
        adapter = DeliveryQueueAdapter(max_retries=0, initial_delay=0.0)
        activity = _make_activity()

        delivered: list[str] = []

        async def side_effect(url, **kwargs):
            if "alice" in url:
                raise httpx.ConnectError("alice unreachable")
            resp = MagicMock()
            resp.status_code = 202
            resp.raise_for_status = MagicMock()
            delivered.append(url)
            return resp

        recipients = [
            "https://example.org/actors/alice",
            "https://example.org/actors/bob",
        ]

        with patch("httpx.AsyncClient.post", side_effect=side_effect):
            asyncio.run(adapter.emit(activity, recipients))

        assert len(delivered) == 1
        assert "bob" in delivered[0]

    def test_zero_retries_attempts_once_only(self):
        adapter = DeliveryQueueAdapter(max_retries=0, initial_delay=0.0)
        activity = _make_activity()

        call_count = 0

        async def fail(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise httpx.ConnectError("always fails")

        with patch("httpx.AsyncClient.post", side_effect=fail):
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                asyncio.run(adapter.emit(activity, [RECIPIENT_URI]))

        assert call_count == 1
        mock_sleep.assert_not_called()
