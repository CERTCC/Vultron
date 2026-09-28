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
from vultron.core.models.case_participant import CaseParticipant
from vultron.enums.roles import CVDRole
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


def seed_case_manager_participant(
    dl: SqliteDataLayer,
    case: as_VulnerabilityCase,
    manager_actor_id: str,
) -> CaseParticipant:
    """Give *case* a ``CVDRole.CASE_MANAGER`` participant for *manager_actor_id*.

    Role gates resolve the CASE_MANAGER from the case's participant roster, so
    a received-side test that expects the gated work to run must seed the role
    holder as the receiving actor (BT-17-005), and a test that expects a
    refusal seeds it as somebody else.  The participant is created in *dl*
    and attached to *case* in memory; the caller persists *case* afterwards.
    """
    participant = CaseParticipant(
        id_=f"{case.id_}/participants/case-manager",
        attributed_to=manager_actor_id,
        context=case.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    dl.create(participant)
    case.case_participants.append(participant.id_)
    case.actor_participant_index[manager_actor_id] = participant.id_
    return participant


def seed_store_owner_as_case_manager(
    dl: SqliteDataLayer, case: as_VulnerabilityCase
) -> CaseParticipant:
    """Make the store's own actor the CASE_MANAGER of *case*.

    The receiving actor of a test that passes no ``receiving_actor_id`` is
    the store's owner, so this is the seeding a CASE_MANAGER-path test needs
    (BT-17-005, BT-05-006).
    """
    owner = dl.actor_id
    assert isinstance(owner, str) and owner, "store must name its actor"
    return seed_case_manager_participant(dl, case, owner)


@pytest.fixture
def seed_case_manager() -> (
    Callable[[SqliteDataLayer, as_VulnerabilityCase, str], CaseParticipant]
):
    """Fixture form of :func:`seed_case_manager_participant`."""
    return seed_case_manager_participant
