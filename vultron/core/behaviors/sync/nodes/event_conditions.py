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
"""Event-type matcher condition nodes for SYNC log-replication.

Each ``Is*EventNode`` matches exactly one ``event_type`` string on the
blackboard ``activity.log_entry``.  They are used as preconditions in the
``AnnounceLogEntryReceivedBT`` Selector branches (BTND-08-001/002).
"""

from __future__ import annotations

from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerCondition
from vultron.core.behaviors.sync.nodes.conditions import _require_log_entry

_REMOVE_EMBARGO_EVENT = "remove_embargo_event_from_case"
_ADD_PARTICIPANT_STATUS_EVENT = "add_participant_status_to_participant"
_ADD_NOTE_TO_CASE_EVENT = "add_note_to_case"
_ACCEPT_INVITE_ACTOR_TO_CASE_EVENT = "accept_invite_actor_to_case"
_CLOSE_CASE_EVENT = "close_case"
_ADD_REPORT_TO_CASE_EVENT = "add_report_to_case"
_ACCEPT_CASE_OWNERSHIP_TRANSFER_EVENT = "accept_case_ownership_transfer"


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


class IsCloseCaseEventNode(DataLayerCondition):
    """Precondition: return SUCCESS when this log entry IS a close-case event.

    Used as the precondition in the ``CloseCaseEffects`` Selector's inner
    Sequence in ``AnnounceLogEntryReceivedBT``::

        Selector(CloseCaseEffects)
          Sequence
            IsCloseCaseEventNode   ← SUCCESS iff event_type matches
            ApplyCloseCaseFromLedgerNode
          Inverter(IsCloseCaseEventNode)  ← SUCCESS iff wrong event type

    The Inverter fires SUCCESS only when the condition does NOT match (routing
    no-op for the wrong event type).  When the condition matches but
    ApplyCloseCaseFromLedgerNode fails, both branches of the Selector fail and
    the FAILURE propagates to block PersistReceivedLogEntry (SYNC-12-001).

    Per BTND-08-001, BTND-08-002, CM-23-003, SYNC-12-001.
    """

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        entry = _require_log_entry(self.blackboard.activity, self.name)
        if entry.event_type == _CLOSE_CASE_EVENT:
            return Status.SUCCESS
        return Status.FAILURE


class IsSubmitReportEventNode(DataLayerCondition):
    """Precondition: return SUCCESS when this log entry IS an add_report_to_case event.

    Used as the precondition in the ``OfferReportEffects`` Selector's inner
    Sequence in ``AnnounceLogEntryReceivedBT``::

        Selector(OfferReportEffects)
          Sequence
            IsSubmitReportEventNode   ← SUCCESS iff event_type matches
            ApplyOfferReportFromLedgerNode
          Inverter(IsSubmitReportEventNode)  ← SUCCESS iff wrong event type

    The Inverter fires SUCCESS only when the condition does NOT match (routing
    no-op for the wrong event type).  When the condition matches but
    ApplyOfferReportFromLedgerNode fails, both branches of the Selector fail
    and the FAILURE propagates to block PersistReceivedLogEntry (SYNC-12-001).

    Per BTND-08-001, BTND-08-002, SYNC-02-002, ISSUE-2134.
    """

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        entry = _require_log_entry(self.blackboard.activity, self.name)
        if entry.event_type == _ADD_REPORT_TO_CASE_EVENT:
            return Status.SUCCESS
        return Status.FAILURE


class IsOwnershipTransferEventNode(DataLayerCondition):
    """Precondition: return SUCCESS when this log entry IS an ownership-transfer event.

    Used as the precondition in the ``OwnershipTransferEffects`` Selector's
    inner Sequence in ``AnnounceLogEntryReceivedBT``::

        Selector(OwnershipTransferEffects)
          Sequence
            IsOwnershipTransferEventNode   ← SUCCESS iff event_type matches
            ApplyOwnershipTransferFromLedgerNode
          Inverter(IsOwnershipTransferEventNode)  ← SUCCESS iff wrong event type

    The Inverter fires SUCCESS only when the condition does NOT match (routing
    no-op for the wrong event type).  When the condition matches but
    ApplyOwnershipTransferFromLedgerNode fails, both branches of the Selector
    fail and the FAILURE propagates to block PersistReceivedLogEntry
    (SYNC-12-001).

    Per BTND-08-001, BTND-08-002, CM-21-007, SYNC-02-002, SYNC-12-001.
    """

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        entry = _require_log_entry(self.blackboard.activity, self.name)
        if entry.event_type == _ACCEPT_CASE_OWNERSHIP_TRANSFER_EVENT:
            return Status.SUCCESS
        return Status.FAILURE
