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

"""Blackboard-client base classes for DataLayer-aware BT nodes.

Per specs/behavior-tree-integration.yaml:
- BT-07-001: BT nodes interact with DataLayer via Protocol interface
- BT-07-002: BT nodes use type-safe DataLayer wrappers
- BT-07-003: State transitions logged via DataLayer integration helpers
"""

import logging
from typing import TYPE_CHECKING, Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.node_logger import node_logger
from vultron.core.models.case import VulnerabilityCase
from vultron.core.ports.case_persistence import CasePersistence

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
)


class DataLayerCondition(py_trees.behaviour.Behaviour):
    """
    Base class for BT condition nodes that check state from DataLayer.

    Condition nodes check preconditions or state without side effects.
    Returns SUCCESS if condition holds, FAILURE otherwise.

    Subclasses should override update() to implement condition logic.
    """

    # Declare the managed logger type so subclass log calls are type-checked
    # against the stdlib logging.Logger API (not py_trees.logging.Logger).
    logger: logging.Logger  # type: ignore[assignment]

    def __init__(self, name: str):
        """
        Initialize condition node.

        Args:
            name: Descriptive name for this condition node
        """
        super().__init__(name=name)
        # py_trees creates self.logger = logging.Logger(name) with parent=None,
        # so messages are silently dropped.  Replace with a proper managed logger
        # so BT node log messages propagate through the standard logging hierarchy.
        self.logger = node_logger(self)  # type: ignore[assignment]
        self.datalayer: CasePersistence | None = None
        self.actor_id: str | None = None
        self.wire_render_port: WireRenderPort | None = None

    def setup(self, **kwargs: Any) -> None:
        """Set up blackboard access for DataLayer and actor_id."""
        self.blackboard = self.attach_blackboard_client(name=self.name)
        self.blackboard.register_key(
            key="datalayer", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="actor_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="wire_render_port",
            access=py_trees.common.Access.READ,
        )

    def initialise(self) -> None:
        """Initialize condition node by reading blackboard state."""
        self.datalayer = self.blackboard.datalayer
        self.actor_id = self.blackboard.actor_id

        try:
            self.wire_render_port = self.blackboard.wire_render_port
        except KeyError:
            # Optional key: registered in setup() but may carry no value on
            # this tick.  py_trees raises KeyError for a registered-but-unset
            # blackboard key; anything else is a real fault (CS-23-001).
            self.wire_render_port = None

        if self.datalayer is None:
            self.logger.error(
                "%s: DataLayer not found in blackboard", self.name
            )
        if self.actor_id is None:
            self.logger.error(
                "%s: actor_id not found in blackboard", self.name
            )

    def _require_datalayer(self) -> Status | None:
        """Return FAILURE if ``self.datalayer`` is not set, else None."""
        if self.datalayer is None:
            self.feedback_message = DATALAYER_UNAVAILABLE
            return Status.FAILURE
        return None

    def _require_datalayer_and_actor(self) -> Status | None:
        """Return FAILURE if ``datalayer`` or ``actor_id`` is not set, else None."""
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
        """
        Evaluate condition. Override in subclasses.

        Returns:
            SUCCESS if condition holds, FAILURE otherwise
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.update() must be implemented by subclass"
        )


class DataLayerAction(py_trees.behaviour.Behaviour):
    """
    Base class for BT action nodes that modify state in DataLayer.

    Action nodes perform state transitions with side effects.
    Returns SUCCESS if action completes, FAILURE if action fails.

    Subclasses should override update() to implement action logic.
    """

    # Declare the managed logger type so subclass log calls are type-checked
    # against the stdlib logging.Logger API (not py_trees.logging.Logger).
    logger: logging.Logger  # type: ignore[assignment]

    def __init__(self, name: str):
        """
        Initialize action node.

        Args:
            name: Descriptive name for this action node
        """
        super().__init__(name=name)
        # py_trees creates self.logger = logging.Logger(name) with parent=None,
        # so messages are silently dropped.  Replace with a proper managed logger
        # so BT node log messages propagate through the standard logging hierarchy.
        self.logger = node_logger(self)  # type: ignore[assignment]
        self.datalayer: CasePersistence | None = None
        self.actor_id: str | None = None
        self.trigger_activity_factory: TriggerActivityPort | None = None
        self.wire_render_port: WireRenderPort | None = None

    def setup(self, **kwargs: Any) -> None:
        """Set up blackboard access for DataLayer, actor_id, and trigger_activity_factory."""
        self.blackboard = self.attach_blackboard_client(name=self.name)
        self.blackboard.register_key(
            key="datalayer", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="actor_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="trigger_activity_factory",
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key="wire_render_port",
            access=py_trees.common.Access.READ,
        )

    def initialise(self) -> None:
        """Initialize action node by reading blackboard state."""
        self.datalayer = self.blackboard.datalayer
        self.actor_id = self.blackboard.actor_id

        try:
            self.trigger_activity_factory = (
                self.blackboard.trigger_activity_factory
            )
        except KeyError:
            # Optional key: registered in setup() but may carry no value on
            # this tick (KeyError from py_trees); anything else is a real
            # fault (CS-23-001).
            self.trigger_activity_factory = None

        try:
            self.wire_render_port = self.blackboard.wire_render_port
        except KeyError:
            self.wire_render_port = None

        if self.datalayer is None:
            self.logger.error(
                "%s: DataLayer not found in blackboard", self.name
            )
        if self.actor_id is None:
            self.logger.error(
                "%s: actor_id not found in blackboard", self.name
            )

    def _require_datalayer(self) -> Status | None:
        """Return FAILURE if ``self.datalayer`` is not set, else None."""
        if self.datalayer is None:
            self.feedback_message = DATALAYER_UNAVAILABLE
            return Status.FAILURE
        return None

    def _require_datalayer_and_actor(self) -> Status | None:
        """Return FAILURE if ``datalayer`` or ``actor_id`` is not set, else None."""
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

    def _require_factory(self) -> Status | None:
        """Return FAILURE if ``trigger_activity_factory`` is not set, else None."""
        if self.trigger_activity_factory is None:
            self.feedback_message = TRIGGER_FACTORY_UNAVAILABLE
            return Status.FAILURE
        return None

    def update(self) -> Status:
        """
        Perform action. Override in subclasses.

        Returns:
            SUCCESS if action completes, FAILURE if action fails
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.update() must be implemented by subclass"
        )
