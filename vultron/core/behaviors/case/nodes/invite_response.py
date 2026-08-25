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

from vultron.core.behaviors.helpers import _EmitSingleActivityBase

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

    def _call_factory(self) -> tuple[str, dict]:
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        return self.trigger_activity_factory.accept_case_invite(
            invite_id=self.invite_id,
            actor=self.actor_id,
        )

    def _on_success(self, activity_id: str, activity_dict: dict) -> None:
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

    def _call_factory(self) -> tuple[str, dict]:
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        return self.trigger_activity_factory.reject_case_invite(
            invite_id=self.invite_id,
            actor=self.actor_id,
        )

    def _on_success(self, activity_id: str, activity_dict: dict) -> None:
        self.logger.info(
            "Actor '%s' rejected case invite '%s'",
            self.actor_id,
            self.invite_id,
        )
