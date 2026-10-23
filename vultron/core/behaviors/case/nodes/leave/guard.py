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

"""Refusing a Leave from a CASE_MANAGER that is not the Case Owner (CM-23-010)."""

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerCondition
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.predicates.addressing import participant_id_for_actor
from vultron.core.predicates.roles import has_case_owner_role
from vultron.primitives import same_actor_id


class CaseManagerLeavesOnlyAsCaseOwnerNode(DataLayerCondition):
    """Refuse a Leave whose sender is the case's CASE_MANAGER but not its Case Owner.

    The CASE_MANAGER's own ``RM.CLOSED`` status entry is the owner-close write
    boundary: it means the Case Owner has left and the case is fully closed
    (CM-23-010, CM-23-013, ADR-0152).  A Leave from a CASE_MANAGER that does
    not hold ``CASE_OWNER`` would close it as an ordinary leaver and so write
    that boundary while the Case Owner is still open.  This guard runs before
    the receipt commit, so the refused Leave writes nothing.  Every other
    sender passes: the Case Owner's Leave, holding CASE_MANAGER or not, and
    any other participant's.
    """

    def __init__(
        self, case_id: str, sender_actor_id: str, name: str | None = None
    ) -> None:
        """Create the guard.

        Args:
            case_id: The case the Leave names.
            sender_actor_id: The Leave's sender.
            name: Optional node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.sender_actor_id = sender_actor_id

    def update(self) -> Status:
        """SUCCESS unless the sender is the CASE_MANAGER and not the Case Owner."""
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure
        manager_id = resolve_case_manager_id(case, self.datalayer)
        if manager_id is None or not same_actor_id(
            manager_id, self.sender_actor_id
        ):
            return Status.SUCCESS
        participant_id = participant_id_for_actor(
            case.actor_participant_index, self.sender_actor_id
        )
        participant = (
            self.datalayer.read(participant_id)
            if participant_id is not None
            else None
        )
        if isinstance(participant, CaseParticipant) and has_case_owner_role(
            list(participant.roles) if participant.roles else []
        ):
            return Status.SUCCESS
        self.feedback_message = (
            f"The CASE_MANAGER '{self.sender_actor_id}' is not the Case Owner"
            f" of case '{self.case_id}', so it cannot leave it: its RM.CLOSED"
            " means the Case Owner has left — REFUSED (CM-23-010)"
        )
        self.logger.warning(
            "%s: %s (activity sender '%s')",
            self.name,
            self.feedback_message,
            self.sender_actor_id,
        )
        return Status.FAILURE
