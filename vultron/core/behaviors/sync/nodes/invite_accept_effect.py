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

"""Ledger effect node for ``accept_invite_actor_to_case`` events.

Per specs/sync-ledger-replication.yaml SYNC-02-002, ADR-0022,
and specs/multi-actor-demo.yaml DEMOMA-07-003.
"""

from __future__ import annotations

import logging

from py_trees.common import Status

from vultron.core.behaviors.sync.nodes._helpers import (
    _extract_id_from_field,
    _LedgerEffectNode,
)
from vultron.core.models.case_participant import CaseParticipant

logger = logging.getLogger(__name__)


class ApplyInviteAcceptFromLedgerNode(_LedgerEffectNode):
    """Apply an ``accept_invite_actor_to_case`` ledger entry to the local case replica.

    When a non-CaseActor participant receives ``Announce(CaseLedgerEntry)``
    and the entry's ``event_type`` is ``accept_invite_actor_to_case``, this
    node extracts the invitee actor ID from ``payload_snapshot["actor"]`` and
    marks the invitee's existing inert record ``joined=True``.  It never
    creates a record: the record exists on every replica from the stub
    Invite's entry
    (:class:`~vultron.core.behaviors.sync.nodes.stub_invite_effect.ApplyStubInviteFromLedgerNode`),
    as it does on the CASE_MANAGER from the moment it sends the Invite
    (CM-11-006, CM-31-012).  That is how existing participants learn that a
    new actor has joined: they MUST NOT update ``case_participants`` from
    ``Accept(Invite)`` messages; they learn it from this ledger entry
    (ADR-0022, SYNC-02-002, DEMOMA-07-003).

    A record already ``joined`` is left alone (idempotent, a replay).  A
    replica that holds no record for the invitee has a broken invariant: the
    chain is complete and applied in order (SYNC-14, SYNC-15), so the stub
    Invite's entry came first.  The node fails with a reason and writes
    nothing, as the CASE_MANAGER refuses an Accept it holds no record for
    (CM-11-021).

    Lenient only on a replica that holds no copy of the case (Regime 2,
    ADR-0087) or a snapshot that names no invitee.
    """

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        entry = self._get_entry()
        snapshot = entry.payload_snapshot
        case_id = entry.case_id

        invitee_id = _extract_id_from_field(snapshot.get("actor"))
        if not invitee_id or not case_id:
            self.logger.debug(
                "%s: payload_snapshot missing 'actor' id or case_id"
                " — skipping invite-accept apply (non-fatal)",
                self.name,
            )
            return Status.SUCCESS

        case = self._resolve_case_replica(case_id)
        if case is None:
            return Status.SUCCESS  # Regime 2 (ADR-0087): partial replica, skip

        participant_id = case.actor_participant_index.get(invitee_id)
        record = (
            self.datalayer.read(participant_id) if participant_id else None
        )
        if not isinstance(record, CaseParticipant):
            self.feedback_message = (
                f"Accept(Invite) entry {entry.log_index} for '{invitee_id}'"
                f" in case '{case_id}' but this replica holds no participant"
                " record for the invitee: the stub Invite's entry has not"
                " been applied, so the chain is incomplete or out of order"
                " (CM-11-006, CM-11-021, SYNC-14)"
            )
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        if record.joined:
            self.logger.debug(
                "%s: invitee '%s' already joined case '%s' — idempotent no-op",
                self.name,
                invitee_id,
                case_id,
            )
            return Status.SUCCESS

        record.joined = True
        self.datalayer.save(record)
        self.logger.info(
            "%s: marked participant '%s' joined=True for case '%s'"
            " (ADR-0114, SYNC-02-002)",
            self.name,
            invitee_id,
            case_id,
        )
        return Status.SUCCESS
