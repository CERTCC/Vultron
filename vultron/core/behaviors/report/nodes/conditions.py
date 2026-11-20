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

"""Condition nodes for the report behavior tree."""

from py_trees.common import Status

from vultron.core.behaviors.act_key_ports import (
    act_key_ports,
    act_key_remappings,
    act_value,
    optional_act_value,
)
from vultron.core.behaviors.act_keys import CASE_ID, SENDER_ID
from vultron.core.behaviors.case.nodes.case_lookup import (
    CaseIdInputPortMixin,
)
from vultron.core.behaviors.case.nodes.participant.common import (
    resolve_participant_state_from_dl,
)
from vultron.core.behaviors.helpers import (
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.predicates.embargo import pxa_is_embargo_eligible
from vultron.core.states.rm import RM


class _CheckReportPhaseRMStateBase(DataLayerConditionWithPorts):
    """Shared update() skeleton for report-phase RM presence checks.

    Resolves actor_id, computes the RM.VALID status key, and dispatches on
    ``_success_when_valid`` to determine which Status value to return.
    Subclasses set ``_success_when_valid = True`` (succeed when VALID) or
    ``False`` (succeed when NOT VALID).
    """

    _success_when_valid: bool

    def __init__(
        self,
        report_id: str,
        sender_actor_id: str | None = None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id
        self.sender_actor_id = sender_actor_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        link_id = VultronReportCaseLink.build_id(self.report_id)
        link = self.datalayer.read(link_id)
        if isinstance(link, VultronReportCaseLink):
            is_valid = link.rm_state == RM.VALID
        else:
            # No link yet → implicit RM.RECEIVED (not yet VALID)
            is_valid = False

        if is_valid:
            if self._success_when_valid:
                self.logger.debug(
                    "%s: Report %s already VALID", self.name, self.report_id
                )
                return Status.SUCCESS
            self.logger.debug(
                "%s: Report %s already VALID - precondition failed",
                self.name,
                self.report_id,
            )
            return Status.FAILURE

        if self._success_when_valid:
            self.logger.debug(
                "%s: Report %s not in VALID state", self.name, self.report_id
            )
            return Status.FAILURE
        self.logger.debug(
            "%s: Report %s in acceptable state for validation",
            self.name,
            self.report_id,
        )
        return Status.SUCCESS


class CheckRMStateValid(_CheckReportPhaseRMStateBase):
    """Check if report is already in RM.VALID state.

    Returns SUCCESS if report status is RM.VALID (early exit optimization).
    Returns FAILURE if report is in any other state.

    Input ports (inherited + declared):
        datalayer (object, required): CasePersistence, remapped to /datalayer.
        actor_id (str, required): Executing actor ID, remapped to /actor_id.

    Per BTND-03-009: typed port declarations replace register_key().
    """

    _success_when_valid = True


class CheckRMStateReceivedOrInvalid(_CheckReportPhaseRMStateBase):
    """Check the report is not already in RM.VALID.

    Returns SUCCESS for any state but VALID; FAILURE when the report is
    already VALID.  An illegal source state such as CLOSED passes here and is
    refused by the RM transition that follows (``TransitionRMtoValid``).

    Input ports (inherited + declared):
        datalayer (object, required): CasePersistence, remapped to /datalayer.
        actor_id (str, required): Executing actor ID, remapped to /actor_id.

    Per BTND-03-009: typed port declarations replace register_key().
    """

    _success_when_valid = False


class _CheckParticipantRMStateBase(DataLayerConditionWithPorts):
    """Shared update() skeleton for case-participant RM state guard nodes.

    Reads an actor's latest RM state in the case on ``/case_id``
    (BTND-01-008) and returns SUCCESS when it equals ``_target_rm``.
    Subclasses set ``_target_rm`` as a class attribute.  The actor is the
    executing one, whose own state a trigger tree checks before it acts;
    :class:`CheckParticipantRMState` checks the sender's instead
    (RSH-08-001).
    """

    _target_rm: RM

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        **act_key_ports(CASE_ID),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return act_key_remappings(CASE_ID)

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id: str | None = None
        self._actor_id: str | None = None

    def initialise(self) -> None:
        super().initialise()
        self._case_id = optional_act_value(self, CASE_ID, str)
        self._actor_id = self._subject_actor_id()

    def _subject_actor_id(self) -> str | None:
        """The actor whose RM state is checked: the executing actor."""
        return self.actor_id

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self._actor_id is not None

        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        participant_id = case.actor_participant_index.get(self._actor_id)
        if participant_id is None:
            self.logger.warning(
                "%s: actor '%s' not in case '%s'",
                self.name,
                self._actor_id,
                self._case_id,
            )
            return Status.FAILURE

        rm_state, _, _ = resolve_participant_state_from_dl(
            self.datalayer, participant_id
        )
        target = self._target_rm
        if rm_state == target:
            self.logger.debug(
                "%s: RM state is %s for actor '%s'",
                self.name,
                target.name,
                self._actor_id,
            )
            return Status.SUCCESS

        self.feedback_message = (
            f"Actor '{self._actor_id}' RM state is {rm_state!r},"
            f" expected {target!r}"
        )
        self.logger.debug("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


class CheckRMStateAccepted(_CheckParticipantRMStateBase):
    """Guard: actor RM state must be ACCEPTED to create a fix.

    Returns ``SUCCESS`` when the actor's latest RM state is ``RM.ACCEPTED``.
    Returns ``FAILURE`` otherwise, blocking the fix-creation action nodes.

    Per AC-7 (issue #1812).
    """

    _target_rm = RM.ACCEPTED


class CheckParticipantRMState(_CheckParticipantRMStateBase):
    """Guard: sender RM is already *target_rm*; a restated move is recorded once.

    The sender is read from ``/sender_id`` (BTND-01-008).

    It is the first child of the repeat Selector
    :func:`~vultron.core.behaviors.report.rm_declaration_tree.unless_rm_already_recorded`
    builds, so its ``SUCCESS`` skips the write: the declared state is already
    recorded and the run changes nothing.  It says so as a
    :class:`~vultron.core.behaviors.idempotency.ReportsNoChange`, so the
    handler reports the run ``SKIPPED``, not ``APPLIED`` (RSH-08-002,
    ID-05-003, #5006).
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **_CheckParticipantRMStateBase.INPUT_PORTS,
        **act_key_ports(SENDER_ID),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return act_key_remappings(CASE_ID, SENDER_ID)

    def __init__(self, target_rm: RM, name: str | None = None) -> None:
        super().__init__(name=name)
        self._target_rm = target_rm

    def _subject_actor_id(self) -> str | None:
        """The sender, whose declared RM state is checked (RSH-08-001)."""
        return act_value(self, SENDER_ID, str)

    @property
    def succeeded_without_change(self) -> bool:
        """True when the declared RM state was already recorded."""
        return self.status == Status.SUCCESS

    @property
    def no_change_reason(self) -> str:
        """Why the run changed nothing."""
        return "the declared RM state is already recorded for the sender"


class EnsureEmbargoExists(CaseIdInputPortMixin, DataLayerConditionWithPorts):
    """Check that the case for this report may reach RM.VALID embargo-wise.

    Returns SUCCESS if the case has a non-None ``active_embargo``, or if the
    case is not embargo-eligible (any of P, X or A set).  Returns FAILURE for
    an embargo-eligible case with no active embargo.

    Implements DUR-07-004: an embargo end time MUST be established before an
    embargo-eligible case reaches RM.VALID.  A case that is not
    embargo-eligible never receives an embargo (EP-04-020) and is validated
    at its current EM state, typically ``EM.NONE``; eligibility is read with
    :func:`~vultron.core.predicates.embargo.pxa_is_embargo_eligible`.

    The case comes from the ``/case_id`` blackboard key published upstream by
    :class:`~vultron.core.behaviors.case.nodes.case_lookup.RequireCaseForReport`
    rather than from a second ``find_case_by_report_id`` call, so a tree resolves
    "the case for this report" exactly once (ARCH-15-004).

    Input ports (inherited + declared):
        datalayer (object, required): CasePersistence, remapped to /datalayer.
        actor_id (str, required): Executing actor ID, remapped to /actor_id.
        case_id (str, optional): remapped to /case_id; required in practice.

    Per BTND-03-009: typed port declarations replace register_key().
    """

    def __init__(self, report_id: str, name: str | None = None):
        """Initialize EnsureEmbargoExists node.

        Args:
            report_id: ID of the VulnerabilityReport, used only for log context.
            name: Optional custom node name (defaults to class name).
        """
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case_id = self._resolve_case_id()
        if case_id is None:
            return Status.FAILURE

        case, failure = self._require_case(case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)
        if case.active_embargo is None and not pxa_is_embargo_eligible(
            case.current_status.pxa.state
        ):
            self.logger.debug(
                "%s: Case for report %s is not embargo-eligible (P/X/A set)"
                " — validation proceeds without an embargo (DUR-07-004,"
                " EP-04-008)",
                self.name,
                self.report_id,
            )
            return Status.SUCCESS
        if case.active_embargo is None:
            self.logger.warning(
                "%s: Case for report %s is embargo-eligible but has no"
                " active embargo — validation blocked (DUR-07-004)",
                self.name,
                self.report_id,
            )
            return Status.FAILURE

        self.logger.debug(
            "%s: Case for report %s has active embargo",
            self.name,
            self.report_id,
        )
        return Status.SUCCESS


class EvaluateReportCredibility(DataLayerConditionWithPorts):
    """
    Evaluate report credibility using policy.

    Phase 1: Always returns SUCCESS (stub implementation).
    Future: Implement configurable policy for credibility checks.

    This node implements the credibility check from the simulation BT.
    """

    def __init__(self, report_id: str, name: str | None = None):
        """
        Initialize EvaluateReportCredibility node.

        Args:
            report_id: ID of VulnerabilityReport to evaluate
            name: Optional custom node name (defaults to class name)
        """
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id

    def update(self) -> Status:
        """
        Evaluate report credibility (stub: always succeeds).

        Returns:
            SUCCESS (always, for Phase 1)
        """
        self.logger.info(
            "%s: Evaluating credibility for report %s (stub: always accepts)",
            self.name,
            self.report_id,
        )
        return Status.SUCCESS


class EvaluateReportValidity(DataLayerConditionWithPorts):
    """
    Evaluate report technical validity using policy.

    Phase 1: Always returns SUCCESS (stub implementation).
    Future: Implement configurable policy for validity checks.

    This node implements the validity check from the simulation BT.
    """

    def __init__(self, report_id: str, name: str | None = None):
        """
        Initialize EvaluateReportValidity node.

        Args:
            report_id: ID of VulnerabilityReport to evaluate
            name: Optional custom node name (defaults to class name)
        """
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id

    def update(self) -> Status:
        """
        Evaluate report validity (stub: always succeeds).

        Returns:
            SUCCESS (always, for Phase 1)
        """
        self.logger.info(
            "%s: Evaluating validity for report %s (stub: always accepts)",
            self.name,
            self.report_id,
        )
        return Status.SUCCESS


class EvaluateCasePriority(DataLayerConditionWithPorts):
    """
    Evaluate whether to engage or defer a case using prioritization policy.

    Phase 1: Always returns SUCCESS (stub — always engage).
    Future: Plug in SSVC or other priority framework via PrioritizationPolicy.

    This node is used when the local actor is DECIDING whether to engage or
    defer (i.e., generating an outgoing RmEngageCaseActivity or
    RmDeferCaseActivity message), as opposed to the receive-side nodes above
    which record a decision already made by the sending actor.

    See specs/prototype-shortcuts.yaml PROTO-05-001 for SSVC deferral policy.
    """

    def __init__(self, case_id: str, name: str | None = None):
        """
        Initialize EvaluateCasePriority node.

        Args:
            case_id: ID of VulnerabilityCase to evaluate
            name: Optional custom node name (defaults to class name)
        """
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def update(self) -> Status:
        """
        Evaluate case priority (stub: always engage).

        Returns:
            SUCCESS (always, for Phase 1)
        """
        self.logger.info(
            "%s: Evaluating priority for case %s (stub: always engage)",
            self.name,
            self.case_id,
        )
        return Status.SUCCESS
