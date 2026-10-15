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

"""Trigger-side emit nodes and receive-side application nodes for the
ownership-transfer workflow (TRIG-11 / OT-02).

Provides:

- :class:`EmitOfferCaseOwnershipTransferNode` — emits the Case Owner's own
  ``Offer(VulnerabilityCase)`` (ownership transfer variant) to the case's
  CASE_MANAGER, naming the transferee as its ``target``.
- :class:`EmitAcceptCaseOwnershipTransferNode`,
  :class:`EmitRejectCaseOwnershipTransferNode` and
  :class:`EmitWithdrawCaseOwnershipTransferNode` — the replies to an Offer,
  defined in ``ownership_offer_reply_emit.py`` and re-exported here.
- :class:`AcceptCaseOwnershipTransferNode` — applies the accepted
  ownership transfer to the DataLayer: updates ``case.attributed_to``,
  moves ``CVDRole.CASE_OWNER`` to the new owner's participant record, and
  commits each changed object as its own ledger entry (CLP-07-013); defined
  in ``ownership_transfer_apply.py`` with
  :class:`AcceptRecordedOwnershipOfferNode` and re-exported here.
- :class:`ForwardOfferToTransfereeNode` — CaseActor-only effect node that
  builds a new ``Offer(VulnerabilityCase)`` addressed to the transferee and
  queues it in the CaseActor's outbox (CM-21-005, ADR-0053).

These leaf nodes are assembled into trigger/receive trees in the parent
``actor_trigger_trees.py`` and ``ownership_transfer_tree.py`` modules per
BTND-07-003.
"""

import logging
from datetime import datetime

from py_trees.common import Status

from vultron.core.behaviors.case.nodes.ownership_offer_reply_emit import (
    EmitAcceptCaseOwnershipTransferNode,
    EmitRejectCaseOwnershipTransferNode,
    EmitWithdrawCaseOwnershipTransferNode,
)
from vultron.core.behaviors.case.nodes.ownership_transfer_apply import (
    AcceptCaseOwnershipTransferNode,
    AcceptRecordedOwnershipOfferNode,
    _TransferCaseOwnershipNode,
)
from vultron.core.behaviors.delegated_authorship import delegated_authorship
from vultron.core.behaviors.helpers import _EmitSingleActivityBase
from vultron.core.participants.authority import resolve_case_manager_id

logger = logging.getLogger(__name__)


class EmitOfferCaseOwnershipTransferNode(_EmitSingleActivityBase):
    """Emit the Case Owner's ``Offer(VulnerabilityCase)`` to the CASE_MANAGER.

    Calls ``trigger_activity_factory.offer_case_ownership_transfer()`` with
    ``actor=self.actor_id`` — the offering Case Owner, never the CASE_MANAGER
    (CM-24-004, ADR-0109) — ``case_id`` and ``transferee_id``, addressed
    ``to`` the case's CASE_MANAGER (CM-21-005), then queues it in the owner's
    own outbox (TRIG-11-001).  The CASE_MANAGER's received tree forwards it to
    the transferee.  An ``end_time`` becomes the Offer's activity-level
    ``end_time``, the deadline to answer it (TRIG-11-007, CM-21-016); without
    one the Offer carries none.
    """

    def __init__(
        self,
        case_id: str,
        transferee_id: str,
        content: str | None = None,
        captured: dict | None = None,
        name: str | None = None,
        end_time: datetime | None = None,
    ) -> None:
        super().__init__(captured=captured, name=name)
        self.case_id = case_id
        self.transferee_id = transferee_id
        self.content = content
        self.end_time = end_time

    def _call_factory(self) -> tuple[str, str]:
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        assert self.datalayer is not None
        # Regime 3 (ADR-0087): the case is read only to address the Offer to
        # its CASE_MANAGER, so the read is lenient here (conformance
        # allowlist).  The trigger refuses, before this tree runs, a case it
        # does not hold or one with no CASE_MANAGER (PCR-08-011, CM-24-006),
        # so a `to`-less Offer is not reached through it.
        case = self.datalayer.read_case(self.case_id)
        case_actor_id: list[str] | None = None
        if case is not None:
            cm_id = resolve_case_manager_id(case, self.datalayer)
            if cm_id:
                case_actor_id = [cm_id]
        return self.trigger_activity_factory.offer_case_ownership_transfer(
            actor=self.actor_id,
            case_id=self.case_id,
            transferee_id=self.transferee_id,
            content=self.content,
            to=case_actor_id,
            end_time=self.end_time,
        )

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        self.logger.info(
            "Actor '%s' sent the CASE_MANAGER an ownership transfer offer for"
            " case '%s' to '%s'",
            self.actor_id,
            self.case_id,
            self.transferee_id,
        )


class ForwardOfferToTransfereeNode(_EmitSingleActivityBase):
    """CaseActor effect node: build and enqueue a forwarded ownership-transfer Offer.

    Implements CM-21-005 / ADR-0053: after the CaseActor records the ledger
    entry for an incoming ``Offer(VulnerabilityCase)``, it MUST forward a new
    ``Offer(VulnerabilityCase, actor=case_actor, attributed_to=original_offerer,
    to=[transferee])`` to the transferee's inbox via the CaseActor's own outbox.

    Must be wrapped in ``create_case_manager_gated_tree`` so that non-CaseManager
    actors skip this node cleanly (they should never forward the offer).

    Logs WARNING and returns FAILURE when ``trigger_activity_factory`` is absent
    from the blackboard — this leaves all outboxes untouched.

    The forward carries ``in_reply_to`` set to *offer_id*, the recorded
    Offer's id (the ``offer_case_ownership_transfer`` entry's
    ``log_object_id``), so an answer naming the forward resolves to the Offer
    it forwards by that link, never by time (CM-21-018).

    The forward carries the received Offer's ``end_time``, so the transferee,
    which holds and answers the forward, knows its deadline (CM-21-016).  The
    forward is an activity this node mints, so its timestamps serialise in
    UTC (CS-13-005); the received Offer's own offset stays on its ledger
    entry.
    """

    def __init__(
        self,
        case_id: str,
        transferee_id: str,
        original_actor_id: str,
        offer_id: str,
        captured: dict | None = None,
        name: str | None = None,
        end_time: datetime | None = None,
    ) -> None:
        super().__init__(captured=captured, name=name)
        self.case_id = case_id
        self.transferee_id = transferee_id
        self.original_actor_id = original_actor_id
        self.offer_id = offer_id
        self.end_time = end_time

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        if self.trigger_activity_factory is None:
            self.logger.warning(
                "%s: no trigger_activity port — cannot forward offer"
                " to transferee (CM-21-005)",
                self.name,
            )
            return Status.FAILURE
        try:
            activity_id, activity_blob = self._call_factory()
            self._emit_through_seam(activity_id, activity_blob)
        except Exception as e:  # noqa: BLE001  # ruff-baseline #3768
            self.feedback_message = f"ForwardOfferToTransfereeNode failed: {e}"
            self.logger.error("%s", self.feedback_message)  # noqa: TRY400  # ruff-baseline #3353
            return Status.FAILURE
        self._on_success(activity_id, activity_blob)
        return Status.SUCCESS

    def _call_factory(self) -> tuple[str, str]:
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        authorship = delegated_authorship(
            doing_actor_id=self.actor_id,
            requesting_actor_id=self.original_actor_id,
        )
        return self.trigger_activity_factory.offer_case_ownership_transfer(
            case_id=self.case_id,
            transferee_id=self.transferee_id,
            actor=authorship.actor,
            to=[self.transferee_id],
            attributed_to=authorship.attributed_to,
            end_time=self.end_time,
            in_reply_to=self.offer_id,
        )

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        self.logger.info(
            "%s: CaseActor '%s' forwarded ownership-transfer offer '%s'"
            " to transferee '%s' in reply to recorded offer '%s'"
            " (CM-21-005, CM-21-018)",
            self.name,
            self.actor_id,
            activity_id,
            self.transferee_id,
            self.offer_id,
        )


__all__ = [
    "_TransferCaseOwnershipNode",
    "AcceptCaseOwnershipTransferNode",
    "AcceptRecordedOwnershipOfferNode",
    "EmitAcceptCaseOwnershipTransferNode",
    "EmitOfferCaseOwnershipTransferNode",
    "EmitRejectCaseOwnershipTransferNode",
    "EmitWithdrawCaseOwnershipTransferNode",
    "ForwardOfferToTransfereeNode",
]
