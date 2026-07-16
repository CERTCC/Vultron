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
"""Call-out point factory type for the Vultron BT port/adapter seam.

This module defines the :data:`CallOutBackendFactory` type alias used by tree
builder functions to accept swappable call-out point backends (ADR-0025).

The type alias lives here (in ``vultron.core.behaviors``) so that tree
builders in ``vultron.core.behaviors.report`` can reference it without
importing from ``vultron.demo``, maintaining the hexagonal-architecture
layering rule (BT-16-001: simulation artifacts stay out of core).

The shape mixin classes and illustrative examples live in
``vultron.demo.fuzzer.call_out_point``.

References
----------
- ADR-0025: ``docs/adr/0025-call-out-point-abstraction-layer.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-18-004
"""

from __future__ import annotations

from typing import Callable

import py_trees as _py_trees

CallOutBackendFactory = Callable[[str], _py_trees.behaviour.Behaviour]
"""Factory callable type for swappable call-out point backends.

Each call-out point in a BT tree builder is constructed by calling a factory
of this type, passing the node's display name as the sole argument.  Tree
builder functions accept one factory parameter per injected call-out point
and default to the corresponding fuzzer factory (BT-18-004).

The returned Behaviour must honour the call-out point's declared blackboard
contract (BT-18-001, BT-18-002): it must write all declared output keys on
SUCCESS, with type-conformant values.

Example::

    from vultron.core.behaviors.call_out_point import CallOutBackendFactory
    from vultron.demo.fuzzer.report_management.validate import (
        EvaluateReportCredibility as _FuzzerCredibility,
    )

    def create_my_tree(
        report_id: str,
        credibility_factory: CallOutBackendFactory = (
            lambda n: _FuzzerCredibility(n)
        ),
    ) -> py_trees.behaviour.Behaviour:
        node = credibility_factory("EvaluateReportCredibility")
        ...
"""
