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

"""Participant verification condition nodes for status workflows.

Contains the sender-is-participant guard node used as step 1 of the
AddParticipantStatusToParticipant workflow (DEMOMA-07-003).
"""

import logging

from py_trees.common import Status

from vultron.core.behaviors.helpers import FindParticipantByActorIdNode

logger = logging.getLogger(__name__)


class VerifySenderIsParticipantNode(FindParticipantByActorIdNode):
    """Step 1: Verify the activity actor is a known case participant.

    Returns SUCCESS if the actor is registered in
    ``case.actor_participant_index``.  Returns FAILURE otherwise, halting
    the parent Sequence.

    If *case_id* is ``None`` the node falls back to a DataLayer lookup of
    *status_id* to derive the case context.

    Per DEMOMA-07-003 step 1.
    """

    def __init__(
        self,
        status_id: str,
        sender_actor_id: str,
        case_id: str | None,
        name: str | None = None,
    ):
        super().__init__(
            case_id=case_id or "",
            target_actor_id=sender_actor_id,
            participant_key="sender_participant",
            name=name or self.__class__.__name__,
        )
        self.status_id = status_id
        self.sender_actor_id = sender_actor_id
        self._case_id_hint = case_id

    def _resolve_case_id(self) -> str | None:
        if self._case_id_hint:
            return self._case_id_hint
        assert self.datalayer is not None
        status_raw = self.datalayer.read(self.status_id)
        if status_raw is None:
            return None
        context = getattr(status_raw, "context", None)
        return str(context) if context else None

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f

        case_id = self._resolve_case_id()
        if case_id is None:
            self.feedback_message = (
                f"Cannot determine case_id for status '{self.status_id}'"
            )
            self.logger.warning(
                "VerifySenderIsParticipant: %s", self.feedback_message
            )
            return Status.FAILURE

        self.case_id = case_id
        result = super().update()
        if result == Status.FAILURE:
            self.logger.warning(
                "VerifySenderIsParticipant: %s (DEMOMA-07-003 step 1)",
                self.feedback_message,
            )
            return Status.FAILURE

        self.logger.debug(
            "VerifySenderIsParticipant: actor '%s' is known in case '%s'"
            " (DEMOMA-07-003 step 1)",
            self.sender_actor_id,
            case_id,
        )
        return Status.SUCCESS
