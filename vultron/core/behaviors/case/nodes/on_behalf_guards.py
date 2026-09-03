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

"""On-behalf assertion guard nodes for the add-on-behalf-status trigger.

Implements the narrow externally-evidenced on-behalf exceptions from ADR-0084:

- :class:`CheckOnBehalfAuthorizedNode` — on-behalf assertion gate:
  asserting actor MUST hold ``CVDRole.CASE_MANAGER`` or ``CVDRole.CASE_OWNER``
  (ADR-0084, PRM-06-003/004)
- :class:`EnsureOnBehalfParticipantExistsNode` — creates a minimal
  ``CaseParticipant`` for the target actor when absent from the case
  (ADR-0084, PRM-06-003/004)
"""

import logging

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
)
from vultron.core.behaviors.case.nodes.participant.common import (
    _create_and_attach_participant,
)
from vultron.core.behaviors.case.nodes.vfd_role_guards import (
    _resolve_actor_roles,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)


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
    with ``required_roles`` and attaches it to the case so that
    ``CreateParticipantStatusNode`` can append a status to it.

    When both ``vf_state`` and ``d_state`` are requested on the same actor
    (e.g. a combined vendor-deployer), pass both roles so the single new
    ``CaseParticipant`` satisfies both the VF and D precondition checks.

    Returns ``SUCCESS`` when the participant exists or was just created.
    Returns ``FAILURE`` if the case cannot be resolved.

    Per ADR-0084, PRM-06-003/004.
    """

    def __init__(
        self,
        case_id: str,
        target_actor_id: str,
        required_roles: list[CVDRole],
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._target_actor_id = target_actor_id
        self._required_roles = required_roles

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

        participant = CaseParticipant(
            attributed_to=self._target_actor_id,
            context=self._case_id,
            case_roles=self._required_roles,
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
            "%s: created on-behalf participant '%s' with roles %s in case '%s'",
            self.name,
            self._target_actor_id,
            self._required_roles,
            self._case_id,
        )
        return Status.SUCCESS
