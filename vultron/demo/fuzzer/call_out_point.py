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
"""Re-export of the four capability shapes under their old fuzzer names.

The shape base classes moved to
:mod:`vultron.core.behaviors.call_out.capability` and took the capability
vocabulary (ADR-0097 decision 6):

- ``EvaluatorCallOutPoint`` is
  :class:`~vultron.core.behaviors.call_out.capability.EvaluatorCapability`;
- ``RetrieverCallOutPoint`` is
  :class:`~vultron.core.behaviors.call_out.capability.RetrieverCapability`;
- ``ComposerCallOutPoint`` is
  :class:`~vultron.core.behaviors.call_out.capability.ComposerCapability`;
- ``ActuatorCallOutPoint`` is
  :class:`~vultron.core.behaviors.call_out.capability.ActuatorCapability`.

Each old name is the same class, so ``issubclass`` checks and existing
imports keep working.  New code imports the core names.

A fuzzer node no longer subclasses a shape directly.  It subclasses its
capability's core declaration, in
:mod:`vultron.core.behaviors.call_out.capabilities`, together with a
probability class from :mod:`vultron.demo.fuzzer.base`, so the contract is
declared once, in core (BT-18-020, BT-18-021).

There is no Sentinel shape.  A Sentinel is a call-in integration pattern, not
a capability shape: it watches a condition and calls a trigger endpoint on its
own initiative, so it has no call-out point node, no blackboard contract and no
backend factory (ADR-0097, BT-18-013).

References
----------
- ADR-0097: ``docs/adr/0097-capability-layer-four-shapes-and-core-declared-contracts.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-18-012, BT-18-020,
  BT-18-021
"""

from __future__ import annotations

from vultron.core.behaviors.call_out.capability import (
    ActuatorCapability as ActuatorCallOutPoint,
    ComposerCapability as ComposerCallOutPoint,
    EvaluatorCapability as EvaluatorCallOutPoint,
    RetrieverCapability as RetrieverCallOutPoint,
)
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
