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

"""Answerers of a recorded Invite or role Offer: the ``INVITEE`` kind and
the role Offer's target (EP-09-010, CM-33-005).
"""

from typing import ClassVar

from py_trees.common import Status

from vultron.core.behaviors.sender_entitlement.addressee import (
    NoStandingError,
    RecordedRequest,
    SenderIsRequestAddresseeNode,
    _case_and_manager,
    _refuse_if_closed,
)
from vultron.core.behaviors.sender_entitlement.base import (
    SenderEntitlementConditionNode,
)
from vultron.core.behaviors.sender_entitlement.declarations import (
    SenderEntitlementKind,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.participants.recipients import (
    closure_recorded,
)
from vultron.core.participants.role_offer import answered_role_offer
from vultron.core.predicates.addressing import (
    distinct_recipients,
    same_actor_id,
)
from vultron.errors import VultronNotFoundError

# ---------------------------------------------------------------------------
# Condition node: INVITEE (the recorded Invite being answered)
# ---------------------------------------------------------------------------


class SenderIsInviteeNode(SenderEntitlementConditionNode):
    """Guard: sender must be the sole ``to`` recipient of the recorded Invite.

    The answer to an Invite is the invitee's to give, and the invitee is the
    Invite's sole ``to`` recipient (EP-09-010).
    The Invite is read from this store, never from the copy the reply embeds,
    which the sender wrote.
    An Invite this store never recorded, or one that names no recipient or
    several, names no invitee, so the sender is refused.

    When ``case_id`` is given the Invite is a case-join Invite, and the
    record must also be one this store's owner (the CASE_MANAGER) issued
    (CM-11-017: "an Invite it sent and recorded") and be for that case: a
    stub Invite names its case through its stub target, and an invitee of one
    case cannot answer for another.

    When ``closure_case_id`` is given, an invitee whose closure that case
    records (RM ``CLOSED``) is refused too: it has left the case and may
    answer nothing further (CM-23-018).  A repeat of a ``Reject`` that closed
    it is ``SKIPPED`` by the tree's closed-sender door before this guard runs
    (``closed_sender`` on the receive-tree factory).

    Spec: EP-09-010, CM-11-017, CM-23-018, HP-01-006.
    """

    guards_kind: ClassVar[SenderEntitlementKind | None] = (
        SenderEntitlementKind.INVITEE
    )

    def __init__(
        self,
        invite_id: str | None,
        sender_actor_id: str,
        name: str | None = None,
        *,
        case_id: str | None = None,
        closure_case_id: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._invite_id = invite_id
        self._sender_actor_id = sender_actor_id
        self._case_id = case_id
        self._closure_case_id = closure_case_id

    @staticmethod
    def _named_case(invite: object) -> str | None:
        """The case a recorded Invite is for: its stub target's case, else its target."""
        target = getattr(invite, "target", None)
        stub_case = getattr(target, "case_id", None)
        return stub_case if isinstance(stub_case, str) else _as_id(target)

    def _admit_unless_closed(self) -> Status:
        """SUCCESS, unless the case records the invitee's closure (CM-23-018)."""
        if self._closure_case_id is None:
            return Status.SUCCESS
        assert self.datalayer is not None
        case = self.datalayer.read(self._closure_case_id)
        if not isinstance(case, VulnerabilityCase) or not closure_recorded(
            case, self.datalayer, self._sender_actor_id
        ):
            return Status.SUCCESS
        self.feedback_message = (
            f"Invitee '{self._sender_actor_id}' has left case"
            f" '{self._closure_case_id}' (RM CLOSED) and may answer nothing"
            " further — REFUSED (CM-23-018, HP-01-006)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE

    def _refuse_case_join(self, why: str) -> Status:
        self.feedback_message = (
            f"Invite '{self._invite_id}' {why} — REFUSED (CM-11-017,"
            " HP-01-006)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        sender = self._sender_actor_id
        invite = (
            self.datalayer.read(self._invite_id) if self._invite_id else None
        )
        recipients = distinct_recipients(
            _as_id(r) for r in (getattr(invite, "to", None) or [])
        )
        if len(recipients) == 1 and same_actor_id(sender, recipients[0]):
            if self._case_id is None:
                return self._admit_unless_closed()
            issuer = _as_id(getattr(invite, "actor", None))
            if issuer is None or not same_actor_id(
                issuer, self.actor_id or ""
            ):
                return self._refuse_case_join(
                    f"was issued by '{issuer}', not by this CASE_MANAGER"
                )
            named_case = self._named_case(invite)
            if named_case != self._case_id:
                return self._refuse_case_join(
                    f"is for case '{named_case}', not '{self._case_id}'"
                )
            return self._admit_unless_closed()

        if invite is None:
            why = f"Invite '{self._invite_id}' was never recorded here"
        elif len(recipients) != 1:
            why = (
                f"Invite '{self._invite_id}' names {len(recipients)}"
                " recipients, so it has no invitee"
            )
        else:
            why = (
                f"Invite '{self._invite_id}' was addressed to"
                f" '{recipients[0]}'"
            )
        self.feedback_message = (
            f"Sender '{sender}' is not the invitee: {why}"
            " — REFUSED (EP-09-010, HP-01-006)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


class SenderIsRoleOfferTargetNode(SenderIsRequestAddresseeNode):
    """Guard: sender is the target of the role Offer its answer names.

    The target is the addressee of the request, so the kind is
    ``NAMED_ACTOR`` (ADR-0129).  The receive-tree factory composes it on the
    CASE_MANAGER's side of the declared rule (CM-33-005).

    It checks standing only: the sender is the target of a role Offer the
    CASE_MANAGER recorded for the case.  The Offer the answer names is the
    recorded Offer or the CASE_MANAGER's forward of it, resolved through the
    forward's ``inReplyTo`` as this store holds it
    (:func:`~vultron.core.participants.role_offer.answered_role_offer`),
    never through the copy the answer embeds, which the sender wrote.
    Whether the Offer is still open, and whether the answer is a redelivery
    of the one that closed it, is the precondition guard that runs right
    after the sender check
    (:class:`~vultron.core.behaviors.case.nodes.role_offer_guard.RoleOfferOpenNode`).

    A case this store does not hold, one that names no CASE_MANAGER, an
    Offer the CASE_MANAGER never recorded, or a target whose closure the
    case records (CM-23-018) leaves the sender with no standing.

    Spec: CM-33-005, CM-23-018, HP-01-006.
    """

    _spec = "CM-33-005"

    def __init__(
        self,
        case_id: str,
        offer_id: str | None,
        sender_actor_id: str,
        name: str | None = None,
    ) -> None:
        """Create the guard.

        Args:
            case_id: The case the answer names.
            offer_id: The Offer the answer names (``None`` when it names
                none, which refuses).
            sender_actor_id: The answer's sender.
            name: Optional node name.
        """
        super().__init__(sender_actor_id=sender_actor_id, name=name)
        self._case_id = case_id
        self._offer_id = offer_id
        self._case: VulnerabilityCase | None = None
        """The case :meth:`_recorded_request` last read."""

    def _recorded_request(self) -> RecordedRequest:
        assert self.datalayer is not None
        sender = self.sender_actor_id
        case, manager_id = _case_and_manager(
            self.datalayer, self._case_id, sender
        )
        if self._offer_id is None:
            raise NoStandingError(f"Sender '{sender}' names no role Offer")
        try:
            offer = answered_role_offer(
                self.datalayer, self._case_id, self._offer_id, manager_id
            )
        except VultronNotFoundError as exc:
            raise NoStandingError(
                f"Sender '{sender}' names Offer '{self._offer_id}', which"
                f" this CASE_MANAGER never recorded as a role Offer for case"
                f" '{self._case_id}' ({exc})"
            ) from exc
        self._case = case
        return RecordedRequest(
            description=f"role Offer '{offer.offer_id}'",
            position="the target",
            addressees=(offer.target_id,),
        )

    def _confirm_standing(self, request: RecordedRequest) -> None:
        """Refuse a target whose closure the case records (CM-23-018).

        Raises:
            NoStandingError: The target has left the case (RM ``CLOSED``).
        """
        assert self.datalayer is not None and self._case is not None
        _refuse_if_closed(
            self.datalayer, self._case, self.sender_actor_id, "Target"
        )
