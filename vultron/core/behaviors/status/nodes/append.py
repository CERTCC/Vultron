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

"""Append-participant-status leaf nodes for DEMOMA-07-003 step 2.

Contains the leaf nodes that implement the append sequence: check idempotency,
load participant, resolve status object, and append + save.  The RM-transition
guards that also participate in that sequence live in
:mod:`vultron.core.behaviors.status.nodes.rm_validation` (BTND-07-004).
"""

import logging
from typing import Any, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction, DataLayerCondition
from vultron.core.behaviors.status.nodes.dimension_filter import (
    BB_DIMENSION_FILTER,
    resolve_dimension_filter,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.protocols import PersistableModel
from vultron.core.models._helpers import _as_id

logger = logging.getLogger(__name__)


class SkipIfIdempotentNode(py_trees.behaviour.Behaviour):
    """Idempotency guard for the append-participant-status Selector.

    Returns SUCCESS when *status_id* is already present in the participant's
    status list — causing the parent Selector to short-circuit and skip the
    append subtree. Returns FAILURE when the status is not yet appended,
    allowing the parent Selector to continue to the append subtree.

    This is the inverse of :class:`CheckStatusNotAlreadyAppendedNode`: that
    node is used to halt a Sequence on duplicate; this node is used to skip
    an append Selector on duplicate.

    Per DEMOMA-07-003 step 2 idempotency requirement.
    """

    def __init__(
        self,
        status_id: str,
        participant_id: str,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.status_id = status_id
        self.participant_id = participant_id

    def setup(self, **kwargs: Any) -> None:
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(
            key="append_status_participant",
            access=py_trees.common.Access.READ,
        )

    def update(self) -> Status:
        participant = self.blackboard.get("append_status_participant")
        if participant is None:
            return Status.FAILURE

        existing_ids = [_as_id(s) for s in participant.participant_statuses]
        if self.status_id in existing_ids:
            logging.getLogger(self.__class__.__module__).info(
                "SkipIfIdempotentNode: status '%s' already on participant"
                " '%s' — idempotent, skipping (SUCCESS)",
                self.status_id,
                self.participant_id,
            )
            return Status.SUCCESS
        return Status.FAILURE


class LoadParticipantNode(DataLayerAction):
    """Load the CaseParticipant from DataLayer to blackboard.

    Reads the participant by ID and writes it to the blackboard under the key
    ``append_status_participant``.

    Returns SUCCESS if the participant is found and is a valid participant model.
    Returns FAILURE if participant not found or is not a participant model.
    """

    def __init__(self, participant_id: str, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.participant_id = participant_id

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="append_status_participant",
            access=py_trees.common.Access.WRITE,
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        participant = self.datalayer.read(self.participant_id)
        if not isinstance(participant, CaseParticipant):
            self.feedback_message = (
                f"Participant '{self.participant_id}' not found"
            )
            self.logger.warning(
                "LoadParticipantNode: %s", self.feedback_message
            )
            return Status.FAILURE

        self.logger.debug(
            "LoadParticipantNode: loaded participant '%s'",
            self.participant_id,
        )
        self.blackboard.set(
            "append_status_participant", participant, overwrite=True
        )
        return Status.SUCCESS


class CheckStatusNotAlreadyAppendedNode(DataLayerCondition):
    """Check idempotency: is the status already appended to the participant?

    Returns SUCCESS if the status is NOT already on the participant
    (i.e., it's safe to append). Returns SUCCESS if the participant has no
    statuses yet.

    Returns FAILURE if the status ID already exists in the participant's
    status list, indicating the append would be redundant.
    """

    def __init__(
        self, status_id: str, participant_id: str, name: str | None = None
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.status_id = status_id
        self.participant_id = participant_id

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="append_status_participant",
            access=py_trees.common.Access.READ,
        )

    def update(self) -> Status:
        participant = self.blackboard.get("append_status_participant")
        if participant is None:
            self.feedback_message = "Participant not on blackboard"
            self.logger.warning(
                "CheckStatusNotAlreadyAppendedNode: %s",
                self.feedback_message,
            )
            return Status.FAILURE

        existing_ids = [_as_id(s) for s in participant.participant_statuses]
        if self.status_id in existing_ids:
            self.logger.info(
                "CheckStatusNotAlreadyAppendedNode: status '%s' already"
                " on participant '%s' — idempotent, skipping",
                self.status_id,
                self.participant_id,
            )
            return Status.FAILURE

        self.logger.debug(
            "CheckStatusNotAlreadyAppendedNode: status '%s' not yet appended",
            self.status_id,
        )
        return Status.SUCCESS


class ResolveAndPersistStatusObjectNode(DataLayerAction):
    """Resolve the status object by ID, persisting fallback if needed.

    When :class:`~vultron.core.behaviors.status.nodes.dimension_filter.FilterParticipantStatusDimensionsNode`
    has partially accepted the inbound status, the *filtered* status (refused
    dimensions carried forward) is persisted at ``status_id`` and used in place
    of the raw assertion, so that the appended record, the ledger ``object``
    reference and the Seam 2 emit all describe the accepted portion (RSH-05).

    Otherwise tries the DataLayer first; if not found, uses
    ``status_obj_fallback``, saves it, then re-reads the canonical record.

    Validates that the resolved object is a ParticipantStatus (has rm and
    vfd attributes).

    Writes the resolved status object to the blackboard under the key
    ``append_status_status_obj``.

    Returns SUCCESS if status is resolved and valid.
    Returns FAILURE if status cannot be resolved or is not a ParticipantStatus.
    """

    def __init__(
        self,
        status_id: str,
        status_obj_fallback: PersistableModel | None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.status_id = status_id
        self.status_obj_fallback = status_obj_fallback

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="append_status_status_obj",
            access=py_trees.common.Access.WRITE,
        )
        self.blackboard.register_key(
            key=BB_DIMENSION_FILTER,
            access=py_trees.common.Access.READ,
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        filtered = resolve_dimension_filter(self.blackboard, self.status_id)
        if filtered is not None:
            status_obj = filtered["filtered_status"]
            self.datalayer.save(status_obj)
            self.logger.info(
                "ResolveAndPersistStatusObjectNode: persisted partially"
                " accepted status '%s' (refused: %s) in place of the raw"
                " assertion (RSH-05)",
                self.status_id,
                ", ".join(filtered["refused"]),
            )
            status_obj = self.datalayer.read(self.status_id) or status_obj
        else:
            status_obj = self.datalayer.read(self.status_id)
        if not hasattr(status_obj, "id_"):
            status_obj = self.status_obj_fallback
            if status_obj is not None:
                self.datalayer.save(status_obj)
                status_obj = self.datalayer.read(self.status_id) or status_obj

        if status_obj is None or not hasattr(status_obj, "id_"):
            self.feedback_message = f"Status '{self.status_id}' not found"
            self.logger.warning(
                "ResolveAndPersistStatusObjectNode: %s",
                self.feedback_message,
            )
            return Status.FAILURE

        if not hasattr(status_obj, "rm") or not hasattr(status_obj, "vfd"):
            self.feedback_message = (
                f"Object '{self.status_id}' is not a ParticipantStatus"
            )
            self.logger.warning(
                "ResolveAndPersistStatusObjectNode: %s",
                self.feedback_message,
            )
            return Status.FAILURE

        self.logger.debug(
            "ResolveAndPersistStatusObjectNode: resolved status '%s'",
            self.status_id,
        )
        self.blackboard.set(
            "append_status_status_obj", status_obj, overwrite=True
        )
        return Status.SUCCESS


class AppendStatusAndSaveParticipantNode(DataLayerAction):
    """Append the status object to the participant and save.

    Appends the resolved status object (from blackboard) to the participant's
    status list and saves the participant to the DataLayer.

    Returns SUCCESS on successful append and save.
    Returns FAILURE if participant or status not on blackboard.
    """

    def __init__(
        self, status_id: str, participant_id: str, name: str | None = None
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.status_id = status_id
        self.participant_id = participant_id

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="append_status_participant",
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key="append_status_status_obj",
            access=py_trees.common.Access.READ,
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        participant = self.blackboard.get("append_status_participant")
        status_obj = self.blackboard.get("append_status_status_obj")

        if participant is None or status_obj is None:
            self.feedback_message = "Participant or status not on blackboard"
            self.logger.warning(
                "AppendStatusAndSaveParticipantNode: %s",
                self.feedback_message,
            )
            return Status.FAILURE

        participant.participant_statuses.append(
            cast(ParticipantStatus, status_obj)
        )
        self.datalayer.save(participant)
        self.logger.info(
            "AppendStatusAndSaveParticipantNode: added status '%s' to"
            " participant '%s' (DEMOMA-07-003 step 2)",
            self.status_id,
            self.participant_id,
        )
        return Status.SUCCESS
