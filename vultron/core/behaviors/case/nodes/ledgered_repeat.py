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

"""The repeat guard for a received activity the case ledger already records.

A guard that judges an activity against the case as it stands refuses a
repeat of one already applied: the state it checked has moved on (the
proposal is decided, the participant reinstated).  That would answer an
applied activity with a refusal notice, which CLP-05-006 forbids.  The
seen-before door finds most repeats from the receiver's record, but the
replay of a re-run held for a retry has its record released (ADR-0154), so
only the ledger shows that the activity was applied.

:class:`ActivityNotYetLedgeredNode` asks the ledger first, by the received
activity's id (ID-02-001, SYNC-21-018).
"""

from typing import cast

from py_trees.common import Status
from py_trees.ports import PortInformation

from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.behaviors.idempotency import SilentIdempotencyGuardMixin
from vultron.core.models.events.base import VultronEvent
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.sync_helpers import is_ledgered_activity

__all__ = ["ActivityNotYetLedgeredNode"]


class ActivityNotYetLedgeredNode(
    SilentIdempotencyGuardMixin, DataLayerConditionWithPorts
):
    """Guard: the case ledger does not already record the received activity.

    SUCCESS when no entry of *case_id*'s ledger names the received activity
    (``/activity``), found by its id as every repeat is (ID-02-001).
    FAILURE, read by the handler as ``SKIPPED``, when one does: the activity
    was applied, so nothing downstream runs, no refusal effect answers it,
    and no second entry is committed (CLP-13-001, CLP-05-006, HP-01-014).
    Read-only, so it runs among the precondition guards, ahead of the guards
    that judge the activity against the case.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        activity_id = cast(
            VultronEvent, self.get_input("activity")
        ).activity_id
        if not is_ledgered_activity(
            cast(CasePersistence, self.datalayer), self.case_id, activity_id
        ):
            return Status.SUCCESS
        self.feedback_message = (
            f"activity '{activity_id}' is already recorded in the ledger of"
            f" case '{self.case_id}' — repeat, nothing to apply (CLP-05-006)"
        )
        return self._idempotent_failure(
            self.logger, "%s: %s", self.name, self.feedback_message
        )
