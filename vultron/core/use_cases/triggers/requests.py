"""Domain request models for trigger use cases.

These are core-layer domain models (no HTTP imports) that carry all parameters
needed by a trigger use case, including ``actor_id``.  Adapter shims in
``vultron/api/v2/backend/trigger_services/`` translate HTTP request bodies
into these models by adding ``actor_id`` from the URL path.

The hierarchy follows a single-base-class pattern: ``TriggerRequest`` holds all
optional fields as a superset.  Intermediate classes ``OfferTriggerRequest`` and
``CaseTriggerRequest`` narrow the base by requiring their respective identifier
field.  Leaf request classes subclass one of these intermediaries and only add
fields (or override optionals to required) where the specific use case demands it.
"""

import re
from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, field_validator
from pydantic.functional_validators import AfterValidator

from vultron.core.models.base import NonEmptyString

_URI_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+\-.]*:[^\s]")


def _valid_uri(v: str) -> str:
    if not _URI_SCHEME_RE.match(v):
        raise ValueError("must be a URI (e.g. urn:uuid:... or https://...)")
    return v


CaseIdString = Annotated[NonEmptyString, AfterValidator(_valid_uri)]


class TriggerRequest(BaseModel):
    """Base class for all trigger use-case request models.

    Declares every field that any trigger request may carry, all optional
    except ``actor_id``.  Concrete subclasses narrow the contract by making
    specific fields required or by adding use-case-specific constraints.
    """

    model_config = ConfigDict(extra="ignore")

    actor_id: NonEmptyString
    offer_id: NonEmptyString | None = None
    case_id: NonEmptyString | None = None
    note: NonEmptyString | None = None
    end_time: datetime | None = None
    proposal_id: NonEmptyString | None = None


class OfferTriggerRequest(TriggerRequest):
    """Trigger request that requires an ``offer_id``."""

    offer_id: NonEmptyString


class CaseTriggerRequest(TriggerRequest):
    """Trigger request that requires a ``case_id`` in URI form."""

    case_id: CaseIdString


class ValidateReportTriggerRequest(OfferTriggerRequest):
    pass


class InvalidateReportTriggerRequest(OfferTriggerRequest):
    pass


class RejectReportTriggerRequest(OfferTriggerRequest):
    """Requires ``offer_id``; ``note`` is strongly encouraged but coerced to
    ``None`` (not rejected) when the caller supplies an empty string, since
    the HTTP adapter already logs a warning in that case."""

    note: NonEmptyString | None = None


class CloseReportTriggerRequest(OfferTriggerRequest):
    pass


class EngageCaseTriggerRequest(CaseTriggerRequest):
    pass


class DeferCaseTriggerRequest(CaseTriggerRequest):
    pass


class ProposeEmbargoTriggerRequest(CaseTriggerRequest):
    end_time: datetime

    @field_validator("end_time")
    @classmethod
    def end_time_must_be_tz_aware_and_future(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("end_time must be timezone-aware")
        if v <= datetime.now(tz=timezone.utc):
            raise ValueError("end_time must be in the future")
        return v


class EvaluateEmbargoTriggerRequest(CaseTriggerRequest):
    pass


class TerminateEmbargoTriggerRequest(CaseTriggerRequest):
    pass
