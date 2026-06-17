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

"""Abstract base classes for BT-backed trigger use cases.

Two-level hierarchy:

- :class:`SvcBTTriggerBase` — top-level template method that owns the
  ``__init__``, the TriggerActivityPort guard, BTBridge construction, BT
  execution, and the failure guard.  Subclasses implement ``_prepare()``,
  ``_build_tree()``, and ``_handle_result()``.

- :class:`SvcEmbargoTriggerBase` — extends ``SvcBTTriggerBase`` with a
  concrete ``_handle_result()`` that validates and stores the
  ``lifecycle_result`` from the BT output, then delegates to the
  per-operation ``_log_lifecycle_result()`` hook.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

import py_trees.behaviour
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.services.embargo_lifecycle import EmbargoLifecycleResult
from vultron.errors import VultronValidationError

logger = logging.getLogger(__name__)


class SvcBTTriggerBase(ABC):
    """Abstract base for all BT-backed trigger use cases.

    The :meth:`execute` template method orchestrates the common workflow:

    1. Initialise transient state (``_captured``, ``_result_out``,
       ``_actor_id``).
    2. Call :meth:`_prepare` (abstract) — subclass resolves domain objects and
       sets ``self._actor_id``.
    3. Validate that a ``TriggerActivityPort`` was supplied and store it as
       ``self._factory``.
    4. Construct a :class:`~vultron.core.behaviors.bridge.BTBridge`.
    5. Call :meth:`_build_tree` (abstract) — subclass returns the BT.
    6. Execute the BT via ``bridge.execute_with_setup``.
    7. Raise on failure.
    8. Call :meth:`_handle_result` (abstract) — subclass logs/extracts output.
    9. Return ``{"activity": self._captured.get("activity")}``.
    """

    _requires_trigger_activity: bool = True

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: object,
        trigger_activity: TriggerActivityPort | None = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._trigger_activity = trigger_activity

    def execute(self) -> dict:
        """Template method: prepare → gate → run BT → handle result."""
        self._captured: dict = {}
        self._result_out: dict[str, object] = {}
        self._actor_id: str = ""

        self._prepare()

        if self._requires_trigger_activity and self._trigger_activity is None:
            raise RuntimeError(
                f"{type(self).__name__} requires a TriggerActivityPort"
            )
        if self._trigger_activity is not None:
            self._factory: TriggerActivityPort = self._trigger_activity

        bridge = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
        )
        tree = self._build_tree()
        result = bridge.execute_with_setup(
            tree,
            actor_id=self._actor_id,
            **self._extra_execute_kwargs(),
        )

        if result.status != Status.SUCCESS:
            error = self._result_out.get("error")
            if isinstance(error, Exception):
                raise error
            raise VultronValidationError(
                f"{type(self).__name__} failed:"
                f" {BTBridge.get_failure_reason(tree)}"
            )

        self._handle_result()

        return {"activity": self._captured.get("activity")}

    @abstractmethod
    def _prepare(self) -> None:
        """Pre-BT validation and setup.

        Implementations MUST set ``self._actor_id`` to the resolved full actor
        URI and may set additional operation-specific attributes (e.g.
        ``self._case``, ``self._embargo``).  Raise domain exceptions on invalid
        input.
        """

    @abstractmethod
    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        """Construct and return the operation-specific BT.

        Called after ``_prepare()`` and after ``self._factory`` is set.
        Implementations may close over ``self._captured`` and
        ``self._result_out`` for BT I/O.
        """

    @abstractmethod
    def _handle_result(self) -> None:
        """Post-BT logging or result extraction.

        Called only when the BT succeeded.
        """

    def _extra_execute_kwargs(self) -> dict[str, Any]:
        """Additional kwargs passed to ``bridge.execute_with_setup``.

        Override to inject extra blackboard context required by specific BT
        trees (e.g. ``{"case_id": self._case_id}`` for trees whose nodes
        read ``case_id`` from the blackboard).
        """
        return {}


class SvcEmbargoTriggerBase(SvcBTTriggerBase):
    """Abstract base for embargo trigger use cases.

    Provides a concrete :meth:`_handle_result` that:

    1. Extracts ``lifecycle_result`` from ``self._result_out``.
    2. Raises ``RuntimeError`` if the value is absent or the wrong type.
    3. Stores the validated result as ``self._lifecycle_result``.
    4. Delegates to the per-operation :meth:`_log_lifecycle_result` hook.
    """

    def _handle_result(self) -> None:
        lifecycle_result = self._result_out.get("lifecycle_result")
        if not isinstance(lifecycle_result, EmbargoLifecycleResult):
            raise RuntimeError(
                f"{type(self).__name__} did not capture lifecycle result"
                " in BT output"
            )
        self._lifecycle_result: EmbargoLifecycleResult = lifecycle_result
        self._log_lifecycle_result()

    @abstractmethod
    def _log_lifecycle_result(self) -> None:
        """Log the per-operation lifecycle result after BT execution."""
