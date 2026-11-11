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

Provides :class:`ActorResolutionCallOutBundle` and the pre-built core
DETERMINISTIC singleton :data:`ACTOR_RESOLUTION_DETERMINISTIC`.  The matching
STOCHASTIC singleton lives in the simulation layer
(:data:`vultron.demo.fuzzer.bundles.actor_resolution.ACTOR_RESOLUTION_STOCHASTIC`).

Actor resolution is a Retriever call-out (ADR-0024): given an actor URI, the
backend attempts to resolve the actor's details from an external directory
service or static registry.  The seam is injectable so callers can swap in a
real directory-service client without touching the core protocol logic.

Ceiling/floor mapping (BT-23-002):

- ``resolve_actor_factory`` — ResolveActorDetails (p=0.90) → AlwaysSucceed.
  No directory service is wired by default; a bare actor URI is sufficient to
  address an outbound activity (AKM-05-001), so the protocol is not blocked
  when discovery returns no details.

References
----------
- ADR-0024: ``docs/adr/0024-coordination-agent-taxonomy.md``
- ADR-0025: ``docs/adr/0025-call-out-point-abstraction-layer.md``
- Spec: ``specs/actor-knowledge-model.yaml`` AKM-05
"""

from __future__ import annotations

from dataclasses import dataclass, field

from vultron.core.behaviors.call_out.bundles.base import CallOutBundle
from vultron.core.behaviors.call_out.nodes import AlwaysSucceed
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory


@dataclass(frozen=True)
class ActorResolutionCallOutBundle(CallOutBundle):
    """Call-out backend bundle for the actor resolution domain.

    The single field backs the Retriever call-out point that resolves an actor
    URI to a :class:`~vultron.core.models.actor.CoreActor` record from an
    external directory service or static registry.

    Defaults to ``AlwaysSucceed`` — the actor URI alone is sufficient to
    address an outbound activity, so the protocol does not block when no
    directory service is wired (AKM-05-001).
    """

    resolve_actor_factory: CallOutBackendFactory = field(
        default=AlwaysSucceed  # type: ignore[assignment]
    )
    """ResolveActorDetails (Retriever): p=0.90 → AlwaysSucceed.

    Store-held answer (BT-18-039): **can**.  The actor's own store holds the
    record of every peer it knows, so the caller reads the store first and
    does not call this Retriever for a peer it already holds
    (:func:`~vultron.core.use_cases.triggers.actor._peers._record_named_peer`).
    """


ACTOR_RESOLUTION_DETERMINISTIC = ActorResolutionCallOutBundle()
"""Deterministic bundle: resolve_actor uses AlwaysSucceed (BT-23-001, BT-23-002)."""

__all__ = [
    "ActorResolutionCallOutBundle",
    "ACTOR_RESOLUTION_DETERMINISTIC",
]
