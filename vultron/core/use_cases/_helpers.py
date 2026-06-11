"""Shared helper utilities for use-case implementations.

Module-level helpers used across multiple use-case modules.
All helpers are private to the use-cases package (prefix ``_``).
"""

import logging
import uuid
from typing import Any

from vultron.core.models.protocols import (
    CaseModel,
    is_case_model,
    is_participant_model,
)
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.states.participant_embargo_consent import (
    PEC,
    PEC_Trigger,
    apply_pec_trigger,
)
from vultron.core.states.rm import RM
from vultron.core.states.roles import CVDRole
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


def _find_case_actor_id(dl: CasePersistence, case_id: str) -> str | None:
    """Return the CaseActor Service ID for *case_id*, if present in the DataLayer.

    First checks for a ``VultronReportCaseLink`` whose ``trusted_case_actor_id``
    was established during bootstrap (CBT-01-006).  Falls back to the legacy
    Service-object scan for backward compatibility.

    Returns ``None`` when no CaseActor Service can be found for *case_id*.
    This is the authoritative resolver for PCR-08-007 (invite sender) and
    PCR-08-008 (accept recipient).
    """
    for link in dl.list_objects("ReportCaseLink"):
        if isinstance(link, VultronReportCaseLink):
            if link.case_id == case_id and link.trusted_case_actor_id:
                return str(link.trusted_case_actor_id)

    for service in dl.list_objects("Service"):
        if getattr(service, "context", None) == case_id:
            return service.id_
    return None


def _idempotent_create(
    dl: CasePersistence,
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
    if dl.read(id_key) is not None:
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


def resolve_case(case_id: str, dl: CasePersistence):
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
    case_id: str, actor_id: str, new_rm_state: RM, dl: CasePersistence
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


def _resolve_case_manager_id(
    case: CaseModel, dl: CasePersistence
) -> str | None:
    """Return the actor ID of the Case Manager (CVDRole.CASE_MANAGER).

    Iterates over all participants in the case's ``actor_participant_index``
    and returns the ``attributed_to`` actor ID of the first participant that
    holds ``CVDRole.CASE_MANAGER``.  Returns ``None`` when no Case Manager
    participant is found.

    This is the correct recipient for all participant-originated outbound
    activities after case creation (PCR-08-001, PCR-08-002).
    """
    for p_id in case.actor_participant_index.values():
        p = dl.read(p_id)
        if p is None:
            continue
        roles = getattr(p, "case_roles", [])
        if CVDRole.CASE_MANAGER in roles:
            manager_actor_id = getattr(p, "attributed_to", None)
            return _as_id(manager_actor_id)
    return None


def resolve_case_participant_id_for_actor(
    case: CaseModel,
    actor_id: str,
    dl: CasePersistence,
) -> str | None:
    """Resolve participant ID from actor ID using ``case_participants`` as truth.

    The lookup canonical source is ``case.case_participants``. The derived
    ``actor_participant_index`` mapping is validated against that source and
    any divergence raises :class:`VultronValidationError`.
    """
    resolved_ids: list[str] = []
    for participant_ref in case.case_participants:
        participant_id = _as_id(participant_ref)
        if participant_id is None:
            continue
        participant_obj = (
            participant_ref
            if is_participant_model(participant_ref)
            else dl.read(participant_id)
        )
        if not is_participant_model(participant_obj):
            continue
        participant_actor_id = _as_id(participant_obj.attributed_to)
        if participant_actor_id == actor_id:
            resolved_ids.append(participant_id)

    unique_ids = sorted(set(resolved_ids))
    if len(unique_ids) > 1:
        raise VultronValidationError(
            "Participant-index divergence: actor "
            f"'{actor_id}' resolves to multiple participants "
            f"{unique_ids!r} in case_participants."
        )

    indexed_id = case.actor_participant_index.get(actor_id)
    if not unique_ids:
        if indexed_id is not None:
            raise VultronValidationError(
                "Participant-index divergence: actor "
                f"'{actor_id}' maps to '{indexed_id}' in "
                "actor_participant_index but has no matching participant in "
                "case_participants."
            )
        return None

    canonical_id = unique_ids[0]
    if indexed_id is not None and indexed_id != canonical_id:
        raise VultronValidationError(
            "Participant-index divergence: actor "
            f"'{actor_id}' resolves to '{canonical_id}' from "
            f"case_participants but actor_participant_index maps to "
            f"'{indexed_id}'."
        )

    return canonical_id


def reset_case_participant_embargo_consent(
    dl: CasePersistence, case: CaseModel
) -> None:
    """Reset all participants' embargo consent state to NO_EMBARGO.

    Called when an embargo is terminated or removed.  Iterates over all
    participants in *case* and applies ``PEC_Trigger.RESET`` to any
    participant whose embargo_consent_state is not already ``NO_EMBARGO``.
    Tolerates both string IDs and inline ``CaseParticipant`` objects in
    ``case.case_participants`` (regression #609).

    This is the single authoritative implementation; the former duplicates
    ``_reset_case_participant_embargo_consent`` (received layer) and
    ``_cascade_pec_reset`` (triggers layer) have been removed in favour of
    this shared helper.
    """
    for entry in case.case_participants:
        participant_id = _as_id(entry)
        if participant_id is None:
            continue
        participant = dl.read(participant_id)
        if not is_participant_model(participant):
            continue
        if participant.embargo_consent_state != PEC.NO_EMBARGO.value:
            participant.embargo_consent_state = apply_pec_trigger(
                PEC(participant.embargo_consent_state), PEC_Trigger.RESET
            )
            dl.save(participant)


def case_addressees(case: CaseModel, excluding_actor_id: str) -> list[str]:
    """Return actor IDs for all case participants except *excluding_actor_id*.

    Uses ``case.actor_participant_index`` (a ``dict[actor_id, participant_id]``)
    so the caller does not need to iterate over ``case_participants`` directly.

    Returns an empty list when there are no other participants.
    """
    return [
        actor_id
        for actor_id in case.actor_participant_index.keys()
        if actor_id != excluding_actor_id
    ]
