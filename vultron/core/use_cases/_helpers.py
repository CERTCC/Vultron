"""Shared helper utilities for use-case implementations.

Module-level helpers used across multiple use-case modules.
All helpers are private to the use-cases package (prefix ``_``).
"""

import hashlib
import logging
from typing import Any

from vultron.core.behaviors.narrative_log import log_rm_transition
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.ports.case_persistence import (
    CasePersistence,
    CaseOutboxPersistence,
)
from vultron.core.states.participant_embargo_consent import (
    PEC,
    PEC_Trigger,
)
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.errors import VultronNotFoundError, VultronValidationError

logger = logging.getLogger(__name__)

_SNAPSHOT_REFERENCE_FIELDS = {
    "object",
    "object_",
    "target",
    "active_embargo",
    "activeEmbargo",
    "proposed_embargoes",
    "proposedEmbargoes",
    "vulnerability_reports",
    "vulnerabilityReports",
    "notes",
    "case_participants",
    "caseParticipants",
    "case_statuses",
    "caseStatuses",
}
_SNAPSHOT_INLINE_DEPTH_LIMIT = 8


def _inline_snapshot_reference_value(
    value: Any,
    dl: CasePersistence | None,
    *,
    should_resolve_strings: bool,
    resolving_ids: set[str],
    expected_context: str | None,
    depth: int,
) -> Any:
    """Inline nested AS2 object references for canonical payload snapshots."""
    if depth > _SNAPSHOT_INLINE_DEPTH_LIMIT:
        return value

    if isinstance(value, dict):
        inlined: dict[str, Any] = {}
        for key, child in value.items():
            inlined[key] = _inline_snapshot_reference_value(
                child,
                dl,
                should_resolve_strings=(key in _SNAPSHOT_REFERENCE_FIELDS),
                resolving_ids=resolving_ids,
                expected_context=expected_context,
                depth=depth + 1,
            )
        return inlined

    if isinstance(value, list):
        return [
            _inline_snapshot_reference_value(
                item,
                dl,
                should_resolve_strings=should_resolve_strings,
                resolving_ids=resolving_ids,
                expected_context=expected_context,
                depth=depth + 1,
            )
            for item in value
        ]

    if (
        not should_resolve_strings
        or dl is None
        or not isinstance(value, str)
        or value in resolving_ids
    ):
        return value

    resolved = dl.read(value)
    if resolved is None or not hasattr(resolved, "model_dump"):
        return value
    resolved_context = _as_id(getattr(resolved, "context", None))
    if (
        expected_context is None
        or resolved_context is None
        or resolved_context != expected_context
    ):
        return value

    resolving_ids.add(value)
    try:
        dumped = resolved.model_dump(
            mode="json",
            by_alias=True,
            serialize_as_any=True,
            exclude_none=True,
        )
        return _inline_snapshot_reference_value(
            dumped,
            dl,
            should_resolve_strings=False,
            resolving_ids=resolving_ids,
            expected_context=expected_context,
            depth=depth + 1,
        )
    finally:
        resolving_ids.remove(value)


def build_activity_payload_snapshot(
    activity: Any, dl: CasePersistence | None = None
) -> dict[str, Any]:
    """Return a normalized, self-contained payload snapshot for ledger entries.

    If a DataLayer is provided, known nested object-reference fields are inlined
    from storage so canonical CaseLedgerEntry snapshots do not carry bare ID
    strings for protocol-significant nested objects.
    """
    if activity is None or not hasattr(activity, "model_dump"):
        return {}

    snapshot: dict[str, Any] = activity.model_dump(
        mode="json",
        by_alias=True,
        serialize_as_any=True,
        exclude_none=True,
    )
    expected_context = snapshot.get("context")
    if not isinstance(expected_context, str):
        expected_context = None
    inlined = _inline_snapshot_reference_value(
        snapshot,
        dl,
        should_resolve_strings=False,
        resolving_ids=set(),
        expected_context=expected_context,
        depth=0,
    )
    return inlined if isinstance(inlined, dict) else {}


def _find_case_actor_id(dl: CasePersistence, case_id: str) -> str | None:
    """Return the CaseActor Service ID for *case_id*, if present in the DataLayer.

    Resolution order:

    1. A ``VultronReportCaseLink`` whose ``trusted_case_actor_id`` was
       established during bootstrap (CBT-01-006).
    2. A *pending* ``VultronReportCaseLink`` whose ``trusted_case_creator_id``
       matches the ``CVDRole.CASE_MANAGER`` participant of the case replica
       (CBT-01-003), i.e. the proposal target has confirmed itself as case
       manager but the link has not been completed yet.
    3. A legacy scan for a ``Service`` object whose ``context`` is *case_id*.

    Path 2 exists because paths 1 and 3 both have a window in which they
    cannot answer.  The link only carries ``case_id``/``trusted_case_actor_id``
    once ``Create(VulnerabilityCase)`` has been *fully processed*, and under
    ADR-0041 the CaseActor ``Service`` object the receiver writes ahead of
    ``Create(as_CaseProposal)`` has no ``context`` (the case does not exist
    yet).  A participant-triggered action taken between replica seeding and
    link completion — e.g. ``invite-actor-to-case`` immediately after
    ``engage-case`` — would otherwise resolve ``None``, sending the Invite from
    the owner's identity with no ``cc:`` to the CaseActor.  The invitee's
    ``Accept`` then returns to a non-CASE_MANAGER, so no canonical
    ``accept_invite_actor_to_case`` entry is ever committed.  The case replica
    embeds the CASE_MANAGER participant from the moment it is seeded
    (CP-09-004), so path 2 closes the window.

    Path 2 is deliberately narrow: it requires *both* an outstanding proposal
    to a known CaseActor *and* the case replica naming that same actor as
    CASE_MANAGER.  A CASE_MANAGER participant alone is not sufficient evidence
    of a CaseActor — cases whose manager is an ordinary participant have no
    CaseActor and MUST still resolve ``None`` (ADR-0021).

    Returns ``None`` when no CaseActor Service can be found for *case_id*.
    This is the authoritative resolver for PCR-08-007 (invite sender) and
    PCR-08-008 (accept recipient).
    """
    pending_creator_ids: set[str] = set()
    for link in dl.list_objects("ReportCaseLink"):
        if isinstance(link, VultronReportCaseLink):
            if link.case_id == case_id and link.trusted_case_actor_id:
                return str(link.trusted_case_actor_id)
            if link.case_id is None and link.trusted_case_creator_id:
                pending_creator_ids.add(str(link.trusted_case_creator_id))

    if pending_creator_ids:
        case = dl.read(case_id)
        if isinstance(case, VulnerabilityCase):
            manager_id = _resolve_case_manager_id(case, dl)
            if manager_id is not None and manager_id in pending_creator_ids:
                return manager_id

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
        # Routine idempotency skip — infrastructure, not protocol story
        # (SL-04-007).  Fires on essentially every received-side activity.
        logger.debug("'%s' already stored — skipping (idempotent)", id_key)
        return
    if obj is not None:
        dl.create(obj)
        logger.info("Stored %s '%s'", label, id_key)
    else:
        logger.warning("no %s object for event '%s'", label, activity_id)


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
    if not isinstance(case_raw, VulnerabilityCase):
        raise VultronValidationError(
            f"Expected VulnerabilityCase, got {type(case_raw).__name__}."
        )
    return case_raw


def _scan_case_participants_for_actor(
    case_obj: VulnerabilityCase,
    actor_id: str,
    dl: CasePersistence,
) -> "CaseParticipant | None":
    """Return the CaseParticipant for actor_id by scanning case_participants.

    Resolves string references via ``dl.read``; skips entries that are
    missing from the DL or are not ``CaseParticipant`` objects.  Returns
    ``None`` when no matching participant is found.
    """
    for participant_ref in case_obj.case_participants:
        if isinstance(participant_ref, str):
            participant_raw = dl.read(participant_ref)
            if participant_raw is None:
                continue
        else:
            participant_raw = participant_ref
        if not isinstance(participant_raw, CaseParticipant):
            continue
        actor_ref = participant_raw.attributed_to
        p_actor_id = (
            actor_ref
            if isinstance(actor_ref, str)
            else getattr(actor_ref, "id_", str(actor_ref))
        )
        if p_actor_id == actor_id:
            return participant_raw
    return None


def _bootstrap_invited_participant(
    participant_id: str,
    actor_id: str,
    case_id: str,
    new_rm_state: RM,
    dl: CasePersistence,
) -> bool:
    """Create a fresh CaseParticipant for an invited actor and advance its RM state.

    Called when actor_participant_index confirms the actor is a participant but
    the participant object is absent from the local DL.  This occurs on the
    invited path: Announce(VulnerabilityCase) delivers only string IDs in
    case_participants, so _store_embedded_participants skips them and no
    CaseParticipant object lands in the invitee's DL (ISSUE-2216, ISSUE-2223).

    Bootstraps at RM.RECEIVED (the required entry state for an invited actor
    per CM-11-001) then attempts new_rm_state in one further step.
    """
    participant = CaseParticipant(
        id_=participant_id,
        attributed_to=actor_id,
        context=case_id,
    )
    # _init_participant_status_if_empty seeds participant_statuses at RM.START.
    if not participant.append_rm_state(
        rm_state=RM.RECEIVED, actor=actor_id, context=case_id
    ):
        logger.warning(
            "update_participant_rm_state: bootstrap RECEIVED blocked "
            "for actor '%s' in case '%s'",
            actor_id,
            case_id,
        )
        return False
    if new_rm_state != RM.RECEIVED and not participant.append_rm_state(
        rm_state=new_rm_state, actor=actor_id, context=case_id
    ):
        logger.warning(
            "update_participant_rm_state: bootstrap RM transition to %s "
            "blocked for actor '%s' in case '%s'",
            new_rm_state,
            actor_id,
            case_id,
        )
        return False
    dl.create(participant)
    log_rm_transition(logger, actor_id, case_id, RM.START, new_rm_state)
    return True


def update_participant_rm_state(
    case_id: str, actor_id: str, new_rm_state: RM, dl: CasePersistence
) -> bool:
    """Append a new ParticipantStatus with new_rm_state to the actor's
    CaseParticipant in the given case and persist the updated participant.

    Handles both inline and string-reference participants.  When the actor is
    listed in ``actor_participant_index`` but its participant object is absent
    from the local DL (invited-path bootstrap gap), the participant is
    created at RM.RECEIVED and advanced to ``new_rm_state`` in one step.

    Returns ``True`` on success (including idempotent no-op), ``False`` when
    the case or participant is not found.

    This neutral helper is importable from any layer without triggering the
    ``triggers`` package ``__init__`` (which would cause circular imports when
    called from the BT nodes layer).
    """
    case_obj = dl.read(case_id)
    if not isinstance(case_obj, VulnerabilityCase):
        logger.warning(
            "update_participant_rm_state: case '%s' not found or wrong type",
            case_id,
        )
        return False

    participant = _scan_case_participants_for_actor(case_obj, actor_id, dl)
    if participant is None:
        participant_id = case_obj.actor_participant_index.get(actor_id)
        if participant_id is None:
            logger.warning(
                "update_participant_rm_state: no CaseParticipant for actor '%s' "
                "in case '%s'; RM state not updated",
                actor_id,
                case_id,
            )
            return False
        return _bootstrap_invited_participant(
            participant_id, actor_id, case_id, new_rm_state, dl
        )

    rm_before: RM | None = None
    if participant.participant_statuses:
        latest = participant.participant_statuses[-1]
        rm_before = latest.rm.state
        if rm_before == new_rm_state:
            logger.debug(
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
    # SL-04-001/SL-04-006 narrative template: the per-participant RM
    # transition is the primary RM story line at INFO.
    log_rm_transition(
        logger,
        actor_id,
        case_id,
        rm_before if rm_before is not None else RM.START,
        new_rm_state,
    )
    return True


def current_participant_rm_state(
    case: VulnerabilityCase, actor_id: str, dl: CasePersistence
) -> RM:
    """Return *actor_id*'s latest RM state in *case*, or ``RM.START``.

    Used by narrative logging (SL-04-006) to report the before-state of an RM
    transition.  Returns ``RM.START`` when the actor is not yet a participant
    or has no recorded status, which is the RM machine's initial state.
    """
    participant_id = resolve_case_participant_id_for_actor(case, actor_id, dl)
    if participant_id is None:
        return RM.START
    participant = dl.read(participant_id)
    if not isinstance(participant, CaseParticipant):
        return RM.START
    statuses = participant.participant_statuses
    if not statuses:
        return RM.START
    state = statuses[-1].rm.state
    return state if isinstance(state, RM) else RM.START


def _resolve_case_manager_id(
    case: VulnerabilityCase, dl: CasePersistence
) -> str | None:
    """Return the actor ID of the Case Manager (CVDRole.CASE_MANAGER).

    Checks two participant sources in order:

    1. ``actor_participant_index`` — the fast lookup used after bootstrap
       (this is the primary path for trigger use cases).
    2. ``case_participants`` — the canonical list used during bootstrap,
       where inline participant objects may not yet be indexed.  This path
       also handles ID-only references that are absent from the index.

    Returns the ``attributed_to`` actor ID of the first participant holding
    ``CVDRole.CASE_MANAGER``, or ``None`` when none is found.

    This is the correct recipient for all participant-originated outbound
    activities after case creation (PCR-08-001, PCR-08-002).
    """
    # Primary path: fast index lookup (normal post-bootstrap operation).
    for p_id in case.actor_participant_index.values():
        p = dl.read(p_id)
        if not isinstance(p, CaseParticipant):
            continue
        if CVDRole.CASE_MANAGER in p.roles:
            manager_actor_id = getattr(p, "attributed_to", None)
            return _as_id(manager_actor_id)

    # Fallback: iterate case_participants for inline objects or IDs not yet
    # in the index (bootstrap path, CBT-01-003).
    indexed_participant_ids = set(case.actor_participant_index.values())
    for participant_ref in case.case_participants:
        if not isinstance(participant_ref, str):
            # Inline participant object — no DataLayer read needed.
            if (
                isinstance(participant_ref, CaseParticipant)
                and CVDRole.CASE_MANAGER in participant_ref.roles
            ):
                attributed = getattr(participant_ref, "attributed_to", None)
                return _as_id(attributed)
            continue
        if participant_ref in indexed_participant_ids:
            # Already checked via the index; skip to avoid duplicates.
            continue
        p = dl.read(participant_ref)
        if not isinstance(p, CaseParticipant):
            continue
        if CVDRole.CASE_MANAGER in p.roles:
            manager_actor_id = getattr(p, "attributed_to", None)
            return _as_id(manager_actor_id)
    return None


def resolve_case_participant_id_for_actor(
    case: VulnerabilityCase,
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
            if isinstance(participant_ref, CaseParticipant)
            else dl.read(participant_id)
        )
        if not isinstance(participant_obj, CaseParticipant):
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
    dl: CasePersistence, case: VulnerabilityCase
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
        if not isinstance(participant, CaseParticipant):
            continue
        if participant.embargo_consent_state != PEC.NO_EMBARGO.value:
            participant.apply_pec_transition(PEC_Trigger.RESET)
            dl.save(participant)


def case_addressees(
    case: VulnerabilityCase, excluding_actor_id: str
) -> list[str]:
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


def _log_label(uri: str) -> str:
    """Return a deterministic redacted label for IDs used in log messages.

    Do not log raw actor/activity identifiers (or URI segments) because they
    may be sensitive.  Instead, emit a short non-reversible hash token that
    still allows correlation across log lines.
    """
    digest = hashlib.sha256(uri.encode("utf-8")).hexdigest()[:12]
    return f"id:{digest}"


def outbox_ids(actor_id: str, dl: CaseOutboxPersistence) -> set[str]:
    """Return the set of string activity IDs in the actor's outbox queue.

    Uses ``outbox_list_for_actor`` when available (explicit actor scope),
    otherwise falls back to the actor-scoped ``outbox_list()``.

    Args:
        actor_id: The actor whose outbox should be queried.
        dl: The DataLayer to use for persistence.

    Returns:
        Set of activity IDs queued for delivery.
    """
    if hasattr(dl, "outbox_list_for_actor"):
        items: list[str] = dl.outbox_list_for_actor(actor_id)  # type: ignore[attr-defined]
        return set(items)
    return set(dl.outbox_list())


def add_activity_to_outbox(
    actor_id: str, activity_id: str, dl: CaseOutboxPersistence
) -> None:
    """Append an activity ID to an actor's outbox and queue it for delivery.

    Uses ``record_outbox_item`` to explicitly enqueue against *actor_id*,
    bypassing any actor-scope on *dl* itself.  This ensures correct delivery
    even when *dl* is a shared (unscoped) DataLayer instance.

    Args:
        actor_id: The actor whose outbox should receive the activity.
        activity_id: The ID of the activity to queue for delivery.
        dl: The DataLayer to use for persistence.
    """
    dl.record_outbox_item(actor_id, activity_id)
    logger.debug(
        "Queued activity '%s' in delivery queue for actor '%s'",
        _log_label(activity_id),
        _log_label(actor_id),
    )
