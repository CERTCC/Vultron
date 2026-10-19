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

"""The checks a role Offer must pass before it is recorded (CM-33-003).

Provides :class:`RoleOfferAdmissibleNode`, the precondition guard of the
``Offer(CaseParticipantRole)`` received tree (ADR-0039).  It runs after the
sender guard, which has established that the CASE_MANAGER got the Offer from
the Case Owner, or that a participant got it from the CASE_MANAGER
(CM-33-002, CM-33-004).
"""

from typing import ClassVar

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.participants.role_offer import (
    entry_names_role_offer,
    recorded_role_offer,
    role_offer_forward_id,
)
from vultron.core.predicates.addressing import (
    participant_id_for_actor,
    same_actor_id,
)
from vultron.enums.roles import CVDRole


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

    @property
    def failed_as_repeat(self) -> bool:
        """Whether the last run failed as a repeat (``ReportsIdempotentRepeat``)."""
        return self.is_redelivery and self.status == Status.FAILURE

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


__all__ = ["RoleOfferAdmissibleNode"]
