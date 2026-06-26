"""BT tree for the CreateCaseProposal received-side use case.

Case-actor side: handles an inbound ``Create(as_CaseProposal)`` and emits
two outbound activities in sequence:

  1. ``Accept(as_CaseProposal)`` — acknowledgement to the vendor
  2. ``Create(VulnerabilityCase)`` — case announcement to the vendor

A durable ``PendingCreateCaseActivity`` marker is written to the DataLayer
after step 1 and cleared on successful completion of step 2 so that a retry
runner (#1139) can recover the obligation if delivery of step 2 fails.

Idempotency (CP-05-006):

The top-level tree is a Selector with two branches:

* **AC-3 guard** — ``_CheckMarkerExistsNode``: if a
  ``PendingCreateCaseActivity`` marker already exists for this proposal_id,
  Accept was already sent and Create delivery is still pending; the retry
  runner owns recovery, so return SUCCESS immediately (no re-send).

* **Normal / duplicate flow** — a Sequence whose first step is itself a
  Selector between ``_LoadExistingCaseNode`` (AC-1/AC-2: finds and reuses
  an existing ``VulnerabilityCase`` for the same report) and
  ``_CreateCaseFromProposalNode`` (normal path: creates a new case).  The
  remaining four steps are unchanged.

Spec: ``specs/case-proposal.yaml`` CP-05-001 through CP-05-006.
"""

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

import logging
from typing import Any, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.activity import (
    VultronAccept,
    VultronCreateCaseActivity,
)
from vultron.core.models.case import VultronCase
from vultron.core.models.pending_create_case_activity import (
    PendingCreateCaseActivity,
)
from vultron.core.ports.case_persistence import CaseOutboxPersistence

logger = logging.getLogger(__name__)


class _CheckMarkerExistsNode(DataLayerAction):
    """Return SUCCESS if a ``PendingCreateCaseActivity`` marker already exists.

    AC-3 guard (CP-05-006): if the marker is present, ``Accept(CaseProposal)``
    was already sent for this proposal and a ``Create(VulnerabilityCase)``
    delivery is still pending.  The retry runner (#1139) owns recovery; the
    current delivery should be a no-op to avoid duplicate Accepts on the
    vendor side.

    Returns FAILURE when no marker is found, allowing the outer Selector to
    proceed to the normal / duplicate flow.
    """

    def __init__(self, proposal_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._proposal_id = proposal_id

    def update(self) -> Status:
        if self.datalayer is None:
            return Status.FAILURE

        marker_id = PendingCreateCaseActivity.build_id(self._proposal_id)
        existing = self.datalayer.read(marker_id)
        if isinstance(existing, PendingCreateCaseActivity):
            logger.info(
                "%s: PendingCreateCaseActivity marker found for proposal '%s'"
                " — Accept already sent; skipping re-send (CP-05-006 AC-3)",
                self.name,
                self._proposal_id,
            )
            return Status.SUCCESS

        return Status.FAILURE


class _LoadExistingCaseNode(DataLayerAction):
    """Find an existing ``VulnerabilityCase`` for *report_id* and load it.

    AC-1 / AC-2 (CP-05-006): detects a duplicate ``Create(as_CaseProposal)``
    for a report that already has a case.  Writes the existing ``case_id`` to
    the blackboard so ``_EmitAcceptCaseProposalNode`` and
    ``_WriteCreateCaseMarkerNode`` can reference it, then returns SUCCESS.

    Returns FAILURE when no existing case is found, allowing the outer
    Selector to fall through to ``_CreateCaseFromProposalNode`` (normal path).
    """

    def __init__(
        self,
        report_id: str | None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._report_id = report_id

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.WRITE
        )

    def update(self) -> Status:
        if self.datalayer is None:
            return Status.FAILURE

        if self._report_id is None:
            return Status.FAILURE

        existing = self.datalayer.find_case_by_report_id(self._report_id)
        if existing is None:
            return Status.FAILURE

        self.blackboard.case_id = existing.id_
        logger.info(
            "%s: Found existing VulnerabilityCase '%s' for report '%s'"
            " — reusing for duplicate proposal (CP-05-006 AC-1/AC-2)",
            self.name,
            existing.id_,
            self._report_id,
        )
        return Status.SUCCESS


class _CreateCaseFromProposalNode(DataLayerAction):
    """Create a VulnerabilityCase from the proposal and write case_id to blackboard.

    The case-actor service is the ``attributed_to`` author of the new case,
    preserving AS2 "I created this" semantics (CP-05-003, ADR-0023).
    """

    def __init__(
        self,
        report_id: str | None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._report_id = report_id

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.WRITE
        )

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.feedback_message = "DataLayer or actor_id not available"
            return Status.FAILURE

        case = VultronCase(attributed_to=self.actor_id)
        if self._report_id is not None:
            case.vulnerability_reports.append(self._report_id)

        try:
            self.datalayer.create(case)
        except ValueError as exc:
            self.feedback_message = f"Case creation failed: {exc}"
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        self.blackboard.case_id = case.id_
        logger.info(
            "%s: Created VulnerabilityCase '%s' from proposal",
            self.name,
            case.id_,
        )
        return Status.SUCCESS


class _EmitAcceptCaseProposalNode(DataLayerAction):
    """Build Accept(CaseProposal), store it, and queue it to the outbox.

    Sets ``accept_activity_id`` on the blackboard so the downstream
    ``_EmitCreateVulnerabilityCaseNode`` can set the causal ``context``
    link (CP-05-003).

    Reads ``case_id`` from the blackboard (written by either
    ``_LoadExistingCaseNode`` or ``_CreateCaseFromProposalNode``) and
    sets ``result`` on the ``Accept`` activity to that URI.  For a
    duplicate proposal, this carries the existing-case reference required
    by CP-05-006 AC-2.  For a first-time proposal, it ties the Accept to
    the newly-created case.

    Failure here returns FAILURE so the Sequence aborts before the
    Create(VulnerabilityCase) is sent — the vendor should not receive an
    unacknowledged case (BT-14-001).
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
        # proposal_dict is the wire-serialised proposal (model_dump(by_alias=True)).
        # Storing it inline satisfies CP-05-003 and the outbox MV-09-001 requirement.
        self._object = (
            proposal_dict if proposal_dict is not None else proposal_id
        )

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="accept_activity_id", access=py_trees.common.Access.WRITE
        )
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.feedback_message = "DataLayer or actor_id not available"
            return Status.FAILURE

        try:
            case_id: str | None = self.blackboard.get("case_id")
        except KeyError:
            case_id = None

        activity = VultronAccept(
            actor=self.actor_id,
            object_=self._object,
            to=[self._vendor_uri],
            result=case_id,
        )

        try:
            self.datalayer.create(activity)
        except ValueError as exc:
            self.feedback_message = (
                f"Accept(CaseProposal) activity creation failed: {exc}"
            )
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
            self.actor_id, activity.id_
        )
        self.blackboard.accept_activity_id = activity.id_
        logger.info(
            "%s: Queued Accept(CaseProposal) '%s' to outbox for vendor '%s'",
            self.name,
            activity.id_,
            self._vendor_uri,
        )
        return Status.SUCCESS


class _EmitCreateVulnerabilityCaseNode(DataLayerAction):
    """Reconstruct Create(VulnerabilityCase) from the stored marker and queue it.

    Reads the pre-constructed ``Create(VulnerabilityCase)`` payload from the
    ``PendingCreateCaseActivity`` marker written by
    ``_WriteCreateCaseMarkerNode``.  Using the stored payload (rather than
    building a new activity from blackboard fields) guarantees that the
    activity ``id_`` in the DataLayer and outbox is identical to the ``id_``
    recorded in the marker.  This is critical for CP-05-005 idempotency: the
    retry runner checks outbox membership by the marker's stored ``id_``, so
    a fresh ``id_`` here would cause a duplicate delivery after crash/restart.

    Failure returns FAILURE so the enclosing Sequence surfaces it; the Accept
    has already been sent at this point (CP-05-005 covers the retry case).
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
            self.feedback_message = "DataLayer or actor_id not available"
            return Status.FAILURE

        # Read the pre-built payload from the marker to guarantee id_ consistency
        # with CP-05-005 retry logic.
        marker_id = PendingCreateCaseActivity.build_id(self._proposal_id)
        raw_marker = self.datalayer.read(marker_id)
        if not isinstance(raw_marker, PendingCreateCaseActivity):
            self.feedback_message = (
                f"PendingCreateCaseActivity marker '{marker_id}' not found"
                " or wrong type; cannot emit Create(VulnerabilityCase)"
            )
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        if not raw_marker.create_activity_payload:
            self.feedback_message = (
                f"Marker '{marker_id}' has no create_activity_payload"
            )
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        try:
            activity = VultronCreateCaseActivity.model_validate(
                raw_marker.create_activity_payload
            )
        except Exception as exc:
            self.feedback_message = (
                f"Could not reconstruct Create(VulnerabilityCase)"
                f" from marker '{marker_id}': {exc}"
            )
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        try:
            self.datalayer.create(activity)
        except ValueError as exc:
            self.feedback_message = (
                f"Create(VulnerabilityCase) activity creation failed: {exc}"
            )
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        try:
            cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
                self.actor_id, activity.id_
            )
        except Exception as exc:
            self.feedback_message = (
                f"Failed to enqueue Create(VulnerabilityCase) to outbox: {exc}"
            )
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        logger.info(
            "%s: Queued Create(VulnerabilityCase) '%s' from proposal '%s'",
            self.name,
            activity.id_,
            self._proposal_id,
        )
        return Status.SUCCESS


class _WriteCreateCaseMarkerNode(DataLayerAction):
    """Write a ``PendingCreateCaseActivity`` marker to the DataLayer.

    Called after ``Accept(CaseProposal)`` has been sent and before
    ``Create(VulnerabilityCase)`` is attempted.  The marker records the
    obligation so that a retry runner (#1139) can complete it if the
    subsequent ``Create(VulnerabilityCase)`` delivery fails (CP-05-005).

    Reads ``case_id`` and ``accept_activity_id`` from the blackboard to
    pre-construct the ``Create(VulnerabilityCase)`` payload stored in the
    marker.  Returns FAILURE if either blackboard key is missing or the
    DataLayer write fails, so the Sequence halts before attempting delivery.
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

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="accept_activity_id", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.feedback_message = "DataLayer or actor_id not available"
            return Status.FAILURE

        try:
            case_id = self.blackboard.get("case_id")
        except KeyError:
            self.feedback_message = "case_id not found in blackboard"
            return Status.FAILURE

        try:
            accept_activity_id = self.blackboard.get("accept_activity_id")
        except KeyError:
            self.feedback_message = (
                "accept_activity_id not found in blackboard"
            )
            return Status.FAILURE

        # Pre-construct the payload that will be (re-)sent as
        # Create(VulnerabilityCase).  Mirrors the logic in
        # _EmitCreateVulnerabilityCaseNode so the retry runner (#1139)
        # can reconstruct the exact same activity without re-running the BT.
        create_activity = VultronCreateCaseActivity(
            actor=self.actor_id,
            object_=case_id,
            context=accept_activity_id,
            to=[self._vendor_uri],
        )
        payload = create_activity.model_dump(by_alias=True)

        marker = PendingCreateCaseActivity(
            proposal_id=self._proposal_id,
            case_actor_id=self.actor_id,
            vendor_uri=self._vendor_uri,
            create_activity_payload=payload,
        )

        try:
            self.datalayer.save(marker)
        except Exception as exc:
            self.feedback_message = f"Failed to write marker: {exc}"
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        logger.info(
            "%s: Wrote PendingCreateCaseActivity marker for proposal '%s'",
            self.name,
            self._proposal_id,
        )
        return Status.SUCCESS


class _ClearCreateCaseMarkerNode(DataLayerAction):
    """Remove the ``PendingCreateCaseActivity`` marker after successful delivery.

    Called after ``Create(VulnerabilityCase)`` has been queued to the
    outbox.  Deletes the marker so the retry runner (#1139) does not
    re-deliver an already-sent activity (CP-05-005, AC-3).

    Always returns SUCCESS: the ``Create(VulnerabilityCase)`` has already
    been delivered; a cleanup failure must not roll back the delivery or
    fail the Sequence.  A warning is logged if the delete fails so that
    stale markers can be detected during retry-runner inspection.
    """

    def __init__(
        self,
        proposal_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._proposal_id = proposal_id

    def update(self) -> Status:
        if self.datalayer is None:
            logger.warning(
                "%s: DataLayer not available — marker '%s' may be stale",
                self.name,
                self._proposal_id,
            )
            return Status.SUCCESS

        marker_id = PendingCreateCaseActivity.build_id(self._proposal_id)
        deleted = self.datalayer.delete("PendingCreateCaseActivity", marker_id)
        if deleted:
            logger.info(
                "%s: Cleared PendingCreateCaseActivity marker for proposal '%s'",
                self.name,
                self._proposal_id,
            )
        else:
            logger.warning(
                "%s: PendingCreateCaseActivity marker for proposal '%s'"
                " was not found during cleanup — may already be cleared",
                self.name,
                self._proposal_id,
            )
        return Status.SUCCESS


def create_case_proposal_received_tree(
    report_id: str | None,
    proposal_id: str,
    vendor_uri: str,
    proposal_dict: dict | None = None,
) -> py_trees.behaviour.Behaviour:
    """Return the received-side BT for processing a ``Create(as_CaseProposal)``.

    The tree is a two-branch Selector implementing CP-05-006 idempotency:

    **Branch 1 — AC-3 guard** (``_CheckMarkerExistsNode``):
      If a ``PendingCreateCaseActivity`` marker already exists for this
      proposal_id, ``Accept(CaseProposal)`` was already sent and
      ``Create(VulnerabilityCase)`` delivery is still pending.  Return SUCCESS
      immediately — the retry runner owns recovery; do not re-send Accept.

    **Branch 2 — normal / duplicate flow** (Sequence of five nodes):
      First, a sub-Selector resolves which ``VulnerabilityCase`` to use:

      * ``_LoadExistingCaseNode`` (AC-1/AC-2): if a case already exists for
        *report_id*, write its ID to the blackboard and succeed — the vendor is
        resending the proposal; reuse the existing case rather than creating a
        second one.
      * ``_CreateCaseFromProposalNode`` (normal path): create a new case.

      Then the remaining four nodes proceed as for the original happy path:

      3. ``_EmitAcceptCaseProposalNode`` — emits Accept(as_CaseProposal)
      4. ``_WriteCreateCaseMarkerNode`` — writes durable retry marker
         (CP-05-005)
      5. ``_EmitCreateVulnerabilityCaseNode`` — emits
         Create(VulnerabilityCase)
      6. ``_ClearCreateCaseMarkerNode`` — removes marker on success
         (CP-05-005)

    If node 5 fails, the marker written in node 4 remains in the DataLayer so
    that a retry runner (#1139) can complete the ``Create(VulnerabilityCase)``
    delivery independently.

    Spec: CP-05-001 through CP-05-006.

    Args:
        report_id: URI of the VulnerabilityReport embedded in the proposal
            (CP-01-004). Pass ``None`` if the report URI could not be
            extracted — the case will be created without a report link.
        proposal_id: URI of the ``as_CaseProposal`` object.
        vendor_uri: URI of the vendor actor to whom the responses are sent.
        proposal_dict: Wire-serialised proposal dict (``model_dump(by_alias=True)``).
            When supplied, the Accept's ``object_`` carries the full inline proposal,
            satisfying CP-05-003 and the MV-09-001 outbox requirement. Falls back
            to bare URI when ``None``.

    Returns:
        A py_trees Selector behaviour ready for ``BTBridge.execute_with_setup``.
    """
    # Sub-Selector: reuse existing case (duplicate) OR create new (normal path)
    case_resolution = py_trees.composites.Selector(
        name="ResolveCaseIdSelector",
        memory=False,
        children=[
            _LoadExistingCaseNode(report_id=report_id),
            _CreateCaseFromProposalNode(report_id=report_id),
        ],
    )

    # Main flow: resolve case → emit Accept → write marker → emit Create → clear
    main_flow = py_trees.composites.Sequence(
        name="CreateCaseProposalReceivedBT",
        memory=False,
        children=[
            case_resolution,
            _EmitAcceptCaseProposalNode(
                proposal_id=proposal_id,
                vendor_uri=vendor_uri,
                proposal_dict=proposal_dict,
            ),
            _WriteCreateCaseMarkerNode(
                proposal_id=proposal_id,
                vendor_uri=vendor_uri,
            ),
            _EmitCreateVulnerabilityCaseNode(
                proposal_id=proposal_id,
                vendor_uri=vendor_uri,
            ),
            _ClearCreateCaseMarkerNode(proposal_id=proposal_id),
        ],
    )

    return py_trees.composites.Selector(
        name="CreateCaseProposalIdempotencySelector",
        memory=False,
        children=[
            _CheckMarkerExistsNode(proposal_id=proposal_id),
            main_flow,
        ],
    )
