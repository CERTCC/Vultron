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

from py_trees.common import Status

from vultron.core.behaviors.embargo.nodes.em_state import ReadEmStateNode
from vultron.core.behaviors.embargo.nodes.reject_proposed import (  # noqa: F401
    ReadProposedEmbargoIdNode,
    RejectProposedEmbargoLifecycleNode,
    SendRejectEmbargoActivityNode,
)
from vultron.core.behaviors.embargo.nodes.terminate import (  # noqa: F401
    SendTerminateEmbargoActivityNode,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.narrative_log import log_em_transition
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    EmbargoLifecycleResult,
    TransitionMode,
)
from vultron.core.states.em import (
    EM,
    is_em_embargo_active,
)
from vultron.core.models._helpers import _as_id
from vultron.errors import (
    VultronError,
    VultronInvalidStateTransitionError,
    VultronNotFoundError,
)


class ValidateEmbargoRevisionStateNode(DataLayerActionWithPorts):
    """Guard that the case EM state permits a revision proposal.

    Returns SUCCESS when EM state is ACTIVE or REVISE.  Returns FAILURE
    (with error in ``result_out``) for any other state — revision proposals
    require an active embargo; use propose-embargo for initial proposals.

    Uses ``ReadEmStateNode`` to read the EM state (AC-1 of issue #1474) rather
    than reading ``case.current_status.em_state`` inline.
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
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        # AC-1: read em_state via named BT node, not inline.
        read_node = ReadEmStateNode(
            case_id=self._case_id, result_out=self._result_out
        )
        read_node.datalayer = self.datalayer
        read_status = read_node.update()
        if read_status != Status.SUCCESS:
            self.feedback_message = read_node.feedback_message
            return Status.FAILURE

        em_state = self._result_out.get("em_before")
        if not isinstance(em_state, EM) or not is_em_embargo_active(em_state):
            bad_state = VultronInvalidStateTransitionError(
                f"Cannot propose embargo revision: case '{self._case_id}'"
                f" EM state '{em_state}' does not allow a revision proposal."
                f" Use propose-embargo for initial proposals."
            )
            self._result_out["error"] = bad_state
            self.feedback_message = str(bad_state)
            return Status.FAILURE

        return Status.SUCCESS


class _EmbargoLifecycleNode(DataLayerActionWithPorts):
    """Base node for EmbargoLifecycle strict-mode transitions.

    1. ``ReadEmStateNode`` reads ``em_state`` → ``result_out["em_before"]``.
    2. The subclass ``_transition()`` calls the service; the service writes
       the EM state update directly (EMB-18-001).
    """

    def __init__(
        self, result_out: dict[str, object], name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._result_out = result_out

    def _case_id(self) -> str:
        raise NotImplementedError

    def _transition(
        self,
        _lifecycle: EmbargoLifecycle,
        _actor_id: str,
        _em_before: EM,
    ) -> EmbargoLifecycleResult:
        raise NotImplementedError

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        # AC-1: read em_state via named BT node, not inline service code.
        read_node = ReadEmStateNode(
            case_id=self._case_id(), result_out=self._result_out
        )
        read_node.datalayer = self.datalayer
        read_status = read_node.update()
        if read_status != Status.SUCCESS:
            self.feedback_message = read_node.feedback_message
            return Status.FAILURE
        em_before = self._result_out["em_before"]
        assert isinstance(em_before, EM)

        lifecycle = EmbargoLifecycle(persistence=self.datalayer)
        try:
            result = self._transition(lifecycle, self.actor_id, em_before)
        except VultronError as exc:
            self._result_out["error"] = exc
            self.feedback_message = str(exc)
            return Status.FAILURE

        self._result_out["lifecycle_result"] = result
        self._result_out["em_after"] = result.em_after

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
        self._case_id_value = case_id
        self._embargo_id = embargo_id

    def _case_id(self) -> str:
        return self._case_id_value

    def _transition(
        self,
        lifecycle: EmbargoLifecycle,
        actor_id: str,
        em_before: EM,
    ) -> EmbargoLifecycleResult:
        return lifecycle.propose_embargo(
            case_id=self._case_id_value,
            embargo_id=self._embargo_id,
            actor_id=actor_id,
            transition_mode=TransitionMode.STRICT,
            em_before=em_before,
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
        self._case_id_value = case_id
        self._embargo_id = embargo_id

    def _case_id(self) -> str:
        return self._case_id_value

    def _transition(
        self,
        lifecycle: EmbargoLifecycle,
        actor_id: str,
        em_before: EM,
    ) -> EmbargoLifecycleResult:
        return lifecycle.accept_embargo_invite(
            case_id=self._case_id_value,
            embargo_id=self._embargo_id,
            actor_id=actor_id,
            transition_mode=TransitionMode.STRICT,
            em_before=em_before,
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
        self._case_id_value = case_id
        self._embargo_id = embargo_id

    def _case_id(self) -> str:
        return self._case_id_value

    def _transition(
        self,
        lifecycle: EmbargoLifecycle,
        actor_id: str,
        em_before: EM,
    ) -> EmbargoLifecycleResult:
        return lifecycle.reject_embargo_invite(
            case_id=self._case_id_value,
            embargo_id=self._embargo_id,
            actor_id=actor_id,
            transition_mode=TransitionMode.STRICT,
            em_before=em_before,
        )


class TerminateEmbargoLifecycleNode(_EmbargoLifecycleNode):
    """Apply STRICT terminate-active-embargo transition.

    AC-3: terminate semantics require an active embargo; the upstream
    ``HasActiveEmbargoNode`` guard in ``terminate_embargo_bt`` enforces that
    the case satisfies ``EmbargoedCase`` preconditions before this node runs.
    """

    def __init__(
        self,
        case_id: str,
        result_out: dict[str, object],
        name: str | None = None,
    ) -> None:
        super().__init__(result_out=result_out, name=name)
        self._case_id_value = case_id

    def _case_id(self) -> str:
        return self._case_id_value

    def _transition(
        self,
        lifecycle: EmbargoLifecycle,
        actor_id: str,
        em_before: EM,
    ) -> EmbargoLifecycleResult:
        return lifecycle.terminate_active_embargo(
            case_id=self._case_id_value,
            actor_id=actor_id,
            transition_mode=TransitionMode.STRICT,
            em_before=em_before,
        )


class ReadEmbargoIdNode(DataLayerActionWithPorts):
    """Read the active embargo ID from the case and write it to the blackboard.

    Returns FAILURE when the case is not found, has no active embargo, or
    the DataLayer is unavailable.  Returns SUCCESS and writes ``embargo_id``
    to the blackboard on success.
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {"embargo_id": PortInformation(data_type=str, required=True)}

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"embargo_id": "/embargo_id"}

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        embargo_id = _as_id(case.active_embargo)
        if embargo_id is None:
            self.feedback_message = (
                f"No active embargo on case '{self._case_id}'"
            )
            return Status.FAILURE

        self._set_output("embargo_id", embargo_id)
        return Status.SUCCESS


class SetEmbargoActiveNode(DataLayerActionWithPorts):
    """Set embargo active on case and transition EM → ACTIVE.

    Routes EM activation through ``EmbargoLifecycle.activate_embargo()``
    in STRICT mode (EMB-18-001).  Returns FAILURE for non-standard EM
    transitions (EMB-18-002): valid source states are PROPOSED and REVISE.
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        name: str | None = None,
        transition_mode: TransitionMode = TransitionMode.STRICT,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.embargo_id = embargo_id
        self._transition_mode = transition_mode

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        # Idempotency check: avoid calling EmbargoLifecycle when the embargo
        # is already active (ACTIVE + matching id is not a valid ACCEPT source).
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        current_embargo_id = _as_id(case.active_embargo)
        if current_embargo_id == self.embargo_id:
            self.feedback_message = (
                f"Case '{self.case_id}' already has embargo"
                f" '{self.embargo_id}' active — idempotent no-op"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

        # EMB-18-001: route EM activation through EmbargoLifecycle.activate_embargo().
        lifecycle = EmbargoLifecycle(persistence=self.datalayer)
        try:
            result = lifecycle.activate_embargo(
                case_id=self.case_id,
                embargo_id=self.embargo_id,
                actor_id=self.actor_id,
                transition_mode=self._transition_mode,
            )
        except (
            VultronNotFoundError,
            VultronInvalidStateTransitionError,
            ValueError,
        ) as exc:
            self.feedback_message = str(exc)
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        em_before = result.em_before
        em_after = result.em_after
        self.feedback_message = (
            f"Activated embargo '{self.embargo_id}' on case"
            f" '{self.case_id}' (EM {em_before} → {em_after})"
        )
        self.logger.debug("%s: %s", self.name, self.feedback_message)
        # SL-04-001/SL-04-006: embargo activation is a protocol milestone.
        if em_after != em_before:
            log_em_transition(
                self.logger,
                self.actor_id or "<unknown>",
                self.case_id,
                em_before,
                em_after,
            )
        return Status.SUCCESS
