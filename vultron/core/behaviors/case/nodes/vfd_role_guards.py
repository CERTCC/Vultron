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
#  Carnegie Mellon®, CERTⓇ and CERT Coordination CenterⓇ are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""VFD role-guard condition nodes for the add-participant-status trigger.

Nodes enforce CVD protocol correctness for received-side status authorization
(RSH-01-002):

- :class:`CheckVendorRoleNode` — gates vf→VF (vf_state=Vf): actor MUST hold
  ``CVDRole.VENDOR`` (CSB-15-001)
- :class:`CheckDeployerRoleNode` — gates d→D (vfd_state=VFD): actor MUST hold
  ``CVDRole.DEPLOYER`` (CSB-15-002; causal-gate enforcement pending #2593)
- :class:`CheckNotSoleObserverVfdNode` — gates v→V (vf_state=Vf): actor
  MUST NOT hold ``CVDRole.OBSERVER`` as their only role (CM-25-005)
- :class:`CheckIsCaseOwnerNode` — hard bypass in ``StatusAdoptionGate``:
  sender MUST hold ``CVDRole.CASE_OWNER`` (RSH-01-002)
- :class:`CheckOnBehalfAuthorizedNode` — on-behalf assertion gate:
  asserting actor MUST hold ``CVDRole.CASE_MANAGER`` or ``CVDRole.CASE_OWNER``
  (ADR-0084, PRM-06-003/004)
- :class:`EnsureOnBehalfParticipantExistsNode` — creates a minimal
  ``CaseParticipant`` for the target actor when absent from the case
  (ADR-0084, PRM-06-003/004)
"""

import logging

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.ports.case_persistence import CasePersistence
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)


def _resolve_actor_roles(
    datalayer: CasePersistence,
    case_id: str,
    actor_id: str,
    node_name: str,
) -> list[CVDRole] | None:
    """Return the CVDRole list for *actor_id* in *case_id*, or None on error.

    Returns ``None`` when the case or participant record cannot be resolved;
    the calling node should return ``Status.FAILURE`` in that case.
    """
    case = datalayer.read_case(case_id)
    if case is None:
        logger.warning("%s: case '%s' not found", node_name, case_id)
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


class CheckVendorRoleNode(DataLayerConditionWithPorts):
    """Gate vf→VF: actor MUST hold CVDRole.VENDOR.

    Returns ``SUCCESS`` when the executing actor holds ``CVDRole.VENDOR`` in
    their ``CaseParticipant.roles`` for the given case.  Returns ``FAILURE``
    otherwise, blocking the ``CreateParticipantStatusNode`` downstream from
    writing a ``VFd`` snapshot.

    Per CSB-15-001 (specs/cs-behavior.yaml).
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

        if CVDRole.VENDOR not in roles:
            self.feedback_message = (
                f"Actor '{self._actor_id}' does not hold CVDRole.VENDOR"
                f" — f→F (VFd) transition blocked (CSB-15-001)"
                f" (roles={roles!r})"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        self.logger.debug(
            "%s: actor '%s' holds CVDRole.VENDOR — f→F guard passed",
            self.name,
            self._actor_id,
        )
        return Status.SUCCESS


class CheckDeployerRoleNode(DataLayerConditionWithPorts):
    """Gate d→D: actor MUST hold CVDRole.DEPLOYER.

    Returns ``SUCCESS`` when the executing actor holds ``CVDRole.DEPLOYER`` in
    their ``CaseParticipant.roles`` for the given case.  A vendor-only actor
    (``CVDRole.VENDOR`` without ``CVDRole.DEPLOYER``) MUST stop at VFd; only
    actors explicitly responsible for deploying fixes may advance to VFD.

    Returns ``FAILURE`` for any actor lacking ``CVDRole.DEPLOYER``, blocking
    the ``CreateParticipantStatusNode`` downstream from writing a ``VFD``
    snapshot.

    Per CSB-15-002 (specs/cs-behavior.yaml).
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

        if CVDRole.DEPLOYER not in roles:
            self.feedback_message = (
                f"Actor '{self._actor_id}' does not hold CVDRole.DEPLOYER"
                f" — d→D (VFD) transition blocked (CSB-15-002)"
                f" (roles={roles!r})"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        self.logger.debug(
            "%s: actor '%s' holds CVDRole.DEPLOYER — d→D guard passed",
            self.name,
            self._actor_id,
        )
        return Status.SUCCESS


class CheckNotSoleObserverVfdNode(DataLayerConditionWithPorts):
    """Gate v→V (vf_state=Vf): actor MUST NOT hold OBSERVER as their only role.

    Returns ``FAILURE`` when the actor's ``case_roles`` list is exactly
    ``[CVDRole.OBSERVER]``, blocking the VFD vendor-awareness transition.
    A participant that also holds ``CVDRole.VENDOR`` or ``CVDRole.DEPLOYER``
    passes this check (CM-26-001 union-of-permissions rule).

    Uses the sole-role test ``case_roles == [CVDRole.OBSERVER]``, NOT
    the membership test ``CVDRole.OBSERVER in case_roles``, per CM-25-005.

    Per CM-25-005 (specs/case-management.yaml) and ADR-0057.
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

        if roles == [CVDRole.OBSERVER]:
            self.feedback_message = (
                f"Actor '{self._actor_id}' holds only CVDRole.OBSERVER"
                f" — v→V (Vfd) transition blocked (CM-25-005)"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        self.logger.debug(
            "%s: actor '%s' is not sole-OBSERVER — v→V guard passed",
            self.name,
            self._actor_id,
        )
        return Status.SUCCESS


class CheckIsCaseOwnerNode(DataLayerConditionWithPorts):
    """Check whether the *sender* actor is a CASE_OWNER participant.

    Used as the hard-bypass child of ``StatusAdoptionGate`` (RSH-01-002):
    a CASE_OWNER's status reports are authoritative ("gospel") and do not
    require approval by the CaseOwnerApprovesStatusUpdate call-out.

    Reads the case from the DataLayer, resolves the sender's participant
    record via ``actor_participant_index``, and returns ``SUCCESS`` only
    when that participant holds ``CVDRole.CASE_OWNER``.

    Returns ``FAILURE`` (proceed to the approval call-out) for any actor
    that is not a known CASE_OWNER, including unknown actors or those
    holding other roles (e.g. COORDINATOR, VENDOR).
    """

    def __init__(
        self,
        sender_actor_id: str,
        case_id: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._sender_actor_id = sender_actor_id
        self._case_id = case_id

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=False)
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id"}

    def initialise(self) -> None:
        super().initialise()
        self._case_id_bb = None
        try:
            self._case_id_bb = self.get_input("case_id")
        except (NoDataAvailable, NotImplementedError):
            pass

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case_id = self._case_id or self._case_id_bb

        if not case_id:
            self.logger.debug(
                "%s: no case_id available — cannot check CASE_OWNER role",
                self.name,
            )
            return Status.FAILURE

        case = self.datalayer.read_case(case_id)
        if case is None:
            self.logger.debug(
                "%s: case '%s' not found or wrong type", self.name, case_id
            )
            return Status.FAILURE

        participant_id = case.actor_participant_index.get(
            self._sender_actor_id
        )
        if participant_id is None:
            self.logger.debug(
                "%s: sender '%s' not in actor_participant_index for case '%s'",
                self.name,
                self._sender_actor_id,
                case_id,
            )
            return Status.FAILURE

        participant = self.datalayer.read(participant_id)
        if not isinstance(participant, CaseParticipant):
            return Status.FAILURE

        roles = participant.roles if hasattr(participant, "roles") else []
        if CVDRole.CASE_OWNER in roles:
            self.logger.debug(
                "%s: sender '%s' IS CASE_OWNER for case '%s'",
                self.name,
                self._sender_actor_id,
                case_id,
            )
            return Status.SUCCESS

        self.logger.debug(
            "%s: sender '%s' is NOT CASE_OWNER for case '%s' (roles=%s)",
            self.name,
            self._sender_actor_id,
            case_id,
            roles,
        )
        return Status.FAILURE


class CheckOnBehalfAuthorizedNode(DataLayerConditionWithPorts):
    """Gate on-behalf assertions: asserting actor MUST hold CASE_MANAGER or CASE_OWNER.

    Used as the first guard in the on-behalf status trigger tree (ADR-0084,
    PRM-06-003/004).  Returns ``SUCCESS`` when the actor holds either
    management role; ``FAILURE`` otherwise.
    """

    def __init__(
        self,
        case_id: str,
        asserting_actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._asserting_actor_id = asserting_actor_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        roles = _resolve_actor_roles(
            self.datalayer, self._case_id, self._asserting_actor_id, self.name
        )
        if roles is None:
            self.feedback_message = (
                f"Could not resolve roles for actor '{self._asserting_actor_id}'"
                f" in case '{self._case_id}'"
            )
            return Status.FAILURE

        authorized = {CVDRole.CASE_MANAGER, CVDRole.CASE_OWNER}
        if not authorized.intersection(roles):
            self.feedback_message = (
                f"Actor '{self._asserting_actor_id}' does not hold"
                f" CASE_MANAGER or CASE_OWNER in case '{self._case_id}'"
                f" — on-behalf assertion blocked (PRM-06-003, ADR-0084)"
                f" (roles={roles!r})"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        self.logger.debug(
            "%s: actor '%s' is authorized for on-behalf assertion (roles=%s)",
            self.name,
            self._asserting_actor_id,
            roles,
        )
        return Status.SUCCESS


class EnsureOnBehalfParticipantExistsNode(DataLayerActionWithPorts):
    """Ensure the target actor has a CaseParticipant; create one if absent.

    For on-behalf v→V (AC-1) and d→D (AC-2): the target (vendor or deployer)
    may not yet be a case participant.  This node looks up the target in
    ``actor_participant_index``; if absent, creates a minimal ``CaseParticipant``
    with ``required_role`` and attaches it to the case so that
    ``CreateParticipantStatusNode`` can append a status to it.

    Returns ``SUCCESS`` when the participant exists or was just created.
    Returns ``FAILURE`` if the case cannot be resolved.

    Per ADR-0084, PRM-06-003/004.
    """

    def __init__(
        self,
        case_id: str,
        target_actor_id: str,
        required_role: CVDRole,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._target_actor_id = target_actor_id
        self._required_role = required_role

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        dl = self.datalayer

        case = dl.read_case(self._case_id)
        if case is None:
            self.feedback_message = f"Case '{self._case_id}' not found"
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        if self._target_actor_id in case.actor_participant_index:
            self.logger.debug(
                "%s: target actor '%s' already has a participant in case '%s'",
                self.name,
                self._target_actor_id,
                self._case_id,
            )
            return Status.SUCCESS

        from vultron.core.behaviors.case.nodes.participant.common import (
            _create_and_attach_participant,
        )

        participant = CaseParticipant(
            attributed_to=self._target_actor_id,
            context=self._case_id,
            case_roles=[self._required_role],
        )
        updated_case = _create_and_attach_participant(
            dl,
            participant,
            self._case_id,
            self._target_actor_id,
            self.logger,
        )
        if updated_case is None:
            self.feedback_message = (
                f"Failed to create/attach participant for"
                f" '{self._target_actor_id}' in case '{self._case_id}'"
            )
            return Status.FAILURE

        dl.save(updated_case)
        self.logger.info(
            "%s: created on-behalf participant '%s' with role %s in case '%s'",
            self.name,
            self._target_actor_id,
            self._required_role,
            self._case_id,
        )
        return Status.SUCCESS
