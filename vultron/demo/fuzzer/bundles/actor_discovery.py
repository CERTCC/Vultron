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
"""STOCHASTIC call-out bundle for the actor discovery domain.

Provides the simulation-layer :data:`ACTOR_DISCOVERY_STOCHASTIC` singleton.
The bundle dataclass and DETERMINISTIC default are core concerns
(``vultron.core.behaviors.call_out.bundles.actor_discovery``) and are
re-exported here for backward-compatible import paths.

Actor discovery is a production-only domain: the demo seeds actors into each
other's DataLayers so scenarios need no global directory (AC-2).  The
STOCHASTIC singleton uses ``AlmostAlwaysSucceed`` (p=0.90) to occasionally
exercise the FAILURE path during fuzz runs, matching the convention for
lookup-style Retriever call-outs with no named simulator fuzzer node.  The
DETERMINISTIC ceiling of p=0.90 is ``AlwaysSucceed`` (BT-23-002).
"""

from __future__ import annotations

import py_trees

from vultron.core.behaviors.call_out.bundles.actor_discovery import (  # noqa: F401
    ACTOR_DISCOVERY_DETERMINISTIC,
    ActorDiscoveryCallOutBundle,
)


def _stochastic_resolve_actor(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.base import AlmostAlwaysSucceed

    return AlmostAlwaysSucceed(name)


ACTOR_DISCOVERY_STOCHASTIC = ActorDiscoveryCallOutBundle(
    resolve_actor_factory=_stochastic_resolve_actor,  # type: ignore[arg-type]
)
"""Stochastic bundle: resolve_actor uses AlmostAlwaysSucceed (p=0.90)."""

__all__ = [
    "ActorDiscoveryCallOutBundle",
    "ACTOR_DISCOVERY_DETERMINISTIC",
    "ACTOR_DISCOVERY_STOCHASTIC",
]
