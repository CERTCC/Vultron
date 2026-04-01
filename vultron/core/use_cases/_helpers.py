"""Shared helper utilities for use-case implementations.

Module-level helpers used across multiple use-case modules.
All helpers are private to the use-cases package (prefix ``_``).
"""

import logging
import uuid
from typing import Any

from vultron.core.models.protocols import (
    is_case_model,
    is_participant_model,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.core.states.rm import RM
from vultron.errors import VultronNotFoundError, VultronValidationError

logger = logging.getLogger(__name__)


def _as_id(obj: Any) -> str | None:
    """Return the ActivityStreams id of *obj* as a plain string.

    - If *obj* is ``None``, returns ``None``.
    - If *obj* has an ``id_`` attribute, returns ``obj.id_``.
    - Otherwise returns ``str(obj)``.

    This handles the mixed ``str | <wire-type>`` collections that arise when
    the DataLayer stores plain string IDs alongside rehydrated objects.
    """
    if obj is None:
        return None
    id_ = getattr(obj, "id_", None)
    if isinstance(id_, str):
        return id_
    return str(obj)


def _idempotent_create(
    dl: DataLayer,
    type_key: str | None,
    id_key: str | None,
    obj: Any,
    label: str,
    activity_id: str | None = None,
) -> None:
    """Guard against duplicate object creation.

    Checks whether *id_key* is already present in the DataLayer.  If so, logs
    and returns without storing.  Otherwise stores *obj* (if not ``None``) via
    ``dl.create``.

    Args:
        dl: The DataLayer to read/write.
        type_key: Object type used as the DataLayer collection key.
        id_key: Object ID to check for existence.
        obj: The domain object to persist when not already present.
        label: Human-readable label used in log messages (e.g. ``"Note"``).
        activity_id: Activity ID used in warning log when *obj* is ``None``.
    """
    if not type_key or not id_key:
        return
    if dl.get(type_key, id_key) is not None:
        logger.info("'%s' already stored — skipping (idempotent)", id_key)
        return
    if obj is not None:
        dl.create(obj)
        logger.info("Stored %s '%s'", label, id_key)
    else:
        logger.warning("no %s object for event '%s'", label, activity_id)


def _report_phase_status_id(
    actor_id: str, report_id: str, rm_state: str
) -> str:
    """Return a deterministic URN for a report-phase participant status record.

    Uses UUID v5 (name-based) so the same (actor, report, rm_state) triple
    always produces the same ID, enabling idempotent DataLayer creation.
    """
    name = f"{actor_id}|{report_id}|{rm_state}"
    return f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, name)}"


def resolve_case(case_id: str, dl: DataLayer):
    """Resolve a VulnerabilityCase by ID; raise domain error if absent or wrong
    type.

    This neutral helper is importable from any layer without triggering the
    ``triggers`` package ``__init__`` (which would cause circular imports when
    called from the BT nodes layer).
    """
    case_raw = dl.read(case_id)
    if case_raw is None:
        raise VultronNotFoundError("VulnerabilityCase", case_id)
    if not is_case_model(case_raw):
        raise VultronValidationError(
            f"Expected VulnerabilityCase, got {type(case_raw).__name__}."
        )
    return case_raw


def update_participant_rm_state(
    case_id: str, actor_id: str, new_rm_state: RM, dl: DataLayer
) -> bool:
    """Append a new ParticipantStatus with new_rm_state to the actor's
    CaseParticipant in the given case and persist the updated participant.

    Handles both inline and string-reference participants.

    Returns ``True`` on success (including idempotent no-op), ``False`` when
    the case or participant is not found.

    This neutral helper is importable from any layer without triggering the
    ``triggers`` package ``__init__`` (which would cause circular imports when
    called from the BT nodes layer).
    """
    case_obj = dl.read(case_id)
    if not is_case_model(case_obj):
        logger.warning(
            "update_participant_rm_state: case '%s' not found or wrong type",
            case_id,
        )
        return False

    for participant_ref in case_obj.case_participants:
        if isinstance(participant_ref, str):
            participant_raw = dl.read(participant_ref)
            if participant_raw is None:
                continue
        else:
            participant_raw = participant_ref

        if not is_participant_model(participant_raw):
            continue

        participant = participant_raw

        actor_ref = participant.attributed_to
        p_actor_id = (
            actor_ref
            if isinstance(actor_ref, str)
            else getattr(actor_ref, "id_", str(actor_ref))
        )
        if p_actor_id == actor_id:
            if participant.participant_statuses:
                latest = participant.participant_statuses[-1]
                if latest.rm_state == new_rm_state:
                    logger.info(
                        "Participant '%s' already in RM state %s in case '%s' "
                        "(idempotent)",
                        actor_id,
                        new_rm_state,
                        case_id,
                    )
                    return True
            appended = participant.append_rm_state(
                rm_state=new_rm_state, actor=actor_id, context=case_id
            )
            if not appended:
                logger.warning(
                    "update_participant_rm_state: RM transition to %s blocked "
                    "for actor '%s' in case '%s'",
                    new_rm_state,
                    actor_id,
                    case_id,
                )
                return False
            dl.save(participant)
            logger.info(
                "Set participant '%s' RM state to %s in case '%s'",
                actor_id,
                new_rm_state,
                case_id,
            )
            return True

    logger.warning(
        "update_participant_rm_state: no CaseParticipant for actor '%s' "
        "in case '%s'; RM state not updated",
        actor_id,
        case_id,
    )
    return False
