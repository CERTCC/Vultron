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
"""Actor-resolution fuzzer node for the Vultron demo layer.

Provides the simulation node of
:class:`~vultron.core.behaviors.call_out.capabilities.actor_resolution.ResolveActorDetailsCapability`,
which the STOCHASTIC bundle
(:data:`vultron.demo.fuzzer.bundles.actor_resolution.ACTOR_RESOLUTION_STOCHASTIC`)
places.  It satisfies BT-16-003 and BT-16-007 (a named integration-point node
with a semantic docstring) and BT-16-005 (automation-potential
categorization).

References
----------
- Spec: ``specs/actor-knowledge-model.yaml`` AKM-05-002;
  ``specs/behavior-tree-integration.yaml`` BT-16-003, BT-16-005, BT-18-021
"""

from __future__ import annotations

from vultron.core.behaviors.call_out.capabilities.actor_resolution import (
    ResolveActorDetailsCapability,
)
from vultron.demo.fuzzer.base import AlmostAlwaysSucceed


class ResolveActorDetails(ResolveActorDetailsCapability, AlmostAlwaysSucceed):
    """Return the actor record of a peer this actor knows only by its URI.

    Simulates :class:`ResolveActorDetailsCapability`,
    whose ports are its blackboard contract (BT-18-021).

    Semantic function:
        Retriever — look up a named peer's profile in a directory service
        or by fetching it from the peer.  The simulated *yes* carries a
        record that names no peer, so the caller keeps the peer's URI
        alone, as it does on a *no* (AKM-05-001).

    Input category: System integration.

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **High** — a profile fetch or directory lookup
    keyed on the peer's URI needs no human judgment.
    """


__all__ = ["ResolveActorDetails"]
