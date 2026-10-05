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
CM-28-014, BT-17-001).  :class:`EvaluateInviteExpiryNode` calls
:meth:`~vultron.core.services.embargo_lifecycle.EmbargoLifecycle.detect_and_apply_expiry`,
writing the outcome to *result_out* so the surrounding tree can commit the
ledger entry and the ``execute()`` caller can branch on it.
:class:`InviteExpiryChangedConsentNode` is the inner condition that decides
whether a commit is needed (CM-28-009).

A participant replica never evaluates a deadline; it applies the manager's
decision from the committed entry through
:class:`ApplyInviteExpiryFromLedgerNode`, reached from
``create_announce_log_entry_tree`` (RSH-08-004, CM-28-014).

For the no-op late-Accept decision (EMB-17-004):
:class:`ApplyInviteExpiryNoopFromLedgerNode` recognises the entry and
returns SUCCESS without applying any PEC transition, so it is not
mis-routed.
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
from vultron.core.services.embargo_lifecycle.results import (
    ParticipantPECChange,
)
from vultron.core.states.participant_embargo_consent import PEC, PEC_Trigger
from vultron.errors import VultronNotFoundError

IS_EXPIRED_KEY = "is_expired"
"""``result_out`` key: the invite's deadline has passed and the invite is unanswered."""

CONSENT_CHANGED_KEY = "consent_changed"
"""``result_out`` key: this evaluation moved the invitee ``INVITED → EXPIRED``."""


class EvaluateInviteExpiryNode(DataLayerActionWithPorts):
    """Apply PEC ``EXPIRE`` to an invitee whose RSVP deadline has passed.

    Delegates to
    :meth:`EmbargoLifecycle.detect_and_apply_expiry` and writes its outcome
    to *result_out*: :data:`IS_EXPIRED_KEY` routes the late answer (EMB-17),
    :data:`CONSENT_CHANGED_KEY` decides whether a lapse entry is committed —
    an expiry already applied is not logged twice (CM-28-009).
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
        self._result_out[CONSENT_CHANGED_KEY] = False
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        try:
            result = EmbargoLifecycle(
                persistence=self.datalayer
            ).detect_and_apply_expiry(
                case_id=self._case_id,
                actor_id=self._invitee_id,
                now=self._now,
            )
        except VultronNotFoundError as exc:
            self.feedback_message = str(exc)
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        self._result_out[IS_EXPIRED_KEY] = result.is_expired
        self._result_out[CONSENT_CHANGED_KEY] = bool(
            result.participant_changes
        )
        self.feedback_message = (
            f"invite of '{self._invitee_id}' on case '{self._case_id}'"
            f" {'expired' if result.is_expired else 'still open'}"
        )
        self.logger.debug("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class InviteExpiryChangedConsentNode(py_trees.behaviour.Behaviour):
    """Condition: the preceding evaluation just applied expiry.

    SUCCESS when :class:`EvaluateInviteExpiryNode` moved the invitee to
    ``EXPIRED``, which is the one outcome an expiry entry records (CM-28-009).
    """

    def __init__(
        self, result_out: dict[str, Any], name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._result_out = result_out

    def update(self) -> Status:
        if self._result_out.get(CONSENT_CHANGED_KEY):
            return Status.SUCCESS
        return Status.FAILURE


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
        changes: list[ParticipantPECChange] = []
        if participant.embargo_consent_state == PEC.INVITED.value:
            pec_before = participant.embargo_consent_state
            participant.apply_pec_transition(PEC_Trigger.EXPIRE)
            self.datalayer.save(participant)
            changes.append(
                ParticipantPECChange(
                    participant_id=participant_id,
                    pec_before=pec_before,
                    pec_after=participant.embargo_consent_state,
                )
            )
        self.feedback_message = (
            f"Replayed invite expiry of '{invitee_id}' on case '{case.id_}'"
            f" ({len(changes)} PEC state change(s))"
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


__all__ = [
    "CONSENT_CHANGED_KEY",
    "IS_EXPIRED_KEY",
    "ApplyInviteExpiryFromLedgerNode",
    "ApplyInviteExpiryNoopFromLedgerNode",
    "EvaluateInviteExpiryNode",
    "InviteExpiryChangedConsentNode",
]
