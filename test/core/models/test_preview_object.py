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

from typing import Any

import pytest
from pydantic import BaseModel

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
from vultron.core.models.case_reference import CaseReference, CaseReferenceLink
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import EmDimension
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_register import EmbargoRegisterEntry
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
    "actor_participant_index",
    "pending_embargo_proposal_index",
    "case_activity",
    "genesis_hash",
    "ledger_position",
    "stub_summary",
}


@pytest.mark.parametrize(
    "full",
    [VulnerabilityItem, CaseParticipant, CaseStatus, EmbargoRegisterEntry],
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
    assert issubclass(loose_form(EmbargoRegisterEntry), PreviewValue)


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
        {"title": Redacted(), "ids": [Redacted(summary="withheld")]}
    )

    assert item.title == Redacted()
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


@pytest.mark.parametrize("cls", [CoreObject, Redacted, CasePreview])
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


@pytest.mark.spec("MV-12-001")
def test_the_case_preview_has_every_case_field_but_its_bookkeeping() -> None:
    """The preview is the case's fields under the case's names (ADR-0217);
    the omit-only rows are not declared, so a received one is set aside."""
    case_fields = set(VulnerabilityCase.model_fields) - OMIT_ONLY

    assert case_fields <= set(CasePreview.model_fields)
    assert not OMIT_ONLY & set(CasePreview.model_fields)


def test_the_case_preview_still_carries_todays_embargo_terms() -> None:
    """``activeEmbargo`` and ``caseStatus`` stay until #6692 moves the terms
    into the case's own fields."""
    assert {"active_embargo", "case_status"} <= set(CasePreview.model_fields)


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


def test_the_preview_status_and_embargo_readers_skip_a_marker() -> None:
    preview = CasePreview(
        summary="a case", case_status=Redacted(), active_embargo=Redacted()
    )

    assert preview_em_state(preview) is None
    assert preview_embargo_id(preview) is None


def test_the_preview_embargo_reader_reads_an_id_or_a_shown_embargo() -> None:
    embargo_form = loose_form(EmbargoEvent)
    by_id = CasePreview(summary="a case", active_embargo="urn:uuid:e1")
    shown = CasePreview(
        summary="a case",
        active_embargo=embargo_form.model_validate({"id": "urn:uuid:e2"}),
    )
    without_id = CasePreview(
        summary="a case", active_embargo=embargo_form.model_validate({})
    )

    assert preview_embargo_id(by_id) == "urn:uuid:e1"
    assert preview_embargo_id(shown) == "urn:uuid:e2"
    assert preview_embargo_id(without_id) is None
    assert preview_embargo_id(object()) is None


def test_the_preview_em_reader_reads_a_shown_status() -> None:
    preview = CasePreview(
        summary="a case", case_status=to_loose(_status(), ("em",))
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
        ("tags", {"x", Redacted()}),
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
    """``as_Object.tag`` holds ``as_Object``s: the form is held whole where
    it would name itself, so the derivation ends."""
    from vultron.wire.as2.vocab.base.objects.object_types import as_Note

    note: Any = loose_form(as_Note).model_validate({"content": Redacted()})

    assert note.content == Redacted()
