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

"""The invitation profile and the cut it makes of a case (ADR-0217).

The profile names, for every case field, the operations the protocol's
envelope permits and the one this codebase applies;
``CasePreview.from_case`` applies it mechanically (CM-17-010).
"""

from types import MappingProxyType
from typing import Any

import pytest
from pydantic import BaseModel

from test.support.embargo_register import register
from test.support.future_dates import days_from_now
from test.support.objects import make
from vultron.core.models.base import CoreObject
from vultron.core.models.case.vulnerability_case import VulnerabilityCase
from vultron.core.models.case_preview import (
    CasePreview,
    invitation_preview_faults,
    preview_em_state,
    preview_embargo_id,
)
from vultron.core.models.case_preview_profile import (
    INVITATION_PROFILE,
    SHOWING_OPERATIONS,
    PreviewFieldRule,
    PreviewOperation,
)
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.preview_object import is_loose_form_of
from vultron.core.models.redacted import Redacted
from vultron.core.models.vulnerability_item import (
    VulnerabilityItem,
    VulnerabilityItemId,
)
from vultron.core.states.em import EM
from vultron.errors import VultronActivityConstructionError

_OP = PreviewOperation
CASE_ID = "https://example.org/cases/profile"
OWNER = "https://example.org/actors/vendor"

#: The operation each named row chooses, as ADR-0217's table lists it.  The
#: rows the profile generates for every other AS2 property are redacted.
_CHOSEN = {
    "id_": _OP.SUBSTITUTE,
    "type_": _OP.SUBSTITUTE,
    "context_": _OP.OMIT,
    "summary": _OP.SUBSTITUTE,
    "attributed_to": _OP.INCLUDE,
    "case_statuses": _OP.SUBSTITUTE,
    "name": _OP.INCLUDE,
    "published": _OP.INCLUDE,
    "updated": _OP.INCLUDE,
    "vulnerability_items": _OP.SUBSTITUTE,
    "content": _OP.REDACT,
    "case_participants": _OP.REDACT,
    "vulnerability_reports": _OP.REDACT,
    "notes": _OP.REDACT,
    "case_references": _OP.REDACT,
    "parent_cases": _OP.REDACT,
    "child_cases": _OP.REDACT,
    "sibling_cases": _OP.REDACT,
    "embargo_register": _OP.SUBSTITUTE,
    "pending_embargo_proposal_index": _OP.OMIT,
    "genesis_hash": _OP.OMIT,
    "ledger_position": _OP.OMIT,
    "actor_participant_index": _OP.OMIT,
    "stub_summary": _OP.OMIT,
}


def _case(**fields: Any) -> VulnerabilityCase:
    return make(
        VulnerabilityCase,
        id_=CASE_ID,
        attributed_to=OWNER,
        stub_summary="A case to join",
        **fields,
    )


def _embargo() -> EmbargoEvent:
    return make(EmbargoEvent, context=CASE_ID, end_time=days_from_now(30))


def _dump(obj: BaseModel) -> dict[str, Any]:
    """*obj* as JSON, without the ``@context`` a top-level dump adds."""
    dumped = obj.model_dump(by_alias=True, exclude_none=True, mode="json")
    dumped.pop("@context", None)
    return dumped


# --- AC-1: the profile --------------------------------------------------


@pytest.mark.spec("CM-17-010")
def test_the_profile_names_every_case_field() -> None:
    assert set(INVITATION_PROFILE) == set(VulnerabilityCase.model_fields)


@pytest.mark.spec("CM-17-010")
@pytest.mark.parametrize("field", sorted(INVITATION_PROFILE))
def test_each_chosen_operation_is_permitted_in_its_row(field: str) -> None:
    rule = INVITATION_PROFILE[field]

    assert rule.permits(rule.chosen, in_force=False)
    assert rule.permits(rule.chosen, in_force=True)


@pytest.mark.spec("CM-17-010")
def test_the_profile_chooses_as_the_table_lists() -> None:
    other = set(CoreObject.model_fields) - set(_CHOSEN)

    assert {name: INVITATION_PROFILE[name].chosen for name in _CHOSEN} == (
        _CHOSEN
    )
    assert {INVITATION_PROFILE[name].chosen for name in other} == {_OP.REDACT}


@pytest.mark.spec("CM-17-025")
def test_every_omit_only_field_is_absent_from_the_preview() -> None:
    omit_only = {
        name for name, rule in INVITATION_PROFILE.items() if rule.omit_only
    }

    assert omit_only
    assert not omit_only & set(CasePreview.model_fields)


@pytest.mark.spec("CM-17-010")
@pytest.mark.spec("CM-17-002")
@pytest.mark.spec("CM-17-013")
@pytest.mark.parametrize(
    ("field", "in_force"),
    [
        ("summary", False),
        ("attributed_to", False),
        ("case_statuses", True),
        ("embargo_register", True),
    ],
)
def test_the_envelope_requires_the_shown_items(
    field: str, in_force: bool
) -> None:
    """The summary and the Case Owner are always shown; the status and the
    register only while an embargo is in force."""
    rule = INVITATION_PROFILE[field]

    assert rule.must_show(in_force=in_force)
    if in_force:
        assert not rule.must_show(in_force=False)


@pytest.mark.spec("CM-17-014")
def test_the_envelope_forbids_including_the_whole_register() -> None:
    """The whole register would carry open proposals (CM-17-014)."""
    rule = INVITATION_PROFILE["embargo_register"]

    assert not rule.permits(_OP.INCLUDE, in_force=False)


def test_the_profile_cannot_be_changed() -> None:
    assert isinstance(INVITATION_PROFILE, MappingProxyType)
    with pytest.raises(TypeError):
        INVITATION_PROFILE["name"] = INVITATION_PROFILE["content"]  # type: ignore[index]


@pytest.mark.parametrize(
    "fields",
    [
        {"permitted": frozenset({_OP.OMIT}), "chosen": _OP.REDACT},
        {
            "permitted": frozenset({_OP.REDACT, _OP.SUBSTITUTE}),
            "chosen": _OP.REDACT,
            "forbidden_in_force": frozenset({_OP.REDACT}),
        },
        {
            "permitted": frozenset({_OP.OMIT}),
            "chosen": _OP.OMIT,
            "forbidden_in_force": frozenset({_OP.INCLUDE}),
        },
        {"permitted": frozenset({_OP.SUBSTITUTE}), "chosen": _OP.SUBSTITUTE},
        {
            "permitted": frozenset({_OP.REDACT}),
            "chosen": _OP.REDACT,
            "substitution": lambda case: None,
        },
    ],
    ids=[
        "chosen not permitted",
        "chosen forbidden in force",
        "in-force restriction outside the envelope",
        "substitute without a substitution",
        "substitution on a row that does not substitute",
    ],
)
def test_a_self_contradicting_row_is_refused(fields: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="preview rule"):
        PreviewFieldRule(**fields)


def test_a_row_that_does_not_substitute_has_nothing_to_substitute() -> None:
    with pytest.raises(ValueError, match="substitutes nothing"):
        INVITATION_PROFILE["content"].substitute(_case())


def test_showing_operations_are_include_and_substitute() -> None:
    assert {_OP.INCLUDE, _OP.SUBSTITUTE} == SHOWING_OPERATIONS


# --- AC-2: the cut ------------------------------------------------------


@pytest.mark.spec("CM-17-010")
@pytest.mark.spec("CM-17-020")
def test_the_cut_shows_the_owner_name_times_and_current_status() -> None:
    case = _case(name="Widget RCE", summary="What only participants see")

    preview = CasePreview.from_case(case, INVITATION_PROFILE)

    assert preview.summary == "A case to join"
    assert preview.attributed_to == OWNER
    assert preview.name == "Widget RCE"
    assert preview.published == case.published
    assert isinstance(preview.case_statuses, list)
    (status,) = preview.case_statuses
    assert _dump(preview)["caseStatuses"] == [_dump(case.current_status)]
    assert is_loose_form_of(status, type(case.current_status))
    assert preview.id_ != case.id_
    assert preview.type_ == "CasePreview"


@pytest.mark.spec("MV-12-004")
@pytest.mark.parametrize(
    ("field", "held"),
    [
        ("content", "The full write-up"),
        ("case_participants", ["https://example.org/participants/p1"]),
        ("vulnerability_reports", ["https://example.org/reports/r1"]),
        ("notes", ["https://example.org/notes/n1"]),
        ("case_references", ["https://example.org/references/ref1"]),
        ("parent_cases", ["https://example.org/cases/parent"]),
        ("child_cases", ["https://example.org/cases/child"]),
        ("sibling_cases", ["https://example.org/cases/sibling"]),
        ("tag", ["https://example.org/tags/t1"]),
    ],
)
def test_a_withheld_value_the_case_holds_is_one_marker(
    field: str, held: object
) -> None:
    preview = CasePreview.from_case(_case(**{field: held}), INVITATION_PROFILE)

    assert getattr(preview, field) == Redacted()


@pytest.mark.spec("MV-12-004")
@pytest.mark.parametrize(
    "field",
    [
        "content",
        "notes",
        "vulnerability_reports",
        "case_references",
        "parent_cases",
        "tag",
        "name",
        "updated",
        "vulnerability_items",
        "content_map",
    ],
)
def test_a_field_with_no_held_value_is_left_out(field: str) -> None:
    """Absent, ``None`` or an empty collection: nothing to withhold, so no
    marker and no key."""
    preview = CasePreview.from_case(
        _case(updated=None) if field == "updated" else _case(),
        INVITATION_PROFILE,
    )

    assert getattr(preview, field) in (None, {})
    assert _wire_key(field) not in _dump(preview)


def _wire_key(field: str) -> str:
    info = CasePreview.model_fields[field]
    return info.serialization_alias or info.alias or field


@pytest.mark.spec("CM-17-025")
def test_the_cut_leaves_out_the_case_bookkeeping() -> None:
    dumped = _dump(CasePreview.from_case(_case(), INVITATION_PROFILE))

    for key in (
        "genesisHash",
        "ledgerPosition",
        "actorParticipantIndex",
        "stubSummary",
        "pendingEmbargoProposalIndex",
    ):
        assert key not in dumped, key


@pytest.mark.spec("CM-05-018")
def test_each_vul_item_is_cut_to_its_ids() -> None:
    item = make(
        VulnerabilityItem,
        context=CASE_ID,
        name="Buffer overflow in the parser",
        ids=[VulnerabilityItemId.cve("CVE-2026-1234")],
    )
    bare = make(VulnerabilityItem, context=CASE_ID, name="No ids yet")
    held_by_id = "https://example.org/items/by-id"

    preview = CasePreview.from_case(
        _case(vulnerability_items=[item, bare, held_by_id]),
        INVITATION_PROFILE,
    )

    shown, empty, marked = _dump(preview)["vulnerabilityItems"]
    assert shown == {
        "type": "VulnerabilityItem",
        "ids": [{"systemName": "CVE", "text": "CVE-2026-1234"}],
    }
    assert empty == {"type": "VulnerabilityItem", "ids": []}
    assert marked == {"type": "Redacted"}


@pytest.mark.spec("CM-17-002")
@pytest.mark.spec("CM-17-011")
@pytest.mark.spec("CM-17-014")
@pytest.mark.parametrize("revising", [False, True], ids=["active", "revise"])
def test_the_register_is_reduced_to_the_in_force_entry_whole(
    revising: bool,
) -> None:
    embargo = _embargo()
    revision = _embargo()
    case = _case(
        embargo_register=register(
            active=embargo, proposed=[revision] if revising else []
        )
    )

    preview = CasePreview.from_case(case, INVITATION_PROFILE)

    (entry,) = _dump(preview)["embargoRegister"]
    assert entry["status"] == "ACTIVE"
    assert entry["embargo"] == _dump(embargo)
    assert preview_embargo_id(preview) == embargo.id_
    assert preview_em_state(preview) is (EM.REVISE if revising else EM.ACTIVE)


@pytest.mark.spec("CM-17-002")
@pytest.mark.parametrize("shape", ["proposed", "terminated"])
def test_with_no_embargo_in_force_the_register_is_left_out(shape: str) -> None:
    embargo = _embargo()
    entries = (
        register(proposed=[embargo])
        if shape == "proposed"
        else register(terminated=embargo)
    )

    preview = CasePreview.from_case(
        _case(embargo_register=entries), INVITATION_PROFILE
    )

    assert preview.embargo_register is None
    assert preview_em_state(preview) is not None


# --- AC-3: refusals -----------------------------------------------------


@pytest.mark.spec("CM-17-010")
@pytest.mark.spec("MV-10-001")
def test_a_case_with_no_stub_summary_is_refused() -> None:
    case = make(VulnerabilityCase, id_=CASE_ID, attributed_to=OWNER)

    with pytest.raises(VultronActivityConstructionError, match="stub_summary"):
        CasePreview.from_case(case, INVITATION_PROFILE)


@pytest.mark.spec("CM-17-010")
def test_a_case_with_no_owner_is_refused() -> None:
    """A valid case always names its owner; a copy that lost it cannot be
    shown to an invitee."""
    case = _case().model_copy(update={"attributed_to": None})

    with pytest.raises(VultronActivityConstructionError, match="attributedTo"):
        CasePreview.from_case(case, INVITATION_PROFILE)


@pytest.mark.spec("CM-17-013")
def test_a_case_holding_no_status_object_is_refused() -> None:
    """A copy that names its statuses only by id has no current status to
    show, so the cut refuses it as the construction error the factory
    raises, not a bare ``ValueError``."""
    case = _case().model_copy(update={"case_statuses": ["urn:uuid:s1"]})

    with pytest.raises(VultronActivityConstructionError, match="CM-17-013"):
        CasePreview.from_case(case, INVITATION_PROFILE)


@pytest.mark.spec("CM-17-011")
@pytest.mark.spec("CM-17-024")
def test_an_in_force_embargo_held_by_id_is_refused() -> None:
    case = _case(embargo_register=register(active=_embargo().id_))

    with pytest.raises(VultronActivityConstructionError, match="CM-17-024"):
        CasePreview.from_case(case, INVITATION_PROFILE)


def test_a_profile_missing_a_case_field_is_refused() -> None:
    partial = {
        name: rule
        for name, rule in INVITATION_PROFILE.items()
        if name != "notes"
    }

    with pytest.raises(VultronActivityConstructionError, match="notes"):
        CasePreview.from_case(_case(), partial)


@pytest.mark.spec("CM-17-014")
def test_a_profile_whose_cut_breaks_the_envelope_is_refused() -> None:
    """A profile that shows the whole register carries the open proposal,
    so its cut is refused rather than sent."""
    whole_register = PreviewFieldRule(
        permitted=frozenset({_OP.SUBSTITUTE}),
        chosen=_OP.SUBSTITUTE,
        substitution=lambda case: [
            {"embargo": e.embargo_id, "status": e.status.value}
            for e in case.embargo_register
        ],
    )
    profile = {**INVITATION_PROFILE, "embargo_register": whole_register}
    case = _case(
        embargo_register=register(active=_embargo(), proposed=[_embargo()])
    )

    with pytest.raises(
        VultronActivityConstructionError, match="open embargo proposal"
    ):
        CasePreview.from_case(case, profile)


@pytest.mark.spec("CM-17-002")
def test_active_register_entry_is_the_active_one() -> None:
    embargo = _embargo()
    case = _case(
        embargo_register=register(active=embargo, proposed=[_embargo()])
    )

    entry = case.active_register_entry

    assert entry is not None and entry.embargo_id == embargo.id_
    assert _case().active_register_entry is None


# --- The envelope check a cut passes ------------------------------------


def _shown(**fields: Any) -> CasePreview:
    return CasePreview.model_validate(
        {"summary": "a case", "attributedTo": OWNER, **fields}
    )


_ACTIVE_STATUS = {"type": "CaseStatus", "emState": "ACTIVE"}
_ACTIVE_ENTRY = {"embargo": "urn:uuid:e1", "status": "ACTIVE"}


@pytest.mark.spec("MV-10-007")
@pytest.mark.parametrize(
    ("fields", "fault"),
    [
        ({"attributedTo": None}, "lacks the Case Owner"),
        ({"attributedTo": {"type": "Redacted"}}, "marks the Case Owner"),
        (
            {"caseStatuses": [_ACTIVE_STATUS]},
            "lacks the in-force entry",
        ),
        (
            {
                "caseStatuses": [_ACTIVE_STATUS],
                "embargoRegister": {"type": "Redacted"},
            },
            "marks 'embargoRegister' Redacted",
        ),
        (
            {
                "caseStatuses": [_ACTIVE_STATUS],
                "embargoRegister": [
                    {"embargo": {"type": "Redacted"}, "status": "ACTIVE"}
                ],
            },
            "lacks or marks the in-force embargo",
        ),
        ({"embargoRegister": [_ACTIVE_ENTRY]}, "lacks or marks the EM state"),
        (
            {
                "embargoRegister": [_ACTIVE_ENTRY],
                "caseStatuses": [
                    {"type": "CaseStatus", "em": {"type": "Redacted"}}
                ],
            },
            "lacks or marks the EM state",
        ),
        (
            {
                "embargoRegister": [
                    _ACTIVE_ENTRY,
                    {"embargo": "urn:uuid:e2", "status": "PROPOSED"},
                ],
                "caseStatuses": [{"type": "CaseStatus", "emState": "REVISE"}],
            },
            "open embargo proposal at 'embargoRegister[1]'",
        ),
    ],
    ids=[
        "no owner",
        "owner marked",
        "in force, no entry",
        "in force, register marked",
        "in force, embargo marked",
        "entry shown, no EM state",
        "entry shown, EM state marked",
        "open proposal",
    ],
)
def test_the_envelope_check_names_each_fault(
    fields: dict[str, Any], fault: str
) -> None:
    faults = invitation_preview_faults(_shown(**fields))

    assert any(fault in each for each in faults), faults


@pytest.mark.spec("MV-12-006")
@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"caseStatuses": [{"type": "CaseStatus", "emState": "NONE"}]},
        {"caseStatuses": {"type": "Redacted"}},
        {"embargoRegister": {"type": "Redacted"}},
        {
            "caseStatuses": [_ACTIVE_STATUS],
            "embargoRegister": [_ACTIVE_ENTRY],
            "name": {"type": "Redacted"},
            "vulnerabilityItems": [{"type": "Redacted"}],
        },
    ],
    ids=[
        "summary and owner only",
        "no embargo",
        "status withheld, nothing in force shown",
        "register withheld, nothing in force shown",
        "in force, terms and EM shown, the rest withheld",
    ],
)
def test_the_envelope_check_leaves_the_rest_to_the_sender(
    fields: dict[str, Any],
) -> None:
    assert invitation_preview_faults(_shown(**fields)) == []
