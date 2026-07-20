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

"""BT leaf node for received Announce(VulnerabilityCase) activities.

Provides the action node that seeds a local DataLayer with a
``VulnerabilityCase`` received from the case's owner/CaseActor, stores
embedded participants, and links any matching report-case associations.

Per ``specs/mpcvd-cases.yaml`` MV-10-003 (create if absent) and
MV-10-004 (idempotent if already present).

The composite tree factory is in ``announce_case_received_tree.py`` at
the process-area root per BTND-07-003.
"""

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.events.actor import (
    AnnounceVulnerabilityCaseReceivedEvent,
)
from vultron.core.models.case import VulnerabilityCase


class SeedAnnouncedCaseNode(DataLayerAction):
    """Persist a received ``VulnerabilityCase`` announcement in the DataLayer.

    On first receipt the node saves ``case_obj`` and stores any embedded
    participants and linked report-case associations (MV-10-003).  On
    repeated receipt the case is already present so the node skips the
    save but still refreshes participants and links (MV-10-004, idempotent).

    Returns ``SUCCESS`` in both paths, ``FAILURE`` on persist error or
    missing DataLayer.
    """

    def __init__(
        self,
        case_id: str,
        case_obj: VulnerabilityCase,
        request: AnnounceVulnerabilityCaseReceivedEvent,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.case_obj = case_obj
        self._request = request

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE

        # Local import avoids a behaviors → use_cases circular dependency.
        # The helpers are pure utility functions with no BT knowledge.
        from vultron.core.use_cases.received.actor.announce import (
            _link_report_case_links,
        )
        from vultron.core.use_cases.received.case._helpers import (
            _store_embedded_participants,
        )

        existing = self.datalayer.read(self.case_id)
        if existing is not None:
            # Idempotent path — case already present locally (MV-10-004).
            self.logger.info(
                "%s: case '%s' already exists locally"
                " — skipping save (idempotent, MV-10-004)",
                self.name,
                self.case_id,
            )
            _store_embedded_participants(
                self.case_obj, self.datalayer, self.case_id
            )
            _link_report_case_links(self.datalayer, self.case_obj)
            return Status.SUCCESS

        try:
            self.datalayer.save(self.case_obj)
            _store_embedded_participants(
                self.case_obj, self.datalayer, self.case_id
            )
            _link_report_case_links(self.datalayer, self.case_obj)
            self.logger.info(
                "%s: seeded case '%s' from actor '%s'",
                self.name,
                self.case_id,
                self._request.actor_id,
            )
            return Status.SUCCESS
        except Exception as exc:
            self.feedback_message = str(exc)
            self.logger.error(
                "%s: failed to seed case '%s': %s",
                self.name,
                self.case_id,
                exc,
            )
            return Status.FAILURE
