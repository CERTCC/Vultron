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
Trigger adapter functions for actor-initiated Vultron behaviors.

Each function builds a domain request model, instantiates the core use-case
class, and delegates to ``execute()``.  Domain exceptions are translated to
FastAPI ``HTTPException`` responses via ``domain_error_translation()``.

Domain logic must not be added here.  See
``vultron/core/use_cases/triggers/`` for implementation details.
"""

from datetime import datetime

from vultron.adapters.driving.fastapi.errors import domain_error_translation
from vultron.core.ports.datalayer import DataLayer
from vultron.core.use_cases.triggers.case import (
    SvcDeferCaseUseCase,
    SvcEngageCaseUseCase,
)
from vultron.core.use_cases.triggers.embargo import (
    SvcEvaluateEmbargoUseCase,
    SvcProposeEmbargoUseCase,
    SvcTerminateEmbargoUseCase,
)
from vultron.core.use_cases.triggers.report import (
    SvcCloseReportUseCase,
    SvcInvalidateReportUseCase,
    SvcRejectReportUseCase,
    SvcSubmitReportUseCase,
    SvcValidateReportUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    CloseReportTriggerRequest,
    DeferCaseTriggerRequest,
    EngageCaseTriggerRequest,
    EvaluateEmbargoTriggerRequest,
    InvalidateReportTriggerRequest,
    ProposeEmbargoTriggerRequest,
    RejectReportTriggerRequest,
    SubmitReportTriggerRequest,
    TerminateEmbargoTriggerRequest,
    ValidateReportTriggerRequest,
)


def validate_report_trigger(
    actor_id: str, offer_id: str, note: str | None, dl: DataLayer
) -> dict:
    with domain_error_translation():
        request = ValidateReportTriggerRequest(
            actor_id=actor_id, offer_id=offer_id, note=note
        )
        return SvcValidateReportUseCase(dl, request).execute()


def invalidate_report_trigger(
    actor_id: str, offer_id: str, note: str | None, dl: DataLayer
) -> dict:
    with domain_error_translation():
        request = InvalidateReportTriggerRequest(
            actor_id=actor_id, offer_id=offer_id, note=note
        )
        return SvcInvalidateReportUseCase(dl, request).execute()


def reject_report_trigger(
    actor_id: str, offer_id: str, note: str, dl: DataLayer
) -> dict:
    with domain_error_translation():
        request = RejectReportTriggerRequest(
            actor_id=actor_id, offer_id=offer_id, note=note or None
        )
        return SvcRejectReportUseCase(dl, request).execute()


def close_report_trigger(
    actor_id: str, offer_id: str, note: str | None, dl: DataLayer
) -> dict:
    with domain_error_translation():
        request = CloseReportTriggerRequest(
            actor_id=actor_id, offer_id=offer_id, note=note
        )
        return SvcCloseReportUseCase(dl, request).execute()


def engage_case_trigger(actor_id: str, case_id: str, dl: DataLayer) -> dict:
    with domain_error_translation():
        request = EngageCaseTriggerRequest(actor_id=actor_id, case_id=case_id)
        return SvcEngageCaseUseCase(dl, request).execute()


def defer_case_trigger(actor_id: str, case_id: str, dl: DataLayer) -> dict:
    with domain_error_translation():
        request = DeferCaseTriggerRequest(actor_id=actor_id, case_id=case_id)
        return SvcDeferCaseUseCase(dl, request).execute()


def propose_embargo_trigger(
    actor_id: str,
    case_id: str,
    note: str | None,
    end_time: datetime | None,
    dl: DataLayer,
) -> dict:
    with domain_error_translation():
        if end_time is None:
            raise ValueError("end_time is required for propose_embargo")
        request = ProposeEmbargoTriggerRequest(
            actor_id=actor_id, case_id=case_id, note=note, end_time=end_time
        )
        return SvcProposeEmbargoUseCase(dl, request).execute()


def evaluate_embargo_trigger(
    actor_id: str,
    case_id: str,
    proposal_id: str | None,
    dl: DataLayer,
) -> dict:
    with domain_error_translation():
        request = EvaluateEmbargoTriggerRequest(
            actor_id=actor_id, case_id=case_id, proposal_id=proposal_id
        )
        return SvcEvaluateEmbargoUseCase(dl, request).execute()


def terminate_embargo_trigger(
    actor_id: str, case_id: str, dl: DataLayer
) -> dict:
    with domain_error_translation():
        request = TerminateEmbargoTriggerRequest(
            actor_id=actor_id, case_id=case_id
        )
        return SvcTerminateEmbargoUseCase(dl, request).execute()


def submit_report_trigger(
    actor_id: str,
    report_name: str,
    report_content: str,
    recipient_id: str,
    dl: DataLayer,
) -> dict:
    with domain_error_translation():
        request = SubmitReportTriggerRequest(
            actor_id=actor_id,
            report_name=report_name,
            report_content=report_content,
            recipient_id=recipient_id,
        )
        return SvcSubmitReportUseCase(dl, request).execute()
