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

# imported for vocabulary registration side-effect
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case_actor import CaseActor
from vultron.core.models.case_participant import CaseParticipant
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
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
def seed_case_manager() -> Callable[
    [SqliteDataLayer, as_VulnerabilityCase, str], CaseParticipant
]:
    """Fixture form of :func:`seed_case_manager_participant`."""
    return seed_case_manager_participant


def make_embargo_case_with_actor(
    case_id: str,
    author_id: str,
    extra_participants: list[str] | None = None,
    case_manager_actor_id: str | None = None,
) -> tuple[SqliteDataLayer, CaseActor, as_VulnerabilityCase, as_EmbargoEvent]:
    """Return (dl, case_actor, case, embargo) for embargo received-side tests.

    Also creates ``as_CaseParticipant`` objects so actor → participant lookups
    in the embargo handlers succeed. Every participant is recorded in both
    ``case_participants`` (the authoritative membership, CM-19-001) and
    ``actor_participant_index``, so the PEC cascades that walk the membership
    list reach every participant, as they do in production.
    """
    from vultron.wire.as2.vocab.objects.case_participant import (
        as_CaseParticipant,
    )

    case_actor_id = f"{case_id}/actor"
    # The cascade commits to the canonical ledger, and CommitCaseLedgerEntryNode
    # is role-gated to the CASE_MANAGER (CLP-09), so the tree must run as — and
    # therefore in the store of — whoever holds that role here. That is
    # `case_manager_actor_id` when a test names one, otherwise the case actor.
    ledger_holder_id = case_manager_actor_id or case_actor_id
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=ledger_holder_id)

    case_actor = CaseActor(
        id_=case_actor_id,
        name=f"CaseActor for {case_id}",
        attributed_to=author_id,
        context=case_id,
    )
    dl.create(case_actor)

    case = as_VulnerabilityCase(
        id_=case_id,
        name="Embargo Cascade Case",
        attributed_to=author_id,
    )
    p1_id = f"{case_id}/participants/p1"
    case.actor_participant_index[author_id] = p1_id
    p1 = as_CaseParticipant(
        id_=p1_id, context=case_id, attributed_to=author_id
    )
    dl.create(p1)
    case.case_participants.append(p1_id)

    for pid in extra_participants or []:
        short = pid.rsplit("/", 1)[-1]
        pn_id = f"{case_id}/participants/{short}"
        case.actor_participant_index[pid] = pn_id
        pn = as_CaseParticipant(id_=pn_id, context=case_id, attributed_to=pid)
        dl.create(pn)
        case.case_participants.append(pn_id)

    dl.create(case)
    case_manager_participant = as_CaseParticipant(
        id_=f"{case_id}/participants/case-actor-p",
        attributed_to=case_manager_actor_id or case_actor_id,
        context=case_id,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    dl.create(case_manager_participant)
    case.case_participants.append(case_manager_participant.id_)
    case.actor_participant_index[case_manager_actor_id or case_actor_id] = (
        case_manager_participant.id_
    )
    dl.save(case)

    embargo = as_EmbargoEvent(
        id_=f"{case_id}/embargo_events/e1",
        content="Cascade test embargo",
        context=case_id,
        end_time=days_from_now_utc(45),
    )
    dl.create(embargo)

    return dl, case_actor, case, embargo
