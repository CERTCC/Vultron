"""
Handler functions for case note activities.
"""

import logging

from vultron.api.v2.backend.handlers._base import verify_semantics
from vultron.core.models.events import MessageSemantics
from vultron.types import DispatchActivity

from vultron.core.ports.datalayer import DataLayer

logger = logging.getLogger(__name__)


@verify_semantics(MessageSemantics.CREATE_NOTE)
def create_note(dispatchable: DispatchActivity, dl: DataLayer) -> None:
    """
    Process a Create(Note) activity.

    Persists the Note to the DataLayer so it can be referenced by
    subsequent add_note_to_case activities. Idempotent: if a Note with
    the same ID already exists, the handler skips creation (ID-04-004).

    Args:
        dispatchable: DispatchActivity containing the Create(Note)
    """
    payload = dispatchable.payload

    try:
        existing = dl.get(payload.object_type, payload.object_id)
        if existing is not None:
            logger.info(
                "Note '%s' already stored — skipping (idempotent)",
                payload.object_id,
            )
            return None

        dl.create(dispatchable.wire_object)
        logger.info("Stored Note '%s'", payload.object_id)

    except Exception as e:
        logger.error(
            "Error in create_note for activity %s: %s",
            payload.activity_id,
            str(e),
        )


@verify_semantics(MessageSemantics.ADD_NOTE_TO_CASE)
def add_note_to_case(dispatchable: DispatchActivity, dl: DataLayer) -> None:
    """
    Process an Add(Note, target=VulnerabilityCase) activity.

    Appends the note reference to the case's notes list and persists the
    updated case. Idempotent: re-adding a note already in the case
    succeeds without side effects (ID-04-004).

    Args:
        dispatchable: DispatchActivity containing the Add(Note, target=case)
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.adapters.driven.db_record import object_to_record

    payload = dispatchable.payload

    try:
        note_id = payload.object_id
        case = rehydrate(payload.target_id)
        case_id = payload.target_id

        existing_ids = [
            (n.as_id if hasattr(n, "as_id") else n) for n in case.notes
        ]
        if note_id in existing_ids:
            logger.info(
                "Note '%s' already in case '%s' — skipping (idempotent)",
                note_id,
                case_id,
            )
            return None

        case.notes.append(note_id)
        dl.update(case_id, object_to_record(case))
        logger.info("Added note '%s' to case '%s'", note_id, case_id)

    except Exception as e:
        logger.error(
            "Error in add_note_to_case for activity %s: %s",
            payload.activity_id,
            str(e),
        )


@verify_semantics(MessageSemantics.REMOVE_NOTE_FROM_CASE)
def remove_note_from_case(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    """
    Process a Remove(Note, target=VulnerabilityCase) activity.

    Removes the note reference from the case's notes list and persists
    the updated case. Idempotent: if the note is not in the case,
    the handler returns without error (ID-04-004).

    Args:
        dispatchable: DispatchActivity containing the Remove(Note, target=case)
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.adapters.driven.db_record import object_to_record

    payload = dispatchable.payload

    try:
        note_id = payload.object_id
        case = rehydrate(payload.target_id)
        case_id = payload.target_id

        existing_ids = [
            (n.as_id if hasattr(n, "as_id") else n) for n in case.notes
        ]
        if note_id not in existing_ids:
            logger.info(
                "Note '%s' not in case '%s' — skipping (idempotent)",
                note_id,
                case_id,
            )
            return None

        case.notes = [
            n
            for n in case.notes
            if (n.as_id if hasattr(n, "as_id") else n) != note_id
        ]
        dl.update(case_id, object_to_record(case))
        logger.info("Removed note '%s' from case '%s'", note_id, case_id)

    except Exception as e:
        logger.error(
            "Error in remove_note_from_case for activity %s: %s",
            payload.activity_id,
            str(e),
        )
