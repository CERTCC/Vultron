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

These nodes persist inbound report-related objects (VulnerabilityReport and
protocol activities) to the DataLayer in an idempotent way.

``StoreReportNode`` delegates existence checks to ``_idempotent_create()``,
which uses ``dl.read()`` to avoid a silent catch-all on ``ValueError``.

``StoreActivityNode`` uses a guarded ``dl.create()`` with a narrow ``ValueError``
catch.  The ``dl.read()`` approach does not work for ``VultronActivity``
objects because they are stored in type-keyed collections (e.g. ``"Create"``)
and cannot be retrieved by URI alone.  A ``ValueError`` from ``dl.create()``
always means "duplicate" for activities — the SQLite DL raises precisely this
error on duplicate IDs within a typed collection.

Per issue #759 AC-1, AC-2, AC-3, AC-4.
"""

from typing import Any

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.use_cases._helpers import _idempotent_create


class StoreReportNode(DataLayerAction):
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

        _idempotent_create(
            self.datalayer,
            "VulnerabilityReport",
            self.report_id,
            self.report_obj,
            "VulnerabilityReport",
        )
        return Status.SUCCESS


class StoreActivityNode(DataLayerAction):
    """Idempotently store an inbound protocol activity in the DataLayer.

    Returns SUCCESS (no-op) when ``activity_id`` is empty or
    ``activity_obj`` is None — matching the guard logic in the original
    procedural handlers.
    """

    def __init__(
        self,
        activity_id: str,
        activity_obj: Any,
        label: str = "activity",
        name: str | None = None,
    ):
        """Initialize StoreActivityNode.

        Args:
            activity_id: ID of the activity to store.
            activity_obj: The activity object to persist (may be None if
                absent in the inbound event).
            label: Human-readable label used in log messages (e.g.
                ``"CreateReport"``).
            name: Optional custom node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self.activity_id = activity_id
        self.activity_obj = activity_obj
        self.label = label

    def update(self) -> Status:
        """Store the activity idempotently.

        Uses a narrow ``ValueError`` catch because ``dl.read()`` cannot look
        up ``VultronActivity`` objects by URI — they are stored in type-keyed
        collections (e.g. ``"Create"``, ``"Read"``).  A ``ValueError`` from
        ``dl.create()`` always indicates a duplicate for activities.

        Returns:
            SUCCESS when the activity is stored (or already exists);
            FAILURE if the DataLayer is unavailable or activity_obj is None
            when activity_id is set (precondition violation).
        """
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        if not self.activity_id:
            self.logger.debug("%s: no activity_id — skipping store", self.name)
            return Status.SUCCESS

        if self.activity_obj is None:
            self.logger.error(
                "%s: activity_obj is None for id '%s' — cannot store",
                self.name,
                self.activity_id,
            )
            return Status.FAILURE

        try:
            self.datalayer.create(self.activity_obj)
            self.logger.info(
                "Stored %s activity '%s'", self.label, self.activity_id
            )
        except ValueError:
            # Duplicate: inbox endpoint may pre-store activities before
            # dispatching.  This is expected and not an error condition.
            self.logger.debug(
                "%s activity '%s' already stored — skipping (idempotent)",
                self.label,
                self.activity_id,
            )
        return Status.SUCCESS
