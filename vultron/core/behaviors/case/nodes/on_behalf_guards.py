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
- :class:`CheckOnBehalfTargetIsParticipantNode` — the target actor MUST
  already be a participant holding the asserted dimension's role; an
  on-behalf assertion never creates a participant (ADR-0084, PRM-06-006)
"""

import logging

from py_trees.common import Status

from vultron.core.behaviors.case.nodes.vfd_role_guards import (
    _resolve_actor_roles,
)
from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
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


class CheckOnBehalfTargetIsParticipantNode(DataLayerConditionWithPorts):
    """Gate on-behalf assertions: the target MUST already be a participant.

    An on-behalf ``v→V`` or ``d→D`` records a status *about* an existing
    participant; it is never a way into a case (PRM-06-006, ADR-0084,
    ADR-0114).  Joining is the Invite flow.  This node is a pure read: it
    writes nothing, so it can sit ahead of every write in the on-behalf tree.

    Returns ``FAILURE`` naming the target when either:

    - the target is not in ``case.actor_participant_index`` (PRM-06-006), or
    - the target's participant does not hold every role in
      ``required_roles`` — ``VENDOR`` for ``v→V`` (PRM-06-003),
      ``DEPLOYER`` for ``d→D`` (PRM-06-004).  Every missing role is named
      (EH-07-001).

    Returns ``SUCCESS`` otherwise.
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

    def _refuse(self, message: str) -> Status:
        self.feedback_message = message
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1: case must exist (ADR-0087)

        participant_id = case.actor_participant_index.get(
            self._target_actor_id
        )
        if participant_id is None:
            return self._refuse(
                f"On-behalf target '{self._target_actor_id}' is not a"
                f" participant in case '{self._case_id}' — an on-behalf"
                f" status assertion never creates a participant; invite the"
                f" actor to the case first (PRM-06-006, ADR-0084)"
            )

        participant = self.datalayer.read(participant_id)
        if not isinstance(participant, CaseParticipant):
            return self._refuse(
                f"On-behalf target '{self._target_actor_id}' is indexed in"
                f" case '{self._case_id}' but its participant record"
                f" '{participant_id}' could not be read"
            )

        missing = [
            r for r in self._required_roles if not participant.has_role(r)
        ]
        if missing:
            return self._refuse(
                f"On-behalf target '{self._target_actor_id}' in case"
                f" '{self._case_id}' does not hold"
                f" {', '.join(str(r) for r in missing)}"
                f" — on-behalf assertion blocked (PRM-06-003, PRM-06-004)"
                f" (roles={[str(r) for r in participant.roles]!r})"
            )

        self.logger.debug(
            "%s: on-behalf target '%s' is a participant in case '%s'",
            self.name,
            self._target_actor_id,
            self._case_id,
        )
        return Status.SUCCESS
