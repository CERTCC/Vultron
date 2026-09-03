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
from typing import TYPE_CHECKING, NamedTuple, cast

import py_trees.behaviour
from py_trees.common import Status

from vultron.core.models.enums import VultronObjectType
from vultron.core.models.dimensions import (
    DDimension,
    PecDimension,
    RmDimension,
    VfDimension,
)
from vultron.core.models.participant_status import (
    ParticipantStatus,
    participant_status_d_state,
    participant_status_rm_state,
    participant_status_vf_state,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.vultron_types import VultronParticipant
from vultron.core.ports.case_persistence import (
    CaseOutboxPersistence,
    CasePersistence,
)
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.states.cs import CS_d, CS_pxa, CS_vf
from vultron.core.states.participant_transitions import (
    participant_transition_violations,
)
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.errors import VultronValidationError
from vultron.core.models._helpers import (
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

    # Regime 1 (ADR-0087): module-level resolver (bare `dl`, not a node) —
    # a missing case is logged at ERROR and returned as None so the calling
    # node fails loudly. Conformance allowlist: module-resolver category.
    stored_case = dl.read_case(case_id)
    if stored_case is None:
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
            vf=(
                VfDimension(state=existing.vf.state)
                if existing.vf is not None
                else None
            ),
            d=(
                DDimension(state=existing.d.state)
                if existing.d is not None
                else None
            ),
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
) -> tuple[RM, CS_vf | None, CS_d | None]:
    """Return (current_rm, current_vf, current_d) from the participant's latest status.

    ``(RM.START, None, None)`` is returned only when the participant genuinely
    has no recorded status — never as a fallback for a status that could not be
    read.  A shape mismatch raises instead (ARCH-15-001, ARCH-15-002).

    ``current_vf`` is ``None`` for non-VENDOR participants; ``current_d`` is
    ``None`` for non-DEPLOYER participants.

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
                participant_status_vf_state(latest),
                participant_status_d_state(latest),
            )
    return RM.START, None, None


def resolve_participant_pxa_state(
    case: VulnerabilityCase,
    participant: object,
) -> CS_pxa:
    """Return the PXA state in force for *participant* before a new write.

    The participant's own latest ``ParticipantStatus.case_status.pxa`` is
    authoritative: the participant-status write path records PXA on the
    *participant* snapshot and does not append to ``case.case_statuses``, so
    ``case.current_status`` reports a stale ``pxa`` and makes every repeat write
    look like a fresh public-disclosure event (#2264).

    Falls back to the case-level PXA, then to ``CS_pxa.pxa``, when the
    participant has no PXA-bearing snapshot yet.  This is the single canonical
    copy of that baseline (ARCH-15-004): the trigger guard and the write node
    MUST agree on it or they validate against different current states.
    """
    statuses = getattr(participant, "participant_statuses", None) or []
    for status in reversed(statuses):
        pxa_state = getattr(
            getattr(getattr(status, "case_status", None), "pxa", None),
            "state",
            None,
        )
        if isinstance(pxa_state, CS_pxa):
            return pxa_state
    try:
        current_status = case.current_status
    except (AttributeError, ValueError):
        return CS_pxa.pxa
    case_pxa = getattr(getattr(current_status, "pxa", None), "state", None)
    return case_pxa if isinstance(case_pxa, CS_pxa) else CS_pxa.pxa


class ParticipantTransitionContext(NamedTuple):
    """The participant state a ``ParticipantStatus`` write is measured against.

    Resolved once per node tick by
    :func:`resolve_participant_transition_context` so that the trigger guard
    and the write node validate against identical inputs.
    """

    participant: object | None
    current_rm: RM
    current_vf: CS_vf | None
    current_d: CS_d | None
    current_pxa: CS_pxa
    actor_roles: list[CVDRole]


def resolve_participant_transition_context(
    dl: CasePersistence,
    case: VulnerabilityCase,
    participant_id: str,
) -> ParticipantTransitionContext:
    """Return the current state and roles for a participant-status write.

    ``current_vf`` / ``current_d`` are ``None`` when the participant has no
    vendor / deployer path at all (ADR-0075) — absence, not an initial state.

    Raises:
        VultronValidationError: when the latest status is not core-shaped
            (propagated from :func:`resolve_participant_state_from_dl`).
    """
    current_rm, current_vf, current_d = resolve_participant_state_from_dl(
        dl, participant_id
    )
    participant = dl.read(participant_id)
    return ParticipantTransitionContext(
        participant=participant,
        current_rm=current_rm,
        current_vf=current_vf,
        current_d=current_d,
        current_pxa=resolve_participant_pxa_state(case, participant),
        actor_roles=(
            list(participant.roles)
            if isinstance(participant, CaseParticipant)
            else []
        ),
    )


def resolve_transition_context_or_report(
    node: py_trees.behaviour.Behaviour,
    dl: CasePersistence,
    case: VulnerabilityCase,
    participant_id: str,
) -> "ParticipantTransitionContext | Status":
    """Resolve the transition context, or report a shape mismatch as FAILURE.

    ``resolve_participant_state_from_dl`` raises when the participant's latest
    status is not core-shaped (ARCH-15-001/002): that is a corrupt row, not an
    absence, and must not be degraded into an initial state (#2232, #2264).  A
    BT node cannot let the exception escape ``update()``, so this converts it to
    ``Status.FAILURE`` with a descriptive ``feedback_message`` once, for every
    node that validates such a write.
    """
    try:
        return resolve_participant_transition_context(dl, case, participant_id)
    except VultronValidationError as exc:
        node.feedback_message = (
            f"Participant '{participant_id}' status is not core-shaped:"
            f" {exc} (ARCH-15-001)"
        )
        node.logger.warning(f"{node.name}: {node.feedback_message}")
        return Status.FAILURE


def validate_participant_status_write(
    node: py_trees.behaviour.Behaviour,
    context: ParticipantTransitionContext,
    *,
    case_id: str,
    actor_id: str,
    rm_state: "RM | None",
    vf_state: "CS_vf | None",
    d_state: "CS_d | None",
    pxa_state: "CS_pxa | None",
    result_out: dict | None,
    validate_rm_transition: bool = True,
) -> "Status | None":
    """Validate a proposed ``ParticipantStatus`` write and report every failure.

    The single entry point every node that validates such a write goes through
    (BTND-10-002).  Delegates the rules to
    :func:`~vultron.core.states.participant_transitions\
    .participant_transition_violations` and, when any are violated, refuses the
    write as a unit while reporting the whole set (EH-07-001):

    * ``node.feedback_message`` renders every violation, so
      ``BTBridge.get_failure_reason`` carries them all (BT-13-001);
    * ``result_out["error"]`` carries them as structured data, which
      ``SvcBTTriggerBase.execute()`` re-raises and the FastAPI layer projects
      into the 422 ``details`` array (EH-05-002, EH-07-003).

    Args:
        validate_rm_transition: Passed through to the evaluator.  ``False`` only
            for the enumerated case-closure quarantine (``force_rm_state``);
            every other caller leaves the full rule set in force.

    Returns:
        ``Status.FAILURE`` when the write is refused, ``None`` when it is legal
        and the caller should proceed.
    """
    violations = participant_transition_violations(
        current_rm=context.current_rm,
        current_vf=context.current_vf,
        current_d=context.current_d,
        current_pxa=context.current_pxa,
        requested_rm=rm_state,
        requested_vf=vf_state,
        requested_d=d_state,
        requested_pxa=pxa_state,
        actor_roles=context.actor_roles,
        validate_rm_transition=validate_rm_transition,
    )
    if not violations:
        return None

    error = VultronValidationError(
        f"Refused ParticipantStatus write for actor '{actor_id}'"
        f" in case '{case_id}'",
        violations=violations,
    )
    node.feedback_message = str(error)
    node.logger.warning(f"{node.name}: {node.feedback_message}")
    if result_out is not None:
        result_out["error"] = error
    return Status.FAILURE


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
