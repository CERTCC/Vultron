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

"""Store what an entry the replacing case copy reflects carries (SYNC-16-007).

An entry at or before the tail of the copy that replaced this replica's case
is stored as a no-op (``EntryReflectedByCaseCopyNode``).  The copy names some
records by id only, so the records such an entry carries are copied here, or
the replica would never hold them (CM-23-016, ADR-0142).
"""

from __future__ import annotations

from py_trees.common import Status

from vultron.core.behaviors.sync.nodes._helpers import _LedgerEffectNode
from vultron.core.services.case_copy import records_a_reflected_entry_adds


class StoreRecordsReflectedEntryCarriesNode(_LedgerEffectNode):
    """Copy each record a reflected entry carries that the case names.

    Runs only for an entry the replacing copy already reflects.  The case
    file is not touched: the copy already names each record, so the node
    stores the records alone, unchanged, and only those this replica lacks
    (:func:`~vultron.core.services.case_copy.records_a_reflected_entry_adds`).
    """

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        entry = self._get_entry()
        records = records_a_reflected_entry_adds(entry, self.datalayer)
        if records:
            with self.datalayer.transaction():
                for record in records:
                    self.datalayer.create(record)
            self.logger.info(
                "%s: stored %d record(s) reflected entry '%s' carries for"
                " case '%s' (SYNC-16-007)",
                self.name,
                len(records),
                entry.id_,
                entry.case_id,
            )
        return Status.SUCCESS
