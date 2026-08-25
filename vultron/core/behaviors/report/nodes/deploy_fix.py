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
"""Production-layer BT nodes for the fix deployment workflow.

Six nodes implement the ``DeployFixBT`` guard/action logic:

- :class:`CSinStateFixDeployed` — short-circuit: fix already deployed
- :class:`RMinStateDeferred` — guard: actor RM is DEFERRED (stay-deferred arm)
- :class:`CheckNoNewDeploymentInfoNode` — ProtocolInternal condition reading a
  change-detection flag written by the upstream ``NewDeploymentInfoSentinel``
- :class:`CheckCSFixNotYetDeployed` — guard: fix not yet deployed (d bit unset)
- :class:`TransitionCStoFixDeployed` — persist VFD VFD snapshot (d→D)
- :class:`EmitCDActivity` — emit CD (Fix Deployed) to the Case Actor

``CheckDeployerRoleNode`` (d→D role guard) is reused from
``vultron.core.behaviors.case.nodes.vfd_role_guards`` (AC-3), and
``CheckRMStateAccepted`` is reused from
``vultron.core.behaviors.report.nodes.develop_fix`` (AC-3).

References: Issue #1825; Source #1248; Concern #1813.
Spec BT-06-001, BT-18-004; ADR-0021 CLP-10-001 (CD via Case Actor); ADR-0025.
Notes: ``notes/bt-fuzzer-rm-fix.md``.
"""

import logging
from typing import cast

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.case.nodes.participant.common import (
    resolve_case_manager_id,
    resolve_participant_state_from_dl,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.dimensions import VfdDimension
from vultron.core.ports.case_persistence import (
    CaseOutboxPersistence,
    CasePersistence,
)
from vultron.core.states.cs import CS_vfd
from vultron.core.states.rm import RM

logger = logging.getLogger(__name__)

NEW_DEPLOYMENT_INFO_KEY = "new_deployment_info"


def _resolve_vfd_state(
    dl: CasePersistence,
    case: VulnerabilityCase,
    actor_id: str,
    node_name: str,
) -> CS_vfd | None:
    """Return the actor's current VFD state in *case*, or None on lookup error.

    Returns ``None`` (caller returns FAILURE) when the actor has no participant
    record in the case.
    """
    participant_id = case.actor_participant_index.get(actor_id)
    if participant_id is None:
        logger.warning(
            "%s: actor '%s' not in case '%s'",
            node_name,
            actor_id,
            case.id_,
        )
        return None
    _, vfd_state = resolve_participant_state_from_dl(dl, participant_id)
    return vfd_state


class CSinStateFixDeployed(DataLayerConditionWithPorts):
    """Short-circuit guard: fix already deployed means nothing to do.

    Returns ``SUCCESS`` when the actor's VFD state is already fix-deployed
    (``CS_vfd.VFD``) — the ``DeployFixBT`` Fallback short-circuits and reports
    SUCCESS to the parent.  Returns ``FAILURE`` when the fix is NOT yet
    deployed, allowing the deployment arms to proceed.

    Per AC-1 (issue #1825); mirrors ``CheckCSFixNotYetReady`` from
    ``develop_fix.py`` but keyed on the fix-deployed (D) bit.
    """

    def __init__(
        self,
        case_id: str,
        actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._actor_id = actor_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case = self.datalayer.read(self._case_id)
        if not isinstance(case, VulnerabilityCase):
            self.logger.warning(
                "%s: case '%s' not found", self.name, self._case_id
            )
            return Status.FAILURE

        vfd_state = _resolve_vfd_state(
            self.datalayer, case, self._actor_id, self.name
        )
        if vfd_state is None:
            return Status.FAILURE

        if VfdDimension(state=vfd_state).is_fix_deployed():
            self.logger.debug(
                "%s: VFD state=%s is fix-deployed — short-circuit SUCCESS",
                self.name,
                vfd_state,
            )
            return Status.SUCCESS

        self.logger.debug(
            "%s: VFD state=%s is not fix-deployed — proceed to deployment",
            self.name,
            vfd_state,
        )
        return Status.FAILURE


class CheckCSFixNotYetDeployed(DataLayerConditionWithPorts):
    """Guard: fix must be READY but NOT yet deployed (VFD state == ``VFd``).

    Returns ``SUCCESS`` only when the actor's VFD state is fix-ready and the
    fix is not yet deployed — i.e. exactly ``CS_vfd.VFd``.  Returns ``FAILURE``
    when the fix is not yet ready (``vfd``/``Vfd``) or already deployed
    (``VFD``).

    This enforces the VFD state-machine precondition for the d→D transition,
    which is valid **only** from ``VFd`` (``_vfd_transitions`` in
    ``vultron/core/states/cs.py``).  A weaker "D bit not set" check would let a
    deployer in ``vfd``/``Vfd`` jump straight to ``VFD`` via
    :class:`TransitionCStoFixDeployed`, producing an invalid status snapshot.
    Mirrors the legacy ``CSinStateVendorAwareFixReadyFixNotDeployed`` guard in
    ``_DeployFixWhenReady``.

    Per AC-3 (issue #1825); guards the ``_DeployFixIfReady`` Sequence.
    """

    def __init__(
        self,
        case_id: str,
        actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._actor_id = actor_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case = self.datalayer.read(self._case_id)
        if not isinstance(case, VulnerabilityCase):
            self.logger.warning(
                "%s: case '%s' not found", self.name, self._case_id
            )
            return Status.FAILURE

        vfd_state = _resolve_vfd_state(
            self.datalayer, case, self._actor_id, self.name
        )
        if vfd_state is None:
            return Status.FAILURE

        dim = VfdDimension(state=vfd_state)
        if not dim.is_fix_ready():
            self.feedback_message = (
                f"Actor '{self._actor_id}' fix not yet ready"
                f" (VFD state={vfd_state!r}) — d→D transition requires VFd"
            )
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        if dim.is_fix_deployed():
            self.feedback_message = (
                f"Actor '{self._actor_id}' fix already deployed"
                f" (VFD state={vfd_state!r}) — d→D transition blocked"
            )
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        self.logger.debug(
            "%s: VFD state=%s is fix-ready-not-deployed — proceed",
            self.name,
            vfd_state,
        )
        return Status.SUCCESS


class RMinStateDeferred(DataLayerConditionWithPorts):
    """Guard: actor RM state must be DEFERRED (stay-deferred arm).

    Returns ``SUCCESS`` when the actor's latest RM state is ``RM.DEFERRED``.
    Returns ``FAILURE`` otherwise.  Used as the first child of the
    ``_ShouldStayInRmDeferred`` Sequence: a deferred deployer with no new
    deployment info should stay deferred (short-circuit the Fallback).

    Per AC-1 (issue #1825); mirrors ``CheckRMStateAccepted`` from
    ``develop_fix.py`` but keyed on ``RM.DEFERRED``.
    """

    def __init__(
        self,
        case_id: str,
        actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._actor_id = actor_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case = self.datalayer.read(self._case_id)
        if not isinstance(case, VulnerabilityCase):
            self.logger.warning(
                "%s: case '%s' not found", self.name, self._case_id
            )
            return Status.FAILURE

        participant_id = case.actor_participant_index.get(self._actor_id)
        if participant_id is None:
            self.logger.warning(
                "%s: actor '%s' not in case '%s'",
                self.name,
                self._actor_id,
                self._case_id,
            )
            return Status.FAILURE

        rm_state, _ = resolve_participant_state_from_dl(
            self.datalayer, participant_id
        )

        if rm_state == RM.DEFERRED:
            self.logger.debug(
                "%s: RM state is DEFERRED for actor '%s'",
                self.name,
                self._actor_id,
            )
            return Status.SUCCESS

        self.feedback_message = (
            f"Actor '{self._actor_id}' RM state is {rm_state!r},"
            f" expected RM.DEFERRED"
        )
        self.logger.debug("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


class CheckNoNewDeploymentInfoNode(DataLayerConditionWithPorts):
    """ProtocolInternal condition: no new deployment info has arrived.

    Reads the blackboard flag ``new_deployment_info`` written by the upstream
    ``NewDeploymentInfoSentinel`` (FUZZ-08f).  Returns ``SUCCESS`` when the
    flag is absent or falsy (no new info — safe to stay deferred) and
    ``FAILURE`` when the flag is truthy (new info arrived — re-evaluate
    deployment).

    This node is NOT a call-out injection seam — the external agent seam is at
    the Sentinel that writes the flag, not at this consuming condition
    (see ``notes/bt-fuzzer-rm-fix.md`` § ``NoNewDeploymentInfo``).  Defaulting
    to SUCCESS when the key is absent matches the legacy fuzzer's
    ``UsuallySucceed`` (p=0.75) happy path: most ticks have no new info.

    Per AC-4 (issue #1825).
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports[NEW_DEPLOYMENT_INFO_KEY] = PortInformation(
            data_type=object, required=False
        )
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {NEW_DEPLOYMENT_INFO_KEY: f"/{NEW_DEPLOYMENT_INFO_KEY}"}

    def initialise(self) -> None:
        super().initialise()
        try:
            self._new_deployment_info = self.get_input(NEW_DEPLOYMENT_INFO_KEY)
        except (NoDataAvailable, NotImplementedError):
            self._new_deployment_info = None

    def update(self) -> Status:
        new_info = self._new_deployment_info

        if new_info:
            self.feedback_message = (
                "new deployment info present — re-evaluate deployment"
            )
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        self.logger.debug(
            "%s: no new deployment info — stay deferred", self.name
        )
        return Status.SUCCESS


class TransitionCStoFixDeployed(DataLayerActionWithPorts):
    """Persist a VFD ParticipantStatus snapshot for the actor in this case.

    Advances the actor's VFD dimension to ``CS_vfd.VFD`` (fix deployed) and
    persists the new ``ParticipantStatus`` record via the DataLayer, appending
    it to the ``CaseParticipant.participant_statuses`` list.

    Per AC-5 (issue #1825); follows the ``TransitionCStoFixReady`` pattern from
    ``develop_fix.py`` but targets the d→D transition.
    """

    def __init__(
        self,
        case_id: str,
        actor_id: str,
        result_out: dict | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._actor_id = actor_id
        self._result_out = result_out if result_out is not None else {}

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        from vultron.core.behaviors.case.nodes.participant.status import (
            CreateParticipantStatusNode,
        )

        node = CreateParticipantStatusNode(
            case_id=self._case_id,
            actor_id=self._actor_id,
            rm_state=None,
            vfd_state=CS_vfd.VFD,
            pxa_state=None,
            result_out=self._result_out,
            name=f"{self.name}._Create",
        )
        node.datalayer = self.datalayer

        try:
            status = node.update()
            if status == Status.SUCCESS:
                # The narrative INFO line (SL-04-006) is emitted by
                # CreateParticipantStatusNode, which knows the before-state.
                self.logger.debug(
                    "%s: VFd → VFD (fix deployed) for actor '%s' in case '%s'",
                    self.name,
                    self._actor_id,
                    self._case_id,
                )
            return status
        except Exception as e:
            self.logger.error(
                "%s: Error transitioning to VFD: %s", self.name, e
            )
            return Status.FAILURE


class EmitCDActivity(DataLayerActionWithPorts):
    """Emit a CD (Fix Deployed) ``Add(ParticipantStatus)`` to the Case Actor.

    Calls ``trigger_activity_factory.add_participant_status_to_participant``
    with the status and participant IDs written to *result_out* by
    :class:`TransitionCStoFixDeployed` and queues the resulting activity ID
    via ``record_outbox_item``.

    Per ADR-0021 CLP-10-001: trigger trees MUST address fix-deployment
    activities to the Case Actor (CASE_MANAGER) so the CaseActor can commit
    a canonical ledger entry.

    Per AC-5 (issue #1825); mirrors ``EmitCFActivity`` from ``develop_fix.py``.
    """

    def __init__(
        self,
        case_id: str,
        actor_id: str,
        result_out: dict,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._actor_id = actor_id
        self._result_out = result_out

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        if (f := self._require_factory()) is not None:
            self.logger.warning(
                "%s: no TriggerActivityPort — cannot emit CD activity",
                self.name,
            )
            return f

        assert self.datalayer is not None
        assert self.trigger_activity_factory is not None

        status_id = self._result_out.get("status_id")
        participant_id = self._result_out.get("participant_id")
        if not status_id or not participant_id:
            self.feedback_message = (
                "status_id or participant_id missing from result_out"
                " — TransitionCStoFixDeployed must precede EmitCDActivity"
            )
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        case = self.datalayer.read(self._case_id)
        if not isinstance(case, VulnerabilityCase):
            self.logger.warning(
                "%s: case '%s' not found", self.name, self._case_id
            )
            return Status.FAILURE

        case_manager_id = resolve_case_manager_id(case, self.datalayer)
        if not case_manager_id:
            self.feedback_message = (
                f"No CASE_MANAGER found for case '{self._case_id}'"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        # When actor IS the case manager (single-actor scenario) to=None means
        # the activity is self-addressed; no external delivery needed.
        to = [case_manager_id] if case_manager_id != self._actor_id else None

        try:
            activity_id = self.trigger_activity_factory.add_participant_status_to_participant(
                status_id=status_id,
                participant_id=participant_id,
                actor=self._actor_id,
                to=to,
            )
            cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
                self._actor_id, activity_id
            )
            self.logger.info(
                "%s: CD activity '%s' emitted for actor '%s' in case '%s'",
                self.name,
                activity_id,
                self._actor_id,
                self._case_id,
            )
            return Status.SUCCESS
        except Exception as e:
            self.logger.error(
                "%s: Error emitting CD activity: %s", self.name, e
            )
            return Status.FAILURE


__all__ = [
    "CSinStateFixDeployed",
    "CheckCSFixNotYetDeployed",
    "RMinStateDeferred",
    "CheckNoNewDeploymentInfoNode",
    "TransitionCStoFixDeployed",
    "EmitCDActivity",
    "NEW_DEPLOYMENT_INFO_KEY",
]
