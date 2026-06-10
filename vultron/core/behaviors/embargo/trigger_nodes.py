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
from vultron.core.models.protocols import is_case_model
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    EmbargoLifecycleResult,
    TransitionMode,
)
from vultron.core.states.em import EM
from vultron.errors import (
    VultronError,
    VultronInvalidStateTransitionError,
    VultronValidationError,
)


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


class ValidateEmbargoRevisionStateNode(DataLayerAction):
    """Guard that the case EM state permits a revision proposal.

    Returns SUCCESS when EM state is ACTIVE or REVISE.  Returns FAILURE
    (with error in ``result_out``) for any other state — revision proposals
    require an active embargo; use propose-embargo for initial proposals.
    """

    def __init__(
        self,
        case_id: str,
        result_out: dict[str, object],
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._result_out = result_out

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE

        case = self.datalayer.read(self._case_id)
        if not is_case_model(case):
            not_found = VultronValidationError(
                f"Case '{self._case_id}' not found or invalid."
            )
            self._result_out["error"] = not_found
            self.feedback_message = str(not_found)
            return Status.FAILURE

        em_state = case.current_status.em_state
        if em_state not in (EM.ACTIVE, EM.REVISE):
            bad_state = VultronInvalidStateTransitionError(
                f"Cannot propose embargo revision: case '{self._case_id}'"
                f" EM state '{em_state}' does not allow a revision proposal."
                f" Use propose-embargo for initial proposals."
            )
            self._result_out["error"] = bad_state
            self.feedback_message = str(bad_state)
            return Status.FAILURE

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
