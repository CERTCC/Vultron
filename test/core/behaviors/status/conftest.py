"""Conftest for status BT tests."""

import pytest

from test.support.received import received_event


@pytest.fixture
def make_payload():
    """Return a helper that extracts the received event for an AS2 activity."""
    return received_event
