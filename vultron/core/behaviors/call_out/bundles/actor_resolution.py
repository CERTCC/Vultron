#!/usr/bin/env python
#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""Call-out bundle for the actor resolution domain (ADR-0024, ADR-0025).

Provides :class:`ActorResolutionCallOutBundle`, the pre-built core
DETERMINISTIC singleton :data:`ACTOR_RESOLUTION_DETERMINISTIC`, and the
backend that answers through an
:class:`~vultron.core.ports.actor_resolution.ActorResolutionPort`
(:class:`ResolveActorDetailsThroughPort`).  The matching STOCHASTIC singleton
lives in the simulation layer
(:data:`vultron.demo.fuzzer.bundles.actor_resolution.ACTOR_RESOLUTION_STOCHASTIC`).

Actor resolution is a Retriever call-out
(:class:`~vultron.core.behaviors.call_out.capabilities.actor_resolution.ResolveActorDetailsCapability`):
given a peer's URI, it returns the peer's actor record.  A deployment wires a
source by building the bundle with :func:`actor_resolution_bundle` over an
adapter of the port: the static adapter returns a profile declared up front,
the live one fetches the peer's profile (AKM-05-002).

Ceiling/floor mapping (BT-23-002, BT-23-013):

- ``resolve_actor_factory`` — ResolveActorDetails (p=0.90) → the ceiling bound
  to the declaration (:func:`always_succeed_as`).  Its *yes* carries a
  type-conformant record that names no peer, so the caller keeps the peer's
  URI alone (AKM-05-001, AKM-02-006): with no source wired, a bare URI is
  enough to address the peer.

References
----------
- ADR-0024: ``docs/adr/0024-coordination-agent-taxonomy.md``
- ADR-0025: ``docs/adr/0025-call-out-point-abstraction-layer.md``
- ADR-0183: ``docs/adr/0183-a-call-out-backend-answers-yes-no-or-error-and-the-seam-turns-the-answer-into-tree-behaviour.md``
- Spec: ``specs/actor-knowledge-model.yaml`` AKM-05
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field

from vultron.core.behaviors.call_out.answer import CallOutAnswer
from vultron.core.behaviors.call_out.bundles.base import CallOutBundle
from vultron.core.behaviors.call_out.capabilities.actor_resolution import (
    PEER_ACTOR_ID_KEY,
    REQUESTER_ACTOR_ID_KEY,
    RESOLVED_ACTOR_KEY,
    ResolveActorDetailsCapability,
)
from vultron.core.behaviors.call_out.nodes import always_succeed_as
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory
from vultron.core.ports.actor_resolution import ActorResolutionPort
from vultron.errors import VultronActorProfileFetchError


class ResolveActorDetailsThroughPort(ResolveActorDetailsCapability):
    """ResolveActorDetails answered by an :class:`ActorResolutionPort`.

    Reads the peer's URI and the acting actor from its input ports and asks
    the port.  A record is *yes*; the port's ``None``, a source that holds
    no record for the peer, is *no*; a
    :class:`~vultron.errors.VultronActorProfileFetchError`, a source that
    could not be asked, is *error* (ADR-0183).  Any other raise is a fault
    in the adapter and leaves the seam as one.

    Build it through :func:`resolve_actor_through`, which binds the port.

    Args:
        name: The node's display name.
        port: The source the backend asks.
    """

    def __init__(self, name: str = "", *, port: ActorResolutionPort) -> None:
        super().__init__(name)
        self._port = port

    def answer(self) -> CallOutAnswer:
        """Ask the port for the peer's record (see the class docstring)."""
        peer_id = str(self.get_input(PEER_ACTOR_ID_KEY))
        requester_id = str(self.get_input(REQUESTER_ACTOR_ID_KEY))
        try:
            record = self._port.resolve_actor(peer_id, requester_id)
        except VultronActorProfileFetchError as exc:
            return CallOutAnswer.error(f"resolving {peer_id!r} failed: {exc}")
        if record is None:
            return CallOutAnswer.no(
                f"the actor-resolution source holds no record for {peer_id!r}"
            )
        return CallOutAnswer.yes({RESOLVED_ACTOR_KEY: record})


def resolve_actor_through(port: ActorResolutionPort) -> CallOutBackendFactory:
    """A ``resolve_actor_factory`` that answers through *port*."""
    return functools.partial(ResolveActorDetailsThroughPort, port=port)


@dataclass(frozen=True)
class ActorResolutionCallOutBundle(CallOutBundle):
    """Call-out backend bundle for the actor resolution domain.

    The single field backs the Retriever call-out point that resolves a
    peer's URI to its :class:`~vultron.core.models.actor.CoreActor` record
    (:class:`ResolveActorDetailsCapability`).

    Defaults to the ceiling bound to that declaration: the actor URI alone
    is sufficient to address an outbound activity, so the protocol does not
    block when no source is wired (AKM-05-001).
    """

    resolve_actor_factory: CallOutBackendFactory = field(
        default=always_succeed_as(ResolveActorDetailsCapability)  # type: ignore[assignment]
    )
    """ResolveActorDetails (Retriever): p=0.90 → the bound ceiling.

    Store-held answer (BT-18-039): **can**.  The actor's own store holds the
    record of every peer it knows, so the caller reads the store first and
    does not call this Retriever for a peer it already holds
    (:func:`~vultron.core.use_cases.triggers.actor._peers._record_named_peer`).
    """


def actor_resolution_bundle(
    port: ActorResolutionPort,
) -> ActorResolutionCallOutBundle:
    """The bundle whose ResolveActorDetails answers through *port*."""
    return ActorResolutionCallOutBundle(
        resolve_actor_factory=resolve_actor_through(port)
    )


ACTOR_RESOLUTION_DETERMINISTIC = ActorResolutionCallOutBundle()
"""Deterministic bundle: resolve_actor is the bound ceiling (BT-23-001, BT-23-013)."""

__all__ = [
    "ACTOR_RESOLUTION_DETERMINISTIC",
    "ActorResolutionCallOutBundle",
    "ResolveActorDetailsThroughPort",
    "actor_resolution_bundle",
    "resolve_actor_through",
]
