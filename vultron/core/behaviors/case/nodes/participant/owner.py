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

from typing import Any, cast

import py_trees
from py_trees.common import Status
from py_trees.ports import PortInformation

from vultron.core.behaviors.case.nodes.participant.common import (
    _create_and_attach_participant,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
)
from vultron.config.actor import ActorConfig
from vultron.core.models.dimensions import PecDimension, RmDimension
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.vultron_types import VultronCase, VultronParticipant
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.core.models._helpers import _as_id, _report_phase_status_id
from vultron.core.use_cases._helpers import update_participant_rm_state


def _resolve_case_id(
    blackboard: Any, case_obj: VultronCase | None = None
) -> str | None:
    case_id = case_obj.id_ if case_obj is not None else None
    return case_id or blackboard.get("case_id")


def _build_owner_initial_status(
    dl: CasePersistence,
    actor_id: str,
    case_id: str,
    report_id: str | None,
    initial_rm_state: RM,
) -> ParticipantStatus:
    if report_id is not None:
        status_id = _report_phase_status_id(
            actor_id,
            report_id,
            initial_rm_state.value,
        )
        if dl.read(status_id) is not None:
            return ParticipantStatus(
                id_=status_id,
                context=case_id,
                rm=RmDimension(state=initial_rm_state),
                attributed_to=actor_id,
                consent=PecDimension(state=PEC.NO_EMBARGO),
                cvd_role=[CVDRole.CASE_OWNER],
            )

    return ParticipantStatus(
        context=case_id,
        rm=RmDimension(state=initial_rm_state),
        attributed_to=actor_id,
        consent=PecDimension(state=PEC.NO_EMBARGO),
        cvd_role=[CVDRole.CASE_OWNER],
    )


def _effective_case_roles(actor_config: ActorConfig | None) -> list[CVDRole]:
    base_roles = actor_config.default_case_roles if actor_config else []
    return list(dict.fromkeys(base_roles + [CVDRole.CASE_OWNER]))


class ResolveOwnerInitialStatusNode(DataLayerActionWithPorts):
    """Resolve/create the owner's initial ParticipantStatus."""

    def __init__(
        self,
        report_id: str | None,
        case_obj: VultronCase | None,
        initial_rm_state: RM,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id
        self.case_obj = case_obj
        self.initial_rm_state = initial_rm_state
        _seg = report_id.split("/")[-1] if report_id else "default"
        self._owner_initial_status_key = f"owner_initial_status_{_seg}"

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=False)
        return ports

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {
            "owner_initial_status": PortInformation(
                data_type=object, required=True
            )
        }

    def _instance_port_remappings(self) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "owner_initial_status": f"/{self._owner_initial_status_key}",
        }

    def initialise(self) -> None:
        super().initialise()
        self.case_id = self._try_get_input("case_id")

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        case_id = (
            self.case_obj.id_ if self.case_obj is not None else None
        ) or self.case_id
        if case_id is None:
            self.logger.error("%s: case_id not available", self.name)
            return Status.FAILURE
        if not isinstance(case_id, str):
            self.logger.error("%s: case_id is not a string", self.name)
            return Status.FAILURE

        self._set_output(
            "owner_initial_status",
            _build_owner_initial_status(
                self.datalayer,
                self.actor_id,
                case_id,
                self.report_id,
                self.initial_rm_state,
            ),
        )
        return Status.SUCCESS


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
        self._owner_initial_status_key = f"owner_initial_status_{_seg}"
        self._new_case_participant_key = f"new_case_participant_{_seg}"

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=False)
        ports["owner_initial_status"] = PortInformation(
            data_type=object, required=True
        )
        return ports

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {
            "new_case_participant": PortInformation(
                data_type=object, required=True
            )
        }

    def _instance_port_remappings(self) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "owner_initial_status": f"/{self._owner_initial_status_key}",
            "new_case_participant": f"/{self._new_case_participant_key}",
        }

    def initialise(self) -> None:
        super().initialise()
        self.case_id = self._try_get_input("case_id")
        self.owner_initial_status = self._try_get_input("owner_initial_status")

    def update(self) -> Status:
        if self.actor_id is None:
            self.logger.error("%s: actor_id not available", self.name)
            return Status.FAILURE
        case_id_obj = self.case_id
        initial_status = self.owner_initial_status
        if not isinstance(initial_status, ParticipantStatus):
            self.logger.error(
                "%s: case_id/%s missing in blackboard",
                self.name,
                self._owner_initial_status_key,
            )
            return Status.FAILURE
        case_id = case_id_obj
        if not isinstance(case_id, str):
            status_context = _as_id(initial_status.context)
            case_id = status_context if status_context is not None else None
        if case_id is None:
            self.logger.error("%s: case_id not available", self.name)
            return Status.FAILURE

        self._set_output(
            "new_case_participant",
            VultronParticipant(
                attributed_to=self.actor_id,
                context=case_id,
                case_roles=_effective_case_roles(self.actor_config),
                participant_statuses=[initial_status],
            ),
        )
        return Status.SUCCESS


class AttachOwnerParticipantToCaseNode(DataLayerActionWithPorts):
    """Persist and attach staged owner participant to the case."""

    def __init__(
        self, report_id: str | None = None, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        _seg = report_id.split("/")[-1] if report_id else "default"
        self._new_case_participant_key = f"new_case_participant_{_seg}"
        self._participant_case_key = f"participant_case_{_seg}"

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=False)
        ports["new_case_participant"] = PortInformation(
            data_type=object, required=True
        )
        return ports

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {
            "participant_case": PortInformation(
                data_type=VulnerabilityCase, required=True
            )
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
        if not isinstance(participant, VultronParticipant):
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

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["participant_case"] = PortInformation(
            data_type=VulnerabilityCase, required=True
        )
        return ports

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


class ShouldAdvanceOwnerToAcceptedNode(py_trees.behaviour.Behaviour):
    """Condition leaf for owner RM advancement branch selection."""

    def __init__(
        self, advance_to_accepted: bool, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._advance_to_accepted = advance_to_accepted

    def update(self) -> Status:
        return Status.SUCCESS if self._advance_to_accepted else Status.FAILURE


class AdvanceOwnerRmToAcceptedNode(DataLayerActionWithPorts):
    """Advance owner RM to ACCEPTED when case creation means engagement."""

    def __init__(
        self, report_id: str | None = None, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        _seg = report_id.split("/")[-1] if report_id else "default"
        self._participant_case_key = f"participant_case_{_seg}"

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=False)
        ports["participant_case"] = PortInformation(
            data_type=object, required=True
        )
        return ports

    def _instance_port_remappings(self) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "participant_case": f"/{self._participant_case_key}",
        }

    def initialise(self) -> None:
        super().initialise()
        raw = self._try_get_input("case_id")
        self._case_id: str | None = raw if isinstance(raw, str) else None
        self._stored_case = self._try_get_input("participant_case")

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        case_id = self._case_id
        if case_id is None:
            case_id = (
                cast(VulnerabilityCase, self._stored_case).id_
                if self._stored_case is not None
                else None
            )
        if case_id is None:
            self.logger.error("%s: case_id not available", self.name)
            return Status.FAILURE

        advanced = update_participant_rm_state(
            case_id,
            self.actor_id,
            RM.ACCEPTED,
            self.datalayer,
        )
        if advanced:
            self.logger.info(
                "Owner RM: VALID → ACCEPTED for actor '%s' in case '%s' "
                "(case creation = case engagement)",
                self.actor_id,
                case_id,
            )
        else:
            self.logger.warning(
                "%s: Could not advance owner RM to ACCEPTED for actor '%s'"
                " in case '%s'",
                self.name,
                self.actor_id,
                case_id,
            )
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

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["participant_case"] = PortInformation(
            data_type=object, required=True
        )
        ports["new_case_participant"] = PortInformation(
            data_type=object, required=True
        )
        return ports

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
        if stored_case is None or not isinstance(
            participant, VultronParticipant
        ):
            self.logger.error(
                "%s: %s/%s missing in blackboard",
                self.name,
                self._participant_case_key,
                self._new_case_participant_key,
            )
            return Status.FAILURE

        return Status.SUCCESS
