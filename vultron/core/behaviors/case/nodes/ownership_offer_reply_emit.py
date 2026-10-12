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

"""Trigger-side emit nodes for the replies to an ownership-transfer Offer.

Provides:

- :class:`EmitAcceptCaseOwnershipTransferNode` — emits
  ``Accept(Offer(VulnerabilityCase))`` from the accepting actor to the
  CASE_MANAGER (CM-21-006).
- :class:`EmitRejectCaseOwnershipTransferNode` — emits
  ``Reject(Offer(VulnerabilityCase))`` from the declining actor to the
  CASE_MANAGER (CM-21-010).
- :class:`EmitWithdrawCaseOwnershipTransferNode` — emits
  ``Undo(Offer(VulnerabilityCase))`` from the offerer to the CASE_MANAGER
  (CM-21-015).

Split from ``ownership_transfer.py`` (BTND-07-004), which re-exports these
names.  The leaf nodes are assembled into trigger trees in
``actor_trigger_trees.py`` per BTND-07-003.
"""

from typing import ClassVar

from vultron.core.behaviors.helpers import _EmitSingleActivityBase
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.errors import VultronNotFoundError


class _EmitOwnershipAnswerNode(_EmitSingleActivityBase):
    """Emit a reply to an ownership-transfer Offer.

    The reply — the transferee's ``Accept`` or ``Reject`` of
    ``Offer(VulnerabilityCase)``, or the offerer's ``Undo`` of it — is
    addressed to the case's CASE_MANAGER, never to the other party: the
    CASE_MANAGER records the reply and broadcasts it (CM-21-006, CM-21-010,
    CM-21-015).  Subclasses name the port method that builds the activity
    (:meth:`_build_answer`) and the verb they log.
    """

    _verb: ClassVar[str]
    """Past-tense verb for the success log line; each subclass sets it."""

    def __init__(
        self,
        offer_id: str,
        case_id: str,
        captured: dict | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(captured=captured, name=name)
        self.offer_id = offer_id
        self.case_id = case_id

    def _build_answer(self, to: list[str] | None) -> tuple[str, str]:
        """Build and persist the answer through the trigger-activity port."""
        raise NotImplementedError

    def _call_factory(self) -> tuple[str, str]:
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        assert self.datalayer is not None
        # Regime 3 (ADR-0087): optional addressing enrichment only — a missing
        # local case leaves `to=None` and the answer is still emitted.
        # Unguarded by design (conformance allowlist).
        case = self.datalayer.read_case(self.case_id)
        case_actor_id: list[str] | None = None
        if case is not None:
            cm_id = resolve_case_manager_id(case, self.datalayer)
            if cm_id:
                case_actor_id = [cm_id]
        return self._build_answer(case_actor_id)

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        self.logger.info(
            "Actor '%s' %s case ownership transfer offer '%s'",
            self.actor_id,
            self._verb,
            self.offer_id,
        )


class EmitAcceptCaseOwnershipTransferNode(_EmitOwnershipAnswerNode):
    """Emit ``Accept(Offer(VulnerabilityCase))`` to the CASE_MANAGER.

    Calls ``trigger_activity_factory.accept_case_ownership_transfer()``
    with ``actor=self.actor_id`` and ``offer_id``, then queues the resulting
    activity in the actor's outbox (TRIG-11-002, CM-21-006).
    """

    _verb = "accepted"

    def _build_answer(self, to: list[str] | None) -> tuple[str, str]:
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        return self.trigger_activity_factory.accept_case_ownership_transfer(
            actor=self.actor_id, offer_id=self.offer_id, to=to
        )


class EmitRejectCaseOwnershipTransferNode(_EmitOwnershipAnswerNode):
    """Emit ``Reject(Offer(VulnerabilityCase))`` to the CASE_MANAGER.

    Calls ``trigger_activity_factory.reject_case_ownership_transfer()``
    with ``actor=self.actor_id`` and ``offer_id``, then queues the resulting
    activity in the actor's outbox (TRIG-11-005, CM-21-010).
    """

    _verb = "rejected"

    def _build_answer(self, to: list[str] | None) -> tuple[str, str]:
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        return self.trigger_activity_factory.reject_case_ownership_transfer(
            actor=self.actor_id, offer_id=self.offer_id, to=to
        )


class EmitWithdrawCaseOwnershipTransferNode(_EmitOwnershipAnswerNode):
    """Emit ``Undo(Offer(VulnerabilityCase))`` to the CASE_MANAGER.

    Calls ``trigger_activity_factory.withdraw_case_ownership_transfer()``
    with ``actor=self.actor_id`` and ``offer_id``, then queues the resulting
    activity in the actor's outbox (TRIG-11-006, CM-21-015).
    """

    _verb = "withdrew"

    def _build_answer(self, to: list[str] | None) -> tuple[str, str]:
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        if to is None:
            # No fallback: the stored Offer's ``actor`` is the offerer itself
            # when it sent the Offer directly, so the port's last-resort
            # addressing would send the withdrawal to its own sender.  A
            # withdrawal goes to the CASE_MANAGER or nowhere (CM-21-015,
            # PCR-08-011).
            raise VultronNotFoundError(
                "CASE_MANAGER", f"(for case '{self.case_id}')"
            )
        return self.trigger_activity_factory.withdraw_case_ownership_transfer(
            actor=self.actor_id, offer_id=self.offer_id, to=to
        )


__all__ = [
    "EmitAcceptCaseOwnershipTransferNode",
    "EmitRejectCaseOwnershipTransferNode",
    "EmitWithdrawCaseOwnershipTransferNode",
]
