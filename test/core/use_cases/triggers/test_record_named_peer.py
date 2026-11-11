"""``_record_named_peer`` runs a real discovery backend with its ports wired.

A backend that reads ``self.datalayer`` in ``update()`` needs ``setup()`` and
``initialise()`` to have run; ticking it bare left that attribute ``None``
(#2707).  Running it through a ``BTBridge`` also means a backend that raises no
longer crashes the request: it degrades to a minimal peer, like any other
non-SUCCESS, and the bridge logs the internal error.
"""

import asyncio
import logging
import threading
from collections.abc import Callable, Iterator
from datetime import timedelta

import py_trees
import pytest
from py_trees.common import Status

from test.support.act_runner import run_tree
from test.support.actor_resolution import BodyFetcher, peer_profile
from test.support.objects import make
from vultron.adapters.driven.actor_resolution import (
    HttpActorResolutionAdapter,
    StaticActorResolutionAdapter,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.http_actor_profile_fetch import (
    HttpActorProfileFetchAdapter,
)
from vultron.core.behaviors.actor_resolution_tree import (
    create_actor_resolution_tree,
)
from vultron.core.behaviors.bridge import BTBridge
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
    return peer_profile(actor_id, inbox=f"{actor_id}/inbox/")


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


def _live(fetcher: object, budget: float = 5.0) -> HttpActorResolutionAdapter:
    return HttpActorResolutionAdapter(
        fetcher,  # type: ignore[arg-type]
        budget=timedelta(seconds=budget),
    )


@pytest.mark.spec("AKM-05-002")
def test_a_live_adapter_profile_is_stored(dl):
    fetch = HttpActorProfileFetchAdapter(BodyFetcher.serving(_peer_profile()))

    _record_through(dl, _live(fetch))

    stored = dl.read(PEER)
    assert isinstance(stored, VultronOrganization)
    assert stored.name == "Peer Org"


@pytest.mark.spec("AKM-05-001")
@pytest.mark.spec("BT-18-015")
def test_a_slow_live_peer_is_an_error_answer_not_an_overrun(dl, caplog):
    """The adapter gives up inside the seam's budget, so the seam sees the
    adapter's *error*, naming the fetch, not a budget overrun (BT-18-027);
    the peer is recorded by its URI."""
    release = threading.Event()

    class _Blocking:
        async def fetch_profile(self, actor_id, requester_id):
            while not release.is_set():
                await asyncio.sleep(0.01)
            return _peer_profile(actor_id)

    try:
        with caplog.at_level(logging.WARNING):
            _record_through(dl, _live(_Blocking(), budget=0.05))
    finally:
        release.set()

    assert _is_minimal(dl.read(PEER))
    assert "CallOutBudgetExceededError" not in caplog.text
    assert any(
        "actor resolution returned FAILURE" in r.getMessage()
        and "CallOutBackendError" in r.getMessage()
        and "took longer than the resolution budget" in r.getMessage()
        for r in caplog.records
    )


def test_a_port_that_raises_otherwise_records_the_minimal_peer(dl, caplog):
    """A raise that is not a fetch error is an adapter fault: the bridge
    logs it at ERROR, and the peer is still recorded by its URI."""
    port = _Port(error=RuntimeError("adapter bug"))

    with caplog.at_level(logging.WARNING):
        _record_through(dl, port)

    assert _is_minimal(dl.read(PEER))
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert any("adapter bug" in r.getMessage() for r in errors)
    assert "actor resolution returned FAILURE" in caplog.text


@pytest.mark.spec("BTND-03-021")
def test_a_wrong_typed_resolved_actor_fails_the_whole_run(dl):
    kept: dict[str, CoreActor] = {}
    bundle = ActorResolutionCallOutBundle(
        resolve_actor_factory=_counting_backend([])  # type: ignore[arg-type]
    )
    tree = create_actor_resolution_tree(bundle.resolve_actor_factory, kept)

    result = run_tree(
        BTBridge(datalayer=dl),
        tree,
        actor_id=ACTING,
        max_iterations=1,
        resolved_actor="not an actor",
    )

    assert result.status == Status.FAILURE
    assert result.internal_error is True
    assert "CoreActor" in (result.feedback_message or "")
    assert kept == {}
