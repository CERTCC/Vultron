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
CLP-10-025, CM-28-014, BT-17-001).  The tree follows the guard → commit → effect pattern
(CLP-10-006, BT-06-006):

1. :class:`EvaluateInviteExpiryNode` calls the **read-only**
   :meth:`~vultron.core.services.embargo_lifecycle.EmbargoLifecycle.assess_invite_expiry`,
   writing :data:`IS_EXPIRED_KEY` and :data:`NEEDS_APPLY_KEY` to *result_out*.
   No PEC transition is applied here.
2. :class:`InviteExpiryNeedsApplyNode` gates whether a ledger entry must be
   committed (CM-28-009) — true only when the invitee is still ``INVITED``.
3. :class:`~vultron.core.behaviors.embargo.nodes.expiry_commit.CommitAndApplyInviteExpiryNode`
   commits the expired-invitation entry, then the CASE_MANAGER's
   ``Update(EmbargoConsent)`` carrying the invitee's ``TIMED_OUT`` row, and
   only then writes the row through the one apply function (ADR-0124).  A
   failed commit therefore leaves the invitee unchanged (CLP-07-013,
   CLP-10-006).

:class:`InviteExpiryChangedConsentNode` is a backward-compatible alias for
:class:`InviteExpiryNeedsApplyNode`.

A participant replica never evaluates a deadline and runs no ``TIME_OUT``:
it copies the ``Update(EmbargoConsent)`` entry through the consent slot, and
:class:`ApplyInviteExpiryFromLedgerNode`, reached from
``create_announce_log_entry_tree`` (RSH-08-004, CM-28-014), recognises the
expiry entry itself.

For the no-op late-Accept decision (EMB-17-004):
:class:`ApplyInviteExpiryNoopFromLedgerNode` recognises the entry and
returns SUCCESS without applying any PEC transition.

For the honour late-Accept decision (EMB-17-001):
:class:`~vultron.core.behaviors.embargo.nodes.expiry_commit.CommitAndApplyHonourLateAcceptNode`
commits the honour entry and its ``AGREED`` row before writing it, and
:class:`ApplyHonourLateAcceptFromLedgerNode` recognises the honour entry on
replicas, which copy the row from its own entry.
"""

from datetime import datetime
from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.behaviors.node_logger import node_logger
from vultron.core.behaviors.sync.nodes._helpers import (
    _extract_id_from_field,
    _LedgerEffectNode,
)
from vultron.core.predicates.addressing import snapshot_actor_id
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


def _snapshot_embargo_id(snapshot: dict[str, object]) -> str | None:
    """The embargo an expiry or honour entry's Invite names (``object.object``)."""
    invite = snapshot.get("object")
    if not isinstance(invite, dict):
        return None
    return _extract_id_from_field(invite.get("object"))


class EvaluateInviteExpiryNode(DataLayerActionWithPorts):
    """Read-only assessment of whether an RSVP deadline has passed.

    Calls the **read-only**
    :meth:`~vultron.core.services.embargo_lifecycle.EmbargoLifecycle.assess_invite_expiry`
    and writes its outcome to *result_out*:

    * :data:`IS_EXPIRED_KEY` — ``True`` when the deadline passed and the
      participant is not a signatory to the active embargo.
      Used by EMB-17 routing.
    * :data:`NEEDS_APPLY_KEY` — ``True`` when the invitee is still ``INVITED``
      and the commit + effect nodes need to run.

    This node makes **no writes** (CLP-10-006 guard role).
    Placed only behind the CASE_MANAGER gate (CM-28-014, BT-17-001).
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


class InviteNotExpiredNode(py_trees.behaviour.Behaviour):
    """Precondition guard: the clock decision found the Invite still open.

    FAILURE when :class:`EvaluateInviteExpiryNode`, the Accept tree's clock
    decision, found the invitee's deadline passed: the Accept is late, so the
    normal answer path must not record it, whether or not the expiry entry
    could be committed (CLP-10-025).  The handler then routes the late
    Accept by its compatibility with the case's embargo (EMB-17-001).
    SUCCESS otherwise, including on a store that is not the CASE_MANAGER,
    where the decision does not run and *result_out* stays unset.
    Read-only.
    """

    def __init__(
        self,
        result_out: dict[str, object],
        invitee_id: str,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._result_out = result_out
        self._invitee_id = invitee_id
        self._case_id = case_id

    def update(self) -> Status:
        if self._result_out.get(IS_EXPIRED_KEY):
            self.feedback_message = (
                f"the Invite of '{self._invitee_id}' on case"
                f" '{self._case_id}' passed its RSVP deadline; a late Accept"
                " is routed by its compatibility with the case's embargo,"
                " not recorded as an answer (EMB-17-001)"
            )
            log = node_logger(self)
            log.debug("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        return Status.SUCCESS


#: Backward-compatible alias for :class:`InviteExpiryNeedsApplyNode`.
InviteExpiryChangedConsentNode = InviteExpiryNeedsApplyNode


class _RecordedActFromLedgerNode(_LedgerEffectNode):
    """Recognise an act entry whose consent change is its own entry.

    The CASE_MANAGER commits the act, then an ``Update(EmbargoConsent)``
    carrying the row it changes; the consent slot copies that row
    (ADR-0124, CM-23-016).  This entry therefore changes nothing here: the
    node returns SUCCESS so the entry is persisted in its chain position, and
    computes nothing (no deadline, no PEC transition).  An entry that names
    no actor or no embargo fails, so it is not persisted (SYNC-12-001).
    Regime 2 (ADR-0087): a replica holding no copy of the case skips with
    SUCCESS.
    """

    _label: str = "act"

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        entry = self._get_entry()
        case = self._resolve_case_replica(entry.case_id)
        if case is None:
            return Status.SUCCESS  # Regime 2 (ADR-0087): partial replica
        # Normalised: the snapshot keeps the sender's spelling (OID-01-006).
        actor_id = snapshot_actor_id(entry.payload_snapshot.get("actor"))
        embargo_id = _snapshot_embargo_id(entry.payload_snapshot)
        if not actor_id or not embargo_id:
            self.feedback_message = (
                f"{self._label} entry on case '{case.id_}' is missing its"
                f" actor ('{actor_id}') or embargo id ('{embargo_id}')"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        self.feedback_message = (
            f"recorded the {self._label} of '{actor_id}' for embargo"
            f" '{embargo_id}' on case '{case.id_}'; its consent row is its"
            " own entry (ADR-0124)"
        )
        self.logger.debug("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class ApplyInviteExpiryFromLedgerNode(_RecordedActFromLedgerNode):
    """Recognise the CASE_MANAGER's expiry entry on a replica (CM-28-014).

    The entry's ``actor`` is the timed-out invitee and its ``object`` the
    Invite, naming the embargo.  The ``TIMED_OUT`` row follows as the
    CASE_MANAGER's own ``Update(EmbargoConsent)`` entry, which the consent
    slot copies, so a replica never evaluates a deadline nor runs
    ``TIME_OUT`` itself (CM-23-016, ADR-0124).
    """

    _label = "invite expiry"


class ApplyInviteExpiryNoopFromLedgerNode(_LedgerEffectNode):
    """Replay the CASE_MANAGER's no-op expiry entry on a replica (EMB-17-004).

    The entry records that the CASE_MANAGER received a late ``Accept`` when
    no embargo was active (EM EXITED or NONE), acknowledged it, and made no
    PEC change (EMB-17-004, ADR-0118); its snapshot is the CASE_MANAGER's
    ``Ignore`` of that Accept.  The replay node recognises the entry
    and returns SUCCESS without touching any participant record, so the entry
    is not mis-routed and its chain position is persisted on every replica.
    Regime 2 (ADR-0087): a replica holding no copy of the case skips with
    SUCCESS.
    """

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        entry = self._get_entry()
        case = self._resolve_case_replica(entry.case_id)
        if case is None:
            return Status.SUCCESS  # Regime 2 (ADR-0087): partial replica
        # The snapshot is the CASE_MANAGER's Ignore of the late Accept; the
        # accepter is the Accept's own actor (EMB-17-004, CLP-07-013).
        late_accept = entry.payload_snapshot.get("object")
        invitee_id = (
            snapshot_actor_id(late_accept.get("actor"))
            if isinstance(late_accept, dict)
            else None
        )
        self.feedback_message = (
            f"Replayed no-op expiry ack for"
            f" '{invitee_id or '(unknown)'}' on case '{case.id_}'"
        )
        self.logger.debug("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class ApplyHonourLateAcceptFromLedgerNode(_RecordedActFromLedgerNode):
    """Recognise the CASE_MANAGER's honour decision on a replica (EMB-17-001).

    The entry's ``actor`` is the accepted participant and its ``object``
    the Invite and the embargo.  The ``AGREED`` row follows as the
    CASE_MANAGER's own ``Update(EmbargoConsent)`` entry, which the consent
    slot copies (CM-23-016, ADR-0124).
    """

    _label = "honoured late Accept"


__all__ = [
    "CONSENT_CHANGED_KEY",
    "IS_EXPIRED_KEY",
    "NEEDS_APPLY_KEY",
    "ApplyHonourLateAcceptFromLedgerNode",
    "ApplyInviteExpiryFromLedgerNode",
    "ApplyInviteExpiryNoopFromLedgerNode",
    "EvaluateInviteExpiryNode",
    "InviteExpiryChangedConsentNode",
    "InviteExpiryNeedsApplyNode",
    "InviteNotExpiredNode",
]
