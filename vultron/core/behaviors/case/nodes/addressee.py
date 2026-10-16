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

"""The addressee door guard of a received tree (HP-01-005, CLP-10-010).

A receiver acts on an activity only when it sent it or is named in its
``to``.  Any other store holds a misaddressed copy: it refuses it, commits
nothing, changes no state and answers nothing, and its refusal names the
receiver and the recipients the sender chose, so the misrouting can be traced
(HP-01-005, ADR-0118, #4132).  ``cc``, ``bto`` and ``bcc`` address no Vultron
recipient and are never read (OX-08-001, ADR-0109).

:class:`ActivityAddressedToReceiverNode` is that check.
:func:`~vultron.core.behaviors.case.receive_activity_tree.create_receive_activity_tree`
places it between the post-close boundary and the sender guard when a tree
passes ``addressee_check`` (CLP-10-010), so intake has already archived the
copy (CLP-10-018) and nothing after the guard runs.
"""

from py_trees.common import Status
from py_trees.ports import PortInformation

from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.predicates.addressing import is_addressed_to, same_actor_id

__all__ = ["ActivityAddressedToReceiverNode", "unaddressed_copy_reason"]


def unaddressed_copy_reason(
    receiving_actor_id: str, event: object, *, label: str
) -> str | None:
    """Why *event* is an unaddressed copy at *receiving_actor_id*, or ``None``.

    ``None`` when the receiver sent the activity or is named in its ``to``
    (matched by :func:`~vultron.core.predicates.addressing.is_addressed_to`,
    so a trailing slash still names the actor).  An event without an
    activity names no recipient at all.

    Args:
        receiving_actor_id: The actor whose store received the copy.
        event: The received event on the blackboard.
        label: Names the activity in the reason, e.g.
            ``"Accept(Invite(EmbargoEvent))"``.
    """
    sender_id = getattr(event, "actor_id", None)
    activity = getattr(event, "activity", None)
    to = list(getattr(activity, "to", None) or []) if activity else []
    if isinstance(sender_id, str) and same_actor_id(
        receiving_actor_id, sender_id
    ):
        return None
    if activity is not None and is_addressed_to(receiving_actor_id, to):
        return None
    return (
        f"'{receiving_actor_id}' is neither the sender nor a recipient of"
        f" {label} '{getattr(event, 'activity_id', None)}' (to={to}); an"
        " unaddressed copy is refused (HP-01-005)"
    )


class ActivityAddressedToReceiverNode(DataLayerConditionWithPorts):
    """Door guard: the executing actor sent the activity or is in its ``to``.

    Returns:
        SUCCESS when the executing actor is the activity's sender or one of
        its ``to`` recipients.

        FAILURE otherwise, with a reason naming the receiver, the activity
        and its ``to`` (HP-01-005), logged at WARNING.  An event with no
        activity names no recipient, so it is refused too.

    Reads only the blackboard; it never touches the store.
    """

    def __init__(self, label: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.label = label
        self._activity: object | None = None

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def initialise(self) -> None:
        super().initialise()
        self._activity = self._try_get_input("activity")

    def update(self) -> Status:
        if self.actor_id is None:
            self.feedback_message = (
                f"no executing actor to check {self.label} against"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        reason = unaddressed_copy_reason(
            self.actor_id, self._activity, label=self.label
        )
        if reason is None:
            return Status.SUCCESS
        self.feedback_message = reason
        self.logger.warning(
            "%s: refused '%s' (actor '%s'): %s",
            self.label,
            getattr(self._activity, "activity_id", None),
            getattr(self._activity, "actor_id", None),
            reason,
        )
        return Status.FAILURE
