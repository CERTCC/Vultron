"""
Handler functions for case participant management activities.
"""

import logging

from vultron.api.v2.backend.handlers._base import verify_semantics
from vultron.core.models.events import MessageSemantics
from vultron.types import DispatchActivity

from vultron.core.ports.datalayer import DataLayer

logger = logging.getLogger(__name__)


@verify_semantics(MessageSemantics.CREATE_CASE_PARTICIPANT)
def create_case_participant(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    """
    Process a Create(CaseParticipant) activity.

    Persists the new CaseParticipant to the DataLayer. Because
    CaseParticipant uses `attributed_to` (a standard as_Object field) for
    the actor reference, the full object survives inbox deserialization.
    Idempotent: if a participant with the same ID already exists, the
    handler logs at INFO and returns without side effects (ID-04-004).

    Args:
        dispatchable: DispatchActivity containing the as_Create with
                      CaseParticipant object
    """
    from vultron.api.v2.data.rehydration import rehydrate

    payload = dispatchable.payload

    try:
        participant = rehydrate(dispatchable.wire_object)
        participant_id = payload.object_id

        existing = dl.get(payload.object_type, payload.object_id)
        if existing is not None:
            logger.info(
                "Participant '%s' already exists — skipping (idempotent)",
                participant_id,
            )
            return None

        dl.create(participant)
        logger.info("Created participant '%s'", participant_id)

    except Exception as e:
        logger.error(
            "Error in create_case_participant for activity %s: %s",
            payload.activity_id,
            str(e),
        )


@verify_semantics(MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE)
def add_case_participant_to_case(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    """
    Process an AddParticipantToCase activity
    (Add(CaseParticipant, target=VulnerabilityCase)).

    Appends the participant reference to the case's case_participants list
    and persists the updated case to the DataLayer. Idempotent: re-adding a
    participant already in the case succeeds without side effects (ID-04-004).

    Args:
        dispatchable: DispatchActivity containing the as_Add with
                      CaseParticipant object and VulnerabilityCase target
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.adapters.driven.db_record import object_to_record

    payload = dispatchable.payload

    try:
        participant = rehydrate(payload.object_id)
        case = rehydrate(payload.target_id)
        participant_id = payload.object_id
        case_id = payload.target_id

        existing_ids = [
            (p.as_id if hasattr(p, "as_id") else p)
            for p in case.case_participants
        ]
        if participant_id in existing_ids:
            logger.info(
                "Participant '%s' already in case '%s' — skipping (idempotent)",
                participant_id,
                case_id,
            )
            return None

        case.add_participant(participant)
        dl.update(case_id, object_to_record(case))

        logger.info(
            "Added participant '%s' to case '%s'", participant_id, case_id
        )

    except Exception as e:
        logger.error(
            "Error in add_case_participant_to_case for activity %s: %s",
            payload.activity_id,
            str(e),
        )


@verify_semantics(MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE)
def remove_case_participant_from_case(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    """
    Process a Remove(CaseParticipant, target=VulnerabilityCase) activity.

    Removes the participant reference from the case's case_participants list
    and persists the updated case. Idempotent: if the participant is not in
    the case, the handler returns without error (ID-04-004).

    Args:
        dispatchable: DispatchActivity containing the as_Remove with
                      CaseParticipant object and VulnerabilityCase target
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.adapters.driven.db_record import object_to_record

    payload = dispatchable.payload

    try:
        participant_id = payload.object_id
        case = rehydrate(payload.target_id)
        case_id = payload.target_id

        existing_ids = [
            (p.as_id if hasattr(p, "as_id") else p)
            for p in case.case_participants
        ]
        if participant_id not in existing_ids:
            logger.info(
                "Participant '%s' not in case '%s' — skipping (idempotent)",
                participant_id,
                case_id,
            )
            return None

        case.remove_participant(participant_id)
        dl.update(case_id, object_to_record(case))

        logger.info(
            "Removed participant '%s' from case '%s'",
            participant_id,
            case_id,
        )

    except Exception as e:
        logger.error(
            "Error in remove_case_participant_from_case for activity %s: %s",
            payload.activity_id,
            str(e),
        )
