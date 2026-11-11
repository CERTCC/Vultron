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
- :class:`~vultron.core.behaviors.call_out.answer.CallOutAnswer`,
  :class:`~vultron.core.behaviors.call_out.answer.CallOutVerdict` and
  :class:`~vultron.core.behaviors.call_out.answer.CallOutContract` — the
  *yes* / *no* / *error* answer every backend gives and the declaration it is
  checked against (ADR-0183).
- :class:`~vultron.core.behaviors.call_out.backend.CallOutBackend` — the base
  class every backend subclasses.
- :class:`~vultron.core.behaviors.call_out.guard.SynchronousCallOut` — the
  seam that turns an answer into tree behaviour, and
  :class:`~vultron.core.behaviors.call_out.guard.TimeBoundedCallOut`, the seam
  with the configured time budget that every bundle hands out (BT-18-015).
- :class:`~vultron.core.behaviors.call_out.actuator.ActuatorBackend` and
  :func:`~vultron.core.behaviors.call_out.actuator.actuator_call` — an
  Actuator acts on one target per call, keyed on an idempotency id the tree
  derives from the act and the target (BT-18-041 to BT-18-044).
- :class:`~vultron.core.behaviors.call_out.capability.EvaluatorCapability`,
  :class:`~vultron.core.behaviors.call_out.capability.RetrieverCapability`,
  :class:`~vultron.core.behaviors.call_out.capability.ComposerCapability` and
  :class:`~vultron.core.behaviors.call_out.capability.ActuatorCapability` —
  the four capability shapes.  Each named capability is declared once, with
  its typed ports, in ``capabilities``, and
  :func:`~vultron.core.behaviors.call_out.capabilities.capability_declarations`
  enumerates them (BT-18-012, BT-18-021).
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

from vultron.core.behaviors.call_out.actuator import (
    ACTUATOR_CONTRACT,
    ActuationRequest,
    ActuatorBackend,
    ActuatorContract,
    actuation_id,
    actuator_call,
)
from vultron.core.behaviors.call_out.answer import (
    BINARY_CONTRACT,
    REFUSAL_REASON_KEY,
    CallOutAnswer,
    CallOutContract,
    CallOutVerdict,
)
from vultron.core.behaviors.call_out.backend import CallOutBackend
from vultron.core.behaviors.call_out.capabilities import (
    capability_declarations,
)
from vultron.core.behaviors.call_out.capability import (
    ActuatorCapability,
    Capability,
    CapabilityShape,
    ComposerCapability,
    EvaluatorCapability,
    RetrieverCapability,
)
from vultron.core.behaviors.call_out.guard import (
    CallOutBackendError,
    CallOutBudgetExceededError,
    CallOutContractError,
    SynchronousCallOut,
    TimeBoundedCallOut,
    guard_call_out_factory,
    time_bounded_call_out,
    unwrap_call_out,
)
from vultron.core.behaviors.call_out.nodes import (
    AlwaysFail,
    AlwaysSucceed,
    NoOpActuator,
    RequireCaseOwnerApprovalNode,
)
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory

__all__ = [
    "ActuatorCapability",
    "Capability",
    "CapabilityShape",
    "ComposerCapability",
    "EvaluatorCapability",
    "RetrieverCapability",
    "capability_declarations",
    "ACTUATOR_CONTRACT",
    "ActuationRequest",
    "ActuatorBackend",
    "ActuatorContract",
    "actuation_id",
    "actuator_call",
    "NoOpActuator",
    "BINARY_CONTRACT",
    "REFUSAL_REASON_KEY",
    "CallOutAnswer",
    "CallOutBackend",
    "CallOutBackendError",
    "CallOutBudgetExceededError",
    "CallOutContract",
    "CallOutVerdict",
    "CallOutBackendFactory",
    "AlwaysSucceed",
    "AlwaysFail",
    "RequireCaseOwnerApprovalNode",
    "CallOutContractError",
    "SynchronousCallOut",
    "TimeBoundedCallOut",
    "guard_call_out_factory",
    "time_bounded_call_out",
    "unwrap_call_out",
]
