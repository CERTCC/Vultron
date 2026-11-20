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
"""A case preview cut for a projection renders to a CSAF Base document.

The CSAF renderer of ADR-0219 reads only the preview and its call site's
inputs (CSAF-06).
"""

import json
from datetime import UTC, datetime
from functools import cache
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry
from referencing.jsonschema import DRAFT202012

from test.support.case_projection import (
    CASE_ID,
    COMMITTED_AT,
    COORDINATOR,
    JOINED_ONLY_VALUES,
    PAYLOAD_ONLY_VALUE,
    POSITION,
    PROJECTOR,
    REPORTER,
    VENDOR,
    ledger_entry,
    projected_case,
    projected_ledger,
)
from test.support.objects import make
from vultron.core.models.case_preview import CasePreview
from vultron.core.models.case_projection import (
    Acknowledgment,
    ProjectingActor,
    ProjectionCut,
    ProjectionInputs,
    PublicationStatus,
)
from vultron.core.models.case_projection_profile import (
    JOINED_LEDGER_ACTS,
    JOINED_PROFILE,
    PUBLIC_PROFILE,
    ProjectionProfile,
)
from vultron.core.models.case_reference import CaseReference, CaseReferenceLink
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.redacted import Redacted
from vultron.core.models.vulnerability_item import (
    VulnerabilityItem,
    VulnerabilityItemId,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronValidationError
from vultron.metadata.csaf.pin import PINNED_COPY_DIR, load_pin
from vultron.wire.csaf.projection import (
    ACTION_CATEGORIES,
    ACTION_SUMMARIES,
    render_csaf,
    role_category,
    tracking_id,
)

_PROFILES = [PUBLIC_PROFILE, JOINED_PROFILE]
_STATUS = {
    PUBLIC_PROFILE.name: PublicationStatus.FINAL,
    JOINED_PROFILE.name: PublicationStatus.INTERIM,
}


def _position(log_index: object, entry_hash: str) -> Any:
    """A preview's ledger position, as a received preview shows it."""
    return CasePreview.model_validate(
        {"ledgerPosition": {"logIndex": log_index, "entryHash": entry_hash}}
    ).ledger_position


@cache
def _validator() -> Draft202012Validator:
    """A validator of the pinned CSAF 2.1 schema, reading every schema it
    references from the pinned local copy."""
    pin = load_pin()
    # Every schema of the copy is read as draft 2020-12, the dialect the
    # CSAF meta-schema extends.
    resources = [
        (
            url,
            DRAFT202012.create_resource(
                json.loads((PINNED_COPY_DIR / path).read_bytes())
            ),
        )
        for url, path in pin.sources.items()
    ]
    registry: Registry[Any] = Registry().with_resources(resources)
    root = json.loads((PINNED_COPY_DIR / pin.root).read_bytes())
    return Draft202012Validator(
        root, registry=registry, format_checker=FormatChecker()
    )


def _inputs(profile: ProjectionProfile, **fields: Any) -> ProjectionInputs:
    defaults: dict[str, Any] = {
        "status": _STATUS[profile.name],
        "projecting_actor": PROJECTOR,
        "position_committed_at": COMMITTED_AT,
    }
    return ProjectionInputs(**{**defaults, **fields})


def _preview(profile: ProjectionProfile, **case_fields: Any) -> CasePreview:
    return CasePreview.for_projection(
        projected_case(**case_fields), projected_ledger(), profile
    )


def _cut(preview: CasePreview, profile: ProjectionProfile) -> ProjectionCut:
    """*preview* as a cut by *profile*, built by hand."""
    return ProjectionCut(
        preview=preview,
        profile_name=profile.name,
        distribution=profile.distribution,
    )


def _csaf(
    preview: CasePreview,
    inputs: ProjectionInputs,
    profile: ProjectionProfile = PUBLIC_PROFILE,
) -> dict[str, Any]:
    """The rendered document, read as plain JSON."""
    rendered: dict[str, Any] = render_csaf(_cut(preview, profile), inputs)
    return rendered


def _render(profile: ProjectionProfile, **inputs: Any) -> dict[str, Any]:
    cut = ProjectionCut.of(projected_case(), projected_ledger(), profile)
    rendered: dict[str, Any] = render_csaf(cut, _inputs(profile, **inputs))
    return rendered


def _document(rendered: dict[str, Any]) -> dict[str, Any]:
    document = rendered["document"]
    assert isinstance(document, dict)
    return document


def _text(rendered: dict[str, Any]) -> str:
    return json.dumps(rendered)


# --- AC-3: schema-valid csaf_base -----------------------------------------


@pytest.mark.spec("CSAF-06-004")
@pytest.mark.parametrize("profile", _PROFILES, ids=lambda p: p.name)
def test_each_profiles_projection_passes_the_pinned_schema(
    profile: ProjectionProfile,
) -> None:
    rendered = _render(profile)

    errors = [error.message for error in _validator().iter_errors(rendered)]
    assert errors == []
    assert _document(rendered)["category"] == "csaf_base"


def test_the_schema_check_is_not_vacuous() -> None:
    """The validator the tests above use refuses an invalid document: a
    vulnerability with no member (``minProperties``), which the generated
    models admit."""
    rendered = _render(PUBLIC_PROFILE)
    rendered["vulnerabilities"] = [{}]

    assert not _validator().is_valid(rendered)


@pytest.mark.spec("CSAF-06-001")
def test_the_renderer_needs_no_case_only_a_preview_and_inputs() -> None:
    """A preview built by hand, with no case behind it, renders: the
    renderer reads only what it is given."""
    preview = CasePreview(
        id_=CASE_ID,
        name="A hand-built preview",
        ledger_position=_position(0, "ef" * 32),
    )

    rendered = _csaf(preview, _inputs(PUBLIC_PROFILE))

    assert _validator().is_valid(rendered)
    assert _document(rendered)["title"] == "A hand-built preview"


@pytest.mark.spec("CSAF-06-001")
@pytest.mark.parametrize(
    "preview",
    [
        CasePreview(id_=CASE_ID),
        CasePreview(id_=CASE_ID, ledger_position=Redacted()),
        CasePreview(id_=CASE_ID, ledger_position=_position(Redacted(), "ef")),
    ],
    ids=["no position", "withheld position", "withheld log index"],
)
def test_a_preview_with_no_identity_is_refused(preview: CasePreview) -> None:
    with pytest.raises(VultronValidationError, match="ADR-0219"):
        _csaf(preview, _inputs(PUBLIC_PROFILE))


def test_a_projecting_actor_with_no_origin_is_refused() -> None:
    actor = ProjectingActor(id_="urn:uuid:no-origin", name="Nobody")

    with pytest.raises(VultronValidationError, match="origin"):
        _render(PUBLIC_PROFILE, projecting_actor=actor)


# --- AC-4: what the profile withholds is absent -----------------------------


@pytest.mark.spec("CSAF-06-002")
@pytest.mark.parametrize("value", sorted(JOINED_ONLY_VALUES.values()))
def test_a_value_the_public_profile_omits_appears_nowhere(value: str) -> None:
    joined = _text(_render(JOINED_PROFILE))
    public = _text(_render(PUBLIC_PROFILE))

    assert value in joined, "the fixture's value reaches the joined document"
    assert value not in public


@pytest.mark.spec("CSAF-06-002")
@pytest.mark.parametrize("profile", _PROFILES, ids=lambda p: p.name)
def test_a_value_only_a_ledger_payload_holds_appears_nowhere(
    profile: ProjectionProfile,
) -> None:
    assert PAYLOAD_ONLY_VALUE not in _text(_render(profile))


@pytest.mark.spec("CSAF-06-002")
@pytest.mark.parametrize("profile", _PROFILES, ids=lambda p: p.name)
def test_the_case_bookkeeping_appears_nowhere(
    profile: ProjectionProfile,
) -> None:
    case = projected_case()
    text = _text(_render(profile))

    assert "The stub summary an invitee reads" not in text
    assert case.genesis_hash not in text


@pytest.mark.spec("CSAF-06-002")
def test_a_redacted_field_renders_as_an_absence_with_no_note() -> None:
    preview = _preview(JOINED_PROFILE).model_copy(
        update={
            "content": Redacted(),
            "vulnerability_reports": Redacted(),
            "case_references": [Redacted()],
        }
    )

    document = _document(
        _csaf(preview, _inputs(JOINED_PROFILE), JOINED_PROFILE)
    )

    assert [note["category"] for note in document["notes"]] == ["summary"]
    assert [ref["category"] for ref in document["references"]] == ["self"]
    assert "Redacted" not in json.dumps(document)


# --- AC-5: a pure function of its identity ---------------------------------


@pytest.mark.spec("CSAF-06-005")
@pytest.mark.parametrize("profile", _PROFILES, ids=lambda p: p.name)
def test_the_same_inputs_give_an_identical_document(
    profile: ProjectionProfile,
) -> None:
    preview = _preview(profile)
    inputs = _inputs(profile)

    assert _csaf(preview, inputs, profile) == _csaf(preview, inputs, profile)
    assert _render(profile) == _render(profile)


@pytest.mark.spec("CSAF-06-005")
def test_the_tracking_id_derives_from_case_profile_and_log_index() -> None:
    tracking = _document(_render(PUBLIC_PROFILE))["tracking"]

    assert tracking["id"] == f"{CASE_ID}/public-v1/{POSITION.log_index}"


def _tracking_id(
    preview: CasePreview,
    inputs: ProjectionInputs,
    profile: ProjectionProfile = PUBLIC_PROFILE,
) -> str:
    return str(_document(_csaf(preview, inputs, profile))["tracking"]["id"])


@pytest.mark.spec("CSAF-06-005")
def test_a_different_log_index_profile_or_credit_gives_another_id() -> None:
    preview = _preview(PUBLIC_PROFILE)
    inputs = _inputs(PUBLIC_PROFILE)
    later = preview.model_copy(
        update={"ledger_position": _position(8, "12" * 32)}
    )
    credited = _inputs(
        PUBLIC_PROFILE,
        caller_acknowledgments=[Acknowledgment(names=("Pat Finder",))],
    )
    other_credit = _inputs(
        PUBLIC_PROFILE,
        caller_acknowledgments=[Acknowledgment(names=("Sam Finder",))],
    )
    bumped = ProjectionProfile(
        name="public-v2",
        distribution=PUBLIC_PROFILE.distribution,
        fields=PUBLIC_PROFILE.fields,
    )

    ids = [
        _tracking_id(preview, inputs),
        _tracking_id(later, inputs),
        _tracking_id(preview, inputs, bumped),
        _tracking_id(preview, credited),
        _tracking_id(preview, other_credit),
    ]

    assert len(set(ids)) == len(ids)


@pytest.mark.spec("CSAF-06-005")
def test_the_default_credit_adds_no_digest_but_caller_credit_does() -> None:
    reporter = Acknowledgment(names=("Pat Reporter",))
    default = _inputs(PUBLIC_PROFILE, default_acknowledgments=[reporter])
    caller = _inputs(PUBLIC_PROFILE, caller_acknowledgments=[reporter])
    none_credited = _inputs(PUBLIC_PROFILE, caller_acknowledgments=[])
    preview = _preview(PUBLIC_PROFILE)

    assert _tracking_id(preview, default) == _tracking_id(
        preview, _inputs(PUBLIC_PROFILE)
    )
    assert _tracking_id(preview, caller).startswith(
        f"{CASE_ID}/public-v1/7/ack-"
    )
    assert _tracking_id(preview, none_credited) != _tracking_id(
        preview, default
    )


def test_tracking_id_names_its_parts_in_order() -> None:
    assert tracking_id("https://x.org/c", "joined-v1", 3, None) == (
        "https://x.org/c/joined-v1/3"
    )


@pytest.mark.spec("CSAF-06-006")
@pytest.mark.parametrize("profile", _PROFILES, ids=lambda p: p.name)
def test_every_projection_is_version_one_with_one_revision(
    profile: ProjectionProfile,
) -> None:
    tracking = _document(_render(profile))["tracking"]

    assert tracking["version"] == "1"
    assert [entry["number"] for entry in tracking["revision_history"]] == ["1"]


@pytest.mark.spec("CSAF-06-007")
@pytest.mark.parametrize("profile", _PROFILES, ids=lambda p: p.name)
def test_every_document_date_is_the_positions_commit_time(
    profile: ProjectionProfile,
) -> None:
    tracking = _document(_render(profile))["tracking"]
    dates = {
        tracking["initial_release_date"],
        tracking["current_release_date"],
        *(entry["date"] for entry in tracking["revision_history"]),
    }

    assert {datetime.fromisoformat(date) for date in dates} == {COMMITTED_AT}


@pytest.mark.spec("CSAF-06-007")
def test_a_later_commit_time_moves_every_document_date() -> None:
    later = datetime(2027, 1, 1, tzinfo=UTC)

    tracking = _document(_render(PUBLIC_PROFILE, position_committed_at=later))[
        "tracking"
    ]

    assert datetime.fromisoformat(tracking["current_release_date"]) == later
    assert datetime.fromisoformat(tracking["initial_release_date"]) == later


@pytest.mark.spec("CSAF-06-008")
@pytest.mark.parametrize("profile", _PROFILES, ids=lambda p: p.name)
def test_a_self_reference_names_the_case_and_the_entry_hash(
    profile: ProjectionProfile,
) -> None:
    references = _document(_render(profile))["references"]
    (own,) = [ref for ref in references if ref["category"] == "self"]

    assert own["url"] == CASE_ID
    assert POSITION.entry_hash in own["summary"]


# --- acknowledgments --------------------------------------------------------


@pytest.mark.spec("CSAF-06-009")
def test_the_document_credits_the_caller_over_the_default() -> None:
    caller = Acknowledgment(organization="Example Lab", summary="Found it.")
    default = Acknowledgment(names=("Pat Reporter",))

    document = _document(
        _render(
            PUBLIC_PROFILE,
            caller_acknowledgments=[caller],
            default_acknowledgments=[default],
        )
    )

    assert document["acknowledgments"] == [
        {"organization": "Example Lab", "summary": "Found it."}
    ]


@pytest.mark.spec("CSAF-06-009")
def test_with_no_caller_credit_the_document_credits_the_default() -> None:
    default = Acknowledgment(names=("Pat Reporter",))

    document = _document(
        _render(PUBLIC_PROFILE, default_acknowledgments=[default])
    )

    assert document["acknowledgments"] == [{"names": ["Pat Reporter"]}]


@pytest.mark.spec("CSAF-06-009")
def test_a_caller_that_credits_no_one_gives_no_acknowledgments() -> None:
    default = Acknowledgment(names=("Pat Reporter",))

    document = _document(
        _render(
            PUBLIC_PROFILE,
            caller_acknowledgments=[],
            default_acknowledgments=[default],
        )
    )

    assert "acknowledgments" not in document


# --- AC-6: involvement, TLP, publisher -------------------------------------


@pytest.mark.spec("CSAF-06-010")
def test_each_act_with_a_csaf_meaning_is_one_completed_action() -> None:
    involvement = _document(_render(JOINED_PROFILE))["involvement"]
    actions = involvement["actions"]

    assert [(a["action_id"], a["category"]) for a in actions] == [
        ("ACT-0", "notification"),
        ("ACT-1", "assessment"),
        ("ACT-3", "embargo"),
    ]
    assert {action["status"] for action in actions} == {"completed"}
    assert actions[1]["referenced_action_ids"] == ["ACT-0"]


def test_an_action_names_its_actor_and_recipients_as_entities() -> None:
    involvement = _document(_render(JOINED_PROFILE))["involvement"]
    entities = {
        entity["entity_id"]: entity for entity in involvement["entities"]
    }
    embargo = involvement["actions"][2]

    (actor,) = embargo["acting_entity_refs"]
    assert entities[actor]["category"] == "coordinator"
    # The actor is never also a recipient (CSAF test 6.1.64.4).
    assert actor not in embargo["receiving_entity_refs"]
    assert {
        entities[ref]["name"] for ref in embargo["receiving_entity_refs"]
    } == {"Example Vendor", JOINED_ONLY_VALUES["reporter_name"]}


def test_an_acts_later_entry_joins_its_first() -> None:
    first = ledger_entry(0, MessageSemantics.SUBMIT_REPORT, actor=REPORTER)
    again = first.model_copy(update={"log_index": 1})
    preview = CasePreview.for_projection(
        projected_case(), [first, again], JOINED_PROFILE
    )

    document = _document(
        _csaf(preview, _inputs(JOINED_PROFILE), JOINED_PROFILE)
    )

    assert [a["action_id"] for a in document["involvement"]["actions"]] == [
        "ACT-0"
    ]


def test_an_act_with_no_actor_is_left_out() -> None:
    entry = ledger_entry(0, MessageSemantics.SUBMIT_REPORT, actor=REPORTER)
    entry.payload_snapshot.pop("actor")
    preview = CasePreview.for_projection(
        projected_case(), [entry], JOINED_PROFILE
    )

    document = _document(
        _csaf(preview, _inputs(JOINED_PROFILE), JOINED_PROFILE)
    )

    assert "involvement" not in document


def test_an_act_with_no_claimed_time_is_dated_by_its_commit() -> None:
    entry = ledger_entry(0, MessageSemantics.SUBMIT_REPORT, actor=REPORTER)
    entry.payload_snapshot.pop("published")
    preview = CasePreview.for_projection(
        projected_case(), [entry], JOINED_PROFILE
    )

    document = _document(
        _csaf(preview, _inputs(JOINED_PROFILE), JOINED_PROFILE)
    )
    (action,) = document["involvement"]["actions"]

    assert datetime.fromisoformat(action["date"]) == COMMITTED_AT


@pytest.mark.spec("CSAF-06-010")
def test_the_public_projection_has_no_involvement() -> None:
    assert "involvement" not in _document(_render(PUBLIC_PROFILE))


def test_the_renderer_maps_every_act_the_joined_profile_keeps() -> None:
    assert set(ACTION_CATEGORIES) == JOINED_LEDGER_ACTS


@pytest.mark.spec("CSAF-06-011")
@pytest.mark.parametrize(
    ("profile", "label"),
    [(PUBLIC_PROFILE, "CLEAR"), (JOINED_PROFILE, "AMBER+STRICT")],
    ids=lambda value: getattr(value, "name", value),
)
def test_the_tlp_label_is_fixed_by_the_profile(
    profile: ProjectionProfile, label: str
) -> None:
    distribution = _document(_render(profile))["distribution"]

    assert distribution["tlp"]["label"] == label


@pytest.mark.parametrize(
    ("roles", "category"),
    [
        ((CVDRole.REPORTER, CVDRole.VENDOR), "vendor"),
        ((CVDRole.REPORTER, CVDRole.COORDINATOR), "coordinator"),
        ((CVDRole.REPORTER,), "discoverer"),
        ((CVDRole.DEPLOYER,), "other"),
        ((), "other"),
    ],
)
def test_the_publisher_category_follows_the_first_role_held(
    roles: tuple[CVDRole, ...], category: str
) -> None:
    actor = ProjectingActor(id_=VENDOR, name="Example Vendor", roles=roles)

    publisher = _document(_render(PUBLIC_PROFILE, projecting_actor=actor))[
        "publisher"
    ]

    assert role_category(roles) == category
    assert publisher["category"] == category
    assert publisher["name"] == "Example Vendor"
    assert publisher["namespace"].rstrip("/") == "https://vendor.example.org"


def test_the_publisher_namespace_is_the_actors_origin() -> None:
    publisher = _document(_render(PUBLIC_PROFILE))["publisher"]

    assert (
        publisher["namespace"].rstrip("/") == (COORDINATOR.split("/actors")[0])
    )


@pytest.mark.parametrize("profile", _PROFILES, ids=lambda p: p.name)
def test_the_status_is_the_call_sites(profile: ProjectionProfile) -> None:
    tracking = _document(_render(profile))["tracking"]

    assert tracking["status"] == _STATUS[profile.name].value


# --- the vulnerability --------------------------------------------------------


def test_each_vul_item_renders_its_ids_title_and_notes() -> None:
    (vulnerability,) = _render(PUBLIC_PROFILE)["vulnerabilities"]

    assert vulnerability["cve"] == "CVE-2026-1234"
    assert vulnerability["ids"] == [
        {"system_name": "Example tracker", "text": "EX-17"}
    ]
    assert vulnerability["title"] == "Parser overflow"
    assert vulnerability["notes"][0]["title"] == "What goes wrong"


def test_only_the_joined_projection_dates_the_embargos_end() -> None:
    (public,) = _render(PUBLIC_PROFILE)["vulnerabilities"]
    (joined,) = _render(JOINED_PROFILE)["vulnerabilities"]

    assert "disclosure_date" not in public
    assert "disclosure_date" in joined


def test_a_case_with_no_vul_items_has_no_vulnerabilities() -> None:
    preview = CasePreview.for_projection(
        projected_case(vulnerability_items=[]), [], PUBLIC_PROFILE
    )

    rendered = _csaf(preview, _inputs(PUBLIC_PROFILE))

    assert "vulnerabilities" not in rendered
    assert _validator().is_valid(rendered)


def test_a_case_with_no_name_is_titled_by_its_id() -> None:
    preview = CasePreview.for_projection(
        projected_case(name=None), [], PUBLIC_PROFILE
    )

    document = _document(_csaf(preview, _inputs(PUBLIC_PROFILE)))

    assert document["title"] == f"Vultron case {CASE_ID}"


def test_the_position_is_read_from_the_preview() -> None:
    position = LedgerPosition(log_index=11, entry_hash="99" * 32)
    preview = CasePreview.for_projection(
        projected_case(ledger_position=position), [], PUBLIC_PROFILE
    )

    tracking = _document(_csaf(preview, _inputs(PUBLIC_PROFILE)))["tracking"]

    assert tracking["id"].endswith("/public-v1/11")


def test_an_action_that_loses_a_distinction_says_it_in_its_summary() -> None:
    actions = _document(_render(JOINED_PROFILE))["involvement"]["actions"]
    by_id = {action["action_id"]: action for action in actions}

    assert (
        by_id["ACT-1"]["summary"]
        == ACTION_SUMMARIES[MessageSemantics.VALIDATE_REPORT.value]
    )
    assert "summary" not in by_id["ACT-0"]


def test_a_case_reference_renders_as_an_external_reference() -> None:
    references = _document(_render(PUBLIC_PROFILE))["references"]

    assert references[1:] == [
        {
            "category": "external",
            "summary": "The vendor's bulletin",
            "url": "https://vendor.example.org/bulletins/17",
        }
    ]


def test_a_reference_with_no_name_is_summarized_by_its_url() -> None:
    reference = make(
        CaseReference,
        context=CASE_ID,
        url=CaseReferenceLink(href="https://example.org/advisory"),
    )
    preview = CasePreview.for_projection(
        projected_case(case_references=[reference]), [], PUBLIC_PROFILE
    )

    references = _document(_csaf(preview, _inputs(PUBLIC_PROFILE)))[
        "references"
    ]

    assert references[1]["summary"] == "https://example.org/advisory"


def test_a_vul_items_own_references_render_on_its_vulnerability() -> None:
    reference = make(
        CaseReference,
        context=CASE_ID,
        name="The item's write-up",
        url=CaseReferenceLink(href="https://example.org/items/1"),
    )
    item = make(
        VulnerabilityItem,
        context=CASE_ID,
        ids=[VulnerabilityItemId.cve("CVE-2026-9999")],
        references=[reference, "https://example.org/references/by-id"],
    )
    preview = CasePreview.for_projection(
        projected_case(vulnerability_items=[item]), [], PUBLIC_PROFILE
    )

    rendered = _csaf(preview, _inputs(PUBLIC_PROFILE))
    (vulnerability,) = rendered["vulnerabilities"]

    assert vulnerability == {
        "cve": "CVE-2026-9999",
        "references": [
            {
                "category": "external",
                "summary": "The item's write-up",
                "url": "https://example.org/items/1",
            }
        ],
    }
    assert _validator().is_valid(rendered)


def test_a_vul_item_with_nothing_shown_is_left_out() -> None:
    preview = _preview(PUBLIC_PROFILE).model_copy(
        update={
            "vulnerability_items": [
                Redacted(),
                "https://example.org/items/by-id",
                {"ids": [Redacted()], "vulNotes": [{"content": Redacted()}]},
            ]
        }
    )
    preview = CasePreview.model_validate(
        preview.model_dump(by_alias=True, exclude_none=True)
    )

    assert "vulnerabilities" not in _csaf(preview, _inputs(PUBLIC_PROFILE))


def test_an_act_with_no_time_at_all_is_left_out() -> None:
    preview = CasePreview.model_validate(
        {
            "id": CASE_ID,
            "ledgerPosition": {"logIndex": 0, "entryHash": "ef"},
            "ledgerEntries": [
                {
                    "type": "CaseLedgerEntry",
                    "logIndex": 0,
                    "semanticType": MessageSemantics.SUBMIT_REPORT.value,
                    "payloadSnapshot": {
                        "id": "https://example.org/activities/0",
                        "actor": REPORTER,
                        "published": "not a time",
                    },
                }
            ],
        }
    )

    document = _document(
        _csaf(preview, _inputs(JOINED_PROFILE), JOINED_PROFILE)
    )

    assert "involvement" not in document
