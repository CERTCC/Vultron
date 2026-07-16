"""
Fixtures for test/core/use_cases/received tests.

Imports VulnerabilityCase (and related wire-layer types) as a side effect so
that the global vocabulary registry is populated before any test in this
directory runs.  Without this import the registry may be empty when tests run
in isolation, causing TinyDB's record_to_object() to fall back to returning a
raw Document instead of a deserialized domain object.
"""

import pytest

# noqa: F401 — imported for vocabulary registration side-effect
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    VulnerabilityCase,
)


@pytest.fixture(autouse=True)
def _close_sqlite_datalayers(monkeypatch):
    """Close all SqliteDataLayer instances created during each test."""
    created: list[SqliteDataLayer] = []
    original_init = SqliteDataLayer.__init__

    def _tracking_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        created.append(self)

    monkeypatch.setattr(SqliteDataLayer, "__init__", _tracking_init)
    yield
    while created:
        created.pop().close()
