#!/usr/bin/env python
#
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
"""Condition nodes for SYNC log-replication workflows."""

from __future__ import annotations

import logging
from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerCondition
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.sync_helpers import is_ledger_fresh_for_case
from vultron.errors import VultronError

logger = logging.getLogger(__name__)


def _find_case_actor(
    dl: CasePersistence, case_id: str, owner_actor_id: str | None = None
) -> object | None:
    fallback: object | None = None
    for service in dl.list_objects("Service"):
        if fallback is None:
            fallback = service
        if getattr(service, "context", None) != case_id:
            continue
        if owner_actor_id is None:
            return service
        if getattr(service, "attributed_to", None) == owner_actor_id:
            return service
    if owner_actor_id is None:
        return fallback
    return None


def _require_log_entry(
    activity: Any, node_name: str
) -> VultronCaseLedgerEntry:
    entry = getattr(activity, "log_entry", None)
    if entry is None:
        entry = getattr(activity, "object_", None)
    if isinstance(entry, CaseLedgerEntry):
        if isinstance(entry, VultronCaseLedgerEntry):
            return entry
        return VultronCaseLedgerEntry.model_validate(
            entry.model_dump(mode="json")
        )
    raise VultronError(
        f"{node_name}: activity did not carry a VultronCaseLedgerEntry"
    )


def _require_case_actor_id(case_actor: object, node_name: str) -> str:
    case_actor_id = getattr(case_actor, "id_", None)
    if isinstance(case_actor_id, str):
        return case_actor_id
    raise VultronError(f"{node_name}: resolved CaseActor had no id_")


class CheckIsOwnCaseActorNode(DataLayerCondition):
    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="case_actor_id", access=py_trees.common.Access.WRITE
        )

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        entry = _require_log_entry(self.blackboard.activity, self.name)
        case_actor = _find_case_actor(
            self.datalayer, entry.case_id, self.actor_id
        )
        if case_actor is None:
            return Status.FAILURE

        case_actor_id = _require_case_actor_id(case_actor, self.name)
        self.blackboard.case_actor_id = case_actor_id
        self.logger.debug(
            "%s: actor '%s' owns CaseActor '%s' for case '%s'",
            self.name,
            self.actor_id,
            case_actor_id,
            entry.case_id,
        )
        return Status.SUCCESS


class CheckIsNotOwnCaseActorNode(DataLayerCondition):
    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        entry = _require_log_entry(self.blackboard.activity, self.name)
        case_actor = _find_case_actor(
            self.datalayer, entry.case_id, self.actor_id
        )
        if case_actor is None:
            return Status.SUCCESS
        return Status.FAILURE


class VerifySenderIsOwnIdNode(DataLayerCondition):
    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="case_actor_id", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        sender_id = getattr(self.blackboard.activity, "actor_id", None)
        case_actor_id = self.blackboard.case_actor_id
        if sender_id == case_actor_id:
            return Status.SUCCESS

        self.logger.warning(
            "%s: rejected spoofed announce sender '%s' for CaseActor '%s'",
            self.name,
            sender_id,
            case_actor_id,
        )
        return Status.FAILURE


class CheckLedgerEntryAlreadyStoredNode(DataLayerCondition):
    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        entry = _require_log_entry(self.blackboard.activity, self.name)
        if self.datalayer.read(entry.id_) is None:
            return Status.FAILURE

        self.logger.debug(
            "%s: log entry '%s' already stored", self.name, entry.id_
        )
        return Status.SUCCESS


_REMOVE_EMBARGO_EVENT = "remove_embargo_event_from_case"
_ADD_PARTICIPANT_STATUS_EVENT = "add_participant_status_to_participant"
_ADD_NOTE_TO_CASE_EVENT = "add_note_to_case"
_ACCEPT_INVITE_ACTOR_TO_CASE_EVENT = "accept_invite_actor_to_case"


class IsRemoveEmbargoEventNode(DataLayerCondition):
    """Precondition: return SUCCESS when this log entry IS a remove-embargo event.

    Used as the precondition in the ``EmbargoEffects`` Selector's inner
    Sequence in ``AnnounceLogEntryReceivedBT``::

        Selector(EmbargoEffects)
          Sequence
            IsRemoveEmbargoEventNode   ← SUCCESS iff event_type matches
            ApplyEmbargoTeardownNode
          Inverter(IsRemoveEmbargoEventNode)  ← SUCCESS iff wrong event type

    The Inverter fires SUCCESS only when the condition does NOT match (routing
    no-op for the wrong event type).  When the condition matches but
    ApplyEmbargoTeardownNode fails, both branches of the Selector fail and
    the FAILURE propagates to block PersistReceivedLogEntry (SYNC-12-001).

    Per BTND-08-001, BTND-08-002, BT-06-001, SYNC-12-001.
    """

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        entry = _require_log_entry(self.blackboard.activity, self.name)
        if entry.event_type == _REMOVE_EMBARGO_EVENT:
            return Status.SUCCESS
        return Status.FAILURE


class IsParticipantStatusEventNode(DataLayerCondition):
    """Precondition: return SUCCESS when this log entry IS a participant-status event.

    Used as the precondition in the ``ParticipantStatusEffects`` Selector's
    inner Sequence in ``AnnounceLogEntryReceivedBT``::

        Selector(ParticipantStatusEffects)
          Sequence
            IsParticipantStatusEventNode   ← SUCCESS iff event_type matches
            ApplyParticipantStatusFromLedgerNode
          Inverter(IsParticipantStatusEventNode)  ← SUCCESS iff wrong event type

    The Inverter fires SUCCESS only when the condition does NOT match (routing
    no-op for the wrong event type).  When the condition matches but
    ApplyParticipantStatusFromLedgerNode fails, both branches of the Selector
    fail and the FAILURE propagates to block PersistReceivedLogEntry (SYNC-12-001).

    Per BTND-08-001, BTND-08-002, DEMOMA-07-003 step 3, SYNC-12-001.
    """

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        entry = _require_log_entry(self.blackboard.activity, self.name)
        if entry.event_type == _ADD_PARTICIPANT_STATUS_EVENT:
            return Status.SUCCESS
        return Status.FAILURE


class IsAddNoteEventNode(DataLayerCondition):
    """Precondition: return SUCCESS when this log entry IS an add-note event.

    Used as the precondition in the ``NoteEffects`` Selector's inner
    Sequence in ``AnnounceLogEntryReceivedBT``::

        Selector(NoteEffects)
          Sequence
            IsAddNoteEventNode   ← SUCCESS iff event_type matches
            ApplyNoteFromLedgerNode
          Inverter(IsAddNoteEventNode)  ← SUCCESS iff wrong event type

    The Inverter fires SUCCESS only when the condition does NOT match (routing
    no-op for the wrong event type).  When the condition matches but
    ApplyNoteFromLedgerNode fails, both branches of the Selector fail and
    the FAILURE propagates to block PersistReceivedLogEntry (SYNC-12-001).

    Per BTND-08-001, BTND-08-002, SYNC-02-002, SYNC-12-001.
    """

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        entry = _require_log_entry(self.blackboard.activity, self.name)
        if entry.event_type == _ADD_NOTE_TO_CASE_EVENT:
            return Status.SUCCESS
        return Status.FAILURE


class IsInviteAcceptEventNode(DataLayerCondition):
    """Precondition: return SUCCESS when this log entry IS an accept-invite event.

    Used as the precondition in the ``InviteAcceptEffects`` Selector's inner
    Sequence in ``AnnounceLogEntryReceivedBT``::

        Selector(InviteAcceptEffects)
          Sequence
            IsInviteAcceptEventNode   ← SUCCESS iff event_type matches
            ApplyInviteAcceptFromLedgerNode
          Inverter(IsInviteAcceptEventNode)  ← SUCCESS iff wrong event type

    The Inverter fires SUCCESS only when the condition does NOT match (routing
    no-op for the wrong event type).  When the condition matches but
    ApplyInviteAcceptFromLedgerNode fails, both branches of the Selector fail
    and the FAILURE propagates to block PersistReceivedLogEntry (SYNC-12-001).

    Per BTND-08-001, BTND-08-002, SYNC-02-002, DEMOMA-07-003, SYNC-12-001.
    """

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        entry = _require_log_entry(self.blackboard.activity, self.name)
        if entry.event_type == _ACCEPT_INVITE_ACTOR_TO_CASE_EVENT:
            return Status.SUCCESS
        return Status.FAILURE


class CheckLedgerFreshnessNode(DataLayerCondition):
    """Gate: return SUCCESS only when the local ledger for *case_id* is fresh.

    "Fresh" means the actor's local ledger entries for the case form a
    contiguous, hash-verified sequence from ``log_index=0``
    (``prev_log_hash == <per-case genesis hash>``) through the actor's highest
    stored entry.  The actor does **not** need to be at the CaseActor's current
    tip — lagging is permitted so long as the local prefix has no gaps.

    An empty local ledger is trivially fresh (the acknowledged prefix is the
    empty prefix).

    When the gate fails (not fresh), a WARNING is emitted that includes the
    staleness reason, surfacing the explicit stale-or-catching-up condition
    required by SYNC-10-002.  This FAILURE result blocks or defers any
    protocol-significant case action that depends on ledger freshness per
    SYNC-10-001.

    Constructor args:
        case_id: URI of the case whose ledger to check.  If ``None``, the
            node reads ``case_id`` from the blackboard key ``"case_id"``.

    Spec: SYNC-10-001, SYNC-10-002, SYNC-10-003, SYNC-10-004, SYNC-10-005.
    """

    def __init__(
        self, case_id: str | None = None, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        if self._case_id is None:
            self.blackboard.register_key(
                key="case_id", access=py_trees.common.Access.READ
            )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        if self._case_id is not None:
            case_id = self._case_id
        else:
            try:
                case_id = self.blackboard.case_id
            except KeyError:
                self.logger.error(
                    "%s: case_id not on blackboard and not provided at "
                    "construction",
                    self.name,
                )
                return Status.FAILURE

        fresh, reason = is_ledger_fresh_for_case(case_id, self.datalayer)
        if not fresh:
            self.logger.warning(
                "%s: ledger NOT fresh for case '%s' — stale-or-catching-up: %s",
                self.name,
                case_id,
                reason,
            )
            return Status.FAILURE

        self.logger.debug("%s: ledger fresh for case '%s'", self.name, case_id)
        return Status.SUCCESS
