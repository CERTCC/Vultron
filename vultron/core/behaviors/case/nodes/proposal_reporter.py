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


"""Reporter participant-registration leaf node for the CaseProposal tree.

Adds the reporter as a participant at RM.ACCEPTED during CaseActor-native
initialization (ADR-0041 AC-2). Split from ``proposal_participants.py`` to
keep both modules under the BTND-07-004 line cap. Composed by
``create_case_proposal_received_tree`` (BTND-07-003).
"""

import logging

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.case.nodes.participant.common import (
    _create_and_attach_participant,
)
from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)


class AddReporterParticipantNode(DataLayerActionWithPorts):
    """Add the reporter as a participant at RM.ACCEPTED.

    Reads the reporter's actor URI from ``VulnerabilityReport.attributed_to``
    in the DataLayer.  Per ADR-0041 AC-2, the reporter is added at
    RM.ACCEPTED — they submitted the report, which is already accepted.

    No-ops gracefully when the report cannot be found (logs a warning, returns
    SUCCESS) so the overall flow is not blocked by a missing reporter.

    **Why degrading is right here, and where it went wrong.** The case is valid
    without this participant: a proposal names the vendor and the case actor
    directly, and refusing the whole case because one *derived* participant could
    not be built would lose more than it protects. So SUCCESS is correct.

    What was wrong was that this node, ``CommitNativeLedgerEntriesNode`` and
    ``SeedReporterSignatoryNode`` each independently discovered the same missing
    write and each logged its own symptom, so one lost report read as three
    unrelated shrugs and nothing named the cause (#2482 AC-4). The write belongs
    to ``StoreProposalReportNode``, which now says so loudly and in one place;
    these three name it in their warnings so a reader lands on the cause rather
    than on the third symptom.

    Reads ``case_id`` from the blackboard.
    """

    def __init__(
        self,
        report_id: str | None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._report_id = report_id
        from vultron.core.behaviors.case.nodes.participant.status import (
            CreateParticipantStatusNode,
        )

        self._reporter_status_node = CreateParticipantStatusNode(
            actor_id="",
            rm_state=RM.ACCEPTED,
            vf_state=None,
            d_state=None,
            pxa_state=None,
            force_rm_state=True,
        )

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id"}

    def initialise(self) -> None:
        super().initialise()
        self._case_id_bb = None
        try:
            self._case_id_bb = self.get_input("case_id")
        except (NoDataAvailable, NotImplementedError):
            pass

    def _resolve_reporter_uri(self, report_id: str) -> str | None:
        assert self.datalayer is not None
        raw_report = self.datalayer.read(report_id)
        if not isinstance(raw_report, VulnerabilityReport):
            logger.warning(
                "%s: report '%s' not found, so the reporter cannot be"
                " identified — skipping reporter participant (best-effort)."
                " The report is written by StoreProposalReportNode from the"
                " copy the proposal carries inline (CP-01-004); if that node"
                " logged nothing, the proposal arrived without one",
                self.name,
                report_id,
            )
            return None
        reporter_uri = getattr(raw_report, "attributed_to", None)
        if not isinstance(reporter_uri, str) or not reporter_uri:
            logger.warning(
                "%s: report '%s' has no attributed_to — skipping reporter"
                " participant (best-effort)",
                self.name,
                report_id,
            )
            return None
        return reporter_uri

    def _already_has_participant(self, case_id: str, actor_uri: str) -> bool:
        assert self.datalayer is not None
        # Regime 3 (ADR-0087): idempotency probe during case construction — an
        # absent case means "not yet a participant", so the caller proceeds to
        # the create path (which owns case-absence handling). Allowlist.
        stored_case = self.datalayer.read_case(case_id)
        if stored_case is None:
            return False
        if actor_uri in stored_case.actor_participant_index:
            logger.debug(
                "%s: '%s' already in actor_participant_index for case '%s'"
                " — skipping",
                self.name,
                actor_uri,
                case_id,
            )
            return True
        return False

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        if not self.actor_id:
            self.feedback_message = "actor_id not set"
            return Status.FAILURE

        if self._report_id is None:
            logger.debug(
                "%s: no report_id — skipping reporter participant", self.name
            )
            return Status.SUCCESS

        case_id = self._case_id_bb
        if not isinstance(case_id, str):
            self.feedback_message = "case_id not found in blackboard"
            return Status.FAILURE

        reporter_uri = self._resolve_reporter_uri(self._report_id)
        if reporter_uri is None:
            return Status.SUCCESS

        if self._already_has_participant(case_id, reporter_uri):
            return Status.SUCCESS

        participant = CaseParticipant(
            attributed_to=reporter_uri,
            context=case_id,
            case_roles=[CVDRole.REPORTER],
            participant_statuses=[],
        )

        updated_case = _create_and_attach_participant(
            self.datalayer,
            participant,
            case_id,
            reporter_uri,
            self.logger,
        )
        if updated_case is None:
            self.feedback_message = f"Case '{case_id}' not found in DataLayer"
            return Status.FAILURE

        self.datalayer.save(updated_case)

        from vultron.core.behaviors.bridge import BTBridge

        # Pre-set the actor_id so execute_with_setup can use actor_id=self.actor_id
        # (the CaseActor's store) without polluting the outer BT's blackboard.
        self._reporter_status_node._actor_id = reporter_uri
        result = BTBridge(datalayer=self.datalayer).execute_with_setup(
            self._reporter_status_node,
            actor_id=self.actor_id,
            case_id=case_id,
        )
        if result.status != Status.SUCCESS:
            self.feedback_message = f"Initial RM.ACCEPTED write failed for reporter '{reporter_uri}'"
            return Status.FAILURE

        logger.info(
            "%s: Added reporter '%s' as REPORTER at RM.ACCEPTED"
            " in case '%s' (ADR-0041 AC-2)",
            self.name,
            reporter_uri,
            case_id,
        )
        return Status.SUCCESS
