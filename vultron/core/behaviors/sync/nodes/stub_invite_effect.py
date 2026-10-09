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

"""Replica replay of the stub Invite: the inert participant record.

:class:`ApplyStubInviteFromLedgerNode` is the effect of the ``StubInvite`` slot
in ``create_announce_log_entry_tree``; its precondition is
:class:`~vultron.core.behaviors.sync.nodes.event_conditions.IsStubInviteEventNode`
(CM-11-006, CM-31-012, SYNC-02-002).

The CASE_MANAGER records the invitee as an inert participant when it sends and
commits the stub Invite.  A replica holds the same record at the same ledger
position, so it builds it from the entry with the CASE_MANAGER's own builder
(:func:`~vultron.core.participants.inert_invitee.build_inert_invitee_participant`),
reading the case's active embargo from its own replica for the consent row.
It makes no choice of its own: a record it already holds is left alone, which
is what the CASE_MANAGER does for a replacement stub or a re-invite on the
same record (CM-11-015).  The ``Accept(Invite)`` entry then marks the record
joined (:class:`~vultron.core.behaviors.sync.nodes.invite_accept_effect.ApplyInviteAcceptFromLedgerNode`).
"""

from __future__ import annotations

from py_trees.common import Status

from vultron.core.behaviors.sync.nodes._helpers import (
    _extract_id_from_field,
    _LedgerEffectNode,
)
from vultron.core.participants.inert_invitee import (
    build_inert_invitee_participant,
)
from vultron.enums.roles import validate_roles


class ApplyStubInviteFromLedgerNode(_LedgerEffectNode):
    """Create the invitee's inert participant record from a stub Invite entry.

    Lenient on a replica that holds no copy of the case (Regime 2, ADR-0087)
    and on a snapshot that names no invitee: those skip with ``SUCCESS``.  A
    snapshot with no roles is a broken entry — the CASE_MANAGER never commits
    an Invite without them (CM-11-019) — and fails with a reason.

    Per CM-11-006, CM-31-012, SYNC-02-002, SYNC-12-001.
    """

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        entry = self._get_entry()
        snapshot = entry.payload_snapshot
        case_id = entry.case_id
        invitee_id = _extract_id_from_field(snapshot.get("object"))
        if not invitee_id or not case_id:
            self.logger.debug(
                "%s: payload_snapshot missing the invitee or the case id"
                " — skipping stub-invite apply (non-fatal)",
                self.name,
            )
            return Status.SUCCESS

        case = self._resolve_case_replica(case_id)
        if case is None:
            return Status.SUCCESS  # Regime 2 (ADR-0087): partial replica, skip

        if invitee_id in case.actor_participant_index:
            self.logger.debug(
                "%s: invitee '%s' already has a record in case '%s'"
                " — idempotent no-op (CM-11-015)",
                self.name,
                invitee_id,
                case_id,
            )
            return Status.SUCCESS

        try:
            roles = validate_roles(snapshot.get("roles") or [])
        except (TypeError, ValueError, KeyError) as exc:
            return self._refuse_roles(invitee_id, case_id, exc)
        if not roles:
            return self._refuse_roles(invitee_id, case_id, "no roles named")
        participant = build_inert_invitee_participant(case, invitee_id, roles)

        if self.datalayer.read(participant.id_) is None:
            self.datalayer.create(participant)
        case.add_participant(participant)
        self.datalayer.save(case)
        self.logger.info(
            "%s: created inert participant for invitee '%s' in case '%s'"
            " from the stub Invite entry (CM-11-006, CM-31-012)",
            self.name,
            invitee_id,
            case_id,
        )
        return Status.SUCCESS

    def _refuse_roles(
        self, invitee_id: str, case_id: str, why: object
    ) -> Status:
        """Fail with a reason: the entry names no usable roles (CM-11-019)."""
        self.feedback_message = (
            f"stub Invite entry for '{invitee_id}' in case '{case_id}'"
            f" names no valid roles: {why} (CM-11-019)"
        )
        self.logger.error("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE
