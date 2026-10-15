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

"""The guard for an act from a sender whose closure the case records.

A participant whose closure the case records (RM ``CLOSED``) may act on
nothing further (CM-23-018), except that a repeat of an act that would close
it again, a ``Leave(VulnerabilityCase)``, a ``Close(Report)`` or a ``Reject``
of its Invite, is a no-op: its effect is already in place.  Such a repeat is
reported ``SKIPPED``, with no ledger entry and nothing sent, whatever its
activity id (ID-05-003).

Any other act from that sender is refused.  Provides
:class:`SenderClosureNotRecordedNode`, run as a preflight by the handlers of
those acts and of an invitee's replies before their received tree
(:func:`vultron.core.use_cases.received._sender_preflight.closed_sender_preflight`).
"""

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.models.case import VulnerabilityCase
from vultron.core.participants.recipients import closure_recorded


class SenderClosureNotRecordedNode(DataLayerConditionWithPorts):
    """Guard: the case does not record the sender's closure.

    SUCCESS when the sender is not at RM ``CLOSED`` here, or when this store
    holds no such case: the act is not a repeat, and the received tree
    decides what it means.

    FAILURE with :attr:`sender_closed` set when the case records the
    sender's closure (CM-23-018).  The handler reports an act that would
    close it again as ``SKIPPED`` (ID-05-003), and any other act as
    ``REFUSED``.

    Keyed on the sender's recorded RM state, never on the activity id, which
    a repeat sent under a new id does not share.  Read-only.
    """

    def __init__(
        self, case_id: str, sender_actor_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.sender_actor_id = sender_actor_id
        self.sender_closed = False
        """``True`` when the last run found the sender's closure recorded."""

    def update(self) -> Status:
        self.sender_closed = False
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case = self.datalayer.read(self.case_id)
        if not isinstance(case, VulnerabilityCase) or not closure_recorded(
            case, self.datalayer, self.sender_actor_id
        ):
            return Status.SUCCESS
        self.sender_closed = True
        self.feedback_message = (
            f"'{self.sender_actor_id}' is already closed on case"
            f" '{self.case_id}' (CM-23-018)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE
