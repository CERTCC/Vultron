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

"""The checks a role Offer and its answer must pass before either is recorded.

Provides:

- :class:`RoleOfferAdmissibleNode` — the precondition guard of the
  ``Offer(CaseParticipantRole)`` received tree (ADR-0039, CM-33-003).  It runs
  after the sender guard, which has established that the CASE_MANAGER got the
  Offer from the Case Owner, or that a participant got it from the
  CASE_MANAGER (CM-33-002, CM-33-004).
- :class:`RoleOfferOpenNode` — the precondition guard of the target's
  ``Accept`` or ``Reject`` received trees (CM-33-005).  It runs after the
  sender guard, which has established that the sender is the target of a role
  Offer the CASE_MANAGER recorded.
"""

from typing import ClassVar

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.protocol_pair import (
    ACCEPT_CASE_PARTICIPANT_ROLE_EVENT_TYPE,
)
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.participants.role_offer import (
    RecordedRoleOffer,
    answered_role_offer,
    entry_names_role_offer,
    recorded_role_offer,
    role_offer_forward_id,
)
from vultron.core.predicates.addressing import (
    participant_id_for_actor,
    same_actor_id,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronBTInternalError, VultronNotFoundError


class RoleOfferAdmissibleNode(DataLayerConditionWithPorts):
    """Guard: the role Offer names a role the target may be offered.

    Refuses, so nothing is committed or forwarded (CM-33-003):

    - an Offer that carries no readable ``CVDRole``, which is never read as a
      default role;
    - an Offer of ``CVDRole.CASE_OWNER`` or ``CVDRole.CASE_MANAGER``;
    - an Offer whose target is not a participant in the case, or already
      holds the offered role;
    - an Offer whose target is the case's CASE_MANAGER: the CASE_MANAGER
      would forward the Offer to itself, an emit whose only recipient is the
      executing actor (BT-17-008), and the answer it owes goes to the
      CASE_MANAGER (CM-33-004).

    A **redelivery** of an Offer the ledger already records, naming the same
    role and target, is not a new Offer and not a refusal (HP-01-003); an
    Offer that reuses a recorded id for another role or target is refused
    (ID-02-001).  The guard sets :attr:`is_redelivery` and skips the other
    checks, which the Offer passed when it was recorded and which the
    target's later Accept would now fail.  When the forward is already
    stored, the redelivery changes nothing: the guard fails, so nothing
    downstream runs and nothing is sent again.  When it is not, the forward
    failed after the commit, and the guard admits the redelivery to finish
    it: the commit reuses the recorded entry rather than adding one, and the
    forward is built under its derived id (OX-06-002).  Either way the
    handler reports the run as ``SKIPPED``.  Only the CASE_MANAGER records
    role Offers, and the forward a participant receives carries its own id,
    so a participant never reads the forward as a redelivery.

    Read-only.  It runs on every store the Offer reaches: the target holds
    the case too, and refuses the same malformed Offer (CM-33-004).
    """

    #: The roles no Offer may carry: they are held through case creation and
    #: ownership transfer, never through a role Offer (CM-33-003).
    UNOFFERABLE_ROLES: ClassVar[frozenset[CVDRole]] = frozenset(
        {CVDRole.CASE_OWNER, CVDRole.CASE_MANAGER}
    )

    def __init__(
        self,
        case_id: str,
        offer_id: str,
        role: CVDRole | None,
        target_actor_id: str | None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.offer_id = offer_id
        self.role = role
        self.target_actor_id = target_actor_id
        self.is_redelivery = False
        """``True`` when the last run found this Offer already ledgered: a
        redelivery, which only finishes an unsent forward, not a refusal."""

    def _refuse(self, reason: str) -> Status:
        self.feedback_message = (
            f"role Offer '{self.offer_id}' {reason} — REFUSED (CM-33-003)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE

    def _redelivery(self, recorded: CaseLedgerEntry) -> Status:
        """Judge an Offer whose id the ledger already records."""
        assert self.datalayer is not None and self.actor_id is not None
        assert self.role is not None
        if not entry_names_role_offer(
            recorded, self.role, self.target_actor_id
        ):
            return self._refuse(
                "reuses the id of a recorded role Offer that names another"
                " role or target (ID-02-001)"
            )
        self.is_redelivery = True
        forward_id = role_offer_forward_id(
            self.actor_id, self.case_id, self.offer_id
        )
        if self.datalayer.read(forward_id) is not None:
            self.feedback_message = (
                f"role Offer '{self.offer_id}' is already recorded and"
                f" forwarded for case '{self.case_id}' — redelivery, nothing"
                " to apply (HP-01-003)"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        self.feedback_message = (
            f"role Offer '{self.offer_id}' is already recorded for case"
            f" '{self.case_id}' but not forwarded — redelivery resumes the"
            " forward (HP-01-003)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS

    def update(self) -> Status:
        self.is_redelivery = False
        if self.role is None:
            return self._refuse("carries no readable CVDRole")
        if self.role in self.UNOFFERABLE_ROLES:
            return self._refuse(
                f"offers {self.role.value}, which no Offer may"
            )
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1: the roster check needs the case
        recorded = recorded_role_offer(
            self.datalayer, self.case_id, self.offer_id
        )
        if recorded is not None:
            return self._redelivery(recorded)
        if not self.target_actor_id:
            return self._refuse("names no target")
        participant_id = participant_id_for_actor(
            case.actor_participant_index, self.target_actor_id
        )
        participant = (
            self.datalayer.read(participant_id) if participant_id else None
        )
        if not isinstance(participant, CaseParticipant):
            return self._refuse(
                f"names '{self.target_actor_id}', which is not a participant"
                f" in case '{self.case_id}'"
            )
        case_manager_id = resolve_case_manager_id(case, self.datalayer)
        if case_manager_id is not None and same_actor_id(
            case_manager_id, self.target_actor_id
        ):
            return self._refuse(
                f"names the case's CASE_MANAGER '{self.target_actor_id}',"
                " which would forward the Offer to itself (CM-33-003, BT-17-008)"
            )
        if participant.has_role(self.role):
            return self._refuse(
                f"offers '{self.target_actor_id}' {self.role.value}, which it"
                " already holds"
            )
        return Status.SUCCESS


class RoleOfferOpenNode(DataLayerConditionWithPorts):
    """Guard: the role Offer an answer names is open, and the answer is to it.

    Runs right after the answer's sender check, which has established that
    the sender is the target of a role Offer the CASE_MANAGER recorded
    (:class:`~vultron.core.behaviors.sender_entitlement.SenderIsRoleOfferTargetNode`),
    so only the target learns the Offer's state.  The Offer and its state are
    read from this store's ledger
    (:func:`~vultron.core.participants.role_offer.answered_role_offer`).

    - A **redelivery** of the answer that closed the Offer is not a refusal
      (HP-01-003).  The guard sets :attr:`is_redelivery`, and the handler
      reports the run as ``SKIPPED``.  When the answer's effects are done it
      fails, so nothing downstream runs.  When it is an Accept whose grant
      the CASE_MANAGER's own replica does not hold, the grant failed after
      the commit, and the guard admits the redelivery to finish it: the
      commit reuses the recorded entry rather than adding one, and the grant
      is idempotent.  It admits only a redelivery that carries the recorded
      role and target, the copy the entry already holds.
    - An answer to an Offer another answer already closed is refused, with no
      entry and no role change (CM-33-005).
    - An answer whose carried Offer names another role or target than the
      recorded Offer is refused.  The entry the CASE_MANAGER commits is the
      answer as received, and every replica grants the role that entry's
      carried Offer names (CM-02-016), so a carried copy that disagrees with
      the recorded Offer would grant on the replicas what the CASE_MANAGER
      never offered.

    Read-only; the sender guard admits no sender at any store but the
    CASE_MANAGER, so only the CASE_MANAGER runs it.

    Spec: CM-33-005, CM-02-016, HP-01-003.
    """

    def __init__(
        self,
        case_id: str,
        offer_id: str | None,
        reply_id: str,
        carried_role: CVDRole | None,
        carried_target_id: str | None,
        name: str | None = None,
    ) -> None:
        """Create the guard.

        Args:
            case_id: The case the answer names.
            offer_id: The Offer the answer names.
            reply_id: The answer's own id, so a redelivery is recognised.
            carried_role: The role the Offer the answer carries names.
            carried_target_id: The target the Offer the answer carries names.
            name: Optional node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.offer_id = offer_id
        self.reply_id = reply_id
        self.carried_role = carried_role
        self.carried_target_id = carried_target_id
        self.is_redelivery = False
        """``True`` when the last run found the answer already ledgered as
        the one that closed the Offer: a benign no-op, not a refusal."""

    def _refuse(self, reason: str) -> Status:
        self.feedback_message = f"{reason} — REFUSED (CM-33-005)"
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE

    def _recorded_offer(self, case: VulnerabilityCase) -> RecordedRoleOffer:
        """The Offer the answer names, as the CASE_MANAGER recorded it.

        Raises:
            VultronBTInternalError: The Offer the sender check found is not
                recorded, a local anomaly rather than the sender's refusal.
        """
        assert self.datalayer is not None
        # The sender check ran first and found this Offer, so its absence now
        # is a local anomaly, not the sender's refusal: raise, so the bridge
        # flags an internal error instead of a REFUSED verdict.
        manager_id = resolve_case_manager_id(case, self.datalayer)
        if manager_id is None or self.offer_id is None:
            raise VultronBTInternalError(
                f"{self.name}: the role Offer the sender check found is gone"
                f" (offer {self.offer_id}, case '{self.case_id}', manager"
                f" {manager_id})"
            )
        try:
            return answered_role_offer(
                self.datalayer, self.case_id, self.offer_id, manager_id
            )
        except VultronNotFoundError as exc:
            raise VultronBTInternalError(
                f"{self.name}: the role Offer the sender check found is gone"
                f" ({exc})"
            ) from exc

    def _carries_recorded_offer(self, offer: RecordedRoleOffer) -> bool:
        """Whether the answer's carried Offer names the recorded role and target."""
        return self.carried_role is not None and entry_names_role_offer(
            offer.entry, self.carried_role, self.carried_target_id
        )

    def _grant_pending(
        self, case: VulnerabilityCase, offer: RecordedRoleOffer
    ) -> bool:
        """Whether the closing Accept's grant is missing from this replica."""
        assert self.datalayer is not None and self.carried_role is not None
        if (
            offer.closed_by_event_type
            != ACCEPT_CASE_PARTICIPANT_ROLE_EVENT_TYPE
        ):
            return False
        participant_id = participant_id_for_actor(
            case.actor_participant_index, offer.target_id
        )
        participant = (
            self.datalayer.read(participant_id) if participant_id else None
        )
        return isinstance(participant, CaseParticipant) and not (
            participant.has_role(self.carried_role)
        )

    def _redelivery(
        self, case: VulnerabilityCase, offer: RecordedRoleOffer
    ) -> Status:
        """Judge a redelivery of the answer that closed the Offer."""
        self.is_redelivery = True
        if self._carries_recorded_offer(offer) and self._grant_pending(
            case, offer
        ):
            self.feedback_message = (
                f"answer '{self.reply_id}' already closed role Offer"
                f" '{offer.offer_id}' but its grant is not applied —"
                " redelivery resumes the grant (HP-01-003)"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS
        self.feedback_message = (
            f"answer '{self.reply_id}' already closed role Offer"
            f" '{offer.offer_id}' — redelivery, nothing to apply"
            " (HP-01-003)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE

    def update(self) -> Status:
        """Check the Offer is open; see the class docstring."""
        self.is_redelivery = False
        if (f := self._require_datalayer()) is not None:
            return f
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1: the sender check found this case
        offer = self._recorded_offer(case)
        if offer.answer_id == self.reply_id:
            return self._redelivery(case, offer)
        if offer.answer_id is not None:
            return self._refuse(
                f"role Offer '{offer.offer_id}' for case '{self.case_id}' was"
                f" already closed by '{offer.answer_id}'"
                f" ({offer.closed_by_event_type})"
            )
        if not self._carries_recorded_offer(offer):
            return self._refuse(
                f"answer '{self.reply_id}' carries an Offer naming role"
                f" {self.carried_role} for '{self.carried_target_id}', not"
                f" the role and target of recorded role Offer"
                f" '{offer.offer_id}'"
            )
        return Status.SUCCESS


__all__ = ["RoleOfferAdmissibleNode", "RoleOfferOpenNode"]
