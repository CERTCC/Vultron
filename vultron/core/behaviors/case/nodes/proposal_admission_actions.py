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


"""Action nodes for the ``CaseProposal`` admission decision (CP-05-002).

Three durable writes, and the ordering among them is the whole safety argument:

- :class:`RecordProposalAdmissionNode` stamps "this proposal began the accept
  path" *before* the case is created, which is the only proposal-keyed evidence
  available during the window where a case exists but no ``Accept`` has been
  emitted yet.
- :class:`RecordProposalDeclineNode` persists the refusal *before* the ``Reject``
  is queued, so a failed emit cannot fall through into an accept.
- :class:`EmitRejectCaseProposalNode` queues the ``Reject`` and then stamps the
  decline record with its id, which is what makes a repeated refusal idempotent.

Spec: ``specs/case-proposal.yaml`` CP-05-002, CP-05-004, CP-05-005, CP-05-006.
"""

import logging
from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerAction,
    _EmitSingleActivityBase,
)
from vultron.core.models.case_proposal_admission import (
    CaseProposalAdmissionRecord,
)
from vultron.core.models.case_proposal_decline import (
    CaseProposalDeclineRecord,
)
from vultron.core.ports.datalayer import DataLayer

logger = logging.getLogger(__name__)


class RecordProposalAdmissionNode(DataLayerAction):
    """Stamp "this proposal began the accept path" before anything is created.

    The first step of the accept flow, and deliberately ahead of case creation.
    The accept path creates the case and commits its ledger entries *before* it
    emits the ``Accept``, so a delivery that fails in that window leaves a case
    with no stored ``Accept`` and nothing proposal-keyed to show the proposal was
    ever adjudicated. The only evidence left would be report-keyed, and a
    report-keyed answer is not trustworthy here: ``report_id`` comes from the
    report the *sender* embedded, so two proposals can name one report and a
    report-keyed guard would report "already answered" for a proposal the service
    never saw.

    Writing this record first closes that window, and it is what lets
    :class:`CheckProposalAlreadyAnsweredNode` answer from an indexed single-row
    read instead of scanning every stored ``Accept``.

    Idempotent: a record that already exists is left alone, so a redelivery that
    resumes a half-built case does not disturb it.

    On the accept path FAILURE is the safe direction — this node runs before any
    write, so failing here aborts the Sequence with nothing to undo. It therefore
    keeps the ordinary ``_require_datalayer_and_actor`` convention rather than
    raising the way the refusal-arm nodes do.

    Spec: CP-05-002, CP-05-005, CP-05-006.
    """

    def __init__(
        self,
        proposal_id: str,
        vendor_uri: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._proposal_id = proposal_id
        self._vendor_uri = vendor_uri

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        record_id = CaseProposalAdmissionRecord.build_id(self._proposal_id)
        if self.datalayer.read(record_id) is not None:
            logger.debug(
                "%s: admission record for '%s' already present",
                self.name,
                self._proposal_id,
            )
            return Status.SUCCESS

        try:
            record = CaseProposalAdmissionRecord(
                proposal_id=self._proposal_id,
                case_actor_id=self.actor_id,
                vendor_uri=self._vendor_uri,
            )
            self.datalayer.create(record)
        except ValueError as exc:
            self.feedback_message = (
                f"could not record admission of '{self._proposal_id}': {exc}"
            )
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        logger.info(
            "%s: recorded admission of proposal '%s'",
            self.name,
            self._proposal_id,
        )
        return Status.SUCCESS


class RecordProposalDeclineNode(DataLayerAction):
    """Persist the decline decision *before* the ``Reject`` is queued.

    Writing the record first is what makes the decision terminal: if the emit
    that follows fails, ``CheckNoDeclineRecordNode`` still refuses the accept
    path, so the tree fails rather than creating the case and sending an
    ``Accept`` the service had already decided against.

    Idempotent — a record that already exists is left as it is, so the original
    decision (and its reason) survives redelivery.

    **Failing to record raises rather than returning FAILURE.** By the time this
    node runs the policy has already refused, and a FAILURE here would hand the
    enclosing Selector to the accept arm — admitting a proposal that was just
    declined. The record is the *only* thing that stops that, so if it cannot be
    written the tree must fail outright. This is the same reason
    ``CheckProposalAlreadyAnsweredNode`` does not catch its store errors.

    That applies to a **missing DataLayer or actor_id** too, not only to a
    rejected write. ``DataLayerAction._require_datalayer_and_actor`` returns
    FAILURE, which is the right answer on the accept path and the wrong one here,
    so this node checks the same preconditions and raises instead. Relying on
    some later node to fail the Sequence would make this gate's safety depend on
    an unrelated node's guards — exactly the coupling
    ``notes/bt-pitfalls.md`` § "A Refusal Arm in a Selector Fails Toward
    'Admit'" warns against.
    """

    def __init__(
        self,
        proposal_id: str,
        vendor_uri: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._proposal_id = proposal_id
        self._vendor_uri = vendor_uri

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            raise RuntimeError(
                f"{self.name}: no DataLayer or actor_id, so the decline of"
                f" '{self._proposal_id}' cannot be recorded and the refusal"
                f" cannot be made terminal; failing the tree rather than"
                f" admitting"
            )

        record_id = CaseProposalDeclineRecord.build_id(self._proposal_id)
        if self.datalayer.read(record_id) is not None:
            logger.debug(
                "%s: decline record for '%s' already present",
                self.name,
                self._proposal_id,
            )
            return Status.SUCCESS

        # Construction is inside the guarded region with the write: a
        # ValidationError on a malformed URI is as much a failure to record the
        # decline as a rejected insert, and both must raise (see the docstring).
        # ValidationError subclasses ValueError in Pydantic v2, so one clause
        # covers both.
        try:
            record = CaseProposalDeclineRecord(
                proposal_id=self._proposal_id,
                case_actor_id=self.actor_id,
                vendor_uri=self._vendor_uri,
            )
            self.datalayer.create(record)
        except ValueError as exc:
            raise RuntimeError(
                f"{self.name}: could not record the decline of"
                f" '{self._proposal_id}', so the refusal cannot be made"
                f" terminal; failing the tree rather than admitting: {exc}"
            ) from exc
        logger.info(
            "%s: recorded decline of proposal '%s'",
            self.name,
            self._proposal_id,
        )
        return Status.SUCCESS


class EmitRejectCaseProposalNode(_EmitSingleActivityBase):
    """Emit ``Reject(as_CaseProposal)`` through the shared outbox seam.

    CP-05-004: when the case actor service declines a proposal it MUST send
    ``Reject(as_CaseProposal)`` with the proposal embedded inline as ``object_``
    so the vendor has full context without a second round-trip (AKM-03-001).

    The node writes no case state and creates no participants.  It is reachable
    only from the decline arm, which runs ahead of ``ResolveCaseIdSelector`` and
    is guarded so it cannot be entered once case creation has begun — a Reject
    emitted after the accept flow's effects would tell the vendor "declined"
    while this store held a half-built case with committed ledger entries, the
    canonical/replica divergence CLP-10-009 exists to prevent.

    Unlike its sibling ``_EmitAcceptCaseProposalNode``, this node routes through
    ``_EmitSingleActivityBase`` rather than calling ``outbox_append`` in its own
    ``update()`` (OX-14-001).  That is where the outstanding-ask hook will live
    (ASK-04-008), and a Reject is precisely what *closes* the vendor's proposal.
    Migrating the Accept node to the same seam is #2881's remaining work.
    """

    def __init__(
        self,
        proposal_id: str,
        vendor_uri: str,
        proposal_dict: dict | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._proposal_id = proposal_id
        self._vendor_uri = vendor_uri
        self._proposal_dict = proposal_dict

    def _call_factory(self) -> tuple[str, str]:
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        assert self.datalayer is not None
        if self._proposal_dict is None:
            # A bare URI would be unreadable to the vendor (AKM-03-001), and
            # there is no inline proposal to fall back on, so refuse loudly
            # rather than sending a Reject the vendor cannot interpret.
            raise ValueError(
                f"{self.name}: no wire proposal available for"
                f" '{self._proposal_id}'; cannot build an inline Reject"
            )
        # The reason travels on the decline record rather than as a constructor
        # argument, so a Reject re-emitted on a later delivery carries the reason
        # the original decision gave.
        record = self.datalayer.read(
            CaseProposalDeclineRecord.build_id(self._proposal_id)
        )
        reason = getattr(record, "reason", None)
        return self.trigger_activity_factory.reject_case_proposal(
            actor=self.actor_id,
            proposal=self._proposal_dict,
            to=[self._vendor_uri],
            summary=reason,
        )

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        # Stamp the decline record with what was actually queued.  This is the
        # only durable trace that the proposer was told: the outbox loses the
        # activity on delivery and the object store cannot say whether it was
        # ever enqueued, so without this a redelivery after delivery mints a
        # fresh Reject every time.  See CheckRejectAlreadyAnsweredNode.
        assert self.datalayer is not None
        record_id = CaseProposalDeclineRecord.build_id(self._proposal_id)
        record = self.datalayer.read(record_id)
        if isinstance(record, CaseProposalDeclineRecord):
            cast(DataLayer, self.datalayer).save(
                record.model_copy(update={"reject_activity_id": activity_id})
            )
        else:
            # The decline arm writes the record before this node runs, so its
            # absence means the ordering was broken rather than that no decision
            # was taken.  Say so loudly instead of leaving the resend guard
            # permanently unable to answer.
            logger.error(
                "%s: queued Reject '%s' for proposal '%s' but found no decline"
                " record to stamp — the refusal is not idempotent",
                self.name,
                activity_id,
                self._proposal_id,
            )
        logger.info(
            "%s: Declined proposal '%s' — queued Reject '%s' to outbox "
            "for vendor '%s'",
            self.name,
            self._proposal_id,
            activity_id,
            self._vendor_uri,
        )


__all__ = [
    "RecordProposalAdmissionNode",
    "RecordProposalDeclineNode",
    "EmitRejectCaseProposalNode",
]
