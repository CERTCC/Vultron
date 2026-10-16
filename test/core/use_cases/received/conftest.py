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
from vultron.core.models.actor import VultronService
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


_CALL_REPORT = pytest.StashKey[pytest.TestReport]()


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    """Keep each test's call-phase report, for the rebuild check below."""
    report = yield
    if report.when == "call":
        item.stash[_CALL_REPORT] = report
    return report


@pytest.fixture(autouse=True)
def _every_network_rebuilds_from_its_ledger(request, _close_sqlite_datalayers):
    """Every per-actor-store scenario rebuilds from its ledger (#4294 AC-5).

    Each ``LedgerNetwork`` a passing test built is checked when the test ends:
    the CASE_MANAGER's whole ledger, replayed into an empty store from the
    case as it stood before the first entry, must reach the CASE_MANAGER's
    participant records, consent rows and embargo register (CLP-07-013,
    CM-23-016).  A network with no entries has nothing to rebuild, and one
    whose test wrote the CASE_MANAGER's store outside the ledger on purpose
    says so with ``bypass_ledger()``.  Runs before the stores are closed.
    """
    from test.support.ledger_rebuild import assert_rebuilds_from_ledger

    from ._ledger_network import BYSTANDER, MANAGER, NETWORKS

    NETWORKS.clear()
    yield
    networks = list(NETWORKS)
    NETWORKS.clear()
    report = request.node.stash.get(_CALL_REPORT, None)
    if report is None or not report.passed:
        return
    for net in networks:
        if net.ledger_bypassed or net.rebuild_seed is None:
            continue
        assert_rebuilds_from_ledger(
            net.stores[MANAGER],
            net.case_id,
            as_actor=BYSTANDER,
            seed=net.rebuild_seed,
        )


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
    # Attached first, so it takes a consent row for every embargo already
    # in the register (ADR-0122), as production attaches before storing.
    case.add_participant(participant)
    dl.create(participant)
    return participant


def seed_case_owner_participant(
    dl: SqliteDataLayer,
    case: as_VulnerabilityCase,
    owner_actor_id: str,
) -> CaseParticipant:
    """Give *case* a ``CVDRole.CASE_OWNER`` participant for *owner_actor_id*.

    A sender check for the Case Owner reads the role off the roster, so a
    received-side test whose sender is the owner must seed it as one.
    The participant is created in *dl* and attached to *case* in memory; the
    caller persists *case* afterwards.
    """
    participant = CaseParticipant(
        id_=f"{case.id_}/participants/case-owner",
        attributed_to=owner_actor_id,
        context=case.id_,
        case_roles=[CVDRole.CASE_OWNER],
    )
    # Attached first, so it takes a consent row for every embargo already
    # in the register (ADR-0122), as production attaches before storing.
    case.add_participant(participant)
    dl.create(participant)
    return participant


def seed_case_participant(
    dl: SqliteDataLayer,
    case: as_VulnerabilityCase,
    actor_id: str,
    roles: list[CVDRole] | None = None,
) -> CaseParticipant:
    """Give *case* an ordinary participant record for *actor_id*.

    A received message whose sender must be a participant (CM-16-001) needs
    the sender on the roster.
    The participant is created in *dl* and attached to *case* in memory; the
    caller persists *case* afterwards.
    """
    participant = CaseParticipant(
        id_=f"{case.id_}/participants/{actor_id.rsplit('/', 1)[-1]}",
        attributed_to=actor_id,
        context=case.id_,
        case_roles=roles or [CVDRole.REPORTER],
    )
    # Attached first, so it takes a consent row for every embargo already
    # in the register (ADR-0122), as production attaches before storing.
    case.add_participant(participant)
    dl.create(participant)
    return participant


def grant_case_owner_role(
    dl: SqliteDataLayer, case_id: str, actor_id: str
) -> CaseParticipant:
    """Add ``CVDRole.CASE_OWNER`` to *actor_id*'s existing participant record.

    The owner's decision on an embargo (ADR-0122) is guarded by the role on
    the roster (HP-01-006); :func:`make_embargo_case_with_actor` seeds its
    author without it.
    """
    case = dl.read_case(case_id)
    assert case is not None, case_id
    participant_id = case.actor_participant_index[actor_id]
    participant = dl.read(participant_id)
    assert isinstance(participant, CaseParticipant)
    if CVDRole.CASE_OWNER not in participant.case_roles:
        participant.case_roles = [*participant.case_roles, CVDRole.CASE_OWNER]
        dl.save(participant)
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


def seed_inert_invitee(
    dl: SqliteDataLayer,
    case: as_VulnerabilityCase,
    invitee_id: str,
    roles: list[CVDRole] | None = None,
) -> CaseParticipant:
    """Seed the inert record a stub Invite leaves for *invitee_id* (CM-11-006).

    An ``Accept`` of a stub Invite activates this record and never creates one
    (CM-11-021), so every test that drives an Accept seeds it first.  Call it
    before ``dl.create(case)``: it attaches the record to *case*.
    """
    from vultron.core.models.dimensions import RmDimension
    from vultron.core.models.participant_status import ParticipantStatus
    from vultron.core.states.rm import RM

    participant = CaseParticipant(
        id_=f"{case.id_}/participants/{invitee_id.rstrip('/').split('/')[-1]}",
        attributed_to=invitee_id,
        context=case.id_,
        case_roles=roles or [CVDRole.VENDOR],
        participant_statuses=[
            ParticipantStatus(
                context=case.id_,
                attributed_to=invitee_id,
                rm=RmDimension(state=RM.RECEIVED),
                cvd_role=roles or [CVDRole.VENDOR],
            )
        ],
        joined=False,
    )
    # Attaching writes its UNINVITED row for every register entry, as the stub
    # Invite's record gets them (ADR-0122), so it is stored after.
    case.add_participant(participant)
    dl.create(participant)
    return participant


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
) -> tuple[
    SqliteDataLayer, VultronService, as_VulnerabilityCase, as_EmbargoEvent
]:
    """Return (dl, case_actor, case, embargo) for embargo received-side tests.

    Also creates ``as_CaseParticipant`` objects so actor → participant lookups
    in the embargo handlers succeed. Every participant is recorded in both
    ``case_participants`` (the authoritative membership, CM-19-001) and
    ``actor_participant_index``, so the consent writes that walk the membership
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

    case_actor = VultronService(
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
    manager_actor_id = case_manager_actor_id or case_actor_id
    if manager_actor_id == author_id:
        # One actor holds one participant record: the author's takes the
        # CASE_MANAGER role rather than a second record for the same actor
        # that the roster could not index (CM-19-001).
        p1.add_role(CVDRole.CASE_MANAGER)
        dl.save(p1)
    else:
        case_manager_participant = as_CaseParticipant(
            id_=f"{case_id}/participants/case-actor-p",
            attributed_to=manager_actor_id,
            context=case_id,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        dl.create(case_manager_participant)
        case.case_participants.append(case_manager_participant.id_)
        case.actor_participant_index[manager_actor_id] = (
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
