"""Shared helper utilities for use-case implementations.

Module-level helpers used across multiple use-case modules.
All helpers are private to the use-cases package (prefix ``_``).
"""

import hashlib
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.participant_status import (
    participant_status_rm_state,
)
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
from vultron.core.participants.authority import resolve_case_manager_id
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
    wire_render_port: "WireRenderPort | None" = None,
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
                wire_render_port=wire_render_port,
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
                wire_render_port=wire_render_port,
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
        if wire_render_port is not None:
            dumped = wire_render_port.render(resolved)
        else:
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
            wire_render_port=wire_render_port,
        )
    finally:
        resolving_ids.remove(value)


def build_activity_payload_snapshot(
    activity: Any,
    dl: CasePersistence | None = None,
    wire_render_port: "WireRenderPort | None" = None,
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
        wire_render_port=wire_render_port,
    )
    return inlined if isinstance(inlined, dict) else {}


def _established_link_actor_id(
    dl: CasePersistence, case_id: str
) -> str | None:
    """Return the ``trusted_case_actor_id`` recorded for *case_id*, if any.

    A completed ``VultronReportCaseLink`` records the address the authority was
    reached at during bootstrap (CBT-01-006).  That recorded address answers
    before the local replica has a participant roster to read, which is the one
    window :func:`resolve_case_manager_id` cannot cover.
    """
    for link in dl.list_objects("ReportCaseLink"):
        if not isinstance(link, VultronReportCaseLink):
            continue
        if link.case_id == case_id and link.trusted_case_actor_id:
            return str(link.trusted_case_actor_id)
    return None


def _find_case_actor_id(dl: CasePersistence, case_id: str) -> str | None:
    """Return the delivery address of *case_id*'s authority, if resolvable.

    **This is address resolution, not authority determination.**  The two are
    different questions and ADR-0088 keeps them apart: "am I the authority?" is
    answered by the role, via
    :func:`~vultron.core.participants.authority.resolve_case_manager_id`, and
    this function only answers "what address do I route to?".  Because
    authority *is* the ``CVDRole.CASE_MANAGER`` role, the authority's address is
    simply the role-holder's address (ARCH-24-005, CM-02-011).

    Resolution order:

    1. The ``trusted_case_actor_id`` recorded on a completed
       ``VultronReportCaseLink`` (CBT-01-006).
    2. The actor enacting ``CVDRole.CASE_MANAGER`` on the case replica.

    Path 1 comes first because it is the only answer available before the local
    replica has a roster to read: the link records the address the authority was
    reached at during bootstrap, whereas path 2 needs
    ``Create(VulnerabilityCase)`` to have seeded a replica.  Path 2 then covers
    everything afterwards, and covers it without a window — the replica embeds
    the CASE_MANAGER participant from the moment it is seeded (CP-09-004).

    Neither path consults a URL shape or a ``Service`` object's hosting
    location.  Both were removed by ADR-0088: they are not evidence of anything
    protocol-salient (ARCH-24-004, CM-02-013), and the ``Service``-``context``
    scan they relied on had a bootstrap window in which the real authority
    failed its own hosting test (CM-02-012).

    Returns ``None`` when the case has no resolvable authority address — a case
    with no CASE_MANAGER participant and no recorded link.  Every caller
    handles ``None``.  Note that an ordinary participant enacting CASE_MANAGER
    *is* the authority and *does* resolve here: under ADR-0088 there is no
    separate "CaseActor entity" that could be absent while the role is held.
    This is the authoritative address lookup for PCR-08-007 (invite sender) and
    PCR-08-008 (accept recipient).
    """
    established = _established_link_actor_id(dl, case_id)
    if established is not None:
        return established

    case = dl.read_case(case_id)
    if case is None:
        return None
    return resolve_case_manager_id(case, dl)


def resolve_receiving_actor_id(
    dl: CasePersistence, receiving_actor_id: str | None
) -> str:
    """Return the actor whose replica a received message is being applied to.

    Received-side use cases need an executing actor identity to run their BT
    under (BT-17-005).  ``receiving_actor_id`` is set by the inbox adapter and
    is authoritative when present.  When it is absent — CLI dispatch, replay,
    tests — the answer is *the actor whose store we were handed*: under
    ADR-0073 a DataLayer is always some specific actor's own, and a received-
    side use case is by construction invoked with the receiving actor's store
    (CM-01-001).

    This replaces an ``or "unknown"`` fabrication that predated per-actor
    storage.  A synthetic identity used to be merely a mislabelled log line
    over a shared pool; now ``actor_id`` *selects the store*, so inventing one
    silently routes every read and write into an empty scratch store and the
    work is lost without an error (ARCH-15-001).

    Raises:
        VultronValidationError: If neither source yields an identity, since
            there is then no defensible answer to "whose replica is this?".
    """
    if receiving_actor_id:
        return receiving_actor_id
    own_actor_id = getattr(dl, "actor_id", None)
    if isinstance(own_actor_id, str) and own_actor_id:
        return own_actor_id
    raise VultronValidationError(
        "cannot resolve the receiving actor: the request carries no"
        " receiving_actor_id and the DataLayer reports no actor of its own,"
        " so there is no store this message could be applied to (CM-01-001)"
    )


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

    An object carrying an id but **no ``type_``** is a *reference*, not something
    that can be stored: ``type_`` is what selects the storage table, so
    ``Record.from_obj`` refuses it outright.  The extractor produces exactly such
    a stub — ``VultronObject(id_=…, type_=None)`` — when an inbound activity names
    its object by bare URI, or by an object with no type.  That stub is load
    bearing: ``event.object_id`` is *derived* from ``object_``, so it is how the id
    survives at all; it simply is not a storable record.

    Storing it was attempted anyway, which aborted the enclosing BT
    (``CreateReportReceivedBT`` among them).  Such a reference is skipped here with
    a warning naming it as one, because there is nothing to store — this is the
    "Bare Object URI" case the Actor Knowledge Model describes, where the sender
    should have inlined the object and the recipient legitimately has no copy.

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
    if obj is None:
        logger.warning("no %s object for event '%s'", label, activity_id)
        return
    if getattr(obj, "type_", None) is None:
        logger.warning(
            "%s '%s' arrived as a bare reference with no type (activity '%s'):"
            " the sender named it by URI instead of inlining it, so there is no"
            " object to store — recording nothing (Actor Knowledge Model)",
            label,
            id_key,
            activity_id,
        )
        return
    dl.create(obj)
    logger.info("Stored %s '%s'", label, id_key)


def resolve_case(case_id: str, dl: CasePersistence):
    """Resolve a VulnerabilityCase by ID; raise domain error if absent or wrong
    type.

    This neutral helper is importable from any layer without triggering the
    ``triggers`` package ``__init__`` (which would cause circular imports when
    called from the BT nodes layer).
    """
    case_raw = dl.read_case(case_id)
    if case_raw is None:
        raise VultronNotFoundError("VulnerabilityCase", case_id)
    return case_raw


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
    # Canonical reader rather than an isinstance-guarded ``RM.START`` fallback:
    # substituting the initial state for an unreadable one is the #2264 defect,
    # and ``participant`` is an already-validated core CaseParticipant here, so
    # its latest status always carries a usable ``rm`` dimension (issue #2232).
    return participant_status_rm_state(statuses[-1])


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

    *actor_id* is retained for call-site readability and logging symmetry only;
    *dl* is already that actor's store, so it does not select the queue.  The
    former ``hasattr(dl, "outbox_list_for_actor")`` branch is gone: both arms
    now resolve to the same call (ADR-0073).

    Args:
        actor_id: The actor whose outbox is being queried. Not used to select
            the queue — *dl* determines that.
        dl: That actor's DataLayer.

    Returns:
        Set of activity IDs queued for delivery.
    """
    del actor_id  # documented above: *dl* selects the queue
    return set(dl.outbox_list())


def add_activity_to_outbox(
    actor_id: str, activity_id: str, dl: CaseOutboxPersistence
) -> None:
    """Append an activity ID to an actor's outbox and queue it for delivery.

    Appends to *dl*'s own outbox.  This previously used
    ``record_outbox_item(actor_id, …)`` to enqueue against *actor_id*
    explicitly, bypassing any actor-scope on *dl* — necessary when *dl* could
    be a shared, unscoped instance.  Under ADR-0073 it cannot be.

    Args:
        actor_id: The actor whose outbox receives the activity. Used only for
            the debug log; *dl* determines the queue.
        activity_id: The ID of the activity to queue for delivery.
        dl: The DataLayer to use for persistence.
    """
    dl.outbox_append(activity_id)
    logger.debug(
        "Queued activity '%s' in delivery queue for actor '%s'",
        _log_label(activity_id),
        _log_label(actor_id),
    )
