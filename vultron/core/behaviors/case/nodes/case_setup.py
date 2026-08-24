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
Case setup action nodes for case management behavior trees.

Provides leaf action nodes that set up core case state: persisting the case
record, assigning attribution, and recording creation events.

CaseActor identity resolution and registration nodes are in
``case_actor_setup.py`` (BTND-07-004 split).

Composite subtrees (``Sequence``/``Selector`` subclasses) that orchestrate
these leaf nodes are defined in ``case_setup_tree.py`` at the process-area
root, per BTND-07-003.

Per specs/case-management.yaml CM-02 requirements.
"""

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.vultron_types import VultronCase


class PersistCase(DataLayerActionWithPorts):
    """
    Persist a VulnerabilityCase to the DataLayer.

    Creates the case record in DataLayer and stores the case_id in the
    blackboard for subsequent nodes.

    Per specs/case-management.yaml CM-02-001.
    """

    def __init__(self, case_obj: VultronCase, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_obj = case_obj

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {"case_id": PortInformation(data_type=str, required=True)}

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id"}

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        try:
            self.datalayer.save(self.case_obj)
            self.logger.info(
                f"{self.name}: Persisted VulnerabilityCase"
                f" {self.case_obj.id_}"
            )
            self._set_output("case_id", self.case_obj.id_)
            return Status.SUCCESS

        except Exception as e:
            self.logger.error(f"{self.name}: Error persisting case: {e}")
            return Status.FAILURE


class SetCaseAttributedTo(DataLayerActionWithPorts):
    """
    Set VulnerabilityCase.attributed_to to the receiving actor's ID.

    Must run before PersistCase so the stored case already carries the
    vendor/coordinator owner reference.

    Per specs/case-management.yaml CM-02-008.
    """

    def __init__(self, case_obj: VultronCase, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_obj = case_obj

    def update(self) -> Status:
        if self.actor_id is None:
            self.logger.error(f"{self.name}: actor_id not available")
            return Status.FAILURE

        self.case_obj.attributed_to = self.actor_id
        self.logger.debug(
            f"{self.name}: Set attributed_to={self.actor_id}"
            f" on case {self.case_obj.id_}"
        )
        return Status.SUCCESS


class RecordOfferReceivedEventNode(DataLayerActionWithPorts):
    """Conditionally record offer_received and stage the case object."""

    def __init__(self, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=True)
        return ports

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {
            "case_for_creation_events": PortInformation(
                data_type=object, required=True
            )
        }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "case_for_creation_events": "/case_for_creation_events",
        }

    def initialise(self) -> None:
        super().initialise()
        self.case_id_bb: str = self.get_input("case_id")

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case_id = self.case_id_bb
        if not isinstance(case_id, str):
            self.logger.error(f"{self.name}: case_id not found in blackboard")
            return Status.FAILURE

        case = self.datalayer.read(case_id)
        if not isinstance(case, VulnerabilityCase):
            self.logger.error(
                f"{self.name}: Case {case_id} not found in DataLayer"
            )
            return Status.FAILURE

        self._set_output("case_for_creation_events", case)
        return Status.SUCCESS


class RecordCaseCreatedEventNode(DataLayerActionWithPorts):
    """Record case_created event and persist updated case."""

    def __init__(self, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=True)
        ports["case_for_creation_events"] = PortInformation(
            data_type=object, required=True
        )
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "case_for_creation_events": "/case_for_creation_events",
        }

    def initialise(self) -> None:
        super().initialise()
        self.case_id_bb: str = self.get_input("case_id")
        self.case_for_creation_events_bb = self.get_input(
            "case_for_creation_events"
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case_id = self.case_id_bb
        if not isinstance(case_id, str):
            self.logger.error(f"{self.name}: case_id not found in blackboard")
            return Status.FAILURE

        case = self.case_for_creation_events_bb
        if not isinstance(case, VulnerabilityCase):
            self.logger.error(
                f"{self.name}: case_for_creation_events missing or invalid"
            )
            return Status.FAILURE

        return Status.SUCCESS
