"""
Fixtures for test/core/use_cases/triggers tests.

Import as_VulnerabilityCase so the vocabulary registry is populated before tests
run, preventing TinyDB from falling back to raw Documents.
"""

from collections.abc import Iterator
from typing import Any

import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service

# imported for vocabulary registration side-effect
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)


@pytest.fixture
def datalayer():
    from vultron.adapters.driven.datalayer import (
        get_datalayer,
        reset_datalayer,
    )

    reset_datalayer()
    datalayer = get_datalayer(
        "https://test.example/api/v2/actors/test-actor",
        db_url="sqlite:///:memory:",
    )
    datalayer.clear_all()
    yield datalayer
    datalayer.clear_all()
    reset_datalayer()


@pytest.fixture
def actor_store() -> Iterator[Any]:
    """Factory for ``(actor, store)`` pairs, each store closed on teardown."""
    stores: list[SqliteDataLayer] = []

    def _make(name: str) -> tuple[as_Service, SqliteDataLayer]:
        actor = as_Service(name=name)
        reset_datalayer(actor.id_)
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor.id_)
        dl.clear_all()
        dl.create(actor)
        stores.append(dl)
        return actor, dl

    yield _make
    for dl in stores:
        actor_id = dl.actor_id
        dl.clear_all()
        dl.close()
        if actor_id:
            reset_datalayer(actor_id)
