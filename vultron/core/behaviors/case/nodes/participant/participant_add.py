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

"""Non-owner participant creation/attachment leaf nodes.

Provides leaf action nodes for the participant creation workflow.
The composite subtrees that orchestrate these nodes
(``SeedParticipantAsSignatoryIfEmbargoActiveNode`` and
``CreateCaseParticipantNode``) live in ``participant_tree.py`` at the
process-area root, per BTND-07-003.
"""

from typing import Any, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.participant.common import (
    _create_and_attach_participant,
    _get_or_create_accepted_status,
    _queue_participant_add_notification,
)
from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.participant_status import (
    ParticipantStatus,
    coerce_cvd_roles,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.vultron_types import VultronParticipant
from vultron.core.states.participant_embargo_consent import PEC
from vultron.enums.roles import CVDRole
from vultron.core.models._helpers import _as_id


class ResolveParticipantAcceptedStatusNode(DataLayerAction):
    """Resolve or create report-phase RM.ACCEPTED status for the participant."""

    def __init__(
        self,
        participant_actor_id: str,
        roles: list[CVDRole],
        report_id: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.participant_actor_id = participant_actor_id
        self.roles = roles
        self.report_id = report_id
        _seg = report_id.split("/")[-1] if report_id else "default"
        self._participant_accepted_status_key = (
            f"participant_accepted_status_{_seg}"
        )

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key=self._participant_accepted_status_key,
            access=py_trees.common.Access.WRITE,
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE

        result = _get_or_create_accepted_status(
            self.datalayer,
            self.participant_actor_id,
            self.report_id,
            self.name,
            self.logger,
            cvd_role=coerce_cvd_roles(self.roles),
            em_consent_state=PEC.NO_EMBARGO,
        )
        setattr(self.blackboard, self._participant_accepted_status_key, result)
        return Status.SUCCESS


class CreateParticipantNode(DataLayerAction):
    """Create an in-memory VultronParticipant and store it on the blackboard."""

    def __init__(
        self,
        participant_actor_id: str,
        roles: list[CVDRole],
        report_id: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.participant_actor_id = participant_actor_id
        self.roles = roles
        _seg = report_id.split("/")[-1] if report_id else "default"
        self._participant_accepted_status_key = (
            f"participant_accepted_status_{_seg}"
        )
        self._new_case_participant_key = f"new_case_participant_{_seg}"
        self._new_participant_id_key = f"new_participant_id_{_seg}"

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key=self._participant_accepted_status_key,
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key=self._new_case_participant_key,
            access=py_trees.common.Access.WRITE,
        )
        self.blackboard.register_key(
            key=self._new_participant_id_key,
            access=py_trees.common.Access.WRITE,
        )

    def update(self) -> Status:
        case_id = self.blackboard.get("case_id")
        if not isinstance(case_id, str):
            self.logger.error("%s: case_id not found in blackboard", self.name)
            return Status.FAILURE

        accepted_status = self.blackboard.get(
            self._participant_accepted_status_key
        )
        if accepted_status is not None and not isinstance(
            accepted_status, ParticipantStatus
        ):
            self.logger.error(
                "%s: %s has invalid type",
                self.name,
                self._participant_accepted_status_key,
            )
            return Status.FAILURE

        participant = VultronParticipant(
            attributed_to=self.participant_actor_id,
            context=case_id,
            case_roles=self.roles,
            participant_statuses=(
                [cast(ParticipantStatus, accepted_status)]
                if accepted_status is not None
                else []
            ),
        )
        setattr(self.blackboard, self._new_case_participant_key, participant)
        setattr(self.blackboard, self._new_participant_id_key, participant.id_)
        return Status.SUCCESS


class AttachParticipantToCaseNode(DataLayerAction):
    """Attach the participant to case surfaces and persist the participant row."""

    def __init__(
        self,
        participant_actor_id: str,
        report_id: str | None = None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.participant_actor_id = participant_actor_id
        _seg = report_id.split("/")[-1] if report_id else "default"
        self._new_case_participant_key = f"new_case_participant_{_seg}"
        self._participant_case_key = f"participant_case_{_seg}"

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key=self._new_case_participant_key,
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key=self._participant_case_key,
            access=py_trees.common.Access.WRITE,
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE

        case_id = self.blackboard.get("case_id")
        participant = self.blackboard.get(self._new_case_participant_key)
        if not isinstance(case_id, str):
            self.logger.error("%s: case_id not found in blackboard", self.name)
            return Status.FAILURE
        if not isinstance(participant, VultronParticipant):
            self.logger.error(
                "%s: %s not found in blackboard",
                self.name,
                self._new_case_participant_key,
            )
            return Status.FAILURE

        stored_case = _create_and_attach_participant(
            self.datalayer,
            participant,
            case_id,
            self.participant_actor_id,
            self.logger,
        )
        if stored_case is None:
            self.logger.error(
                "%s: Case %s not found in DataLayer",
                self.name,
                case_id,
            )
            return Status.FAILURE

        setattr(self.blackboard, self._participant_case_key, stored_case)
        return Status.SUCCESS


class RecordParticipantAddedEventNode(DataLayerAction):
    """Record participant_added event and persist case updates."""

    def __init__(
        self, report_id: str | None = None, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        _seg = report_id.split("/")[-1] if report_id else "default"
        self._participant_case_key = f"participant_case_{_seg}"
        self._new_participant_id_key = f"new_participant_id_{_seg}"

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key=self._participant_case_key,
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key=self._new_participant_id_key,
            access=py_trees.common.Access.READ,
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE

        stored_case = self.blackboard.get(self._participant_case_key)
        participant_id = self.blackboard.get(self._new_participant_id_key)
        if not isinstance(stored_case, VulnerabilityCase) or not isinstance(
            participant_id, str
        ):
            self.logger.error(
                "%s: %s/%s missing in blackboard",
                self.name,
                self._participant_case_key,
                self._new_participant_id_key,
            )
            return Status.FAILURE

        self.datalayer.save(stored_case)
        return Status.SUCCESS


class CaseHasActiveEmbargoNode(DataLayerAction):
    """Condition node: SUCCESS when the case has an active embargo."""

    def __init__(
        self, report_id: str | None = None, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        _seg = report_id.split("/")[-1] if report_id else "default"
        self._participant_case_key = f"participant_case_{_seg}"

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key=self._participant_case_key,
            access=py_trees.common.Access.READ,
        )

    def update(self) -> Status:
        stored_case = self.blackboard.get(self._participant_case_key)
        if not isinstance(stored_case, VulnerabilityCase):
            self.logger.error(
                "%s: %s missing in blackboard",
                self.name,
                self._participant_case_key,
            )
            return Status.FAILURE
        return (
            Status.SUCCESS
            if _as_id(stored_case.active_embargo) is not None
            else Status.FAILURE
        )


class CaseHasNoActiveEmbargoNode(DataLayerAction):
    """Condition node: SUCCESS when no active embargo exists for this case."""

    def __init__(
        self, report_id: str | None = None, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        _seg = report_id.split("/")[-1] if report_id else "default"
        self._participant_case_key = f"participant_case_{_seg}"

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key=self._participant_case_key,
            access=py_trees.common.Access.READ,
        )

    def update(self) -> Status:
        stored_case = self.blackboard.get(self._participant_case_key)
        if not isinstance(stored_case, VulnerabilityCase):
            self.logger.error(
                "%s: %s missing in blackboard",
                self.name,
                self._participant_case_key,
            )
            return Status.FAILURE
        return (
            Status.SUCCESS
            if _as_id(stored_case.active_embargo) is None
            else Status.FAILURE
        )


class SeedParticipantAsSignatoryNode(DataLayerAction):
    """Seed the new participant as SIGNATORY when an embargo is active."""

    def __init__(
        self,
        participant_actor_id: str,
        report_id: str | None = None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.participant_actor_id = participant_actor_id
        _seg = report_id.split("/")[-1] if report_id else "default"
        self._participant_case_key = f"participant_case_{_seg}"
        self._new_case_participant_key = f"new_case_participant_{_seg}"

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key=self._participant_case_key,
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key=self._new_case_participant_key,
            access=py_trees.common.Access.READ,
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE

        stored_case = self.blackboard.get(self._participant_case_key)
        participant = self.blackboard.get(self._new_case_participant_key)
        if not isinstance(stored_case, VulnerabilityCase) or not isinstance(
            participant, VultronParticipant
        ):
            self.logger.error(
                "%s: %s/%s missing in blackboard",
                self.name,
                self._participant_case_key,
                self._new_case_participant_key,
            )
            return Status.FAILURE

        active_embargo_id = _as_id(stored_case.active_embargo)
        if active_embargo_id is None:
            self.logger.error(
                "%s: cannot seed SIGNATORY without active embargo",
                self.name,
            )
            return Status.FAILURE

        participant.embargo_consent_state = PEC.SIGNATORY
        if active_embargo_id not in participant.accepted_embargo_ids:
            participant.accepted_embargo_ids.append(active_embargo_id)
        self.datalayer.save(participant)
        self.logger.info(
            "Seeded participant '%s' (actor '%s') as SIGNATORY"
            " for active embargo in case '%s' (CM-14-005)",
            participant.id_,
            self.participant_actor_id,
            stored_case.id_,
        )
        return Status.SUCCESS


class QueueAddParticipantNotificationNode(DataLayerAction):
    """Queue Add(CaseParticipant) outbox notification for the sender actor."""

    def __init__(
        self,
        participant_actor_id: str,
        report_id: str | None = None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.participant_actor_id = participant_actor_id
        _seg = report_id.split("/")[-1] if report_id else "default"
        self._new_participant_id_key = f"new_participant_id_{_seg}"

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key=self._new_participant_id_key,
            access=py_trees.common.Access.READ,
        )

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                "%s: DataLayer or actor_id not available", self.name
            )
            return Status.FAILURE

        case_id = self.blackboard.get("case_id")
        participant_id = self.blackboard.get(self._new_participant_id_key)
        if not isinstance(case_id, str) or not isinstance(participant_id, str):
            self.logger.error(
                "%s: case_id/%s not found in blackboard",
                self.name,
                self._new_participant_id_key,
            )
            return Status.FAILURE

        if not _queue_participant_add_notification(
            self.datalayer,
            self.name,
            self.logger,
            self.actor_id,
            self.participant_actor_id,
            participant_id,
            case_id,
            trigger_activity=self.trigger_activity_factory,
        ):
            return Status.FAILURE
        return Status.SUCCESS
