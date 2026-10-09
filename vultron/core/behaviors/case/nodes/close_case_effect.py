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

"""Ledger effect node for ``close_case`` events.

Per specs/case-management.yaml CM-23-003, CM-23-004,
specs/sync-ledger-replication.yaml SYNC-02-002, and ADR-0050.
"""

from __future__ import annotations

import logging

from py_trees.common import Status

from vultron.core.behaviors.case.nodes.participant.rm_closure import (
    RMClosureWriter,
)
from vultron.core.behaviors.sync.nodes._helpers import (
    _extract_id_from_field,
    _LedgerEffectNode,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.participant_status import participant_status_rm_state
from vultron.core.states.rm import RM

logger = logging.getLogger(__name__)


class ApplyCloseCaseFromLedgerNode(_LedgerEffectNode):
    """Apply a ``close_case`` ledger entry to the local case replica.

    When a non-CaseActor participant receives ``Announce(CaseLedgerEntry)``
    and the entry's ``event_type`` is ``close_case``, this node extracts the
    departing actor ID from ``payload_snapshot["actor"]`` and advances that
    actor's :class:`~vultron.core.models.participant_status.ParticipantStatus`
    to ``RM.CLOSED`` on the local DataLayer replica, by the same ordinary RM
    transitions the CASE_MANAGER wrote (``V → D → C`` from Valid, RMB-14-005).

    This is the fan-out counterpart of the CaseActor's ``receive_close_case_tree``
    effect: both paths MUST produce the same end state on every replica
    (CM-23-003, CM-23-004, ADR-0050).

    Lenient on missing data: if the case replica is absent, the departing actor
    ID is not extractable, or the participant record is missing, the node
    returns SUCCESS to avoid blocking the ``Announce`` processing flow.

    Per specs/case-management.yaml CM-23-003, CM-23-004,
    specs/sync-ledger-replication.yaml SYNC-02-002.
    """

    def __init__(self, name: str | None = None) -> None:
        _name = name or self.__class__.__name__
        super().__init__(name=_name)
        # Pre-build the status writers (BTND-10-004: no construction in
        # update()); update() supplies the runtime departing actor to
        # close().  The departing actor's self-declaratory
        # Leave (PRM-06-001, ADR-0121) is replicated as ordinary RM transitions, so a Leave
        # from VALID is V -> D -> C on every replica (RMB-14-005, CM-23-012).
        # The path starts from this replica's own view of the actor's RM state,
        # so a lagging replica may write a rung the manager never saw; the
        # end state is RM.CLOSED either way.
        self._closure = RMClosureWriter(name=_name)

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        entry = self._get_entry()
        snapshot = entry.payload_snapshot
        case_id = entry.case_id

        departing_actor_id = _extract_id_from_field(snapshot.get("actor"))
        if not departing_actor_id or not case_id:
            self.logger.debug(
                "%s: payload_snapshot missing 'actor' id or case_id"
                " — skipping close-case apply (non-fatal)",
                self.name,
            )
            return Status.SUCCESS

        case = self._resolve_case_replica(case_id)
        if case is None:
            return Status.SUCCESS  # Regime 2 (ADR-0087): partial replica, skip

        if departing_actor_id not in case.actor_participant_index:
            self.logger.debug(
                "%s: departing actor '%s' not in actor_participant_index"
                " for case '%s' — skipping (non-fatal)",
                self.name,
                departing_actor_id,
                case_id,
            )
            return Status.SUCCESS

        # Idempotency: skip if already at RM.CLOSED
        participant_id = case.actor_participant_index[departing_actor_id]
        participant = self.datalayer.read(participant_id)
        if isinstance(participant, CaseParticipant):
            for ps in participant.participant_statuses:
                if participant_status_rm_state(ps) == RM.CLOSED:
                    self.logger.debug(
                        "%s: departing actor '%s' already at RM.CLOSED — no-op",
                        self.name,
                        departing_actor_id,
                    )
                    return Status.SUCCESS

        # Advance the departing actor to RM.CLOSED via the canonical writer,
        # attributed to the departing actor; BTBridge seeds case_id on the
        # blackboard so CaseIdInputPortMixin can read it (ADR-0089).
        closed = self._closure.close(
            self,
            self.datalayer,
            participant_id,
            case_id,
            actor_id=departing_actor_id,
        )
        if closed != Status.SUCCESS:
            self.logger.warning(
                "%s: failed to advance departing actor '%s' to RM.CLOSED"
                " in case '%s': %s",
                self.name,
                departing_actor_id,
                case_id,
                self.feedback_message,
            )
            return Status.FAILURE

        self.logger.info(
            "%s: applied ledger close-case for departing actor '%s'"
            " in case '%s' (CM-23-003, SYNC-02-002)",
            self.name,
            departing_actor_id,
            case_id,
        )
        return Status.SUCCESS
