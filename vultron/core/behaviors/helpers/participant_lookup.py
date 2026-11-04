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

"""Resolve a case participant by actor ID (BTND-04-005 shared node)."""

from typing import Any

from py_trees.common import Status
from py_trees.ports import PortInformation

from vultron.core.behaviors.helpers.ports_base import (
    DataLayerConditionWithPorts,
)
from vultron.core.behaviors.node_logger import port_wiring_logger
from vultron.core.models.case_participant import CaseParticipant


class FindParticipantByActorIdNode(DataLayerConditionWithPorts):
    """
    Resolve and store a case participant by actor ID.

    Iterates ``case.case_participants`` and resolves each participant reference
    until it finds a participant whose ``attributed_to`` matches the target
    actor ID. On success the matched participant is written to the blackboard.
    """

    def __init__(
        self,
        case_id: str,
        target_actor_id: str,
        participant_key: str = "participant",
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.target_actor_id = target_actor_id
        self.participant_key = participant_key
        self.found_participant: CaseParticipant | None = None
        """The record the last successful run found, else ``None``."""

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "participant": PortInformation(data_type=object, required=True),
    }

    def setup(self, **kwargs: Any) -> None:
        self.setup_ports(
            port_remappings={
                "datalayer": "/datalayer",
                "actor_id": "/actor_id",
                "participant": f"/{self.participant_key}",
            },
            logger=port_wiring_logger(),
        )

    def _participant_actor_id(self, participant: CaseParticipant) -> str:
        actor_ref = participant.attributed_to
        return (
            actor_ref
            if isinstance(actor_ref, str)
            else getattr(actor_ref, "id_", str(actor_ref))
        )

    def _participant_id(self, participant: object) -> str:
        return str(getattr(participant, "id_", participant))

    def _found(self, participant: object) -> None:
        """Publish the matched *participant* and keep it for subclasses."""
        self._set_output("participant", participant)
        if isinstance(participant, CaseParticipant):
            self.found_participant = participant

    def _fail(self, message: str) -> Status:
        self.feedback_message = message
        self.logger.error("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE

    def _find_matching_participant(
        self, case_obj: object
    ) -> tuple[object | None, str | None, str | None]:
        assert self.datalayer is not None
        matched_participant: object | None = None
        matched_participant_id: str | None = None
        for participant_ref in getattr(case_obj, "case_participants", []):
            if isinstance(participant_ref, str):
                participant_obj = self.datalayer.read(
                    participant_ref, raise_on_missing=False
                )
            else:
                # For inline objects, read the live DL record to avoid stale
                # snapshots (#2233 — _build_case_object materialises inlines
                # for delivery; the standalone record may have advanced since).
                pid = getattr(participant_ref, "id_", None)
                live = (
                    self.datalayer.read(pid, raise_on_missing=False)
                    if pid
                    else None
                )
                participant_obj = (
                    live
                    if isinstance(live, CaseParticipant)
                    else participant_ref
                )
            if not isinstance(participant_obj, CaseParticipant):
                continue
            if (
                self._participant_actor_id(participant_obj)
                != self.target_actor_id
            ):
                continue

            participant_id = self._participant_id(participant_obj)
            if (
                matched_participant_id is not None
                and participant_id != matched_participant_id
            ):
                return (
                    None,
                    None,
                    "Participant-index divergence: actor "
                    f"{self.target_actor_id} resolves to multiple "
                    "case_participants.",
                )
            matched_participant = participant_obj
            matched_participant_id = participant_id

        return matched_participant, matched_participant_id, None

    def update(self) -> Status:
        self.found_participant = None
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case_obj, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        index_match = case_obj.actor_participant_index.get(
            self.target_actor_id
        )
        matched_participant, matched_participant_id, error_message = (
            self._find_matching_participant(case_obj)
        )
        if error_message is not None:
            return self._fail(error_message)

        if matched_participant is None:
            if index_match is not None:
                return self._fail(
                    "Participant-index divergence: actor "
                    f"{self.target_actor_id} mapped to {index_match} in "
                    "actor_participant_index but missing from "
                    "case_participants."
                )
            self.feedback_message = f"No participant for actor {self.target_actor_id} in case {self.case_id}"
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        if index_match != matched_participant_id:
            if index_match is None:
                self._found(matched_participant)
                self.feedback_message = (
                    f"Found participant for actor {self.target_actor_id}"
                )
                self.logger.debug("%s: %s", self.name, self.feedback_message)
                return Status.SUCCESS
            return self._fail(
                "Participant-index divergence: actor "
                f"{self.target_actor_id} resolves to "
                f"{matched_participant_id} from case_participants but "
                f"actor_participant_index maps to {index_match}."
            )

        self._found(matched_participant)
        self.feedback_message = (
            f"Found participant for actor {self.target_actor_id}"
        )
        self.logger.debug("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS
