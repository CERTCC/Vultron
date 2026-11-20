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

"""A preview's contents are loose forms of their classes (ADR-0217).

These rows hold the forms themselves: what :func:`loose_form` derives, that
it leaves the type registries alone, and the case preview's own field set.
How a received preview is read is the parse edge's question, held by
``test/wire/as2/test_redaction_marker.py``.
"""

from typing import Annotated, Any

import pytest
from pydantic import (
    BaseModel,
    Field as PydanticField,
    SerializationInfo,
    ValidationError,
    ValidationInfo,
    field_serializer,
    field_validator,
)

from test.support.objects import make
from vultron.core.models._helpers import INBOUND_CONTEXT_KEY
from vultron.core.models.base import CoreObject
from vultron.core.models.case.vulnerability_case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_preview import (
    CasePreview,
    preview_em_state,
    preview_embargo_id,
)
from vultron.core.models.case_preview_profile import INVITATION_PROFILE
from vultron.core.models.case_reference import CaseReference, CaseReferenceLink
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import EmDimension
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_termination import EmbargoTermination
from vultron.core.models.preview_object import (
    PreviewObject,
    PreviewValue,
    is_loose_form_of,
    loose_form,
    to_loose,
)
from vultron.core.models.redacted import Redacted
from vultron.core.models.registry import CORE_TYPE_MAP, CORE_VOCABULARY
from vultron.core.models.vulnerability_item import (
    VulnerabilityItem,
    VulnerabilityItemId,
)
from vultron.core.states.em import EM

INBOUND = {INBOUND_CONTEXT_KEY: True}
CASE_ID = "https://example.org/cases/1"

#: The case fields a preview never carries: the case's bookkeeping, which
#: means nothing outside the case, and open embargo proposals, relayed after
#: joining (ADR-0217's omit-only rows).
OMIT_ONLY = {
    name for name, rule in INVITATION_PROFILE.items() if rule.omit_only
}


@pytest.mark.parametrize(
    "full",
    [VulnerabilityItem, CaseParticipant, CaseStatus, EmbargoTermination],
)
def test_a_loose_form_has_every_field_of_its_class_under_its_names(
    full: type[BaseModel],
) -> None:
    form = loose_form(full)

    assert set(form.model_fields) >= set(full.model_fields)
    for name, info in full.model_fields.items():
        loose = form.model_fields[name]
        assert loose.serialization_alias == info.serialization_alias, name


@pytest.mark.parametrize("full", [VulnerabilityItem, CaseParticipant])
def test_every_field_of_a_loose_form_but_its_type_is_optional(
    full: type[BaseModel],
) -> None:
    form = loose_form(full)

    # An empty language map is left out of a dump, as on the full class.
    assert form.model_validate({}).model_dump(exclude_none=True) == {
        "type_": full.model_fields["type_"].default
    }


def test_a_loose_form_keeps_its_class_type_and_refuses_another() -> None:
    form = loose_form(VulnerabilityItem)

    assert form.model_validate({}).type_ == "VulnerabilityItem"
    with pytest.raises(ValueError, match="type"):
        form.model_validate({"type": "Note"})


def test_each_class_has_one_loose_form() -> None:
    assert loose_form(VulnerabilityItem) is loose_form(VulnerabilityItem)


def test_a_loose_form_derives_from_the_base_its_kind_takes() -> None:
    assert issubclass(loose_form(VulnerabilityItem), PreviewObject)
    assert issubclass(loose_form(EmbargoTermination), PreviewValue)


def test_a_loose_form_names_its_full_class() -> None:
    form = loose_form(VulnerabilityItem)

    assert form.full_form is VulnerabilityItem
    assert is_loose_form_of(form.model_validate({}), VulnerabilityItem)
    assert not is_loose_form_of(form.model_validate({}), CaseStatus)


@pytest.mark.spec("ARCH-12-010")
def test_a_loose_form_leaves_the_type_registries_to_its_full_class() -> None:
    """The type names the full class a stored row is read back as."""
    form = loose_form(VulnerabilityItem)

    assert CORE_TYPE_MAP["VulnerabilityItem"] is VulnerabilityItem
    assert form not in CORE_TYPE_MAP.values()
    assert form not in CORE_VOCABULARY.values()


def test_a_loose_form_is_not_its_full_class() -> None:
    """A full object is never read as a preview's loose form, nor the
    reverse."""
    form = loose_form(VulnerabilityItem)

    assert not issubclass(form, VulnerabilityItem)
    assert not issubclass(CasePreview, VulnerabilityCase)


def test_a_nested_object_takes_its_own_loose_form() -> None:
    item: Any = loose_form(VulnerabilityItem).model_validate(
        {"ids": [{"systemName": "CVE", "text": "CVE-2026-1234"}]}
    )

    (shown,) = item.ids
    assert is_loose_form_of(shown, VulnerabilityItemId)


@pytest.mark.spec("MV-12-001")
def test_a_loose_form_holds_a_marker_in_a_field_and_a_list_item() -> None:
    item: Any = loose_form(VulnerabilityItem).model_validate(
        {"name": Redacted(), "ids": [Redacted(summary="withheld")]}
    )

    assert item.name == Redacted()
    assert item.ids == [Redacted(summary="withheld")]


@pytest.mark.spec("MV-12-001")
def test_a_marker_in_a_time_field_is_kept_as_a_marker() -> None:
    """The base's timestamp validator and serializer read only times."""
    item = loose_form(VulnerabilityItem).model_validate(
        {"published": Redacted()}
    )

    assert item.model_dump(mode="json", by_alias=True, exclude_none=True)[
        "published"
    ] == {"type": "Redacted"}


def test_a_scalar_dimension_is_shown_whole_or_withheld() -> None:
    """A dimension is written as its bare state, so it has no fields to cut."""
    status: Any = loose_form(CaseStatus).model_validate({"emState": "ACTIVE"})

    assert status.em == EmDimension(state=EM.ACTIVE)
    assert (
        status.model_dump(by_alias=True, exclude_none=True, mode="json")[
            "emState"
        ]
        == "ACTIVE"
    )


@pytest.mark.spec("MV-12-006")
@pytest.mark.spec("OID-01-013")
@pytest.mark.spec("CLP-15-011")
def test_a_loose_form_is_received_without_an_id_or_a_published() -> None:
    """A preview shows what its sender chose: an object without its own id
    or time is read as shown, and none is minted for it (OID-01-014)."""
    item = loose_form(VulnerabilityItem).model_validate(
        {"type": "VulnerabilityItem"}, context=INBOUND
    )

    assert item.id_ is None
    assert item.published is None


@pytest.mark.parametrize("cls", [BaseModel, CoreObject, Redacted, CasePreview])
def test_a_class_with_no_loose_form_is_refused(cls: type) -> None:
    with pytest.raises(TypeError, match="no loose form"):
        loose_form(cls)


def _status() -> CaseStatus:
    return make(CaseStatus, context=CASE_ID, em=EmDimension(state=EM.ACTIVE))


def test_to_loose_shows_every_field_held() -> None:
    status = _status()

    shown = to_loose(status)

    assert is_loose_form_of(shown, CaseStatus)
    assert shown.model_dump(by_alias=True, exclude_none=True, mode="json") == (
        status.model_dump(by_alias=True, exclude_none=True, mode="json")
    )


def test_to_loose_shows_only_the_fields_named() -> None:
    shown = to_loose(_status(), ("context", "em"))

    assert shown.model_dump(by_alias=True, exclude_none=True, mode="json") == {
        "@context": shown.model_dump(by_alias=True, mode="json")["@context"],
        "type": "CaseStatus",
        "context": CASE_ID,
        "emState": "ACTIVE",
    }


def test_the_profile_names_the_known_bookkeeping_as_omit_only() -> None:
    """The omit-only rows are the case's bookkeeping and its open-proposal
    index, so the drift test below is not vacuous."""
    assert {
        "actor_participant_index",
        "pending_embargo_proposal_index",
        "genesis_hash",
        "ledger_position",
        "stub_summary",
    } == OMIT_ONLY


@pytest.mark.spec("MV-12-001")
def test_every_preview_field_is_a_case_field() -> None:
    """The preview carries no field of its own: the embargo in force travels
    as the case's ``embargoRegister`` and the status as its ``caseStatuses``,
    so no ``activeEmbargo`` or ``caseStatus`` remains (ADR-0217)."""
    assert set(CasePreview.model_fields) <= set(VulnerabilityCase.model_fields)
    assert not {"active_embargo", "case_status"} & set(
        CasePreview.model_fields
    )


@pytest.mark.spec("MV-12-001")
def test_every_case_field_is_a_preview_field_or_an_omit_only_row() -> None:
    """A case field is shown in the preview's field of the same name, or it
    is a profile row that permits only omit, which the preview does not
    declare, so a received one is set aside (MV-11-003).  A new case field
    fails here until it is classified."""
    case_fields = set(VulnerabilityCase.model_fields)

    assert case_fields - OMIT_ONLY == set(CasePreview.model_fields)
    assert case_fields >= OMIT_ONLY


#: The case fields of the preview a marker may not stand in: the preview's
#: own identity and the summary every preview carries (MV-10-001).
_NOT_WITHHELD = {"id_", "type_", "summary", "context_"}


@pytest.mark.spec("MV-12-001")
@pytest.mark.parametrize(
    "field",
    sorted(set(VulnerabilityCase.model_fields) - OMIT_ONLY - _NOT_WITHHELD),
)
def test_every_case_field_of_the_preview_holds_a_marker(field: str) -> None:
    preview = CasePreview.model_validate(
        {"summary": "a case", field: Redacted()}
    )

    assert getattr(preview, field) == Redacted()


@pytest.mark.parametrize("field", ["id_", "summary"])
def test_the_preview_identity_and_summary_hold_no_marker(field: str) -> None:
    data = {"summary": "a case", field: Redacted()}

    with pytest.raises(ValueError, match=field.rstrip("_")):
        CasePreview.model_validate(data)


def _shown(status: str, **fields: object) -> PreviewObject:
    """A preview's registered embargo, showing *status* (ADR-0202)."""
    return loose_form(EmbargoEvent).model_validate(
        {"status": status, **fields}
    )


@pytest.mark.parametrize(
    "preview",
    [
        CasePreview(
            summary="a case",
            case_statuses=Redacted(),
            embargo_register=Redacted(),
        ),
        CasePreview(
            summary="a case",
            case_statuses=[Redacted()],
            embargo_register=[Redacted()],
        ),
    ],
    ids=["list marked", "item marked"],
)
def test_the_preview_status_and_embargo_readers_skip_a_marker(
    preview: CasePreview,
) -> None:
    assert preview_em_state(preview) is None
    assert preview_embargo_id(preview) is None


def test_the_preview_embargo_reader_reads_the_shown_active_embargo() -> None:
    shown = CasePreview(
        summary="a case",
        embargo_register=[_shown("ACTIVE", id="urn:uuid:e2")],
    )
    without_id = CasePreview(
        summary="a case", embargo_register=[_shown("ACTIVE")]
    )
    proposed_only = CasePreview(
        summary="a case",
        embargo_register=[_shown("PROPOSED", id="urn:uuid:e3")],
    )

    assert preview_embargo_id(shown) == "urn:uuid:e2"
    assert preview_embargo_id(without_id) is None
    assert preview_embargo_id(proposed_only) is None
    assert preview_embargo_id(object()) is None


def test_the_preview_em_reader_reads_the_current_status() -> None:
    """The EM state is the last shown status's, as the case's own current
    status is its last (CM-29-001)."""
    earlier = make(CaseStatus, context=CASE_ID, em=EmDimension(state=EM.NONE))
    preview = CasePreview(
        summary="a case",
        case_statuses=[to_loose(earlier), to_loose(_status(), ("em",))],
    )

    assert preview_em_state(preview) is EM.ACTIVE


class _Collections(BaseModel):
    """A stand-in value model with each kind of collection field."""

    tags: set[str] = set()
    pair: tuple[str, int] = ("a", 1)
    names: tuple[str, ...] = ()
    scores: dict[str, int] = {}
    anything: Any = None


@pytest.mark.parametrize(
    ("field", "shown"),
    [
        # Built from a tuple: a frozen model hashes, which a set literal
        # cannot show a type checker.
        ("tags", set(("x", Redacted()))),
        ("names", ("x", Redacted())),
        ("scores", {"x": Redacted()}),
    ],
)
def test_a_loose_form_admits_a_marker_as_a_collection_item(
    field: str, shown: object
) -> None:
    form = loose_form(_Collections)

    assert getattr(form.model_validate({field: shown}), field) == shown


def test_a_loose_form_keeps_a_fixed_tuple_and_an_any_field_as_declared() -> (
    None
):
    """A fixed-length tuple has no item type to loosen, and ``Any`` already
    admits a marker."""
    form = loose_form(_Collections)

    assert form.model_validate({"pair": ("b", 2)}).model_dump()["pair"] == (
        "b",
        2,
    )
    shown: Any = form.model_validate({"anything": Redacted()})
    assert shown.anything == Redacted()


@pytest.mark.spec("MV-10-001")
@pytest.mark.spec("OID-01-013")
def test_a_received_case_preview_still_needs_its_own_id() -> None:
    """The case preview is a whole object of its own: only what it shows is
    read without an id (MV-12-006)."""
    with pytest.raises(ValueError, match="carries no 'id'"):
        CasePreview.model_validate(
            {"type": "CasePreview", "summary": "a case"}, context=INBOUND
        )


def test_a_loose_form_sends_no_field_its_full_class_keeps_local() -> None:
    """``ParticipantStatus.force_rm_state`` is excluded from every dump, so
    its loose form leaves it out too."""
    from vultron.core.models.participant_status import ParticipantStatus

    form = loose_form(ParticipantStatus)
    shown = form.model_validate({"force_rm_state": True})

    assert "forceRmState" not in shown.model_dump(by_alias=True)


def test_a_loose_form_loosens_a_field_its_class_narrows() -> None:
    """``CaseReference.url`` holds a Link, not the base's string, so its
    loose form holds a loose Link and a whole reference survives it."""
    reference = make(
        CaseReference, url=CaseReferenceLink(href="https://example.org/x")
    )

    shown = to_loose(reference)

    assert shown.model_dump(by_alias=True, exclude_none=True, mode="json")[
        "url"
    ] == {"type": "Link", "href": "https://example.org/x", "rel": []}


def test_to_loose_refuses_a_field_its_class_lacks() -> None:
    with pytest.raises(ValueError, match="no field"):
        to_loose(_status(), ("context", "emStatus"))


def test_a_class_whose_fields_name_it_again_has_a_loose_form() -> None:
    """``as_Object.tag`` holds ``as_Object``s: the form names itself by a
    reference, resolved once it is built, so the derivation ends and the
    form holds a loose object at every depth.  Which loose form a typed
    object takes is the parse edge's choice (``test_redaction_marker.py``).
    """
    from vultron.wire.as2.vocab.base.objects.base import as_Object
    from vultron.wire.as2.vocab.base.objects.object_types import as_Note

    note: Any = loose_form(as_Note).model_validate(
        {
            "content": Redacted(),
            "tag": [{"type": "Note", "tag": [{"type": "Note"}]}],
        }
    )

    assert note.content == Redacted()
    (inner,) = note.tag
    (innermost,) = inner.tag
    assert isinstance(innermost, loose_form(as_Object))


def test_a_loose_subclass_is_read_where_its_parents_loose_form_is() -> None:
    """A subclass's form extends its parent's, so a field declaring the
    parent's loose form holds the subclass's."""
    from vultron.core.models.case_participant.roles import VendorParticipant
    from vultron.wire.as2.vocab.base.objects.base import as_Object
    from vultron.wire.as2.vocab.base.objects.object_types import as_Note

    assert issubclass(loose_form(as_Note), loose_form(as_Object))
    assert issubclass(
        loose_form(VendorParticipant), loose_form(CaseParticipant)
    )


def test_a_loose_form_extends_no_mixin_its_class_shares() -> None:
    """A mixin without fields, and the record base every object shares, are
    not a loose form's base: an object's form extends the loose object, a
    value's the loose value."""
    from vultron.core.models.base.record import CoreRecord

    item_form = loose_form(VulnerabilityItem)

    assert PreviewObject in item_form.__bases__
    assert not any(
        is_loose_form_of(base, CoreRecord) for base in item_form.__mro__
    )


@pytest.mark.parametrize(
    ("status", "shown_as"),
    [
        ({"cvdRole": ["VENDOR"]}, ["VENDOR"]),
        ({"cvdRole": ["vendor", Redacted()]}, ["VENDOR", Redacted()]),
        (
            {"cvdRole": [{"type": "Redacted"}, "vendor"]},
            [Redacted(), "VENDOR"],
        ),
    ],
)
def test_a_loose_form_reads_and_writes_a_value_as_its_full_class(
    status: dict[str, Any], shown_as: list[object]
) -> None:
    """The full class's reading rule (a role by name or value) and writing
    rule (a role by name) are carried, a marker passed by in its place."""
    from vultron.core.models.participant_status import ParticipantStatus

    shown = loose_form(ParticipantStatus).model_validate(status)

    assert shown.model_dump(by_alias=True)["cvdRole"] == [
        item.model_dump(by_alias=True) if isinstance(item, Redacted) else item
        for item in shown_as
    ]


def test_to_loose_shows_a_value_its_full_class_writes_its_own_way() -> None:
    """``to_loose`` reads back the full class's own dump, so a role written
    by name is read by name."""
    from vultron.core.models.participant_status import ParticipantStatus
    from vultron.enums import CVDRole

    status = make(
        ParticipantStatus, context=CASE_ID, cvd_role=[CVDRole.VENDOR]
    )

    shown = to_loose(status, ("cvd_role",))

    assert shown.model_dump(by_alias=True)["cvdRole"] == ["VENDOR"]


class _Deduped(BaseModel):
    """A stand-in whose reading rule changes how many items there are."""

    names: list[str] = []

    @field_validator("names", mode="before")
    @classmethod
    def _once_each(cls, value: Any) -> Any:
        return list(dict.fromkeys(value)) if isinstance(value, list) else value


def test_a_rule_that_changes_the_item_count_reads_the_whole_list() -> None:
    """Markers cannot keep their places when the rule drops an item, so the
    rule is given the whole list, markers and all, and decides."""
    form = loose_form(_Deduped)

    shown: Any = form.model_validate({"names": ["a", "a", Redacted()]})

    assert shown.names == ["a", Redacted()]


class _WithInfo(BaseModel):
    """A stand-in whose reading and writing rules take pydantic's info."""

    label: str = "x"

    @field_validator("label", mode="before")
    @classmethod
    def _read(cls, value: Any, info: ValidationInfo) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_serializer("label")
    def _write(self, value: str, info: SerializationInfo) -> str:
        return value.upper()


def test_a_rule_that_takes_info_is_carried_with_it() -> None:
    form = loose_form(_WithInfo)

    shown = form.model_validate({"label": " a "})

    assert shown.model_dump()["label"] == "A"


class _Parent(BaseModel):
    """A stand-in whose field names its own subclass."""

    name: str = "parent"
    child: _Child | None = None


class _Child(_Parent):
    age: int = 0


_Parent.model_rebuild()


def test_a_subclass_named_by_its_parent_is_derived_after_the_parent() -> None:
    """The subclass's form extends the parent's, which is still being built
    when the parent's field names it, so it is derived once the parent is."""
    parent: Any = loose_form(_Parent).model_validate(
        {"child": {"name": Redacted(), "age": 3}}
    )

    assert issubclass(loose_form(_Child), loose_form(_Parent))
    assert is_loose_form_of(parent.child, _Child)
    assert parent.child.name == Redacted()


def test_a_discriminated_union_keeps_its_discriminator() -> None:
    """A termination cause is chosen by its ``kind``: each loose member keeps
    its ``kind`` as declared, and a cut-down cause is read as the member it
    names."""
    from vultron.core.models.embargo_termination import (
        EmbargoTermination,
        FixReadyCause,
    )

    form = loose_form(EmbargoTermination)

    shown: Any = form.model_validate(
        {"cause": {"kind": "FIX_READY", "vendors": [Redacted()]}}
    )
    assert is_loose_form_of(shown.cause, FixReadyCause)
    assert shown.cause.vendors == [Redacted()]
    withheld: Any = form.model_validate({"cause": Redacted()})
    assert withheld.cause == Redacted()


class _Annotated(BaseModel):
    """A stand-in with annotated fields that name no model."""

    count: Annotated[int, PydanticField(ge=0)] | None = None
    any_model: BaseModel | None = None


def test_an_annotation_naming_no_model_keeps_its_constraints() -> None:
    """Loosening rebuilds only an ``Annotated`` that names a model, so a
    constraint on any other value still holds."""
    form = loose_form(_Annotated)

    with pytest.raises(ValidationError):
        form.model_validate({"count": -1})


def test_a_field_holding_any_model_holds_it_as_declared() -> None:
    """``BaseModel`` stands for any model, as ``CoreObject`` does for any
    object, so it has no loose form of its own."""
    held = _status()

    shown: Any = loose_form(_Annotated).model_validate({"any_model": held})

    assert shown.any_model is held


def test_the_loose_object_keeps_the_type_it_was_given() -> None:
    """An object read as the loose object, because its ``type`` names nothing
    known, keeps that ``type``, or none, rather than taking the base's name."""
    assert PreviewObject.model_validate({"content": "x"}).type_ is None
    assert (
        PreviewObject.model_validate({"type": "NoSuchType"}).type_
        == "NoSuchType"
    )
