#!/usr/bin/env python

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

"""Shared helpers for participant BT nodes."""

import logging
from typing import TYPE_CHECKING, Any, cast

from vultron.core.models.enums import VultronObjectType
from vultron.core.models.dimensions import (
    PecDimension,
    RmDimension,
    VfdDimension,
)
from vultron.core.models.participant_status import (
    ParticipantStatus,
    coerce_cvd_roles,
    coerce_em_consent_state,
    participant_status_rm_state,
    participant_status_vfd_state,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.vultron_types import VultronParticipant
from vultron.core.ports.case_persistence import (
    CaseOutboxPersistence,
    CasePersistence,
)
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.states.cs import CS_vfd
from vultron.core.states.rm import RM, is_rm_at_least
from vultron.enums.roles import CVDRole
from vultron.core.models._helpers import (
    _as_id,
    _report_phase_status_id,
    report_phase_context,
)

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort


def _create_and_attach_participant(
    dl: CasePersistence,
    participant: VultronParticipant,
    case_id: str,
    actor_id_for_index: str,
    node_logger: logging.Logger,
) -> VulnerabilityCase | None:
    """
    Create participant if needed and attach it to the case (unsaved return).

    The caller is responsible for calling ``dl.save(case)`` after any further
    case updates are applied.
    """
    if dl.read(participant.id_) is None:
        dl.create(participant)
        node_logger.info(
            "Created CaseParticipant '%s' for actor '%s'",
            participant.id_,
            participant.attributed_to,
        )
    else:
        node_logger.debug(
            "CaseParticipant %s already exists — skipping creation",
            participant.id_,
        )

    stored_case = dl.read(case_id)
    if not isinstance(stored_case, VulnerabilityCase):
        node_logger.error("Case %s not found in DataLayer", case_id)
        return None

    existing_participant_id = stored_case.actor_participant_index.get(
        actor_id_for_index
    )
    if existing_participant_id is not None:
        existing_participant = dl.read(existing_participant_id)
        if isinstance(existing_participant, CaseParticipant):
            stored_case.add_participant(existing_participant)
            node_logger.debug(
                "Participant already registered for actor '%s' in case '%s'",
                actor_id_for_index,
                case_id,
            )
            return stored_case

    stored_case.add_participant(participant)

    node_logger.info(
        "CaseParticipant '%s' attached to case '%s'",
        participant.id_,
        stored_case.id_,
    )
    return stored_case


def _get_or_create_accepted_status(
    dl: CasePersistence,
    actor_id: str,
    report_id: str | None,
    node_name: str,
    node_logger: logging.Logger,
    cvd_role: list[CVDRole],
    em_consent_state: PEC | None,
) -> ParticipantStatus | None:
    if report_id is None:
        return None

    # CLP-07-007: context must use the case URI once a case exists.  Single
    # canonical copy of that selection lives in models/_helpers (ARCH-15-004).
    context = report_phase_context(dl, report_id)

    accepted_status_id = _report_phase_status_id(
        actor_id,
        report_id,
        RM.ACCEPTED.value,
    )
    existing = dl.read(accepted_status_id)
    if isinstance(existing, ParticipantStatus):
        should_update_role = existing.cvd_role != cvd_role
        should_backfill_consent = (
            existing.consent.state if existing.consent is not None else None
        ) is None and em_consent_state is not None
        # AC-3: backfill context if it still holds the report URI.
        should_backfill_context = (
            existing.context == report_id and context != report_id
        )
        if (
            should_update_role
            or should_backfill_consent
            or should_backfill_context
        ):
            existing.cvd_role = cvd_role
            if should_backfill_consent and em_consent_state is not None:
                existing.consent = PecDimension(state=em_consent_state)
            if should_backfill_context:
                existing.context = context
            dl.save(existing)
        # Construct a fresh core ParticipantStatus for callers that require
        # the core type (e.g. CaseParticipant.participant_statuses).  The
        # DataLayer vocabulary registry may return the wire-layer subclass;
        # we normalise here so downstream code never sees a wire-layer type.
        return ParticipantStatus(
            id_=existing.id_,
            context=existing.context,
            rm=RmDimension(state=existing.rm.state),
            vfd=VfdDimension(state=existing.vfd.state),
            attributed_to=getattr(existing, "attributed_to", actor_id),
            cvd_role=existing.cvd_role,
            consent=(
                PecDimension(state=existing.consent.state)
                if existing.consent is not None
                else None
            ),
        )

    node_logger.info(
        "%s: Creating fresh RM.ACCEPTED status for actor '%s' "
        "(report-phase status not pre-created)",
        node_name,
        actor_id,
    )
    accepted_status = ParticipantStatus(
        id_=accepted_status_id,
        context=context,
        rm=RmDimension(state=RM.ACCEPTED),
        attributed_to=actor_id,
        cvd_role=cvd_role,
        consent=(
            PecDimension(state=em_consent_state)
            if em_consent_state is not None
            else None
        ),
    )
    try:
        dl.create(accepted_status)
    except ValueError:
        pass
    return accepted_status


def resolve_participant_state_from_dl(
    dl: CasePersistence,
    participant_id: str,
) -> tuple[RM, CS_vfd]:
    """Return (current_rm, current_vfd) from the participant's latest status.

    ``(RM.START, CS_vfd.vfd)`` is returned only when the participant genuinely
    has no recorded status — never as a fallback for a status that could not be
    read.  Substituting an initial state on an unreadable status silently reset
    a participant's ladder (#2264, a symptom of #2232); a shape mismatch now
    raises instead (ARCH-15-001, ARCH-15-002).  Both dimensions go through
    their canonical reader: leaving VFD on the old ``hasattr``/``isinstance``
    degrade would have kept the identical defect alive one dimension over.

    Raises:
        VultronValidationError: when the latest status is not core-shaped.
    """
    participant_obj = dl.read(participant_id)
    if participant_obj is not None and hasattr(
        participant_obj, "participant_statuses"
    ):
        statuses = getattr(participant_obj, "participant_statuses")
        if statuses:
            latest = statuses[-1]
            return (
                participant_status_rm_state(latest),
                participant_status_vfd_state(latest),
            )
    return RM.START, CS_vfd.vfd


def resolve_case_manager_id(
    case: VulnerabilityCase,
    dl: CasePersistence,
) -> str | None:
    """Return the actor ID of the CASE_MANAGER participant, or None.

    Checks ``actor_participant_index`` first (fast path), then falls back to
    iterating ``case_participants`` for bootstrap-phase inline objects.

    Behaviors-layer twin of
    ``vultron.core.use_cases._helpers._resolve_case_manager_id``; kept here so
    BT nodes (e.g. ``EmitCFActivity``, ``EmitCDActivity``) resolve the Case
    Actor without a behaviors→use_cases import (BTND-04-003).
    """
    for p_id in case.actor_participant_index.values():
        p = dl.read(p_id)
        if not isinstance(p, CaseParticipant):
            continue
        if CVDRole.CASE_MANAGER in p.roles:
            return _as_id(getattr(p, "attributed_to", None))

    indexed_ids = set(case.actor_participant_index.values())
    for p_ref in case.case_participants:
        if not isinstance(p_ref, str):
            if (
                isinstance(p_ref, CaseParticipant)
                and CVDRole.CASE_MANAGER in p_ref.roles
            ):
                return _as_id(getattr(p_ref, "attributed_to", None))
            continue
        if p_ref in indexed_ids:
            continue
        p = dl.read(p_ref)
        if not isinstance(p, CaseParticipant):
            continue
        if CVDRole.CASE_MANAGER in p.roles:
            return _as_id(getattr(p, "attributed_to", None))
    return None


def _queue_participant_add_notification(
    dl: CasePersistence,
    node_name: str,
    node_logger: logging.Logger,
    sender_actor_id: str,
    participant_actor_id: str,
    participant_id: str,
    case_id: str,
    trigger_activity: "TriggerActivityPort | None" = None,
) -> bool:
    stored_participant = dl.read(participant_id)
    if (
        getattr(stored_participant, "type_", None)
        != VultronObjectType.CASE_PARTICIPANT
    ):
        node_logger.error(
            "%s: Could not resolve stored CaseParticipant '%s'",
            node_name,
            participant_id,
        )
        return False

    if trigger_activity is None:
        node_logger.error(
            "%s: trigger_activity_factory not available for participant"
            " add notification",
            node_name,
        )
        return False

    add_notification_id = trigger_activity.add_participant_to_case(
        participant_id=participant_id,
        case_id=case_id,
        actor=sender_actor_id,
        to=[participant_actor_id],
    )
    cast(CaseOutboxPersistence, dl).outbox_append(add_notification_id)
    node_logger.info(
        "Queued Add(CaseParticipant '%s' for actor '%s' to case '%s') "
        "activity '%s' to actor '%s' outbox",
        participant_id,
        participant_actor_id,
        case_id,
        add_notification_id,
        sender_actor_id,
    )
    return True


def _ensure_reporter_participant(
    dl: CasePersistence,
    link: VultronReportCaseLink,
    case_obj: VulnerabilityCase,
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
    logger = logging.getLogger(__name__)
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
        latest_rm = statuses[-1].rm.state if statuses else RM.START
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
        rm=RmDimension(state=RM.ACCEPTED),
        context=case_id,
        attributed_to=reporter_actor_id,
        consent=PecDimension(state=PEC.NO_EMBARGO),
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
    latest_rm: RM,
) -> None:
    """Upgrade an existing participant record from below RM.ACCEPTED to RM.ACCEPTED.

    Saves the new status as an independent DataLayer record, then reads it back
    via the DataLayer so the stored canonical record is used (ADR-0034:
    dl.read() returns core-typed objects for ParticipantStatus).
    """
    logger = logging.getLogger(__name__)
    _coerced_consent = coerce_em_consent_state(
        getattr(existing, "embargo_consent_state", None)
    )
    upgrade_status = ParticipantStatus(
        rm=RmDimension(state=RM.ACCEPTED),
        context=case_id,
        attributed_to=reporter_actor_id,
        consent=(
            PecDimension(state=_coerced_consent)
            if _coerced_consent is not None
            else None
        ),
        cvd_role=coerce_cvd_roles(getattr(existing, "roles", [])),
    )
    try:
        dl.create(upgrade_status)
    except ValueError:
        dl.save(upgrade_status)
    wire_status = dl.read(upgrade_status.id_)
    if isinstance(existing, CaseParticipant):
        existing.add_participant_status(
            wire_status
            if isinstance(wire_status, ParticipantStatus)
            else upgrade_status
        )
    dl.save(existing)
    logger.info(
        "ensure_reporter_participant: upgraded participant '%s' from "
        "%s to RM.ACCEPTED (#589, #624)",
        participant_id,
        latest_rm,
    )
