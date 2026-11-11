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
the ``<DOMAIN>_DETERMINISTIC`` bundles: :class:`AlwaysSucceed` (always answers
*yes*) and :class:`AlwaysFail` (always answers *no*), and
:class:`NoOpActuator`, the :class:`AlwaysSucceed` every Actuator field
defaults to.

A bundle field that answers a declared capability binds its default to that
capability's core declaration with :func:`always_succeed_as` or
:func:`always_fail_as`.  The bound default takes the declaration's ports as
its contract, so a *yes* writes every declared output port with a
type-conformant value (:func:`~vultron.core.behaviors.call_out.answer.constant_yes`,
BT-23-013) and the default is traceable to the capability it stands in for.
The mechanism reads the declaration; nothing is written per capability.

These are core-owned, production-usable backends: the DETERMINISTIC bundle is
the happy-path default a real actor uses when a call-out point has no wired-in
capability implementation yet (ADR-0025). They deliberately carry **no** probabilistic
behaviour — that belongs exclusively to the simulation layer
(``vultron/demo/fuzzer/base.py``'s ``WeightedBehavior`` family, kept out of core
per BT-16-001).

Interface contract
------------------
Both classes are :class:`~vultron.core.behaviors.call_out.backend.CallOutBackend`
subclasses constructed with a single ``name: str`` argument: ``AlwaysSucceed``
answers *yes* and ``AlwaysFail`` answers *no* (ADR-0183).  Any
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
- Spec: ``specs/behavior-tree-integration.yaml`` BT-23-001, BT-23-002,
  BT-23-013
"""

from __future__ import annotations

import functools

from vultron.core.behaviors.call_out.actuator import ActuatorBackend
from vultron.core.behaviors.call_out.answer import (
    CallOutAnswer,
    constant_yes,
    yes_value,
)
from vultron.core.behaviors.call_out.backend import CallOutBackend
from vultron.core.behaviors.call_out.capability import (
    ActuatorCapability,
    Capability,
)

#: The reason every :class:`AlwaysFail` refusal carries.
DETERMINISTIC_REFUSAL_REASON = (
    "DETERMINISTIC default: this call-out point declines (BT-23-002)"
)

#: The reason every :class:`RequireCaseOwnerApprovalNode` refusal carries.
CASE_OWNER_APPROVAL_REQUIRED_REASON = (
    "Case Owner approval is required and has not been obtained (RSH-07-001)"
)


class AlwaysSucceed(CallOutBackend):
    """Deterministic call-out backend that always answers *yes*.

    The ceiling default for any call-out point whose stochastic success
    probability is ``>= 0.5`` (BT-23-002). Core-owned and production-usable;
    carries no probabilistic behaviour.

    Its *yes* carries a value for every output its ``contract`` declares
    (:func:`~vultron.core.behaviors.call_out.answer.constant_yes`): none for
    the bare class, every declared port once :func:`always_succeed_as`
    binds it to a capability declaration (BT-23-013).
    """

    #: Read-only rate interface parity with the simulation ``AlwaysSucceed``.
    success_rate: float = 1.0

    def answer(self) -> CallOutAnswer:
        """Always answer *yes*, with a value for every declared output."""
        return constant_yes(self.contract)


class AlwaysFail(CallOutBackend):
    """Deterministic call-out backend that always answers *no*.

    The floor default for any call-out point whose stochastic success
    probability is ``< 0.5`` (BT-23-002). Core-owned and production-usable;
    carries no probabilistic behaviour.
    """

    #: Read-only rate interface parity with the simulation ``AlwaysFail``.
    success_rate: float = 0.0

    def answer(self) -> CallOutAnswer:
        """Always answer *no*, with :data:`DETERMINISTIC_REFUSAL_REASON`."""
        return CallOutAnswer.no(DETERMINISTIC_REFUSAL_REASON)


class NoOpActuator(ActuatorBackend, AlwaysSucceed):
    """Deterministic Actuator default: acts on nothing and answers *yes*.

    The ceiling default (an :class:`AlwaysSucceed`, BT-23-002) of every
    Actuator call-out point a deployment has not wired.  It causes no side
    effect, so a repeat under the same idempotency id repeats nothing
    (BT-18-044), and it still refuses a tick with no bound target
    (BT-18-041).
    """


class RequireCaseOwnerApprovalNode(CallOutBackend):
    """Conservative approval gate: blocking stub pending full round-trip.

    This is the DETERMINISTIC default for security-significant authorization
    gates (RSH-07-001, ADR-0076). Always answers *no* to block any
    downstream state adoption until the Case Owner explicitly approves.

    .. note::
        This is a **blocking stub**. ADR-0076 specifies that the full
        implementation should perform an Offer/Accept/Reject round-trip with
        the Case Owner (send ``Offer`` carrying the pending action, wait for
        ``Accept`` or ``Reject``, answer *yes* or *no* accordingly).
        That round-trip is tracked in a follow-on issue. Until then, this node
        permanently blocks non-owner state adoption — the correct conservative
        posture for a security-significant gate.

    A permissive override (``STATUS_AUTHORIZATION_PERMISSIVE``) is available
    for demos and trusted-participant deployments but MUST be explicitly
    configured (RSH-07-003).
    """

    #: Read-only rate interface parity with the simulation backends.
    success_rate: float = 0.0

    def answer(self) -> CallOutAnswer:
        """Answer *no*: approval is required but not yet obtained."""
        return CallOutAnswer.no(CASE_OWNER_APPROVAL_REQUIRED_REASON)


@functools.cache
def _bound(
    declaration: type[Capability], constant: type[CallOutBackend]
) -> type[CallOutBackend]:
    """The class that answers as *constant* and binds to *declaration*.

    Cached, so every field bound to one capability builds one class.  The
    class is built at run time and is not an attribute of this module, so
    its ``__qualname__`` names it for logs and tree displays only; it is
    not importable or picklable by reference.
    """
    if not (
        isinstance(declaration, type)
        and issubclass(declaration, Capability)
        and declaration.declaration() is declaration
    ):
        raise TypeError(
            f"{declaration!r} is not a capability declaration; a default "
            "binds to a core declaration under "
            "vultron.core.behaviors.call_out.capabilities (BT-18-021)."
        )
    if constant is AlwaysFail and declaration.REFUSAL_PORTS:
        raise TypeError(
            f"{declaration.__name__} declares refusal ports "
            f"{sorted(declaration.REFUSAL_PORTS)}, which AlwaysFail does not "
            "give; its floor default is a backend that builds them "
            "(ADR-0183)."
        )
    if constant is AlwaysSucceed and issubclass(
        declaration, ActuatorCapability
    ):
        constant = NoOpActuator
    for typ in declaration.contract.outputs.values():
        # Fail when the bundle is built, not on the first yes.
        yes_value(typ)
    stem = declaration.__name__.removesuffix("Capability")
    name = f"{constant.__name__}{stem}"
    bound = type(
        name,
        (declaration, constant),
        {
            "__module__": __name__,
            "__qualname__": name,
            "__doc__": (
                f"DETERMINISTIC {constant.__name__} bound to "
                f":class:`{declaration.__module__}.{declaration.__qualname__}`"
                " (BT-23-013); built by :func:`always_succeed_as` or "
                ":func:`always_fail_as`."
            ),
        },
    )
    return bound


def always_succeed_as(declaration: type[Capability]) -> type[CallOutBackend]:
    """The DETERMINISTIC ceiling default for *declaration* (BT-23-002, BT-23-013).

    Returns an :class:`AlwaysSucceed` (a :class:`NoOpActuator` for an
    Actuator) that binds to *declaration*: its *yes* writes every output
    port the declaration names, with
    :func:`~vultron.core.behaviors.call_out.answer.yes_value`.  The class is
    a :class:`~vultron.core.behaviors.call_out.protocol.CallOutBackendFactory`,
    so a bundle field defaults to it directly.

    Raises:
        TypeError: *declaration* is not a core capability declaration, or
            declares an output port no constant value can fill.
    """
    return _bound(declaration, AlwaysSucceed)


def always_fail_as(declaration: type[Capability]) -> type[CallOutBackend]:
    """The DETERMINISTIC floor default for *declaration* (BT-23-006).

    Returns an :class:`AlwaysFail` that binds to *declaration*.  It answers
    *no* exactly as :class:`AlwaysFail` does; the binding names the
    capability it stands in for, so a check can find its ports
    (BT-18-002 binds only a *yes*).

    Raises:
        TypeError: *declaration* is not a core capability declaration.
    """
    return _bound(declaration, AlwaysFail)


__all__ = [
    "AlwaysSucceed",
    "AlwaysFail",
    "CASE_OWNER_APPROVAL_REQUIRED_REASON",
    "DETERMINISTIC_REFUSAL_REASON",
    "NoOpActuator",
    "RequireCaseOwnerApprovalNode",
    "always_fail_as",
    "always_succeed_as",
]
