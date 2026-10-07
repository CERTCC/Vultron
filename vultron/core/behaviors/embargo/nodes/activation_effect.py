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

"""Ledger replay of ``add_embargo_event_to_case`` entries (RSH-08-004).

The CASE_MANAGER commits the ``Add(EmbargoEvent)`` it accepts from the case
owner (EP-09-005) and activates the embargo with ``SetEmbargoActiveNode``.
:class:`ApplyEmbargoActivationFromLedgerNode` runs the same node on a
participant replica from the committed entry, so the replica's EM state and
``active_embargo`` follow the CASE_MANAGER's without the ``Add`` reaching the
replica directly (PCR-03-001).  It is the activation counterpart of
``ApplyEmbargoTeardownNode`` and, like it, goes through ``EmbargoLifecycle`` in
``OBSERVED`` mode (EMB-18-001): the CASE_MANAGER already decided, so the
replica syncs to the decision rather than re-adjudicating it.
"""

from __future__ import annotations

from py_trees.common import Status

from vultron.core.behaviors.embargo.nodes.lifecycle import SetEmbargoActiveNode
from vultron.core.behaviors.embargo.nodes.relay_effect import (
    _EmbargoRelayEffectNode,
)
from vultron.core.behaviors.sync.nodes.event_conditions import (
    _SingleEventTypeNode,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.services.embargo_lifecycle import TransitionMode

#: Ledger ``event_type`` of a committed embargo activation.
EMBARGO_ACTIVATION_EVENT_TYPE = (
    MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE.value
)


class IsAddEmbargoEventNode(_SingleEventTypeNode):
    """Precondition: this entry is an ``add_embargo_event_to_case`` event.

    Used in the ``EmbargoActivation`` slot of ``AnnounceLogEntryReceivedBT``.

    Per RSH-08-004, BTND-08-001, SYNC-12-001.
    """

    matched_event_type = EMBARGO_ACTIVATION_EVENT_TYPE


class ApplyEmbargoActivationFromLedgerNode(_EmbargoRelayEffectNode):
    """Activate the entry's embargo on the replica (EM → ACTIVE).

    Stores the ``EmbargoEvent`` the entry carries inline when the replica does
    not hold it (EMB-18-003), then runs ``SetEmbargoActiveNode`` in
    ``OBSERVED`` mode, which calls ``EmbargoLifecycle.activate_embargo``.  An
    embargo already in force is a no-op, so a re-delivered entry changes
    nothing.

    SUCCESS with nothing written when the replica holds no copy of the case
    (Regime 2, ADR-0087).  FAILURE, so the entry is not persisted
    (SYNC-12-001), when the entry names no embargo, names one the replica can
    neither find nor reconstruct, or the activation fails.
    """

    def update(self) -> Status:
        entry = self._get_entry()
        resolved = self._resolve(entry.payload_snapshot.get("object"))
        if isinstance(resolved, Status):
            return resolved
        case, embargo_id = resolved
        status = self._delegate(
            SetEmbargoActiveNode(
                case_id=case.id_,
                embargo_id=embargo_id,
                transition_mode=TransitionMode.OBSERVED,
                name=f"{self.name}.SetEmbargoActive",
            )
        )
        if status == Status.SUCCESS:
            self.logger.info(
                "%s: replayed activation of embargo '%s' on case '%s'"
                " (RSH-08-004)",
                self.name,
                embargo_id,
                case.id_,
            )
        return status
