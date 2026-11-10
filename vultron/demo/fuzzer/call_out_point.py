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
"""Call-out point shape mixins for the Vultron demo fuzzer.

This module provides:

- :data:`CallOutBackendFactory` — the factory callable type used to inject
  swappable backends into tree builder functions (ADR-0025, BT-18-004).
- Four shape mixin classes, one per capability shape (Evaluator, Retriever,
  Composer, Actuator), that name the shape of a fuzzer node.

A fuzzer node combines one shape mixin with a ``WeightedBehavior``
probability class from :mod:`vultron.demo.fuzzer.base`.  The probability
class is the :class:`~vultron.core.behaviors.call_out.backend.CallOutBackend`:
it answers *yes* with a zero value for each output the node's ``contract``
declares (BT-18-003) and *no* with a reason, and the seam
(:class:`~vultron.core.behaviors.call_out.guard.SynchronousCallOut`) writes
them (ADR-0183).  The mixins carry no behaviour of their own; the Actuator
mixin refuses a subclass that declares outputs (BT-18-028).

There is no Sentinel mixin.  A Sentinel is a call-in integration pattern, not
a capability shape: it watches a condition and calls a trigger endpoint on its
own initiative, so it has no call-out point node, no blackboard contract and no
backend factory (ADR-0097, BT-18-013).

References
----------
- ADR-0024: ``docs/adr/0024-coordination-agent-taxonomy.md``
- ADR-0025: ``docs/adr/0025-call-out-point-abstraction-layer.md``
- ADR-0097: ``docs/adr/0097-capability-layer-four-shapes-and-core-declared-contracts.md``
- ADR-0183: ``docs/adr/0183-a-call-out-backend-answers-yes-no-or-error-and-the-seam-turns-the-answer-into-tree-behaviour.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-18-001 through BT-18-004
"""

from __future__ import annotations

from typing import Any

from vultron.core.behaviors.call_out_point import (
    CallOutBackendFactory,
)

__all__ = [
    "CallOutBackendFactory",
    "EvaluatorCallOutPoint",
    "RetrieverCallOutPoint",
    "ComposerCallOutPoint",
    "ActuatorCallOutPoint",
]


# ---------------------------------------------------------------------------
# Shape mixin classes
# ---------------------------------------------------------------------------


class EvaluatorCallOutPoint:
    """Mixin for Evaluator-shaped call-out points (ADR-0024).

    An Evaluator receives situation context and records a decision: on *yes*
    it gives a structured recommendation for its declared output ports
    (BT-18-002, BT-18-003); on *no* it gives the reason for the decision
    (BT-18-007, ADR-0183).

    Subclasses must:
      - Declare ``contract`` with the output ports given on *yes* and their
        expected Python types.
      - Document a blackboard contract section in their docstring (BT-18-001).

    Example blackboard contract docstring section::

        Blackboard contract (BT-18-001):
          Input keys:  report_id — str (read from caller's context)
          Output keys: credibility_verdict: str  (yes only)
    """


class RetrieverCallOutPoint:
    """Mixin for Retriever-shaped call-out points (ADR-0024).

    A Retriever receives an on-demand query and gives structured facts from
    an external source for its declared output ports on *yes*.  For
    binary-result Retrievers (boolean queries), the contract declares no
    outputs and the result is the verdict alone (BT-18-006, BT-18-010).

    Subclasses must:
      - Declare ``contract``.
      - Document a blackboard contract section in their docstring (BT-18-001).
    """


class ComposerCallOutPoint:
    """Mixin for Composer-shaped call-out points (ADR-0024).

    A Composer receives composition context and gives a generated content
    artifact for a declared output port on *yes*.  The distinction from an
    Evaluator is semantic: a Composer generates a *new* content artifact
    (advisory, patch notes, exploit write-up), whereas an Evaluator produces
    a recommendation.

    Subclasses must:
      - Declare ``contract`` with the artifact output port.
      - Document a blackboard contract section in their docstring (BT-18-001).
    """


class ActuatorCallOutPoint:
    """Mixin for Actuator-shaped call-out points (ADR-0024 amendment 2026-07-07).

    An Actuator receives a trigger and context; it invokes an external system
    to cause a side effect (notification dispatch, state write, queue mutation,
    API call).  It does NOT produce a content artifact on the blackboard.
    *Yes* means the side effect was confirmed; *no* means the backend decided
    not to act.  A side effect it cannot confirm is *error* (ADR-0183).

    Subclasses must:
      - Declare no outputs (see ADR-0024); a subclass that does is refused
        when the class is created (BT-18-028).
      - Document a blackboard contract section in their docstring (BT-18-001).
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        contract = getattr(cls, "contract", None)
        if contract is not None and contract.outputs:
            raise TypeError(
                f"Actuator {cls.__name__} declares outputs "
                f"{sorted(contract.outputs)}; an Actuator places no artifact "
                "on the blackboard (BT-18-028)."
            )
