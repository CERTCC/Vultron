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
"""STOCHASTIC call-out bundle for the actor resolution domain.

Provides the simulation-layer :data:`ACTOR_RESOLUTION_STOCHASTIC` singleton.
The bundle dataclass and DETERMINISTIC default are core concerns
(``vultron.core.behaviors.call_out.bundles.actor_resolution``) and are
re-exported here for backward-compatible import paths.

Actor resolution is a production-only domain: the demo seeds actors into each
other's DataLayers so scenarios need no global directory (AC-2).  The
STOCHASTIC singleton places the named node
:class:`~vultron.demo.fuzzer.actor_resolution.ResolveActorDetails`, an
``AlmostAlwaysSucceed`` (p=0.90) bound to the core declaration, to
occasionally exercise the FAILURE path during fuzz runs.  The DETERMINISTIC
ceiling of p=0.90 is the ``AlwaysSucceed`` bound to that declaration
(BT-23-002, BT-23-013).
"""

from __future__ import annotations

from vultron.core.behaviors.call_out.bundles.actor_resolution import (
    ACTOR_RESOLUTION_DETERMINISTIC,
    ActorResolutionCallOutBundle,
)
from vultron.demo.fuzzer.actor_resolution import ResolveActorDetails

ACTOR_RESOLUTION_STOCHASTIC = ActorResolutionCallOutBundle(
    resolve_actor_factory=ResolveActorDetails,  # type: ignore[arg-type]
)
"""Stochastic bundle: resolve_actor uses ResolveActorDetails (p=0.90)."""

__all__ = [
    "ActorResolutionCallOutBundle",
    "ACTOR_RESOLUTION_DETERMINISTIC",
    "ACTOR_RESOLUTION_STOCHASTIC",
]
