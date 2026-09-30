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

"""The single trigger request-model family and its result binding (ADR-0110).

- Every concrete ``*TriggerRequest`` binds ``TriggerRequest[ResultT_co]`` to
  the ``TriggerResult`` subtype its verb returns, resolvable statically through
  one ``trigger(request) -> ResultT_co`` signature with no cast (UCORG-05-006
  groundwork) and at runtime through :func:`result_type_of`.
- Every core request derives from its verb's body model, which owns the
  fields; ``actor_id`` is the one field the core adds (TRIG-06-001).
- The adapter module re-exports the body models unchanged, so the OpenAPI
  component names survive (TRIG-12-003) and ``CaseTriggerRequest`` is one
  class.
- The ``end_time`` rule is declared once and covers both the initial proposal
  and the revision (CS-22-001); the revision copy had no test before #3831.
"""

import inspect
from datetime import datetime, timedelta, timezone
from typing import assert_type

import pytest
from pydantic import BaseModel, ValidationError

from vultron.adapters.driving.fastapi import trigger_models
from vultron.core.models.use_case_result import (
    ActivityResult,
    CaseResult,
    NoteResult,
    OfferResult,
    RoleOfferResult,
    StatusResult,
    TriggerResult,
)
from vultron.core.use_cases.triggers import request_bodies, requests
from vultron.core.use_cases.triggers.request_bodies import (
    CaseTriggerRequest,
    ProposeEmbargoRequest,
    ProposeEmbargoRevisionRequest,
)
from vultron.core.use_cases.triggers.requests import (
    AddNoteToCaseTriggerRequest,
    AddParticipantStatusTriggerRequest,
    CreateCaseTriggerRequest,
    EngageCaseTriggerRequest,
    OfferCaseParticipantRoleTriggerRequest,
    ProposeEmbargoRevisionTriggerRequest,
    ProposeEmbargoTriggerRequest,
    ResultT_co,
    SubmitReportTriggerRequest,
    TriggerRequest,
    result_type_of,
)

_ACTOR = "https://example.org/actors/vendor"
_CASE = "https://example.org/api/v2/VulnerabilityCases/abc"
_FUTURE = datetime(2099, 12, 1, tzinfo=timezone.utc)


def _concrete_requests() -> list[type[TriggerRequest[TriggerResult]]]:
    """Every ``TriggerRequest`` subclass ``requests`` exports."""
    found = [
        obj
        for name in requests.__all__
        if isinstance(obj := getattr(requests, name), type)
        and issubclass(obj, TriggerRequest)
        and obj is not TriggerRequest
    ]
    return found


def test_the_request_family_kept_every_member() -> None:
    """27 verbs plus the ``OfferTriggerRequest`` intermediate, none lost."""
    assert len(_concrete_requests()) >= 28


# ---------------------------------------------------------------------------
# Result binding (AC-5)
# ---------------------------------------------------------------------------


def _trigger(request: TriggerRequest[ResultT_co]) -> ResultT_co:
    """The one-method driving port's shape (UCORG-05-006), minus the port.

    Returns an instance of the bound result type so the runtime check below
    exercises the same binding mypy and pyright resolve statically.
    """
    result_cls = result_type_of(type(request))
    sample: dict[str, dict[str, object]] = {
        "ActivityResult": {"emitting_actor_id": _ACTOR},
        "NoteResult": {"emitting_actor_id": _ACTOR},
        "CaseResult": {"emitting_actor_id": _ACTOR},
        "StatusResult": {},
        "OfferResult": {},
        "RoleOfferResult": {"activity_id": "urn:uuid:1", "activity": {}},
    }
    result = result_cls.model_validate(sample[result_cls.__name__])
    # ``result_type_of`` returns ``type[TriggerResult]``; the static binding
    # is what the call sites below assert with ``assert_type``.
    return result  # type: ignore[return-value]


def test_static_binding_resolves_each_verbs_result_without_a_cast() -> None:
    """mypy and pyright resolve ``ResultT_co`` through ``_trigger`` alone.

    ``assert_type`` is checked by both type checkers and is a no-op at runtime;
    the ``isinstance`` lines confirm the runtime value agrees with the type.
    """
    engage = _trigger(EngageCaseTriggerRequest(actor_id=_ACTOR, case_id=_CASE))
    assert_type(engage, ActivityResult)
    assert isinstance(engage, ActivityResult)

    note = _trigger(
        AddNoteToCaseTriggerRequest(
            actor_id=_ACTOR, case_id=_CASE, note_name="n", note_content="c"
        )
    )
    assert_type(note, NoteResult)
    assert isinstance(note, NoteResult)

    created = _trigger(
        CreateCaseTriggerRequest(actor_id=_ACTOR, name="n", content="c")
    )
    assert_type(created, CaseResult)
    assert isinstance(created, CaseResult)

    status = _trigger(
        AddParticipantStatusTriggerRequest(actor_id=_ACTOR, case_id=_CASE)
    )
    assert_type(status, StatusResult)
    assert isinstance(status, StatusResult)

    offer = _trigger(
        SubmitReportTriggerRequest(
            actor_id=_ACTOR,
            report_name="r",
            report_content="c",
            recipient_id=_ACTOR,
        )
    )
    assert_type(offer, OfferResult)
    assert isinstance(offer, OfferResult)

    role = _trigger(
        OfferCaseParticipantRoleTriggerRequest(
            actor_id=_ACTOR, case_id=_CASE, target_actor_id=_ACTOR
        )
    )
    assert_type(role, RoleOfferResult)
    assert isinstance(role, RoleOfferResult)


@pytest.mark.parametrize(
    "request_cls", _concrete_requests(), ids=lambda cls: cls.__name__
)
def test_every_concrete_request_binds_a_trigger_result_subtype(
    request_cls: type[TriggerRequest[TriggerResult]],
) -> None:
    """AC-5: no request is left bound to the fieldless root."""
    bound = result_type_of(request_cls)
    assert issubclass(bound, TriggerResult)
    assert bound is not TriggerResult


def test_result_type_of_refuses_an_unbound_request() -> None:
    """The base itself binds nothing; asking for its result is an error."""
    with pytest.raises(TypeError, match="does not bind"):
        result_type_of(TriggerRequest)


def test_result_type_var_is_covariant_and_bound() -> None:
    """``ResultT_co`` is the ADR-0110 type variable, not a fresh one."""
    assert ResultT_co.__covariant__ is True
    assert ResultT_co.__bound__ is TriggerResult


# ---------------------------------------------------------------------------
# One request-model family (AC-4)
# ---------------------------------------------------------------------------


def _body_models() -> list[type[BaseModel]]:
    return [
        obj
        for _, obj in inspect.getmembers(request_bodies, inspect.isclass)
        if issubclass(obj, BaseModel)
        and obj is not BaseModel
        and obj.__module__ == request_bodies.__name__
    ]


def test_adapter_module_re_exports_every_body_model_unchanged() -> None:
    """TRIG-12-003: the OpenAPI component names are the same class objects."""
    for body in _body_models():
        assert getattr(trigger_models, body.__name__) is body
        assert body.__name__ in trigger_models.__all__
    assert (
        trigger_models.EvaluateEmbargoRequest
        is request_bodies.AcceptEmbargoRequest
    )


def test_case_trigger_request_is_defined_once() -> None:
    assert requests.CaseTriggerRequest is CaseTriggerRequest
    assert trigger_models.CaseTriggerRequest is CaseTriggerRequest


@pytest.mark.parametrize("body", _body_models(), ids=lambda cls: cls.__name__)
def test_body_models_never_carry_actor_id(body: type[BaseModel]) -> None:
    """TRIG-06-001: the actor is the URL path, never a body field."""
    assert "actor_id" not in body.model_fields


@pytest.mark.parametrize(
    "request_cls", _concrete_requests(), ids=lambda cls: cls.__name__
)
def test_every_core_request_adds_actor_id_to_a_body_model(
    request_cls: type[TriggerRequest[TriggerResult]],
) -> None:
    """Each core request derives from a body model and adds only ``actor_id``.

    The intermediate ``OfferTriggerRequest`` derives from
    ``ReportTriggerRequest``; the two status requests and ``RejectReport``
    derive from the ``CaseTriggerRequest`` / ``ReportTriggerRequest`` bases
    and add the fields no HTTP body supplies.
    """
    bodies = [
        base
        for base in request_cls.__mro__
        if issubclass(base, BaseModel)
        and base.__module__ == request_bodies.__name__
    ]
    assert bodies, f"{request_cls.__name__} derives from no body model"
    assert "actor_id" in request_cls.model_fields
    body_fields = set().union(*(b.model_fields for b in bodies))
    own = set(request_cls.model_fields) - body_fields - {"actor_id"}
    allowed_extras = {
        "AddParticipantStatusTriggerRequest": {
            "rm_state",
            "vf_state",
            "d_state",
            "pxa_state",
        },
        "AddOnBehalfStatusTriggerRequest": {
            "target_actor_id",
            "vf_state",
            "d_state",
        },
    }
    assert own <= allowed_extras.get(request_cls.__name__, set()), (
        f"{request_cls.__name__} declares fields its body model does not:"
        f" {sorted(own)}"
    )


# ---------------------------------------------------------------------------
# The end_time rule, declared once (AC-4, CS-22-001)
# ---------------------------------------------------------------------------

_END_TIME_MODELS: list[type[BaseModel]] = [
    ProposeEmbargoRequest,
    ProposeEmbargoRevisionRequest,
    ProposeEmbargoTriggerRequest,
    ProposeEmbargoRevisionTriggerRequest,
]


def _end_time_payload(model: type[BaseModel], end_time: datetime) -> dict:
    payload: dict[str, object] = {"case_id": _CASE, "end_time": end_time}
    if "actor_id" in model.model_fields:
        payload["actor_id"] = _ACTOR
    return payload


def test_end_time_validator_is_declared_once() -> None:
    """CS-22-001: one function object serves the proposal and the revision."""
    owner = ProposeEmbargoRequest.__dict__[
        "end_time_must_be_tz_aware_and_future"
    ]
    assert "end_time_must_be_tz_aware_and_future" not in (
        ProposeEmbargoRevisionRequest.__dict__
    )
    for model in _END_TIME_MODELS:
        assert (
            getattr(model, "end_time_must_be_tz_aware_and_future").__func__
            is owner.__func__
        )


@pytest.mark.parametrize("model", _END_TIME_MODELS, ids=lambda m: m.__name__)
def test_end_time_rejects_a_naive_datetime(model: type[BaseModel]) -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        model.model_validate(_end_time_payload(model, datetime(2099, 12, 1)))


@pytest.mark.parametrize("model", _END_TIME_MODELS, ids=lambda m: m.__name__)
def test_end_time_rejects_a_past_datetime(model: type[BaseModel]) -> None:
    past = datetime.now(tz=timezone.utc) - timedelta(days=1)
    with pytest.raises(ValidationError, match="in the future"):
        model.model_validate(_end_time_payload(model, past))


@pytest.mark.parametrize("model", _END_TIME_MODELS, ids=lambda m: m.__name__)
def test_end_time_accepts_an_aware_future_datetime(
    model: type[BaseModel],
) -> None:
    built = model.model_validate(_end_time_payload(model, _FUTURE))
    assert getattr(built, "end_time") == _FUTURE
