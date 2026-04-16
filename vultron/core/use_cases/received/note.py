"""Use cases for case note activities."""

import logging
from typing import Any, cast

from vultron.core.models.events.note import (
    AddNoteToCaseReceivedEvent,
    CreateNoteReceivedEvent,
    RemoveNoteFromCaseReceivedEvent,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.core.models.protocols import is_case_model
from vultron.core.use_cases._helpers import _as_id, _idempotent_create
from vultron.wire.as2.vocab.activities.case import AddNoteToCaseActivity

logger = logging.getLogger(__name__)


class CreateNoteReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: CreateNoteReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: CreateNoteReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        _idempotent_create(
            self._dl,
            request.object_type,
            request.note_id,
            request.note,
            "Note",
            request.activity_id,
        )


class AddNoteToCaseReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: AddNoteToCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: AddNoteToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        note_id = request.note_id
        case_id = request.case_id
        if note_id is None or case_id is None:
            logger.warning("add_note_to_case: missing note_id or case_id")
            return
        case = self._dl.read(case_id)

        if not is_case_model(case):
            logger.warning("add_note_to_case: case '%s' not found", case_id)
            return

        existing_ids = [_as_id(n) for n in case.notes]
        if note_id in existing_ids:
            logger.info(
                "Note '%s' already in case '%s' — skipping (idempotent)",
                note_id,
                case_id,
            )
            return

        case.notes.append(note_id)
        self._dl.save(case)
        logger.info("Added note '%s' to case '%s'", note_id, case_id)

        self._broadcast_note_to_participants(
            note_id=note_id,
            case_id=case_id,
            author_id=request.actor_id,
            case=case,
        )

    def _broadcast_note_to_participants(
        self,
        note_id: str,
        case_id: str,
        author_id: str,
        case: Any,
    ) -> None:
        """Broadcast note addition to all case participants via CaseActor.

        Implements CM-06-005: when a note is added to a case the CaseActor
        MUST broadcast the note to all participants (excluding the author).
        Recipients are derived from VulnerabilityCase.actor_participant_index.
        """
        # Locate the CaseActor (type_="Service") for this case.
        service_records = self._dl.by_type("Service")
        case_actor_id: str | None = None
        for obj_id, data in service_records.items():
            if data.get("context") == case_id:
                case_actor_id = obj_id
                break

        if case_actor_id is None:
            logger.debug(
                "add_note_to_case: no CaseActor found for case '%s'"
                " — skipping broadcast (CM-06-005)",
                case_id,
            )
            return

        recipient_ids = [
            actor_id
            for actor_id in case.actor_participant_index.keys()
            if actor_id != author_id
        ]
        if not recipient_ids:
            logger.debug(
                "add_note_to_case: no eligible recipients in case '%s'"
                " — skipping broadcast",
                case_id,
            )
            return

        broadcast = AddNoteToCaseActivity(
            actor=case_actor_id,
            object_=cast(Any, self._dl.read(note_id)),
            target=case_id,
            to=recipient_ids,
        )
        try:
            self._dl.create(broadcast)
        except ValueError:
            logger.debug(
                "add_note_to_case: broadcast activity %s already exists"
                " — skipping",
                broadcast.id_,
            )
            return

        case_actor_obj = self._dl.read(case_actor_id)
        if case_actor_obj is not None and hasattr(case_actor_obj, "outbox"):
            cast(Any, case_actor_obj).outbox.items.append(broadcast.id_)
            self._dl.save(case_actor_obj)

        self._dl.record_outbox_item(case_actor_id, broadcast.id_)

        logger.info(
            "add_note_to_case: CaseActor '%s' broadcast AddNoteToCase for"
            " note '%s' in case '%s' to %d participant(s) (CM-06-005)",
            case_actor_id,
            note_id,
            case_id,
            len(recipient_ids),
        )


class RemoveNoteFromCaseReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: RemoveNoteFromCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: RemoveNoteFromCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        note_id = request.note_id
        case_id = request.case_id
        if note_id is None or case_id is None:
            logger.warning("remove_note_from_case: missing note_id or case_id")
            return
        case = self._dl.read(case_id)

        if not is_case_model(case):
            logger.warning(
                "remove_note_from_case: case '%s' not found", case_id
            )
            return

        existing_ids = [_as_id(n) for n in case.notes]
        if note_id not in existing_ids:
            logger.info(
                "Note '%s' not in case '%s' — skipping (idempotent)",
                note_id,
                case_id,
            )
            return

        case.notes = [  # type: ignore[assignment]
            n for n in case.notes if _as_id(n) != note_id
        ]
        self._dl.save(case)
        logger.info("Removed note '%s' from case '%s'", note_id, case_id)
