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


"""Outbound-activity emit leaf nodes for the CaseProposal received tree.

Queue ``Accept(as_CaseProposal)`` and ``Create(VulnerabilityCase)`` to the
CaseActor outbox. Composed by ``create_case_proposal_received_tree``
(BTND-07-003).
"""

import logging

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.case.nodes.proposal_retry_marker import (
    announced_case_id,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    _EmitSingleActivityBase,
)
from vultron.core.models.pending_create_case_activity import (
    PendingCreateCaseActivity,
)
from vultron.errors import VultronError

logger = logging.getLogger(__name__)


class EmitAcceptCaseProposalNode(_EmitSingleActivityBase):
    """Build Accept(CaseProposal), store it, and queue it to the outbox.

    Sets ``accept_activity_id`` on the blackboard so the downstream
    ``WriteCreateCaseMarkerNode`` can set the causal ``in_reply_to``
    link on ``Create(VulnerabilityCase)`` (CP-05-003, ADR-0045).

    Reads ``case_id`` from the blackboard (written by either
    ``LoadExistingCaseNode`` or ``CreateCaseFromProposalNode``) and
    sets ``result`` on the ``Accept`` activity to that URI.  For a
    duplicate proposal, this carries the existing-case reference required
    by CP-05-006 AC-2.  For a first-time proposal, it ties the Accept to
    the newly-created case.

    Failure here returns FAILURE so the Sequence aborts before the
    Create(VulnerabilityCase) is sent — the report receiver should not receive an
    unacknowledged case (BT-14-001).
    """

    def __init__(
        self,
        proposal_id: str,
        proposer_uri: str,
        proposal_dict: dict | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._proposal_id = proposal_id
        self._proposer_uri = proposer_uri
        # proposal_dict is the wire-serialised proposal (model_dump(by_alias=True)).
        # The factory embeds it inline (CP-05-003, AKM-03-001); without it there
        # is nothing to embed, so the emit fails rather than sending a bare id.
        self._proposal_dict = proposal_dict

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=False),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "accept_activity_id": PortInformation(data_type=str, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "accept_activity_id": "/accept_activity_id",
        }

    def initialise(self) -> None:
        super().initialise()
        try:
            self._case_id_bb: str | None = self.get_input("case_id")
        except (NoDataAvailable, NotImplementedError):
            self._case_id_bb = None

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        if (f := self._require_factory()) is not None:
            logger.error("%s: %s", self.name, self.feedback_message)
            return f
        assert self.trigger_activity_factory is not None
        if self._proposal_dict is None:
            self.feedback_message = (
                f"Accept(CaseProposal) for '{self._proposal_id}' has no"
                " proposal to embed (CP-05-003, AKM-03-001)"
            )
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        case_id = self._case_id_bb

        # The adapter builds, persists, and seals the Accept, so the body the
        # outbox delivers is the body the factory produced (VM-08-003).
        try:
            activity_id, _blob = (
                self.trigger_activity_factory.accept_case_proposal(
                    actor=self.actor_id,
                    proposal=self._proposal_dict,
                    to=[self._proposer_uri],
                    result=case_id,
                )
            )
        except VultronError as exc:
            self.feedback_message = (
                f"Accept(CaseProposal) activity creation failed: {exc}"
            )
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        # Route through the shared emit seam (OX-14-001, ASK-04-008).
        # outbox_append is now called inside _emit_through_seam, not directly
        # (ADR-0073: the queue lives in the owning actor's store).
        self._emit_through_seam(activity_id, "")
        self._set_output("accept_activity_id", activity_id)
        logger.info(
            "%s: Queued Accept(CaseProposal) '%s' to outbox for report receiver '%s'",
            self.name,
            activity_id,
            self._proposer_uri,
        )
        return Status.SUCCESS


class EmitCreateVulnerabilityCaseNode(_EmitSingleActivityBase):
    """Reconstruct Create(VulnerabilityCase) from the stored marker and queue it.

    Reads the pre-constructed ``Create(VulnerabilityCase)`` payload from the
    ``PendingCreateCaseActivity`` marker written by
    ``WriteCreateCaseMarkerNode``.  Using the stored payload (rather than
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
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._proposal_id = proposal_id

    def _already_queued(self) -> bool:
        """Whether this proposal's Create was queued by an earlier delivery.

        ``WriteCreateCaseMarkerNode`` writes no marker for a redelivered
        proposal whose Create is already stored, so a missing marker with
        that activity present is the announced case, not a lost marker
        (CP-05-005, #4146).
        """
        assert self.datalayer is not None
        case_id = announced_case_id(self.datalayer, self._proposal_id)
        if case_id is None:
            return False
        logger.info(
            "%s: Create(VulnerabilityCase) of case '%s' for proposal '%s' was"
            " already queued — not announcing the case again (CP-05-005)",
            self.name,
            case_id,
            self._proposal_id,
        )
        return True

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        # Read the pre-built payload from the marker to guarantee id_ consistency
        # with CP-05-005 retry logic.
        marker_id = PendingCreateCaseActivity.build_id(self._proposal_id)
        raw_marker = self.datalayer.read(marker_id)
        if raw_marker is None:
            try:
                already_queued = self._already_queued()
            except VultronError as exc:
                # WriteCreateCaseMarkerNode fails the tree on this first; here
                # it only means there is nothing this node may emit.
                logger.warning("%s: %s", self.name, exc)
                already_queued = False
            if already_queued:
                return Status.SUCCESS
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

        if (f := self._require_factory()) is not None:
            logger.error("%s: %s", self.name, self.feedback_message)
            return f
        assert self.trigger_activity_factory is not None

        # The adapter rebuilds the prepared activity, persists it under the
        # marker's id, and seals the body the outbox will deliver (VM-08-003).
        try:
            activity_id, _blob = (
                self.trigger_activity_factory.emit_prepared_create_case(
                    raw_marker.create_activity_payload
                )
            )
        except VultronError as exc:
            self.feedback_message = (
                f"Could not emit Create(VulnerabilityCase)"
                f" from marker '{marker_id}': {exc}"
            )
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        try:
            # Route through the shared emit seam (OX-14-001, ASK-04-008).
            # factory.emit_prepared_create_case returns (id, blob); pass
            # empty blob since no captured dict is present here.
            self._emit_through_seam(activity_id, "")
        except Exception as exc:  # noqa: BLE001  # ruff-baseline #3768
            self.feedback_message = (
                f"Failed to enqueue Create(VulnerabilityCase) to outbox: {exc}"
            )
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        logger.info(
            "%s: Queued Create(VulnerabilityCase) '%s' from proposal '%s'",
            self.name,
            activity_id,
            self._proposal_id,
        )
        return Status.SUCCESS
