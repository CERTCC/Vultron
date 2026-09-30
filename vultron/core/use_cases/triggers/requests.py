"""Domain request models for trigger use cases.

These are core-layer domain models (no HTTP imports) that carry every
parameter a trigger use case needs, including ``actor_id``.  Each one derives
from the verb's request *body* model in
:mod:`vultron.core.use_cases.triggers.request_bodies` — the class FastAPI
validates the HTTP body against, re-exported by
``vultron/adapters/driving/fastapi/trigger_models.py`` — and adds ``actor_id``
through :class:`TriggerRequest`.  The two families are therefore one
(ADR-0110): the body model owns the fields and their validators (the
``end_time`` rule is declared once, on ``ProposeEmbargoRequest``), and
``CaseTriggerRequest`` is defined once and re-exported here for its existing
importers.

``TriggerRequest`` is generic in the result type its verb's use case returns.
``ResultT_co`` is bound to :class:`TriggerResult` and covariant, so a single
``trigger(request: TriggerRequest[ResultT_co]) -> ResultT_co`` signature
resolves each verb's result subtype statically (UCORG-05-006 groundwork);
:func:`result_type_of` recovers the same binding at runtime.

``actor_id`` is the local actor initiating the action, injected by the
driving adapter from the URL path, never from the body (TRIG-06-001).
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from vultron.core.models.base import NonEmptyString, UriString
from vultron.core.models.use_case_result import (
    ActivityResult,
    CaseResult,
    NoteResult,
    OfferResult,
    RoleOfferResult,
    StatusResult,
    TriggerResult,
)
from vultron.core.states.cs import CS_d, CS_pxa, CS_vf
from vultron.core.states.rm import RM
from vultron.core.use_cases.triggers.request_bodies import (
    AcceptActorRecommendationRequest,
    AcceptCaseInviteRequest,
    AcceptCaseOwnershipTransferRequest,
    AcceptEmbargoRequest,
    AddNoteToCaseRequest,
    AddObjectToCaseRequest,
    AddReportToCaseRequest,
    CaseTriggerRequest,
    CloseCaseRequest,
    CloseReportRequest,
    CreateCaseRequest,
    InvalidateReportRequest,
    InviteActorToCaseRequest,
    OfferCaseOwnershipTransferRequest,
    OfferCaseParticipantRoleRequest,
    ProposeEmbargoRequest,
    ProposeEmbargoRevisionRequest,
    RejectCaseInviteRequest,
    RejectEmbargoRequest,
    ReportTriggerRequest,
    SubmitReportRequest,
    SuggestActorToCaseRequest,
    TerminateEmbargoRequest,
    ValidateReportRequest,
)

ResultT_co = TypeVar("ResultT_co", bound=TriggerResult, covariant=True)


class TriggerRequest(BaseModel, Generic[ResultT_co]):
    """Base of every trigger use-case request: ``actor_id`` plus a result type.

    Concrete requests bind ``ResultT_co`` to the :class:`TriggerResult`
    subtype their verb's use case returns and mix in the verb's body model,
    which carries every other field.  The type parameter is phantom — no field
    is typed with it — so it costs nothing at validation time and exists for
    the static binding between a request and its result.
    """

    model_config = ConfigDict(extra="ignore")

    actor_id: NonEmptyString


def result_type_of(
    request_cls: type[TriggerRequest[Any]],
) -> type[TriggerResult]:
    """Return the :class:`TriggerResult` subtype *request_cls* is bound to.

    Walks the MRO for the parametrised ``TriggerRequest[...]`` base pydantic
    recorded and returns its argument.  Raises ``TypeError`` for a request
    class that never bound one — every concrete request MUST.
    """
    for klass in request_cls.__mro__:
        metadata = getattr(klass, "__pydantic_generic_metadata__", None)
        if (
            metadata
            and metadata.get("origin") is TriggerRequest
            and metadata.get("args")
        ):
            bound = metadata["args"][0]
            if isinstance(bound, type) and issubclass(bound, TriggerResult):
                return bound
    raise TypeError(
        f"{request_cls.__name__} does not bind a TriggerResult subtype"
    )


class OfferTriggerRequest(
    TriggerRequest[ActivityResult], ReportTriggerRequest
):
    """Trigger request that requires an ``offer_id``."""


class ValidateReportTriggerRequest(OfferTriggerRequest, ValidateReportRequest):
    pass


class InvalidateReportTriggerRequest(
    OfferTriggerRequest, InvalidateReportRequest
):
    pass


class RejectReportTriggerRequest(OfferTriggerRequest):
    """Requires ``offer_id``; ``note`` is strongly encouraged but coerced to
    ``None`` (not rejected) when the caller supplies an empty string, since
    the HTTP adapter already logs a warning in that case.

    Deliberately not derived from ``RejectReportRequest``: that body requires
    the ``note`` key so a client must state a reason (TRIG-03-004), while the
    core request accepts the coerced ``None`` the service passes through.
    """

    note: NonEmptyString | None = None


class CloseReportTriggerRequest(OfferTriggerRequest, CloseReportRequest):
    pass


class SubmitReportTriggerRequest(
    TriggerRequest[OfferResult], SubmitReportRequest
):
    """Trigger request for a finder to create and offer a vulnerability report.

    Creates a ``VulnerabilityReport`` in the actor's DataLayer and queues an
    ``RmSubmitReportActivity`` offer to the specified recipient.
    """


class EngageCaseTriggerRequest(
    TriggerRequest[ActivityResult], CaseTriggerRequest
):
    pass


class DeferCaseTriggerRequest(
    TriggerRequest[ActivityResult], CaseTriggerRequest
):
    pass


class LeaveCaseTriggerRequest(
    TriggerRequest[ActivityResult], CloseCaseRequest
):
    """Trigger request for an actor to send Leave(VulnerabilityCase).

    Routes ``Leave(VulnerabilityCase)`` to the Case Actor inbox so the
    Case Actor can commit a ``close_case`` ledger entry and broadcast it
    to all participants (ADR-0050).  The demo ``close-case`` route's body is
    ``CloseCaseRequest``.
    """


class ProposeEmbargoTriggerRequest(
    TriggerRequest[ActivityResult], ProposeEmbargoRequest
):
    pass


class AcceptEmbargoTriggerRequest(
    TriggerRequest[ActivityResult], AcceptEmbargoRequest
):
    pass


# Backward-compatible alias
EvaluateEmbargoTriggerRequest = AcceptEmbargoTriggerRequest


class RejectEmbargoTriggerRequest(
    TriggerRequest[ActivityResult], RejectEmbargoRequest
):
    pass


class ProposeEmbargoRevisionTriggerRequest(
    TriggerRequest[ActivityResult], ProposeEmbargoRevisionRequest
):
    pass


class TerminateEmbargoTriggerRequest(
    TriggerRequest[ActivityResult], TerminateEmbargoRequest
):
    pass


class AddNoteToCaseTriggerRequest(
    TriggerRequest[NoteResult], AddNoteToCaseRequest
):
    """Trigger request for adding a note to a case."""


class CreateCaseTriggerRequest(TriggerRequest[CaseResult], CreateCaseRequest):
    """Trigger request to create a new VulnerabilityCase.

    The actor creates a local case and emits a CreateCaseActivity queued in
    the outbox for delivery to the CaseActor (or other recipients).
    """


class AddObjectToCaseTriggerRequest(
    TriggerRequest[ActivityResult], AddObjectToCaseRequest
):
    """Trigger request to attach an existing AS2 object to a case.

    The object must already exist in the actor's datalayer.  The use case
    will read it by ``object_id`` and queue an ``Add(object, target=case)``
    activity in the actor's outbox.  Type-specific wrappers (e.g.,
    ``AddReportToCaseTriggerRequest``) extend this with additional
    type-validation before delegating here.
    """


class AddReportToCaseTriggerRequest(
    TriggerRequest[ActivityResult], AddReportToCaseRequest
):
    """Trigger request to link a report to an existing case."""


class SuggestActorToCaseTriggerRequest(
    TriggerRequest[ActivityResult], SuggestActorToCaseRequest
):
    """Trigger request for an actor to recommend another actor to a case.

    Emits a RecommendActorActivity addressed to the Case Actor, which then
    autonomously invites the suggested actor.
    """


class AcceptCaseInviteTriggerRequest(
    TriggerRequest[ActivityResult], AcceptCaseInviteRequest
):
    """Trigger request for an invitee to accept a case invitation.

    Emits an RmAcceptInviteToCaseActivity queued in the actor's outbox for
    delivery to the Case Actor that issued the invitation.
    """


class RejectCaseInviteTriggerRequest(
    TriggerRequest[ActivityResult], RejectCaseInviteRequest
):
    """Trigger request for an invitee to reject a case invitation.

    Emits an RmRejectInviteToCaseActivity queued in the actor's outbox for
    delivery to the Case Actor that issued the invitation.
    """


class AcceptActorRecommendationTriggerRequest(
    TriggerRequest[ActivityResult], AcceptActorRecommendationRequest
):
    """Trigger request for the Case Owner to accept an actor recommendation.

    Emits an Accept(Offer(CaseParticipant)) queued in the Case Owner's outbox
    for delivery to the CaseActor (ADR-0026, CM-16-006).
    """


class InviteActorToCaseTriggerRequest(
    TriggerRequest[ActivityResult], InviteActorToCaseRequest
):
    """Trigger request for the case owner to directly invite an actor.

    Emits an RmInviteToCaseActivity addressed to the invitee, queued in the
    actor's outbox for delivery.
    """


class AddParticipantStatusTriggerRequest(
    TriggerRequest[StatusResult], CaseTriggerRequest
):
    """Trigger request to send a ParticipantStatus update to the case.

    The actor self-reports their current RM/VF/D/PXA state to the Case Manager.
    Emits an Add(ParticipantStatus, target=CaseParticipant) activity.  The
    demo ``notify-*`` routes build this from their ``CaseTriggerRequest``-shaped
    bodies; no client supplies the state fields directly.
    """

    rm_state: RM | None = None
    vf_state: CS_vf | None = None
    d_state: CS_d | None = None
    pxa_state: CS_pxa | None = None


class AddOnBehalfStatusTriggerRequest(
    TriggerRequest[StatusResult], CaseTriggerRequest
):
    """On-behalf v→V / d→D assertion by Case Manager or Case Owner.

    ``actor_id`` is the asserting actor (must hold CASE_MANAGER or CASE_OWNER);
    ``target_actor_id`` is the vendor/deployer whose awareness is being recorded.
    ``vf_state`` may only be ``CS_vf.Vf`` (v→V); ``CS_vf.VF`` (f→F) is rejected
    here because f→F is always self-declared by the Vendor role holder.

    Per ADR-0084, PRM-06-003/004/005.
    """

    target_actor_id: UriString
    vf_state: CS_vf | None = None
    d_state: CS_d | None = None

    @field_validator("vf_state")
    @classmethod
    def vf_state_not_fix_ready(cls, v: CS_vf | None) -> CS_vf | None:
        if v is not None and v == CS_vf.VF:
            raise ValueError(
                "f→F (CS_vf.VF) cannot be asserted on behalf of another actor"
                " (ADR-0084, PRM-06-005)"
            )
        return v

    @model_validator(mode="after")
    def at_least_one_dimension(self) -> "AddOnBehalfStatusTriggerRequest":
        if self.vf_state is None and self.d_state is None:
            raise ValueError(
                "at least one of vf_state or d_state must be provided"
                " (PRM-06-003/004)"
            )
        return self


class OfferCaseParticipantRoleTriggerRequest(
    TriggerRequest[RoleOfferResult], OfferCaseParticipantRoleRequest
):
    """Trigger request to offer a CVDRole to a target Actor in a Case.

    Emits ``Offer(CaseParticipantRole, target=Actor, context=VulnerabilityCase)``
    from the requesting actor (ADR-0039).
    """


class OfferCaseOwnershipTransferTriggerRequest(
    TriggerRequest[ActivityResult], OfferCaseOwnershipTransferRequest
):
    """Trigger request to offer case ownership to another actor.

    Emits ``Offer(VulnerabilityCase)`` (ownership transfer variant) from the
    requesting actor to ``transferee_id`` (TRIG-11-001).
    """


class AcceptCaseOwnershipTransferTriggerRequest(
    TriggerRequest[ActivityResult], AcceptCaseOwnershipTransferRequest
):
    """Trigger request to accept a case ownership transfer offer.

    Emits ``Accept(Offer(VulnerabilityCase))`` from the requesting actor back
    to the offering actor (TRIG-11-002).
    """


__all__ = [
    "AcceptActorRecommendationTriggerRequest",
    "AcceptCaseInviteTriggerRequest",
    "AcceptCaseOwnershipTransferTriggerRequest",
    "AcceptEmbargoTriggerRequest",
    "AddNoteToCaseTriggerRequest",
    "AddObjectToCaseTriggerRequest",
    "AddOnBehalfStatusTriggerRequest",
    "AddParticipantStatusTriggerRequest",
    "AddReportToCaseTriggerRequest",
    "CaseTriggerRequest",
    "CloseReportTriggerRequest",
    "CreateCaseTriggerRequest",
    "DeferCaseTriggerRequest",
    "EngageCaseTriggerRequest",
    "EvaluateEmbargoTriggerRequest",
    "InvalidateReportTriggerRequest",
    "InviteActorToCaseTriggerRequest",
    "LeaveCaseTriggerRequest",
    "OfferCaseOwnershipTransferTriggerRequest",
    "OfferCaseParticipantRoleTriggerRequest",
    "OfferTriggerRequest",
    "ProposeEmbargoRevisionTriggerRequest",
    "ProposeEmbargoTriggerRequest",
    "RejectCaseInviteTriggerRequest",
    "RejectEmbargoTriggerRequest",
    "RejectReportTriggerRequest",
    "ResultT_co",
    "SubmitReportTriggerRequest",
    "SuggestActorToCaseTriggerRequest",
    "TerminateEmbargoTriggerRequest",
    "TriggerRequest",
    "ValidateReportTriggerRequest",
    "result_type_of",
]
