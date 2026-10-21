"""Shared helper utilities for use-case implementations.

Module-level helpers used across multiple use-case modules.
All helpers are private to the use-cases package (prefix ``_``).
"""

import hashlib
import logging

from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.participant_status import (
    participant_status_rm_state,
)
from vultron.core.participants.authority import (  # noqa: F401  (re-export)
    case_manager_address as _find_case_actor_id,
    resolve_case_manager_id,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.states.rm import RM
from vultron.errors import VultronNotFoundError, VultronValidationError

logger = logging.getLogger(__name__)

# The held-activity readers live in ``core/services`` so BT nodes may use them
# too (BTND-04-003).  Re-exported here for every existing importer.
from vultron.core.services.received_activity import (  # noqa: E402,F401
    holds_activity,
    holds_received_activity,
    read_held_activity,
    read_received_activity,
)


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
) -> bool:
    """Append an activity ID to an actor's outbox and queue it for delivery.

    An id already pending is not queued again (OX-06-002, ADR-0119).

    Appends to *dl*'s own outbox.  This previously used
    ``record_outbox_item(actor_id, …)`` to enqueue against *actor_id*
    explicitly, bypassing any actor-scope on *dl* — necessary when *dl* could
    be a shared, unscoped instance.  Under ADR-0073 it cannot be.

    Args:
        actor_id: The actor whose outbox receives the activity. Used only for
            the debug log; *dl* determines the queue.
        activity_id: The ID of the activity to queue for delivery.
        dl: The DataLayer to use for persistence.

    Returns:
        ``True`` when the activity was queued, ``False`` when it was already
        pending.
    """
    queued = dl.outbox_append(activity_id)
    logger.debug(
        "%s activity '%s' in delivery queue for actor '%s'",
        "Queued" if queued else "Already pending:",
        _log_label(activity_id),
        _log_label(actor_id),
    )
    return queued
