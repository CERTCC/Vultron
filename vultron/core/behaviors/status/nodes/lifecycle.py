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

"""Case lifecycle trigger nodes for DEMOMA-07-003 steps 4–5.

Contains the public-disclosure embargo teardown branch (step 4, legacy
``PublicDisclosureBranchNode``, kept for export compatibility), and the
auto-close emit node (step 5).  The auto-close precondition and idempotency
guards are in ``conditions.py``; the routing guard is
:class:`~vultron.core.behaviors.sender.nodes.actions.ResolveCaseManagerNode`.

EmbargoTeardownAuthorizationGate nodes (``ThreatTerminationBranchNode``) live in
:mod:`~vultron.core.behaviors.status.nodes.threat_termination` and are
re-exported from here for backward-compatible import paths.
"""

import logging
from typing import cast

import py_trees
from py_trees.common import Status
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.embargo.trigger_tree import (
    reject_proposed_embargo_bt,
    terminate_embargo_bt,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.protocols import PersistableModel
from vultron.core.predicates.roles import has_case_owner_role
from vultron.core.states.em import EM
from vultron.core.behaviors.status.nodes.threat_termination import (  # noqa: F401
    ThreatTerminationBranchNode,
    _ThreatTerminationSkipConditionNode,
)

logger = logging.getLogger(__name__)


class _PublicDisclosureSkipConditionNode(DataLayerConditionWithPorts):
    """Inner guard for :class:`PublicDisclosureBranchNode`.

    Returns SUCCESS (skip teardown) when:
    - The new status is NOT public-aware (CS.P not set), OR
    - DataLayer or case_id is unavailable, OR
    - The sender is not a known case participant, OR
    - The sender does NOT hold the CASE_OWNER role, OR
    - The EM state is NONE or EXITED (nothing to tear down).

    Returns FAILURE (proceed to teardown) when the sender IS a CASE_OWNER
    who has sent a public-aware status update AND EM state is ACTIVE, REVISE,
    or PROPOSED (EMB-16-001).
    """

    def __init__(
        self,
        status_obj: PersistableModel | None,
        sender_actor_id: str,
        case_id: str | None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.status_obj = status_obj
        self.sender_actor_id = sender_actor_id
        self.case_id = case_id

    def _public_aware(self) -> bool:
        """Return True if the status signals public awareness (CS.P is set)."""
        from vultron.core.states.cs import CS_pxa

        case_status: object = getattr(self.status_obj, "case_status", None)
        if case_status is None:
            pxa_state = None
        elif hasattr(case_status, "pxa"):
            _pxa = getattr(case_status, "pxa")
            if _pxa is None:
                return False
            pxa_state = _pxa.state
        elif hasattr(case_status, "pxa_state"):
            pxa_state = getattr(case_status, "pxa_state")
        else:
            pxa_state = None
        if pxa_state is None:
            return False
        return pxa_state in (
            CS_pxa.Pxa,
            CS_pxa.PxA,
            CS_pxa.PXa,
            CS_pxa.PXA,
        )

    def _sender_is_case_owner(self, case: VulnerabilityCase) -> bool:
        """Return True iff sender is a known CASE_OWNER participant."""
        assert self.datalayer is not None
        sender_participant_id = case.actor_participant_index.get(
            self.sender_actor_id
        )
        if sender_participant_id is None:
            return False
        sender_participant = self.datalayer.read(sender_participant_id)
        roles = (
            sender_participant.roles
            if isinstance(sender_participant, CaseParticipant)
            else []
        )
        return has_case_owner_role(roles)

    def _em_state(self, case: VulnerabilityCase) -> EM:
        """Return current EM state; falls back to NONE on missing status."""
        try:
            return case.current_status.em.state
        except (ValueError, AttributeError):
            return EM.NONE

    def update(self) -> Status:
        if not self._public_aware():
            return Status.SUCCESS

        if self.datalayer is None or not self.case_id:
            return Status.SUCCESS

        # Lenient guard (ADR-0087): this node returns FAILURE only to *signal*
        # that a teardown is required; every other path is SUCCESS ("nothing to
        # tear down"). An unresolvable case cannot require a teardown, so
        # SUCCESS is the correct nothing-to-do answer (conformance allowlist).
        case = self.datalayer.read_case(self.case_id)
        if case is None:
            return Status.SUCCESS

        if not self._sender_is_case_owner(case):
            return Status.SUCCESS

        # Check EM state directly (EMB-16-001): teardown is required for
        # ACTIVE, REVISE (terminate path) and PROPOSED (reject path).
        # NONE and EXITED have nothing to tear down.
        em_state = self._em_state(case)
        if em_state not in (EM.ACTIVE, EM.REVISE, EM.PROPOSED):
            return Status.SUCCESS

        # Condition met: sender is CASE_OWNER reporting public awareness AND
        # there is an active or proposed embargo to handle.
        return Status.FAILURE


class PublicDisclosureBranchNode(py_trees.composites.Selector):
    """Step 4: Trigger embargo teardown if public disclosure is detected.

    Condition: the new ParticipantStatus has CS.P (public-aware) set AND
    the sender holds the CASE_OWNER role.

    When the condition is met, routes teardown based on EM state (EMB-16-001):

    - EM ACTIVE/REVISE → ``terminate_embargo_bt`` (terminate path).
    - EM PROPOSED → ``reject_proposed_embargo_bt`` (reject path, EMB-16-001).

    Skips silently if conditions are not met (EM NONE/EXITED, or sender is not
    CASE_OWNER, or status is not public-aware).

    Returns SUCCESS when teardown conditions are not met (skip path) or
    when teardown completes and the broadcast activity is queued.
    Returns FAILURE when teardown is needed but routing prerequisites are
    absent or the activity cannot be dispatched (BT-14-001, BT-19-001).

    Implemented as a ``py_trees.composites.Selector`` (memory=False):

    - Child 1 ``_PublicDisclosureSkipConditionNode``: SUCCESS → skip teardown.
    - Child 2 Teardown Selector: tries ACTIVE/REVISE arm then PROPOSED arm.
      - ``TerminateEmbargoBT``: for EM ACTIVE/REVISE.
      - ``RejectProposedEmbargoBT``: for EM PROPOSED (EMB-16-001).

    Per DEMOMA-07-003 step 4, EMB-16-001.
    """

    def __init__(
        self,
        status_obj: PersistableModel | None,
        sender_actor_id: str,
        case_id: str | None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__, memory=False)
        result_out: dict[str, object] = {}
        if case_id is None:
            teardown_subtree: py_trees.behaviour.Behaviour = (
                py_trees.behaviours.Success(name="TeardownSkipped")
            )
        else:
            reject_proposed_subtree = reject_proposed_embargo_bt(
                case_id=case_id,
                result_out=result_out,
            )
            terminate_subtree = terminate_embargo_bt(
                case_id=case_id,
                result_out=result_out,
            )
            # Selector: try terminate (ACTIVE/REVISE) first; if it fails because
            # there is no active embargo, try reject (PROPOSED).
            teardown_subtree = py_trees.composites.Selector(
                name="TeardownSelector",
                memory=False,
                children=[terminate_subtree, reject_proposed_subtree],
            )
        self.add_children(
            [
                _PublicDisclosureSkipConditionNode(
                    status_obj=status_obj,
                    sender_actor_id=sender_actor_id,
                    case_id=case_id,
                    name="SkipCondition",
                ),
                teardown_subtree,
            ]
        )


class EmitCloseCaseNode(DataLayerActionWithPorts):
    """Step 5 emit: Queue a ``Leave(VulnerabilityCase)`` to the Case Manager.

    Reads ``case_manager_id`` from the blackboard (written by the preceding
    :class:`~vultron.core.behaviors.sender.nodes.actions.ResolveCaseManagerNode`)
    and calls ``trigger_activity_factory.close_case(...)`` to create and queue
    the activity.

    Returns SUCCESS when the activity is queued successfully or when
    ``trigger_activity_factory`` is absent (best-effort: receive-side paths
    intentionally omit the factory).
    Returns FAILURE only on an unexpected exception during activity creation.

    Per DEMOMA-07-003 step 5, DEMOMA-07-006.
    """

    def __init__(
        self,
        case_id: str | None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_manager_id": PortInformation(data_type=str, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_manager_id": "/case_manager_id"}

    def initialise(self) -> None:
        super().initialise()
        try:
            self.case_manager_id: str | None = self.get_input(
                "case_manager_id"
            )
        except (NoDataAvailable, NotImplementedError):
            self.case_manager_id = None

    def update(self) -> Status:
        if self.datalayer is None or not self.case_id:
            return Status.SUCCESS

        if self.trigger_activity_factory is None:
            self.logger.warning(
                "EmitCloseCase: no TriggerActivityPort — cannot emit"
                " Leave(VulnerabilityCase) for case '%s'",
                self.case_id,
            )
            return Status.SUCCESS

        case_manager_id = self.case_manager_id
        if not case_manager_id:
            self.feedback_message = (
                f"EmitCloseCase: case_manager_id not set on blackboard"
                f" for case '{self.case_id}' — cannot emit"
            )
            self.logger.warning(self.feedback_message)
            return Status.SUCCESS

        try:
            activity_id, _ = self.trigger_activity_factory.close_case(
                case_id=self.case_id,
                actor=self.actor_id or "",
                to=[case_manager_id],
            )
            cast(CaseOutboxPersistence, self.datalayer).outbox_append(
                activity_id
            )
            self.logger.info(
                "EmitCloseCase: queued Leave(VulnerabilityCase) '%s'"
                " to CaseActor '%s' (DEMOMA-07-003 step 5)",
                activity_id,
                case_manager_id,
            )
        except Exception as e:
            self.feedback_message = (
                f"EmitCloseCase: failed to emit close_case: {e}"
            )
            self.logger.error(self.feedback_message)
            return Status.FAILURE

        return Status.SUCCESS
