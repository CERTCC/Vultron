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

"""Finish the embargo acts a failed commit left part-way (CLP-07-015).

An embargo act stores the entries it owes before its first commit
(:func:`~vultron.core.behaviors.embargo.copy_commit.commit_and_apply_embargo_entries`).
:class:`FinishOwedEmbargoEntriesNode` runs first in every CASE_MANAGER
embargo tree for the case, received and trigger alike, before any guard
reads a consent row (ADR-0146).  It is the first case-wide clock decision
(:func:`~vultron.core.behaviors.case.case_clock_decisions.case_clock_decisions`),
ahead of the end-time check, whose termination would freeze the rows an act
still owes; an embargo trigger that opts out of the case-wide decisions takes
it on its own (``SvcEmbargoTriggerBase``).  Either way it runs inside the
CASE_MANAGER gate, so a replica, which stores no plan, never runs it.
"""

from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.embargo.copy_commit import (
    finish_owed_embargo_entries,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.ports.case_outbox import CaseOutboxPersistence

#: Name of the finishing node in a clock-decision stage.
FINISH_OWED_EMBARGO_ENTRIES_NAME = "FinishOwedEmbargoEntries"


class FinishOwedEmbargoEntriesNode(
    DataLayerActionWithPorts, StateWriteCapable
):
    """Commit the entries an earlier embargo act on the case still owes.

    For each plan stored for *case_id*: when the act's own entry is in the
    ledger, commits the owed entries unchanged and in their planned order
    and applies them by copying; when it is not, discards the plan and
    commits nothing.  Succeeds with nothing done when no plan is stored.

    *case_id* ``None`` reads the case from ``/case_id``, for a tree that
    learns it at tick time (the case-proposal tree, which creates the case).

    Catches nothing.  A commit that fails, or an owed entry that no longer
    applies, raises: the tree ends as an internal error with the plan kept,
    so no later node reads a consent row of a part-way act (CLP-07-015,
    ADR-0095).  A clock-decision stage does not absorb a raise.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id"}

    def __init__(
        self, case_id: str | None = None, name: str | None = None
    ) -> None:
        super().__init__(name=name or FINISH_OWED_EMBARGO_ENTRIES_NAME)
        self._case_id = case_id

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        case_id = self._case_id or self._try_get_input("case_id")
        if not isinstance(case_id, str) or not case_id:
            # A tree that learns its case at tick time and has none names no
            # case, so no act on it can be open.
            self.feedback_message = "no case on the blackboard; nothing open"
            return Status.SUCCESS
        handled = finish_owed_embargo_entries(
            cast(CaseOutboxPersistence, self.datalayer),
            case_id,
            cast(str, self.actor_id),
        )
        self.feedback_message = (
            f"handled {len(handled)} open embargo plan(s) on case"
            f" '{case_id}' (CLP-07-015)"
        )
        if handled:
            self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


__all__ = ["FINISH_OWED_EMBARGO_ENTRIES_NAME", "FinishOwedEmbargoEntriesNode"]
