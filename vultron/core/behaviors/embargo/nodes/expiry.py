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

The CASE_MANAGER evaluates invite expiry lazily behind its role gate
(:func:`~vultron.core.behaviors.embargo.expiry_tree.create_invite_expiry_tree`,
CM-28-014, BT-17-001).  The tree follows the guard → commit → effect pattern
(CLP-10-006, BT-06-006):

1. :class:`EvaluateInviteExpiryNode` calls the **read-only**
   :meth:`~vultron.core.services.embargo_lifecycle.EmbargoLifecycle.assess_invite_expiry`,
   writing :data:`IS_EXPIRED_KEY` and :data:`NEEDS_APPLY_KEY` to *result_out*.
   No PEC transition is applied here.
2. :class:`InviteExpiryNeedsApplyNode` gates whether a ledger entry must be
   committed (CM-28-009) — true only when the invitee is still ``INVITED``.
3. After the commit node, :class:`RecordInviteExpiryNode` calls
   :meth:`~vultron.core.services.embargo_lifecycle.EmbargoLifecycle.record_invite_expiry`
   to apply ``INVITED → EXPIRED``.  A failed commit therefore leaves the
   invitee unchanged (CLP-10-006).

:class:`InviteExpiryChangedConsentNode` is a backward-compatible alias for
:class:`InviteExpiryNeedsApplyNode`.

A participant replica never evaluates a deadline; it applies the manager's
decision from the committed entry through
:class:`ApplyInviteExpiryFromLedgerNode`, reached from
``create_announce_log_entry_tree`` (RSH-08-004, CM-28-014).

For the no-op late-Accept decision (EMB-17-004):
:class:`ApplyInviteExpiryNoopFromLedgerNode` recognises the entry and
returns SUCCESS without applying any PEC transition.

For the honour late-Accept decision (EMB-17-001):
:class:`HonourLateAcceptNode` applies the honour after the commit, and
:class:`ApplyHonourLateAcceptFromLedgerNode` replays it on replicas.
"""

from datetime import datetime
from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.behaviors.sync.nodes._helpers import (
    _extract_id_from_field,
    _LedgerEffectNode,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.errors import VultronNotFoundError

IS_EXPIRED_KEY = "is_expired"
"""``result_out`` key: the invite's deadline has passed and the invite is unanswered."""

NEEDS_APPLY_KEY = "needs_apply"
"""``result_out`` key: the invitee is still ``INVITED`` and EXPIRE needs to be applied.

Set by :class:`EvaluateInviteExpiryNode` (read-only assess).  The tree's
commit node runs when this is ``True``; after a successful commit
:class:`RecordInviteExpiryNode` applies ``INVITED → EXPIRED`` (CLP-10-006).
"""

CONSENT_CHANGED_KEY = NEEDS_APPLY_KEY
"""Backward-compatible alias for :data:`NEEDS_APPLY_KEY`."""


class EvaluateInviteExpiryNode(DataLayerActionWithPorts):
    """Read-only assessment of whether an RSVP deadline has passed.

    Calls the **read-only**
    :meth:`~vultron.core.services.embargo_lifecycle.EmbargoLifecycle.assess_invite_expiry`
    and writes its outcome to *result_out*:

    * :data:`IS_EXPIRED_KEY` — ``True`` when the deadline passed and the
      participant is not a signatory to the active embargo.  Used by EMB-17 routing.
    * :data:`NEEDS_APPLY_KEY` — ``True`` when the invitee is still ``INVITED``
      and the commit + effect nodes need to run.

    This node makes **no writes** (CLP-10-006 guard role).
    Placed only behind the CASE_MANAGER gate (CM-28-014, BT-17-001).
    """

    def __init__(
        self,
        case_id: str,
        invitee_id: str,
        now: datetime,
        result_out: dict[str, Any],
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._invitee_id = invitee_id
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
    """Condition: the preceding assessment found an unexpired EXPIRE to apply.

    SUCCESS when :class:`EvaluateInviteExpiryNode` found the invitee still
    ``INVITED`` with a passed deadline — the one outcome that requires a
    ledger entry and a subsequent :class:`RecordInviteExpiryNode` (CM-28-009,
    CLP-10-006).
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


#: Backward-compatible alias for :class:`InviteExpiryNeedsApplyNode`.
InviteExpiryChangedConsentNode = InviteExpiryNeedsApplyNode


class RecordInviteExpiryNode(DataLayerActionWithPorts):
    """Apply PEC ``EXPIRE`` (``INVITED → EXPIRED``) after the commit.

    This is the **effect** node (CLP-10-006, BT-06-006).  It calls
    :meth:`~vultron.core.services.embargo_lifecycle.EmbargoLifecycle.record_invite_expiry`
    only **after** the commit node has persisted the ledger entry, so a
    failed commit leaves the invitee unchanged.
    """

    def __init__(
        self,
        case_id: str,
        invitee_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._invitee_id = invitee_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        try:
            result = EmbargoLifecycle(
                persistence=self.datalayer
            ).record_invite_expiry(
                case_id=self._case_id,
                actor_id=self._invitee_id,
            )
        except VultronNotFoundError as exc:
            self.feedback_message = str(exc)
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        self.feedback_message = (
            f"Applied invite expiry of '{self._invitee_id}'"
            f" on case '{self._case_id}'"
            f" ({len(result.participant_changes)} consent row change(s))"
        )
        if result.participant_changes:
            self.logger.info("%s: %s", self.name, self.feedback_message)
        else:
            self.logger.debug("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class ApplyInviteExpiryFromLedgerNode(_LedgerEffectNode):
    """Replay the CASE_MANAGER's expiry entry on a replica (CM-28-014, ADR-0118).

    The entry's ``actor`` is the expired invitee (the snapshot is attributed to
    it, CM-28-009); the replica applies ``EXPIRE`` (``INVITED → EXPIRED``)
    idempotently — only from ``INVITED``, any other state is left unchanged —
    and evaluates no deadline of its own.
    Regime 2 (ADR-0087): a replica holding no copy of the case, or no record
    of the invitee, skips with SUCCESS.  An entry that names no invitee fails,
    so it is not persisted as applied (SYNC-12-001).
    """

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        entry = self._get_entry()
        case = self._resolve_case_replica(entry.case_id)
        if case is None:
            return Status.SUCCESS  # Regime 2 (ADR-0087): partial replica
        invitee_id = _extract_id_from_field(
            entry.payload_snapshot.get("actor")
        )
        if not invitee_id:
            self.feedback_message = (
                f"expiry entry on case '{case.id_}' names no invitee"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        participant_id = case.actor_participant_index.get(invitee_id)
        if not participant_id:
            self.feedback_message = (
                f"no participant record for '{invitee_id}' on case"
                f" '{case.id_}' — skipping (partial replica)"
            )
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS
        participant = self.datalayer.read(participant_id)
        if not isinstance(participant, CaseParticipant):
            self.feedback_message = (
                f"participant id '{participant_id}' for '{invitee_id}' on"
                f" case '{case.id_}' is not a CaseParticipant — skipping"
            )
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS
        # The same operation the CASE_MANAGER ran after its commit: every row
        # still INVITED expires, and nothing else moves.
        changes = (
            EmbargoLifecycle(persistence=self.datalayer)
            .record_invite_expiry(case_id=case.id_, actor_id=invitee_id)
            .participant_changes
        )
        self.feedback_message = (
            f"Replayed invite expiry of '{invitee_id}' on case '{case.id_}'"
            f" ({len(changes)} consent row change(s))"
        )
        if changes:
            self.logger.info("%s: %s", self.name, self.feedback_message)
        else:
            self.logger.debug("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class ApplyInviteExpiryNoopFromLedgerNode(_LedgerEffectNode):
    """Replay the CASE_MANAGER's no-op expiry entry on a replica (EMB-17-004).

    The entry records that the CASE_MANAGER received a late ``Accept`` when
    no embargo was active (EM EXITED or NONE), acknowledged it, and made no
    PEC change (EMB-17-004, ADR-0118).  The replay node recognises the entry
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
        invitee_id = _extract_id_from_field(
            entry.payload_snapshot.get("actor")
        )
        self.feedback_message = (
            f"Replayed no-op expiry ack for"
            f" '{invitee_id or '(unknown)'}' on case '{case.id_}'"
        )
        self.logger.debug("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class HonourLateAcceptNode(DataLayerActionWithPorts):
    """Apply the CASE_MANAGER's honour decision after the commit (EMB-17-001).

    This is the **effect** node in
    :func:`~vultron.core.behaviors.embargo.expiry_tree.create_honour_late_accept_tree`.
    Called after the ledger entry is committed, it applies
    ``EXPIRED → ACCEPTED`` (or ``DECLINED → INVITED → ACCEPTED``) by
    delegating to
    :meth:`~vultron.core.services.embargo_lifecycle.EmbargoLifecycle.honour_late_accept`
    (CLP-10-006, BT-06-006, EMB-17-001, ADR-0118).
    """

    def __init__(
        self,
        case_id: str,
        actor_id: str,
        embargo_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._actor_id = actor_id
        self._embargo_id = embargo_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        try:
            result = EmbargoLifecycle(
                persistence=self.datalayer
            ).honour_late_accept(
                case_id=self._case_id,
                actor_id=self._actor_id,
                embargo_id=self._embargo_id,
            )
        except VultronNotFoundError as exc:
            self.feedback_message = str(exc)
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        self.feedback_message = (
            f"Honoured late Accept for '{self._actor_id}'"
            f" on case '{self._case_id}' (embargo '{self._embargo_id}',"
            f" {len(result.participant_changes)} consent row change(s))"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class ApplyHonourLateAcceptFromLedgerNode(_LedgerEffectNode):
    """Replay the CASE_MANAGER's honour decision on a replica (EMB-17-001).

    The entry's ``actor`` is the accepted participant; the entry's ``object``
    carries the Invite's id and the embargo's id.  The replica applies
    ``EXPIRED → ACCEPTED`` (or ``DECLINED → INVITED → ACCEPTED``) by
    calling
    :meth:`~vultron.core.services.embargo_lifecycle.EmbargoLifecycle.honour_late_accept`.
    Regime 2 (ADR-0087): a replica holding no copy of the case skips with
    SUCCESS.  An entry that names no actor or embargo fails (SYNC-12-001).
    """

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        entry = self._get_entry()
        case = self._resolve_case_replica(entry.case_id)
        if case is None:
            return Status.SUCCESS  # Regime 2 (ADR-0087): partial replica
        actor_id = _extract_id_from_field(entry.payload_snapshot.get("actor"))
        obj = entry.payload_snapshot.get("object") or {}
        embargo_obj = obj.get("object") or {}
        embargo_id = _extract_id_from_field(embargo_obj)
        if not actor_id or not embargo_id:
            self.feedback_message = (
                f"honour-late-accept entry on case '{case.id_}'"
                f" is missing actor ('{actor_id}') or"
                f" embargo id ('{embargo_id}')"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        participant_id = case.actor_participant_index.get(actor_id)
        if not participant_id:
            self.feedback_message = (
                f"no participant record for '{actor_id}' on case"
                f" '{case.id_}' — skipping (partial replica)"
            )
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS
        try:
            result = EmbargoLifecycle(
                persistence=self.datalayer
            ).honour_late_accept(
                case_id=entry.case_id,
                actor_id=actor_id,
                embargo_id=embargo_id,
            )
        except VultronNotFoundError as exc:
            self.feedback_message = str(exc)
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        self.feedback_message = (
            f"Replayed honour-late-accept for '{actor_id}'"
            f" on case '{case.id_}' (embargo '{embargo_id}',"
            f" {len(result.participant_changes)} consent row change(s))"
        )
        if result.participant_changes:
            self.logger.info("%s: %s", self.name, self.feedback_message)
        else:
            self.logger.debug("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


__all__ = [
    "CONSENT_CHANGED_KEY",
    "IS_EXPIRED_KEY",
    "NEEDS_APPLY_KEY",
    "ApplyHonourLateAcceptFromLedgerNode",
    "ApplyInviteExpiryFromLedgerNode",
    "ApplyInviteExpiryNoopFromLedgerNode",
    "EvaluateInviteExpiryNode",
    "HonourLateAcceptNode",
    "InviteExpiryChangedConsentNode",
    "InviteExpiryNeedsApplyNode",
    "RecordInviteExpiryNode",
]
