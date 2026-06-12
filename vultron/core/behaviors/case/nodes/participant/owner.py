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

"""Owner-participant creation nodes and subtree."""

from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.participant.common import (
    _create_and_attach_participant,
)
from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.actor_config import ActorConfig
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.protocols import is_case_model
from vultron.core.models.vultron_types import VultronCase, VultronParticipant
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.states.rm import RM
from vultron.core.states.roles import CVDRole
from vultron.core.use_cases._helpers import (
    _as_id,
    _report_phase_status_id,
    update_participant_rm_state,
)


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
                rm_state=initial_rm_state,
                attributed_to=actor_id,
            )

    return ParticipantStatus(
        context=case_id,
        rm_state=initial_rm_state,
        attributed_to=actor_id,
    )


def _effective_case_roles(actor_config: ActorConfig | None) -> list[CVDRole]:
    base_roles = actor_config.default_case_roles if actor_config else []
    return list(dict.fromkeys(base_roles + [CVDRole.CASE_OWNER]))


class ResolveOwnerInitialStatusNode(DataLayerAction):
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

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="owner_initial_status", access=py_trees.common.Access.WRITE
        )

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                "%s: DataLayer or actor_id not available",
                self.name,
            )
            return Status.FAILURE

        try:
            case_id = _resolve_case_id(self.blackboard, self.case_obj)
        except KeyError:
            case_id = None
        if case_id is None:
            self.logger.error("%s: case_id not available", self.name)
            return Status.FAILURE

        self.blackboard.owner_initial_status = _build_owner_initial_status(
            self.datalayer,
            self.actor_id,
            case_id,
            self.report_id,
            self.initial_rm_state,
        )
        return Status.SUCCESS


class CreateOwnerParticipantNode(DataLayerAction):
    """Create the in-memory owner participant and stage it on blackboard."""

    def __init__(
        self,
        actor_config: ActorConfig | None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.actor_config = actor_config

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="owner_initial_status", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="new_case_participant",
            access=py_trees.common.Access.WRITE,
        )

    def update(self) -> Status:
        if self.actor_id is None:
            self.logger.error("%s: actor_id not available", self.name)
            return Status.FAILURE
        try:
            case_id_obj = self.blackboard.get("case_id")
        except KeyError:
            case_id_obj = None
        initial_status = self.blackboard.get("owner_initial_status")
        if not isinstance(initial_status, ParticipantStatus):
            self.logger.error(
                "%s: case_id/owner_initial_status missing in blackboard",
                self.name,
            )
            return Status.FAILURE
        case_id = case_id_obj
        if not isinstance(case_id, str):
            status_context = _as_id(initial_status.context)
            case_id = status_context if status_context is not None else None
        if case_id is None:
            self.logger.error("%s: case_id not available", self.name)
            return Status.FAILURE

        self.blackboard.new_case_participant = VultronParticipant(
            attributed_to=self.actor_id,
            context=case_id,
            case_roles=_effective_case_roles(self.actor_config),
            participant_statuses=[initial_status],
        )
        return Status.SUCCESS


class AttachOwnerParticipantToCaseNode(DataLayerAction):
    """Persist and attach staged owner participant to the case."""

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="new_case_participant",
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key="participant_case", access=py_trees.common.Access.WRITE
        )

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                "%s: DataLayer or actor_id not available",
                self.name,
            )
            return Status.FAILURE
        try:
            case_id_obj = self.blackboard.get("case_id")
        except KeyError:
            case_id_obj = None
        participant = self.blackboard.get("new_case_participant")
        if not isinstance(participant, VultronParticipant):
            self.logger.error(
                "%s: case_id/new_case_participant missing in blackboard",
                self.name,
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

        self.blackboard.participant_case = stored_case
        return Status.SUCCESS


class PersistOwnerCaseNode(DataLayerAction):
    """Persist the updated case after owner participant attachment."""

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="participant_case", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE
        stored_case = self.blackboard.get("participant_case")
        if not is_case_model(stored_case):
            self.logger.error(
                "%s: participant_case missing in blackboard",
                self.name,
            )
            return Status.FAILURE
        self.datalayer.save(stored_case)
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


class AdvanceOwnerRmToAcceptedNode(DataLayerAction):
    """Advance owner RM to ACCEPTED when case creation means engagement."""

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="participant_case", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                "%s: DataLayer or actor_id not available",
                self.name,
            )
            return Status.FAILURE
        try:
            case_id_obj = self.blackboard.get("case_id")
        except KeyError:
            case_id_obj = None
        case_id = case_id_obj if isinstance(case_id_obj, str) else None
        if case_id is None:
            stored_case = self.blackboard.get("participant_case")
            case_id = stored_case.id_ if is_case_model(stored_case) else None
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


class RecordOwnerJoinedEventNode(DataLayerAction):
    """Record owner_joined event and persist the case update."""

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="participant_case",
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key="new_case_participant",
            access=py_trees.common.Access.READ,
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE

        stored_case = self.blackboard.get("participant_case")
        participant = self.blackboard.get("new_case_participant")
        if not is_case_model(stored_case) or not isinstance(
            participant, VultronParticipant
        ):
            self.logger.error(
                "%s: participant_case/new_case_participant missing in"
                " blackboard",
                self.name,
            )
            return Status.FAILURE

        return Status.SUCCESS


class CreateCaseOwnerParticipant(py_trees.composites.Sequence):
    """
    Composed subtree that creates and attaches the case-owner participant.

    Per specs/case-management.yaml CM-02-008, BTND-05-002, and BTND-07-001.
    """

    def __init__(
        self,
        actor_config: ActorConfig | None = None,
        report_id: str | None = None,
        case_obj: VultronCase | None = None,
        advance_to_accepted: bool = False,
        initial_rm_state: RM = RM.VALID,
        name: str | None = None,
    ):
        super().__init__(
            name=name or self.__class__.__name__,
            memory=False,
            children=[
                ResolveOwnerInitialStatusNode(
                    report_id=report_id,
                    case_obj=case_obj,
                    initial_rm_state=initial_rm_state,
                ),
                CreateOwnerParticipantNode(actor_config=actor_config),
                AttachOwnerParticipantToCaseNode(),
                PersistOwnerCaseNode(),
                py_trees.composites.Selector(
                    name="AdvanceOwnerRmIfConfigured",
                    memory=False,
                    children=[
                        py_trees.composites.Sequence(
                            name="AdvanceOwnerRmBranch",
                            memory=False,
                            children=[
                                ShouldAdvanceOwnerToAcceptedNode(
                                    advance_to_accepted=advance_to_accepted
                                ),
                                AdvanceOwnerRmToAcceptedNode(),
                            ],
                        ),
                        py_trees.behaviours.Success(name="SkipAdvanceOwnerRm"),
                    ],
                ),
            ],
        )
