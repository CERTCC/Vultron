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
"""Production-layer BT action nodes for the fix development workflow.

Two action nodes implement the ``DevelopFixBT`` creation sequence:

- :class:`TransitionCStoFixReady` — persist VF=VF ParticipantStatus snapshot
- :class:`EmitCFActivity` — emit CF (Fix Readiness) to Case Actor

The entry guard/condition nodes (``CheckIsVendorRoleNode``,
``CheckCSFixNotYetReady``) live in :mod:`develop_fix_conditions` and are
re-exported here for backward compatibility.

The tree's RM guard, ``CheckRMStateAccepted``, lives in ``conditions.py``
alongside the other RM-state condition nodes: three trees use it
(``DevelopFixBT``, ``DeployFixBT``, ``DeployMitigationBT``), so it is a
participant-RM condition rather than anything specific to developing a fix.

References
----------
- Issue: #1812
- Spec: ``specs/behavior-tree-integration.yaml`` BT-06-001
- ADR-0025: factory injection seam
"""

import logging
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from vultron.core.behaviors.case.nodes.participant.status import (
        CreateParticipantStatusNode,
    )

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.behaviors.case.nodes.participant.roles import (
    resolve_case_manager_id,
)
from vultron.core.behaviors.case.nodes.participant.common import (
    resolve_participant_state_from_dl,
)
from vultron.core.behaviors.report.nodes.develop_fix_conditions import (  # noqa: F401
    CheckCSFixNotYetReady,
    CheckIsVendorRoleNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.states.cs import CS_vf

logger = logging.getLogger(__name__)


class TransitionCStoFixReady(DataLayerActionWithPorts):
    """Persist a VF=VF ParticipantStatus snapshot for the actor in this case.

    Advances the actor's VF dimension to ``CS_vf.VF`` (fix ready) and
    persists the new ``ParticipantStatus`` record via the DataLayer, appending
    it to the ``CaseParticipant.participant_statuses`` list.

    Per AC-7 (issue #1812); follows the ``CreateParticipantStatusNode``
    pattern (``vultron/core/behaviors/case/nodes/participant/status.py``).
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

    def _make_status_node(
        self, vf_state: CS_vf | None, label: str
    ) -> "CreateParticipantStatusNode":
        from vultron.core.behaviors.case.nodes.participant.status import (
            CreateParticipantStatusNode,
        )

        assert self.datalayer is not None
        node = CreateParticipantStatusNode(
            case_id=self._case_id,
            actor_id=self._actor_id,
            rm_state=None,
            vf_state=vf_state,
            d_state=None,
            pxa_state=None,
            result_out=self._result_out,
            name=f"{self.name}.{label}",
        )
        node.datalayer = self.datalayer
        return node

    def _ensure_vendor_aware(self) -> Status:
        """Advance actor to VF=Vf if still at initial state (CSB-16-001 strict adjacency)."""
        assert self.datalayer is not None
        case = self.datalayer.read(self._case_id)
        if not isinstance(case, VulnerabilityCase):
            return Status.SUCCESS
        participant_id = case.actor_participant_index.get(self._actor_id)
        if participant_id is None:
            return Status.SUCCESS
        _, current_vf, _ = resolve_participant_state_from_dl(
            self.datalayer, participant_id
        )
        if current_vf not in (None, CS_vf.vf):
            return Status.SUCCESS
        try:
            return self._make_status_node(CS_vf.Vf, "_VendorAware").update()
        except Exception as e:
            self.logger.error("%s: Error advancing to VF=Vf: %s", self.name, e)
            return Status.FAILURE

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        if self._ensure_vendor_aware() != Status.SUCCESS:
            return Status.FAILURE

        node = self._make_status_node(CS_vf.VF, "_Create")
        try:
            status = node.update()
            if status == Status.SUCCESS:
                self.logger.debug(
                    "%s: VF → VF for actor '%s' in case '%s'",
                    self.name,
                    self._actor_id,
                    self._case_id,
                )
            return status
        except Exception as e:
            self.logger.error(
                "%s: Error transitioning to VF=VF: %s", self.name, e
            )
            return Status.FAILURE


class _EmitParticipantStatusActivityBase(DataLayerActionWithPorts):
    """Shared guard+factory-dispatch+outbox-write skeleton for
    ``Add(ParticipantStatus)`` trigger activities (BTND-07-005).

    Calls ``trigger_activity_factory.add_participant_status_to_participant``
    with the status and participant IDs written to *result_out* by
    :class:`TransitionCStoFixReady` and queues the resulting activity ID
    via ``outbox_append``.

    Subclasses provide only a constructor docstring; all protocol logic
    lives here.  The ``result_out`` dict must be populated by the preceding
    ``TransitionCStoFix*`` node (keys: ``status_id``, ``participant_id``).

    Per ADR-0021 CLP-10-001: trigger trees MUST address fix-readiness
    activities to the Case Actor (CASE_MANAGER) so the CaseActor can
    commit a canonical ledger entry.

    Per AC-7 (issue #1812).
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
                "%s: no TriggerActivityPort — cannot emit participant-status activity",
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
                f" — a TransitionCS node must precede {self.__class__.__name__}"
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
            cast(CaseOutboxPersistence, self.datalayer).outbox_append(
                activity_id
            )
            self.logger.info(
                "Actor '%s' emitted %s for case '%s'",
                self._actor_id,
                self.__class__.__name__,
                self._case_id,
            )
            return Status.SUCCESS
        except Exception as e:
            self.logger.error(
                "%s: Error emitting participant-status activity: %s",
                self.name,
                e,
            )
            return Status.FAILURE


class EmitCFActivity(_EmitParticipantStatusActivityBase):
    """Emit a CF (Fix Readiness) ``Add(ParticipantStatus)`` to the Case Actor.

    Calls ``trigger_activity_factory.add_participant_status_to_participant``
    with the status and participant IDs written to *result_out* by
    :class:`TransitionCStoFixReady` and queues the resulting activity ID
    via ``record_outbox_item``.

    Per ADR-0021 CLP-10-001: trigger trees MUST address fix-readiness
    activities to the Case Actor (CASE_MANAGER) so the CaseActor can
    commit a canonical ledger entry.

    Per AC-7 (issue #1812).
    """


__all__ = [
    "_EmitParticipantStatusActivityBase",
    "CheckIsVendorRoleNode",
    "CheckCSFixNotYetReady",
    "TransitionCStoFixReady",
    "EmitCFActivity",
]
