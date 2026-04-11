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
"""Per-semantic inbound domain event types for SYNC-2 log replication."""

from typing import Literal, cast

from vultron.core.models.case_log_entry import VultronCaseLogEntry
from vultron.core.models.events.base import MessageSemantics, VultronEvent


class AnnounceLogEntryReceivedEvent(VultronEvent):
    """CaseActor announced a canonical CaseLogEntry for log replication.

    Spec: SYNC-02-003, SYNC-03-001, SYNC-03-002, SYNC-03-003.
    """

    semantic_type: Literal[MessageSemantics.ANNOUNCE_CASE_LOG_ENTRY] = (
        MessageSemantics.ANNOUNCE_CASE_LOG_ENTRY
    )

    @property
    def log_entry(self) -> VultronCaseLogEntry | None:
        """Return the received :class:`VultronCaseLogEntry`, or ``None``."""
        if self.object_ is None:
            return None
        return cast(VultronCaseLogEntry, self.object_)

    @property
    def log_entry_id(self) -> str | None:
        """Return the ID of the received log entry."""
        return self.object_id
