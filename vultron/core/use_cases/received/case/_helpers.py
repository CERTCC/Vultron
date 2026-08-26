"""Use cases for vulnerability case activities."""

import logging
from typing import Any

from pydantic import ValidationError

from vultron.core.behaviors.case.nodes.participant.common import (  # noqa: F401
    _ensure_reporter_participant,
    _upgrade_participant_to_accepted,
)
from vultron.core.behaviors.case.update_support import (
    find_excluded_actor_ids,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.participant_status import (
    participant_status_rm_state,
)
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.states.rm import RM, is_monotonic_rm_forward
from vultron.errors import VultronValidationError

logger = logging.getLogger(__name__)


def _normalize_participant_refs(case_obj: Any) -> list[str]:
    """Return ``case_participants`` as a list of string IDs.

    After :func:`_store_embedded_participants` has projected and persisted each
    inline participant as a standalone DataLayer record, callers should persist
    the case with ``case_participants`` replaced by the returned string-ID list
    so the stored row is free of inline sub-objects (#2233).

    Does **not** mutate *case_obj*; callers use ``model_copy`` to build the
    object to persist (CM-27-001 — direct field assignment to shape-dual
    collections is not permitted).

    Safe to call on both core and wire case objects — uses ``getattr`` to
    access ``case_participants`` without typing the parameter.  Returns an
    empty list when ``case_participants`` is absent or empty.
    """
    participants = getattr(case_obj, "case_participants", None) or []
    result: list[str] = []
    for ref in participants:
        if isinstance(ref, str):
            result.append(ref)
        else:
            pid = getattr(ref, "id_", None)
            if pid is not None:
                result.append(str(pid))
    return result


def _find_report_case_link(
    creator_id: str, dl: CasePersistence
) -> VultronReportCaseLink | None:
    """Return a pending ReportCaseLink expecting a bootstrap from *creator_id*.

    Scans all ``ReportCaseLink`` records and returns the first that has
    ``trusted_case_creator_id == creator_id`` and ``case_id is None``
    (i.e. awaiting bootstrap).  Using the sender identity rather than the
    case's vulnerability_reports list makes the lookup independent of whether
    the case snapshot embeds the report.
    """
    for obj in dl.list_objects("ReportCaseLink"):
        if isinstance(obj, VultronReportCaseLink):
            if (
                obj.trusted_case_creator_id == creator_id
                and obj.case_id is None
            ):
                return obj
    return None


def _check_participant_embargo_acceptance(
    case: VulnerabilityCase, dl: CasePersistence
) -> set[str]:
    """Check which participants have not accepted the active embargo.

    Returns a set of actor IDs whose case updates should be withheld per
    CM-10-004 (participants that have not accepted the active embargo).
    """
    return find_excluded_actor_ids(case, dl)


def _store_embedded_embargo(
    case_obj: VulnerabilityCase, dl: CasePersistence, case_id: str
) -> None:
    """Store the ``EmbargoEvent`` a received case carried inline, if any.

    Delegates to the BT-node helper of the same name so there is one
    implementation; this wrapper exists so the received-side use cases can reach
    it alongside :func:`_store_embedded_participants` rather than importing from
    a behaviours module.

    The sender carries the embargo rather than referencing it because a receiver
    cannot dereference a URI it does not hold (AKM-03-001) — see
    ``_case_for_wire``. Storing it is what makes this actor's own
    ``case.active_embargo`` resolve.
    """
    from vultron.core.behaviors.case.nodes.announce import (
        _store_embedded_embargo as _store,
    )

    _store(case_obj, dl)
    logger.debug(
        "_store_embedded_embargo: checked inline embargo for case '%s'",
        case_id,
    )


def _store_embedded_participants(
    case_obj: VulnerabilityCase, dl: CasePersistence, case_id: str
) -> None:
    """Persist embedded participant objects from a case snapshot.

    When a bootstrapped or announced ``VulnerabilityCase`` carries fully
    materialised participant objects (not just ID strings), each is stored
    as an independent DataLayer record.  This ensures BT nodes such as
    ``CheckParticipantExists`` (#561) and ``AppendParticipantStatusNode``
    (#562, #566) can retrieve them by their UUID.

    Called from:
    - ``CreateCaseReceivedUseCase._handle_bootstrap`` (Create path, CBT-05-005)
    - ``AnnounceVulnerabilityCaseReceivedUseCase.execute`` (Announce path, #566)

    Idempotent: ``dl.save()`` upserts so repeated calls are safe.

    Each embedded participant is projected to the canonical core shape first
    (see :func:`_project_to_core_participant`) — a received snapshot arrives in
    the wire shape, and both the regression check below and every later reader
    of the stored row require the core shape (issue #2232).

    A received snapshot is a remote point-in-time view, so it must never
    regress local RM progress.  Bootstrap and Announce activities are built
    before delivery and may arrive after the receiver has already advanced a
    participant locally; blindly upserting would roll that participant back
    (e.g. RECEIVED → START), after which the legitimate next transition is
    rejected as invalid by the RM state machine.  Participants whose stored
    RM state is already at or beyond the snapshot's are therefore left alone.

    Args:
        case_obj: The bootstrapped or announced case domain object.
        dl: DataLayer to persist participants into.
        case_id: ID of the case (for log context).
    """
    participants = getattr(case_obj, "case_participants", []) or []
    for participant_ref in participants:
        if isinstance(participant_ref, str):
            continue
        pid = getattr(participant_ref, "id_", None)
        if pid is None:
            continue
        participant = _project_to_core_participant(participant_ref, pid)
        if participant is None:
            continue
        if _would_regress_participant(participant, dl, pid, case_id):
            continue
        dl.save(participant)
        logger.debug(
            "store_embedded_participants: stored participant '%s'"
            " for case '%s' (CBT-05-005, #566)",
            pid,
            case_id,
        )


def _project_to_core_participant(
    participant_ref: object, pid: str
) -> CaseParticipant | None:
    """Return *participant_ref* as a canonical core participant, or ``None``.

    This is the wire→core ingress boundary for embedded participants.  A
    received ``VulnerabilityCase`` snapshot is deserialised from AS2, so its
    ``case_participants`` are wire objects (``as_CaseParticipant``) carrying
    wire-shaped statuses with a flat ``rm_state`` — legitimate inbound data, not
    a corrupt row.  Every core-side reader below this point (the RM comparison
    in :func:`_would_regress_participant`, and anything that later reads the
    stored row) requires the canonical nested ``rm: RmDimension`` shape, so the
    projection has to happen here rather than being discovered downstream
    (issue #2232).

    Projecting at ingress rather than only at persistence also means the row
    that lands in the DataLayer is core-shaped, which is what makes
    ``dl.read()`` return a core object per DL-05-001.

    ``None`` means *this participant cannot be stored* and the caller must skip
    it.  A projection failure is logged at ERROR: core types are stricter than
    wire types, so it means the sender's snapshot was never valid domain data.
    Skipping one unprojectable participant is deliberately preferred over
    letting the exception abort the whole received-case behavior tree — a single
    malformed embedded participant must not cost the receiver the entire case
    (and, because the HTTP inbox re-queues on exception, must not turn the
    activity into an undrainable poison message).

    Args:
        participant_ref: An embedded participant object from the snapshot,
            either core-shaped already or a wire projection exposing
            ``to_core()``.
        pid: The participant's ID, for log context.

    Returns:
        A core :class:`CaseParticipant` (possibly a role subclass), or ``None``
        when the object cannot be represented in the canonical core shape.
    """
    if isinstance(participant_ref, CaseParticipant):
        return participant_ref
    to_core = getattr(participant_ref, "to_core", None)
    if to_core is None:
        logger.error(
            "participant '%s' cannot be projected to the canonical core"
            " shape and will be skipped: a"
            " %s exposes no to_core() projection, so it cannot be stored in"
            " the canonical core shape (issue #2232).",
            pid,
            type(participant_ref).__name__,
        )
        return None
    try:
        projected = to_core()
    except (ValidationError, VultronValidationError, ValueError, TypeError):
        logger.error(
            "participant '%s' cannot be projected to the canonical core shape"
            " and will be skipped: its %s snapshot failed core validation"
            " (issue #2232).",
            pid,
            type(participant_ref).__name__,
            exc_info=True,
        )
        return None
    if not isinstance(projected, CaseParticipant):
        logger.error(
            "participant '%s' cannot be projected to the canonical core shape"
            " and will be skipped: %s.to_core() returned a %s, not a core"
            " CaseParticipant (issue #2232).",
            pid,
            type(participant_ref).__name__,
            type(projected).__name__,
        )
        return None
    return projected


def _participant_rm_state(participant: object) -> RM | None:
    """Return the latest RM state recorded on *participant*, if any.

    ``None`` means *no status has been recorded yet* — a legitimate state that
    callers must handle.  It does **not** mean "the status was unreadable":
    a status that exists but exposes no usable ``rm`` dimension raises, because
    that is a shape mismatch rather than an absence (issue #2232, ARCH-15).

    Raises:
        VultronValidationError: when the latest status is not core-shaped.
    """
    statuses = getattr(participant, "participant_statuses", None) or []
    if not statuses:
        return None
    return participant_status_rm_state(statuses[-1])


def _would_regress_participant(
    incoming: CaseParticipant, dl: CasePersistence, pid: str, case_id: str
) -> bool:
    """Return ``True`` when saving *incoming* would roll back local RM state.

    Only the RM dimension is compared: it is the dimension whose state machine
    rejects backward transitions outright, so a regression there is what
    actually breaks subsequent protocol progress.

    Both sides are read through the canonical RM reader, so both must be
    core-shaped.  *incoming* is projected by the caller; the stored side is
    projected here because a legacy wire-shaped row can still be returned by
    ``dl.read()`` via the DL-05-004 escape list.  When the stored side cannot be
    read, ``False`` is returned: an incoming canonical snapshot overwriting an
    unreadable row is an improvement, not a regression.
    """
    stored = dl.read(pid)
    if stored is None:
        return False
    existing = _project_to_core_participant(stored, pid)
    if existing is None:
        return False

    existing_rm = _participant_rm_state(existing)
    incoming_rm = _participant_rm_state(incoming)
    if existing_rm is None or incoming_rm is None:
        return False
    if existing_rm == incoming_rm:
        return False
    if is_monotonic_rm_forward(existing_rm, incoming_rm):
        return False

    logger.info(
        "store_embedded_participants: keeping local participant '%s' at RM.%s"
        " for case '%s' — incoming snapshot is behind at RM.%s",
        pid,
        existing_rm,
        case_id,
        incoming_rm,
    )
    return True
