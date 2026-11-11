"""``_record_named_peer`` runs a real discovery backend with its ports wired.

A backend that reads ``self.datalayer`` in ``update()`` needs ``setup()`` and
``initialise()`` to have run; ticking it bare left that attribute ``None``
(#2707).  Running it through a ``BTBridge`` also means a backend that raises no
longer crashes the request: it degrades to a minimal peer, like any other
non-SUCCESS, and the bridge logs the internal error.
"""

import logging
from collections.abc import Callable, Iterator

import py_trees
import pytest
from py_trees.common import Status

from test.support.objects import make
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.call_out.answer import CallOutAnswer
from vultron.core.behaviors.call_out.backend import CallOutBackend
from vultron.core.behaviors.call_out.bundles.actor_resolution import (
    ActorResolutionCallOutBundle,
)
from vultron.core.behaviors.helpers.ports_base import (
    DataLayerConditionWithPorts,
)
from vultron.core.models.actor import CoreActor
from vultron.core.use_cases.triggers.actor._peers import _record_named_peer

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
