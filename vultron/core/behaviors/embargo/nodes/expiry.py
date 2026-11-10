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

"""Invite-expiry BT nodes: evaluation (CASE_MANAGER only) and replica replay.

The CASE_MANAGER evaluates invite expiry lazily, as a clock decision of the
Invite Accept tree behind the received-tree factory's role gate
(:func:`~vultron.core.behaviors.embargo.expiry_tree.invite_expiry_decision`,
CLP-10-025, CM-28-014, CM-28-016, BT-17-001).  The tree follows the
guard → commit → effect pattern (CLP-10-006, BT-06-006):

1. :class:`EvaluateInviteExpiryNode` calls the **read-only**
   :meth:`~vultron.core.services.embargo_lifecycle.EmbargoLifecycle.assess_invite_expiry`,
   writing :data:`IS_EXPIRED_KEY` and :data:`NEEDS_APPLY_KEY` to *result_out*.
   No PEC transition is applied here.
2. :class:`InviteExpiryNeedsApplyNode` gates whether a ledger entry must be
   committed (CM-28-009) — true only when the invitee is still ``INVITED``.
3. :class:`~vultron.core.behaviors.embargo.nodes.expiry_commit.CommitAndApplyInviteExpiryNode`
   commits the CASE_MANAGER's ``Update(EmbargoConsent)`` carrying the
   invitee's ``TIMED_OUT`` row, and only then writes the row through the one
   apply function (ADR-0124).  A failed commit therefore leaves the invitee
   unchanged (CLP-07-013, CLP-10-006).

:class:`InviteExpiryChangedConsentNode` is a backward-compatible alias for
:class:`InviteExpiryNeedsApplyNode`.

A participant replica never evaluates a deadline and runs no ``TIME_OUT``:
it copies the ``Update(EmbargoConsent)`` entry through the consent slot of
``create_announce_log_entry_tree`` (RSH-08-004, CM-28-030).

A late Accept is answered as an on-time one is, by whether the embargo it
names is still available (EMB-17-001, MSM-07-012): one of the embargo in
force or of an open proposal, before its end time, is recorded (EMB-17-002,
ADR-0152), and replicas copy the row it states.
"""

from datetime import datetime
from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.errors import VultronNotFoundError

IS_EXPIRED_KEY = "is_expired"
"""``result_out`` key: the invite's deadline has passed and the invite is unanswered."""

NEEDS_APPLY_KEY = "needs_apply"
"""``result_out`` key: the invitee's row is still ``INVITED`` and TIME_OUT needs applying.

Set by :class:`EvaluateInviteExpiryNode` (read-only assess).  When it is
``True`` the expiry tree commits the expiry and its ``TIMED_OUT`` row, then
applies ``INVITED → TIMED_OUT`` (CLP-10-006, ADR-0124).
"""

CONSENT_CHANGED_KEY = NEEDS_APPLY_KEY
"""Backward-compatible alias for :data:`NEEDS_APPLY_KEY`."""


class EvaluateInviteExpiryNode(DataLayerActionWithPorts):
    """Read-only assessment of whether an RSVP deadline has passed.

    Calls the **read-only**
    :meth:`~vultron.core.services.embargo_lifecycle.EmbargoLifecycle.assess_invite_expiry`
    and writes its outcome to *result_out*:

    * :data:`IS_EXPIRED_KEY` — ``True`` when the deadline passed and the
      participant is not a signatory to the active embargo.  It decides
      nothing about the Accept's answer, which reads the embargo's
      availability (MSM-07-012).
    * :data:`NEEDS_APPLY_KEY` — ``True`` when the invitee is still ``INVITED``
      and the commit + effect nodes need to run.

    This node makes **no writes** (CLP-10-006 guard role).
    Placed only behind the CASE_MANAGER gate (CM-28-016, BT-17-001).
    """

    def __init__(
        self,
        case_id: str,
        invitee_id: str,
        embargo_id: str,
        now: datetime,
        result_out: dict[str, Any],
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._invitee_id = invitee_id
        self._embargo_id = embargo_id
        self._now = now
        self._result_out = result_out

    def update(self) -> Status:
        self._result_out[IS_EXPIRED_KEY] = False
        self._result_out[NEEDS_APPLY_KEY] = False
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        try:
            is_expired, needs_apply = EmbargoLifecycle(
                persistence=self.datalayer
            ).assess_invite_expiry(
                case_id=self._case_id,
                actor_id=self._invitee_id,
                embargo_id=self._embargo_id,
                now=self._now,
            )
        except VultronNotFoundError as exc:
            self.feedback_message = str(exc)
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        self._result_out[IS_EXPIRED_KEY] = is_expired
        self._result_out[NEEDS_APPLY_KEY] = needs_apply
        self.feedback_message = (
            f"invite of '{self._invitee_id}' on case '{self._case_id}'"
            f" {'expired' if is_expired else 'still open'}"
            f"{' (needs apply)' if needs_apply else ''}"
        )
        self.logger.debug("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class InviteExpiryNeedsApplyNode(py_trees.behaviour.Behaviour):
    """Condition: the preceding assessment found a TIME_OUT to apply.

    SUCCESS when :class:`EvaluateInviteExpiryNode` found the invitee still
    ``INVITED`` with a passed deadline — the one outcome that requires a
    ledger entry and a subsequent
    :class:`~vultron.core.behaviors.embargo.nodes.expiry_commit.CommitAndApplyInviteExpiryNode`
    (CM-28-009, CLP-10-006).
    """

    def __init__(
        self, result_out: dict[str, Any], name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._result_out = result_out

    def update(self) -> Status:
        if self._result_out.get(NEEDS_APPLY_KEY):
            return Status.SUCCESS
        return Status.FAILURE


InviteExpiryChangedConsentNode = InviteExpiryNeedsApplyNode


__all__ = [
    "CONSENT_CHANGED_KEY",
    "IS_EXPIRED_KEY",
    "NEEDS_APPLY_KEY",
    "EvaluateInviteExpiryNode",
    "InviteExpiryChangedConsentNode",
    "InviteExpiryNeedsApplyNode",
]
