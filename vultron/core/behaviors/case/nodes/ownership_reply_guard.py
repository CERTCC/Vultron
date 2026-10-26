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

"""The CASE_MANAGER's guards on a reply to an ownership-transfer Offer.

Provides:

- :class:`OfferParty` — which party to an Offer sent the reply a guard
  checks.
- :class:`OwnershipOfferOpenNode` — precondition guard that refuses a reply
  to an ownership-transfer Offer that is no longer open, and recognises a
  redelivery of the reply that closed it (CM-21-014, CM-21-016).
- :class:`OwnershipTransfereeActiveNode` — precondition guard that refuses
  an Accept from a transferee that is no longer an active participant
  (CM-21-021).
- :func:`case_manager_ownership_offer_open_guard` — the open-Offer guard,
  and for an Accept the active-transferee guard after it, behind the
  CASE_MANAGER gate, for the reply trees' ``precondition_guards``.

The guards on the owner's proposal are in
:mod:`~vultron.core.behaviors.case.nodes.ownership_offer_guard`, which
re-exports these names.
"""

from datetime import datetime
from enum import Enum

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)
from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.behaviors.idempotency import FlaggedRepeatGuardMixin
from vultron.core.models._helpers import now_utc
from vultron.core.participants.ownership_offer import (
    RecordedOwnershipOffer,
    recorded_ownership_offer,
)
from vultron.core.participants.recipients import why_may_not_act_on_case
from vultron.core.ports.case_persistence import CasePersistence
from vultron.errors import VultronBTInternalError, VultronNotFoundError


class OfferParty(Enum):
    """The party to an ownership-transfer Offer whose reply is checked."""

    TRANSFEREE = "transferee"
    """Answers the Offer: Accept or Reject (CM-21-011)."""

    OFFERER = "offerer"
    """Withdraws the Offer: Undo (CM-21-015)."""


#: The requirement a refusal of a reply to a closed Offer cites, per party.
_CLOSED_SPEC: dict[OfferParty, str] = {
    OfferParty.TRANSFEREE: "CM-21-011",
    OfferParty.OFFERER: "CM-21-015",
}

#: The requirements a refusal of a reply after the deadline cites, per party:
#: the deadline binds an answer (CM-21-016), and an expired Offer is closed
#: (CM-21-017), so it cannot be withdrawn (CM-21-015).
_LATE_SPEC: dict[OfferParty, str] = {
    OfferParty.TRANSFEREE: "CM-21-016",
    OfferParty.OFFERER: "CM-21-015, CM-21-017",
}


def _named_offer(
    datalayer: CasePersistence, case_id: str, offer_id: str | None
) -> RecordedOwnershipOffer:
    """The Offer a reply names, as the CASE_MANAGER recorded it.

    Raises:
        VultronNotFoundError: The reply names no Offer, or the CASE_MANAGER
            recorded no such Offer.
    """
    if offer_id is None:
        raise VultronNotFoundError(
            "ownership-transfer Offer", f"None (case '{case_id}')"
        )
    return recorded_ownership_offer(datalayer, case_id, offer_id)


def _require_named_offer(
    node: DataLayerConditionWithPorts,
    case_id: str,
    offer_id: str | None,
    found_by: str,
) -> RecordedOwnershipOffer:
    """The Offer a reply names, which *found_by* already found recorded.

    Its absence now is a local anomaly, not the sender's refusal, so it
    raises: the bridge flags an internal error instead of a ``REFUSED``
    verdict.

    Raises:
        VultronBTInternalError: The Offer is not recorded.
    """
    assert node.datalayer is not None
    try:
        return _named_offer(node.datalayer, case_id, offer_id)
    except VultronNotFoundError as exc:
        raise VultronBTInternalError(
            f"{node.name}: the Offer {found_by} found is gone ({exc})"
        ) from exc


class OwnershipOfferOpenNode(
    FlaggedRepeatGuardMixin, DataLayerConditionWithPorts
):
    """Guard: the ownership-transfer Offer a reply names is still open.

    Runs right after the reply's sender check, which has established that
    the sender is the party to the Offer the reply needs
    (:class:`~vultron.core.behaviors.sender_entitlement.SenderIsOwnershipOfferPartyNode`),
    so only a sender with standing learns the Offer's state.  The Offer is
    read from this store's ledger (CLP-11-001).

    - A **redelivery** of the reply that already closed the Offer is not a
      refusal (HP-01-003), but it must change nothing: by then ownership may
      have moved on through a later Offer, and re-applying the old reply
      would hand it back with no ledger entry.  The guard sets
      :attr:`is_redelivery` and fails, so nothing downstream runs, and the
      handler reports the run as ``SKIPPED``.
    - A reply to an Offer an answer or withdrawal already closed is refused
      (CM-21-014).
    - A reply after the Offer's ``end_time`` is refused (CM-21-016).

    The deadline is the ``end_time`` the ledgered Offer carries, and nothing
    records its passing (CM-21-017, ADR-0152): the CASE_MANAGER compares it
    with its own clock here, so the guard runs behind the CASE_MANAGER gate
    (:func:`case_manager_ownership_offer_open_guard`).  A replica changes
    nothing on an expiry, so it never evaluates one.

    Spec: CM-21-011, CM-21-013, CM-21-014, CM-21-015, CM-21-016, HP-01-003.
    """

    _REPEAT_FLAG = "is_redelivery"

    def __init__(
        self,
        case_id: str,
        offer_id: str | None,
        reply_id: str,
        sender_id: str,
        party: OfferParty,
        now: datetime | None = None,
        name: str | None = None,
    ) -> None:
        """Create the guard.

        Args:
            case_id: The case the reply names.
            offer_id: The Offer the reply names.
            reply_id: The reply's own id, so a redelivery is recognised.
            sender_id: The reply's sender, named in a refusal; the sender
                check has already established its standing.
            party: The party whose reply it is; it picks the requirements a
                refusal cites.
            now: The instant the deadline is compared against.  ``None``
                reads the clock when the guard runs.
            name: Optional node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._offer_id = offer_id
        self._reply_id = reply_id
        self._sender_id = sender_id
        self._party = party
        self._now = now
        self.is_redelivery = False
        """``True`` when the last run found the reply already ledgered as
        the one that closed the Offer: a benign no-op, not a refusal."""

    def _refuse(self, reason: str, spec: str) -> Status:
        self.feedback_message = f"{reason} — REFUSED ({spec})"
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE

    def _refuse_late(self, offer: RecordedOwnershipOffer) -> Status:
        deadline = (
            offer.end_time.isoformat() if offer.end_time is not None else "?"
        )
        return self._refuse(
            f"Ownership-transfer Offer '{offer.offer_id}' for case"
            f" '{self._case_id}' expired at its end_time {deadline}; reply"
            f" '{self._reply_id}' from '{self._sender_id}' came too late",
            _LATE_SPEC[self._party],
        )

    def update(self) -> Status:
        """Check the Offer is open; see the class docstring.

        Raises:
            VultronBTInternalError: The Offer the sender check found is not
                recorded, a local anomaly rather than the sender's refusal.
        """
        self.is_redelivery = False
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        _case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1: the gate found this store's case
        # The sender check ran first and found this Offer, so its absence
        # now is a local anomaly, not the sender's refusal.
        offer = _require_named_offer(
            self, self._case_id, self._offer_id, "the sender check"
        )
        if offer.answer_id == self._reply_id:
            self.is_redelivery = True
            self.feedback_message = (
                f"Reply '{self._reply_id}' already closed ownership-transfer"
                f" Offer '{offer.offer_id}' — redelivery, nothing to apply"
                " (HP-01-003)"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        if offer.is_answered_other_than(self._reply_id):
            return self._refuse(
                f"Ownership-transfer Offer '{offer.offer_id}' for case"
                f" '{self._case_id}' was already closed by"
                f" '{offer.answer_id}' ({offer.closed_by_semantic_type})",
                f"{_CLOSED_SPEC[self._party]}, CM-21-014",
            )
        if offer.is_past_deadline(self._now or now_utc()):
            return self._refuse_late(offer)
        return Status.SUCCESS


class OwnershipTransfereeActiveNode(DataLayerConditionWithPorts):
    """Guard: the transferee accepting an Offer is still an active participant.

    The CASE_MANAGER admitted the proposal only for an active transferee
    (:class:`OwnershipProposalAdmissibleNode`), but the transferee may have
    lapsed since: removed, left the case, or not agreed to an embargo that
    became active while the Offer was open.  Its Accept is then refused, so
    ownership never moves to an actor the case would send no content to
    (CM-21-021, CM-10-004).

    The transferee is the one the recorded Offer names, the same actor the
    role change grants ``CASE_OWNER`` to, never the sender id; the sender
    check has already established they are the same.  Runs after
    :class:`OwnershipOfferOpenNode`, so a redelivery of the Accept that
    closed the Offer stays ``SKIPPED`` whatever the transferee's standing now
    (HP-01-003).  Only the Accept runs it: CM-21-021 governs the answer that
    moves ownership, and a Reject moves nothing.

    Spec: CM-21-021, CM-10-004.
    """

    def __init__(
        self,
        case_id: str,
        offer_id: str | None,
        name: str | None = None,
    ) -> None:
        """Create the guard.

        Args:
            case_id: The case the Accept names.
            offer_id: The Offer the Accept names, which the open-Offer guard
                has already found recorded.
            name: Optional node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._offer_id = offer_id

    def update(self) -> Status:
        """Check the transferee is active; see the class docstring.

        Raises:
            VultronBTInternalError: The Offer the earlier guards found is not
                recorded, a local anomaly rather than the sender's refusal.
        """
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1: the gate found this store's case
        offer = _require_named_offer(
            self, self._case_id, self._offer_id, "the earlier guards"
        )
        why = why_may_not_act_on_case(
            case, self.datalayer, offer.transferee_id
        )
        if why is None:
            return Status.SUCCESS
        self.feedback_message = (
            f"the transferee '{offer.transferee_id}' of ownership-transfer"
            f" Offer '{offer.offer_id}' {why}, so it is no longer an active"
            f" participant of case '{self._case_id}' and may not take"
            " ownership — REFUSED (CM-21-021, CM-10-004)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


def case_manager_ownership_offer_open_guard(
    case_id: str,
    offer_id: str | None,
    reply_id: str,
    sender_id: str,
    party: OfferParty,
    now: datetime | None = None,
    *,
    transferee_must_be_active: bool = False,
) -> py_trees.behaviour.Behaviour:
    """Precondition guard: at the CASE_MANAGER, the replied-to Offer is open.

    With *transferee_must_be_active*, the Accept's case, the transferee must
    also still be an active participant
    (:class:`OwnershipTransfereeActiveNode`, CM-21-021), checked after the
    Offer is found open so a redelivery is still recognised first.

    A replica skips it as ``SUCCESS``: it takes the change from the
    CASE_MANAGER alone, which the sender check establishes (PCR-03-001),
    and changes nothing when an Offer expires (CM-21-017).  A
    receiver that does not hold the case is not its CASE_MANAGER (ADR-0087
    Regime 3).
    """
    children: list[py_trees.behaviour.Behaviour] = [
        OwnershipOfferOpenNode(
            case_id=case_id,
            offer_id=offer_id,
            reply_id=reply_id,
            sender_id=sender_id,
            party=party,
            now=now,
        )
    ]
    if transferee_must_be_active:
        children.append(
            OwnershipTransfereeActiveNode(case_id=case_id, offer_id=offer_id)
        )
    return create_case_manager_gated_tree(
        name="OwnershipOfferOpenIfCaseManager",
        case_id=case_id,
        body_name="OwnershipOfferOpen",
        children=children,
        case_may_be_absent=True,
    )
