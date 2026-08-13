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

"""Receiver-side action nodes for Leave(VulnerabilityCase) processing.

Implements the role-discriminating effects of a received Leave activity:

- :class:`AdvanceParticipantToRMClosedNode`: Advances the leaving actor's
  :class:`~vultron.core.models.participant_status.ParticipantStatus` to
  ``RM.CLOSED`` in the local DataLayer.  Used on both the owner and non-owner
  paths (the departure effect is the same; what differs is whether the whole
  case also closes).

- :class:`AdvanceCaseActorToRMClosedNode`: Advances the Case Actor's own
  :class:`~vultron.core.models.participant_status.ParticipantStatus` to
  ``RM.CLOSED``.  Only reached on the owner Leave path (CM-23-002 step 2).

Per ADR-0050, ADR-0051, and specs/case-management.yaml CM-23-002/CM-23-003.
"""

import logging

from py_trees.common import Status

from vultron.core.behaviors.case.nodes.participant.status import (
    CreateParticipantStatusNode,
)
from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.participant_status import (
    participant_status_rm_state,
)
from vultron.core.states.rm import RM

logger = logging.getLogger(__name__)


class AdvanceParticipantToRMClosedNode(DataLayerAction):
    """Advance the leaving actor's RM state to ``RM.CLOSED`` in the DataLayer.

    Reads the leaving actor's :class:`~vultron.core.models.case_participant
    .CaseParticipant` record from the DataLayer and appends a new
    :class:`~vultron.core.models.participant_status.ParticipantStatus` entry
    with ``rm_state=RM.CLOSED``.  Idempotent: if the participant is already at
    ``RM.CLOSED``, the node returns ``SUCCESS`` without creating a duplicate
    entry.

    Used on both the owner and non-owner Leave receive paths (the participant
    departure effect is identical; only the downstream case-closure steps differ).

    Per CM-23-002 (owner path step 1), CM-23-003 (non-owner path step 1).
    """

    def __init__(
        self,
        leaving_actor_id: str,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._leaving_actor_id = leaving_actor_id
        self._case_id = case_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case = self.datalayer.read(self._case_id)
        if not isinstance(case, VulnerabilityCase):
            self.logger.warning(
                "%s: case '%s' not found or wrong type",
                self.name,
                self._case_id,
            )
            return Status.FAILURE

        participant_id = case.actor_participant_index.get(
            self._leaving_actor_id
        )
        if participant_id is None:
            self.logger.debug(
                "%s: leaving actor '%s' not in actor_participant_index"
                " for case '%s' — skipping (non-fatal)",
                self.name,
                self._leaving_actor_id,
                self._case_id,
            )
            return Status.SUCCESS

        participant = self.datalayer.read(participant_id)
        if not isinstance(participant, CaseParticipant):
            self.logger.warning(
                "%s: participant '%s' not found or wrong type",
                self.name,
                participant_id,
            )
            return Status.FAILURE

        # Idempotency: skip if already at RM.CLOSED
        for ps in participant.participant_statuses:
            if participant_status_rm_state(ps) == RM.CLOSED:
                self.logger.debug(
                    "%s: participant '%s' already at RM.CLOSED — no-op",
                    self.name,
                    participant_id,
                )
                return Status.SUCCESS

        result_out: dict = {}
        node = CreateParticipantStatusNode(
            case_id=self._case_id,
            actor_id=self._leaving_actor_id,
            rm_state=RM.CLOSED,
            vfd_state=None,
            pxa_state=None,
            result_out=result_out,
            name=f"{self.name}.CreateParticipantStatus",
        )
        node.datalayer = self.datalayer
        node.actor_id = self._leaving_actor_id
        result = node.update()
        if result != Status.SUCCESS:
            self.logger.warning(
                "%s: failed to create RM.CLOSED ParticipantStatus for"
                " actor '%s' in case '%s'",
                self.name,
                self._leaving_actor_id,
                self._case_id,
            )
            return Status.FAILURE

        self.logger.info(
            "%s: advanced actor '%s' to RM.CLOSED in case '%s'"
            " (CM-23-002/CM-23-003)",
            self.name,
            self._leaving_actor_id,
            self._case_id,
        )
        return Status.SUCCESS


class AdvanceCaseActorToRMClosedNode(DataLayerAction):
    """Advance the Case Actor's own RM state to ``RM.CLOSED``.

    Reads the Case Actor's :class:`~vultron.core.models.case_participant
    .CaseParticipant` record from the DataLayer and appends a new
    :class:`~vultron.core.models.participant_status.ParticipantStatus` entry
    with ``rm_state=RM.CLOSED``.  Only executed on the owner Leave path, as
    the penultimate step before emitting the ``case_fully_closed`` ledger entry
    (CM-23-002 step 2; ADR-0051).

    Idempotent: returns ``SUCCESS`` without modification if the Case Actor is
    already at ``RM.CLOSED``.
    """

    def __init__(
        self,
        case_actor_id: str,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_actor_id = case_actor_id
        self._case_id = case_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case = self.datalayer.read(self._case_id)
        if not isinstance(case, VulnerabilityCase):
            self.logger.warning(
                "%s: case '%s' not found or wrong type",
                self.name,
                self._case_id,
            )
            return Status.FAILURE

        participant_id = case.actor_participant_index.get(self._case_actor_id)
        if participant_id is None:
            self.logger.warning(
                "%s: case actor '%s' not in actor_participant_index"
                " for case '%s'",
                self.name,
                self._case_actor_id,
                self._case_id,
            )
            return Status.FAILURE

        participant = self.datalayer.read(participant_id)
        if not isinstance(participant, CaseParticipant):
            self.logger.warning(
                "%s: participant '%s' for case actor not found or wrong type",
                self.name,
                participant_id,
            )
            return Status.FAILURE

        # Idempotency: skip if already at RM.CLOSED
        for ps in participant.participant_statuses:
            if participant_status_rm_state(ps) == RM.CLOSED:
                self.logger.debug(
                    "%s: case actor '%s' already at RM.CLOSED — no-op",
                    self.name,
                    self._case_actor_id,
                )
                return Status.SUCCESS

        result_out: dict = {}
        node = CreateParticipantStatusNode(
            case_id=self._case_id,
            actor_id=self._case_actor_id,
            rm_state=RM.CLOSED,
            vfd_state=None,
            pxa_state=None,
            result_out=result_out,
            name=f"{self.name}.CreateParticipantStatus",
        )
        node.datalayer = self.datalayer
        node.actor_id = self._case_actor_id
        result = node.update()
        if result != Status.SUCCESS:
            self.logger.warning(
                "%s: failed to create RM.CLOSED ParticipantStatus for"
                " case actor '%s' in case '%s'",
                self.name,
                self._case_actor_id,
                self._case_id,
            )
            return Status.FAILURE

        self.logger.info(
            "%s: advanced case actor '%s' to RM.CLOSED in case '%s'"
            " (CM-23-002 step 2, ADR-0051)",
            self.name,
            self._case_actor_id,
            self._case_id,
        )
        return Status.SUCCESS
