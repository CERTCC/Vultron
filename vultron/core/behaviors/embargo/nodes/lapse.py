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

"""Invite lapse: the CASE_MANAGER evaluates it, a replica replays it (CM-28-014).

An embargo Invite carries the deadline its addressee must answer by
(CM-28-012), and the CASE_MANAGER recorded that deadline against the invitee
when it committed the Invite (CM-28-013).  Lapse is evaluated lazily, when the
manager next hears from the invitee — its late ``Accept`` — and only by the
manager (CM-28-003): :class:`EvaluateInviteLapseNode` runs behind the role
gate in :func:`~vultron.core.behaviors.embargo.lapse_tree.create_invite_lapse_tree`,
which commits the lapse entry (CM-28-009) and then applies it through
:class:`RecordInviteLapseNode`.  A participant replica never
reads a clock against a deadline; it applies the manager's decision from the
committed entry through :class:`ApplyInviteLapseFromLedgerNode`, reached from
``create_announce_log_entry_tree`` (RSH-08-004).
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
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.errors import VultronNotFoundError

IS_LAPSED_KEY = "is_lapsed"
"""``result_out`` key: the invite's deadline has passed and it is unanswered."""

DECLINES_KEY = "declines"
"""``result_out`` key: the invitee is still ``INVITED``, so the lapse declines it."""


class EvaluateInviteLapseNode(DataLayerActionWithPorts):
    """Read whether an invitee's RSVP deadline has passed; write nothing.

    Delegates to :meth:`EmbargoLifecycle.assess_invite_lapse` and writes its
    outcome to *result_out*: :data:`IS_LAPSED_KEY` routes the late answer
    (EMB-17), :data:`DECLINES_KEY` decides whether the lapse entry is
    committed and then applied (CM-28-009).  The node is a guard: the
    ``DECLINE`` is :class:`RecordInviteLapseNode`'s, after the commit
    (CLP-10-006), so a failed commit leaves the invitee ``INVITED`` and a
    redelivery commits the lapse rather than reading it as recorded.
    Placed only behind the CASE_MANAGER gate (CM-28-014).
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
        self._result_out[IS_LAPSED_KEY] = False
        self._result_out[DECLINES_KEY] = False
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        try:
            assessment = EmbargoLifecycle(
                persistence=self.datalayer
            ).assess_invite_lapse(
                case_id=self._case_id,
                actor_id=self._invitee_id,
                now=self._now,
            )
        except VultronNotFoundError as exc:
            self.feedback_message = str(exc)
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        self._result_out[IS_LAPSED_KEY] = assessment.is_lapsed
        self._result_out[DECLINES_KEY] = assessment.declines
        self.feedback_message = (
            f"invite of '{self._invitee_id}' on case '{self._case_id}'"
            f" {'lapsed' if assessment.is_lapsed else 'still open'}"
        )
        self.logger.debug("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class InviteLapseDeclinesNode(py_trees.behaviour.Behaviour):
    """Condition: the preceding evaluation found a lapse still to apply.

    SUCCESS when :class:`EvaluateInviteLapseNode` found the invitee
    ``INVITED`` past its deadline, the one outcome a lapse entry records
    (CM-28-009).
    """

    def __init__(
        self, result_out: dict[str, Any], name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._result_out = result_out

    def update(self) -> Status:
        if self._result_out.get(DECLINES_KEY):
            return Status.SUCCESS
        return Status.FAILURE


class RecordInviteLapseNode(DataLayerActionWithPorts):
    """Apply the committed lapse in the CASE_MANAGER's own store.

    Runs after the lapse entry's commit and applies the same ``DECLINE`` a
    replica applies from that entry, through
    :meth:`EmbargoLifecycle.record_invite_lapse` (CM-28-014).  Regime 1
    (ADR-0087): :class:`EvaluateInviteLapseNode` has just read this record,
    so its absence is the manager's own fault and raises as an internal
    error rather than reading as the sender's (ADR-0095).
    """

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
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
            ).record_invite_lapse(
                case_id=self._case_id, actor_id=self._invitee_id
            )
        except VultronNotFoundError as exc:
            raise RuntimeError(
                f"{self.name}: the lapse of '{self._invitee_id}' on case"
                f" '{self._case_id}' is in the ledger but its participant"
                f" record cannot be read: {exc}"
            ) from exc
        self.feedback_message = (
            f"Applied invite lapse of '{self._invitee_id}' on case"
            f" '{self._case_id}' ({len(result.participant_changes)} PEC state"
            " change(s))"
        )
        self.logger.debug("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class ApplyInviteLapseFromLedgerNode(_LedgerEffectNode):
    """Replay the CASE_MANAGER's lapse entry on a replica (CM-28-014).

    The entry's ``actor`` is the lapsed invitee (the snapshot is attributed to
    it, CM-28-009); the replica applies the same ``DECLINE`` through
    :meth:`EmbargoLifecycle.record_invite_lapse`, idempotently, and evaluates
    no deadline of its own.  Regime 2 (ADR-0087): a replica holding no copy of
    the case, or no record of the invitee, skips with SUCCESS.  An entry that
    names no invitee fails, so it is not persisted as applied (SYNC-12-001).
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
                f"lapse entry on case '{case.id_}' names no invitee"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        try:
            result = EmbargoLifecycle(
                persistence=self.datalayer
            ).record_invite_lapse(case_id=case.id_, actor_id=invitee_id)
        except VultronNotFoundError:
            self.feedback_message = (
                f"no participant record for '{invitee_id}' on case"
                f" '{case.id_}' — skipping (partial replica)"
            )
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS
        self.feedback_message = (
            f"Replayed invite lapse of '{invitee_id}' on case '{case.id_}'"
            f" ({len(result.participant_changes)} PEC state change(s))"
        )
        if result.participant_changes:
            self.logger.info("%s: %s", self.name, self.feedback_message)
        else:
            self.logger.debug("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


__all__ = [
    "DECLINES_KEY",
    "IS_LAPSED_KEY",
    "ApplyInviteLapseFromLedgerNode",
    "EvaluateInviteLapseNode",
    "InviteLapseDeclinesNode",
    "RecordInviteLapseNode",
]
