"""
Fixtures for test/core/behaviors/report tests.

Imports as_VulnerabilityCase (and related wire-layer types) as a side effect so
that the global vocabulary registry is populated before any test in this
directory runs.  Without this import the registry may be empty when tests run
in isolation, causing TinyDB's record_to_object() to fall back to returning a
raw Document instead of a deserialized domain object.
"""

import pytest

# noqa: F401 — imported for vocabulary registration side-effect
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)
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
