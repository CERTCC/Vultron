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

"""Nodes that keep what a received case snapshot carries (EMB-18-003, CBT-05-005).

A ``VulnerabilityCase`` that arrives on a ``Create`` or an ``Engage`` is a
remote point-in-time view that carries the participants and the embargo it
names inline.  Two steps make it usable on the receiver:

- hold the embargo the case names, and refuse a case naming one this store
  cannot read (:class:`HoldCarriedEmbargoNode`);
- store each inline participant as its own record so later nodes can find it by
  id (:class:`StoreEmbeddedParticipantsNode`).

Both delegate to the neutral helpers in ``vultron/core/services/``, which the
announce seed shares (BT-22-005), so there is one implementation of each.
"""

from typing import Any

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.services.carried_embargo import store_carried_embargo
from vultron.core.services.case_replica_seeding import (
    store_embedded_participants,
)
from vultron.errors import VultronNotFoundError, VultronValidationError


class HoldCarriedEmbargoNode(DataLayerActionWithPorts):
    """Hold the ``EmbargoEvent`` the received case names, before it is saved.

    ``FAILURE`` when the case names an embargo this store cannot read, with
    nothing saved (EMB-18-003); a tree places it ahead of any node that saves
    the case.
    """

    def __init__(
        self, case_obj: Any, case_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_obj = case_obj
        self.case_id = case_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        try:
            store_carried_embargo(self.case_obj, self.datalayer)
        except (VultronNotFoundError, VultronValidationError) as exc:
            self.feedback_message = (
                f"case '{self.case_id}' names an active embargo this store"
                f" cannot read (EMB-18-003): {exc}"
            )
            self.logger.warning(
                "%s: refusing received case: %s",
                self.name,
                self.feedback_message,
            )
            return Status.FAILURE
        return Status.SUCCESS


class StoreEmbeddedParticipantsNode(DataLayerActionWithPorts):
    """Store the participants a received case snapshot carries inline.

    Idempotent, and never regresses local RM progress
    (:func:`~vultron.core.services.case_replica_seeding.store_embedded_participants`).
    Always ``SUCCESS`` once the DataLayer is available.
    """

    def __init__(
        self, case_obj: Any, case_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_obj = case_obj
        self.case_id = case_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        store_embedded_participants(
            self.case_obj, self.datalayer, self.case_id
        )
        return Status.SUCCESS
