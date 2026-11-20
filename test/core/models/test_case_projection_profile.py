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
"""The public and joined profiles a case is cut by for a projection.

Each names one ADR-0217 operation for every case field, as the field-group
table of ``notes/csaf-projection.md`` lists it, and what it does with the
ledger list, the one preview field that is not a case field (ADR-0219).
"""

from types import MappingProxyType
from typing import Any

import pytest
from pydantic import ValidationError

from test.support.case_projection import (
    CASE_ID,
    JOINED_ONLY_UNRENDERED,
    JOINED_ONLY_VALUES,
    PAYLOAD_ONLY_VALUE,
    POSITION,
    REPORTER,
    ledger_entry,
    projected_case,
    projected_ledger,
)
from vultron.core.models.base import CoreObject
from vultron.core.models.case.vulnerability_case import VulnerabilityCase
from vultron.core.models.case_preview import (
    CasePreview,
    invitation_preview_faults,
)
from vultron.core.models.case_preview_profile import (
    INVITATION_PROFILE,
    PreviewOperation,
)
from vultron.core.models.case_projection import (
    Acknowledgment,
    ProjectingActor,
    ProjectionCut,
    ProjectionInputs,
    PublicationStatus,
    reporter_acknowledgments,
)
from vultron.core.models.case_projection_profile import (
    JOINED_LEDGER_ACTS,
    JOINED_PROFILE,
    PUBLIC_PROFILE,
    SHOWN_PAYLOAD_KEYS,
    DistributionLabel,
    ProjectionProfile,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.redacted import Redacted

_OP = PreviewOperation

#: The rows the two profiles share, as the table lists them.
_SHARED = {
    "id_": _OP.INCLUDE,
    "type_": _OP.SUBSTITUTE,
    "context_": _OP.OMIT,
    "name": _OP.INCLUDE,
    "summary": _OP.INCLUDE,
    "published": _OP.INCLUDE,
    "updated": _OP.INCLUDE,
    "vulnerability_items": _OP.INCLUDE,
    "case_references": _OP.INCLUDE,
    "case_statuses": _OP.SUBSTITUTE,
    "ledger_position": _OP.INCLUDE,
    "stub_summary": _OP.OMIT,
    "actor_participant_index": _OP.OMIT,
    "pending_embargo_proposal_index": _OP.OMIT,
    "genesis_hash": _OP.OMIT,
    "parent_cases": _OP.OMIT,
    "child_cases": _OP.OMIT,
    "sibling_cases": _OP.OMIT,
}
#: The rows the public profile omits and the joined profile includes.
_JOINED_ONLY = {
    "content",
    "notes",
    "vulnerability_reports",
    "attributed_to",
    "embargo_register",
    "case_participants",
}
_PROFILES = [PUBLIC_PROFILE, JOINED_PROFILE]


# --- AC-2: every case field has one operation --------------------------------


@pytest.mark.spec("CSAF-06-003")
@pytest.mark.parametrize("profile", _PROFILES, ids=lambda p: p.name)
def test_each_profile_names_every_case_field(
    profile: ProjectionProfile,
) -> None:
    assert set(profile.fields) == set(VulnerabilityCase.model_fields)


@pytest.mark.spec("CSAF-06-003")
def test_a_profile_with_an_unclassified_case_field_is_refused() -> None:
    rows = dict(PUBLIC_PROFILE.fields)
    del rows["content"]

    with pytest.raises(ValueError, match="content"):
        ProjectionProfile(
            name="partial-v1",
            distribution=DistributionLabel.CLEAR,
            fields=rows,
        )


@pytest.mark.spec("CSAF-06-003")
@pytest.mark.parametrize(
    ("profile", "joined_only"),
    [(PUBLIC_PROFILE, _OP.OMIT), (JOINED_PROFILE, _OP.INCLUDE)],
    ids=["public", "joined"],
)
def test_each_profile_chooses_as_the_table_lists(
    profile: ProjectionProfile, joined_only: PreviewOperation
) -> None:
    expected = {**_SHARED, **dict.fromkeys(_JOINED_ONLY, joined_only)}
    other = set(CoreObject.model_fields) - set(expected)

    assert {name: profile.fields[name].chosen for name in expected} == (
        expected
    )
    assert {profile.fields[name].chosen for name in other} == {_OP.OMIT}


@pytest.mark.parametrize("profile", _PROFILES, ids=lambda p: p.name)
def test_a_profiles_rows_cannot_be_changed(
    profile: ProjectionProfile,
) -> None:
    assert isinstance(profile.fields, MappingProxyType)


def test_each_profile_has_a_versioned_name_and_its_label() -> None:
    assert (PUBLIC_PROFILE.name, PUBLIC_PROFILE.distribution) == (
        "public-v1",
        DistributionLabel.CLEAR,
    )
    assert (JOINED_PROFILE.name, JOINED_PROFILE.distribution) == (
        "joined-v1",
        DistributionLabel.AMBER_STRICT,
    )


# --- AC-1: the ledger list ---------------------------------------------------


def _entries(preview: CasePreview) -> list[dict[str, Any]]:
    """The ledger entries *preview* keeps, as JSON."""
    dumped = preview.model_dump(mode="json", by_alias=True, exclude_none=True)
    entries: list[dict[str, Any]] = dumped["ledgerEntries"]
    return entries


def test_the_public_cut_carries_no_ledger() -> None:
    public = CasePreview.for_projection(
        projected_case(), projected_ledger(), PUBLIC_PROFILE
    )

    assert PUBLIC_PROFILE.ledger_operation is _OP.OMIT
    assert public.ledger_entries is None
    assert "ledgerEntries" not in public.model_dump(
        by_alias=True, exclude_none=True
    )


def test_the_joined_cut_keeps_only_the_acts_it_lists_in_order() -> None:
    ledger = projected_ledger()

    preview = CasePreview.for_projection(
        projected_case(), ledger, JOINED_PROFILE
    )

    kept = [entry["logIndex"] for entry in _entries(preview)]
    assert kept == [
        entry.log_index
        for entry in ledger
        if entry.semantic_type in JOINED_LEDGER_ACTS
    ]
    assert MessageSemantics.ADD_CASE_STATUS_TO_CASE.value not in {
        entry["semanticType"] for entry in _entries(preview)
    }


def test_the_joined_cut_keeps_only_each_activitys_envelope() -> None:
    preview = CasePreview.for_projection(
        projected_case(), projected_ledger(), JOINED_PROFILE
    )

    for entry in _entries(preview):
        assert set(entry["payloadSnapshot"]) <= set(SHOWN_PAYLOAD_KEYS)
        assert "prevLogHash" not in entry
        assert "receivedAt" not in entry
    assert PAYLOAD_ONLY_VALUE not in preview.model_dump_json()


def test_a_ledger_with_no_kept_act_is_left_out() -> None:
    preview = CasePreview.for_projection(projected_case(), [], JOINED_PROFILE)

    assert preview.ledger_entries is None


@pytest.mark.spec("CSAF-06-002")
def test_the_public_cut_shows_none_of_the_joined_only_values() -> None:
    public = CasePreview.for_projection(
        projected_case(), projected_ledger(), PUBLIC_PROFILE
    ).model_dump_json()
    joined = CasePreview.for_projection(
        projected_case(), projected_ledger(), JOINED_PROFILE
    ).model_dump_json()

    for value in [
        *JOINED_ONLY_VALUES.values(),
        *JOINED_ONLY_UNRENDERED.values(),
    ]:
        assert value in joined
        assert value not in public


@pytest.mark.spec("CSAF-06-002")
def test_the_public_cut_shows_the_current_status_by_its_pxa_state_alone() -> (
    None
):
    """The public profile omits the embargo register and the Case Owner, so
    the status it shows carries neither the EM state nor its author."""
    (public,) = _dumped_statuses(PUBLIC_PROFILE)
    (joined,) = _dumped_statuses(JOINED_PROFILE)

    assert public["pxaState"] == joined["pxaState"]
    assert set(public) == {"id", "type", "context", "published", "pxaState"}
    assert "emState" in joined


def _dumped_statuses(profile: ProjectionProfile) -> list[dict[str, Any]]:
    preview = CasePreview.for_projection(
        projected_case(), projected_ledger(), profile
    )
    dumped = preview.model_dump(mode="json", by_alias=True, exclude_none=True)
    statuses: list[dict[str, Any]] = dumped["caseStatuses"]
    return statuses


@pytest.mark.parametrize("profile", _PROFILES, ids=lambda p: p.name)
def test_a_projection_preview_names_the_case_and_its_position(
    profile: ProjectionProfile,
) -> None:
    preview = CasePreview.for_projection(
        projected_case(), projected_ledger(), profile
    )

    assert preview.id_ == CASE_ID
    dumped = preview.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert dumped["ledgerPosition"] == POSITION.model_dump(by_alias=True)
    assert isinstance(preview.case_statuses, list)
    assert len(preview.case_statuses) == 1


@pytest.mark.spec("CM-17-025")
def test_the_invitation_cut_carries_no_ledger_or_position() -> None:
    case = projected_case(case_participants=[], embargo_register=[])

    preview = CasePreview.from_case(case, INVITATION_PROFILE)

    assert preview.ledger_position is None
    assert preview.ledger_entries is None


@pytest.mark.spec("CM-17-025")
@pytest.mark.parametrize(
    ("field", "key"),
    [
        ("ledger_position", "ledgerPosition"),
        ("ledger_entries", "ledgerEntries"),
    ],
)
def test_an_invitation_preview_with_ledger_bookkeeping_is_faulted(
    field: str, key: str
) -> None:
    value = (
        {"logIndex": 0, "entryHash": "ab"}
        if field == "ledger_position"
        else [Redacted()]
    )
    preview = CasePreview.model_validate(
        {
            "summary": "A case to join",
            "attributedTo": "https://example.org/actors/owner",
            field: value,
        }
    )

    (fault,) = invitation_preview_faults(preview)
    assert key in fault
    assert "CM-17-025" in fault


# --- the call site's inputs --------------------------------------------------


_ACTOR = ProjectingActor(id_="https://example.org/actors/a", name="A")


def _inputs(**fields: object) -> ProjectionInputs:
    return ProjectionInputs.model_validate(
        {
            "status": PublicationStatus.FINAL,
            "projecting_actor": _ACTOR,
            "position_committed_at": projected_case().published,
            **fields,
        }
    )


@pytest.mark.parametrize("profile", _PROFILES, ids=lambda p: p.name)
def test_a_cut_carries_the_name_and_label_of_its_profile(
    profile: ProjectionProfile,
) -> None:
    """A document cannot be named or labelled by another profile than the
    one that decided what it holds (ADR-0219)."""
    case, ledger = projected_case(), projected_ledger()

    cut = ProjectionCut.of(case, ledger, profile)

    assert (cut.profile_name, cut.distribution) == (
        profile.name,
        profile.distribution,
    )
    assert cut.preview == CasePreview.for_projection(case, ledger, profile)


def test_a_cut_takes_no_name_or_label_apart_from_its_profile() -> None:
    """The name and label are read from the profile the cut holds, so a cut
    cannot state another profile's name or label beside it."""
    preview = CasePreview.for_projection(
        projected_case(), projected_ledger(), JOINED_PROFILE
    )

    with pytest.raises(ValidationError):
        ProjectionCut.model_validate(
            {
                "preview": preview,
                "profile": JOINED_PROFILE,
                "profile_name": PUBLIC_PROFILE.name,
                "distribution": PUBLIC_PROFILE.distribution,
            }
        )
    with pytest.raises(ValidationError):
        ProjectionCut.model_validate(
            {"preview": preview, "profile": PUBLIC_PROFILE.name}
        )


@pytest.mark.spec("CSAF-06-009")
def test_the_callers_credit_comes_before_the_default() -> None:
    caller = Acknowledgment(names=("Pat",))
    default = Acknowledgment(names=("Sam",))

    assert _inputs(
        caller_acknowledgments=[caller], default_acknowledgments=[default]
    ).acknowledgments == (caller,)
    assert _inputs(default_acknowledgments=[default]).acknowledgments == (
        default,
    )
    assert (
        _inputs(
            caller_acknowledgments=[], default_acknowledgments=[default]
        ).acknowledgments
        == ()
    )


def test_an_acknowledgment_that_credits_no_one_is_refused() -> None:
    with pytest.raises(ValueError, match="ADR-0218"):
        Acknowledgment()


@pytest.mark.spec("CSAF-06-009")
def test_the_default_credit_is_the_reporter_participants() -> None:
    credit = reporter_acknowledgments(projected_case())

    assert credit == (
        Acknowledgment(names=(JOINED_ONLY_VALUES["reporter_name"],)),
    )


def test_a_reporter_with_no_name_is_credited_by_its_actor() -> None:
    case = projected_case()
    (reporter,) = [
        p
        for p in case.case_participants
        if not isinstance(p, str) and p.attributed_to == REPORTER
    ]
    reporter.name = None

    assert reporter_acknowledgments(case) == (
        Acknowledgment(names=(REPORTER,)),
    )


def test_a_participant_held_by_id_is_not_credited() -> None:
    case = projected_case()
    case.case_participants = [
        "https://example.org/participants/by-id",
        *case.case_participants,
    ]

    assert reporter_acknowledgments(case) == (
        Acknowledgment(names=(JOINED_ONLY_VALUES["reporter_name"],)),
    )


def test_the_joined_cut_keeps_only_the_ids_an_activity_names() -> None:
    """An object the activity embeds as its actor, recipient or reply
    target is cut to its id, so it is not carried whole."""
    entry = ledger_entry(
        0,
        MessageSemantics.SUBMIT_REPORT,
        actor=REPORTER,
        to=["https://example.org/actors/v"],
    )
    entry.payload_snapshot["actor"] = {"id": REPORTER, "name": "Inline"}
    entry.payload_snapshot["to"] = [
        {"id": "https://example.org/actors/v", "summary": "Inline"},
        {"type": "Note"},
    ]
    entry.payload_snapshot["inReplyTo"] = {
        "id": "https://example.org/activities/x",
        "type": "Offer",
        "object": {"content": PAYLOAD_ONLY_VALUE},
    }

    (cut,) = _entries(
        CasePreview.for_projection(projected_case(), [entry], JOINED_PROFILE)
    )

    assert cut["payloadSnapshot"]["actor"] == REPORTER
    assert cut["payloadSnapshot"]["to"] == ["https://example.org/actors/v"]
    assert cut["payloadSnapshot"]["inReplyTo"] == (
        "https://example.org/activities/x"
    )
    assert "Inline" not in str(cut)
