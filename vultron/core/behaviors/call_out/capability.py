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
"""The four capability shapes, and how a capability declares its ports.

A **capability** is a named call-out point: one question a tree asks a
service the actor runs.  It is declared once, in core, as a subclass of one
of the four shape base classes here
(ADR-0097#core-declared-typed-port-contract,
ADR-0097#shape-base-classes-move-to-core-and-are-renamed):

- :class:`EvaluatorCapability` records a decision;
- :class:`RetrieverCapability` returns facts from an outside source;
- :class:`ComposerCapability` produces a content artifact;
- :class:`ActuatorCapability` causes a side effect and places no artifact
  on the blackboard (BT-18-028).

A declaration names its blackboard contract as ADR-0044 typed ports
(BT-18-012): ``INPUT_PORTS`` read before it answers, ``OUTPUT_PORTS``
written on *yes*, and ``REFUSAL_PORTS``, the structured refusal fields
written on *no* beside the reason.  The ports are the authority; the
declaration's ``contract``, which the seam checks every answer against, is
derived from them and may not be set by hand.  The class docstring describes
the same ports in its ``Blackboard contract (BT-18-001):`` section.

The port lifecycle is the same for every shape, and the shape base fixes it:

- an input port is read by the backend, through :meth:`Capability.get_input`,
  while it answers;
- every output port is written by the seam
  (:class:`~vultron.core.behaviors.call_out.guard.SynchronousCallOut`) when
  the answer is *yes*, and only then (BT-18-002);
- every refusal port is written by the seam when the answer is *no*.

A port's ``data_type`` is checked on both sides.  A value of the wrong type
on an input port raises ``TypeError`` from :meth:`Capability.get_input`, and
an answer carrying a wrong-typed output raises
:class:`~vultron.core.behaviors.call_out.errors.CallOutContractError` at the
seam.  Neither is a ``VultronError``, so ``BTBridge`` fails the whole tree
run as an internal error instead of one node (BTND-03-021).  For that check
to mean anything, a declared ``data_type`` is a concrete class: ``object``
would let every value through, so a declaration naming it is refused.

The ports use py_trees' ``PortInformation`` but not its ``PortsMixin``
(``BehaviourWithPorts``), which ADR-0044 adopts for nodes that read and write
their own ports.  A capability backend writes none of its own: the seam
writes the outputs and refusal ports at the plain keys the tree reads, which
``PortsMixin`` would instead synthesize per node unless every port were
remapped.  ``PortsMixin`` also registers every concrete class by name in a
global registry, and many fuzzer nodes share a name with a core node, which
warns.  So :class:`Capability` keeps the declaration form and the checks —
one owner per port, a concrete type on both reads and writes — and leaves
the wiring to the seam.

A backend binds to a declaration by subclassing it, and so takes its ports
as they are: a subclass of a declaration that declares ports again is
refused when it is created (BT-18-021).  The probabilistic simulation node
for a capability stays in ``vultron/demo/fuzzer/`` (BT-16-001) and
subclasses the core declaration and a probability class.

The declarations live in :mod:`vultron.core.behaviors.call_out.capabilities`
and are enumerated by
:func:`~vultron.core.behaviors.call_out.capabilities.capability_declarations`.

References
----------
- ADR-0044: ``docs/adr/0044-py-trees-typed-ports-adoption.md``
- ADR-0097: ``docs/adr/0097-capability-layer-four-shapes-and-core-declared-contracts.md``
- ADR-0183: ``docs/adr/0183-a-call-out-backend-answers-yes-no-or-error-and-the-seam-turns-the-answer-into-tree-behaviour.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-18-001, BT-18-002,
  BT-18-012, BT-18-020, BT-18-021, BT-18-028;
  ``specs/behavior-tree-node-design.yaml`` BTND-03-021
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import ClassVar

import py_trees
from py_trees.common import Access
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.call_out.actuator import (
    ActuatorBackend,
    ActuatorContract,
)
from vultron.core.behaviors.call_out.answer import (
    REFUSAL_REASON_KEY,
    CallOutContract,
    is_of_port_type,
)
from vultron.core.behaviors.call_out.backend import CallOutBackend

#: The class attributes a declaration names its ports in.
PORT_ATTRIBUTES: tuple[str, ...] = (
    "INPUT_PORTS",
    "OUTPUT_PORTS",
    "REFUSAL_PORTS",
)

_NO_PORTS: Mapping[str, PortInformation] = MappingProxyType({})


class CapabilityShape(StrEnum):
    """The four call-out capability shapes (ADR-0097, BT-18-028)."""

    EVALUATOR = "Evaluator"
    RETRIEVER = "Retriever"
    COMPOSER = "Composer"
    ACTUATOR = "Actuator"


def _check_ports(
    cls: type, attribute: str, ports: object
) -> Mapping[str, PortInformation]:
    """Return *ports* frozen, or raise ``TypeError`` naming what is wrong."""
    if not isinstance(ports, Mapping):
        raise TypeError(
            f"{cls.__name__}.{attribute} is {type(ports).__name__}, not a "
            "mapping of port name to PortInformation (ADR-0044)."
        )
    for key, info in ports.items():
        if not isinstance(info, PortInformation):
            raise TypeError(
                f"{cls.__name__}.{attribute}[{key!r}] is "
                f"{type(info).__name__}, not a PortInformation (ADR-0044)."
            )
        data_type: object = info.data_type
        if not isinstance(data_type, type) or data_type is object:
            raise TypeError(
                f"{cls.__name__}.{attribute}[{key!r}] declares "
                f"{data_type!r}; a capability port names a concrete class, "
                "so its runtime type check can refuse a wrong value "
                "(ADR-0044, BTND-03-021)."
            )
        if info.has_default:
            raise TypeError(
                f"{cls.__name__}.{attribute}[{key!r}] declares a default; "
                "a capability port has none, because a missing value is "
                "the backend's to report, never a stand-in (BT-18-002)."
            )
        if attribute != "INPUT_PORTS" and not info.required:
            raise TypeError(
                f"{cls.__name__}.{attribute}[{key!r}] is optional; every "
                "declared output and refusal port is written whenever its "
                "verdict is given (BT-18-002)."
            )
    return MappingProxyType(dict(ports))


class Capability(CallOutBackend):
    """The base of the four capability shapes; see the module docstring.

    Do not subclass this directly: a declaration subclasses one of
    :class:`EvaluatorCapability`, :class:`RetrieverCapability`,
    :class:`ComposerCapability` or :class:`ActuatorCapability`.

    Class attributes:
        shape: The capability's shape, fixed by the shape base.
        INPUT_PORTS: Ports read while answering, by blackboard key.
        OUTPUT_PORTS: Ports written on *yes*, by blackboard key.
        REFUSAL_PORTS: Structured refusal ports written on *no* beside the
            reason, by blackboard key.
        REFUSAL_REASON_KEY: Blackboard key the *no* reason is written to.
        contract: Derived from the ports when the class is created; the
            declaration the seam checks every answer against (ADR-0183).
    """

    shape: ClassVar[CapabilityShape]
    INPUT_PORTS: ClassVar[Mapping[str, PortInformation]] = _NO_PORTS
    OUTPUT_PORTS: ClassVar[Mapping[str, PortInformation]] = _NO_PORTS
    REFUSAL_PORTS: ClassVar[Mapping[str, PortInformation]] = _NO_PORTS
    REFUSAL_REASON_KEY: ClassVar[str] = REFUSAL_REASON_KEY

    #: The contract class the shape derives ``contract`` as.
    _contract_type: ClassVar[type[CallOutContract]] = CallOutContract
    #: True only on the four shape bases, which declare no capability.
    _is_shape_base: ClassVar[bool] = True

    def __init_subclass__(cls, **kwargs: object) -> None:
        if "contract" in vars(cls):
            raise TypeError(
                f"{cls.__name__} sets contract; a capability's contract is "
                "derived from its declared ports, which are the authority "
                "(BT-18-012)."
            )
        own = [
            a
            for a in (*PORT_ATTRIBUTES, "REFUSAL_REASON_KEY")
            if a in vars(cls)
        ]
        bound = sorted(
            {
                klass.__qualname__
                for klass in cls.__mro__[1:]
                if isinstance(klass, type)
                and issubclass(klass, Capability)
                and klass.declaration() is klass
            }
        )
        if len(bound) > 1:
            raise TypeError(
                f"{cls.__name__} binds to the capabilities {bound}; a "
                "backend stands in for one capability, so it binds to one "
                "declaration (BT-18-021)."
            )
        declaration = cls.declaration()
        if own and declaration is not None and declaration is not cls:
            raise TypeError(
                f"{cls.__name__} declares {own} again; it binds to the "
                f"capability {declaration.__name__}, whose ports are the "
                "contract, so it does not restate them (BT-18-021)."
            )
        cls.INPUT_PORTS = _check_ports(cls, "INPUT_PORTS", cls.INPUT_PORTS)
        cls.OUTPUT_PORTS = _check_ports(cls, "OUTPUT_PORTS", cls.OUTPUT_PORTS)
        cls.REFUSAL_PORTS = _check_ports(
            cls, "REFUSAL_PORTS", cls.REFUSAL_PORTS
        )
        if overlap := sorted(
            set(cls.INPUT_PORTS) & {*cls.OUTPUT_PORTS, *cls.REFUSAL_PORTS}
        ):
            raise TypeError(
                f"{cls.__name__} declares {overlap} as both input and "
                "written ports; a port is read or written, not both "
                "(ADR-0044)."
            )
        try:
            cls.contract = cls._contract_type(
                outputs={k: p.data_type for k, p in cls.OUTPUT_PORTS.items()},
                refusal_reason_key=cls.REFUSAL_REASON_KEY,
                refusal_fields={
                    k: p.data_type for k, p in cls.REFUSAL_PORTS.items()
                },
            )
        except ValueError as exc:
            raise TypeError(f"{cls.__name__}: {exc}") from exc
        if not vars(cls).get("_is_shape_base", False):
            cls._check_shape()
        super().__init_subclass__(**kwargs)

    @classmethod
    def _check_shape(cls) -> None:
        """Raise ``TypeError`` when the ports break the shape's rule."""

    @classmethod
    def declaration(cls) -> type[Capability] | None:
        """The core declaration this class is or binds to, else ``None``.

        The declaration is the most basic class in the method resolution
        order that is a capability but not a shape base: a backend that
        subclasses a declaration answers that declaration, and a shape base
        answers ``None``.
        """
        for klass in reversed(cls.__mro__):
            if (
                isinstance(klass, type)
                and issubclass(klass, Capability)
                and not vars(klass).get("_is_shape_base", False)
            ):
                return klass
        return None

    def __init__(self, name: str = "") -> None:
        super().__init__(name)
        self._inputs: py_trees.blackboard.Client | None = None
        if self.INPUT_PORTS:
            self._inputs = self.attach_blackboard_client(
                name=f"{type(self).__name__}_{self.name}_inputs"
            )
            for key in self.INPUT_PORTS:
                self._inputs.register_key(key, Access.READ)

    def get_input(self, port: str) -> object | None:
        """Read input port *port*, checked against its declared type.

        An optional input port (``required=False``) with nothing on it reads
        as ``None``; a required one raises.  Only absence reads as ``None``:
        a wrong-typed value raises on either kind of port (BTND-03-021).

        Raises:
            KeyError: *port* is not a declared input port.
            NoDataAvailable: Nothing is on a required port.
            TypeError: The value is not of the port's ``data_type``.  It is
                a wiring error, so it fails the whole tree run, not the one
                node (BTND-03-021).
        """
        if port not in self.INPUT_PORTS or self._inputs is None:
            raise KeyError(
                f"{self.name}: {port!r} is not an input port of "
                f"{type(self).__name__}."
            )
        try:
            value: object = self._inputs.get(port)
        except KeyError:
            value = None
        info = self.INPUT_PORTS[port]
        if value is None:
            if not info.required:
                return None
            raise NoDataAvailable(
                f"{self.name}: input port {port!r} has no data available."
            )
        data_type = info.data_type
        if not is_of_port_type(value, data_type):
            raise TypeError(
                f"{self.name}: value on input port {port!r} is not of type "
                f"{data_type.__name__}, but {type(value).__name__} "
                "(BTND-03-021)."
            )
        return value


class EvaluatorCapability(Capability):
    """An Evaluator: records a decision (ADR-0097, BT-18-028).

    On *yes* it gives its recommendation for every declared output port; on
    *no* it gives the reason for its decision and any declared refusal
    ports (BT-18-007, ADR-0183).  An Evaluator whose decision is the verdict
    alone declares no outputs.
    """

    shape = CapabilityShape.EVALUATOR
    _is_shape_base = True


class RetrieverCapability(Capability):
    """A Retriever: returns facts from an outside source (ADR-0097).

    On *yes* it gives the facts it fetched for every declared output port.
    A binary Retriever, which answers a yes-or-no query, declares no outputs
    and its verdict is the result (BT-18-006, BT-18-010).

    A declaration says, in a ``Store-held answer (BT-18-039):`` line of its
    docstring, whether the case file or the actor's own store can hold the
    fact it fetches, and so whether a read-first guard must precede it.
    """

    shape = CapabilityShape.RETRIEVER
    _is_shape_base = True


class ComposerCapability(Capability):
    """A Composer: produces a content artifact (ADR-0097, BT-18-028).

    On *yes* it gives the artifact it generated for its declared output
    port.  The distinction from an Evaluator is what it produces: a Composer
    generates a new artifact (advisory, patch notes, exploit write-up), an
    Evaluator a recommendation.  So a Composer declares at least one output.
    """

    shape = CapabilityShape.COMPOSER
    _is_shape_base = True

    @classmethod
    def _check_shape(cls) -> None:
        if not cls.OUTPUT_PORTS:
            raise TypeError(
                f"Composer {cls.__name__} declares no output port; a "
                "Composer gives the artifact it produces (BT-18-028)."
            )


class ActuatorCapability(Capability, ActuatorBackend):
    """An Actuator: causes a side effect in an outside system (BT-18-028).

    It places no artifact on the blackboard, so it declares no output ports,
    and its ``contract`` is an
    :class:`~vultron.core.behaviors.call_out.actuator.ActuatorContract`.  As
    an :class:`~vultron.core.behaviors.call_out.actuator.ActuatorBackend` it
    acts on the one target its tree binds and takes an idempotency id per
    call (BT-18-041, BT-18-043).  *Yes* means the side effect is confirmed;
    *no* means the backend decided not to act; a side effect it cannot
    confirm is *error* (ADR-0183).
    """

    shape = CapabilityShape.ACTUATOR
    _is_shape_base = True
    _contract_type = ActuatorContract


__all__ = [
    "ActuatorCapability",
    "Capability",
    "CapabilityShape",
    "ComposerCapability",
    "EvaluatorCapability",
    "PORT_ATTRIBUTES",
    "RetrieverCapability",
]
