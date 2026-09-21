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


"""CaseActor and CASE_OWNER participant-registration leaf nodes.

Register the CaseActor (COORDINATOR + CASE_MANAGER) and the report receiver
(CASE_OWNER) as case participants during CaseActor-native initialization
(ADR-0041). The reporter participant node lives in ``proposal_reporter.py``
(BTND-07-004 headroom). Composed by ``create_case_proposal_received_tree``
(BTND-07-003).
"""

import logging

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.case.nodes.participant.common import (
    _create_and_attach_participant,
)
from vultron.core.behaviors.case.nodes.participant.owner import (
    _effective_case_roles,
)
from vultron.core.behaviors.case.nodes.participant.status import (
    CreateParticipantStatusNode,
)
from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.models.vultron_types import VultronParticipant
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)


class AddCaseActorParticipantNode(DataLayerActionWithPorts):
    """Register the CaseActor itself as COORDINATOR + CASE_MANAGER participant.

    Under ADR-0041 the CaseActor creates the VulnerabilityCase, so it must
    also register itself as the CASE_MANAGER so that ResolveCaseManagerNode
    can locate it later (e.g. add-note-to-case, send_tree).

    Per CM-23-005 and ADR-0051, the CaseActor MUST have a full RM lifecycle.
    Three bootstrap ParticipantStatus records are emitted at creation:
      - RM.RECEIVED  = CaseProposal received and being evaluated
      - RM.VALID     = CaseProposal validated; case creation begun
      - RM.ACCEPTED  = VulnerabilityCase successfully created and coordinated

    These statuses are later committed as CaseLedgerEntries by
    CommitNativeLedgerEntriesNode (CM-23-007).

    Reads ``case_id`` from the blackboard.  No-ops if the CaseActor is
    already in ``actor_participant_index`` (idempotent on duplicate delivery).
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        # Pre-build bootstrap status nodes (BTND-10-004, ADR-0089)
        self._received_node = CreateParticipantStatusNode(
            actor_id="",
            rm_state=RM.RECEIVED,
            vf_state=None,
            d_state=None,
            pxa_state=None,
        )
        self._valid_node = CreateParticipantStatusNode(
            actor_id="",
            rm_state=RM.VALID,
            vf_state=None,
            d_state=None,
            pxa_state=None,
        )
        self._accepted_node = CreateParticipantStatusNode(
            actor_id="",
            rm_state=RM.ACCEPTED,
            vf_state=None,
            d_state=None,
            pxa_state=None,
        )

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=False)
        return ports

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

    def _register_participant(self, case_id: str) -> Status:
        """Create the participant and apply bootstrap statuses via the writer."""
        assert self.datalayer is not None
        assert self.actor_id is not None

        participant = VultronParticipant(
            attributed_to=self.actor_id,
            context=case_id,
            name=f"CaseActor for {case_id}",
            case_roles=[CVDRole.COORDINATOR, CVDRole.CASE_MANAGER],
            participant_statuses=[],
        )

        updated_case = _create_and_attach_participant(
            self.datalayer,
            participant,
            case_id,
            self.actor_id,
            self.logger,
        )
        if updated_case is None:
            self.feedback_message = f"Case '{case_id}' not found in DataLayer"
            return Status.FAILURE

        self.datalayer.save(updated_case)

        # Apply RECEIVED → VALID → ACCEPTED via the composed writer (ADR-0089)
        from vultron.core.behaviors.bridge import BTBridge

        bridge = BTBridge(datalayer=self.datalayer)
        for node in (
            self._received_node,
            self._valid_node,
            self._accepted_node,
        ):
            result = bridge.execute_with_setup(
                node,
                actor_id=self.actor_id,
                case_id=case_id,
            )
            if result.status != Status.SUCCESS:
                self.feedback_message = (
                    f"Bootstrap status write failed for '{case_id}'"
                )
                return Status.FAILURE

        logger.info(
            "%s: Registered CaseActor '%s' as CASE_MANAGER for case '%s'"
            " with bootstrap RM lifecycle (RM.RECEIVED → RM.VALID →"
            " RM.ACCEPTED) per CM-23-005/ADR-0051",
            self.name,
            self.actor_id,
            case_id,
        )
        return Status.SUCCESS

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        case_id = self._case_id_bb
        if not isinstance(case_id, str):
            self.feedback_message = "case_id not found in blackboard"
            return Status.FAILURE

        # Regime 3 (ADR-0087): idempotency probe during case construction, not
        # a coordination guard. A truly-absent case falls through to the
        # register path, which hard-fails via _create_and_attach_participant
        # (returns None → FAILURE). Graceful ``is not None`` is intentional.
        stored_case = self.datalayer.read_case(case_id)
        if stored_case is not None:
            if self.actor_id in stored_case.actor_participant_index:
                return Status.SUCCESS

        return self._register_participant(case_id)


class AddVendorOwnerParticipantNode(DataLayerActionWithPorts):
    """Add the report receiver as CASE_OWNER participant at RM.RECEIVED.

    The actor that sent the proposal is the case owner (receiver of the
    original vulnerability report).  Per ADR-0041 AC-1, the CaseActor adds
    them as CASE_OWNER at RM.RECEIVED in its own DataLayer.

    The receiver's additional CVD roles come from
    ``ActorConfig.default_case_roles`` (CFG-07-002, CFG-07-004) — the same
    source the pre-ADR-0041 vendor-side ``CreateCaseOwnerParticipant`` used.
    They must not be hard-coded: a coordinator that receives a report is a
    CASE_OWNER but never a VENDOR, and giving it ``CVDRole.VENDOR`` makes
    downstream VFD fix-lifecycle guards demand a fix it will never produce.

    Reads ``case_id`` from the blackboard (written by ResolveCaseIdSelector).
    """

    def __init__(
        self,
        vendor_uri: str,
        report_id: str | None,
        actor_config: ActorConfig | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._vendor_uri = vendor_uri
        self._report_id = report_id
        self._actor_config = actor_config
        # Pre-build the initial status node (BTND-10-004, ADR-0089).
        # actor_id is set here so execute_with_setup can use actor_id=self.actor_id
        # (the CaseActor's store) without BTBridge cloning an empty vendor store.
        self._status_node = CreateParticipantStatusNode(
            actor_id=vendor_uri,
            rm_state=RM.RECEIVED,
            vf_state=None,
            d_state=None,
            pxa_state=None,
        )

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=False)
        return ports

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

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        if not self.actor_id:
            self.feedback_message = "actor_id not set"
            return Status.FAILURE

        case_id = self._case_id_bb
        if not isinstance(case_id, str):
            self.feedback_message = "case_id not found in blackboard"
            return Status.FAILURE

        # Skip if vendor already has a participant in this case.
        # Regime 3 (ADR-0087): idempotency probe during case construction. A
        # truly-absent case falls through to _create_and_attach_participant
        # below, which hard-fails (returns None → FAILURE at the guard).
        stored_case = self.datalayer.read_case(case_id)
        if stored_case is not None:
            if self._vendor_uri in stored_case.actor_participant_index:
                logger.debug(
                    "%s: vendor '%s' already in actor_participant_index"
                    " for case '%s' — skipping",
                    self.name,
                    self._vendor_uri,
                    case_id,
                )
                return Status.SUCCESS

        # Roles come from the local ActorConfig (CFG-07-002, CFG-07-004) so
        # role guards (e.g. CheckVendorRoleNode) work for vendors without
        # mislabelling coordinators as vendors.  A future spec amendment
        # should carry role hints in the CaseProposal itself so the CaseActor
        # does not have to rely on co-located configuration.
        participant = VultronParticipant(
            attributed_to=self._vendor_uri,
            context=case_id,
            case_roles=_effective_case_roles(self._actor_config),
            participant_statuses=[],
        )

        updated_case = _create_and_attach_participant(
            self.datalayer,
            participant,
            case_id,
            self._vendor_uri,
            self.logger,
        )
        if updated_case is None:
            self.feedback_message = f"Case '{case_id}' not found in DataLayer"
            return Status.FAILURE

        self.datalayer.save(updated_case)

        from vultron.core.behaviors.bridge import BTBridge

        result = BTBridge(datalayer=self.datalayer).execute_with_setup(
            self._status_node,
            actor_id=self.actor_id,
            case_id=case_id,
        )
        if result.status != Status.SUCCESS:
            self.feedback_message = f"Initial RM.RECEIVED write failed for vendor '{self._vendor_uri}'"
            return Status.FAILURE

        logger.info(
            "%s: Added report receiver '%s' with roles %s at RM.RECEIVED"
            " in case '%s' (ADR-0041 AC-1)",
            self.name,
            self._vendor_uri,
            [r.value for r in participant.case_roles],
            case_id,
        )
        return Status.SUCCESS
