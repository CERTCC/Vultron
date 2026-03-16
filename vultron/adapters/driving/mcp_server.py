"""
MCP server driving adapter.

Exposes Vultron trigger use cases as MCP (Model Context Protocol) tool
functions.  Each tool function:

1. Accepts structured parameters
2. Gets a DataLayer instance
3. Instantiates the appropriate UseCase class with the DataLayer
4. Calls ``execute()`` with a domain request model
5. Returns the result

Full MCP registration is Priority 1000 (Agentic AI readiness).
The functions here are ready to be registered once the MCP SDK is available.

See ``plan/PRIORITIES.md`` PRIORITY 1000 for the design rationale.
"""

import logging
from typing import Any

from vultron.adapters.driven.datalayer_tinydb import get_datalayer
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
    TerminateEmbargoTriggerRequest,
    ValidateReportTriggerRequest,
)

logger = logging.getLogger(__name__)


def mcp_validate_report(
    actor_id: str, offer_id: str, note: str | None = None
) -> dict[str, Any]:
    """MCP tool: trigger report validation for an actor."""
    dl = get_datalayer()
    request = ValidateReportTriggerRequest(
        actor_id=actor_id, offer_id=offer_id, note=note
    )
    return SvcValidateReportUseCase(dl).execute(request)


def mcp_invalidate_report(
    actor_id: str, offer_id: str, note: str | None = None
) -> dict[str, Any]:
    """MCP tool: tentatively reject a report offer for an actor."""
    dl = get_datalayer()
    request = InvalidateReportTriggerRequest(
        actor_id=actor_id, offer_id=offer_id, note=note
    )
    return SvcInvalidateReportUseCase(dl).execute(request)


def mcp_reject_report(
    actor_id: str, offer_id: str, note: str
) -> dict[str, Any]:
    """MCP tool: hard-reject a report offer for an actor."""
    dl = get_datalayer()
    request = RejectReportTriggerRequest(
        actor_id=actor_id, offer_id=offer_id, note=note
    )
    return SvcRejectReportUseCase(dl).execute(request)


def mcp_close_report(
    actor_id: str, offer_id: str, note: str | None = None
) -> dict[str, Any]:
    """MCP tool: close a report via the RM lifecycle for an actor."""
    dl = get_datalayer()
    request = CloseReportTriggerRequest(
        actor_id=actor_id, offer_id=offer_id, note=note
    )
    return SvcCloseReportUseCase(dl).execute(request)


def mcp_engage_case(actor_id: str, case_id: str) -> dict[str, Any]:
    """MCP tool: engage a case for an actor."""
    dl = get_datalayer()
    request = EngageCaseTriggerRequest(actor_id=actor_id, case_id=case_id)
    return SvcEngageCaseUseCase(dl).execute(request)


def mcp_defer_case(actor_id: str, case_id: str) -> dict[str, Any]:
    """MCP tool: defer a case for an actor."""
    dl = get_datalayer()
    request = DeferCaseTriggerRequest(actor_id=actor_id, case_id=case_id)
    return SvcDeferCaseUseCase(dl).execute(request)


def mcp_propose_embargo(
    actor_id: str,
    case_id: str,
    note: str | None = None,
    end_time: str | None = None,
) -> dict[str, Any]:
    """MCP tool: propose an embargo on a case for an actor.

    ``end_time`` is an optional ISO 8601 datetime string.
    """
    from datetime import datetime

    parsed_end_time = datetime.fromisoformat(end_time) if end_time else None
    dl = get_datalayer()
    request = ProposeEmbargoTriggerRequest(
        actor_id=actor_id,
        case_id=case_id,
        note=note,
        end_time=parsed_end_time,
    )
    return SvcProposeEmbargoUseCase(dl).execute(request)


def mcp_evaluate_embargo(
    actor_id: str, case_id: str, proposal_id: str | None = None
) -> dict[str, Any]:
    """MCP tool: accept an embargo proposal for an actor."""
    dl = get_datalayer()
    request = EvaluateEmbargoTriggerRequest(
        actor_id=actor_id, case_id=case_id, proposal_id=proposal_id
    )
    return SvcEvaluateEmbargoUseCase(dl).execute(request)


def mcp_terminate_embargo(actor_id: str, case_id: str) -> dict[str, Any]:
    """MCP tool: terminate the active embargo on a case for an actor."""
    dl = get_datalayer()
    request = TerminateEmbargoTriggerRequest(
        actor_id=actor_id, case_id=case_id
    )
    return SvcTerminateEmbargoUseCase(dl).execute(request)


MCP_TOOLS = [
    mcp_validate_report,
    mcp_invalidate_report,
    mcp_reject_report,
    mcp_close_report,
    mcp_engage_case,
    mcp_defer_case,
    mcp_propose_embargo,
    mcp_evaluate_embargo,
    mcp_terminate_embargo,
]
