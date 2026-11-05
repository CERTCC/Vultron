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


"""Use cases for case ownership transfer: offer, accept, reject, withdraw.

No HTTP framework imports permitted here.
"""

import logging
from collections.abc import Mapping
from typing import ClassVar, cast

import py_trees.behaviour

from vultron.core.behaviors.call_out.bundles.actor_discovery import (
    ACTOR_DISCOVERY_DETERMINISTIC,
    ActorDiscoveryCallOutBundle,
)
from vultron.core.behaviors.case.actor_trigger_trees import (
    accept_case_ownership_transfer_trigger_bt,
    offer_case_ownership_transfer_trigger_bt,
    reject_case_ownership_transfer_trigger_bt,
    withdraw_case_ownership_transfer_trigger_bt,
)
from vultron.core.models._helpers import _as_id
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.participants.recipients import why_may_not_act_on_case
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.services.received_activity import (
    read_held_activity,
    read_received_activity,
)
from vultron.core.use_cases.triggers._base import SvcActivityTriggerBase
from vultron.core.use_cases.triggers._helpers import (
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.actor._peers import _record_named_peer
from vultron.core.use_cases.triggers.requests import (
    AcceptCaseOwnershipTransferTriggerRequest,
    OfferCaseOwnershipTransferTriggerRequest,
    RejectCaseOwnershipTransferTriggerRequest,
    WithdrawCaseOwnershipTransferTriggerRequest,
)
from vultron.errors import (
    VultronNotFoundError,
    VultronValidationError,
)
from vultron.primitives import normalise_actor_id, same_actor_id

logger = logging.getLogger(__name__)


class SvcOfferCaseOwnershipTransferUseCase(SvcActivityTriggerBase):
    """Offer case ownership to another actor (trigger-side path).

    The Case Owner sends its proposal, ``Offer(Offer(VulnerabilityCase))``,
    to the case's CASE_MANAGER, from the owner's identity and outbox
    (CM-21-005, TRIG-11-001, ADR-0148).  It executes no tree as the
    CASE_MANAGER and never emits in its name (CM-24-010, ADR-0109): the
    CASE_MANAGER's received tree makes the one ``Offer(VulnerabilityCase)``
    the transferee answers, with ``attributedTo`` naming the owner
    (CM-24-005).

    The ``202`` this trigger earns therefore means the proposal was queued,
    not that the transferee was told; the result's ``activity`` is the
    owner's proposal, which the owner names to withdraw it (TRIG-11-006).
    """

    def __init__(
        self,
        dl: object,
        request: object,
        trigger_activity: object = None,
        call_out: ActorDiscoveryCallOutBundle = ACTOR_DISCOVERY_DETERMINISTIC,
        wire_render_port: "WireRenderPort | None" = None,
        sync_port: "SyncActivityPort | None" = None,
    ) -> None:
        super().__init__(
            dl=dl,  # type: ignore[arg-type]
            request=request,
            trigger_activity=trigger_activity,  # type: ignore[arg-type]
            wire_render_port=wire_render_port,
            sync_port=sync_port,
        )
        self._actor_discovery_call_out = call_out

    def _prepare(self) -> None:
        request = cast(OfferCaseOwnershipTransferTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        offering_actor_id = actor.id_
        self._case = resolve_case(request.case_id, self._dl)

        # The Offer goes to the CASE_MANAGER or nowhere (CM-21-005,
        # PCR-08-011).  A case always has a CASE_MANAGER (CM-02-014), so none
        # is a fault, not a direct send to the transferee.
        case_manager_id = resolve_case_manager_id(self._case, self._dl)
        if case_manager_id is None:
            raise VultronNotFoundError(
                "CASE_MANAGER", f"(for case '{self._case.id_}')"
            )
        # Fail closed on a proposal the CASE_MANAGER must refuse (CM-21-026):
        # it sends itself no Offer (BT-17-008), and the owner already owns
        # the case.  Checked before anything is written.
        for refused, why in (
            (case_manager_id, "the case's CASE_MANAGER"),
            (offering_actor_id, "the offering Case Owner itself"),
        ):
            if same_actor_id(request.transferee_id, refused):
                raise VultronValidationError(
                    f"transferee_id '{request.transferee_id}' is {why};"
                    " ownership can be offered only to another actor"
                    " (CM-21-026)"
                )
        # The CASE_MANAGER offers the case only to an active participant
        # (CM-21-021), judged here on the owner's own replica before anything
        # is queued (TRIG-01-003), with the id spelled as the roster keys it
        # (OID-01-006).  An owner that means to transfer the case to anyone
        # else invites it first.
        inactive = why_may_not_act_on_case(
            self._case, self._dl, normalise_actor_id(request.transferee_id)
        )
        if inactive is not None:
            raise VultronValidationError(
                f"transferee_id '{request.transferee_id}' {inactive}, so"
                f" case '{self._case.id_}' may not be offered to it; only an"
                " active participant may be, so invite it to the case first"
                " (CM-21-021)"
            )

        # A transferee is a peer named by URI — the same reasoning as an invitee
        # or a recommended actor; see ``_record_named_peer``. Handing ownership
        # to an actor on another node is the normal case, and that node's record
        # will never be in this store.
        _record_named_peer(
            self._dl,
            request.transferee_id,
            "transferee_id",
            self._actor_discovery_call_out,
        )

        self._transferee_id = request.transferee_id
        self._content = request.content
        self._end_time = request.end_time
        self._actor_id = offering_actor_id

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return offer_case_ownership_transfer_trigger_bt(
            case_id=self._case.id_,
            transferee_id=self._transferee_id,
            content=self._content,
            captured=self._captured,
            end_time=self._end_time,
        )

    def _handle_result(self) -> None:
        logger.info(
            "Actor '%s' sent the CASE_MANAGER an ownership transfer offer for"
            " case '%s' to '%s'",
            self._actor_id,
            self._case.id_,
            self._transferee_id,
        )


class _SvcOwnershipAnswerBase(SvcActivityTriggerBase):
    """An actor replies to an ownership-transfer Offer it holds.

    Shared by the transferee's accept and reject triggers and the owner's
    withdraw trigger: each reads what it replies to by id from the actor's
    own store — the CASE_MANAGER's Offer from the body intake archived, or
    the owner's own proposal as it sent it — and
    emits its reply to the case's CASE_MANAGER (CM-21-006, CM-21-010,
    CM-21-015).  Subclasses build the tree and name the verb they log.
    """

    _verb: ClassVar[str]
    """Past-tense verb for the success log line; each subclass sets it."""

    def _prepare(self) -> None:
        request = cast(
            AcceptCaseOwnershipTransferTriggerRequest
            | RejectCaseOwnershipTransferTriggerRequest
            | WithdrawCaseOwnershipTransferTriggerRequest,
            self._request,
        )
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_

        self._offer_id = request.offer_id
        self._case_id = self._held_case_id(request.offer_id)

    def _held_case_id(self, offer_id: str) -> str:
        """The case the Offer this actor holds names.

        The transferee answers the CASE_MANAGER's Offer it received,
        archived by intake under the receiver's key, never read under an id
        a sender chose (DL-06-006).  Nothing else stands in for it: an actor
        that never received the Offer has nothing to answer (ADR-0148).

        Raises:
            VultronNotFoundError: This actor holds no such Offer, or it
                names no case.
        """
        offer = read_received_activity(
            self._received_activities, offer_id, "Offer(VulnerabilityCase)"
        )
        raw_case_id = _as_id(getattr(offer, "object_", None))
        if not raw_case_id:
            raise VultronNotFoundError(
                "VulnerabilityCase (in Offer case reference)", offer_id
            )
        return raw_case_id

    def _handle_result(self) -> None:
        logger.info(
            "Actor '%s' %s case ownership transfer offer '%s'",
            self._actor_id,
            self._verb,
            self._offer_id,
        )


class SvcAcceptCaseOwnershipTransferUseCase(_SvcOwnershipAnswerBase):
    """Accept a case ownership transfer offer (trigger-side path).

    Emits ``Accept(Offer(VulnerabilityCase))`` from the accepting actor to
    the case's CASE_MANAGER (TRIG-11-002, CM-21-006).
    """

    _verb = "accepted"

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return accept_case_ownership_transfer_trigger_bt(
            offer_id=self._offer_id,
            case_id=self._case_id,
            captured=self._captured,
        )


class SvcRejectCaseOwnershipTransferUseCase(_SvcOwnershipAnswerBase):
    """Decline a case ownership transfer offer (trigger-side path).

    Emits ``Reject(Offer(VulnerabilityCase))`` from the declining actor to
    the case's CASE_MANAGER (TRIG-11-005, CM-21-010), which ledgers it and
    broadcasts the decline (CM-21-012, CM-21-032).
    """

    _verb = "rejected"

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return reject_case_ownership_transfer_trigger_bt(
            offer_id=self._offer_id,
            case_id=self._case_id,
            captured=self._captured,
        )


class SvcWithdrawCaseOwnershipTransferUseCase(_SvcOwnershipAnswerBase):
    """Withdraw an open case ownership transfer offer (trigger-side path).

    Emits ``Undo(Offer(Offer(VulnerabilityCase)))`` from the Case Owner to
    the case's CASE_MANAGER (TRIG-11-006, CM-21-015): the request's
    ``offer_id`` names the owner's own proposal, the one activity of the
    transfer it holds, and the CASE_MANAGER withdraws the Offer it made from
    it (ADR-0148).  The CASE_MANAGER admits it only from the owner that
    Offer was made for while it is still open, ledgers it and broadcasts the
    withdrawal.  The trigger does not pre-judge that: the CASE_MANAGER's
    ledger is what says whether the Offer is open (CM-21-034).
    """

    _verb = "withdrew"

    def _held_case_id(self, offer_id: str) -> str:
        """The case the owner's own proposal names, its ``context``.

        The proposal is an activity this actor sent, held under its own id.

        Raises:
            VultronNotFoundError: This actor holds no such proposal, or it
                names no case.
        """
        proposal = read_held_activity(
            self._received_activities,
            self._dl,
            offer_id,
            "Offer(Offer(VulnerabilityCase))",
        )
        inner = getattr(proposal, "object_", None)
        # A wire ``type_`` is a StrEnum and a core one a plain str; both
        # compare equal to "Offer".  A mapping inner (a dict, or a received
        # view's read-only mapping) may carry either key.
        inner_type = (
            inner.get("type") or inner.get("type_")
            if isinstance(inner, Mapping)
            else getattr(inner, "type_", None)
        )
        raw_case_id = _as_id(getattr(proposal, "context", None))
        if inner_type != "Offer" or not raw_case_id:
            # The owner withdraws its own proposal, never the CASE_MANAGER's
            # Offer made from it (ADR-0148): an id naming anything else is a
            # caller error, refused before any tree runs.
            raise VultronNotFoundError(
                "ownership-transfer proposal Offer(Offer(VulnerabilityCase))"
                " naming its case (offer_id must name the proposal the offer"
                " trigger returned)",
                offer_id,
            )
        return raw_case_id

    def _prepare(self) -> None:
        super()._prepare()
        # The withdrawal goes to the CASE_MANAGER or nowhere (CM-21-036,
        # PCR-08-011).  The offerer holds the case it offered, and a case
        # always has a CASE_MANAGER (CM-02-014), so either missing is a
        # not-found, refused before any tree runs, as the offer trigger does.
        case = resolve_case(self._case_id, self._dl)
        if resolve_case_manager_id(case, self._dl) is None:
            raise VultronNotFoundError(
                "CASE_MANAGER", f"(for case '{case.id_}')"
            )

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return withdraw_case_ownership_transfer_trigger_bt(
            offer_id=self._offer_id,
            case_id=self._case_id,
            captured=self._captured,
        )
