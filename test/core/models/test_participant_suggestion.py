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
"""The suggestion context is a case profile, and a suggestion an identity.

- Every model profile's fields are a subset of its model's, at every nesting
  level (BT-24-009): a ratchet over every :class:`ModelProfile` subclass.
- The suggestion context carries exactly the reports' descriptive content
  and the participants' actor ids and roles (BT-24-002, BT-24-009).
- A suggestion requires an actor id, a role and a rationale, forbids extra
  fields and carries no timing (BT-24-004, BT-24-006).
"""

from __future__ import annotations

import datetime
import importlib
import pkgutil
import typing
from typing import ClassVar

import pytest
from pydantic import BaseModel, Field, ValidationError

import vultron.core.models as core_models
from test.support.objects import make
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.participant_suggestion import (
    ParticipantProfile,
    ParticipantSuggestion,
    ReportProfile,
    SuggestionContext,
)
from vultron.core.models.profile import ModelProfile, profile_violations
from vultron.core.models.report import VulnerabilityReport
from vultron.enums import CVDRole
from vultron.errors import VultronValidationError
from vultron.primitives import NonEmptyString

_OWNER = "https://example.org/actors/owner"
_VENDOR = "https://example.org/actors/vendor"
_CASE = "https://example.org/cases/c-1"
_REPORT = "https://example.org/reports/r-1"


def _profiles() -> list[type[ModelProfile]]:
    """Every concrete profile under ``vultron.core.models``."""
    for info in pkgutil.walk_packages(
        core_models.__path__, prefix=f"{core_models.__name__}."
    ):
        importlib.import_module(info.name)
    found: list[type[ModelProfile]] = []
    pending = list(ModelProfile.__subclasses__())
    while pending:
        cls = pending.pop()
        pending.extend(cls.__subclasses__())
        if cls.__module__.startswith("vultron."):
            found.append(cls)
    return sorted(set(found), key=lambda c: c.__qualname__)


_PROFILES = _profiles()


def test_the_profiles_are_found() -> None:
    assert {SuggestionContext, ReportProfile, ParticipantProfile} <= set(
        _PROFILES
    )


@pytest.mark.spec("BT-24-009")
@pytest.mark.parametrize("profile", _PROFILES, ids=lambda c: c.__qualname__)
def test_every_profile_is_a_subset_of_its_model(
    profile: type[ModelProfile],
) -> None:
    assert profile_violations(profile) == []


@pytest.mark.spec("BT-24-009")
def test_the_suggestion_context_is_not_a_case() -> None:
    """A subclass would inherit every later case field and fail open."""
    assert not issubclass(SuggestionContext, VulnerabilityCase)
    assert SuggestionContext.profile_of is VulnerabilityCase
    assert ReportProfile.profile_of is VulnerabilityReport
    assert ParticipantProfile.profile_of is CaseParticipant


@pytest.mark.spec("BT-24-002")
@pytest.mark.spec("BT-24-009")
def test_the_fields_the_suggestion_context_carries_are_pinned() -> None:
    """Widening what leaves the actor is a visible change (BT-24-003)."""
    assert set(SuggestionContext.model_fields) == {
        "id_",
        "vulnerability_reports",
        "case_participants",
    }
    assert set(ReportProfile.model_fields) == {
        "id_",
        "name",
        "summary",
        "content",
    }
    assert set(ParticipantProfile.model_fields) == {
        "attributed_to",
        "case_roles",
    }


# --- the subset check finds what it must ----------------------------------


class _Unrelated(ModelProfile):
    profile_of = VulnerabilityReport

    not_a_report_field: NonEmptyString


class _Widened(ModelProfile):
    profile_of = VulnerabilityReport

    content: str | None = None


class _WrongNested(ModelProfile):
    profile_of = VulnerabilityCase

    vulnerability_reports: list[ParticipantProfile] = Field(
        default_factory=list
    )


class _NotAList(ModelProfile):
    profile_of = VulnerabilityCase

    case_participants: ParticipantProfile | None = None


class _BadLeaf(ModelProfile):
    profile_of = CaseParticipant

    case_roles: list[str] = Field(default_factory=list)


class _BadAtDepth(ModelProfile):
    profile_of = VulnerabilityCase

    id_: NonEmptyString
    case_participants: list[_BadLeaf] = Field(default_factory=list)


class _NoModel(ModelProfile):
    profile_of: ClassVar[type[BaseModel]]  # type: ignore[misc]

    id_: NonEmptyString


@pytest.mark.spec("BT-24-009")
@pytest.mark.parametrize(
    ("profile", "fragment"),
    [
        (_Unrelated, "not_a_report_field is not a field of"),
        (_Widened, "_Widened.content"),
        (_WrongNested, "_WrongNested.vulnerability_reports"),
        (_NotAList, "_NotAList.case_participants"),
        (_BadAtDepth, "_BadLeaf.case_roles"),
        (_NoModel, "names no model it profiles"),
    ],
    ids=lambda v: v.__name__ if isinstance(v, type) else v,
)
def test_the_subset_check_reports_a_breach(
    profile: type[ModelProfile], fragment: str
) -> None:
    problems = profile_violations(profile)
    assert any(fragment in p for p in problems), problems


def test_the_test_profiles_are_not_in_the_roster() -> None:
    assert not {_Unrelated, _Widened, _BadAtDepth} & set(_PROFILES)


# --- from_case ------------------------------------------------------------


def _participant(actor_id: str, *roles: CVDRole) -> CaseParticipant:
    return make(
        CaseParticipant,
        attributed_to=actor_id,
        context=_CASE,
        case_roles=list(roles),
    )


def _report() -> VulnerabilityReport:
    return make(
        VulnerabilityReport,
        id_=_REPORT,
        attributed_to=_OWNER,
        name="Overflow in libexample",
        summary="A heap overflow in libexample, shipped by Example Corp.",
        content="Example Corp's libexample 2.1 is bundled by Other Inc.",
    )


def _case(**fields: object) -> VulnerabilityCase:
    return make(VulnerabilityCase, id_=_CASE, attributed_to=_OWNER, **fields)


@pytest.mark.spec("BT-24-003")
@pytest.mark.spec("BT-24-009")
def test_from_case_carries_the_evidence_and_who_is_in() -> None:
    owner = _participant(_OWNER, CVDRole.REPORTER, CVDRole.CASE_OWNER)
    vendor = _participant(_VENDOR, CVDRole.VENDOR)
    case = _case(
        vulnerability_reports=[_report()], case_participants=[owner, vendor]
    )

    context = SuggestionContext.from_case(case)

    assert context.id_ == _CASE
    assert context.vulnerability_reports == [
        ReportProfile(
            id_=_REPORT,
            name="Overflow in libexample",
            summary="A heap overflow in libexample, shipped by Example Corp.",
            content="Example Corp's libexample 2.1 is bundled by Other Inc.",
        )
    ]
    assert context.case_participants == [
        ParticipantProfile(
            attributed_to=_OWNER,
            case_roles=[CVDRole.REPORTER, CVDRole.CASE_OWNER],
        ),
        ParticipantProfile(attributed_to=_VENDOR, case_roles=[CVDRole.VENDOR]),
    ]
    assert [p.attributed_to for p in context.vendors] == [_VENDOR]


def test_an_empty_case_projects_to_an_empty_context() -> None:
    context = SuggestionContext.from_case(_case())
    assert context.vulnerability_reports == []
    assert context.case_participants == []
    assert context.vendors == []


@pytest.mark.parametrize(
    "fields",
    [
        {"vulnerability_reports": [_REPORT]},
        {"case_participants": ["https://example.org/participants/p-1"]},
    ],
    ids=["report", "participant"],
)
def test_from_case_refuses_a_bare_reference(fields: dict[str, object]) -> None:
    """Dropping it would hide evidence or a party already in the case."""
    with pytest.raises(VultronValidationError, match="bare references"):
        SuggestionContext.from_case(_case(**fields))


def test_from_case_refuses_a_participant_with_no_actor() -> None:
    nobody = make(CaseParticipant, context=_CASE, name="unnamed")
    with pytest.raises(VultronValidationError, match="ParticipantProfile"):
        SuggestionContext.from_case(_case(case_participants=[nobody]))


def test_a_profile_built_from_the_wrong_model_is_refused() -> None:
    with pytest.raises(TypeError, match="profiles VulnerabilityReport"):
        ReportProfile.from_model(_participant(_VENDOR))


def test_a_profile_forbids_extra_fields_and_is_frozen() -> None:
    with pytest.raises(ValidationError):
        ReportProfile(id_=_REPORT, attachment=[])  # type: ignore[call-arg]
    profile = ReportProfile(id_=_REPORT)
    with pytest.raises(ValidationError):
        profile.name = "changed"  # type: ignore[misc]


# --- the suggestion -------------------------------------------------------


@pytest.mark.spec("BT-24-004")
def test_a_suggestion_names_an_actor_a_role_and_a_reason() -> None:
    suggestion = ParticipantSuggestion(
        actor_id=_VENDOR, role=CVDRole.VENDOR, rationale="ships libexample"
    )
    assert suggestion.role is CVDRole.VENDOR


@pytest.mark.spec("BT-24-004")
@pytest.mark.parametrize(
    "fields",
    [
        {"role": CVDRole.VENDOR, "rationale": "r"},
        {"actor_id": _VENDOR, "rationale": "r"},
        {"actor_id": _VENDOR, "role": CVDRole.VENDOR},
        {"actor_id": _VENDOR, "role": CVDRole.VENDOR, "rationale": ""},
        {"actor_id": "", "role": CVDRole.VENDOR, "rationale": "r"},
        {"actor_id": _VENDOR, "role": "finder", "rationale": "r"},
    ],
    ids=[
        "no-actor",
        "no-role",
        "no-rationale",
        "blank-rationale",
        "blank-actor",
        "unknown-role",
    ],
)
def test_a_suggestion_missing_a_part_is_refused(
    fields: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ParticipantSuggestion(**fields)  # type: ignore[arg-type]


@pytest.mark.spec("BT-24-006")
def test_a_suggestion_carries_no_timing() -> None:
    with pytest.raises(ValidationError):
        ParticipantSuggestion(
            actor_id=_VENDOR,
            role=CVDRole.VENDOR,
            rationale="r",
            invite_at="2026-12-01T00:00:00Z",  # type: ignore[call-arg]
        )
    hints = typing.get_type_hints(ParticipantSuggestion)
    timing = (datetime.datetime, datetime.date, datetime.timedelta)
    for name in ParticipantSuggestion.model_fields:
        assert not any(
            isinstance(t, type) and issubclass(t, timing)
            for t in (hints[name], *typing.get_args(hints[name]))
        ), name
