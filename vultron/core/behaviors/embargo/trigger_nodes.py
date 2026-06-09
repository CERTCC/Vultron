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

"""Trigger-side embargo lifecycle action nodes."""

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    EmbargoLifecycleResult,
    TransitionMode,
)
from vultron.errors import VultronError


class PersistEmbargoEventNode(DataLayerAction):
    """Persist the trigger-created embargo event before outbound fan-out."""

    def __init__(self, embargo: EmbargoEvent, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._embargo = embargo

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE
        try:
            self.datalayer.create(self._embargo)
        except ValueError:
            self.logger.warning(
                "EmbargoEvent '%s' already exists", self._embargo.id_
            )
        return Status.SUCCESS


class _EmbargoLifecycleNode(DataLayerAction):
    """Base node for EmbargoLifecycle strict-mode transitions."""

    def __init__(
        self, result_out: dict[str, object], name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._result_out = result_out

    def _transition(
        self, lifecycle: EmbargoLifecycle, actor_id: str
    ) -> EmbargoLifecycleResult:
        raise NotImplementedError

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.feedback_message = "DataLayer or actor_id not available"
            return Status.FAILURE

        lifecycle = EmbargoLifecycle(persistence=self.datalayer)
        try:
            result = self._transition(lifecycle, self.actor_id)
        except VultronError as exc:
            self._result_out["error"] = exc
            self.feedback_message = str(exc)
            return Status.FAILURE

        self._result_out["lifecycle_result"] = result
        return Status.SUCCESS


class ProposeEmbargoLifecycleNode(_EmbargoLifecycleNode):
    """Apply STRICT propose/counter-propose transition."""

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        result_out: dict[str, object],
        name: str | None = None,
    ) -> None:
        super().__init__(result_out=result_out, name=name)
        self._case_id = case_id
        self._embargo_id = embargo_id

    def _transition(
        self, lifecycle: EmbargoLifecycle, actor_id: str
    ) -> EmbargoLifecycleResult:
        return lifecycle.propose_embargo(
            case_id=self._case_id,
            embargo_id=self._embargo_id,
            actor_id=actor_id,
            transition_mode=TransitionMode.STRICT,
        )


class AcceptEmbargoLifecycleNode(_EmbargoLifecycleNode):
    """Apply STRICT accept-invite transition."""

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        result_out: dict[str, object],
        name: str | None = None,
    ) -> None:
        super().__init__(result_out=result_out, name=name)
        self._case_id = case_id
        self._embargo_id = embargo_id

    def _transition(
        self, lifecycle: EmbargoLifecycle, actor_id: str
    ) -> EmbargoLifecycleResult:
        return lifecycle.accept_embargo_invite(
            case_id=self._case_id,
            embargo_id=self._embargo_id,
            actor_id=actor_id,
            transition_mode=TransitionMode.STRICT,
        )


class RejectEmbargoLifecycleNode(_EmbargoLifecycleNode):
    """Apply STRICT reject-invite transition."""

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        result_out: dict[str, object],
        name: str | None = None,
    ) -> None:
        super().__init__(result_out=result_out, name=name)
        self._case_id = case_id
        self._embargo_id = embargo_id

    def _transition(
        self, lifecycle: EmbargoLifecycle, actor_id: str
    ) -> EmbargoLifecycleResult:
        return lifecycle.reject_embargo_invite(
            case_id=self._case_id,
            embargo_id=self._embargo_id,
            actor_id=actor_id,
            transition_mode=TransitionMode.STRICT,
        )


class TerminateEmbargoLifecycleNode(_EmbargoLifecycleNode):
    """Apply STRICT terminate-active-embargo transition."""

    def __init__(
        self,
        case_id: str,
        result_out: dict[str, object],
        name: str | None = None,
    ) -> None:
        super().__init__(result_out=result_out, name=name)
        self._case_id = case_id

    def _transition(
        self, lifecycle: EmbargoLifecycle, actor_id: str
    ) -> EmbargoLifecycleResult:
        return lifecycle.terminate_active_embargo(
            case_id=self._case_id,
            actor_id=actor_id,
            transition_mode=TransitionMode.STRICT,
        )
