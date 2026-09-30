"""Use cases for case participant management activities."""

import logging

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.case_participant_received_tree import (
    create_add_case_participant_received_tree,
    create_remove_case_participant_received_tree,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.events.case_participant import (
    AddCaseParticipantToCaseReceivedEvent,
    CreateCaseParticipantReceivedEvent,
    RemoveCaseParticipantFromCaseReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.use_cases._helpers import (
    _idempotent_create,
    resolve_receiving_actor_id,
)
from vultron.core.use_cases.received._bt_verdict import verdict_from_bt

logger = logging.getLogger(__name__)


class CreateCaseParticipantReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: CreateCaseParticipantReceivedEvent,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: CreateCaseParticipantReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        return _idempotent_create(
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
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: AddCaseParticipantToCaseReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        participant_id = request.participant_id
        case_id = request.case_id
        if participant_id is None or case_id is None:
            logger.warning(
                "add_case_participant_to_case: missing participant_id or case_id"
            )
            return HandlerResult.refused(
                "Add(CaseParticipant, Case) is missing its participant id or"
                " case id"
            )
        tree = create_add_case_participant_received_tree(
            participant_id=participant_id,
            case_id=case_id,
        )
        bridge = BTBridge(
            datalayer=self._dl, wire_render_port=self._wire_render_port
        )
        result = bridge.execute_with_setup(
            tree=tree,
            # The *receiving* actor, not the sender (BT-17-005): an
            # inbound activity is applied to the receiver's own replica,
            # so the tree must execute in the receiver's store.
            actor_id=resolve_receiving_actor_id(
                self._dl, request.receiving_actor_id
            ),
            activity=request,
        )
        verdict = verdict_from_bt(
            tree, result, label="AddCaseParticipantReceivedBT"
        )
        if verdict.disposition is not HandlerDisposition.APPLIED:
            # The participant was not added: an unknown case or participant
            # is a rejection of the message, not an internal error (#2255).
            logger.warning(
                "AddCaseParticipantReceivedBT did not add participant '%s'"
                " to case '%s': %s",
                participant_id,
                case_id,
                verdict.reason,
            )
            return verdict
        logger.info(
            "Added participant '%s' to case '%s'",
            participant_id,
            case_id,
        )
        return HandlerResult.applied()


class RemoveCaseParticipantFromCaseReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: RemoveCaseParticipantFromCaseReceivedEvent,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._request: RemoveCaseParticipantFromCaseReceivedEvent = request

    def execute(self) -> HandlerResult:
        request = self._request
        participant_id = request.participant_id
        case_id = request.case_id
        if participant_id is None or case_id is None:
            logger.warning(
                "remove_case_participant_from_case: missing participant_id or case_id"
            )
            return HandlerResult.refused(
                "Remove(CaseParticipant, Case) is missing its participant id"
                " or case id"
            )
        # The node treats an absent participant as idempotent SUCCESS, so the
        # no-op has to be told apart here to report it as SKIPPED.
        case = self._dl.read_case(case_id)
        if case is not None and participant_id not in [
            _as_id(p) for p in case.case_participants
        ]:
            logger.info(
                "Participant '%s' not in case '%s' — skipping (idempotent)",
                participant_id,
                case_id,
            )
            return HandlerResult.skipped(
                f"participant '{participant_id}' not in case '{case_id}'"
            )
        tree = create_remove_case_participant_received_tree(
            participant_id=participant_id,
            case_id=case_id,
        )
        bridge = BTBridge(
            datalayer=self._dl, wire_render_port=self._wire_render_port
        )
        result = bridge.execute_with_setup(
            tree=tree,
            # The *receiving* actor, not the sender (BT-17-005): an
            # inbound activity is applied to the receiver's own replica,
            # so the tree must execute in the receiver's store.
            actor_id=resolve_receiving_actor_id(
                self._dl, request.receiving_actor_id
            ),
            activity=request,
        )
        verdict = verdict_from_bt(
            tree, result, label="RemoveCaseParticipantReceivedBT"
        )
        if verdict.disposition is not HandlerDisposition.APPLIED:
            logger.warning(
                "RemoveCaseParticipantReceivedBT did not remove participant"
                " '%s' from case '%s': %s",
                participant_id,
                case_id,
                verdict.reason,
            )
            return verdict
        logger.info(
            "Removed participant '%s' from case '%s'",
            participant_id,
            case_id,
        )
        return verdict
