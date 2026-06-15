"""Use cases for vulnerability case activities."""

import logging
from typing import Any

from vultron.core.behaviors.case.update_support import (
    find_excluded_actor_ids,
)
from vultron.core.models.participant import VultronParticipant
from vultron.core.models.participant_status import (
    ParticipantStatus,
    coerce_cvd_roles,
    coerce_em_consent_state,
)
from vultron.core.models.protocols import CaseModel
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.states.rm import RM, is_rm_at_least
from vultron.core.states.roles import CVDRole
from vultron.core.use_cases._helpers import _as_id

logger = logging.getLogger(__name__)


def _find_case_actor_id_from_participants(
    case_obj: CaseModel, dl: CasePersistence
) -> str | None:
    """Find the CaseActor ID from the CASE_MANAGER participant in the case.

    Uses duck-typing on ``case_roles`` to avoid importing wire-layer types.
    Returns the ``attributed_to`` URI of the first participant holding
    ``CVDRole.CASE_MANAGER`` (CBT-01-003).

    Handles both inline objects and ID-only references stored in
    ``case_participants``.
    """
    for participant_ref in case_obj.case_participants:
        # Try inline object first (participant embedded in snapshot)
        if not isinstance(participant_ref, str):
            roles = getattr(participant_ref, "case_roles", [])
            if CVDRole.CASE_MANAGER in roles:
                attributed = getattr(participant_ref, "attributed_to", None)
                if attributed:
                    return str(attributed)
            continue

        # ID-only reference — look up from DataLayer
        participant = dl.read(participant_ref)
        if participant is None:
            continue
        roles = getattr(participant, "case_roles", [])
        if CVDRole.CASE_MANAGER in roles:
            attributed = getattr(participant, "attributed_to", None)
            if attributed:
                return str(attributed)
    return None


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
    case: CaseModel, dl: CasePersistence
) -> set[str]:
    """Check which participants have not accepted the active embargo.

    Returns a set of actor IDs whose case updates should be withheld per
    CM-10-004 (participants that have not accepted the active embargo).
    """
    return find_excluded_actor_ids(case, dl)


def _store_embedded_participants(
    case_obj: CaseModel, dl: CasePersistence, case_id: str
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
        dl.save(participant_ref)
        logger.info(
            "store_embedded_participants: stored participant '%s'"
            " for case '%s' (CBT-05-005, #566)",
            pid,
            case_id,
        )


def _ensure_reporter_participant(
    dl: CasePersistence,
    link: VultronReportCaseLink,
    case_obj: CaseModel,
    case_id: str,
) -> None:
    """Ensure the reporter's participant record is at RM.ACCEPTED (#589, #624).

    When ``Create(VulnerabilityCase)`` carries participant IDs as bare
    strings, ``_store_embedded_participants`` skips them.  Without an
    explicit participant record in the DataLayer,
    ``SvcAddParticipantStatusUseCase._resolve_current_participant_state``
    falls back to ``RM.START``, causing the Vendor's Case Actor to reject the
    subsequent ``Add(ParticipantStatus)`` as a backwards transition.

    The reporter submitted the original report, which implies they have
    already ``RM.ACCEPTED`` from their own perspective.  The reporter is
    identified as ``attributed_to`` of the ``Offer(Report)`` activity
    (``report.attributed_to``).  Their ``START→RECEIVED→VALID→ACCEPTED`` arc
    is hidden from the protocol — their first observable action already
    implies ``RM.ACCEPTED`` (#624).

    This function:

    * Creates the participant record at ``RM.ACCEPTED`` if it is absent.
    * Upgrades an existing participant from any state below ``RM.ACCEPTED``
      (e.g. ``RM.START`` seeded by the wire-layer default) to ``RM.ACCEPTED``.
    * No-ops if the participant is already at or beyond ``RM.ACCEPTED``.

    This invariant applies **only** to the reporter/finder.  All other
    participants enter through a visible protocol interaction and their RM
    lifecycle proceeds normally from ``RM.RECEIVED``.

    Args:
        dl: The reporter's local DataLayer.
        link: The ``VultronReportCaseLink`` associating the report to this
            case bootstrap.
        case_obj: The bootstrapped ``VulnerabilityCase`` snapshot.
        case_id: ID of the case (for log context and status context).
    """
    report = dl.read(link.report_id)
    if report is None:
        logger.warning(
            "ensure_reporter_participant: report '%s' not found "
            "— cannot seed reporter participant (#589)",
            link.report_id,
        )
        return

    reporter_actor_id = _as_id(getattr(report, "attributed_to", None))
    if not reporter_actor_id:
        logger.warning(
            "ensure_reporter_participant: report '%s' has no attributed_to "
            "— cannot seed reporter participant (#589)",
            link.report_id,
        )
        return

    index = getattr(case_obj, "actor_participant_index", {}) or {}
    participant_id = index.get(reporter_actor_id)
    if not participant_id:
        logger.warning(
            "ensure_reporter_participant: reporter '%s' not in "
            "actor_participant_index for case '%s' — skipping (#589)",
            reporter_actor_id,
            case_id,
        )
        return

    existing = dl.read(participant_id)
    if existing is not None:
        statuses = getattr(existing, "participant_statuses", []) or []
        latest_rm = statuses[-1].rm_state if statuses else RM.START
        if is_rm_at_least(latest_rm, RM.ACCEPTED):
            logger.debug(
                "ensure_reporter_participant: participant '%s' already "
                "≥ RM.ACCEPTED — skipping (#589, #624)",
                participant_id,
            )
            return
        _upgrade_participant_to_accepted(
            dl, existing, participant_id, case_id, reporter_actor_id, latest_rm
        )
        return

    status = ParticipantStatus(
        rm_state=RM.ACCEPTED,
        context=case_id,
        attributed_to=reporter_actor_id,
        em_consent_state=PEC.NO_EMBARGO,
        cvd_role=[CVDRole.REPORTER],
    )
    participant = VultronParticipant(
        id_=participant_id,
        attributed_to=reporter_actor_id,
        context=case_id,
        participant_statuses=[status],
    )
    try:
        dl.create(participant)
        logger.info(
            "ensure_reporter_participant: created participant '%s' for "
            "reporter '%s' at RM.ACCEPTED (#589)",
            participant_id,
            reporter_actor_id,
        )
    except ValueError:
        logger.debug(
            "ensure_reporter_participant: participant '%s' was concurrently "
            "created — idempotent (#589)",
            participant_id,
        )


def _upgrade_participant_to_accepted(
    dl: CasePersistence,
    existing: Any,
    participant_id: str,
    case_id: str,
    reporter_actor_id: str,
    latest_rm: "RM",
) -> None:
    """Upgrade an existing participant record from below RM.ACCEPTED to RM.ACCEPTED.

    Saves the new status as an independent DataLayer record, then reads it back
    via the vocabulary registry so the serialised type matches what the
    participant container expects.  This avoids wire/domain type mismatches when
    appending to ``CaseParticipant.participant_statuses``.
    """
    upgrade_status = ParticipantStatus(
        rm_state=RM.ACCEPTED,
        context=case_id,
        attributed_to=reporter_actor_id,
        em_consent_state=coerce_em_consent_state(
            getattr(existing, "embargo_consent_state", None)
        ),
        cvd_role=coerce_cvd_roles(getattr(existing, "case_roles", [])),
    )
    try:
        dl.create(upgrade_status)
    except ValueError:
        dl.save(upgrade_status)
    wire_status = dl.read(upgrade_status.id_)
    participant_statuses = getattr(existing, "participant_statuses", None)
    if participant_statuses is not None:
        participant_statuses.append(
            wire_status if wire_status is not None else upgrade_status
        )
    dl.save(existing)
    logger.info(
        "ensure_reporter_participant: upgraded participant '%s' from "
        "%s to RM.ACCEPTED (#589, #624)",
        participant_id,
        latest_rm,
    )
