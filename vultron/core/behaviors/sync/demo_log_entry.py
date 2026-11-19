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
CASE_MANAGER act (VM-08-003, CLP-07-013).  Its ``semantic_type`` is the
registry's label for that payload (ADR-0140); the caller names only its
``log_object_id``.
"""

from typing import cast

from py_trees.ports import PortInformation

from vultron.core.behaviors.act_key_ports import (
    act_key_ports,
    act_key_remappings,
    act_value,
)
from vultron.core.behaviors.act_keys import CASE_ID, OBJECT_ID
from vultron.core.behaviors.case_manager_commit import (
    _CommitCaseManagerActivityBase,
)
from vultron.core.models.events.base import MessageSemantics

#: The registry's label for the demo verb's ``Announce(VulnerabilityCase)``.
DEMO_LOG_ENTRY_SEMANTIC_TYPE = (
    MessageSemantics.ANNOUNCE_VULNERABILITY_CASE.value
)


class CommitDemoLogEntryNode(_CommitCaseManagerActivityBase):
    """Commit the CASE_MANAGER's ``Announce(VulnerabilityCase)`` for the demo verb.

    Addressed to nobody: the commit tree's fan-out announces the entry to the
    case's participants (SYNC-02-001, SYNC-02-003).  The entry's
    ``log_object_id`` is the caller's ``/object_id``, not the activity's id.

    The case and the object are read from ``/case_id`` and ``/object_id``
    (BTND-01-008); the trigger seeds both with
    :func:`~vultron.core.behaviors.act_key_scope.with_act_keys`.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **_CommitCaseManagerActivityBase.INPUT_PORTS,
        **act_key_ports(CASE_ID, OBJECT_ID),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            **super()._domain_port_remappings(),
            **act_key_remappings(CASE_ID, OBJECT_ID),
        }

    def __init__(self, name: str | None = None) -> None:
        super().__init__(
            # Unused: the case is read from ``/case_id`` through
            # :meth:`_act_case_id`; #6572 drops the base's parameter.
            case_id="",
            semantic_type=DEMO_LOG_ENTRY_SEMANTIC_TYPE,
            notify_participants=False,
            name=name,
        )

    def _act_case_id(self) -> str:
        return act_value(self, CASE_ID, str)

    def _ledger_object_id(self, activity_id: str) -> str:
        return act_value(self, OBJECT_ID, str)

    def _build(self, to: list[str] | None) -> tuple[str, str]:
        assert self.trigger_activity_factory is not None
        return self.trigger_activity_factory.record_case_announced(
            case_id=self._act_case_id(),
            actor=cast(str, self.actor_id),
            object_id=act_value(self, OBJECT_ID, str),
            at=self._require_act_instant(),
        )


__all__ = ["CommitDemoLogEntryNode", "DEMO_LOG_ENTRY_SEMANTIC_TYPE"]
