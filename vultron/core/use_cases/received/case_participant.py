"""Use cases for case participant management activities."""

import logging

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.case_participant_received_tree import (
    create_add_case_participant_received_tree,
    create_remove_case_participant_received_tree,
)
from vultron.core.models.events.case_participant import (
    AddCaseParticipantToCaseReceivedEvent,
    CreateCaseParticipantReceivedEvent,
    RemoveCaseParticipantFromCaseReceivedEvent,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.use_cases._helpers import _idempotent_create

logger = logging.getLogger(__name__)


class CreateCaseParticipantReceivedUseCase:
    def __init__(
        self, dl: CasePersistence, request: CreateCaseParticipantReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: CreateCaseParticipantReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        _idempotent_create(
            self._dl,
            request.object_type,
            request.participant_id,
            request.participant,
            "CaseParticipant",
            request.activity_id,
        )


class AddCaseParticipantToCaseReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: AddCaseParticipantToCaseReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: AddCaseParticipantToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        participant_id = request.participant_id
        case_id = request.case_id
        if participant_id is None or case_id is None:
            logger.warning(
                "add_case_participant_to_case: missing participant_id or case_id"
            )
            return
        tree = create_add_case_participant_received_tree(
            participant_id=participant_id,
            case_id=case_id,
        )
        bridge = BTBridge(datalayer=self._dl)
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=request.actor_id,
            activity=request,
        )
        if result.status != Status.SUCCESS:
            logger.warning(
                "AddCaseParticipantReceivedBT did not succeed"
                " for participant '%s' / case '%s': %s",
                participant_id,
                case_id,
                BTBridge.get_failure_reason(tree),
            )
        else:
            logger.info(
                "Added participant '%s' to case '%s'",
                participant_id,
                case_id,
            )


class RemoveCaseParticipantFromCaseReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: RemoveCaseParticipantFromCaseReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: RemoveCaseParticipantFromCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        participant_id = request.participant_id
        case_id = request.case_id
        if participant_id is None or case_id is None:
            logger.warning(
                "remove_case_participant_from_case: missing participant_id or case_id"
            )
            return
        tree = create_remove_case_participant_received_tree(
            participant_id=participant_id,
            case_id=case_id,
        )
        bridge = BTBridge(datalayer=self._dl)
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=request.actor_id,
            activity=request,
        )
        if result.status != Status.SUCCESS:
            logger.warning(
                "RemoveCaseParticipantReceivedBT did not succeed"
                " for participant '%s' / case '%s': %s",
                participant_id,
                case_id,
                BTBridge.get_failure_reason(tree),
            )
        else:
            logger.info(
                "Removed participant '%s' from case '%s'",
                participant_id,
                case_id,
            )
