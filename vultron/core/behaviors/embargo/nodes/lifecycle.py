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

from typing import Any, cast

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.protocols import is_case_model
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    EmbargoLifecycleResult,
    TransitionMode,
)
from vultron.core.states.em import (
    EM,
    EMAdapter,
    create_em_machine,
    is_valid_em_transition,
)
from vultron.core.use_cases._helpers import (
    _as_id,
    _resolve_case_manager_id,
    reset_case_participant_embargo_consent,
)
from vultron.core.use_cases.triggers._helpers import add_activity_to_outbox
from vultron.errors import (
    VultronError,
    VultronInvalidStateTransitionError,
    VultronValidationError,
)
from transitions import MachineError


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


class TerminateEmbargoNode(DataLayerAction):
    """Trigger-side embargo teardown for a given case.

    Applies the ACTIVE/REVISE → EXITED EM state transition via the state
    machine, clears ``active_embargo``, resets all participant embargo
    consent states, and queues a ``Terminate(EmbargoEvent)`` activity when a
    ``trigger_activity_factory`` is available.

    Always returns SUCCESS.  Failures (no active embargo, invalid EM
    transition, activity dispatch errors) are logged as WARNING and are
    treated as non-fatal.
    """

    def __init__(self, case_id: str | None, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def update(self) -> Status:
        if self.datalayer is None or not self.case_id:
            return Status.SUCCESS

        case = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            return Status.SUCCESS

        if case.active_embargo is None:
            self.logger.info(
                "%s: no active embargo on case '%s' — skipping",
                self.name,
                self.case_id,
            )
            return Status.SUCCESS

        em_state = case.current_status.em_state
        adapter = EMAdapter(em_state)
        em_machine = create_em_machine()
        em_machine.add_model(adapter, initial=em_state)

        try:
            getattr(adapter, "terminate")()
        except MachineError:
            self.logger.warning(
                "%s: EM %s → EXITED blocked for case '%s'",
                self.name,
                em_state,
                self.case_id,
            )
            return Status.SUCCESS

        embargo_id = (
            case.active_embargo
            if isinstance(case.active_embargo, str)
            else getattr(case.active_embargo, "id_", None)
        )
        case_manager_id = _resolve_case_manager_id(
            cast(Any, case), self.datalayer
        )

        case.current_status.em_state = EM(adapter.state)
        case.active_embargo = None
        reset_case_participant_embargo_consent(self.datalayer, case)
        self.datalayer.save(case)

        self.logger.info(
            "%s: embargo terminated on case '%s' (EM %s → %s)",
            self.name,
            self.case_id,
            em_state,
            adapter.state,
        )

        self._dispatch_activity(embargo_id, case_manager_id)
        return Status.SUCCESS

    def _dispatch_activity(
        self, embargo_id: str | None, case_manager_id: str | None
    ) -> None:
        """Queue a Terminate(EmbargoEvent) activity to the case manager's outbox.

        No-ops when ``trigger_activity_factory`` is unavailable, ``embargo_id``
        is missing, or the case manager cannot be resolved.  Activity dispatch
        failures are logged as WARNING and do not affect the BT return value.
        """
        if (
            self.trigger_activity_factory is None
            or embargo_id is None
            or self.datalayer is None
        ):
            return

        if case_manager_id is None:
            self.logger.warning(
                "%s: no CASE_MANAGER found for case '%s'"
                " — activity dispatch skipped",
                self.name,
                self.case_id,
            )
            return

        try:
            case_id: str = self.case_id  # type: ignore[assignment]  # guarded above
            announce_id, _ = self.trigger_activity_factory.terminate_embargo(
                embargo_id=embargo_id,
                case_id=case_id,
                actor=case_manager_id,
                to=[case_manager_id],
            )
            add_activity_to_outbox(
                case_manager_id,
                announce_id,
                cast(CaseOutboxPersistence, self.datalayer),
            )
        except Exception as exc:
            self.logger.warning(
                "%s: activity dispatch failed for case '%s': %s",
                self.name,
                self.case_id,
                exc,
            )


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

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE

        case = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            self.feedback_message = f"Case '{self.case_id}' not found"
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        current_embargo_id = _as_id(case.active_embargo)
        if current_embargo_id == self.embargo_id:
            self.feedback_message = (
                f"Case '{self.case_id}' already has embargo"
                f" '{self.embargo_id}' active — idempotent no-op"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

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
        self.datalayer.save(case)

        self.feedback_message = (
            f"Activated embargo '{self.embargo_id}' on case"
            f" '{self.case_id}' (EM {current_em} → ACTIVE)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS
