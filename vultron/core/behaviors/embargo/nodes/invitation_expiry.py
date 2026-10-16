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

"""The CASE_MANAGER's expiry of several embargo invitations at once.

Two acts expire every invitation of a set, one row at a time:

- the owner-close settle step (CM-23-014) expires every invitation still
  awaiting a reply, deadline or not
  (:class:`~vultron.core.behaviors.case.nodes.leave.settle.ExpirePendingInvitesOnCloseNode`);
- the overdue-invitation sweep (CM-28-015) expires every invitation whose
  RSVP deadline has passed (:class:`ExpireOverdueInvitesNode`), a clock
  decision of every received embargo tree and embargo trigger (CLP-10-025,
  ADR-0135).

Both share :class:`ExpireInvitationsNode`: for each invitation it runs the
one expiry path,
:func:`~vultron.core.behaviors.embargo.expiry_tree.create_commit_and_record_expiry_tree`,
as a nested tree, so each expiry commits the ``invite_to_embargo_on_case_expired``
entry (CM-28-009), then the CASE_MANAGER's ``Update(EmbargoConsent)`` carrying
the ``TIMED_OUT`` row, and only then writes the row (CM-28-014, ADR-0124).
Replicas copy the row from its ``Update`` entry
(:class:`~vultron.core.behaviors.embargo.nodes.expiry.ApplyInviteExpiryFromLedgerNode`
recognises the expiry entry, RSH-08-004).
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, ClassVar, cast

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


class ExpireInvitationsNode(DataLayerActionWithPorts, StateWriteCapable, ABC):
    """Expire every embargo invitation a subclass selects, one row at a time.

    For each ``(participant, embargo_id)`` pair :meth:`_invitations` returns,
    the node runs one commit → effect tree as a nested tree, the one the
    late-Accept path runs, so the transition logic is one copy.  A set with
    no invitation commits nothing.  Not gated: the caller places the node
    behind the CASE_MANAGER role gate (CM-28-014, BT-17-001), and the nested
    tree runs as the same actor.

    The entry names the Invite the ledger last recorded for that invitee and
    embargo.  The snapshot is attributed to the invitee (CM-28-009), but the
    invitee sent nothing, so ``published`` is the CASE_MANAGER's own clock.

    **An expiry is best-effort.**  Each nested tree commits before it writes
    the consent row, so a refused commit writes nothing and the case file
    holds no change the ledger lacks (CLP-07-013).  A refusal is logged as a
    WARNING and the next invitation is tried, and the node still succeeds.
    An internal error is not a refusal and is raised (ADR-0095, #4113).
    """

    #: The requirement whose expiries the subclass commits, for the log.
    _SPEC: ClassVar[str]

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id

    @abstractmethod
    def _invitations(
        self, lifecycle: EmbargoLifecycle
    ) -> list[tuple[CaseParticipant, str]]:
        """The ``(participant, embargo_id)`` pairs to expire, in order."""

    @abstractmethod
    def _what(self) -> str:
        """What the selected invitations are, for the log ("pending", …)."""

    def _published(self) -> str:
        """The claimed time each expiry entry carries: the manager's clock."""
        return now_utc().isoformat()

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        _, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1: case must exist (ADR-0087)

        selected = self._invitations(
            EmbargoLifecycle(persistence=self.datalayer)
        )
        if not selected:
            self.feedback_message = (
                f"no {self._what()} embargo Invite on case '{self._case_id}'"
            )
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

        entries = recorded_entries_for_case(
            case_id=self._case_id, dl=self.datalayer
        )
        expired = 0
        for participant, embargo_id in selected:
            if self._expire(entries, participant, embargo_id):
                expired += 1
        self.feedback_message = (
            f"expired {expired} of {len(selected)} {self._what()} embargo"
            f" Invite(s) on case '{self._case_id}' ({self._SPEC})"
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
                " Invite to embargo '%s' cannot be expired (%s)",
                self.name,
                participant.id_,
                self._case_id,
                embargo_id,
                self._SPEC,
            )
            return False
        invite_id = latest_invite_id(entries, invitee_id, embargo_id)
        if invite_id is None:
            self.logger.warning(
                "%s: the ledger of case '%s' records no Invite to embargo"
                " '%s' for '%s'; expiring the INVITED row without naming"
                " the Invite (%s)",
                self.name,
                self._case_id,
                embargo_id,
                invitee_id,
                self._SPEC,
            )
        tree = create_commit_and_record_expiry_tree(
            case_id=self._case_id,
            invitee_id=invitee_id,
            invite_id=invite_id,
            embargo_id=embargo_id,
            published=self._published(),
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


class ExpireOverdueInvitesNode(ExpireInvitationsNode):
    """Expire every invitation on the case whose RSVP deadline has passed.

    The CM-28-015 sweep, a clock decision (CLP-10-025): the CASE_MANAGER runs
    it after the door guards of every received embargo activity, before the
    activity's precondition guards, and ahead of every embargo trigger's own
    tree, so the case owner learns of each timeout through the expiry
    entry's fan-out before it decides on an embargo (MSM-07-007).  It
    decides from *now*, the CASE_MANAGER's clock, and the case file; the
    activity only prompts it.

    The invitations are
    :meth:`~vultron.core.services.embargo_lifecycle.EmbargoLifecycle.overdue_invitations`:
    ``INVITED`` rows on an open proposal or the embargo in force whose
    deadline is at or before *now*.  A row on a replaced, rejected,
    cancelled or ended embargo is frozen and is not swept (ADR-0122); a row
    already ``TIMED_OUT`` is not ``INVITED``, so a repeat sweep commits
    nothing.
    """

    _SPEC: ClassVar[str] = "CM-28-015"

    def __init__(
        self, case_id: str, now: datetime, name: str | None = None
    ) -> None:
        super().__init__(case_id=case_id, name=name)
        self._now = now

    def _invitations(
        self, lifecycle: EmbargoLifecycle
    ) -> list[tuple[CaseParticipant, str]]:
        return lifecycle.overdue_invitations(self._case_id, self._now)

    def _what(self) -> str:
        return "overdue"

    def _published(self) -> str:
        return self._now.isoformat()


__all__ = [
    "ExpireInvitationsNode",
    "ExpireOverdueInvitesNode",
    "latest_invite_id",
]
