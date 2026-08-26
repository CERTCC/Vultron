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

from datetime import UTC, datetime
from typing import Any, cast

import pytest
from pydantic import BaseModel

from vultron.adapters.driven.db_record import (
    Record,
    _KEEP_INLINE_NESTED_TYPES,
    _dehydrate_data,
    object_to_record,
    record_to_object,
)
from vultron.errors import VultronValidationError
from vultron.wire.as2.enums import (
    as_IntransitiveActivityType,
    as_TransitiveActivityType,
)
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


# ---------------------------------------------------------------------------
# _KEEP_INLINE_NESTED_TYPES derivation guard (issue #2218)
# ---------------------------------------------------------------------------


def test_keep_inline_nested_types_contains_all_transitive_activity_values():
    """_KEEP_INLINE_NESTED_TYPES must cover every as_TransitiveActivityType value."""
    for member in as_TransitiveActivityType:
        assert member.value in _KEEP_INLINE_NESTED_TYPES, (
            f"as_TransitiveActivityType.{member.name} ({member.value!r}) "
            "is missing from _KEEP_INLINE_NESTED_TYPES"
        )


def test_keep_inline_nested_types_contains_all_intransitive_activity_values():
    """_KEEP_INLINE_NESTED_TYPES must cover every as_IntransitiveActivityType value."""
    for member in as_IntransitiveActivityType:
        assert member.value in _KEEP_INLINE_NESTED_TYPES, (
            f"as_IntransitiveActivityType.{member.name} ({member.value!r}) "
            "is missing from _KEEP_INLINE_NESTED_TYPES"
        )


def test_keep_inline_nested_types_contains_case_ledger_entry():
    """_KEEP_INLINE_NESTED_TYPES must include the Vultron-specific CaseLedgerEntry."""
    assert "CaseLedgerEntry" in _KEEP_INLINE_NESTED_TYPES


def test_keep_inline_nested_types_matches_enum_union_exactly():
    """_KEEP_INLINE_NESTED_TYPES must equal the union of both enum value sets plus CaseLedgerEntry."""
    expected = (
        frozenset(e.value for e in as_TransitiveActivityType)
        | frozenset(e.value for e in as_IntransitiveActivityType)
        | {"CaseLedgerEntry"}
    )
    assert _KEEP_INLINE_NESTED_TYPES == expected


# ---------------------------------------------------------------------------
# Round-trip normalization tests for the 8 types migrated in #2401 (DL-05-005)
# ---------------------------------------------------------------------------

_CASE_ID_2401 = "urn:uuid:case-2401-0000-0000-000000000000"
_LOG_OBJ_ID_2401 = "urn:uuid:logobj-2401-0000-000000000000"
_ACTOR_ID_2401 = "https://example.org/actors/finder-2401"
_ACTOR_INBOX_2401 = "https://example.org/actors/finder-2401/inbox"


def _make_wire_vulnerability_report():
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        as_VulnerabilityReport,
    )

    return as_VulnerabilityReport(
        name="CVE-2401-0001",
        content="details",
        attributed_to=_ACTOR_ID_2401,
    )


def _make_wire_vulnerability_case():
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

    return as_VulnerabilityCase(name="Case-2401")


def _make_wire_embargo_event():
    from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

    return as_EmbargoEvent(context=_CASE_ID_2401)


def _make_wire_case_status():
    from vultron.wire.as2.vocab.objects.case_status import as_CaseStatus

    return as_CaseStatus(context=_CASE_ID_2401)


def _make_wire_case_ledger_entry():
    from vultron.wire.as2.vocab.objects.case_ledger_entry import (
        as_CaseLedgerEntry,
    )

    return as_CaseLedgerEntry(
        case_id=_CASE_ID_2401,
        log_object_id=_LOG_OBJ_ID_2401,
        event_type="RS",
    )


def _make_wire_case_reference():
    from vultron.wire.as2.vocab.objects.case_reference import as_CaseReference

    return as_CaseReference(url="https://example.org/cases/ext-case-2401")


def _make_wire_embargo_policy():
    from datetime import timedelta

    from vultron.wire.as2.vocab.objects.embargo_policy import as_EmbargoPolicy

    return as_EmbargoPolicy(
        actor_id=_ACTOR_ID_2401,
        inbox=_ACTOR_INBOX_2401,
        preferred_duration=timedelta(days=90),
    )


def _make_wire_vulnerability_record():
    from vultron.wire.as2.vocab.objects.vulnerability_record import (
        as_VulnerabilityRecord,
    )

    return as_VulnerabilityRecord(name="CVE-2401-0001")


@pytest.mark.parametrize(
    "make_wire_obj,expected_type",
    [
        (_make_wire_vulnerability_report, "VulnerabilityReport"),
        (_make_wire_vulnerability_case, "VulnerabilityCase"),
        (_make_wire_embargo_event, "EmbargoEvent"),
        (_make_wire_case_status, "CaseStatus"),
        (_make_wire_case_ledger_entry, "CaseLedgerEntry"),
        (_make_wire_case_reference, "CaseReference"),
        (_make_wire_embargo_policy, "EmbargoPolicy"),
        (_make_wire_vulnerability_record, "VulnerabilityRecord"),
    ],
    ids=[
        "VulnerabilityReport",
        "VulnerabilityCase",
        "EmbargoEvent",
        "CaseStatus",
        "CaseLedgerEntry",
        "CaseReference",
        "EmbargoPolicy",
        "VulnerabilityRecord",
    ],
)
def test_object_to_record_normalizes_migrated_wire_type(
    make_wire_obj, expected_type
):
    """Wire instances of each type migrated in #2401 are stored in core shape.

    Regression for DL-05-005: these types were previously stored as-is in
    their wire shape, producing rows whose field names might not match what
    the core reader expected.  Each must now be stored with type_ equal to
    the core vocabulary entry name.
    """
    wire_obj = make_wire_obj()
    record = object_to_record(cast(Any, wire_obj))
    assert record.type_ == expected_type


def test_embargo_event_without_context_raises_on_persist():
    """A wire EmbargoEvent with no context cannot be persisted.

    Core EmbargoEvent.context is NonEmptyString (required).  The wire class
    accepts None, but projecting it via to_core() raises because the core
    constraint is not met.  This must surface as VultronValidationError —
    not silently stored — so the caller can supply context before persisting.
    """
    from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

    no_context = as_EmbargoEvent()
    assert no_context.context is None, "wire class must accept None context"

    with pytest.raises(VultronValidationError):
        object_to_record(cast(Any, no_context))


# ---------------------------------------------------------------------------
# CP-01-004: a ref field the model requires to be inline is never dehydrated
# ---------------------------------------------------------------------------


def _inline_proposal():
    """An ``as_CaseProposal`` carrying its report inline, as CP-01-004 requires."""
    from vultron.wire.as2.vocab.objects.case_proposal import as_CaseProposal
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        as_VulnerabilityReport,
    )

    report = as_VulnerabilityReport(
        id_="urn:uuid:rpt-cp01004-0000-0000-000000000001",
        name="CP-01-004-REPORT",
        content="the vulnerability being proposed for coordination",
        attributed_to="https://example.org/actors/finder-cp01004",
    )
    return as_CaseProposal(
        id_="urn:uuid:prop-cp01004-0000-0000-000000000001",
        attributed_to="https://example.org/actors/vendor-cp01004",
        object_=report,
        target="https://example.org/actors/case-actor-cp01004",
    )


def test_case_proposal_object_survives_storage_as_an_inline_report():
    """CP-01-004: storing a CaseProposal MUST NOT collapse its report to an id.

    Regression for #2482.  ``object_`` is in ``_AS_OBJECT_REF_FIELDS``, so it was
    dehydrated like any other reference — but CP-01-004 requires the report to be
    carried inline, and ingress stores only the *first* level of nesting, so the
    report had no record of its own to rehydrate from.  The by-ID re-read at
    delivery therefore handed the receiver a bare URI, and every consequence of
    the report (participant, ledger entries, signatory seed) degraded to a
    best-effort skip.  Nothing raised.
    """
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        as_VulnerabilityReport,
    )

    proposal = _inline_proposal()
    record = object_to_record(cast(Any, proposal))

    stored = record.data_["object_"]
    assert isinstance(stored, dict), (
        "CP-01-004 requires the report inline; storage collapsed it to"
        f" {stored!r}, which no read can undo because the report was never"
        " given a record of its own"
    )
    report = proposal.object_
    assert isinstance(report, as_VulnerabilityReport)
    assert stored["id_"] == report.id_
    assert (
        stored["attributed_to"] == "https://example.org/actors/finder-cp01004"
    )


def test_case_proposal_round_trips_with_a_typed_report():
    """The report comes back typed, not as a dict or an id (#2482)."""
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        as_VulnerabilityReport,
    )

    proposal = _inline_proposal()
    back = record_to_object(object_to_record(cast(Any, proposal)))
    restored = getattr(back, "object_", None)

    assert isinstance(
        restored, as_VulnerabilityReport
    ), f"expected a typed report on read-back, got {type(restored).__name__}"
    assert restored.attributed_to == (
        "https://example.org/actors/finder-cp01004"
    ), "the reporter must survive the round-trip — it is who becomes a participant"
    assert restored.content == (
        "the vulnerability being proposed for coordination"
    )


def test_case_proposal_declares_object_as_an_inline_required_ref():
    """The invariant lives on the model, not in a storage-layer lookup table.

    ``_dehydrate_data`` consults this declaration, so a model that requires a
    ref inline says so once, next to the field, rather than being enumerated in
    the adapter that would otherwise collapse it.
    """
    from vultron.wire.as2.vocab.objects.case_proposal import as_CaseProposal

    assert "object_" in as_CaseProposal.inline_required_refs


def _case_carrying_its_embargo():
    """An ``as_VulnerabilityCase`` with its ``active_embargo`` carried inline."""
    from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

    case_id = "urn:uuid:case-dl08000-0000-0000-000000000001"
    # ``context`` names the case the embargo is on; the core model requires it
    # (``EmbargoEvent.context: NonEmptyString``), so an embargo without one is
    # not a projectable domain object in the first place.
    embargo = as_EmbargoEvent(
        id_="urn:uuid:emb-dl08000-0000-0000-000000000001",
        summary="embargo carried with the case",
        context=case_id,
    )
    return as_VulnerabilityCase(
        id_=case_id,
        attributed_to="https://example.org/actors/case-actor-dl08",
        published=datetime(2026, 8, 24, tzinfo=UTC),
        active_embargo=embargo,
    )


def test_case_declares_active_embargo_as_an_inline_required_ref():
    """DL-08-002: the invariant is declared, not left to the annotation.

    ``as_EmbargoEventRef`` expands to include ``str``, so a flattened case
    type-checks and validates without complaint.  The declaration is the only
    machine-readable record that the object must be carried, and it is what the
    storage layer consults (DL-08-001).
    """
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

    assert "active_embargo" in as_VulnerabilityCase.inline_required_refs


def test_case_active_embargo_survives_storage_as_an_inline_object():
    """AKM-03-001: storing a case MUST NOT collapse its embargo to an id.

    A recipient cannot dereference a URI it does not hold and no dereferencing
    mechanism is specified, so a bare id hands every replica a case pointing at
    an object it can never read — and the manager's own teardown then cannot
    announce itself, because ``terminate_embargo`` begins by reading the
    ``EmbargoEvent`` it is about.
    """
    case = _case_carrying_its_embargo()
    record = object_to_record(cast(Any, case))

    stored = record.data_["active_embargo"]
    assert not isinstance(stored, str), (
        "AKM-03-001 requires the embargo inline; storage reduced it to"
        f" {stored!r}, which the receiver cannot resolve"
    )
    assert stored["id_"] == "urn:uuid:emb-dl08000-0000-0000-000000000001"


def test_case_to_core_keeps_the_carried_embargo():
    """``to_core()`` must not flatten a declared inline-required ref.

    The core case is what gets stored, and ``outbox_delivery`` re-serialises the
    *stored* activity, so a flattening here puts the bare id back on the wire no
    matter what the sender held.
    """
    case = _case_carrying_its_embargo()
    core = case.to_core()

    assert not isinstance(core.active_embargo, str), (
        "to_core() reduced active_embargo to an id; the declaration in"
        " inline_required_refs says it is carried (DL-08-001)"
    )
    assert (
        core.active_embargo_id == "urn:uuid:emb-dl08000-0000-0000-000000000001"
    ), "the id is still reachable via active_embargo_id when that is what is wanted"


def test_case_to_core_passes_through_a_bare_embargo_id():
    """A case that only ever held an id must still project.

    ``inline_required_refs`` says the field must not be *reduced* to an id on
    the way out; it cannot conjure an object a sender never had.  Rehydrating
    such a case has to keep working rather than raise.
    """
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

    case = as_VulnerabilityCase(
        id_="urn:uuid:case-dl08001-0000-0000-000000000001",
        attributed_to="https://example.org/actors/case-actor-dl08",
        published=datetime(2026, 8, 24, tzinfo=UTC),
        active_embargo="urn:uuid:emb-dl08001-0000-0000-000000000001",
    )

    core = case.to_core()

    assert core.active_embargo == "urn:uuid:emb-dl08001-0000-0000-000000000001"


# ---------------------------------------------------------------------------
# DL-08-003: an activity whose object_ names a peer actor
# ---------------------------------------------------------------------------

_PEER_ACTOR_ID = "http://vendor:7999/api/v2/actors/vendor-dl08003"
_CASE_ACTOR_ID = "http://coordinator:7999/api/v2/actors/case-actor"


def _invite_naming_a_peer():
    """An ``Invite(Actor, Case)`` as the Case Actor builds it for a peer.

    Built through the factory, not the internal vocab class, per the
    AF-05-001 boundary (``test/architecture/test_activity_factory_imports.py``).
    """
    from vultron.core.models.actor import CoreActor
    from vultron.wire.as2.factories import rm_invite_to_case_activity

    return rm_invite_to_case_activity(
        invitee=CoreActor(id_=_PEER_ACTOR_ID),
        target="urn:uuid:case-dl08003-0000-0000-000000000001",
        id_="urn:uuid:inv-dl08003-0000-0000-000000000001",
        actor=_CASE_ACTOR_ID,
        to=[_PEER_ACTOR_ID],
    )


def _recommendation_naming_a_peer():
    """An ``Offer(Actor, Case)`` — the other activity that names a peer."""
    from vultron.core.models.actor import CoreActor
    from vultron.wire.as2.factories import recommend_actor_activity

    return recommend_actor_activity(
        recommended=CoreActor(id_=_PEER_ACTOR_ID),
        target="urn:uuid:case-dl08003-0000-0000-000000000001",
        id_="urn:uuid:rec-dl08003-0000-0000-000000000001",
        actor=_CASE_ACTOR_ID,
    )


def test_invite_keeps_the_invited_peer_inline():
    """The invitee must survive storage as an object, not an id (DL-08-003).

    Nothing in the sender's store can give this id a record: the invitee is a
    peer on another node, and under ADR-0073 a peer's record lives in the store
    of whichever actor knows it — which for an Invite emitted by the Case Actor
    is not the Case Actor's store. Dehydrating it therefore had nothing to read
    back from, so the stored Invite returned a bare string and outbox delivery
    refused it for AKM-03-001 after exhausting its retries. The invitation never
    arrived and the invitee's ``reject-case-invite`` answered 404 for an invite
    it had never been told about (#2548, fcv-reject).
    """
    invite = _invite_naming_a_peer()

    record = object_to_record(cast(Any, invite))
    stored = record.data_.get("object_")

    assert isinstance(stored, dict), (
        f"the invitee collapsed to {stored!r}; nothing in this store can expand"
        " it again (DL-08-003)"
    )
    assert stored.get("id_") == _PEER_ACTOR_ID


def test_invited_peer_round_trips_as_an_object():
    """Read-back is what ``outbox_delivery`` re-serialises, so it is the gate."""
    back = record_to_object(
        object_to_record(cast(Any, _invite_naming_a_peer()))
    )
    restored = getattr(back, "object_", None)

    assert not isinstance(
        restored, str
    ), "a bare string object_ is exactly what the AKM-03-001 gate rejects"
    assert getattr(restored, "id_", None) == _PEER_ACTOR_ID


def _role_offer_naming_a_peer():
    """An ``Offer(CaseParticipantRole, target=Actor, context=Case)`` (ADR-0039).

    Names a peer in ``target`` rather than ``object_`` — same rule, other field.
    """
    from vultron.enums.roles import CVDRole
    from vultron.wire.as2.factories import (
        offer_case_participant_role_activity,
    )
    from vultron.wire.as2.vocab.base.objects.actors import as_Actor
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

    return offer_case_participant_role_activity(
        role=CVDRole.VENDOR,
        target_actor=as_Actor(id_=_PEER_ACTOR_ID),
        case=as_VulnerabilityCase(
            id_="urn:uuid:case-dl08003-0000-0000-000000000001"
        ),
        id_="urn:uuid:role-dl08003-0000-0000-000000000001",
        actor=_CASE_ACTOR_ID,
    )


@pytest.mark.parametrize(
    "builder, fields",
    [
        (_invite_naming_a_peer, {"object_"}),
        (_recommendation_naming_a_peer, {"object_"}),
        (_role_offer_naming_a_peer, {"object_", "target"}),
    ],
    ids=["invite", "recommendation", "role-offer"],
)
def test_peer_actor_ref_is_declared_inline_required(builder, fields):
    """Every activity naming a *peer actor* in a ref field declares that field.

    These are the only three, and the role offer is the only one that names its
    peer in ``target``.  Every other required-and-typed ``object_`` in the
    vocabulary is either an activity (kept inline by
    ``_KEEP_INLINE_NESTED_TYPES``) or a case/report/status/participant/embargo,
    all of which do have a record in the sending actor's own store.  An actor
    object is the one that never does — and the role offer's ``object_`` is the
    one other kind that never does, since the factory mints the
    ``CaseParticipantRole`` inline and no code path persists it (DL-08-001).

    ``_OfferCaseOwnershipTransferActivity.target`` is deliberately excluded: it
    is typed as a ref union, so an id there is the declared shape.

    Asserted on the class the *factory* returns rather than an imported vocab
    class, so it also pins the factory to a class that carries the declaration.
    """
    assert fields <= type(builder()).inline_required_refs


@pytest.mark.parametrize(
    "builder, semantic_cls_name",
    [
        (_invite_naming_a_peer, "_RmInviteToCaseActivity"),
        (_recommendation_naming_a_peer, "_RecommendActorActivity"),
        (_role_offer_naming_a_peer, "_OfferCaseParticipantRoleActivity"),
    ],
    ids=["invite", "recommendation", "role-offer"],
)
def test_stored_activity_still_matches_its_semantic_class(
    builder, semantic_cls_name
):
    """Storage must not cost an activity its semantics.

    ``coerce_to_semantic_class`` is what turns the base class read back out of
    storage into the specific one, and it needs the fields the matcher keys on to
    still be typed objects.  When they are not, the read-back is classified
    UNKNOWN and stays an ``as_Offer``/``as_Invite`` — which is not an error
    anywhere, it just means the receiver has no semantics to dispatch on and the
    protocol step silently never happens.
    """
    from vultron.adapters.driven.datalayer_sqlite.hydration import (
        coerce_to_semantic_class,
    )

    stored = record_to_object(object_to_record(cast(Any, builder())))
    coerced = coerce_to_semantic_class(cast(Any, stored))

    assert type(coerced).__name__ == semantic_cls_name


def test_recommended_peer_round_trips_as_an_object():
    """The Offer path has the same gap as the Invite path (DL-08-003).

    ``suggest-actor-to-case`` is emitted by the recommender and addressed to the
    Case Manager, and the actor it names is by definition one the case does not
    have — so no store on the sending side holds it either.
    """
    back = record_to_object(
        object_to_record(cast(Any, _recommendation_naming_a_peer()))
    )
    restored = getattr(back, "object_", None)

    assert not isinstance(
        restored, str
    ), "a bare string object_ is exactly what the AKM-03-001 gate rejects"
    assert getattr(restored, "id_", None) == _PEER_ACTOR_ID
