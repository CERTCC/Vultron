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

"""End the CASE_MANAGER's sender-sequence holds before its role passes.

The outgoing CASE_MANAGER judges every activity it holds for the case before
the role passes to another actor (SYNC-21-025, ADR-0178), so the new one
inherits no hold and no held activity is lost.
"""

from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.sender_sequence_order import (
    end_case_sender_sequence_holds,
)

__all__ = ["DrainSequenceHoldsNode"]


class DrainSequenceHoldsNode(DataLayerActionWithPorts):
    """End every sender-sequence hold for the case before the role passes.

    Runs at the CASE_MANAGER in the tree that commits the acceptance of a
    ``CASE_MANAGER`` role delegation, ahead of the grant (CM-02-016): every
    sender's held activities become due for their replay, judged in number
    order with the gaps skipped, as when a wait ends (SYNC-21-025).  Their
    replays follow this delivery through the inbox, before any later
    delivery, so the outgoing CASE_MANAGER keeps nothing held and sends no
    notice for any of them.  Its writes are the CASE_MANAGER's own
    bookkeeping (SYNC-21-020), never case state.
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.ended = 0
        """How many holds the last run ended."""

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        self.ended = end_case_sender_sequence_holds(
            cast(CasePersistence, self.datalayer), self.case_id
        )
        if self.ended:
            self.logger.info(
                "%s: ended %d sender-sequence hold(s) on case '%s' before"
                " the CASE_MANAGER role passes (SYNC-21-025)",
                self.name,
                self.ended,
                self.case_id,
            )
        return Status.SUCCESS
