"""Conftest for status BT tests."""

import pytest

from vultron.semantic_registry import extract_event


@pytest.fixture
def make_payload():
    """Return a helper that extracts a VultronEvent from an AS2 activity."""

    def _make_payload(activity, **extra_fields):
        event = extract_event(activity)
        if extra_fields:
            return event.model_copy(update=extra_fields)
        return event

    return _make_payload
