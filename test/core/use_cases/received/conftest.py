"""
Fixtures for test/core/use_cases/received tests.

Imports as_VulnerabilityCase (and related wire-layer types) as a side effect so
that the global vocabulary registry is populated before any test in this
directory runs.  Without this import the registry may be empty when tests run
in isolation, causing TinyDB's record_to_object() to fall back to returning a
raw Document instead of a deserialized domain object.
"""

from collections.abc import Callable
from typing import cast

import pytest

# noqa: F401 — imported for vocabulary registration side-effect
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
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


class _AnonymousStore:
    """A store that cannot say whose it is, wrapping a real one for inspection.

    ``resolve_receiving_actor_id`` falls back to the store's ``actor_id``; this
    double reports none, so a request without ``receiving_actor_id`` has no
    receiver at all.  Every other attribute is the wrapped store's, so a test
    can assert on what the use case did (or did not) write.
    """

    actor_id = None

    def __init__(self, inner: SqliteDataLayer) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> object:
        return getattr(self._inner, name)


@pytest.fixture
def anonymous_store() -> Callable[[SqliteDataLayer], SqliteDataLayer]:
    """Wrap a store so it reports no ``actor_id`` (receiver unresolvable)."""

    def _wrap(inner: SqliteDataLayer) -> SqliteDataLayer:
        return cast(SqliteDataLayer, _AnonymousStore(inner))

    return _wrap
