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

from typing import Any, cast

import pytest
from pydantic import BaseModel

from vultron.adapters.driven.db_record import (
    Record,
    _dehydrate_data,
    object_to_record,
    record_to_object,
)
from vultron.errors import VultronValidationError
from vultron.wire.as2.factories import rm_submit_report_activity


# Fixtures for reused test objects
@pytest.fixture
def sample_record():
    return Record(id_="123", type_="TestType", data_={"key": "value"})


@pytest.fixture
def base_object():
    from vultron.wire.as2.vocab.base.base import as_Base

    return as_Base(id_="test-id", type_="BaseObject", name="Test Object")


@pytest.fixture
def note_object():
    from vultron.wire.as2.vocab.base.objects.object_types import as_Note

    return as_Note(content="Test Content")


# Tests (atomic and with descriptive names)
def test_record_has_id_type_and_data_attributes(sample_record):
    assert sample_record.id_ == "123"
    assert sample_record.type_ == "TestType"
    assert sample_record.data_ == {"key": "value"}


def test_object_to_record_preserves_id_type_and_data_for_base_object(
    base_object,
):
    record = object_to_record(base_object)
    assert record.id_ == base_object.id_
    assert record.type_ == base_object.type_
    assert record.data_ == base_object.model_dump()


def test_object_to_record_returns_Record_for_note_object(note_object):
    record = object_to_record(note_object)
    assert isinstance(record, Record)


def test_record_to_object_reconstructs_note_and_preserves_id_type_and_data(
    note_object,
):
    record = object_to_record(note_object)
    reconstructed = cast(Any, record_to_object(record))
    # ensure type and class are preserved
    assert reconstructed.id_ == note_object.id_
    assert reconstructed.type_ == note_object.type_
    # ensure content/fields are preserved via model dump
    assert reconstructed.model_dump() == note_object.model_dump()


# --- _dehydrate_data unit tests ---


def test_dehydrate_data_replaces_object_ref_field_with_id_string():
    """A qualifying field (``object_``) with a non-empty id_ is collapsed."""
    nested_id = "urn:uuid:abc123"
    data = {
        "id_": "urn:uuid:parent",
        "object_": {"id_": nested_id, "type_": "Note", "content": "hi"},
    }
    result = _dehydrate_data(data)
    assert result["object_"] == nested_id


def test_dehydrate_data_leaves_top_level_id_unchanged():
    """The top-level id_ of the record is never collapsed."""
    parent_id = "urn:uuid:parent"
    data = {"id_": parent_id, "type_": "Note"}
    result = _dehydrate_data(data)
    assert result["id_"] == parent_id


def test_dehydrate_data_leaves_string_values_unchanged():
    """Non-dict values (including actor strings) are passed through as-is."""
    data = {"id_": "urn:uuid:x", "actor": "https://example.org/alice"}
    result = _dehydrate_data(data)
    assert result["actor"] == "https://example.org/alice"


def test_dehydrate_data_leaves_none_values_unchanged():
    """None values on qualifying fields are passed through unchanged."""
    data = {"id_": "urn:uuid:x", "target": None}
    result = _dehydrate_data(data)
    assert result["target"] is None


def test_dehydrate_data_does_not_collapse_list_items():
    """Lists (e.g. embedded sub-objects) are always passed through unchanged."""
    id1 = "urn:uuid:item1"
    id2 = "urn:uuid:item2"
    data = {
        "id_": "urn:uuid:parent",
        "items": [
            {"id_": id1, "type_": "Note"},
            {"id_": id2, "type_": "Note"},
            "plain-string",
        ],
    }
    result = _dehydrate_data(data)
    # List is preserved entirely — items must not be collapsed to ID strings.
    assert result["items"] == [
        {"id_": id1, "type_": "Note"},
        {"id_": id2, "type_": "Note"},
        "plain-string",
    ]


def test_dehydrate_data_leaves_non_ref_field_dict_intact():
    """A nested dict on a non-reference field (e.g. ``inbox``) is not touched."""
    inbox_id = "urn:uuid:inbox1"
    data = {
        "id_": "urn:uuid:parent",
        "inbox": {"id_": inbox_id, "type_": "OrderedCollection"},
    }
    result = _dehydrate_data(data)
    # ``inbox`` is not in _AS_OBJECT_REF_FIELDS; it must remain a dict.
    assert isinstance(result["inbox"], dict)
    assert result["inbox"]["id_"] == inbox_id


def test_dehydrate_data_leaves_dict_without_id_intact():
    """A nested dict without an id_ key is left as-is (not collapsed)."""
    data = {
        "id_": "urn:uuid:parent",
        "object_": {"type_": "Note"},
    }
    result = _dehydrate_data(data)
    assert isinstance(result["object_"], dict)


def test_dehydrate_data_ignores_empty_string_id():
    """A qualifying field whose id_ is an empty string is not collapsed."""
    data = {
        "id_": "urn:uuid:parent",
        "object_": {"id_": "", "type_": "Note"},
    }
    result = _dehydrate_data(data)
    assert isinstance(result["object_"], dict)


def test_dehydrate_data_dehydrates_all_object_ref_fields():
    """All fields in _AS_OBJECT_REF_FIELDS are candidates for dehydration."""
    from vultron.adapters.driven.db_record import _AS_OBJECT_REF_FIELDS

    obj_id = "urn:uuid:obj"
    for field_name in _AS_OBJECT_REF_FIELDS:
        data = {
            "id_": "urn:uuid:parent",
            field_name: {"id_": obj_id, "type_": "Note"},
        }
        result = _dehydrate_data(data)
        assert (
            result[field_name] == obj_id
        ), f"Expected {field_name!r} to be dehydrated to ID string"


# --- object_to_record dehydration integration tests ---


def test_object_to_record_stores_nested_object_as_id_reference():
    """An activity with a nested object stores only the nested object's ID."""
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        as_VulnerabilityReport,
    )

    report = as_VulnerabilityReport(
        name="Test CVE",
        content="Details of the vulnerability",
        attributed_to="https://example.org/finder",
    )
    offer = rm_submit_report_activity(
        report,
        "https://example.org/finder",
        actor="https://example.org/finder",
    )

    record = object_to_record(offer)
    stored_object_field = record.data_.get("object_")

    # The nested report must be stored as a plain ID string, not a full dict.
    assert isinstance(stored_object_field, str)
    assert stored_object_field == report.id_


def test_object_to_record_nested_report_not_duplicated_in_offer_data():
    """The stored offer data must not contain a full copy of the nested report."""
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        as_VulnerabilityReport,
    )

    report = as_VulnerabilityReport(
        name="Another CVE",
        content="More vulnerability details",
        attributed_to="https://example.org/finder",
    )
    offer = rm_submit_report_activity(
        report,
        "https://example.org/finder",
        actor="https://example.org/finder",
    )

    record = object_to_record(offer)

    # Ensure the report's content field does NOT appear inside the stored
    # offer's data, confirming no inline copy is stored.
    import json

    serialised = json.dumps(record.data_)
    assert report.content is not None
    assert report.content not in serialised


# ---------------------------------------------------------------------------
# Wire/core shape guard on the write path (issue #2232)
# ---------------------------------------------------------------------------


def test_object_to_record_normalizes_wire_class_shadowing_a_core_type():
    """A wire vocab class whose ``type_`` has a core counterpart is normalised.

    Regression for #2232: the only shape guard was ``type_.startswith("as_")``,
    but wire vocabulary ``type_`` values are bare ("CaseParticipant"), so a
    wire-shaped object was happily written into a core-typed DataLayer row.
    Core readers then saw a flat ``rm_state`` where they expected a nested
    ``rm`` dimension.

    The row must now carry the canonical core shape — nested
    ``rm: {"state": ...}`` — so no wire-shaped ``CaseParticipant`` row exists to
    be misread.
    """
    from vultron.core.models.registry import CORE_VOCABULARY
    from vultron.wire.as2.vocab.objects.case_participant import (
        as_CaseParticipant,
    )

    wire_participant = as_CaseParticipant(
        attributed_to="https://example.org/actors/vendor",
        context="https://example.org/cases/case-2232",
    )
    # The pre-existing guard cannot catch this: type_ is bare, not "as_"-prefixed.
    assert not str(wire_participant.type_).startswith("as_")
    assert str(wire_participant.type_) in CORE_VOCABULARY

    record = object_to_record(cast(Any, wire_participant))

    assert record.type_ == "CaseParticipant"
    statuses = record.data_["participant_statuses"]
    assert statuses, "normalised participant must retain its RM ladder"
    for status in statuses:
        # Canonical core shape: nested rm dimension, no flat rm_state.
        assert "rm_state" not in status
        assert status["rm"]["state"] == "START"


def test_object_to_record_normalizes_wire_participant_status():
    """A wire ``ParticipantStatus`` persists in the nested core ``rm`` shape."""
    from vultron.core.states.rm import RM
    from vultron.wire.as2.vocab.objects.case_status import (
        as_ParticipantStatus,
    )

    wire_status = as_ParticipantStatus(
        rm_state=RM.VALID,
        context="https://example.org/cases/case-2232",
        attributed_to="https://example.org/actors/vendor",
    )

    record = object_to_record(cast(Any, wire_status))

    assert record.type_ == "ParticipantStatus"
    assert "rm_state" not in record.data_
    assert record.data_["rm"]["state"] == "VALID"


def test_object_to_record_normalizes_wire_participant_nested_in_core_case():
    """A wire participant nested inside a core case is normalised too.

    Regression for the first fix of #2232, which inspected only the top-level
    object.  A ``VulnerabilityCase`` row stores its ``case_participants``
    inline, so a wire-shaped participant nested in a core-shaped case still
    persisted a flat ``rm_state`` — the row shape the issue's "Done when"
    forbids.
    """
    from vultron.core.models.case import VulnerabilityCase
    from vultron.core.states.rm import RM
    from vultron.wire.as2.vocab.objects.case_participant import (
        as_CaseParticipant,
    )
    from vultron.wire.as2.vocab.objects.case_status import (
        as_ParticipantStatus,
    )

    case_id = "urn:uuid:3f1b8d0e-1111-4111-8111-000000002232"
    wire_participant = as_CaseParticipant(
        attributed_to="https://example.org/actors/vendor",
        context=case_id,
        participant_statuses=[
            as_ParticipantStatus(context=case_id, rm_state=RM.RECEIVED)
        ],
    )
    case = VulnerabilityCase(id_=case_id, name="case-2232").model_copy(
        update={"case_participants": [wire_participant]}
    )

    record = object_to_record(cast(Any, case))

    stored_status = record.data_["case_participants"][0][
        "participant_statuses"
    ][0]
    assert "rm_state" not in stored_status
    assert stored_status["rm"]["state"] == "RECEIVED"


def test_object_to_record_raises_when_wire_class_has_no_to_core():
    """A shadowing wire class without ``to_core()`` cannot be persisted.

    Covers the ``to_core is None`` branch: the object shadows a core type, so
    storing it as-is would produce a row nothing can read back reliably, and
    there is no projection available to fix it.
    """
    from vultron.core.models.protocols import PersistableModel

    class _ShadowingWireClass(BaseModel):
        """Stands in for a wire class that never grew a ``to_core()``."""

        id_: str = "urn:uuid:00000000-0000-4000-8000-000000002232"
        type_: str = "ParticipantStatus"

    # Impersonate the wire package so the module-prefix check matches.
    _ShadowingWireClass.__module__ = "vultron.wire.as2.vocab.objects.fake"

    with pytest.raises(VultronValidationError, match="no to_core"):
        object_to_record(cast(PersistableModel, _ShadowingWireClass()))


def test_normalization_failure_is_distinguishable_from_duplicate_row():
    """A projection failure must not look like an "already exists" ValueError.

    ``crud.create`` raises ``ValueError`` for a genuine duplicate and callers
    legitimately swallow that.  When normalisation failure raised ``ValueError``
    too, an unprojectable object was silently never stored and never logged
    (the ingress pre-store in ``routers/actors/_inbox.py`` did exactly this).
    A distinct, non-``ValueError`` type keeps the two causes separable.
    """
    from vultron.wire.as2.vocab.objects.case_participant import (
        as_CaseParticipant,
    )

    # NonEmptyString rejects "" on the core class but not on the wire class,
    # so this object is constructible yet unprojectable.
    unprojectable = as_CaseParticipant(
        attributed_to="https://example.org/actors/vendor",
        context="https://example.org/cases/case-2232",
        accepted_embargo_ids=[""],
    )

    with pytest.raises(VultronValidationError) as exc_info:
        object_to_record(cast(Any, unprojectable))

    assert not isinstance(exc_info.value, ValueError)
    assert "2232" in str(exc_info.value)


def test_object_to_record_still_accepts_wire_activities():
    """Activities have no core counterpart, so they must remain persistable."""
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        as_VulnerabilityReport,
    )

    report = as_VulnerabilityReport(
        name="CVE-2232",
        content="details",
        attributed_to="https://example.org/finder",
    )
    offer = rm_submit_report_activity(
        report,
        "https://example.org/finder",
        actor="https://example.org/finder",
    )

    record = object_to_record(offer)
    assert record.type_ == "Offer"
