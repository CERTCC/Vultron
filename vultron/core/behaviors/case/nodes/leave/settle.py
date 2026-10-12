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

"""Owner-close settle step: expire every pending embargo Invite (CM-23-014).

After a case closes, a pending Invite can only expire.  Waiting for its RSVP
deadline would keep the CASE_MANAGER working for a closed case, only to write
one more entry after ``case_fully_closed``.  So the owner-close sequence
(CM-23-002) expires each one first, between the CASE_MANAGER's own
``RM.CLOSED`` entry and ``case_fully_closed``.

Each expiry is the same commit → effect pair the lazy late-Accept path runs
(:func:`~vultron.core.behaviors.embargo.expiry_tree.create_commit_and_record_expiry_tree`):
one ``invite_to_embargo_on_case_expired`` entry (CM-28-009), then
``INVITED → TIMED_OUT`` on that one consent row through ``EmbargoLifecycle``
(CM-18-005).  Replicas apply it from the entry through
:class:`~vultron.core.behaviors.embargo.nodes.expiry.ApplyInviteExpiryFromLedgerNode`
(CM-28-014, RSH-08-004).
"""

from typing import Any, cast

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.expiry_tree import (
    create_commit_and_record_expiry_tree,
)
from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.behaviors.sync.nodes._helpers import _extract_id_from_field
from vultron.core.models._helpers import now_utc
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.rsvp_deadline import EMBARGO_REINVITE_EVENT_TYPE
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.core.sync_helpers import recorded_entries_for_case
from vultron.errors import VultronBTInternalError

_INVITE_EMISSION_EVENT_TYPES = frozenset(
    {
        MessageSemantics.INVITE_TO_EMBARGO_ON_CASE.value,
        EMBARGO_REINVITE_EVENT_TYPE,
    }
)
"""Ledger entries that record an ``Invite(EmbargoEvent)`` sent to one invitee.

The CASE_MANAGER's relay (EP-09-002) and its EMB-17-003 re-invite.  Each
names its one invitee in ``to`` and the embargo as its ``object``.
"""


def _snapshot_value(snapshot: dict[str, Any], key: str) -> Any:
    """*key* in *snapshot*, under its wire or its trailing-underscore spelling."""
    value = snapshot.get(key)
    return value if value is not None else snapshot.get(f"{key}_")


def _is_invite_to(
    entry: CaseLedgerEntry, invitee_id: str, embargo_id: str
) -> bool:
    """Whether *entry* records an Invite to *embargo_id* sent to *invitee_id*."""
    if entry.event_type not in _INVITE_EMISSION_EVENT_TYPES:
        return False
    snapshot = entry.payload_snapshot
    recipients = _snapshot_value(snapshot, "to")
    if not isinstance(recipients, list) or len(recipients) != 1:
        return False
    if _extract_id_from_field(recipients[0]) != invitee_id:
        return False
    return (
        _extract_id_from_field(_snapshot_value(snapshot, "object"))
        == embargo_id
    )


def latest_invite_id(
    entries: list[CaseLedgerEntry], invitee_id: str, embargo_id: str
) -> str | None:
    """The id of the last recorded Invite to *embargo_id* sent to *invitee_id*.

    *entries* is the case's ledger, oldest first.  ``None`` when the ledger
    records no such Invite.
    """
    for entry in reversed(entries):
        if _is_invite_to(entry, invitee_id, embargo_id):
            return entry.log_object_id
    return None


class ExpirePendingInvitesOnCloseNode(
    DataLayerActionWithPorts, StateWriteCapable
):
    """Expire every embargo Invite still awaiting a reply (CM-23-014).

    Runs in the owner-close sequence after
    :class:`~vultron.core.behaviors.case.nodes.leave.record.CommitCaseActorRMClosedEntryNode`
    and before ``case_fully_closed``.  For each pending invitation that
    :meth:`~vultron.core.services.embargo_lifecycle.EmbargoLifecycle.pending_invitations`
    returns, it runs one commit → effect tree as a nested tree, so every
    expired-invitation entry precedes ``case_fully_closed``.  The tree is the
    late-Accept path's own, so the transition logic is one copy.  A case with
    no pending invitation commits nothing.

    The CASE_MANAGER gate is the received tree's own: the node sits in the
    close tree's ``manager_effects``, which the factory wraps in
    ``CloseCaseEffectsIfCaseManager`` (BT-17-008, CM-28-014), and the nested
    tree runs as the same actor.

    The deadline is not read: after close an Invite can only expire.  A row
    on a final register entry is frozen (ADR-0122) and is not pending, so the
    case Invite of a stub invitee, whose row sits on the embargo the close
    already required to end (CM-23-011), needs no settling either.

    The entry names the Invite the ledger last recorded for that invitee and
    embargo.  The snapshot is attributed to the invitee (CM-28-009), but the
    invitee sent nothing, so ``published`` is the CASE_MANAGER's own clock.

    **Recording is best-effort**, for the reason
    :meth:`~vultron.core.behaviors.case.nodes.leave.record.CommitCaseActorRMClosedEntryNode._best_effort`
    gives: a FAILURE here would skip ``case_fully_closed``, and the enclosing
    Selector would read it as a non-owner Leave.  A commit the nested tree
    refuses is logged as a WARNING and the next invitation is tried.  An
    internal error is not a refusal and is raised (ADR-0095, #4113).
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        _, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1: case must exist (ADR-0087)

        pending = EmbargoLifecycle(
            persistence=self.datalayer
        ).pending_invitations(self._case_id)
        if not pending:
            self.feedback_message = (
                f"no pending embargo Invite on case '{self._case_id}'"
            )
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

        entries = recorded_entries_for_case(
            case_id=self._case_id, dl=self.datalayer
        )
        expired = 0
        for participant, embargo_id in pending:
            if self._expire(entries, participant, embargo_id):
                expired += 1
        self.feedback_message = (
            f"expired {expired} of {len(pending)} pending embargo Invite(s)"
            f" on case '{self._case_id}' before case_fully_closed (CM-23-014)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS

    def _expire(
        self,
        entries: list[CaseLedgerEntry],
        participant: CaseParticipant,
        embargo_id: str,
    ) -> bool:
        """Commit and apply one expiry; ``False`` when it was not committed."""
        assert self.actor_id is not None
        invitee_id = participant.attributed_to
        if invitee_id is None:
            self.logger.warning(
                "%s: participant '%s' on case '%s' names no actor, so its"
                " Invite to embargo '%s' cannot be expired (CM-23-014)",
                self.name,
                participant.id_,
                self._case_id,
                embargo_id,
            )
            return False
        invite_id = latest_invite_id(entries, invitee_id, embargo_id)
        if invite_id is None:
            self.logger.warning(
                "%s: the ledger of case '%s' records no Invite to embargo"
                " '%s' for '%s'; expiring the INVITED row without naming"
                " the Invite (CM-23-014)",
                self.name,
                self._case_id,
                embargo_id,
                invitee_id,
            )
        tree = create_commit_and_record_expiry_tree(
            case_id=self._case_id,
            invitee_id=invitee_id,
            invite_id=invite_id,
            embargo_id=embargo_id,
            published=now_utc().isoformat(),
        )
        result = BTBridge(
            datalayer=cast(CaseOutboxPersistence, self.datalayer)
        ).execute_with_setup(tree=tree, actor_id=self.actor_id)
        if result.internal_error:
            raise VultronBTInternalError(
                f"{self.name}: nested expiry commit for '{invitee_id}' on"
                f" case '{self._case_id}' failed: {result.feedback_message}"
            )
        if result.status != Status.SUCCESS:
            reason = (
                f"could not expire the Invite to embargo '{embargo_id}' for"
                f" '{invitee_id}' on case '{self._case_id}' (best-effort):"
                f" {result.feedback_message}"
            )
            self.logger.warning("%s: %s", self.name, reason)
            return False
        return True


__all__ = ["ExpirePendingInvitesOnCloseNode", "latest_invite_id"]
