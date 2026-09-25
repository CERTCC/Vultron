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


"""Retry-marker leaf nodes for the CaseProposal received tree.

Check, write and clear the durable ``PendingCreateCaseActivity`` marker that
lets a retry runner (#1139) complete a ``Create(VulnerabilityCase)`` delivery
if it failed after ``Accept`` was sent (CP-05-005/CP-05-006). Composed by
``create_case_proposal_received_tree`` (BTND-07-003).
"""

import logging
from typing import Any

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.helpers import (
    DataLayerAction,
    DataLayerActionWithPorts,
)
from vultron.core.models.activity import VultronCreateCaseActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.pending_create_case_activity import (
    PendingCreateCaseActivity,
)
from vultron.core.models.report import VulnerabilityReport
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)


class CheckMarkerExistsNode(DataLayerAction):
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
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

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


class WriteCreateCaseMarkerNode(DataLayerActionWithPorts):
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
        self.wire_render_port = None
        self._case_id_bb: str | None = None
        self._accept_activity_id_bb: str | None = None

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=False),
        "accept_activity_id": PortInformation(data_type=str, required=False),
        "wire_render_port": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "accept_activity_id": "/accept_activity_id",
            "wire_render_port": "/wire_render_port",
        }

    def initialise(self) -> None:
        super().initialise()
        self._case_id_bb = None
        self._accept_activity_id_bb = None
        self.wire_render_port = None
        try:
            self._case_id_bb = self.get_input("case_id")
        except (NoDataAvailable, NotImplementedError):
            self._case_id_bb = None
        try:
            self._accept_activity_id_bb = self.get_input("accept_activity_id")
        except (NoDataAvailable, NotImplementedError):
            self._accept_activity_id_bb = None
        try:
            self.wire_render_port = self.get_input("wire_render_port")
        except (NoDataAvailable, NotImplementedError):
            self.wire_render_port = None

    def _collect_reporter_uris(self, raw_case: VulnerabilityCase) -> list[str]:
        """Return URIs of REPORTER/FINDER participants in *raw_case*, excluding vendor.

        CaseActor bootstraps non-vendor participants (ADR-0041 AC-5) by including
        them as direct ``to`` recipients of ``Create(VulnerabilityCase)`` so their
        DataLayers can seed a case replica immediately via
        ``CreateCaseReceivedUseCase`` without waiting for the
        ``Offer(CaseManagerRole)`` round-trip (which ADR-0041 removes).
        """
        assert self.datalayer is not None
        uris: list[str] = []
        for p_id in raw_case.actor_participant_index.values():
            p = self.datalayer.read(p_id)
            if not isinstance(p, CaseParticipant):
                continue
            if (
                CVDRole.REPORTER not in p.roles
                and CVDRole.FINDER not in p.roles
            ):
                continue
            uri = getattr(p, "attributed_to", None)
            if isinstance(uri, str) and uri and uri != self._vendor_uri:
                uris.append(uri)
        return uris

    def _build_case_object(
        self, raw_case: VulnerabilityCase
    ) -> "dict[str, Any] | None":
        assert self.datalayer is not None
        # Materialise each participant ref so _store_embedded_participants
        # on the vendor side receives full objects, not bare ID strings (AC-5).
        materialized: list[Any] = []
        for ref in raw_case.case_participants:
            if isinstance(ref, str):
                p_obj = self.datalayer.read(ref)
                materialized.append(p_obj if p_obj is not None else ref)
            else:
                materialized.append(ref)
        case_copy = raw_case.model_copy(
            update={"case_participants": materialized}
        )
        if self.wire_render_port is None:
            logger.warning(
                "%s: wire_render_port not available; cannot render case object",
                self.name,
            )
            return None
        case_dict = self.wire_render_port.render(case_copy)
        case_dict.setdefault("type", "VulnerabilityCase")
        # Inline full VulnerabilityReport dicts after render so invited
        # actors' _store_embedded_reports stores them (CBT-01-007, ISSUE-2134).
        # Done post-render because VulnerabilityCase.vulnerability_reports is
        # typed list[str]; embedding objects directly triggers Pydantic warnings.
        inlined_reports: list[Any] = []
        for ref in raw_case.vulnerability_reports:
            if isinstance(ref, str):
                r_obj = self.datalayer.read(ref)
                if isinstance(r_obj, VulnerabilityReport):
                    r_dict = self.wire_render_port.render(r_obj)
                    r_dict.setdefault("type", "VulnerabilityReport")
                    inlined_reports.append(r_dict)
                else:
                    inlined_reports.append(ref)
            else:
                inlined_reports.append(ref)
        case_dict["vulnerability_reports"] = inlined_reports
        return case_dict

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        case_id = self._case_id_bb
        if not isinstance(case_id, str):
            self.feedback_message = "case_id not found in blackboard"
            return Status.FAILURE

        accept_activity_id = self._accept_activity_id_bb
        if not isinstance(accept_activity_id, str):
            self.feedback_message = (
                "accept_activity_id not found in blackboard"
            )
            return Status.FAILURE

        # Regime 1 (ADR-0087, #3101): the CaseActor authored this case upstream
        # in the same tree, so an absent case is an anomaly, not a skip.
        # Resolve once here and pass the object to the payload helpers.
        case, failure = self._require_case(case_id)
        if failure is not None:
            return failure

        # Pre-construct the payload that will be (re-)sent as
        # Create(VulnerabilityCase).  Mirrors the logic in
        # EmitCreateVulnerabilityCaseNode so the retry runner (#1139)
        # can reconstruct the exact same activity without re-running the BT.
        # AC-5 (ADR-0041): embed full inline case object with materialised
        # participants so _store_embedded_participants seeds the vendor replica.
        case_object = self._build_case_object(case)
        if case_object is None:
            self.feedback_message = (
                "wire_render_port not available; cannot render"
                f" VulnerabilityCase {case_id!r}"
            )
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        # ADR-0041 AC-5: bootstrap all known participants directly.
        # Include REPORTER/FINDER URIs so their DataLayers receive the case
        # replica immediately; CreateCaseReceivedUseCase handles them via the
        # non-vendor participant path (no ReportCaseLink required).
        # CP-05-003 / ADR-0045: context = case URI (deferral routing key);
        # in_reply_to = Accept URI (causal antecedent, AS2-correct field).
        reporter_uris = self._collect_reporter_uris(case)
        create_activity = VultronCreateCaseActivity(
            actor=self.actor_id,
            object_=case_object,
            context=case_id,
            in_reply_to=accept_activity_id,
            to=[self._vendor_uri] + reporter_uris,
        )
        # ARCH-20-001, honestly: ``create_activity`` is a *core-branch* object, so
        # this dump is core producing the wire shape itself.  It stands because
        # the marker's payload is not a core representation at all — it is the
        # AS2 document the retry runner will re-send over HTTP (#1139), and AS2
        # is the HTTP transmission format (ADR-0099 detail 1).  Since detail 4 it
        # is the same dump ``WireRenderPort`` performs (camelCase, ``@context``);
        # it stays inline only because the port is not injected into this node.
        # Counted by ``test/architecture/test_core_by_alias_dumps.py``.
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


class ClearCreateCaseMarkerNode(DataLayerAction):
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
