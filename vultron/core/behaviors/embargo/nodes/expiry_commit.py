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

"""The CASE_MANAGER's expiry decision: commit, then apply.

A decision the CASE_MANAGER takes about one invitee's consent row from the
clock (CLP-07-013, ADR-0124): an RSVP deadline passed with no answer
(CM-28-009), recorded as the change it makes, a factory-built
``Update(EmbargoConsent)`` carrying the ``TIMED_OUT`` row in full; no other
entry records the decision, and nothing is attributed to the invitee, who
sent nothing (ADR-0140, ADR-0152).  An honoured late ``Accept`` is no such
decision: it is recorded as an on-time ``Accept`` is (EMB-17-002).

The node decides the row first, trial-applies it, commits the ``Update`` from its
sealed blob, and only then writes the row through the one apply function.  A
commit the ledger refuses leaves the row as it was, and the node fails (it
does not raise); an internal error, including a missing consent row, raises
(CLP-10-025, ADR-0095).  A replica copies the row from the ``Update`` entry
through the consent slot, as it copies every other consent-row change
(CM-23-016).  The trees place the node behind the CASE_MANAGER role gate
(CM-28-016, BT-17-001).
"""

from typing import ClassVar, cast

from py_trees.common import Status

from vultron.core.behaviors.embargo.copy_commit import (
    commit_and_apply_embargo_entries,
    consent_row_entry,
    read_embargo_case_file,
)
from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.models.embargo_consent_move import consent_row_move
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.states.participant_embargo_consent import PEC_Trigger
from vultron.errors import VultronEntryRefusedError, VultronNotFoundError


class _CommitConsentRowDecisionNode(
    DataLayerActionWithPorts, StateWriteCapable
):
    """Commit the CASE_MANAGER's ``Update(EmbargoConsent)`` for a decision, then apply.

    1. **Decide** the row :attr:`_TRIGGER` leaves
       (:func:`~vultron.core.models.embargo_consent_move.consent_row_move`);
       a row the trigger does not move changes nothing and commits nothing.
    2. **Trial, commit, apply** through
       :func:`~vultron.core.behaviors.embargo.copy_commit.commit_and_apply_embargo_entries`:
       the CASE_MANAGER's ``Update(EmbargoConsent)`` carrying the row in full,
       built through the trigger-activity port and committed from its sealed
       blob, and only then is the row written.

    *cause_object_id* is what the decision is about (the Invite answered, or
    the case when it cannot be named); with :attr:`_CAUSE` it seeds the
    ``Update``'s derived id, so a re-run after a failure commits the same
    entry (ID-04-004).
    """

    #: Names the occasion in the ``Update``'s derived id.
    _CAUSE: ClassVar[str]
    #: The consent trigger the decision applies to the invitee's row.
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
        cause_object_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._invitee_id = invitee_id
        self._embargo_id = embargo_id
        self._cause_object_id = cause_object_id

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
        # A participant missing the row for a register entry is a broken
        # invariant (ADR-0122): ``consent_row_move`` raises, and the raise
        # ends the tree as an internal error, never a refusal (CLP-10-025).
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
        planned = consent_row_entry(
            datalayer=dl,
            trigger_activity=self._require_trigger_activity_port(),
            actor_id=cast(str, self.actor_id),
            case_id=self._case_id,
            change=change,
            cause_id=f"{self._CAUSE}:{self._cause_object_id}",
        )
        try:
            commit_and_apply_embargo_entries(dl, self._case_id, [planned])
        except VultronEntryRefusedError as exc:
            return self._fail(str(exc))
        except NotImplementedError:
            raise  # a stub port is a composition fault, not a refusal
        except RuntimeError as exc:
            # The ledger refused the entry (commit_emitted_activity): the row
            # is unwritten, and the decision fails as a guard would, so a
            # clock-decision stage logs it and goes on (CLP-10-025).
            return self._fail(f"the entry did not commit: {exc}")
        self.feedback_message = (
            f"committed the {change.row.state} row of '{self._invitee_id}'"
            f" for embargo '{self._embargo_id}' on case '{self._case_id}'"
            f" ({self._CAUSE}), then applied it (ADR-0124)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class CommitAndApplyInviteExpiryNode(_CommitConsentRowDecisionNode):
    """Commit an expired invitation's ``TIMED_OUT`` row, then apply it.

    The commit → effect half of the CM-28-009 expiry: the CASE_MANAGER's
    ``Update(EmbargoConsent)`` carrying the invitee's ``TIMED_OUT`` row
    (CM-28-014), distinct from the invitee's own ``Reject``, and only then
    ``INVITED → TIMED_OUT`` is written.  Only the row for *embargo_id*
    moves: the deadline belongs to that invitation (CM-28-001).  A row no
    longer ``INVITED`` commits nothing.
    """

    _CAUSE = "invite-expired"
    _TRIGGER = PEC_Trigger.TIME_OUT


__all__ = [
    "CommitAndApplyInviteExpiryNode",
]
