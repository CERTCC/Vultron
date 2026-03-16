"""Domain request models for trigger use cases.

These are core-layer domain models (no HTTP imports) that carry all parameters
needed by a trigger use case, including ``actor_id``.  Adapter shims in
``vultron/api/v2/backend/trigger_services/`` translate HTTP request bodies
into these models by adding ``actor_id`` from the URL path.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from vultron.core.models.events.base import NonEmptyString


class TriggerRequest(BaseModel):
    """Base class for all trigger use-case request models.

    Provides shared ``model_config`` (extras ignored) and ``actor_id``
    so concrete subclasses only need to declare their own additional fields.
    """

    model_config = ConfigDict(extra="ignore")

    actor_id: NonEmptyString


class ValidateReportTriggerRequest(TriggerRequest):
    offer_id: str
    note: str | None = None


class InvalidateReportTriggerRequest(TriggerRequest):
    offer_id: str
    note: str | None = None


class RejectReportTriggerRequest(TriggerRequest):
    offer_id: str
    note: str


class CloseReportTriggerRequest(TriggerRequest):
    offer_id: str
    note: str | None = None


class EngageCaseTriggerRequest(TriggerRequest):
    case_id: str


class DeferCaseTriggerRequest(TriggerRequest):
    case_id: str


class ProposeEmbargoTriggerRequest(TriggerRequest):
    case_id: str
    note: str | None = None
    end_time: datetime | None = None


class EvaluateEmbargoTriggerRequest(TriggerRequest):
    case_id: str
    proposal_id: str | None = None


class TerminateEmbargoTriggerRequest(TriggerRequest):
    case_id: str
