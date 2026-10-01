#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University


"""Seed a participant case replica from a received case snapshot.

A ``VulnerabilityCase`` that arrives from its CASE_MANAGER — announced, created
by bootstrap, or carried on an engage/defer — is a remote point-in-time view.
Storing it on the receiver's replica (Case Replica Seeding) takes the same
three steps on every path:

- :func:`store_embedded_participants` persists each inline participant as its
  own record, without regressing local RM progress;
- :func:`normalize_participant_refs` gives the ID-only participant list the
  stored case row carries (#2233);
- :func:`link_report_case_links` points a pending ``ReportCaseLink`` at the
  announced case.

Both the received use cases and the announce seed BT node call these, so they
live here rather than in either layer (BT-22-005, BTND-04-004); a BT node
importing them from ``use_cases/`` would break BTND-04-003 and close an import
cycle.  Hold the carried embargo first —
:func:`~vultron.core.services.carried_embargo.store_carried_embargo`.
"""

import logging
from typing import Any

from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.participant_status import (
    participant_status_rm_state,
)
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.states.rm import RM, is_monotonic_rm_forward

logger = logging.getLogger(__name__)


def normalize_participant_refs(case_obj: Any) -> list[str]:
    """Return ``case_participants`` as a list of string IDs.

    After :func:`store_embedded_participants` has projected and persisted each
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


def store_embedded_participants(
    case_obj: VulnerabilityCase, dl: CasePersistence, case_id: str
) -> None:
    """Persist embedded participant objects from a case snapshot.

    When a bootstrapped or announced ``VulnerabilityCase`` carries fully
    materialised participant objects (not just ID strings), each is stored
    as an independent DataLayer record.  This ensures BT nodes such as
    ``CheckParticipantExists`` (#561) and ``AppendParticipantStatusNode``
    (#562, #566) can retrieve them by their UUID.

    Called from:
    - ``CreateCaseReceivedUseCase`` (Create/bootstrap path, CBT-05-005)
    - ``EngageCaseReceivedUseCase`` (Engage path, #573)
    - ``SeedAnnouncedCaseNode`` (Announce path, #566)

    Idempotent: ``dl.save()`` upserts so repeated calls are safe.

    Each embedded participant is checked to be a core :class:`CaseParticipant`
    first (see :func:`_project_to_core_participant`) — under ADR-0099 detail 3
    a received snapshot deserialises straight into core objects, and both the
    regression check below and every later reader of the stored row require
    that canonical shape (issue #2232).  Bare ID strings carry no ``id_`` and
    are skipped here; they are not participant records to store.

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


def link_report_case_links(dl: CasePersistence, case) -> None:
    """Attach any matching ``ReportCaseLink`` records to the announced case."""
    for report_ref in case.vulnerability_reports:
        report_id = _as_id(report_ref)
        if report_id is None:
            continue

        link = dl.read(VultronReportCaseLink.build_id(report_id))
        if not isinstance(link, VultronReportCaseLink):
            continue
        if link.case_id == case.id_:
            continue

        dl.save(link.model_copy(update={"case_id": case.id_}))
        logger.info(
            "AnnounceVulnerabilityCase: linked report '%s' to case '%s'",
            report_id,
            case.id_,
        )


def _project_to_core_participant(
    participant_ref: object, pid: str
) -> CaseParticipant | None:
    """Return *participant_ref* as a canonical core participant, or ``None``.

    This is the wire→core ingress boundary for embedded participants.  Under
    ADR-0099 detail 3 a received ``VulnerabilityCase`` snapshot deserialises
    its ``case_participants`` straight into core :class:`CaseParticipant`
    objects — ``as_CaseParticipant`` is an alias of that class — so a
    participant either *is* the canonical core object already or cannot be
    represented at all.  No projection capability is duck-typed on the object
    (ARCH-20-008); a snapshot that failed core validation never reaches this
    point, because ``extra="forbid"`` and the core validators refused it at
    parse (ARCH-12-003).

    Every core-side reader below this point (the RM comparison in
    :func:`_would_regress_participant`, and anything that later reads the
    stored row) requires the canonical nested ``rm: RmDimension`` shape, so
    the check happens here rather than being discovered downstream (issue
    #2232).  Storing the core object is also what makes ``dl.read()`` return a
    core object per DL-05-001.

    ``None`` means *this participant cannot be stored* and the caller must skip
    it.  The failure is logged at ERROR: a value that is not a core participant
    means the sender's snapshot was never valid domain data.  Skipping one
    such participant is deliberately preferred over letting an exception abort
    the whole received-case behavior tree — a single malformed embedded
    participant must not cost the receiver the entire case (and, because the
    HTTP inbox re-queues on exception, must not turn the activity into an
    undrainable poison message).

    Args:
        participant_ref: An embedded participant object from the snapshot.
        pid: The participant's ID, for log context.

    Returns:
        The core :class:`CaseParticipant` (possibly a role subclass), or
        ``None`` when the object is not one.
    """
    if isinstance(participant_ref, CaseParticipant):
        return participant_ref
    logger.error(
        "participant '%s' cannot be projected to the canonical core shape and"
        " will be skipped: a %s is not a core CaseParticipant, so it cannot be"
        " stored in the canonical core shape (issue #2232).",
        pid,
        type(participant_ref).__name__,
    )
    return None


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
