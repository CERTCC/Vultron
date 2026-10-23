"""Per-semantic inbound domain event type for ProcessingFault activities.

Covers the receiver-side Create(ProcessingFault) notification flow
defined in ADR-0080, ASK-07-001.
"""

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

from typing import Literal

from pydantic import model_validator

from vultron.core.models.activity import VultronActivity
from vultron.core.models.enums import VultronObjectType
from vultron.core.models.events.base import MessageSemantics, VultronEvent


class CreateProcessingFaultReceivedEvent(VultronEvent):
    """Sender received a Create(ProcessingFault) NACK from a receiver.

    Indicates the receiver could not process the sender's status assertion
    (ADR-0080, ASK-07-001).  ``object_`` contains a minimal ``CoreObject``
    wrapping the ``as_ProcessingFault``; the ``in_reply_to`` field on that
    object points to the failed activity URI (ASK-07-004).
    """

    semantic_type: Literal[MessageSemantics.CREATE_PROCESSING_FAULT] = (
        MessageSemantics.CREATE_PROCESSING_FAULT
    )

    @property
    def fault_id(self) -> str | None:
        return self.object_id


class RefusalNoticeReceivedEvent(VultronEvent):
    """A participant received a ``Reject`` of an activity it sent.

    The CASE_MANAGER's refusal notice (CLP-05-001, ADR-0141): the refused
    activity is inline in ``object_``, ``inReplyTo`` names it and
    ``summary`` carries the refusing guard's reason.  Every ``Reject`` of an
    inline activity other than an ``Invite`` or an ``Offer`` arrives as this
    event, including the CASE_MANAGER's decline of a ``Leave`` (CM-23-011).
    """

    semantic_type: Literal[MessageSemantics.REFUSAL_NOTICE] = (
        MessageSemantics.REFUSAL_NOTICE
    )
    activity: VultronActivity  # pyright: ignore[reportGeneralTypeIssues]

    @model_validator(mode="after")
    def _names_the_refused_activity(self) -> "RefusalNoticeReceivedEvent":
        if self.in_reply_to is None and self.object_id is None:
            raise ValueError(
                f"refusal notice '{self.activity_id}' names no refused"
                " activity: no inReplyTo and no object id (CLP-05-001)"
            )
        return self

    @property
    def refused_activity_id(self) -> str:
        """The refused activity: the one ``inReplyTo`` names, else the object.

        Never ``None``: an event naming neither is refused at construction.
        """
        refused = self.in_reply_to or self.object_id
        assert refused is not None
        return refused

    @property
    def case_id(self) -> str | None:
        """The case the notice concerns.

        The notice's own ``context``, else the refused activity's, else the
        case the refused activity acts on directly (a ``Leave`` of the case).
        """
        if self.context_id is not None:
            return self.context_id
        if self.inner_context_id is not None:
            return self.inner_context_id
        if self.inner_object_type == VultronObjectType.VULNERABILITY_CASE:
            return self.inner_object_id
        return None

    @property
    def reason(self) -> str | None:
        """The refusing guard's reason, as the notice's ``summary`` gives it."""
        return self.activity.summary
