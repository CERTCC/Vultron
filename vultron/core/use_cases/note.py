"""Use cases for case note activities."""

import logging
from typing import cast

from vultron.core.models.events.note import (
    AddNoteToCaseReceivedEvent,
    CreateNoteReceivedEvent,
    RemoveNoteFromCaseReceivedEvent,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.core.use_cases._types import CaseModel

logger = logging.getLogger(__name__)


class CreateNoteReceivedUseCase:
    def __init__(self, dl: DataLayer) -> None:
        self._dl = dl

    def execute(self, request: CreateNoteReceivedEvent) -> None:
        try:
            existing = self._dl.get(request.object_type, request.object_id)
            if existing is not None:
                logger.info(
                    "Note '%s' already stored — skipping (idempotent)",
                    request.object_id,
                )
                return

            obj_to_store = request.note
            if obj_to_store is not None:
                self._dl.create(obj_to_store)
                logger.info("Stored Note '%s'", request.object_id)
            else:
                logger.warning(
                    "create_note: no note object for event '%s'",
                    request.activity_id,
                )

        except Exception as e:
            logger.error(
                "Error in create_note for activity %s: %s",
                request.activity_id,
                str(e),
            )


class AddNoteToCaseReceivedUseCase:
    def __init__(self, dl: DataLayer) -> None:
        self._dl = dl

    def execute(self, request: AddNoteToCaseReceivedEvent) -> None:
        try:
            note_id = request.object_id
            case_id = request.target_id
            case = cast(CaseModel, self._dl.read(case_id))

            if case is None:
                logger.warning(
                    "add_note_to_case: case '%s' not found", case_id
                )
                return

            existing_ids = [
                (n.as_id if hasattr(n, "as_id") else n) for n in case.notes
            ]
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

        except Exception as e:
            logger.error(
                "Error in add_note_to_case for activity %s: %s",
                request.activity_id,
                str(e),
            )


class RemoveNoteFromCaseReceivedUseCase:
    def __init__(self, dl: DataLayer) -> None:
        self._dl = dl

    def execute(self, request: RemoveNoteFromCaseReceivedEvent) -> None:
        try:
            note_id = request.object_id
            case_id = request.target_id
            case = cast(CaseModel, self._dl.read(case_id))

            if case is None:
                logger.warning(
                    "remove_note_from_case: case '%s' not found", case_id
                )
                return

            existing_ids = [
                (n.as_id if hasattr(n, "as_id") else n) for n in case.notes
            ]
            if note_id not in existing_ids:
                logger.info(
                    "Note '%s' not in case '%s' — skipping (idempotent)",
                    note_id,
                    case_id,
                )
                return

            case.notes = [  # type: ignore[assignment]
                n
                for n in case.notes
                if (n.as_id if hasattr(n, "as_id") else n) != note_id
            ]
            self._dl.save(case)
            logger.info("Removed note '%s' from case '%s'", note_id, case_id)

        except Exception as e:
            logger.error(
                "Error in remove_note_from_case for activity %s: %s",
                request.activity_id,
                str(e),
            )
