"""``_record_named_peer`` runs a real discovery backend with its ports wired.

A backend that reads ``self.datalayer`` in ``update()`` needs ``setup()`` and
``initialise()`` to have run; ticking it bare left that attribute ``None``
(#2707).  Running it through a ``BTBridge`` also means a backend that raises no
longer crashes the request: it degrades to a minimal peer, like any other
non-SUCCESS, and the bridge logs the internal error.
"""

import logging
from collections.abc import Callable, Iterator
from datetime import timedelta

import py_trees
import pytest
from py_trees.common import Status

from test.support.objects import make
from vultron.adapters.driven.actor_resolution import (
    HttpActorResolutionAdapter,
    StaticActorResolutionAdapter,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.http_actor_profile_fetch import (
    HttpActorProfileFetchAdapter,
)
from vultron.adapters.driven.http_object_fetch import ObjectFetchResult
from vultron.core.behaviors.call_out.answer import CallOutAnswer
from vultron.core.behaviors.call_out.backend import CallOutBackend
from vultron.core.behaviors.call_out.bundles.actor_resolution import (
    ActorResolutionCallOutBundle,
    actor_resolution_bundle,
)
from vultron.core.behaviors.call_out.capabilities.actor_resolution import (
    RESOLVED_ACTOR_KEY,
)
from vultron.core.behaviors.helpers.ports_base import (
    DataLayerConditionWithPorts,
)
from vultron.core.models.actor import CoreActor, VultronOrganization
from vultron.core.use_cases.triggers.actor._peers import _record_named_peer
from vultron.errors import VultronActorProfileFetchError

ACTING = "https://example.org/actors/acting"
PEER = "https://example.org/actors/peer"


@pytest.fixture
def dl() -> Iterator[SqliteDataLayer]:
    datalayer = SqliteDataLayer("sqlite:///:memory:", actor_id=ACTING)
    try:
        datalayer.clear_all()
        yield datalayer
    finally:
        datalayer.close()


def _directory_backend(
    seen: list[tuple[object, str | None]],
) -> Callable[[str], py_trees.behaviour.Behaviour]:
    """A backend class that records what its wired ports gave it."""

    class _DirectoryBackend(CallOutBackend, DataLayerConditionWithPorts):
        def initialise(self) -> None:
            self.datalayer = self.get_input("datalayer")
            self.actor_id = self.get_input("actor_id")

        def answer(self) -> CallOutAnswer:
            assert self.datalayer is not None
            seen.append((self.datalayer.read(PEER), self.actor_id))
            return CallOutAnswer.yes()

    return _DirectoryBackend


def _record(dl: SqliteDataLayer, factory: object) -> None:
    bundle = ActorResolutionCallOutBundle(
        resolve_actor_factory=factory  # type: ignore[arg-type]
    )
    _record_named_peer(dl, PEER, "peer_id", ACTING, bundle)


def test_real_backend_has_its_ports_when_record_named_peer_ticks_it(dl):
    seen: list[tuple[object, str | None]] = []

    _record(dl, _directory_backend(seen))

    # The backend read the acting actor's store (no peer record yet) and ran
    # as the acting actor.
    assert seen == [(None, ACTING)]
    assert isinstance(dl.read(PEER), CoreActor)


def _counting_backend(calls: list[str]) -> type[CallOutBackend]:
    """A backend class that counts the times the seam asks it."""

    class _CountingBackend(CallOutBackend):
        def answer(self) -> CallOutAnswer:
            calls.append(self.name)
            return CallOutAnswer.yes()

    return _CountingBackend


@pytest.mark.spec("BT-18-039")
def test_known_peer_is_not_resolved_again(dl):
    held = make(
        CoreActor, id_=PEER, name="Held Peer", published=None, updated=None
    )
    dl.create(held)
    calls: list[str] = []

    _record(dl, _counting_backend(calls))

    assert calls == []
    stored = dl.read(PEER)
    assert isinstance(stored, CoreActor)
    assert stored.name == "Held Peer"


@pytest.mark.spec("BT-18-039")
def test_unknown_peer_is_resolved_before_it_is_recorded(dl):
    assert dl.read(PEER) is None
    calls: list[str] = []

    _record(dl, _counting_backend(calls))

    assert calls == ["ResolveActorDetails"]
    assert isinstance(dl.read(PEER), CoreActor)


def test_raising_backend_degrades_to_minimal_peer(dl, caplog):
    class _Broken(CallOutBackend):
        def answer(self) -> CallOutAnswer:
            raise AttributeError("directory client not configured")

    with caplog.at_level(logging.WARNING):
        _record(dl, _Broken)

    assert isinstance(dl.read(PEER), CoreActor)
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert any("AttributeError" in r.getMessage() for r in errors)
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any(
        "actor resolution returned FAILURE" in r.getMessage()
        and "AttributeError" in r.getMessage()
        for r in warnings
    )


@pytest.mark.spec("BT-18-011")
def test_running_backend_logs_internal_error_then_warning(dl, caplog):
    class _Running(CallOutBackend):
        def update(self) -> Status:
            return Status.RUNNING

    with caplog.at_level(logging.WARNING):
        _record(dl, _Running)

    assert isinstance(dl.read(PEER), CoreActor)
    levels = {
        r.levelno for r in caplog.records if "BT-18-011" in r.getMessage()
    }
    assert levels == {logging.ERROR, logging.WARNING}


# --- ResolveActorDetails through ActorResolutionPort (#6306) -------------


class _Port:
    """An ``ActorResolutionPort`` answering with one record, or raising."""

    def __init__(
        self,
        record: CoreActor | None = None,
        error: Exception | None = None,
    ) -> None:
        self._record = record
        self._error = error
        self.asked: list[tuple[str, str]] = []

    def resolve_actor(
        self, actor_id: str, requester_id: str
    ) -> CoreActor | None:
        self.asked.append((actor_id, requester_id))
        if self._error is not None:
            raise self._error
        return self._record


def _peer_profile(actor_id: str = PEER) -> VultronOrganization:
    return make(
        VultronOrganization,
        id_=actor_id,
        name="Peer Org",
        inbox=f"{actor_id}/inbox/",
        published=None,
        updated=None,
    )


def _record_through(dl: SqliteDataLayer, port: object) -> None:
    _record_named_peer(
        dl,
        PEER,
        "peer_id",
        ACTING,
        actor_resolution_bundle(port),  # type: ignore[arg-type]
    )


def _is_minimal(stored: object) -> bool:
    return (
        type(stored) is CoreActor
        and stored.id_ == PEER
        and [
            k
            for k in ("published", "updated", "inbox", "outbox", "name")
            if getattr(stored, k, None) is not None
        ]
        == []
    )


@pytest.mark.spec("AKM-05-002")
def test_a_resolved_record_of_the_peer_is_stored(dl):
    profile = _peer_profile()
    port = _Port(profile)

    _record_through(dl, port)

    assert port.asked == [(PEER, ACTING)]
    stored = dl.read(PEER)
    assert isinstance(stored, VultronOrganization)
    assert stored.name == "Peer Org"
    assert stored.inbox == f"{PEER}/inbox/"


@pytest.mark.spec("AKM-05-002")
def test_a_static_adapter_profile_is_stored(dl):
    _record_through(dl, StaticActorResolutionAdapter([_peer_profile()]))

    stored = dl.read(PEER)
    assert isinstance(stored, VultronOrganization)
    assert stored.name == "Peer Org"


@pytest.mark.spec("AKM-05-001")
def test_a_static_adapter_with_no_profile_records_the_minimal_peer(dl, caplog):
    other = _peer_profile(f"{PEER}-other")

    with caplog.at_level(logging.WARNING):
        _record_through(dl, StaticActorResolutionAdapter([other]))

    assert _is_minimal(dl.read(PEER))
    assert "actor resolution returned FAILURE" in caplog.text


@pytest.mark.spec("AKM-02-006")
def test_a_record_of_another_actor_is_never_stored_as_the_peer(dl, caplog):
    impostor = _peer_profile(f"{PEER}-impostor")

    with caplog.at_level(logging.INFO):
        _record_through(dl, _Port(impostor))

    assert _is_minimal(dl.read(PEER))
    assert dl.read(impostor.id_) is None
    assert f"record of '{impostor.id_}'" in caplog.text


@pytest.mark.spec("AKM-05-001")
def test_a_source_that_cannot_be_asked_records_the_minimal_peer(dl, caplog):
    port = _Port(error=VultronActorProfileFetchError("peer unreachable"))

    with caplog.at_level(logging.WARNING):
        _record_through(dl, port)

    assert _is_minimal(dl.read(PEER))
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any(
        "actor resolution returned FAILURE" in r.getMessage()
        and "peer unreachable" in r.getMessage()
        for r in warnings
    )


@pytest.mark.spec("AKM-05-001")
@pytest.mark.spec("AKM-02-006")
def test_the_deterministic_default_records_the_minimal_peer_quietly(
    dl, caplog
):
    with caplog.at_level(logging.WARNING):
        _record_named_peer(dl, PEER, "peer_id", ACTING)

    assert _is_minimal(dl.read(PEER))
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


@pytest.mark.spec("BTND-03-021")
def test_a_record_left_by_an_earlier_run_is_never_kept(dl):
    """A *yes* with no record keeps the minimal peer, not a stale one."""
    stale = py_trees.blackboard.Client(name="stale-writer")
    stale.register_key(RESOLVED_ACTOR_KEY, py_trees.common.Access.WRITE)
    stale.set(RESOLVED_ACTOR_KEY, _peer_profile())
    calls: list[str] = []

    _record(dl, _counting_backend(calls))

    assert calls == ["ResolveActorDetails"]
    assert _is_minimal(dl.read(PEER))
    # The run restores what it found, so it neither clears nor leaks the key.
    assert stale.get(RESOLVED_ACTOR_KEY).name == "Peer Org"
    stale.unregister_key(RESOLVED_ACTOR_KEY, clear=True)


@pytest.mark.spec("AKM-05-002")
def test_a_live_adapter_profile_is_stored(dl):
    body = _peer_profile().model_dump(mode="json", by_alias=True)

    class _Fetcher:
        async def fetch(self, reference, requester_id):
            return ObjectFetchResult(body, None, 1)

    live = HttpActorResolutionAdapter(
        HttpActorProfileFetchAdapter(_Fetcher()),  # type: ignore[arg-type]
        budget=timedelta(seconds=5),
    )

    _record_through(dl, live)

    stored = dl.read(PEER)
    assert isinstance(stored, VultronOrganization)
    assert stored.name == "Peer Org"
