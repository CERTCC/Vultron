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


"""Condition nodes for the ``CaseProposal`` admission decision (CP-05-002).

Every guard here sits on a **refusal arm**, and that changes what a safe answer
is. A Selector falls through on FAILURE, so for a node in the decline arm both
"no" and "I could not tell" hand control to the accept arm — in a refusal arm
FAILURE and SUCCESS can *both* mean admit. These nodes therefore let store
errors propagate rather than converting them to FAILURE, inverting the
catch-and-return convention BT-HELPER-01 uses elsewhere. See
``notes/bt-pitfalls.md`` § "A Refusal Arm in a Selector Fails Toward 'Admit'".

The second rule these guards share: every probe is keyed on the **proposal**,
never on the report. ``report_id`` arrives from the report the sender embedded in
its own proposal, so a report-keyed guard can be skipped by naming a report the
service has already seen.

Spec: ``specs/case-proposal.yaml`` CP-05-002, CP-05-004, CP-05-005, CP-05-006,
CP-05-008.
"""

import logging
from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.case.nodes.post_close import (
    case_is_fully_closed,
)
from vultron.core.behaviors.case.nodes.proposal_case_lookup import (
    proposal_case_ids,
)
from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.case_proposal_admission import (
    CaseProposalAdmissionRecord,
)
from vultron.core.models.case_proposal_decline import (
    CaseProposalDeclineRecord,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.errors import VultronWiringError

logger = logging.getLogger(__name__)


class CheckProposalAlreadyAnsweredNode(DataLayerAction):
    """Return SUCCESS if this proposal was already accepted.

    Guards the admission decision against re-adjudicating a proposal the service
    already answered. Once ``Accept(as_CaseProposal)`` has been sent the answer
    is irrevocable (CP-05-005), so a later "decline" must never reach the wire.

    The evidence is the ``CaseProposalAdmissionRecord`` for this proposal, an
    indexed single-row read.  The accept flow stores it in the same
    ``ActTransaction`` as the case and the queued ``Accept`` (ADR-0146), so the
    record exists exactly when the ``Accept`` was committed: a failed delivery
    rolls both back, and a later delivery is adjudicated afresh.

    **The probe is keyed on the proposal, never on the report.** ``report_id``
    is ``request.inner_object_id`` — the id of the report the *sender* embedded
    in its proposal — so it is chosen by whoever sent the proposal, and two
    proposals may name one report. A report-keyed "has a case been created?"
    probe would answer SUCCESS for a proposal this service never adjudicated,
    which short-circuits this arm *before* the admission call-out point is
    ticked and admits the proposal through ``LoadExistingCaseNode``'s
    duplicate-reuse path. A gate that a sender can skip by naming a report it
    has seen is not a gate.

    **Store errors are not caught here.** Returning FAILURE would let the
    enclosing Selector run the accept arm, and returning SUCCESS would do the
    same by skipping the decline arm — in a Selector, *both* directions of "I
    could not tell" mean admit. Letting the exception reach ``BTBridge`` fails
    the whole tree instead, which is the only safe answer available to a node in
    this position. See ``notes/bt-pitfalls.md`` § "A Refusal Arm in a Selector
    Fails Toward 'Admit'".

    A ``report_id=None`` redelivery of an accepted proposal is recognised here
    from the admission record, so it is not re-adjudicated; the accept arm
    then finds its case through the stored ``Accept`` (``LoadExistingCaseNode``,
    #4650), so no second case is created.
    """

    def __init__(
        self,
        proposal_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._proposal_id = proposal_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        admitted_id = CaseProposalAdmissionRecord.build_id(self._proposal_id)
        if self.datalayer.read(admitted_id) is None:
            return Status.FAILURE
        logger.info(
            "%s: proposal '%s' was already accepted — not re-adjudicating",
            self.name,
            self._proposal_id,
        )
        return Status.SUCCESS


class CheckProposalCaseFullyClosedNode(DataLayerAction):
    """Return SUCCESS if this proposal resolves to a fully closed case.

    A ``Create(as_CaseProposal)`` names a report, not a case, so the factory's
    post-close guard (``CaseOpenToExternalWritesNode``) cannot see which case
    it would touch.  This node answers that question for the proposal tree.
    When the case is fully closed (its ledger holds ``case_fully_closed``), the
    proposal is declined with ``Reject(as_CaseProposal)`` and nothing is
    written for the case (CP-05-006, CP-05-008, CM-23-013).

    Every case the proposal resolves to is checked: the proposer's own case
    for the report (a new proposal id from the owner, CP-05-008) and the case
    the proposal's stored ``Accept`` names (a redelivery, CP-05-006, also from
    a former owner after an ownership transfer).  The lookup is
    ``proposal_case_ids``, the one ``LoadExistingCaseNode`` uses to pick the
    case the accept arm reuses, so both nodes resolve the same case.  A
    different proposer's case for the same report is never this proposal's
    case (CP-05-008), so another party's closed case does not decline it.

    **Store errors are not caught here**, and a missing DataLayer raises.  The
    node sits on a refusal arm, so FAILURE ("not closed") runs the accept arm
    against a case that may be closed.  Only a whole-tree failure is safe.  See
    ``notes/bt-pitfalls.md`` § "A Refusal Arm in a Selector Fails Toward
    'Admit'".

    Attributes:
        closed_case_id: The fully closed case the proposal resolved to, set
            when the node returns SUCCESS; ``None`` otherwise.  The use case
            reads it to name the case in its ``REFUSED`` reason.
    """

    def __init__(
        self,
        proposal_id: str,
        proposer_uri: str,
        report_id: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._proposal_id = proposal_id
        self._proposer_uri = proposer_uri
        self._report_id = report_id
        self.closed_case_id: str | None = None

    def initialise(self) -> None:
        super().initialise()
        self.closed_case_id = None

    def update(self) -> Status:
        if self.datalayer is None:
            raise VultronWiringError(
                f"{self.name}: no DataLayer, so it cannot tell whether"
                f" proposal '{self._proposal_id}' resolves to a fully closed"
                f" case; failing the tree rather than admitting"
            )
        datalayer = cast(CasePersistence, self.datalayer)
        for case_id in proposal_case_ids(
            datalayer,
            self._proposal_id,
            self._proposer_uri,
            self._report_id,
            admission_record_is_prior=True,
            accepted_for_proposer_only=False,
        ):
            if case_is_fully_closed(datalayer, case_id):
                self.closed_case_id = case_id
                self.feedback_message = (
                    f"proposal '{self._proposal_id}' resolves to case"
                    f" '{case_id}', which is fully closed (CM-23-013)"
                )
                self.logger.info(
                    "%s: declining proposal '%s' from actor_id=%s: case '%s'"
                    " is fully closed (CP-05-006, CP-05-008, CM-23-013)",
                    self.name,
                    self._proposal_id,
                    self._proposer_uri,
                    case_id,
                )
                return Status.SUCCESS
        return Status.FAILURE


class CheckDeclineRecordExistsNode(DataLayerAction):
    """Return SUCCESS if this proposal was already declined.

    The decline record and its ``Reject`` commit in one transaction
    (``RefusalActTransaction``), so a stored record means the ``Reject`` was
    queued, and the decision stands without being re-made (CP-05-006).  A
    store error propagates: in a refusal arm, FAILURE would admit.
    """

    def __init__(self, proposal_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._proposal_id = proposal_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        record_id = CaseProposalDeclineRecord.build_id(self._proposal_id)
        if self.datalayer.read(record_id) is not None:
            return Status.SUCCESS
        return Status.FAILURE


__all__ = [
    "CheckProposalAlreadyAnsweredNode",
    "CheckProposalCaseFullyClosedNode",
    "CheckDeclineRecordExistsNode",
]
