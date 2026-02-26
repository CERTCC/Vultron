#!/usr/bin/env python
"""
Test for health check retry logic in receive_report_demo.py

Bug: The demo script fails when the API server is starting up because
it only checks once with a 2-second timeout. In Docker environments,
the server may take several seconds to fully start after the container starts.

Solution: Add retry logic with exponential backoff to wait for the server
to be ready before proceeding.
"""

import time
from unittest.mock import Mock, patch

import pytest
import requests

from vultron.demo.receive_report_demo import (
    DataLayerClient,
    check_server_availability,
)


def test_check_server_availability_succeeds_immediately():
    """Test that health check succeeds when server is ready."""
    client = DataLayerClient(base_url="http://test:7999/api/v2")

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.ok = True

    with patch("requests.get", return_value=mock_response):
        result = check_server_availability(
            client, max_retries=1, retry_delay=0.1
        )

    assert result is True


def test_check_server_availability_fails_permanently():
    """Test that health check fails after max retries."""
    client = DataLayerClient(base_url="http://test:7999/api/v2")

    with patch(
        "requests.get",
        side_effect=requests.exceptions.ConnectionError("Connection refused"),
    ):
        result = check_server_availability(
            client, max_retries=2, retry_delay=0.1
        )

    assert result is False


def test_check_server_availability_succeeds_after_retry():
    """Test that health check succeeds after initial failures (simulating startup delay)."""
    client = DataLayerClient(base_url="http://test:7999/api/v2")

    # First 2 calls fail, third succeeds
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.ok = True

    side_effects = [
        requests.exceptions.ConnectionError("Connection refused"),
        requests.exceptions.ConnectionError("Connection refused"),
        mock_response,
    ]

    with patch("requests.get", side_effect=side_effects):
        result = check_server_availability(
            client, max_retries=3, retry_delay=0.1
        )

    assert result is True


def test_check_server_availability_logs_retry_attempts(caplog):
    """Test that health check logs retry attempts."""
    client = DataLayerClient(base_url="http://test:7999/api/v2")

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.ok = True

    side_effects = [
        requests.exceptions.ConnectionError("Connection refused"),
        mock_response,
    ]

    with patch("requests.get", side_effect=side_effects):
        result = check_server_availability(
            client, max_retries=3, retry_delay=0.1
        )

    assert result is True
    # Should see retry attempt logs
    assert (
        "Retrying in" in caplog.text
        or "Checking server availability" in caplog.text
        or "Checking server at" in caplog.text
    )


def test_check_server_availability_respects_max_retries():
    """Test that health check stops after max_retries attempts."""
    client = DataLayerClient(base_url="http://test:7999/api/v2")

    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise requests.exceptions.ConnectionError("Connection refused")

    with patch("requests.get", side_effect=side_effect):
        result = check_server_availability(
            client, max_retries=3, retry_delay=0.1
        )

    assert result is False
    assert call_count == 3  # Should try exactly 3 times
