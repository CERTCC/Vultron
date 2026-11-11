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

"""Typed-Ports base classes for DataLayer-aware BT nodes.

Per specs/behavior-tree-node-design.yaml BTND-03-009 through BTND-03-011:
- BTND-03-009: Typed-Ports nodes declare blackboard contracts via the
  INPUT_PORTS / OUTPUT_PORTS class attributes rather than imperative
  register_key() calls.
- BTND-03-010: Typed-Ports nodes call setup_ports() in setup() with remappings
  {"datalayer": "/datalayer", "actor_id": "/actor_id"} to wire the BTBridge
  flat keys.
- BTND-03-011: Typed-Ports nodes read injected values via get_input() in
  initialise() rather than direct blackboard attribute access.
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from py_trees.common import Status
from py_trees.ports import BehaviourWithPorts, NoDataAvailable, PortInformation

from vultron.core.behaviors.bridge.act_instant import ACT_INSTANT_KEY
from vultron.core.behaviors.node_logger import node_logger, port_wiring_logger
from vultron.core.models.case import VulnerabilityCase
from vultron.core.ports.case_persistence import CasePersistence
from vultron.errors import VultronMissingActInstantError, VultronWiringError

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.helpers.case_resolution import (
    require_case,
    resolve_case_replica,
)
from vultron.core.behaviors.helpers.messages import (
    DATALAYER_OR_ACTOR_UNAVAILABLE,
    DATALAYER_UNAVAILABLE,
    TRIGGER_FACTORY_UNAVAILABLE,
    WIRE_RENDER_PORT_UNAVAILABLE,
)

# BTBridge writes datalayer and actor_id as flat root-level blackboard keys.
# Ports nodes remap their port names to these absolute paths so that
# get_input("datalayer") reads the same value that was written by
# BTBridge.setup_tree().
_DL_KEY = "/datalayer"
_ACTOR_KEY = "/actor_id"
# The act's instant, placed by the act's outermost run (ADR-0176).
_AT_KEY = f"/{ACT_INSTANT_KEY}"


class _ActInstantPort:
    """The ``at`` input port both ports bases declare (ADR-0176).

    A node that needs the time calls :meth:`_require_act_instant` when it
    ticks.  The port is optional in the declaration because most nodes never
    read it; reading it in a run that carries no instant raises.
    """

    def _require_act_instant(self) -> datetime:
        """Return the act's instant from the tree run, or raise.

        Called in ``update()``, never at build or in ``__init__``: a time read
        then would be read before the act took the tree lock.

        Raises:
            VultronMissingActInstantError: The run carries no ``/at``.  A
                composition fault, which ``BTBridge`` reports as an internal
                error; it is never answered by reading the clock
                (ARCH-10-001).
        """
        node = cast(BehaviourWithPorts, self)
        try:
            at = node.get_input(ACT_INSTANT_KEY)
        except (NoDataAvailable, NotImplementedError):
            at = None
        if not isinstance(at, datetime):
            raise VultronMissingActInstantError(
                f"{node.name}: this tree run carries no act instant"
                f" ({_AT_KEY}); start it inside an act (ADR-0176)"
            )
        return at


class _OptionalPortRead:
    """The optional-port read both ports bases share (BTND-03-021)."""

    def _try_get_input(self, key: str) -> object | None:
        """Return the value on port ``key``, or ``None`` when it is absent.

        Only absence becomes ``None``: an unset key (``NoDataAvailable``) or a
        key holding ``None`` (``NotImplementedError``).  A value of the wrong
        ``data_type`` raises ``TypeError`` out of the tick, and ``BTBridge``
        fails the whole tree run.  Catching it here would let the junk read as
        "not supplied" (BTND-03-021, ARCH-15).
        """
        node = cast(BehaviourWithPorts, self)
        try:
            return cast(object, node.get_input(key))
        except (NoDataAvailable, NotImplementedError):
            return None


class DataLayerConditionWithPorts(
    _OptionalPortRead, _ActInstantPort, BehaviourWithPorts
):
    """Base class for typed-Ports BT condition nodes with DataLayer access.

    Declares ``datalayer`` and ``actor_id`` as required input ports, remapped
    to the flat BTBridge blackboard keys ``/datalayer`` and ``/actor_id``.
    Subclasses extend ``INPUT_PORTS`` / ``OUTPUT_PORTS`` (e.g.
    ``{**DataLayerConditionWithPorts.INPUT_PORTS, ...}``) and implement
    ``update()``.  They read injected values via ``get_input()`` in
    ``initialise()``.

    Per BTND-03-009: typed port declarations replace imperative register_key().
    Per BTND-03-010: setup_ports() with remappings wires BTBridge flat keys.
    Per BTND-03-011: get_input() replaces direct blackboard attribute access.
    """

    logger: logging.Logger  # type: ignore[assignment]

    def __init__(self, name: str):
        super().__init__(name=name)
        self.logger = node_logger(self)
        self.datalayer: CasePersistence | None = None
        self.actor_id: str | None = None

    INPUT_PORTS: dict[str, PortInformation] = {
        "datalayer": PortInformation(data_type=object, required=True),
        "actor_id": PortInformation(data_type=str, required=True),
        ACT_INSTANT_KEY: PortInformation(data_type=object, required=False),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {}

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        """Subclasses override to map domain input-port names to absolute blackboard paths.

        Merged into the ``port_remappings`` dict passed to ``setup_ports()`` so
        that domain keys declared in ``INPUT_PORTS`` resolve to the same global
        paths written by preceding ``DataLayerAction`` writer nodes.
        """
        return {}

    def _instance_port_remappings(self) -> dict[str, str]:
        """Override for instance-state-dependent port paths (dynamic keys)."""
        return {}

    def setup(self, **kwargs: Any) -> None:
        self.setup_ports(
            port_remappings={
                "datalayer": _DL_KEY,
                "actor_id": _ACTOR_KEY,
                ACT_INSTANT_KEY: _AT_KEY,
                **self._domain_port_remappings(),
                **self._instance_port_remappings(),
            },
            logger=port_wiring_logger(),
        )

    def initialise(self) -> None:
        try:
            self.datalayer = self.get_input("datalayer")
        except NotImplementedError:
            self.datalayer = None
        try:
            self.actor_id = self.get_input("actor_id")
        except NotImplementedError:
            self.actor_id = None

    def _require_datalayer(self) -> Status | None:
        if self.datalayer is None:
            self.feedback_message = DATALAYER_UNAVAILABLE
            return Status.FAILURE
        return None

    def _require_datalayer_and_actor(self) -> Status | None:
        if self.datalayer is None or self.actor_id is None:
            self.feedback_message = DATALAYER_OR_ACTOR_UNAVAILABLE
            return Status.FAILURE
        return None

    def _require_case(
        self, case_id: "str | None"
    ) -> "tuple[VulnerabilityCase, Status | None]":
        """Resolve a case that must exist (Regime 1); see :func:`require_case`."""
        return require_case(self, case_id)

    def _resolve_case_replica(
        self, case_id: "str | None"
    ) -> "VulnerabilityCase | None":
        """Resolve a replica case (Regime 2); see :func:`resolve_case_replica`."""
        return resolve_case_replica(self, case_id)

    def update(self) -> Status:
        raise NotImplementedError(
            f"{self.__class__.__name__}.update() must be implemented"
        )


class DataLayerActionWithPorts(
    _OptionalPortRead, _ActInstantPort, BehaviourWithPorts
):
    """Base class for typed-Ports BT action nodes with DataLayer access.

    Declares ``datalayer``, ``actor_id``, and optionally
    ``trigger_activity_factory`` and ``wire_render_port`` as input ports,
    remapped to BTBridge flat keys.  Subclasses extend ``INPUT_PORTS`` / ``OUTPUT_PORTS`` (e.g.
    ``{**DataLayerActionWithPorts.INPUT_PORTS, ...}``) and implement
    ``update()``.

    Per BTND-03-009 through BTND-03-011.
    """

    logger: logging.Logger  # type: ignore[assignment]

    def __init__(self, name: str):
        super().__init__(name=name)
        self.logger = node_logger(self)
        self.datalayer: CasePersistence | None = None
        self.actor_id: str | None = None
        self.trigger_activity_factory: TriggerActivityPort | None = None
        self.wire_render_port: WireRenderPort | None = None

    INPUT_PORTS: dict[str, PortInformation] = {
        "datalayer": PortInformation(data_type=object, required=True),
        "actor_id": PortInformation(data_type=str, required=True),
        "trigger_activity_factory": PortInformation(
            data_type=object, required=False
        ),
        "wire_render_port": PortInformation(data_type=object, required=False),
        ACT_INSTANT_KEY: PortInformation(data_type=object, required=False),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {}

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        """Subclasses override to map domain input-port names to absolute blackboard paths.

        Merged into the ``port_remappings`` dict passed to ``setup_ports()`` so
        that domain keys declared in ``INPUT_PORTS`` resolve to the same global
        paths written by preceding ``DataLayerAction`` writer nodes.
        """
        return {}

    def _instance_port_remappings(self) -> dict[str, str]:
        """Override for instance-state-dependent port paths (dynamic keys)."""
        return {}

    def setup(self, **kwargs: Any) -> None:
        self.setup_ports(
            port_remappings={
                "datalayer": _DL_KEY,
                "actor_id": _ACTOR_KEY,
                "trigger_activity_factory": "/trigger_activity_factory",
                "wire_render_port": "/wire_render_port",
                ACT_INSTANT_KEY: _AT_KEY,
                **self._domain_port_remappings(),
                **self._instance_port_remappings(),
            },
            logger=port_wiring_logger(),
        )

    def initialise(self) -> None:
        try:
            self.datalayer = self.get_input("datalayer")
        except NotImplementedError:
            self.datalayer = None
        try:
            self.actor_id = self.get_input("actor_id")
        except NotImplementedError:
            self.actor_id = None
        try:
            self.trigger_activity_factory = self.get_input(
                "trigger_activity_factory"
            )
        except (NoDataAvailable, NotImplementedError):
            self.trigger_activity_factory = None
        try:
            self.wire_render_port = self.get_input("wire_render_port")
        except (NoDataAvailable, NotImplementedError):
            self.wire_render_port = None

    def _require_datalayer(self) -> Status | None:
        if self.datalayer is None:
            self.feedback_message = DATALAYER_UNAVAILABLE
            return Status.FAILURE
        return None

    def _require_datalayer_and_actor(self) -> Status | None:
        if self.datalayer is None or self.actor_id is None:
            self.feedback_message = DATALAYER_OR_ACTOR_UNAVAILABLE
            return Status.FAILURE
        return None

    def _require_wire_render_port(self) -> "WireRenderPort":
        """Return the rendering port, or raise if the tree was built without it.

        Core never produces the AS2 shape of an object itself (ARCH-20-001), so
        a node that needs it has no fallback: a missing port is a composition
        fault, never the sender's doing.  Raises
        :class:`~vultron.errors.VultronWiringError`, which ``BTBridge`` reports
        as an internal error and a received handler re-raises rather than
        refusing the sender (#2255, ADR-0095).
        """
        if self.wire_render_port is None:
            raise VultronWiringError(WIRE_RENDER_PORT_UNAVAILABLE)
        return self.wire_render_port

    def _require_trigger_activity_port(self) -> "TriggerActivityPort":
        """Return the trigger-activity port, or raise if the tree lacks it.

        For a node that records the CASE_MANAGER's own act: its ledger entry
        is the factory-built activity's sealed blob (VM-08-003), so without
        the port there is nothing to commit and no fallback.  A missing port
        is a composition fault, never the sender's doing, so it raises
        :class:`~vultron.errors.VultronWiringError` rather than returning a
        FAILURE an enclosing Selector could read as a guard that did not
        pass (ARCH-15-001).
        """
        if self.trigger_activity_factory is None:
            raise VultronWiringError(
                f"{self.name}: {TRIGGER_FACTORY_UNAVAILABLE}"
            )
        return self.trigger_activity_factory

    def _require_case(
        self, case_id: "str | None"
    ) -> "tuple[VulnerabilityCase, Status | None]":
        """Resolve a case that must exist (Regime 1); see :func:`require_case`."""
        return require_case(self, case_id)

    def _resolve_case_replica(
        self, case_id: "str | None"
    ) -> "VulnerabilityCase | None":
        """Resolve a replica case (Regime 2); see :func:`resolve_case_replica`."""
        return resolve_case_replica(self, case_id)

    def _require_factory(self) -> Status | None:
        if self.trigger_activity_factory is None:
            self.feedback_message = TRIGGER_FACTORY_UNAVAILABLE
            return Status.FAILURE
        return None

    def update(self) -> Status:
        raise NotImplementedError(
            f"{self.__class__.__name__}.update() must be implemented"
        )
