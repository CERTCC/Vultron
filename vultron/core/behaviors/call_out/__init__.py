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
"""Core-owned call-out point seam: Protocol, deterministic nodes, and bundles.

This package holds the parts of the call-out point abstraction (ADR-0025) that
are **core concerns**, kept out of the simulation layer so that
``vultron.core.behaviors`` tree builders never import ``vultron.demo``
(BT-16-001):

- :class:`~vultron.core.behaviors.call_out.protocol.CallOutBackendFactory` —
  the swappable-backend Protocol (BT-23-004).
- :class:`~vultron.core.behaviors.call_out.nodes.AlwaysSucceed` /
  :class:`~vultron.core.behaviors.call_out.nodes.AlwaysFail` — deterministic,
  production-usable constant backends (BT-23-002).
- ``bundles`` — per-domain bundle dataclasses and their ``<DOMAIN>_DETERMINISTIC``
  singletons (BT-23-003), the happy-path defaults every tree builder uses when
  no explicit ``call_out`` bundle is supplied.

The probabilistic ``WeightedBehavior`` node family and the
``<DOMAIN>_STOCHASTIC`` bundles remain in ``vultron.demo.fuzzer`` — they are
simulation artifacts and are injected explicitly via ``call_out=`` by demo /
test code.
"""

from vultron.core.behaviors.call_out.nodes import (
    AlwaysFail,
    AlwaysSucceed,
    RequireCaseOwnerApprovalNode,
)
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory

__all__ = [
    "CallOutBackendFactory",
    "AlwaysSucceed",
    "AlwaysFail",
    "RequireCaseOwnerApprovalNode",
]
