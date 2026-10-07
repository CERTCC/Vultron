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

"""The case owner's Reject of an open embargo proposal (EP-08-003).

:class:`DecideRejectedEmbargoProposalNode` applies the owner's ER or EJ on
the received path and in the ledger replay;
:class:`OwnerRejectsRevisionAfterDisclosureNode` tells when that Reject must
end the embargo instead (EMB-04-002).  The P/X/A abandonment of open
proposals (EMB-16-001) is the CASE_MANAGER's decision, not an owner's
Reject, and lives in :mod:`.abandon`.

Extracted from lifecycle.py to keep that module under the BTND-07-004
500-line limit.
"""

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
)
from vultron.core.behaviors.narrative_log import log_em_transition
from vultron.core.models._helpers import _as_id
from vultron.core.predicates.embargo import pxa_is_embargo_eligible
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    TransitionMode,
)
from vultron.core.states.em import EM
from vultron.errors import VultronError


class DecideRejectedEmbargoProposalNode(DataLayerActionWithPorts):
    """Apply the case owner's Reject of an open proposal (ER / EJ, EP-08-003).

    Only the owner's answer decides a proposal; a participant's Reject is
    consent, which :class:`RecordParticipantRejectionNode` records.  When
    ``rejecting_actor_id`` is the owner and ``embargo_id`` is still an open
    proposal of the case, this node calls
    ``EmbargoLifecycle.reject_embargo_invite`` for the owner, which drives
    ``PROPOSED → NONE`` or ``REVISE → ACTIVE`` and forgets the proposal
    together (EMB-18-001) — or, while another proposal stays open, only
    forgets this one (EP-08-001).  It leaves the consent record alone:
    :class:`RecordParticipantRejectionNode` runs before it on both paths.  The received path runs it ``STRICT`` in the
    CASE_MANAGER's store; the ledger replay runs it ``OBSERVED`` (EP-09-007).

    Returns SUCCESS and changes nothing when the rejecting actor is not the
    owner, or when the embargo is no longer an open proposal (already
    decided, or the active embargo — a withdrawal, which moves no EM state),
    so a repeated Reject is idempotent.  Returns FAILURE when the case cannot
    be read or the lifecycle refuses the transition (for example ``STRICT``
    EJ with P/X/A set, EMB-04-002).
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        rejecting_actor_id: str,
        name: str | None = None,
        *,
        transition_mode: TransitionMode = TransitionMode.STRICT,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.embargo_id = embargo_id
        self.rejecting_actor_id = rejecting_actor_id
        self.transition_mode = transition_mode

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        if _as_id(case.attributed_to) != self.rejecting_actor_id:
            self.feedback_message = (
                f"'{self.rejecting_actor_id}' is not the owner of case"
                f" '{self.case_id}': its Reject is consent and decides nothing"
            )
            return Status.SUCCESS
        if self.embargo_id not in case.proposed_embargo_ids:
            self.feedback_message = (
                f"Embargo '{self.embargo_id}' is not an open proposal of case"
                f" '{self.case_id}' — nothing to decide"
            )
            return Status.SUCCESS

        try:
            result = EmbargoLifecycle(
                persistence=self.datalayer
            ).reject_embargo_invite(
                case_id=self.case_id,
                embargo_id=self.embargo_id,
                actor_id=self.rejecting_actor_id,
                transition_mode=self.transition_mode,
                # RecordParticipantRejectionNode runs first on both paths and
                # has already applied the owner's consent effect (MSM-07-004).
                record_consent=False,
            )
        except VultronError as exc:
            self.feedback_message = str(exc)
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        log_em_transition(
            self.logger,
            self.rejecting_actor_id,
            self.case_id,
            result.em_before,
            result.em_after,
        )
        self.feedback_message = (
            f"Owner rejected embargo '{self.embargo_id}' on case"
            f" '{self.case_id}' (EM {result.em_before} → {result.em_after})"
        )
        return Status.SUCCESS


class OwnerRejectsRevisionAfterDisclosureNode(DataLayerConditionWithPorts):
    """True when the owner's Reject must end the embargo, not keep it (EMB-04-002).

    SUCCESS when ``rejecting_actor_id`` is the case owner, the case is in
    ``REVISE``, ``embargo_id`` is the last open proposal (so the Reject would
    decide the revision, EP-08-001) and CS is already public, exploited or
    attacked.  Returning to the prior terms is then not allowed: the EJ must
    be answered with ET.  FAILURE in every other case, so the owner's Reject
    is decided by :class:`DecideRejectedEmbargoProposalNode` as usual.
    Read-only.
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        rejecting_actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.embargo_id = embargo_id
        self.rejecting_actor_id = rejecting_actor_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        if (
            _as_id(case.attributed_to) == self.rejecting_actor_id
            and case.em_state == EM.REVISE
            and case.proposed_embargo_ids == [self.embargo_id]
            and not pxa_is_embargo_eligible(case.current_status.pxa.state)
        ):
            self.feedback_message = (
                f"Owner rejected revision '{self.embargo_id}' of case"
                f" '{self.case_id}' with P/X/A set: the embargo ends (ET)"
                " rather than returning to its prior terms (EMB-04-002)"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS
        return Status.FAILURE
