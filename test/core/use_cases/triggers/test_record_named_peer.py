"""``_record_named_peer`` runs a real discovery backend with its ports wired.

A backend that reads ``self.datalayer`` in ``update()`` needs ``setup()`` and
``initialise()`` to have run; ticking it bare left that attribute ``None``
(#2707).
"""

from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.call_out.bundles.actor_discovery import (
    ActorDiscoveryCallOutBundle,
)
from vultron.core.behaviors.helpers.ports_base import (
    DataLayerConditionWithPorts,
)
from vultron.core.models.actor import CoreActor
from vultron.core.use_cases.triggers.actor._peers import _record_named_peer

ACTING = "https://example.org/actors/acting"
PEER = "https://example.org/actors/peer"

_seen: list[object] = []


class _DirectoryBackend(DataLayerConditionWithPorts):
    def initialise(self) -> None:
        self.datalayer = self.get_input("datalayer")

    def update(self) -> Status:
        _seen.append(self.datalayer.read(PEER))  # type: ignore[union-attr]
        return Status.SUCCESS


def test_real_backend_has_datalayer_when_record_named_peer_ticks_it():
    _seen.clear()
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=ACTING)
    try:
        dl.clear_all()
        bundle = ActorDiscoveryCallOutBundle(
            resolve_actor_factory=_DirectoryBackend
        )
        _record_named_peer(dl, PEER, "peer_id", ACTING, bundle)
        assert _seen == [None]
        assert isinstance(dl.read(PEER), CoreActor)
    finally:
        dl.close()
