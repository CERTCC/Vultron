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

"""Idempotent storage action nodes for the report behavior tree.

``StoreReportNode`` persists an inbound VulnerabilityReport in an idempotent
way, delegating existence checks to ``idempotent_store()``, which uses
``dl.read()`` to avoid a silent catch-all on ``ValueError``.

The received activity is not stored here: intake archives it first
(CLP-10-017, CLP-10-019).

Per issue #759 AC-1, AC-2, AC-3, AC-4.
"""

from typing import Any

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.services.idempotent_store import idempotent_store


class StoreReportNode(DataLayerActionWithPorts):
    """Idempotently store a VulnerabilityReport in the DataLayer.

    Returns SUCCESS (no-op) when ``report_id`` is empty or ``report_obj`` is
    None — this matches the guard logic in the original procedural handler
    where a missing embedded report is logged and skipped.
    """

    def __init__(
        self,
        report_id: str,
        report_obj: Any,
        name: str | None = None,
    ):
        """Initialize StoreReportNode.

        Args:
            report_id: ID of the VulnerabilityReport to store.
            report_obj: The report object to persist (may be None if absent
                in the inbound activity).
            name: Optional custom node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id
        self.report_obj = report_obj

    def update(self) -> Status:
        """Store the report idempotently.

        Returns:
            SUCCESS always (including no-op if report_id is empty or
            report_obj is None); FAILURE if the DataLayer is unavailable.
        """
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        if not self.report_id:
            self.logger.debug("%s: no report_id — skipping store", self.name)
            return Status.SUCCESS

        idempotent_store(
            self.datalayer,
            "VulnerabilityReport",
            self.report_id,
            self.report_obj,
            "VulnerabilityReport",
        )
        return Status.SUCCESS
