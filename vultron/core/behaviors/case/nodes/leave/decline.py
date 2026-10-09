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

"""Declining an owner close that a live embargo forbids (CM-23-011)."""

import logging

from vultron.core.behaviors.helpers import _EmitSingleActivityBase

logger = logging.getLogger(__name__)


_ACTIVE_EMBARGO_DECLINE = "owner close declined: active embargo (CM-23-011)"
"""The default ``decline_reason``: the CM-23-011 owner-close decline."""

LATE_LEAVE_DECLINE = (
    "Leave declined: the case is fully closed and records nothing (CM-23-013)"
)
"""The ``decline_reason`` of the post-close reply to a late Leave."""


class EmitRejectCloseCaseNode(_EmitSingleActivityBase):
    """Emit a ``Reject(Leave(VulnerabilityCase))`` declining a Leave.

    Per CM-23-011, when the Case Owner sends ``Leave(VulnerabilityCase)`` while
    the case still holds an active embargo, the Case Actor declines the closure
    with an ``as:Reject`` ("received and understood but declined", MSM-05-001)
    instead of running the CM-23-002 closure sequence.  The decline is sent
    back to the owner (``close_sender_id``) and threaded to the received Leave
    via ``in_reply_to``.

    The same reply answers a ``Leave`` that arrives after
    ``case_fully_closed`` when the CASE_MANAGER's ``post_close_reply`` policy
    is ``REJECT`` (CM-23-013, ADR-0131); ``decline_reason`` names which
    decline it is in the log.

    Subclasses :class:`_EmitSingleActivityBase`; only ``_call_factory`` is
    overridden (BTND-07-005, BTND-07-009).
    """

    def __init__(
        self,
        case_id: str,
        close_sender_id: str,
        close_activity_id: str | None = None,
        captured: dict | None = None,
        name: str | None = None,
        decline_reason: str = _ACTIVE_EMBARGO_DECLINE,
    ) -> None:
        super().__init__(captured=captured, name=name)
        self._case_id = case_id
        self._close_sender_id = close_sender_id
        self._close_activity_id = close_activity_id
        self._decline_reason = decline_reason

    def _call_factory(self) -> tuple[str, str]:
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        return self.trigger_activity_factory.reject_close_case(
            case_id=self._case_id,
            actor=self.actor_id,
            close_sender=self._close_sender_id,
            in_reply_to=self._close_activity_id,
        )

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        self.logger.info(
            "Case actor '%s' sent as:Reject to '%s' for case '%s' — %s",
            self.actor_id,
            self._close_sender_id,
            self._case_id,
            self._decline_reason,
        )
