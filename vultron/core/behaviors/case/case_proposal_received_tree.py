"""BT tree for the CreateCaseProposal received-side use case.

Case-actor side: handles an inbound ``Create(as_CaseProposal)`` and emits
two outbound activities in sequence:

  1. ``Accept(as_CaseProposal)`` — acknowledgement to the vendor
  2. ``Create(VulnerabilityCase)`` — case announcement to the vendor

Spec: ``specs/case-proposal.yaml`` CP-05-001 through CP-05-004.
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
from vultron.core.ports.case_persistence import CaseOutboxPersistence

logger = logging.getLogger(__name__)


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

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.feedback_message = "DataLayer or actor_id not available"
            return Status.FAILURE

        activity = VultronAccept(
            actor=self.actor_id,
            object_=self._object,
            to=[self._vendor_uri],
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
    """Build Create(VulnerabilityCase), store it, and queue it to the outbox.

    Reads ``case_id`` and ``accept_activity_id`` from the blackboard.
    Sets ``context`` to the Accept activity URI for causal traceability
    (CP-05-003, ADR-0023).

    Failure returns FAILURE so the Sequence surface it; the Accept has
    already been sent at this point (CP-05-005 covers the retry case).
    """

    def __init__(
        self,
        vendor_uri: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
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

        # CP-05-003: context = URI of the Accept(CaseProposal) activity
        activity = VultronCreateCaseActivity(
            actor=self.actor_id,
            object_=case_id,
            context=accept_activity_id,
            to=[self._vendor_uri],
        )

        try:
            self.datalayer.create(activity)
        except ValueError as exc:
            self.feedback_message = (
                f"Create(VulnerabilityCase) activity creation failed: {exc}"
            )
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
            self.actor_id, activity.id_
        )
        logger.info(
            "%s: Queued Create(VulnerabilityCase) '%s' for case '%s'",
            self.name,
            activity.id_,
            case_id,
        )
        return Status.SUCCESS


def create_case_proposal_received_tree(
    report_id: str | None,
    proposal_id: str,
    vendor_uri: str,
    proposal_dict: dict | None = None,
) -> py_trees.behaviour.Behaviour:
    """Return the received-side BT for processing a ``Create(as_CaseProposal)``.

    The tree is a Sequence of three leaf nodes:

    1. ``_CreateCaseFromProposalNode`` — creates VulnerabilityCase
    2. ``_EmitAcceptCaseProposalNode`` — emits Accept(as_CaseProposal)
    3. ``_EmitCreateVulnerabilityCaseNode`` — emits Create(VulnerabilityCase)

    Spec: CP-05-001 through CP-05-004.

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
        A py_trees Sequence behaviour ready for ``BTBridge.execute_with_setup``.
    """
    return py_trees.composites.Sequence(
        name="CreateCaseProposalReceivedBT",
        memory=False,
        children=[
            _CreateCaseFromProposalNode(report_id=report_id),
            _EmitAcceptCaseProposalNode(
                proposal_id=proposal_id,
                vendor_uri=vendor_uri,
                proposal_dict=proposal_dict,
            ),
            _EmitCreateVulnerabilityCaseNode(vendor_uri=vendor_uri),
        ],
    )
