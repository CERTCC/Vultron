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

"""The CASE_MANAGER's expiry and honour decisions: commit, then apply.

Two decisions the CASE_MANAGER takes about one invitee's consent row, from
the clock or from its policy (CLP-07-013, ADR-0124):

- :class:`CommitAndApplyInviteExpiryNode` — an RSVP deadline passed with no
  answer (CM-28-009): the expired-invitation entry, then the
  ``Update(EmbargoConsent)`` carrying the ``TIMED_OUT`` row.
- :class:`CommitAndApplyHonourLateAcceptNode` — a late ``Accept`` honoured on
  the embargo in force (EMB-17-001): the honour entry, then the
  ``Update(EmbargoConsent)`` carrying the ``AGREED`` row.

Each decides the row first, trial-applies it, commits the act's entry and
then the row's, and only then writes the row through the one apply function.
A commit that fails leaves the row as it was.  A replica copies the row from
its ``Update`` entry through the consent slot; the act's entry changes
nothing there (``ApplyInviteExpiryFromLedgerNode``,
``ApplyHonourLateAcceptFromLedgerNode``).  The trees place both nodes behind
the CASE_MANAGER role gate (CM-28-014, BT-17-001).
"""

import json
from typing import Any, ClassVar, cast

from py_trees.common import Status

from vultron.core.behaviors.embargo.copy_commit import (
    PlannedEmbargoEntry,
    commit_and_apply_embargo_entries,
    consent_row_entry,
    read_embargo_case_file,
)
from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.behaviors.sync.commit_tree import commit_emitted_activity
from vultron.core.models.embargo_consent_move import consent_row_move
from vultron.core.models.rsvp_deadline import (
    HONOUR_LATE_ACCEPT_EVENT_TYPE,
    INVITE_EXPIRED_EVENT_TYPE,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.states.participant_embargo_consent import PEC_Trigger
from vultron.errors import VultronEntryRefusedError, VultronNotFoundError


class _CommitActThenConsentRowNode(
    DataLayerActionWithPorts, StateWriteCapable
):
    """Commit the CASE_MANAGER's act, then the consent row it changes, then apply.

    1. **Decide** the row :attr:`_TRIGGER` leaves
       (:func:`~vultron.core.models.embargo_consent_move.consent_row_move`);
       a row the trigger does not move changes nothing and commits nothing.
    2. **Trial, commit, apply** through
       :func:`~vultron.core.behaviors.embargo.copy_commit.commit_and_apply_embargo_entries`:
       the act's own entry (:attr:`_ACT_EVENT_TYPE`, *act_snapshot*), then
       the CASE_MANAGER's ``Update(EmbargoConsent)`` carrying the row in
       full, and only then is the row written.

    *act_object_id* is the act entry's object (the Invite answered, or the
    case when it cannot be named); the ``Update``'s id derives from the act,
    so a re-run after a failure commits the same entry (ID-04-004).
    """

    #: Ledger ``event_type`` of the act's own entry.
    _ACT_EVENT_TYPE: ClassVar[str]
    #: The consent trigger the act applies to the invitee's row.
    _TRIGGER: ClassVar[PEC_Trigger]
    #: True when an actor with no participant record is a failure, not a
    #: no-op.
    _REQUIRES_PARTICIPANT: ClassVar[bool] = False

    def __init__(
        self,
        *,
        case_id: str,
        invitee_id: str,
        embargo_id: str,
        act_object_id: str,
        act_snapshot: dict[str, Any],
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._invitee_id = invitee_id
        self._embargo_id = embargo_id
        self._act_object_id = act_object_id
        self._act_snapshot = act_snapshot

    def _commit_act(self) -> None:
        commit_emitted_activity(
            datalayer=cast(CaseOutboxPersistence, self.datalayer),
            actor_id=cast(str, self.actor_id),
            case_id=self._case_id,
            activity_id=self._act_object_id,
            activity_blob=json.dumps(self._act_snapshot),
            event_type=self._ACT_EVENT_TYPE,
        )

    def _fail(self, message: str) -> Status:
        self.feedback_message = message
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        dl = cast(CaseOutboxPersistence, self.datalayer)
        try:
            before = read_embargo_case_file(dl, self._case_id)
        except VultronNotFoundError as exc:
            return self._fail(str(exc))
        if self._REQUIRES_PARTICIPANT and (
            self._invitee_id not in before.participants
        ):
            return self._fail(
                f"case '{self._case_id}' holds no participant record for"
                f" '{self._invitee_id}'"
            )
        change = consent_row_move(
            before, self._invitee_id, self._embargo_id, self._TRIGGER
        )
        if change is None:
            self.feedback_message = (
                f"'{self._invitee_id}''s row for embargo '{self._embargo_id}'"
                f" on case '{self._case_id}' does not move by"
                f" {self._TRIGGER}; nothing to commit"
            )
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS
        commit_row = consent_row_entry(
            datalayer=dl,
            trigger_activity=self._require_trigger_activity_port(),
            actor_id=cast(str, self.actor_id),
            case_id=self._case_id,
            change=change,
            cause_id=f"{self._ACT_EVENT_TYPE}:{self._act_object_id}",
        ).commit
        assert commit_row is not None  # a consent-row entry always commits

        def _commit() -> None:
            # One decision, two entries: the act, then the row it changes.
            self._commit_act()
            commit_row()

        try:
            commit_and_apply_embargo_entries(
                dl,
                self._case_id,
                [PlannedEmbargoEntry(change=change, commit=_commit)],
            )
        except VultronEntryRefusedError as exc:
            return self._fail(str(exc))
        self.feedback_message = (
            f"committed '{self._ACT_EVENT_TYPE}' and the {change.row.state}"
            f" row of '{self._invitee_id}' for embargo '{self._embargo_id}'"
            f" on case '{self._case_id}', then applied it (ADR-0124)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class CommitAndApplyInviteExpiryNode(_CommitActThenConsentRowNode):
    """Commit an expired invitation and its ``TIMED_OUT`` row, then apply it.

    The commit → effect half of the CM-28-009 expiry: the expired-invitation
    entry (distinct from a ``Reject``), then the CASE_MANAGER's
    ``Update(EmbargoConsent)`` carrying the invitee's ``TIMED_OUT`` row
    (CM-28-014), and only then ``INVITED → TIMED_OUT`` is written.  Only the
    row for *embargo_id* moves: the deadline belongs to that invitation
    (CM-28-001).  A row no longer ``INVITED`` commits nothing.
    """

    _ACT_EVENT_TYPE = INVITE_EXPIRED_EVENT_TYPE
    _TRIGGER = PEC_Trigger.TIME_OUT


class CommitAndApplyHonourLateAcceptNode(_CommitActThenConsentRowNode):
    """Commit the honour decision and the ``AGREED`` row, then apply it.

    The CASE_MANAGER's policy decision to honour a late ``Accept``
    (EMB-17-001, ADR-0118): the honour entry, then its
    ``Update(EmbargoConsent)`` carrying the participant's ``AGREED`` row,
    and only then ``TIMED_OUT → AGREED`` or ``DECLINED → AGREED`` is
    written.  An already ``AGREED`` row commits nothing; an actor with no
    participant record fails.
    """

    _ACT_EVENT_TYPE = HONOUR_LATE_ACCEPT_EVENT_TYPE
    _TRIGGER = PEC_Trigger.AGREE
    _REQUIRES_PARTICIPANT = True


__all__ = [
    "CommitAndApplyHonourLateAcceptNode",
    "CommitAndApplyInviteExpiryNode",
]
