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

"""Store-local ``RM.CLOSED`` advances for a received Leave(VulnerabilityCase).

Both nodes here write a ``ParticipantStatus`` to the *local* DataLayer and
nothing else.  Recording the CASE_MANAGER's transition on the ledger is a
separate concern — see :mod:`.record`.

Per ADR-0050, ADR-0051, and specs/case-management.yaml CM-23-002/CM-23-003.
"""

import logging

from py_trees.common import Status

from vultron.core.behaviors.case.nodes.participant.rm_closure import (
    RMClosureWriter,
)
from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.participant_status import (
    participant_status_rm_state,
)
from vultron.core.states.rm import RM

logger = logging.getLogger(__name__)


class AdvanceParticipantToRMClosedNode(DataLayerActionWithPorts):
    """Advance the leaving actor's RM state to ``RM.CLOSED`` in the DataLayer.

    Reads the leaving actor's :class:`~vultron.core.models.case_participant
    .CaseParticipant` record from the DataLayer and appends a new
    :class:`~vultron.core.models.participant_status.ParticipantStatus` entry
    for each ordinary RM transition from its current rung to ``RM.CLOSED``
    (:class:`RMClosureWriter`): one entry from Received, Invalid, Accepted or
    Deferred, and ``DEFERRED`` then ``CLOSED`` from Valid (CM-23-012,
    RMB-14-005).  Idempotent: if the participant is already at
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
        _name = name or self.__class__.__name__
        super().__init__(name=_name)
        self._leaving_actor_id = leaving_actor_id
        self._case_id = case_id
        # Pre-build the status writers (BTND-10-004: no construction in
        # update()).  The closure is written as ordinary RM transitions, so a
        # Leave from VALID is V -> D -> C (RMB-14-005, CM-23-012).
        self._closure = RMClosureWriter(actor_id=leaving_actor_id, name=_name)

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1: case must exist (ADR-0087)

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

        closed = self._closure.close(
            self, self.datalayer, participant_id, self._case_id
        )
        if closed != Status.SUCCESS:
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


class AdvanceCaseActorToRMClosedNode(DataLayerActionWithPorts):
    """Advance the Case Actor's own RM state to ``RM.CLOSED``.

    Reads the Case Actor's :class:`~vultron.core.models.case_participant
    .CaseParticipant` record from the DataLayer and appends a new
    :class:`~vultron.core.models.participant_status.ParticipantStatus` entry
    for each ordinary RM transition to ``RM.CLOSED`` (:class:`RMClosureWriter`,
    RMB-14-005).  Only executed on the owner Leave path, as
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
        _name = name or self.__class__.__name__
        super().__init__(name=_name)
        self._case_actor_id = case_actor_id
        self._case_id = case_id
        # Pre-build the status writers (BTND-10-004: no construction in
        # update()).  The closure is written as ordinary RM transitions, so a
        # Leave from VALID is V -> D -> C (RMB-14-005, CM-23-012).
        self._closure = RMClosureWriter(actor_id=case_actor_id, name=_name)

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1: case must exist (ADR-0087)

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

        closed = self._closure.close(
            self, self.datalayer, participant_id, self._case_id
        )
        if closed != Status.SUCCESS:
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
