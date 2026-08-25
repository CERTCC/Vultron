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
"""Production-layer BT nodes for the fix development workflow.

Five nodes implement the ``DevelopFixBT`` guard/action logic:

- :class:`CheckIsVendorRoleNode` — short-circuit: actor is not a vendor
- :class:`CheckCSFixNotYetReady` — short-circuit: fix already ready
- :class:`CheckRMStateAccepted` — guard: actor RM must be ACCEPTED
- :class:`TransitionCStoFixReady` — persist VFD VFd snapshot
- :class:`EmitCFActivity` — emit CF (Fix Readiness) to Case Actor

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

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
)
from vultron.core.behaviors.case.nodes.participant.common import (
    resolve_case_manager_id,
    resolve_participant_state_from_dl,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import VfdDimension
from vultron.core.ports.case_persistence import (
    CasePersistence,
    CaseOutboxPersistence,
)
from vultron.core.states.cs import CS_vfd
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)


def _resolve_actor_roles(
    datalayer: "CasePersistence",
    case_id: str,
    actor_id: str,
    node_name: str,
) -> list[CVDRole] | None:
    """Return CVDRole list for *actor_id* in *case_id*, or None on error."""
    case = datalayer.read(case_id)
    if not isinstance(case, VulnerabilityCase):
        logger.warning(
            "%s: case '%s' not found or wrong type", node_name, case_id
        )
        return None

    participant_id = case.actor_participant_index.get(actor_id)
    if participant_id is None:
        logger.warning(
            "%s: actor '%s' not in case '%s'", node_name, actor_id, case_id
        )
        return None

    participant = datalayer.read(participant_id)
    if not isinstance(participant, CaseParticipant):
        logger.warning(
            "%s: participant '%s' not found or wrong type",
            node_name,
            participant_id,
        )
        return None

    return list(participant.roles) if participant.roles else []


class CheckIsVendorRoleNode(DataLayerConditionWithPorts):
    """Gate: actor MUST hold CVDRole.VENDOR to proceed with fix development.

    Returns ``SUCCESS`` when the actor holds ``CVDRole.VENDOR`` — allowing
    the fix-development workflow to continue.  Returns ``FAILURE`` for any
    non-vendor actor so the Fallback short-circuits and reports SUCCESS to
    the parent (non-vendors are excused from fix development).

    Note: in the DevelopFixBT Fallback, SUCCESS here means "not a vendor,
    skip fix development". FAILURE here means "is a vendor, proceed to inner
    Sequence".  The semantics are those of a short-circuit guard:
    non-vendors succeed early; vendors fall through to the creation sequence.

    Per AC-7 (issue #1812).
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

        roles = _resolve_actor_roles(
            self.datalayer, self._case_id, self._actor_id, self.name
        )
        if roles is None:
            self.feedback_message = (
                f"Could not resolve roles for actor '{self._actor_id}'"
                f" in case '{self._case_id}'"
            )
            return Status.FAILURE

        if CVDRole.VENDOR in roles:
            self.logger.debug(
                "%s: actor '%s' is a vendor — proceed to fix development",
                self.name,
                self._actor_id,
            )
            return Status.FAILURE

        self.logger.debug(
            "%s: actor '%s' is not a vendor — short-circuit SUCCESS",
            self.name,
            self._actor_id,
        )
        return Status.SUCCESS


class CheckCSFixNotYetReady(DataLayerConditionWithPorts):
    """Short-circuit guard: fix already ready means nothing to do.

    Returns ``SUCCESS`` when the actor's VFD state is already fix-ready
    (``CS_vfd.VFd`` or ``CS_vfd.VFD``) — the Fallback short-circuits and
    reports SUCCESS to the parent.  Returns ``FAILURE`` when fix is NOT yet
    ready, allowing the inner Sequence to proceed.

    Per AC-7 (issue #1812).
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

        _, vfd_state = resolve_participant_state_from_dl(
            self.datalayer, participant_id
        )

        is_ready = VfdDimension(state=vfd_state).is_fix_ready()
        if is_ready:
            self.logger.debug(
                "%s: VFD state=%s is fix-ready — short-circuit SUCCESS",
                self.name,
                vfd_state,
            )
            return Status.SUCCESS

        self.logger.debug(
            "%s: VFD state=%s is not fix-ready — proceed to creation",
            self.name,
            vfd_state,
        )
        return Status.FAILURE


class CheckRMStateAccepted(DataLayerConditionWithPorts):
    """Guard: actor RM state must be ACCEPTED to create a fix.

    Returns ``SUCCESS`` when the actor's latest RM state is ``RM.ACCEPTED``.
    Returns ``FAILURE`` otherwise, blocking the fix-creation action nodes.

    Per AC-7 (issue #1812).
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

        if rm_state == RM.ACCEPTED:
            self.logger.debug(
                "%s: RM state is ACCEPTED for actor '%s'",
                self.name,
                self._actor_id,
            )
            return Status.SUCCESS

        self.feedback_message = (
            f"Actor '{self._actor_id}' RM state is {rm_state!r},"
            f" expected RM.ACCEPTED"
        )
        self.logger.debug("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


class TransitionCStoFixReady(DataLayerActionWithPorts):
    """Persist a VFd ParticipantStatus snapshot for the actor in this case.

    Advances the actor's VFD dimension to ``CS_vfd.VFd`` (fix developed) and
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
        self, vfd_state: CS_vfd, label: str
    ) -> "CreateParticipantStatusNode":
        from vultron.core.behaviors.case.nodes.participant.status import (
            CreateParticipantStatusNode,
        )

        assert self.datalayer is not None
        node = CreateParticipantStatusNode(
            case_id=self._case_id,
            actor_id=self._actor_id,
            rm_state=None,
            vfd_state=vfd_state,
            pxa_state=None,
            result_out=self._result_out,
            name=f"{self.name}.{label}",
        )
        node.datalayer = self.datalayer
        return node

    def _ensure_vendor_aware(self) -> Status:
        """Advance actor to Vfd if still at vfd (CSB-16-001 strict adjacency)."""
        assert self.datalayer is not None
        case = self.datalayer.read(self._case_id)
        if not isinstance(case, VulnerabilityCase):
            return Status.SUCCESS
        participant_id = case.actor_participant_index.get(self._actor_id)
        if participant_id is None:
            return Status.SUCCESS
        _, current_vfd = resolve_participant_state_from_dl(
            self.datalayer, participant_id
        )
        if current_vfd != CS_vfd.vfd:
            return Status.SUCCESS
        try:
            return self._make_status_node(CS_vfd.Vfd, "_VendorAware").update()
        except Exception as e:
            self.logger.error("%s: Error advancing to Vfd: %s", self.name, e)
            return Status.FAILURE

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        if self._ensure_vendor_aware() != Status.SUCCESS:
            return Status.FAILURE

        node = self._make_status_node(CS_vfd.VFd, "_Create")
        try:
            status = node.update()
            if status == Status.SUCCESS:
                # The narrative INFO line (SL-04-006) is emitted by
                # CreateParticipantStatusNode, which knows the before-state.
                self.logger.debug(
                    "%s: VFD → VFd for actor '%s' in case '%s'",
                    self.name,
                    self._actor_id,
                    self._case_id,
                )
            return status
        except Exception as e:
            self.logger.error(
                "%s: Error transitioning to VFd: %s", self.name, e
            )
            return Status.FAILURE


class EmitCFActivity(DataLayerActionWithPorts):
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
                "%s: no TriggerActivityPort — cannot emit CF activity",
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
                " — TransitionCStoFixReady must precede EmitCFActivity"
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
                "%s: CF activity '%s' emitted for actor '%s' in case '%s'",
                self.name,
                activity_id,
                self._actor_id,
                self._case_id,
            )
            return Status.SUCCESS
        except Exception as e:
            self.logger.error(
                "%s: Error emitting CF activity: %s", self.name, e
            )
            return Status.FAILURE


__all__ = [
    "CheckIsVendorRoleNode",
    "CheckCSFixNotYetReady",
    "CheckRMStateAccepted",
    "TransitionCStoFixReady",
    "EmitCFActivity",
]
