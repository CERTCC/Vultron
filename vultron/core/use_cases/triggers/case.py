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

"""
Class-based use cases for case-level trigger behaviors.

No HTTP framework imports permitted here.
"""

import logging
from typing import TYPE_CHECKING, Any, cast

from vultron.core.models.case import VultronCase
from vultron.core.models.protocols import (
    is_participant_model,
    ParticipantStatusModel,
)
from vultron.core.states.rm import RM
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.use_cases._helpers import update_participant_rm_state
from vultron.core.use_cases._helpers import case_addressees
from vultron.core.use_cases.triggers._helpers import (
    add_activity_to_outbox,
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    AddObjectToCaseTriggerRequest,
    AddParticipantStatusTriggerRequest,
    AddReportToCaseTriggerRequest,
    CreateCaseTriggerRequest,
    DeferCaseTriggerRequest,
    EngageCaseTriggerRequest,
)
from vultron.errors import VultronNotFoundError, VultronValidationError

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


class SvcEngageCaseUseCase:
    """Engage a case (RM → ACCEPTED)."""

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: EngageCaseTriggerRequest,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: EngageCaseTriggerRequest = request
        self._trigger_activity = trigger_activity

    def execute(self) -> dict:
        request = self._request
        actor_id = request.actor_id
        case_id = request.case_id
        dl = self._dl

        actor = resolve_actor(actor_id, dl)
        actor_id = actor.id_

        case = resolve_case(case_id, dl)

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcEngageCaseUseCase requires a TriggerActivityPort"
            )

        activity_id, activity_dict = self._trigger_activity.engage_case(
            case_id=case_id,
            actor=actor_id,
            to=case_addressees(case, actor_id) or None,
        )

        update_participant_rm_state(case.id_, actor_id, RM.ACCEPTED, dl)

        add_activity_to_outbox(actor_id, activity_id, dl)

        logger.info(
            "Actor '%s' engaged case '%s' (RM → ACCEPTED)",
            actor_id,
            case.id_,
        )

        return {"activity": activity_dict}


class SvcDeferCaseUseCase:
    """Defer a case (RM → DEFERRED)."""

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: DeferCaseTriggerRequest,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: DeferCaseTriggerRequest = request
        self._trigger_activity = trigger_activity

    def execute(self) -> dict:
        request = self._request
        actor_id = request.actor_id
        case_id = request.case_id
        dl = self._dl

        actor = resolve_actor(actor_id, dl)
        actor_id = actor.id_

        case = resolve_case(case_id, dl)

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcDeferCaseUseCase requires a TriggerActivityPort"
            )

        activity_id, activity_dict = self._trigger_activity.defer_case(
            case_id=case_id,
            actor=actor_id,
            to=case_addressees(case, actor_id) or None,
        )

        update_participant_rm_state(case.id_, actor_id, RM.DEFERRED, dl)

        add_activity_to_outbox(actor_id, activity_id, dl)

        logger.info(
            "Actor '%s' deferred case '%s' (RM → DEFERRED)",
            actor_id,
            case.id_,
        )

        return {"activity": activity_dict}


class SvcCreateCaseUseCase:
    """Create a new VulnerabilityCase and emit a CreateCaseActivity.

    The actor creates a local case and queues the activity for delivery to
    the CaseActor inbox.  An optional report_id links an existing
    VulnerabilityReport to the new case.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: CreateCaseTriggerRequest,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._trigger_activity = trigger_activity

    def execute(self) -> dict[str, Any]:
        actor_id = self._request.actor_id
        actor = resolve_actor(actor_id, self._dl)
        actor_id = actor.id_

        case = VultronCase(
            name=self._request.name,
            content=self._request.content,
            attributed_to=actor.id_,
        )

        if self._request.report_id is not None:
            raw = self._dl.read(self._request.report_id)
            if raw is None:
                raise VultronNotFoundError(
                    "VulnerabilityReport", self._request.report_id
                )
            if getattr(raw, "type_", "") != "VulnerabilityReport":
                raise VultronValidationError(
                    f"'{self._request.report_id}' is not a VulnerabilityReport"
                )
            raw_id = getattr(raw, "id_", None) or self._request.report_id
            case.vulnerability_reports.append(raw_id)

        self._dl.create(case)

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcCreateCaseUseCase requires a TriggerActivityPort"
            )

        activity_id, activity_dict = self._trigger_activity.create_case(
            case_id=case.id_,
            actor=actor.id_,
        )

        add_activity_to_outbox(actor_id, activity_id, self._dl)

        logger.info(
            "Actor '%s' created case '%s' (CreateCaseActivity '%s')",
            actor_id,
            case.id_,
            activity_id,
        )

        return {"activity": activity_dict}


class SvcAddObjectToCaseUseCase:
    """Add any existing AS2 object to a case (general-purpose).

    Reads the object by ``object_id`` from the datalayer, creates a generic
    ``Add(object, target=case)`` activity, and queues it in the actor's
    outbox.  The object must already exist; this use case does not create it.

    Type-specific wrappers (e.g., ``SvcAddReportToCaseUseCase``) delegate
    here after performing their own validation (TRIG-10-002).

    Implements: TRIG-10-001.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AddObjectToCaseTriggerRequest,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._trigger_activity = trigger_activity

    def execute(self) -> dict[str, Any]:
        actor_id = self._request.actor_id
        case_id = self._request.case_id
        object_id = self._request.object_id
        dl = self._dl

        actor = resolve_actor(actor_id, dl)
        actor_id = actor.id_

        resolve_case(case_id, dl)

        raw = dl.read(object_id)
        if raw is None:
            raise VultronNotFoundError("AS2Object", object_id)

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcAddObjectToCaseUseCase requires a TriggerActivityPort"
            )

        activity_id, activity_dict = self._trigger_activity.add_object_to_case(
            actor=actor_id,
            object_id=object_id,
            case_id=case_id,
        )

        add_activity_to_outbox(actor_id, activity_id, dl)

        logger.info(
            "Actor '%s' added object '%s' to case '%s'",
            actor_id,
            object_id,
            case_id,
        )

        return {"activity": activity_dict}


class SvcAddReportToCaseUseCase:
    """Link a VulnerabilityReport to an existing case.

    Validates that the referenced object is a ``VulnerabilityReport``, then
    delegates to :class:`SvcAddObjectToCaseUseCase` (TRIG-10-002).
    Emits an ``Add(VulnerabilityReport, target=VulnerabilityCase)`` activity
    queued in the actor's outbox.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AddReportToCaseTriggerRequest,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._trigger_activity = trigger_activity

    def execute(self) -> dict[str, Any]:
        actor_id = self._request.actor_id
        dl = self._dl

        raw = dl.read(self._request.report_id)
        if raw is None:
            raise VultronNotFoundError(
                "VulnerabilityReport", self._request.report_id
            )
        if getattr(raw, "type_", "") != "VulnerabilityReport":
            raise VultronValidationError(
                f"'{self._request.report_id}' is not a VulnerabilityReport"
            )

        inner = SvcAddObjectToCaseUseCase(
            dl,
            AddObjectToCaseTriggerRequest(
                actor_id=actor_id,
                case_id=self._request.case_id,
                object_id=self._request.report_id,
            ),
            trigger_activity=self._trigger_activity,
        )
        return inner.execute()


class SvcAddParticipantStatusUseCase:
    """Self-report actor RM/VFD/PXA state to the Case Manager.

    Creates a VultronParticipantStatus object, saves it, then emits an
    Add(ParticipantStatus, target=CaseParticipant) activity addressed to the
    Case Manager (DEMOMA-07-001).
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AddParticipantStatusTriggerRequest,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._trigger_activity = trigger_activity

    def execute(self) -> dict[str, Any]:
        from vultron.core.models.participant_status import (
            VultronParticipantStatus,
        )
        from vultron.core.models.case_status import VultronCaseStatus
        from vultron.core.states.rm import RM
        from vultron.core.states.cs import CS_vfd

        request = self._request
        actor_id = request.actor_id
        case_id = request.case_id
        dl = self._dl

        actor = resolve_actor(actor_id, dl)
        actor_id = actor.id_

        case = resolve_case(case_id, dl)

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcAddParticipantStatusUseCase requires a TriggerActivityPort"
            )

        # Look up the actor's participant record ID
        participant_id = case.actor_participant_index.get(actor_id)
        if participant_id is None:
            raise VultronNotFoundError(
                "CaseParticipant",
                f"actor '{actor_id}' not in case '{case_id}'",
            )

        # Build embedded CaseStatus if a participant-perspective pxa_state was
        # provided; inherit em_state from the current case-level status.
        case_status: VultronCaseStatus | None = None
        if request.pxa_state is not None:
            current_em = getattr(
                getattr(case, "current_status", None), "em_state", None
            )
            from vultron.core.states.em import EM

            case_status = VultronCaseStatus(
                context=case_id,
                attributed_to=actor_id,
                em_state=current_em if current_em is not None else EM.NONE,
                pxa_state=request.pxa_state,
            )

        # Build and persist the status object
        status = VultronParticipantStatus(
            context=case_id,
            attributed_to=actor_id,
            rm_state=(
                request.rm_state if request.rm_state is not None else RM.START
            ),
            vfd_state=(
                request.vfd_state
                if request.vfd_state is not None
                else CS_vfd.vfd
            ),
            case_status=case_status,
        )
        try:
            dl.create(status)
        except ValueError:
            dl.save(status)

        # Find Case Manager ID to address activity
        from vultron.core.states.roles import CVDRole

        case_manager_id: str | None = None
        for p_id in case.actor_participant_index.values():
            p = dl.read(p_id)
            roles = getattr(p, "case_roles", [])
            if CVDRole.CASE_MANAGER in roles:
                case_manager_id = getattr(p, "attributed_to", None)
                if case_manager_id:
                    case_manager_id = str(case_manager_id)
                break

        if case_manager_id is None:
            raise VultronNotFoundError(
                "CaseParticipant",
                f"no CASE_MANAGER found in case '{case_id}'"
                " — cannot send status update",
            )

        activity_id = (
            self._trigger_activity.add_participant_status_to_participant(
                status_id=status.id_,
                participant_id=participant_id,
                actor=actor_id,
                to=[case_manager_id],
            )
        )

        add_activity_to_outbox(actor_id, activity_id, dl)

        # Immediately reflect the new status on the local participant record so
        # callers can observe it without waiting for the Case Manager to
        # acknowledge via inbox (DEMOMA-07-001, local-consistency property).
        # AddParticipantStatusToParticipantReceivedUseCase has a duplicate-ID
        # guard that prevents double-append when the message is later processed.
        self._update_local_participant(participant_id, status, dl)

        # If this status signals public disclosure by the CASE_OWNER, initiate
        # embargo teardown directly.  In co-located deployments the Case Actor
        # inbox may be unreachable (URN-based ID), so we apply the same logic
        # that AddParticipantStatusToParticipantReceivedUseCase
        # ._check_public_disclosure would execute (DEMOMA-07-003 step 4).
        self._maybe_terminate_embargo(
            case_status, participant_id, case_manager_id, case_id, dl
        )

        logger.info(
            "Actor '%s' reported status to participant '%s' in case '%s'",
            actor_id,
            participant_id,
            case_id,
        )

        return {"activity_id": activity_id, "status_id": status.id_}

    def _update_local_participant(
        self,
        participant_id: str,
        status: Any,
        dl: CaseOutboxPersistence,
    ) -> None:
        """Append *status* to the local participant record if not already present."""
        p = dl.read(participant_id)
        if not is_participant_model(p):
            return
        existing_ids = {
            getattr(s, "id_", None) or str(s) for s in p.participant_statuses
        }
        if status.id_ not in existing_ids:
            # Re-read the status so it arrives as the same layer type that
            # the participant model expects (e.g. the wire ParticipantStatus
            # with its VultronObjectType enum type_).  Appending the freshly
            # created core VultronParticipantStatus directly would cause a
            # Pydantic serialization mismatch on model_dump.
            wire_status = dl.read(status.id_) or status
            p.participant_statuses.append(
                cast(ParticipantStatusModel, wire_status)
            )
            dl.save(p)
            logger.debug(
                "Local participant '%s' updated with new status '%s'",
                participant_id,
                status.id_,
            )

    def _maybe_terminate_embargo(
        self,
        case_status: Any,
        participant_id: str,
        case_manager_id: str,
        case_id: str,
        dl: CaseOutboxPersistence,
    ) -> None:
        """Trigger embargo teardown when the CASE_OWNER signals public awareness."""
        if case_status is None:
            return

        from vultron.core.states.cs import CS_pxa
        from vultron.core.states.roles import CVDRole

        pxa = getattr(case_status, "pxa_state", None)
        if pxa is None:
            return
        public_aware = pxa in (
            CS_pxa.Pxa,
            CS_pxa.PxA,
            CS_pxa.PXa,
            CS_pxa.PXA,
        )
        if not public_aware:
            return

        sender = dl.read(participant_id)
        roles = getattr(sender, "case_roles", [])
        if CVDRole.CASE_OWNER not in roles:
            return

        logger.info(
            "CASE_OWNER signalled public awareness in case '%s'; "
            "initiating embargo teardown as Case Manager '%s'",
            case_id,
            case_manager_id,
        )
        try:
            from vultron.core.use_cases.triggers.embargo import (
                SvcTerminateEmbargoUseCase,
            )
            from vultron.core.use_cases.triggers.requests import (
                TerminateEmbargoTriggerRequest,
            )

            req = TerminateEmbargoTriggerRequest(
                actor_id=case_manager_id,
                case_id=case_id,
            )
            SvcTerminateEmbargoUseCase(
                dl,
                req,
                trigger_activity=self._trigger_activity,
            ).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Embargo teardown failed for case '%s': %s",
                case_id,
                exc,
            )
