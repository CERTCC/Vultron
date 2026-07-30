"""Use cases for vulnerability case activities."""

import logging

from vultron.core.behaviors.case.nodes.participant.common import (  # noqa: F401
    _ensure_reporter_participant,
    _upgrade_participant_to_accepted,
)
from vultron.core.behaviors.case.update_support import (
    find_excluded_actor_ids,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.states.rm import RM, is_monotonic_rm_forward

logger = logging.getLogger(__name__)


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
        if _would_regress_participant(participant_ref, dl, pid, case_id):
            continue
        dl.save(participant_ref)
        logger.info(
            "store_embedded_participants: stored participant '%s'"
            " for case '%s' (CBT-05-005, #566)",
            pid,
            case_id,
        )


def _participant_rm_state(participant: object) -> RM | None:
    """Return the latest RM state recorded on *participant*, if any."""
    statuses = getattr(participant, "participant_statuses", None) or []
    if not statuses:
        return None
    rm = getattr(statuses[-1], "rm", None)
    state = getattr(rm, "state", None)
    return state if isinstance(state, RM) else None


def _would_regress_participant(
    incoming: object, dl: CasePersistence, pid: str, case_id: str
) -> bool:
    """Return ``True`` when saving *incoming* would roll back local RM state.

    Only the RM dimension is compared: it is the dimension whose state machine
    rejects backward transitions outright, so a regression there is what
    actually breaks subsequent protocol progress.
    """
    existing = dl.read(pid)
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
