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
"""

import logging

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.helpers import (
    DataLayerConditionWithPorts,
)
from vultron.core.models.case import VulnerabilityCase
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

        case = self.datalayer.read(case_id)
        if not isinstance(case, VulnerabilityCase):
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
