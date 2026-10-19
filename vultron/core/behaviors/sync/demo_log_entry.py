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

"""The demo ``sync-log-entry`` verb's commit (TRIG-10-004).

The entry records the CASE_MANAGER's ``Announce(VulnerabilityCase)``, built
by the factory and committed from its sealed blob like every other
CASE_MANAGER act (VM-08-003, CLP-07-013); the caller names its
``semantic_type`` and ``log_object_id``.
"""

from typing import cast

from vultron.core.behaviors.case_manager_commit import (
    _CommitCaseManagerActivityBase,
)


class CommitDemoLogEntryNode(_CommitCaseManagerActivityBase):
    """Commit the CASE_MANAGER's ``Announce(VulnerabilityCase)`` for the demo verb.

    Addressed to nobody: the commit tree's fan-out announces the entry to the
    case's participants (SYNC-02-002).  The entry's ``log_object_id`` is the
    caller's *object_id*, not the activity's id.
    """

    def __init__(
        self,
        case_id: str,
        object_id: str,
        semantic_type: str,
        name: str | None = None,
    ) -> None:
        super().__init__(
            case_id=case_id,
            semantic_type=semantic_type,
            notify_participants=False,
            name=name,
        )
        self._object_id = object_id

    def _ledger_object_id(self, activity_id: str) -> str:
        return self._object_id

    def _build(self, to: list[str] | None) -> tuple[str, str]:
        assert self.trigger_activity_factory is not None
        return self.trigger_activity_factory.record_case_announced(
            case_id=self._case_id,
            actor=cast(str, self.actor_id),
            semantic_type=self._semantic_type,
            object_id=self._object_id,
        )


__all__ = ["CommitDemoLogEntryNode"]
