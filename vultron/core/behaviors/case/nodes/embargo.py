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

"""
Embargo management action nodes and helpers for case behavior trees.

Provides helpers and action nodes for initializing default embargo events
during case creation.

The composite subtree assembling these leaf nodes is defined in the sibling
``embargo_tree.py`` module at the process-area root per BTND-07-003:

- ``InitializeDefaultEmbargoNode``

Per specs/case-management.yaml CM-02, OX-03-001 and
notes/protocol-event-cascades.md D5-6-EMBARGORCP.
"""

import logging
from datetime import datetime, timedelta, timezone

import isodate  # type: ignore[import-untyped]
from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.enums import VultronObjectType
from vultron.core.models.case import VulnerabilityCase
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    TransitionMode,
)
from vultron.core.states.participant_embargo_consent import PEC, PEC_Trigger
from vultron.core.models._helpers import _as_id
from vultron.errors import VultronError

logger = logging.getLogger(__name__)

_DEFAULT_EMBARGO_DAYS = 90


def _preferred_embargo_duration(
    dl: CasePersistence, node_name: str, node_logger: logging.Logger
) -> timedelta:
    duration = timedelta(days=_DEFAULT_EMBARGO_DAYS)
    policies = list(dl.list_objects(VultronObjectType.EMBARGO_POLICY))
    if not policies:
        return duration

    preferred = getattr(policies[0], "preferred_duration", None)
    if isinstance(preferred, timedelta):
        return preferred

    node_logger.warning(
        "%s: EmbargoPolicy preferred_duration %r is not a timedelta; "
        "falling back to default %d days",
        node_name,
        preferred,
        _DEFAULT_EMBARGO_DAYS,
    )
    return duration


class ResolveEmbargoDurationNode(DataLayerActionWithPorts):
    """Resolve preferred embargo duration and publish it to blackboard."""

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {
            "default_embargo_duration": PortInformation(
                data_type=object, required=True
            )
        }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"default_embargo_duration": "/default_embargo_duration"}

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        duration = _preferred_embargo_duration(
            self.datalayer, self.name, self.logger
        )
        self._set_output("default_embargo_duration", duration)
        return Status.SUCCESS


class CreateEmbargoEventNode(DataLayerActionWithPorts):
    """Create a default embargo event and publish embargo_id to blackboard."""

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=True)
        ports["default_embargo_duration"] = PortInformation(
            data_type=object, required=True
        )
        return ports

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {
            "default_embargo_id": PortInformation(data_type=str, required=True)
        }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "default_embargo_duration": "/default_embargo_duration",
            "default_embargo_id": "/default_embargo_id",
        }

    def initialise(self) -> None:
        super().initialise()
        self.case_id_bb: str = self.get_input("case_id")
        self.default_embargo_duration_bb = self.get_input(
            "default_embargo_duration"
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case_id = self.case_id_bb
        if not isinstance(case_id, str):
            self.logger.error("%s: case_id not found in blackboard", self.name)
            return Status.FAILURE

        duration = self.default_embargo_duration_bb
        if not isinstance(duration, timedelta):
            self.logger.error(
                "%s: default_embargo_duration missing or invalid", self.name
            )
            return Status.FAILURE

        end_time = datetime.now(tz=timezone.utc) + duration
        embargo = EmbargoEvent(end_time=end_time, context=case_id)
        try:
            self.datalayer.create(embargo)
        except ValueError:
            self.logger.debug(
                "%s: Embargo %s already exists — skipping creation",
                self.name,
                embargo.id_,
            )

        self._set_output("default_embargo_id", embargo.id_)
        self.logger.info(
            "Initialized default embargo '%s' for case '%s'"
            " (end_time: %s, duration: %s)",
            embargo.id_,
            case_id,
            end_time.isoformat(),
            isodate.duration_isoformat(duration),
        )
        return Status.SUCCESS


class AdvanceEMStateToActiveNode(DataLayerActionWithPorts):
    """Advance EM state via EmbargoLifecycle propose+accept sequence."""

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=True)
        ports["default_embargo_id"] = PortInformation(
            data_type=str, required=True
        )
        return ports

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {
            "default_embargo_initialized": PortInformation(
                data_type=object, required=True
            )
        }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "default_embargo_id": "/default_embargo_id",
            "default_embargo_initialized": "/default_embargo_initialized",
        }

    def initialise(self) -> None:
        super().initialise()
        self.case_id_bb: str = self.get_input("case_id")
        self.default_embargo_id_bb: str = self.get_input("default_embargo_id")

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        case_id = self.case_id_bb
        embargo_id = self.default_embargo_id_bb
        if not isinstance(case_id, str) or not isinstance(embargo_id, str):
            self.logger.error(
                "%s: case_id/default_embargo_id not found in blackboard",
                self.name,
            )
            return Status.FAILURE

        stored_case = self.datalayer.read(case_id, raise_on_missing=False)
        if not isinstance(stored_case, VulnerabilityCase):
            self.logger.error(
                "%s: Case %s not found in DataLayer", self.name, case_id
            )
            return Status.FAILURE

        if _as_id(stored_case.active_embargo) is not None:
            self.logger.debug(
                "%s: Case '%s' already has active_embargo '%s' — skipping EM advance",
                self.name,
                case_id,
                _as_id(stored_case.active_embargo),
            )
            self._set_output("default_embargo_initialized", False)
            return Status.SUCCESS

        owner_actor_id = _as_id(stored_case.attributed_to)
        if owner_actor_id != self.actor_id:
            self.logger.error(
                "%s: actor '%s' is not case owner '%s' for case '%s'",
                self.name,
                self.actor_id,
                owner_actor_id,
                case_id,
            )
            return Status.FAILURE

        status = self._propose_with_em_io(case_id, embargo_id)
        if status != Status.SUCCESS:
            return status

        self._set_output("default_embargo_initialized", True)
        return Status.SUCCESS

    def _propose_with_em_io(self, case_id: str, embargo_id: str) -> Status:
        """Run propose_embargo via EmbargoLifecycle service."""
        assert (
            self.datalayer is not None
        )  # caller guards; here for type narrowing
        assert self.actor_id is not None

        lifecycle = EmbargoLifecycle(persistence=self.datalayer)
        try:
            lifecycle.propose_embargo(
                case_id=case_id,
                embargo_id=embargo_id,
                actor_id=self.actor_id,
                transition_mode=TransitionMode.STRICT,
            )
        except VultronError as exc:
            self.logger.error(
                "%s: Failed to propose embargo '%s' for case '%s': %s",
                self.name,
                embargo_id,
                case_id,
                exc,
            )
            return Status.FAILURE

        return Status.SUCCESS


class AttachEmbargoToCaseNode(DataLayerActionWithPorts):
    """Ensure case.active_embargo references the initialized embargo event."""

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=True)
        ports["default_embargo_initialized"] = PortInformation(
            data_type=object, required=True
        )
        ports["default_embargo_id"] = PortInformation(
            data_type=str, required=True
        )
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "default_embargo_initialized": "/default_embargo_initialized",
            "default_embargo_id": "/default_embargo_id",
        }

    def initialise(self) -> None:
        super().initialise()
        self.bb_case_id: str = self.get_input("case_id")
        self.bb_default_embargo_id: str = self.get_input("default_embargo_id")

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case_id = self.bb_case_id
        embargo_id = self.bb_default_embargo_id

        stored_case = self.datalayer.read(case_id, raise_on_missing=False)
        if not isinstance(stored_case, VulnerabilityCase):
            self.logger.error(
                "%s: Case %s not found in DataLayer", self.name, case_id
            )
            return Status.FAILURE

        active_embargo_id = _as_id(stored_case.active_embargo)
        if active_embargo_id is None:
            lifecycle = EmbargoLifecycle(persistence=self.datalayer)
            try:
                lifecycle.activate_embargo(
                    case_id=case_id,
                    embargo_id=embargo_id,
                    actor_id=self.actor_id,
                )
            except VultronError as exc:
                self.feedback_message = str(exc)
                self.logger.error(
                    "%s: Failed to activate embargo '%s' on case '%s': %s",
                    self.name,
                    embargo_id,
                    case_id,
                    exc,
                )
                return Status.FAILURE
            self.logger.info(
                "Attached embargo '%s' to case '%s' as active_embargo",
                embargo_id,
                case_id,
            )
            return Status.SUCCESS

        if active_embargo_id != embargo_id:
            self.logger.debug(
                "%s: Keeping existing active_embargo '%s' for case '%s'"
                " (new embargo '%s' left unattached)",
                self.name,
                active_embargo_id,
                case_id,
                embargo_id,
            )
        return Status.SUCCESS


class SeedOwnerAsSignatoryNode(DataLayerActionWithPorts):
    """Seed the case-owner participant as SIGNATORY (CM-14-003)."""

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=True)
        ports["default_embargo_initialized"] = PortInformation(
            data_type=object, required=True
        )
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "default_embargo_initialized": "/default_embargo_initialized",
        }

    def initialise(self) -> None:
        super().initialise()
        self.bb_case_id: str = self.get_input("case_id")
        self.embargo_initialized = self.get_input(
            "default_embargo_initialized"
        )

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        case_id = self.bb_case_id
        embargo_initialized = self.embargo_initialized
        if embargo_initialized is False:
            return Status.SUCCESS

        stored_case = self.datalayer.read(case_id, raise_on_missing=False)
        if not isinstance(stored_case, VulnerabilityCase):
            self.logger.error(
                "%s: Case %s not found in DataLayer", self.name, case_id
            )
            return Status.FAILURE

        participant_id = stored_case.actor_participant_index.get(self.actor_id)
        if not participant_id:
            self.logger.warning(
                "%s: No participant found for owner '%s' in case '%s'"
                " — cannot seed SIGNATORY",
                self.name,
                self.actor_id,
                case_id,
            )
            return Status.SUCCESS

        participant = self.datalayer.read(
            participant_id, raise_on_missing=False
        )
        if not isinstance(participant, CaseParticipant):
            self.logger.warning(
                "%s: Participant '%s' not found in case '%s'"
                " — cannot seed SIGNATORY",
                self.name,
                participant_id,
                case_id,
            )
            return Status.SUCCESS

        embargo_id = _as_id(stored_case.active_embargo)
        if participant.embargo_consent_state != PEC.SIGNATORY:
            participant.apply_pec_transition(PEC_Trigger.ACCEPT)
        if embargo_id and embargo_id not in participant.accepted_embargo_ids:
            participant.accepted_embargo_ids.append(embargo_id)
        self.datalayer.save(participant)
        self.logger.info(
            "Seeded case-owner participant '%s' (actor '%s') as SIGNATORY"
            " for embargo in case '%s' (CM-14-003)",
            participant_id,
            self.actor_id,
            case_id,
        )
        return Status.SUCCESS
