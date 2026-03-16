"""Domain request models for trigger use cases.

These are core-layer domain models (no HTTP imports) that carry all parameters
needed by a trigger use case, including ``actor_id``.  Adapter shims in
``vultron/api/v2/backend/trigger_services/`` translate HTTP request bodies
into these models by adding ``actor_id`` from the URL path.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ValidateReportTriggerRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    actor_id: str
    offer_id: str
    note: str | None = None


class InvalidateReportTriggerRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    actor_id: str
    offer_id: str
    note: str | None = None


class RejectReportTriggerRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    actor_id: str
    offer_id: str
    note: str


class CloseReportTriggerRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    actor_id: str
    offer_id: str
    note: str | None = None


class EngageCaseTriggerRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    actor_id: str
    case_id: str


class DeferCaseTriggerRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    actor_id: str
    case_id: str


class ProposeEmbargoTriggerRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    actor_id: str
    case_id: str
    note: str | None = None
    end_time: datetime | None = None


class EvaluateEmbargoTriggerRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    actor_id: str
    case_id: str
    proposal_id: str | None = None


class TerminateEmbargoTriggerRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    actor_id: str
    case_id: str
