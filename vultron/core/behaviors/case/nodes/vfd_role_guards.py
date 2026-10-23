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
- :class:`CheckDeployerRoleNode` — gates d→D (d_state=D): actor MUST hold
  ``CVDRole.DEPLOYER`` (CSB-15-002)
- :class:`CheckSomeVendorAtVFNode` — causal gate for DEPLOYER-only d→D: at
  least one ``CVDRole.VENDOR`` participant in the case MUST have
  ``vf.state=VF`` (fix-ready) before a deployer may advance d→D (CSB-15-004)
- :class:`CheckNotSoleObserverVfdNode` — gates v→V (vf_state=Vf): actor
  MUST NOT hold ``CVDRole.OBSERVER`` as their only role (CM-25-005)

Note: ``CheckIsCaseOwnerNode`` has been consolidated into
``SenderIsCaseOwnerNode`` in
``vultron.core.behaviors.sender_entitlement`` (ADR-0115, AC-2).

On-behalf assertion guards (ADR-0121) live in :mod:`on_behalf_guards` and are
re-exported here for backward compatibility.
"""

import logging

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerConditionWithPorts,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.participants._lookup import iter_case_participants
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.predicates.participants import some_vendor_at_vf
from vultron.core.predicates.roles import (
    has_deployer_role,
    has_vendor_role,
    is_sole_observer,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronNotFoundError

logger = logging.getLogger(__name__)


class ActorNotInCaseError(VultronNotFoundError):
    """The actor has no entry in ``case.actor_participant_index``."""

    def __init__(self, case_id: str, actor_id: str) -> None:
        super().__init__("Participant for actor", actor_id)
        self.case_id = case_id


class ParticipantRecordUnreadableError(VultronNotFoundError):
    """The index names a participant record that is missing or mistyped."""

    def __init__(self, participant_id: str, actor_id: str) -> None:
        super().__init__("CaseParticipant", participant_id)
        self.actor_id = actor_id


def _read_indexed_participant(
    datalayer: CasePersistence,
    case: VulnerabilityCase,
    actor_id: str,
) -> CaseParticipant:
    """Return *actor_id*'s participant in *case* via the roster index.

    Raises :class:`ActorNotInCaseError` when the actor is not indexed, and
    :class:`ParticipantRecordUnreadableError` when the indexed record is
    missing or not a :class:`CaseParticipant` (BT-HELPER-01: raise, never
    return ``None``).  The two are distinct so a caller can tell a policy
    outcome (not a participant) from a broken store.
    """
    participant_id = case.actor_participant_index.get(actor_id)
    if participant_id is None:
        raise ActorNotInCaseError(case.id_, actor_id)
    participant = datalayer.read(participant_id)
    if not isinstance(participant, CaseParticipant):
        raise ParticipantRecordUnreadableError(participant_id, actor_id)
    return participant


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
    # Regime 1 (ADR-0087): module-level resolver (bare `datalayer`, not a node)
    # shared by several role guards — a missing case is logged and returned as
    # None so each calling node fails. Conformance allowlist: module-resolver
    # category (the node cannot pass `self` to _require_case from here).
    case = datalayer.read_case(case_id)
    if case is None:
        logger.warning("%s: case '%s' not found", node_name, case_id)
        return None

    try:
        participant = _read_indexed_participant(datalayer, case, actor_id)
    except ActorNotInCaseError:
        logger.warning(
            "%s: actor '%s' not in case '%s'", node_name, actor_id, case_id
        )
        return None
    except ParticipantRecordUnreadableError as exc:
        logger.warning(
            "%s: participant '%s' not found or wrong type",
            node_name,
            exc.resource_id,
        )
        return None

    return list(participant.roles) if participant.roles else []


def _collect_all_participants(
    case: VulnerabilityCase,
    datalayer: CasePersistence,
) -> list[CaseParticipant]:
    """Return all CaseParticipants reachable from *case*, deduped.

    Delegates to :func:`~vultron.core.participants._lookup.iter_case_participants`
    for the canonical two-phase scan (issue #3218/#3220).
    """
    return list(iter_case_participants(case, datalayer))


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

        if not has_vendor_role(roles):
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

        if not has_deployer_role(roles):
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


class CheckSomeVendorAtVFNode(DataLayerConditionWithPorts):
    """Causal gate for DEPLOYER-only d→D: at least one VENDOR must be at VF.

    Returns ``SUCCESS`` when at least one ``CVDRole.VENDOR`` participant in the
    case has ``vf.state=CS_vf.VF`` (fix-ready).  Returns ``FAILURE`` when no
    vendor has produced a fix, blocking the deployer from recording fix
    deployment before a fix exists.

    Delegates to the pure predicate
    :func:`~vultron.core.predicates.participants.some_vendor_at_vf` after
    reading all case participants from the DataLayer.

    Per CSB-15-004 (specs/cs-behavior.yaml).
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

        case, failure = self._require_case(
            self._case_id
        )  # Regime 1: causal gate requires the case (ADR-0087)
        if failure is not None:
            return failure

        participants = _collect_all_participants(case, self.datalayer)
        if not some_vendor_at_vf(participants):
            self.feedback_message = (
                f"No VENDOR participant in case '{self._case_id}' has"
                f" vf.state=VF — d→D causal gate blocked (CSB-15-004)"
                f" for actor '{self._actor_id}'"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        self.logger.debug(
            "%s: causal gate passed — some VENDOR is at VF in case '%s'",
            self.name,
            self._case_id,
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

        if is_sole_observer(roles):
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
