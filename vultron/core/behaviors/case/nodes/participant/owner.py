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

"""Owner-participant creation leaf nodes (BTND-07-003)."""

from typing import cast

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.case.nodes.participant.common import (
    _create_and_attach_participant,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
)
from vultron.config.actor import ActorConfig
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.core.models._helpers import _as_id


def _effective_case_roles(actor_config: ActorConfig | None) -> list[CVDRole]:
    base_roles = actor_config.default_case_roles if actor_config else []
    return list(dict.fromkeys(base_roles + [CVDRole.CASE_OWNER]))


class CreateOwnerParticipantNode(DataLayerActionWithPorts):
    """Create the in-memory owner participant and stage it on blackboard."""

    def __init__(
        self,
        actor_config: ActorConfig | None,
        report_id: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.actor_config = actor_config
        _seg = report_id.split("/")[-1] if report_id else "default"
        self._new_case_participant_key = f"new_case_participant_{_seg}"

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=False),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "new_case_participant": PortInformation(
            data_type=object, required=True
        ),
    }

    def _instance_port_remappings(self) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "new_case_participant": f"/{self._new_case_participant_key}",
        }

    def initialise(self) -> None:
        super().initialise()
        self.case_id = self._try_get_input("case_id")

    def update(self) -> Status:
        if self.actor_id is None:
            self.logger.error("%s: actor_id not available", self.name)
            return Status.FAILURE
        case_id = self.case_id
        if not isinstance(case_id, str):
            self.logger.error("%s: case_id not available", self.name)
            return Status.FAILURE

        self._set_output(
            "new_case_participant",
            CaseParticipant(
                attributed_to=self.actor_id,
                context=case_id,
                case_roles=_effective_case_roles(self.actor_config),
                participant_statuses=[],
            ),
        )
        return Status.SUCCESS


class CreateOwnerInitialStatusNode(DataLayerActionWithPorts):
    """Apply the owner's initial ParticipantStatus via the writer node.

    Pre-builds a :class:`CreateParticipantStatusNode` in ``__init__`` and
    executes it via ``BTBridge.execute_with_setup`` so the write is routed
    through the composed evaluator (BTND-10-004, ADR-0089).
    """

    def __init__(
        self,
        initial_rm_state: RM = RM.RECEIVED,
        report_id: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        from vultron.core.behaviors.case.nodes.participant.status import (
            CreateParticipantStatusNode,
        )

        self._status_node = CreateParticipantStatusNode(
            actor_id="",
            rm_state=initial_rm_state,
            vf_state=None,
            d_state=None,
            pxa_state=None,
            force_rm_state=(initial_rm_state != RM.RECEIVED),
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

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        case_id = self._case_id_bb
        if not isinstance(case_id, str):
            self.feedback_message = "case_id not found in blackboard"
            return Status.FAILURE

        from vultron.core.behaviors.bridge import BTBridge

        result = BTBridge(datalayer=self.datalayer).execute_with_setup(
            self._status_node,
            actor_id=self.actor_id,
            case_id=case_id,
        )
        return result.status


class AttachOwnerParticipantToCaseNode(DataLayerActionWithPorts):
    """Persist and attach staged owner participant to the case."""

    def __init__(
        self, report_id: str | None = None, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        _seg = report_id.split("/")[-1] if report_id else "default"
        self._new_case_participant_key = f"new_case_participant_{_seg}"
        self._participant_case_key = f"participant_case_{_seg}"

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=False),
        "new_case_participant": PortInformation(
            data_type=object, required=True
        ),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "participant_case": PortInformation(
            data_type=VulnerabilityCase, required=True
        ),
    }

    def _instance_port_remappings(self) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "new_case_participant": f"/{self._new_case_participant_key}",
            "participant_case": f"/{self._participant_case_key}",
        }

    def initialise(self) -> None:
        super().initialise()
        self.case_id = self._try_get_input("case_id")
        self.new_case_participant = self._try_get_input("new_case_participant")

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        case_id_obj = self.case_id
        participant = self.new_case_participant
        if not isinstance(participant, CaseParticipant):
            self.logger.error(
                "%s: case_id/%s missing in blackboard",
                self.name,
                self._new_case_participant_key,
            )
            return Status.FAILURE
        case_id = case_id_obj
        if not isinstance(case_id, str):
            case_id = _as_id(participant.context)
        if case_id is None:
            self.logger.error("%s: case_id not available", self.name)
            return Status.FAILURE

        stored_case = _create_and_attach_participant(
            self.datalayer,
            participant,
            case_id,
            self.actor_id,
            self.logger,
        )
        if stored_case is None:
            self.logger.error(
                "%s: Case %s not found in DataLayer",
                self.name,
                case_id,
            )
            return Status.FAILURE

        self._set_output("participant_case", stored_case)
        return Status.SUCCESS


class PersistOwnerCaseNode(DataLayerActionWithPorts):
    """Persist the updated case after owner participant attachment."""

    def __init__(
        self, report_id: str | None = None, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        _seg = report_id.split("/")[-1] if report_id else "default"
        self._participant_case_key = f"participant_case_{_seg}"

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "participant_case": PortInformation(
            data_type=VulnerabilityCase, required=True
        ),
    }

    def _instance_port_remappings(self) -> dict[str, str]:
        return {"participant_case": f"/{self._participant_case_key}"}

    def initialise(self) -> None:
        super().initialise()
        self._stored_case = self._try_get_input("participant_case")

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        stored_case = self._stored_case
        if stored_case is None:
            self.logger.error(
                "%s: %s missing in blackboard",
                self.name,
                self._participant_case_key,
            )
            return Status.FAILURE
        self.datalayer.save(cast(VulnerabilityCase, stored_case))
        return Status.SUCCESS


class RecordOwnerJoinedEventNode(DataLayerActionWithPorts):
    """Record owner_joined event and persist the case update."""

    def __init__(
        self, report_id: str | None = None, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        _seg = report_id.split("/")[-1] if report_id else "default"
        self._participant_case_key = f"participant_case_{_seg}"
        self._new_case_participant_key = f"new_case_participant_{_seg}"

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "participant_case": PortInformation(
            data_type=VulnerabilityCase, required=True
        ),
        "new_case_participant": PortInformation(
            data_type=object, required=True
        ),
    }

    def _instance_port_remappings(self) -> dict[str, str]:
        return {
            "participant_case": f"/{self._participant_case_key}",
            "new_case_participant": f"/{self._new_case_participant_key}",
        }

    def initialise(self) -> None:
        super().initialise()
        self._stored_case = self._try_get_input("participant_case")
        self._participant = self._try_get_input("new_case_participant")

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        stored_case = self._stored_case
        participant = self._participant
        if stored_case is None or not isinstance(participant, CaseParticipant):
            self.logger.error(
                "%s: %s/%s missing in blackboard",
                self.name,
                self._participant_case_key,
                self._new_case_participant_key,
            )
            return Status.FAILURE

        return Status.SUCCESS
