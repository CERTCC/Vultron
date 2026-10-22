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

"""The replica's copy of the CASE_MANAGER's abandonment of a proposal (EMB-16-001).

Split out of ``abandon`` (BTND-07-004), which re-exports it.  The slot of the
CASE_MANAGER's ``Reject(Invite(EmbargoEvent))`` of a proposal it received and
of its ``Undo(Invite(EmbargoEvent))`` of an Invite it sent (ADR-0152).
"""

from py_trees.common import Status

from vultron.core.behaviors.embargo.nodes.relay_effect import (
    _answered_invite,
    _embargo_of_invite,
)
from vultron.core.behaviors.narrative_log import log_em_transition
from vultron.core.behaviors.sync.nodes._helpers import _extract_id_from_field
from vultron.core.behaviors.sync.nodes.embargo_copy_effect import (
    ApplyEmbargoChangeFromLedgerNode,
)
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.embargo_apply import (
    EmbargoChange,
    RegisterStep,
    RegisterStepKind,
)
from vultron.core.predicates.addressing import snapshot_actor_id


class ApplyEmbargoAbandonmentFromLedgerNode(ApplyEmbargoChangeFromLedgerNode):
    """Copy the CASE_MANAGER's abandonment of one proposal (EMB-16-001).

    The slot of the CASE_MANAGER's ``Reject(Invite(EmbargoEvent))`` of a
    proposal it received and of its ``Undo(Invite(EmbargoEvent))`` of an
    Invite it sent (ADR-0152).  Each is the threat-signal ``CANCEL`` step of
    the embargo its Invite names (ADR-0122): the replica copies it through
    the one apply function, so the proposal leaves this replica's open
    proposals, and EM returns to ``NONE`` with the last one (EP-09-007,
    ADR-0124).  The CASE_MANAGER commits the cancelling entry first, so the
    ``Undo`` of each Invite it relayed finds the proposal cancelled: in
    place, a no-op, as a repeated entry is.  One whose step does not apply is
    held for gap handling (``ApplyEmbargoChangeFromLedgerNode``).
    """

    def _change(self, entry: CaseLedgerEntry) -> EmbargoChange:
        embargo_id = _extract_id_from_field(
            _embargo_of_invite(_answered_invite(entry.payload_snapshot))
        )
        if not embargo_id:
            raise TypeError("the abandonment names no embargo")
        return RegisterStep(kind=RegisterStepKind.CANCEL, embargo=embargo_id)

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        entry = self._get_entry()
        before = self._resolve_case_replica(entry.case_id)
        status = super().update()
        after = self._resolve_case_replica(entry.case_id)
        if (
            status is Status.SUCCESS
            and before is not None
            and after is not None
        ):
            log_em_transition(
                self.logger,
                snapshot_actor_id(entry.payload_snapshot.get("actor")) or "",
                entry.case_id,
                before.em_state,
                after.em_state,
            )
        return status


__all__ = ["ApplyEmbargoAbandonmentFromLedgerNode"]
