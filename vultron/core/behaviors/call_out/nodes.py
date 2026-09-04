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
"""Deterministic constant call-out point backend nodes (BT-23-001, BT-23-002).

This module provides the two **deterministic** call-out point backends used by
the ``<DOMAIN>_DETERMINISTIC`` bundles: :class:`AlwaysSucceed` (always returns
``SUCCESS``) and :class:`AlwaysFail` (always returns ``FAILURE``).

These are core-owned, production-usable backends: the DETERMINISTIC bundle is
the happy-path default a real actor uses when a call-out point has no wired-in
capability implementation yet (ADR-0025). They deliberately carry **no** probabilistic
behaviour — that belongs exclusively to the simulation layer
(``vultron/demo/fuzzer/base.py``'s ``WeightedBehavior`` family, kept out of core
per BT-16-001).

Interface contract
------------------
Both classes are ``py_trees.behaviour.Behaviour`` subclasses constructed with a
single ``name: str`` argument, so any
:class:`~vultron.core.behaviors.call_out.protocol.CallOutBackendFactory` may
produce them interchangeably with the demo layer's ``WeightedBehavior`` nodes.

A ``success_rate`` class attribute (``1.0`` / ``0.0``) is provided so these
nodes present the same read-only rate interface as the simulation ``AlwaysSucceed``
/ ``AlwaysFail`` (which subclass ``WeightedBehavior``). This keeps the two
same-named-but-distinct node families substitutable for callers that only read
the rate; the core nodes remain non-probabilistic regardless of the value.

.. note::

    A same-named ``AlwaysSucceed`` / ``AlwaysFail`` pair also exists in
    ``vultron/demo/fuzzer/base.py`` as ``WeightedBehavior`` subclasses. The two
    pairs are intentionally **duplicated, not cross-imported**: core must not
    depend on demo (BT-16-001). They are kept substitutable through the shared
    :class:`CallOutBackendFactory` contract, not through a shared base class.

References
----------
- ADR-0025: ``docs/adr/0025-call-out-point-abstraction-layer.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-23-001, BT-23-002
"""

from __future__ import annotations

import py_trees
from py_trees.common import Status


class AlwaysSucceed(py_trees.behaviour.Behaviour):
    """Deterministic call-out backend that always returns ``SUCCESS``.

    The ceiling default for any call-out point whose stochastic success
    probability is ``>= 0.5`` (BT-23-002). Core-owned and production-usable;
    carries no probabilistic behaviour.
    """

    #: Read-only rate interface parity with the simulation ``AlwaysSucceed``.
    success_rate: float = 1.0

    def __init__(self, name: str = "") -> None:
        super().__init__(name=name or self.__class__.__name__)

    def update(self) -> Status:
        """Always return ``Status.SUCCESS``."""
        return Status.SUCCESS


class AlwaysFail(py_trees.behaviour.Behaviour):
    """Deterministic call-out backend that always returns ``FAILURE``.

    The floor default for any call-out point whose stochastic success
    probability is ``< 0.5`` (BT-23-002). Core-owned and production-usable;
    carries no probabilistic behaviour.
    """

    #: Read-only rate interface parity with the simulation ``AlwaysFail``.
    success_rate: float = 0.0

    def __init__(self, name: str = "") -> None:
        super().__init__(name=name or self.__class__.__name__)

    def update(self) -> Status:
        """Always return ``Status.FAILURE``."""
        return Status.FAILURE


class RequireCaseOwnerApprovalNode(py_trees.behaviour.Behaviour):
    """Conservative approval gate: blocking stub pending full round-trip.

    This is the DETERMINISTIC default for security-significant authorization
    gates (RSH-07-001, RSH-07-002, ADR-0076). Always returns ``FAILURE`` to
    block any downstream state adoption or side-effect execution until the
    Case Owner explicitly approves.

    .. note::
        This is a **blocking stub**. ADR-0076 specifies that the full
        implementation should perform an Offer/Accept/Reject round-trip with
        the Case Owner (send ``Offer`` carrying the pending action, wait for
        ``Accept`` or ``Reject``, return ``SUCCESS``/``FAILURE`` accordingly).
        That round-trip is tracked in a follow-on issue. Until then, this node
        permanently blocks non-owner state adoption — the correct conservative
        posture for a security-significant gate.

    A permissive override (``STATUS_AUTHORIZATION_PERMISSIVE``) is available
    for demos and trusted-participant deployments but MUST be explicitly
    configured (RSH-07-003).
    """

    #: Read-only rate interface parity with the simulation backends.
    success_rate: float = 0.0

    def __init__(self, name: str = "") -> None:
        super().__init__(name=name or self.__class__.__name__)

    def update(self) -> Status:
        """Return ``Status.FAILURE``: approval required but not yet obtained."""
        return Status.FAILURE


__all__ = ["AlwaysSucceed", "AlwaysFail", "RequireCaseOwnerApprovalNode"]
