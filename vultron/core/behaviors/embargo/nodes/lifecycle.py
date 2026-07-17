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

"""Embargo state machine and lifecycle transition nodes."""

from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.protocols import is_case_model
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    EmbargoLifecycleResult,
    TransitionMode,
)
from vultron.core.states.em import (
    EM,
    is_em_embargo_active,
    is_valid_em_transition,
)
from vultron.core.use_cases._helpers import _as_id
from vultron.core.use_cases._helpers import add_activity_to_outbox
from vultron.errors import (
    VultronError,
    VultronInvalidStateTransitionError,
    VultronValidationError,
)


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

        try:
            em_state = case.current_status.em_state
        except ValueError:
            em_state = None
        if em_state is None or not is_em_embargo_active(em_state):
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


class ReadEmbargoIdNode(DataLayerAction):
    """Read the active embargo ID from the case and write it to the blackboard.

    Returns FAILURE when the case is not found, has no active embargo, or
    the DataLayer is unavailable.  Returns SUCCESS and writes ``embargo_id``
    to the blackboard on success.
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id

    def setup(self, **kwargs: object) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="embargo_id",
            access=py_trees.common.Access.WRITE,
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE

        case = self.datalayer.read(self._case_id)
        if not is_case_model(case):
            self.feedback_message = f"Case '{self._case_id}' not found"
            return Status.FAILURE

        embargo_id = _as_id(case.active_embargo)
        if embargo_id is None:
            self.feedback_message = (
                f"No active embargo on case '{self._case_id}'"
            )
            return Status.FAILURE

        self.blackboard.embargo_id = embargo_id
        return Status.SUCCESS


class SendTerminateEmbargoActivityNode(DataLayerAction):
    """Build and queue a ``Terminate(EmbargoEvent)`` activity.

    Reads ``embargo_id`` and ``case_manager_id`` from the blackboard and
    constructs the outbound activity via ``trigger_activity_factory``.

    Returns FAILURE (BT-14-001) when the factory is unavailable, a required
    blackboard key is missing, or dispatch raises an exception.
    Returns SUCCESS when the activity is created and queued.
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id

    def setup(self, **kwargs: object) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="embargo_id",
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key="case_manager_id",
            access=py_trees.common.Access.READ,
        )

    def update(self) -> Status:
        if self.trigger_activity_factory is None:
            self.feedback_message = (
                "trigger_activity_factory not available"
                " — broadcast FAILURE (BT-14-001)"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        if self.datalayer is None or self.actor_id is None:
            self.feedback_message = "DataLayer or actor_id not available"
            return Status.FAILURE

        try:
            embargo_id: str = self.blackboard.embargo_id
            case_manager_id: str = self.blackboard.case_manager_id
        except KeyError as exc:
            self.feedback_message = f"Required blackboard key missing: {exc}"
            return Status.FAILURE

        try:
            announce_id, _ = self.trigger_activity_factory.terminate_embargo(
                embargo_id=embargo_id,
                case_id=self._case_id,
                actor=self.actor_id,
                to=[case_manager_id],
            )
            add_activity_to_outbox(
                self.actor_id,
                announce_id,
                self.datalayer,  # type: ignore[arg-type]
            )
        except Exception as exc:
            self.feedback_message = (
                f"activity dispatch failed for case '{self._case_id}': {exc}"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        return Status.SUCCESS


class SetEmbargoActiveNode(DataLayerAction):
    """Set embargo active on case and transition EM → ACTIVE.

    Handles idempotency and state-sync override for non-standard EM
    transitions (e.g. receive-side state-sync when sender has already
    activated).
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.embargo_id = embargo_id

    def _read_case(self) -> Any | None:
        assert self.datalayer is not None
        case = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            self.feedback_message = f"Case '{self.case_id}' not found"
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return None
        return case

    def _apply_transition(self, case: Any) -> None:
        """Apply EM → ACTIVE transition and persist; warn on non-standard path."""
        current_em = case.current_status.em_state
        if not is_valid_em_transition(current_em, EM.ACTIVE):
            self.logger.warning(
                "%s: EM transition %s → ACTIVE is not a standard machine"
                " transition for case '%s'; applying state-sync override",
                self.name,
                current_em,
                self.case_id,
            )
        case.set_embargo(self.embargo_id)
        case.current_status.em_state = EM.ACTIVE
        assert self.datalayer is not None
        self.datalayer.save(case)
        self.feedback_message = (
            f"Activated embargo '{self.embargo_id}' on case"
            f" '{self.case_id}' (EM {current_em} → ACTIVE)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)

    def update(self) -> Status:
        fail = self._require_datalayer()
        if fail is not None:
            return fail

        case = self._read_case()
        if case is None:
            return Status.FAILURE

        current_embargo_id = _as_id(case.active_embargo)
        if current_embargo_id == self.embargo_id:
            self.feedback_message = (
                f"Case '{self.case_id}' already has embargo"
                f" '{self.embargo_id}' active — idempotent no-op"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

        self._apply_transition(case)
        return Status.SUCCESS
