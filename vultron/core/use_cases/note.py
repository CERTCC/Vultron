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


def create_note(event: CreateNoteReceivedEvent, dl: DataLayer) -> None:
    try:
        existing = dl.get(event.object_type, event.object_id)
        if existing is not None:
            logger.info(
                "Note '%s' already stored — skipping (idempotent)",
                event.object_id,
            )
            return

        obj_to_store = event.note
        if obj_to_store is not None:
            dl.create(obj_to_store)
            logger.info("Stored Note '%s'", event.object_id)
        else:
            logger.warning(
                "create_note: no note object for event '%s'",
                event.activity_id,
            )

    except Exception as e:
        logger.error(
            "Error in create_note for activity %s: %s",
            event.activity_id,
            str(e),
        )


def add_note_to_case(event: AddNoteToCaseReceivedEvent, dl: DataLayer) -> None:
    try:
        note_id = event.object_id
        case_id = event.target_id
        case = cast(CaseModel, dl.read(case_id))

        if case is None:
            logger.warning("add_note_to_case: case '%s' not found", case_id)
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
        dl.save(case)
        logger.info("Added note '%s' to case '%s'", note_id, case_id)

    except Exception as e:
        logger.error(
            "Error in add_note_to_case for activity %s: %s",
            event.activity_id,
            str(e),
        )


def remove_note_from_case(
    event: RemoveNoteFromCaseReceivedEvent, dl: DataLayer
) -> None:
    try:
        note_id = event.object_id
        case_id = event.target_id
        case = cast(CaseModel, dl.read(case_id))

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
        dl.save(case)
        logger.info("Removed note '%s' from case '%s'", note_id, case_id)

    except Exception as e:
        logger.error(
            "Error in remove_note_from_case for activity %s: %s",
            event.activity_id,
            str(e),
        )
