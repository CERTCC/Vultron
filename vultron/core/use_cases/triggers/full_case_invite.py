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

"""Trigger use cases that answer the full-case Invite (ADR-0121, CM-11-011).

No HTTP framework imports permitted here.
"""

import logging
from typing import cast

import py_trees.behaviour

from vultron.core.behaviors.case.actor_trigger_trees import (
    full_case_invite_reply_trigger_bt,
)
from vultron.core.behaviors.case.nodes.full_case_invite import (
    stored_invite_floor,
)
from vultron.core.behaviors.case.nodes.invite_response import (
    EmitAcceptFullCaseInviteNode,
    EmitRejectFullCaseInviteNode,
    EmitTentativeRejectFullCaseInviteNode,
)
from vultron.core.models._helpers import _as_id
from vultron.core.sync_helpers import (
    is_ledger_fresh_for_case,
    ledger_tail_position,
)
from vultron.core.use_cases._helpers import read_received_activity
from vultron.core.use_cases.triggers._base import SvcActivityTriggerBase
from vultron.core.use_cases.triggers._helpers import resolve_actor
from vultron.core.use_cases.triggers.requests import (
    AcceptFullCaseInviteTriggerRequest,
)
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronValidationError,
)

logger = logging.getLogger(__name__)


class _SvcFullCaseInviteReplyBase(SvcActivityTriggerBase):
    """Answer the full-case Invite with a judgement carrying this actor's position.

    The participant reads the Invite as it holds it, and fails closed until
    its own copy of the ledger is contiguous from genesis and has reached the
    Invite's floor (SYNC-10-004, CM-11-012): the reply's position is the tail
    of that copy, so it can never be behind the floor.  Subclasses name the
    emit node.
    """

    emit_node: type[
        EmitAcceptFullCaseInviteNode
        | EmitTentativeRejectFullCaseInviteNode
        | EmitRejectFullCaseInviteNode
    ]

    def _prepare(self) -> None:
        request = cast(AcceptFullCaseInviteTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_
        held = read_received_activity(
            self._dl, request.invite_id, "full-case Invite"
        )
        floor = stored_invite_floor(held)
        case_id = _as_id(getattr(held, "target", None))
        if floor is None or case_id is None:
            raise VultronValidationError(
                f"'{request.invite_id}' is not a full-case Invite: it names"
                " no case or carries no ledger position (CM-11-010)"
            )
        fresh, reason = is_ledger_fresh_for_case(case_id, self._dl)
        if not fresh:
            raise VultronInvalidStateTransitionError(
                f"ledger of case '{case_id}' has not caught up to the"
                f" Invite's position {floor.log_index} ({reason});"
                " retry once replication catches up (SYNC-10-004)"
            )
        try:
            position = ledger_tail_position(case_id, self._dl)
        except VultronValidationError as exc:
            raise VultronInvalidStateTransitionError(
                f"ledger of case '{case_id}' has not caught up to the"
                f" Invite's position {floor.log_index} ({exc});"
                " retry once replication catches up (SYNC-10-004)"
            ) from exc
        if position.log_index < floor.log_index:
            raise VultronInvalidStateTransitionError(
                f"ledger of case '{case_id}' has not caught up to the"
                f" Invite's position {floor.log_index} (holds"
                f" {position.log_index}); retry once replication catches up"
                " (SYNC-10-004)"
            )
        self._invite_id = request.invite_id
        self._position = position

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return full_case_invite_reply_trigger_bt(
            self.emit_node,
            invite_id=self._invite_id,
            position=self._position,
            captured=self._captured,
        )

    def _handle_result(self) -> None:
        logger.info(
            "Actor '%s' answered full-case invite '%s' (%s)",
            self._actor_id,
            self._invite_id,
            self.emit_node.__name__,
        )


class SvcAcceptFullCaseInviteUseCase(_SvcFullCaseInviteReplyBase):
    """Judge the case valid: ``Accept(full-case Invite)`` — RV."""

    emit_node = EmitAcceptFullCaseInviteNode


class SvcTentativeRejectFullCaseInviteUseCase(_SvcFullCaseInviteReplyBase):
    """Judge the case invalid: ``TentativeReject(full-case Invite)`` — RI."""

    emit_node = EmitTentativeRejectFullCaseInviteNode


class SvcRejectFullCaseInviteUseCase(_SvcFullCaseInviteReplyBase):
    """Close the case: ``Reject(full-case Invite)`` — RC."""

    emit_node = EmitRejectFullCaseInviteNode
