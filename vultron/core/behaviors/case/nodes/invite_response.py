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

"""Invite-response emit nodes for case behavior trees.

Provides the Accept and Reject leaf action nodes that emit outbound
activities in response to an incoming case invitation.

Extracted from ``actor.py`` per BTND-07-004 (500-line leaf-module limit).
Composite subtrees assembling these nodes are defined in
``actor_trigger_trees.py``:

- ``accept_case_invite_trigger_bt``
- ``reject_case_invite_trigger_bt``
"""

import logging
from typing import cast

from vultron.core.behaviors.helpers import _EmitSingleActivityBase
from vultron.core.models.ledger_position import LedgerPosition

logger = logging.getLogger(__name__)


class EmitAcceptCaseInviteNode(_EmitSingleActivityBase):
    """Create Accept(Invite) and queue in the invitee's outbox.

    Uses ``trigger_activity_factory.accept_case_invite()`` — the factory
    derives the recipient from the persisted invite object.
    """

    def __init__(
        self,
        invite_id: str,
        captured: dict | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(captured=captured, name=name)
        self.invite_id = invite_id

    def _call_factory(self) -> tuple[str, str]:
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        return self.trigger_activity_factory.accept_case_invite(
            invite_id=self.invite_id,
            actor=self.actor_id,
        )

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        self.logger.info(
            "Actor '%s' accepted case invite '%s'",
            self.actor_id,
            self.invite_id,
        )


class EmitRejectCaseInviteNode(_EmitSingleActivityBase):
    """Create Reject(Invite) and queue in the invitee's outbox.

    Uses ``trigger_activity_factory.reject_case_invite()`` — the factory
    derives the recipient from the persisted invite object.
    """

    def __init__(
        self,
        invite_id: str,
        captured: dict | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(captured=captured, name=name)
        self.invite_id = invite_id

    def _call_factory(self) -> tuple[str, str]:
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        return self.trigger_activity_factory.reject_case_invite(
            invite_id=self.invite_id,
            actor=self.actor_id,
        )

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        self.logger.info(
            "Actor '%s' rejected case invite '%s'",
            self.actor_id,
            self.invite_id,
        )


class _EmitFullCaseInviteReplyNode(_EmitSingleActivityBase):
    """Create a reply to the full-case Invite and queue it in the outbox.

    The reply carries the replier's own ledger position (CM-11-011); the
    factory derives the recipient from the persisted Invite.  Subclasses name
    the ``TriggerActivityPort`` method that builds their reply.
    """

    factory_method: str

    def __init__(
        self,
        invite_id: str,
        position: LedgerPosition,
        captured: dict | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(captured=captured, name=name)
        self.invite_id = invite_id
        self.position = position

    def _call_factory(self) -> tuple[str, str]:
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        build = getattr(self.trigger_activity_factory, self.factory_method)
        return cast(
            tuple[str, str],
            build(
                invite_id=self.invite_id,
                actor=self.actor_id,
                ledger_log_index=self.position.log_index,
                ledger_entry_hash=self.position.entry_hash,
            ),
        )

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        self.logger.info(
            "Actor '%s' answered full-case invite '%s' with '%s'"
            " at ledger position %d",
            self.actor_id,
            self.invite_id,
            self.factory_method,
            self.position.log_index,
        )


class EmitAcceptFullCaseInviteNode(_EmitFullCaseInviteReplyNode):
    """Create ``Accept(full-case Invite)`` — RV (VAM-04-012)."""

    factory_method = "accept_full_case_invite"


class EmitTentativeRejectFullCaseInviteNode(_EmitFullCaseInviteReplyNode):
    """Create ``TentativeReject(full-case Invite)`` — RI (VAM-04-013)."""

    factory_method = "tentative_reject_full_case_invite"


class EmitRejectFullCaseInviteNode(_EmitFullCaseInviteReplyNode):
    """Create ``Reject(full-case Invite)`` — RC (VAM-04-014)."""

    factory_method = "reject_full_case_invite"
