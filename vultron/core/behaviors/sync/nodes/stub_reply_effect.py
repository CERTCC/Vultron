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

"""Replica replay of the invitee's reply to the stub Invite.

The ledger holds the wire messages exchanged (ADR-0114).  The invitee's
``Accept(Invite(stub))`` and ``Reject(Invite(stub))`` are already entries
(``accept_invite_actor_to_case``, ``reject_invite_actor_to_case``), and each
carries the reply verbatim: the replying actor, the stub Invite and the reply's
``published``.  They are the entries for the reply's own effects on the
invitee's record, which a replica applies through the functions the
CASE_MANAGER's trees also call
(:mod:`vultron.core.participants.stub_reply`):

- :class:`ApplyInviteAcceptFromLedgerNode` -- consent signed to the embargo in
  force, and ``joined``;
- :class:`ApplyInviteRejectFromLedgerNode` -- consent ``DECLINED`` on the
  embargo in force.

A reply for a record the replica does not hold is a broken invariant (the
chain is complete and in order, SYNC-14, SYNC-15, and ``create_case_participant``
came first), so the node FAILS with a reason and writes nothing; it is lenient
only on a replica that holds no copy of the case (Regime 2, ADR-0087).  No id is
made and no clock is read: ``updated`` is the reply's ``published`` as received.
A stale entry replayed over a seed that is ahead changes nothing.

Per CM-11-006, CM-31-012, SYNC-02-002, SYNC-12-001, RSH-08-004.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from py_trees.common import Status

from vultron.core.behaviors.sync.nodes._helpers import (
    _extract_id_from_field,
    _LedgerEffectNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.participants.stub_reply import (
    apply_stub_accept,
    apply_stub_reject,
    parse_published,
)

_Effect = Callable[[VulnerabilityCase, CaseParticipant, datetime], bool]


class _ApplyStubReplyFromLedgerNode(_LedgerEffectNode):
    """Apply the effect of a stub reply to the replying actor's held record."""

    effect: _Effect

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        entry = self._get_entry()
        snapshot = entry.payload_snapshot
        actor_id = _extract_id_from_field(snapshot.get("actor"))
        if not actor_id or not entry.case_id:
            self.logger.debug(
                "%s: payload_snapshot missing the replying actor or the case"
                " id — skipping (non-fatal)",
                self.name,
            )
            return Status.SUCCESS

        case = self._resolve_case_replica(entry.case_id)
        if case is None:
            return Status.SUCCESS  # Regime 2 (ADR-0087): partial replica, skip

        held_id = case.actor_participant_index.get(actor_id)
        record = self.datalayer.read(held_id) if held_id else None
        if not isinstance(record, CaseParticipant):
            self.feedback_message = (
                f"{entry.event_type} entry {entry.log_index} for '{actor_id}'"
                f" in case '{entry.case_id}' but this replica holds no"
                " participant record: the create_case_participant entry has"
                " not been applied, so the chain is incomplete or out of"
                " order (CM-11-006, CM-11-021, SYNC-14)"
            )
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        try:
            published = parse_published(snapshot.get("published"))
        except ValueError as exc:
            self.feedback_message = (
                f"{entry.event_type} entry {entry.log_index} for '{actor_id}':"
                f" {exc} (CLP-15-006)"
            )
            self.logger.exception("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        if type(self).effect(case, record, published):
            self.datalayer.save(record)
            self.logger.info(
                "%s: applied the reply of '%s' to its participant record in"
                " case '%s' (SYNC-02-002)",
                self.name,
                actor_id,
                entry.case_id,
            )
        else:
            self.logger.debug(
                "%s: nothing to change for '%s' — idempotent no-op",
                self.name,
                actor_id,
            )
        return Status.SUCCESS


class ApplyInviteAcceptFromLedgerNode(_ApplyStubReplyFromLedgerNode):
    """Apply an ``accept_invite_actor_to_case`` entry: consent signed, joined."""

    effect = staticmethod(apply_stub_accept)


class ApplyInviteRejectFromLedgerNode(_ApplyStubReplyFromLedgerNode):
    """Apply a ``reject_invite_actor_to_case`` entry: consent ``DECLINED``."""

    effect = staticmethod(apply_stub_reject)
