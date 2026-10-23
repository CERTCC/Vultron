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

"""Guard: the object an ``Add`` carries belongs to the case it targets."""

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.models._helpers import _as_id


class CarriedObjectInTargetCaseNode(DataLayerConditionWithPorts):
    """Guard: the object an ``Add`` attaches names the ``Add``'s case.

    An ``Add(Note)`` or ``Add(CaseStatus)`` attaches an object whose own
    ``context`` names the case it belongs to.  One whose ``context`` is
    another case, or names none, is refused before the commit, so the
    target case never gains another case's object and no entry carries
    that object to the target case's participants (HP-08-007, #4831).
    An ``Add(ParticipantStatus)`` uses it with the target participant's
    own case (HP-08-008, #4961).

    The object checked is the one the tree goes on to attach: the record
    stored under *object_id* when the store holds one, else the carried
    copy.  The inbox's routing rebuild already prefers a stored record
    (IO-03-004), so this guard reads the same object on every path.
    Read-only, so it runs before the guarded commit (CLP-10-006).
    """

    def __init__(
        self,
        object_id: str,
        carried: object,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.object_id = object_id
        self.carried = carried
        self.case_id = case_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        attached = self.datalayer.read(self.object_id) or self.carried
        context = _as_id(getattr(attached, "context", None))
        if context == self.case_id:
            return Status.SUCCESS
        self.feedback_message = (
            f"'{self.object_id}' belongs to case '{context}', not the"
            f" target case '{self.case_id}' — REFUSED (HP-08-007)"
            if context
            else f"'{self.object_id}' names no case; it cannot be attached"
            f" to case '{self.case_id}' — REFUSED (HP-08-007)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


__all__ = ["CarriedObjectInTargetCaseNode"]
