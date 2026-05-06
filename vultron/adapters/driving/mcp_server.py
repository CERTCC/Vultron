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

from vultron.adapters.driven.datalayer import get_datalayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.use_cases.triggers.case import (
    SvcDeferCaseUseCase,
    SvcEngageCaseUseCase,
)
from vultron.core.use_cases.triggers.embargo import (
    SvcAcceptEmbargoUseCase,
    SvcProposeEmbargoRevisionUseCase,
    SvcProposeEmbargoUseCase,
    SvcRejectEmbargoUseCase,
    SvcTerminateEmbargoUseCase,
)
from vultron.core.use_cases.triggers.report import (
    SvcCloseReportUseCase,
    SvcInvalidateReportUseCase,
    SvcRejectReportUseCase,
    SvcValidateReportUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptEmbargoTriggerRequest,
    CloseReportTriggerRequest,
    DeferCaseTriggerRequest,
    EngageCaseTriggerRequest,
    InvalidateReportTriggerRequest,
    ProposeEmbargoRevisionTriggerRequest,
    ProposeEmbargoTriggerRequest,
    RejectEmbargoTriggerRequest,
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
    return SvcValidateReportUseCase(dl, request).execute()


def mcp_invalidate_report(
    actor_id: str, offer_id: str, note: str | None = None
) -> dict[str, Any]:
    """MCP tool: tentatively reject a report offer for an actor."""
    dl = get_datalayer()
    trigger_activity = TriggerActivityAdapter(dl)
    request = InvalidateReportTriggerRequest(
        actor_id=actor_id, offer_id=offer_id, note=note
    )
    return SvcInvalidateReportUseCase(dl, request, trigger_activity).execute()


def mcp_reject_report(
    actor_id: str, offer_id: str, note: str
) -> dict[str, Any]:
    """MCP tool: hard-reject a report offer for an actor."""
    dl = get_datalayer()
    trigger_activity = TriggerActivityAdapter(dl)
    request = RejectReportTriggerRequest(
        actor_id=actor_id, offer_id=offer_id, note=note
    )
    return SvcRejectReportUseCase(dl, request, trigger_activity).execute()


def mcp_close_report(
    actor_id: str, offer_id: str, note: str | None = None
) -> dict[str, Any]:
    """MCP tool: close a report via the RM lifecycle for an actor."""
    dl = get_datalayer()
    trigger_activity = TriggerActivityAdapter(dl)
    request = CloseReportTriggerRequest(
        actor_id=actor_id, offer_id=offer_id, note=note
    )
    return SvcCloseReportUseCase(dl, request, trigger_activity).execute()


def mcp_engage_case(actor_id: str, case_id: str) -> dict[str, Any]:
    """MCP tool: engage a case for an actor."""
    dl = get_datalayer()
    trigger_activity = TriggerActivityAdapter(dl)
    request = EngageCaseTriggerRequest(actor_id=actor_id, case_id=case_id)
    return SvcEngageCaseUseCase(dl, request, trigger_activity).execute()


def mcp_defer_case(actor_id: str, case_id: str) -> dict[str, Any]:
    """MCP tool: defer a case for an actor."""
    dl = get_datalayer()
    trigger_activity = TriggerActivityAdapter(dl)
    request = DeferCaseTriggerRequest(actor_id=actor_id, case_id=case_id)
    return SvcDeferCaseUseCase(dl, request, trigger_activity).execute()


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
    if parsed_end_time is None:
        raise ValueError("end_time is required for propose_embargo")
    dl = get_datalayer()
    trigger_activity = TriggerActivityAdapter(dl)
    request = ProposeEmbargoTriggerRequest(
        actor_id=actor_id,
        case_id=case_id,
        note=note,
        end_time=parsed_end_time,
    )
    return SvcProposeEmbargoUseCase(dl, request, trigger_activity).execute()


def mcp_accept_embargo(
    actor_id: str, case_id: str, proposal_id: str | None = None
) -> dict[str, Any]:
    """MCP tool: accept an embargo proposal for an actor."""
    dl = get_datalayer()
    trigger_activity = TriggerActivityAdapter(dl)
    request = AcceptEmbargoTriggerRequest(
        actor_id=actor_id, case_id=case_id, proposal_id=proposal_id
    )
    return SvcAcceptEmbargoUseCase(dl, request, trigger_activity).execute()


def mcp_reject_embargo(
    actor_id: str, case_id: str, proposal_id: str | None = None
) -> dict[str, Any]:
    """MCP tool: reject an embargo proposal for an actor."""
    dl = get_datalayer()
    trigger_activity = TriggerActivityAdapter(dl)
    request = RejectEmbargoTriggerRequest(
        actor_id=actor_id, case_id=case_id, proposal_id=proposal_id
    )
    return SvcRejectEmbargoUseCase(dl, request, trigger_activity).execute()


def mcp_propose_embargo_revision(
    actor_id: str,
    case_id: str,
    end_time: str,
    note: str | None = None,
) -> dict[str, Any]:
    """MCP tool: propose a revision to an active embargo for an actor.

    ``end_time`` is a required ISO 8601 datetime string.
    Only valid when EM state is ACTIVE or REVISE.
    """
    from datetime import datetime

    parsed_end_time = datetime.fromisoformat(end_time)
    dl = get_datalayer()
    trigger_activity = TriggerActivityAdapter(dl)
    request = ProposeEmbargoRevisionTriggerRequest(
        actor_id=actor_id,
        case_id=case_id,
        note=note,
        end_time=parsed_end_time,
    )
    return SvcProposeEmbargoRevisionUseCase(
        dl, request, trigger_activity
    ).execute()


def mcp_terminate_embargo(actor_id: str, case_id: str) -> dict[str, Any]:
    """MCP tool: terminate the active embargo on a case for an actor."""
    dl = get_datalayer()
    trigger_activity = TriggerActivityAdapter(dl)
    request = TerminateEmbargoTriggerRequest(
        actor_id=actor_id, case_id=case_id
    )
    return SvcTerminateEmbargoUseCase(dl, request, trigger_activity).execute()


MCP_TOOLS = [
    mcp_validate_report,
    mcp_invalidate_report,
    mcp_reject_report,
    mcp_close_report,
    mcp_engage_case,
    mcp_defer_case,
    mcp_propose_embargo,
    mcp_accept_embargo,
    mcp_reject_embargo,
    mcp_propose_embargo_revision,
    mcp_terminate_embargo,
]
