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
ownership-transfer workflow (TRIG-11 / OT-02, ADR-0148).

Provides:

- :class:`EmitProposeCaseOwnershipTransferNode` — emits the Case Owner's
  proposal, ``Offer(Offer(VulnerabilityCase))``, to the case's CASE_MANAGER,
  the inner Offer naming the transferee as its ``target``.
- :class:`EmitAcceptCaseOwnershipTransferNode`,
  :class:`EmitRejectCaseOwnershipTransferNode` and
  :class:`EmitWithdrawCaseOwnershipTransferNode` — the replies, defined in
  ``ownership_offer_reply_emit.py`` and re-exported here.
- :class:`AcceptCaseOwnershipTransferNode` — applies the accepted
  ownership transfer to the DataLayer: updates ``case.attributed_to``,
  moves ``CVDRole.CASE_OWNER`` to the new owner's participant record, and
  commits each changed object as its own ledger entry (CLP-07-013); defined
  in ``ownership_transfer_apply.py`` with
  :class:`AcceptRecordedOwnershipOfferNode` and re-exported here.
- :class:`MakeOwnershipTransferOfferNode` — CASE_MANAGER-only effect node
  that makes the one ``Offer(VulnerabilityCase)`` of the transfer from the
  owner's proposal, queues it in the CASE_MANAGER's outbox and commits it
  (CM-21-005, ADR-0148).

These leaf nodes are assembled into trigger/receive trees in the parent
``actor_trigger_trees.py`` and ``ownership_transfer_tree.py`` modules per
BTND-07-003.
"""

import logging
from datetime import datetime
from typing import cast

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
from vultron.core.behaviors.helpers import (
    TRIGGER_FACTORY_UNAVAILABLE,
    _EmitSingleActivityBase,
)
from vultron.core.behaviors.sync.commit_tree import commit_emitted_activity
from vultron.core.models.protocol_pair import (
    OFFER_CASE_OWNERSHIP_TRANSFER_SEMANTIC_TYPE,
)
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.participants.ownership_offer import ownership_offer_id
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.errors import VultronWiringError

logger = logging.getLogger(__name__)


class EmitProposeCaseOwnershipTransferNode(_EmitSingleActivityBase):
    """Emit the Case Owner's ownership-transfer proposal to the CASE_MANAGER.

    Calls ``trigger_activity_factory.propose_case_ownership_transfer()``
    with ``actor=self.actor_id`` — the proposing Case Owner, never the
    CASE_MANAGER (CM-24-004, ADR-0109) — ``case_id`` and ``transferee_id``,
    addressed ``to`` the case's CASE_MANAGER (CM-21-005), then queues it in
    the owner's own outbox (TRIG-11-001).  The proposal is
    ``Offer(Offer(VulnerabilityCase))``: the CASE_MANAGER's received tree
    makes the inner Offer itself, under its own id (ADR-0148).  An
    ``end_time`` becomes the inner Offer's ``end_time``, the deadline to
    answer it (TRIG-11-007, CM-21-016); without one the Offer carries none.
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
        return self.trigger_activity_factory.propose_case_ownership_transfer(
            actor=self.actor_id,
            case_id=self.case_id,
            transferee_id=self.transferee_id,
            content=self.content,
            to=case_actor_id,
            end_time=self.end_time,
        )

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        self.logger.info(
            "Actor '%s' proposed to the CASE_MANAGER an ownership transfer of"
            " case '%s' to '%s'",
            self.actor_id,
            self.case_id,
            self.transferee_id,
        )


class MakeOwnershipTransferOfferNode(_EmitSingleActivityBase):
    """CASE_MANAGER effect: make the ownership-transfer Offer a proposal asks for.

    The one ``Offer(VulnerabilityCase)`` of the transfer (ADR-0148,
    CM-21-005): the CASE_MANAGER builds it from what it validated in the
    owner's proposal — the case, the transferee as ``target`` and ``to``,
    and the deadline as ``end_time`` (CM-21-016) — with ``actor`` itself and
    ``attributedTo`` the owner, from the shared delegated-authorship helper
    (CM-24-001, CM-24-002, CM-24-005).  Nothing else of the inner Offer is
    copied: its id is
    :func:`~vultron.core.participants.ownership_offer.ownership_offer_id`,
    derived from the proposal, so a redelivery rebuilds the same Offer and
    the outbox queues it once (OX-06-002).

    It queues the Offer, then commits it as the
    ``offer_case_ownership_transfer`` entry, whose snapshot is the sealed
    Offer itself (SYNC-09-002, VM-08-003): that is the Offer the transferee
    answers and the ledger closes.  The build, the queue and the commit are
    one transaction, so a failed commit sends nothing.  The commit runs here, inside the
    CASE_MANAGER gate the factory wraps ``manager_effects`` in (CLP-09-001,
    BT-17-008).

    It runs after the proposal's own entry, so a fault building, queuing or
    committing the Offer is the CASE_MANAGER's, never a refusal of the
    owner: it is not caught, and escapes to ``BTBridge`` as an internal error
    (ARCH-15-001).  The proposal's own entry is in the same act, so the
    fault keeps nothing, and a redelivery of the proposal runs the act
    afresh, making the Offer under the same id (CLP-07-015).  A missing
    factory raises :class:`VultronWiringError`, a wiring fault the handler
    also reports as internal.
    The Offer's timestamps serialise in UTC, as for any activity the
    CASE_MANAGER mints (CS-13-005).
    """

    def __init__(
        self,
        case_id: str,
        transferee_id: str,
        owner_id: str,
        proposal_id: str,
        captured: dict | None = None,
        name: str | None = None,
        end_time: datetime | None = None,
    ) -> None:
        super().__init__(captured=captured, name=name)
        self.case_id = case_id
        self.transferee_id = transferee_id
        self.owner_id = owner_id
        self.proposal_id = proposal_id
        self.end_time = end_time

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        if self.trigger_activity_factory is None:
            # A composition fault, not a refusal of the owner, whose proposal
            # is already ledgered (ARCH-15-001).
            raise VultronWiringError(
                f"{self.name}: {TRIGGER_FACTORY_UNAVAILABLE} to make the"
                f" ownership-transfer Offer of case '{self.case_id}'"
            )
        # Not caught: see the class docstring.  Built (which stores it),
        # queued and committed in one transaction, so a failed commit takes
        # the queued Offer back out: no transferee is sent an Offer the
        # ledger does not record (CLP-07-015, ADR-0146).
        with cast(CaseOutboxPersistence, self.datalayer).transaction():
            activity_id, activity_blob = self._call_factory()
            self._emit_through_seam(activity_id, activity_blob)
            self._record_sent(activity_id, activity_blob)
        self._on_success(activity_id, activity_blob)
        return Status.SUCCESS

    def _call_factory(self) -> tuple[str, str]:
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        authorship = delegated_authorship(
            doing_actor_id=self.actor_id,
            requesting_actor_id=self.owner_id,
        )
        return self.trigger_activity_factory.offer_case_ownership_transfer(
            case_id=self.case_id,
            transferee_id=self.transferee_id,
            actor=authorship.actor,
            to=[self.transferee_id],
            attributed_to=authorship.attributed_to,
            end_time=self.end_time,
            id_=ownership_offer_id(
                self.actor_id, self.case_id, self.proposal_id, self.owner_id
            ),
        )

    def _record_sent(self, activity_id: str, activity_blob: str) -> None:
        """Commit the queued Offer as its one canonical entry (SYNC-09-002)."""
        assert self.actor_id is not None
        commit_emitted_activity(
            datalayer=cast(CaseOutboxPersistence, self.datalayer),
            actor_id=self.actor_id,
            case_id=self.case_id,
            activity_id=activity_id,
            activity_blob=activity_blob,
            semantic_type=OFFER_CASE_OWNERSHIP_TRANSFER_SEMANTIC_TYPE,
        )

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        self.logger.info(
            "%s: CASE_MANAGER '%s' offered case '%s' to '%s' as Offer '%s',"
            " made from '%s''s proposal '%s' (CM-21-005, ADR-0148)",
            self.name,
            self.actor_id,
            self.case_id,
            self.transferee_id,
            activity_id,
            self.owner_id,
            self.proposal_id,
        )


__all__ = [
    "_TransferCaseOwnershipNode",
    "AcceptCaseOwnershipTransferNode",
    "AcceptRecordedOwnershipOfferNode",
    "EmitAcceptCaseOwnershipTransferNode",
    "EmitProposeCaseOwnershipTransferNode",
    "EmitRejectCaseOwnershipTransferNode",
    "EmitWithdrawCaseOwnershipTransferNode",
    "MakeOwnershipTransferOfferNode",
]
