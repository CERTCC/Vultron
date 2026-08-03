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

"""Shared base class for embargo activity emit nodes (BTND-07-005)."""

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.use_cases._helpers import add_activity_to_outbox


class _SendEmbargoActivityBase(DataLayerAction):
    """Abstract base for embargo activity emit nodes (BTND-07-005).

    Implements the common guard/factory-dispatch/outbox-write skeleton:

    1. Check factory availability → delegate to ``_on_factory_unavailable()``.
    2. Guard ``datalayer`` and ``actor_id`` via ``_require_datalayer_and_actor()``.
    3. Resolve ``embargo_id`` and ``case_manager_id`` → ``_resolve_embargo_and_manager()``.
    4. Call the factory → ``_call_factory(actor_id, embargo_id, case_manager_id)``.
    5. Write the activity to the outbox; on failure → ``_on_outbox_write_failure()``.

    Subclasses must override all four hook methods.  Subclasses that read from
    the blackboard must also override ``setup()`` to register their keys (calling
    ``super().setup(**kwargs)`` first).
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id

    def _on_factory_unavailable(self) -> Status:
        """Status to return when ``trigger_activity_factory`` is ``None``.

        Implementations must set ``self.feedback_message``, log an appropriate
        message, and return either ``SUCCESS`` (best-effort/skip) or ``FAILURE``
        (fail-fast, per BT-14-001).
        """
        raise NotImplementedError

    def _resolve_embargo_and_manager(self) -> "tuple[str, str] | Status":
        """Resolve the embargo ID and Case Manager actor ID for the factory call.

        Called after ``datalayer`` and ``actor_id`` have been validated.
        Returns ``(embargo_id, case_manager_id)`` on success, or a ``Status``
        value to return early (e.g. ``FAILURE`` on hard error, ``SUCCESS`` on
        graceful skip).
        """
        raise NotImplementedError

    def _call_factory(
        self, _actor_id: str, _embargo_id: str, _case_manager_id: str
    ) -> "tuple[str, object]":
        """Invoke the appropriate ``TriggerActivityPort`` method.

        Returns ``(activity_id, <extra>)``; raises on any factory error.
        """
        raise NotImplementedError

    def _on_outbox_write_failure(
        self, _activity_id: str, _exc: Exception
    ) -> Status:
        """Status to return when the outbox write fails after activity creation.

        The activity has already been constructed at this point.  Return
        ``SUCCESS`` for best-effort semantics (teardown must not be blocked) or
        ``FAILURE`` for fail-fast semantics (BT-14-001).
        """
        raise NotImplementedError

    def update(self) -> Status:
        if self.trigger_activity_factory is None:
            return self._on_factory_unavailable()

        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        params = self._resolve_embargo_and_manager()
        if isinstance(params, Status):
            return params
        embargo_id, case_manager_id = params

        try:
            activity_id, _extra = self._call_factory(
                self.actor_id, embargo_id, case_manager_id
            )
        except Exception as exc:
            self.feedback_message = (
                f"Factory call failed for case '{self._case_id}': {exc}"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        try:
            add_activity_to_outbox(
                self.actor_id,
                activity_id,
                self.datalayer,  # type: ignore[arg-type]
            )
        except Exception as exc:
            return self._on_outbox_write_failure(activity_id, exc)

        self.feedback_message = (
            f"Queued '{activity_id}' for case '{self._case_id}'"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS
