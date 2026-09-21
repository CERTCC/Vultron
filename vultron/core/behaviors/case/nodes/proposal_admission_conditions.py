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

Spec: ``specs/case-proposal.yaml`` CP-05-002, CP-05-004, CP-05-005, CP-05-006.
"""

import logging
from typing import Any, cast

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.case_proposal_admission import (
    CaseProposalAdmissionRecord,
)
from vultron.core.models.case_proposal_decline import (
    CaseProposalDeclineRecord,
)
from vultron.core.ports.case_persistence import CasePersistence

logger = logging.getLogger(__name__)


class CheckProposalAlreadyAnsweredNode(DataLayerAction):
    """Return SUCCESS if the accept path has already begun for this proposal.

    Guards the admission decision against re-adjudicating a proposal the service
    already answered. Once ``Accept(as_CaseProposal)`` has been sent the answer
    is irrevocable (CP-05-005), so a later "decline" must never reach the wire.

    "Answered" is deliberately wider than "an Accept was sent". ``main_flow``
    creates the case and commits its ledger entries *before* it emits the
    ``Accept``, so a delivery that fails in between leaves a case with no stored
    ``Accept``. An Accept-only guard cannot see that, and a later declining
    delivery would then Reject a case this store had already half-built — and,
    because the decline record blocks the accept arm from then on, that case
    could never be completed.

    **Every probe here is keyed on the proposal, never on the report.** That
    distinction is the whole correctness of this node. ``report_id`` is
    ``request.inner_object_id`` — the id of the report the *sender* embedded in
    its proposal — so it is chosen by whoever sent the proposal, and two
    proposals may name one report. A report-keyed "has a case been created?"
    probe therefore answers SUCCESS for a proposal this service never
    adjudicated, which short-circuits this arm *before* the admission call-out
    point is ticked and admits the proposal through ``_LoadExistingCaseNode``'s
    duplicate-reuse path. A gate that a sender can skip by naming a report it
    has seen is not a gate. So two proposal-keyed things count as answered:

    - a ``CaseProposalAdmissionRecord`` for this proposal, written as
      ``main_flow``'s first step and therefore present from before the case
      exists — this is what covers the half-built case above, and it is an
      indexed single-row read; or
    - a stored ``Accept`` whose object is this proposal, which is the fallback
      for a store written before the admission record existed.

    The ``Accept`` fallback rehydrates every ``Accept`` row, so it runs only
    when it can matter: a report-keyed lookup is used purely as a cheap
    *negative* prefilter, because no case for the report means nothing was
    answered and no scan is needed. That keeps the common case — a first-time
    proposal under the admitting default — off the scan entirely, while the
    positive answer still comes only from proposal-keyed evidence.

    **Store errors are not caught here.** Returning FAILURE would let the
    enclosing Selector run the accept arm, and returning SUCCESS would do the
    same by skipping the decline arm — in a Selector, *both* directions of "I
    could not tell" mean admit. Letting the exception reach ``BTBridge`` fails
    the whole tree instead, which is the only safe answer available to a node in
    this position. See ``notes/bt-pitfalls.md`` § "A Refusal Arm in a Selector
    Fails Toward 'Admit'".

    Residual gap: a ``report_id=None`` redelivery still creates a duplicate case
    on the accept path, tracked in #2890. The admission record makes that
    detectable here, but ``_LoadExistingCaseNode`` is the node that would have
    to act on it.
    """

    def __init__(
        self,
        proposal_id: str,
        report_id: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._proposal_id = proposal_id
        self._report_id = report_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        admitted_id = CaseProposalAdmissionRecord.build_id(self._proposal_id)
        if self.datalayer.read(admitted_id) is not None:
            logger.info(
                "%s: proposal '%s' already began the accept path — not"
                " re-adjudicating",
                self.name,
                self._proposal_id,
            )
            return Status.SUCCESS

        # Negative prefilter only: no case for this report means nothing was
        # answered, so the Accept scan below can be skipped.  A case that *does*
        # exist proves nothing on its own — it may belong to another proposal
        # naming the same report — so the positive answer still comes from the
        # proposal-keyed scan.
        if self._report_id is not None:
            existing = cast(
                CasePersistence, self.datalayer
            ).find_case_by_report_id(self._report_id)
            if existing is None:
                return Status.FAILURE

        if (
            find_activity_for_proposal(
                self.datalayer, self._proposal_id, "Accept"
            )
            is not None
        ):
            logger.info(
                "%s: proposal '%s' was already accepted — not re-adjudicating",
                self.name,
                self._proposal_id,
            )
            return Status.SUCCESS
        return Status.FAILURE


class CheckDeclineRecordExistsNode(DataLayerAction):
    """Return SUCCESS if this proposal was already declined."""

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


class CheckNoDeclineRecordNode(DataLayerAction):
    """Return SUCCESS only if this proposal has *not* been declined.

    The precondition on the accept path. It is the guard that stops a failed
    ``Reject`` emit from falling through into case creation — the enclosing
    Selector will try the accept arm, and this node refuses it.

    On a store error this returns FAILURE: when the service cannot tell whether
    it already declined, creating the case is the wrong way to guess.
    """

    def __init__(self, proposal_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._proposal_id = proposal_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        record_id = CaseProposalDeclineRecord.build_id(self._proposal_id)
        try:
            record = self.datalayer.read(record_id)
        except Exception as exc:  # noqa: BLE001 — see docstring
            self.feedback_message = (
                f"could not determine whether proposal "
                f"'{self._proposal_id}' was declined: {exc}"
            )
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        if record is not None:
            self.feedback_message = (
                f"proposal '{self._proposal_id}' was declined; "
                "the accept path must not run"
            )
            logger.info("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        return Status.SUCCESS


class CheckRejectAlreadyAnsweredNode(DataLayerAction):
    """Return SUCCESS if this service has already queued a ``Reject`` for it.

    Lets the resend arm distinguish "declined and told them" from "declined but
    the ``Reject`` never made it out", so only the second case re-emits.

    **The question is answered from the decline record, not from the outbox or
    the object store.** Each of the other two readings is wrong in a different
    direction, and the pair of them is why this needs a third state:

    - *Stored?* The adapter persists the activity and *then* ``_emit_through_seam``
      enqueues it, so a queue write that faults leaves a stored ``Reject``
      nobody will ever deliver. A store-only check reads that as "already told
      them" and reports SUCCESS forever with an empty outbox — a silently lost
      refusal.
    - *Queued?* ``outbox_pop`` removes the activity on delivery while its stored
      copy remains, so a ``Reject`` that was successfully **delivered** is
      indistinguishable from one never queued. An outbox-only check therefore
      returns FAILURE forever after delivery, and the emit that follows mints a
      *fresh* ``Reject`` on every later delivery of the same proposal. That is
      unbounded: a proposer (or anyone) replaying a declined proposal N times
      gets N persisted and queued ``Reject`` activities.

    ``CaseProposalDeclineRecord.reject_activity_id`` records what this service
    actually queued, which is the fact both readings were proxying for. It is set
    once the emit succeeds and never cleared, so "declined and answered" is
    durable across delivery, and "declined but unanswered" stays recoverable.
    """

    def __init__(self, proposal_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._proposal_id = proposal_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        record = self.datalayer.read(
            CaseProposalDeclineRecord.build_id(self._proposal_id)
        )
        if getattr(record, "reject_activity_id", None) is not None:
            return Status.SUCCESS
        return Status.FAILURE


def activity_names_proposal(activity: Any, proposal_id: str) -> bool:
    """Return True if *activity*'s top-level object is *proposal_id*.

    The object round-trips as the rehydrated ``as_CaseProposal``, as the bare URI
    storage dehydrated it to, or as a plain dict, so all three shapes are probed.
    Only the **top-level** object is compared, which is what keeps unrelated
    activities out: an ``Accept(Offer(VulnerabilityReport))`` from validate-report
    names the Offer, not the proposal.
    """
    obj = getattr(activity, "object_", None)
    if obj == proposal_id:
        return True
    if getattr(obj, "id_", None) == proposal_id:
        return True
    return isinstance(obj, dict) and obj.get("id") == proposal_id


def find_activity_for_proposal(
    datalayer: Any, proposal_id: str, activity_type: str
) -> Any | None:
    """Return a stored *activity_type* activity whose object is *proposal_id*."""
    for activity in datalayer.list_objects(activity_type) or []:
        if str(getattr(activity, "type_", "")) != activity_type:
            continue
        if activity_names_proposal(activity, proposal_id):
            return activity
    return None


__all__ = [
    "CheckProposalAlreadyAnsweredNode",
    "CheckDeclineRecordExistsNode",
    "CheckNoDeclineRecordNode",
    "CheckRejectAlreadyAnsweredNode",
    "activity_names_proposal",
    "find_activity_for_proposal",
]
