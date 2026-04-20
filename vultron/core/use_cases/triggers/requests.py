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

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, field_validator

from vultron.core.models.base import NonEmptyString, UriString


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

    offer_id: NonEmptyString  # pyright: ignore[reportGeneralTypeIssues]


class CaseTriggerRequest(TriggerRequest):
    """Trigger request that requires a ``case_id`` in URI form."""

    case_id: UriString  # pyright: ignore[reportGeneralTypeIssues]


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


class SubmitReportTriggerRequest(TriggerRequest):
    """Trigger request for a finder to create and offer a vulnerability report.

    Creates a ``VulnerabilityReport`` in the actor's DataLayer and queues an
    ``RmSubmitReportActivity`` offer to the specified recipient.
    """

    report_name: NonEmptyString
    report_content: NonEmptyString
    recipient_id: UriString


class EngageCaseTriggerRequest(CaseTriggerRequest):
    pass


class DeferCaseTriggerRequest(CaseTriggerRequest):
    pass


class ProposeEmbargoTriggerRequest(CaseTriggerRequest):
    end_time: datetime  # pyright: ignore[reportGeneralTypeIssues]

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


class AddNoteToCaseTriggerRequest(CaseTriggerRequest):
    """Trigger request for adding a note to a case."""

    note_name: NonEmptyString
    note_content: NonEmptyString
    in_reply_to: NonEmptyString | None = None


class CreateCaseTriggerRequest(TriggerRequest):
    """Trigger request to create a new VulnerabilityCase.

    The actor creates a local case and emits a CreateCaseActivity queued in
    the outbox for delivery to the CaseActor (or other recipients).
    """

    name: NonEmptyString
    content: NonEmptyString
    report_id: NonEmptyString | None = None


class AddReportToCaseTriggerRequest(CaseTriggerRequest):
    """Trigger request to link a report to an existing case."""

    report_id: NonEmptyString


class SuggestActorToCaseTriggerRequest(CaseTriggerRequest):
    """Trigger request for an actor to recommend another actor to a case.

    Emits a RecommendActorActivity addressed to the case owner (typically
    the CaseActor), which then autonomously invites the suggested actor.
    """

    suggested_actor_id: NonEmptyString


class AcceptCaseInviteTriggerRequest(TriggerRequest):
    """Trigger request for an invitee to accept a case invitation.

    Emits an RmAcceptInviteToCaseActivity queued in the actor's outbox for
    delivery to the case owner.
    """

    invite_id: NonEmptyString
