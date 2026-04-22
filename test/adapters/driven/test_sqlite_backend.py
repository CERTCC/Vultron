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

"""Tests for the SQLite/SQLModel-backed DataLayer adapter.

Unit tests use an in-memory SQLite database (no file I/O required).
Integration tests (marked ``@pytest.mark.integration``) use a real
file-backed database via ``tmp_path``.
"""

import os

import pytest

from vultron.adapters.driven.db_record import Record
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def dl():
    """In-memory SqliteDataLayer for unit tests."""
    instance = SqliteDataLayer("sqlite:///:memory:")
    yield instance
    instance.clear_all()
    instance.close()


@pytest.fixture
def tmp_db_url(tmp_path):
    """SQLite URL pointing to a temporary file (for integration tests)."""
    db_path = tmp_path / "test_sqlite.db"
    return f"sqlite:///{db_path}"


@pytest.fixture
def file_dl(tmp_db_url):
    """File-backed SqliteDataLayer for integration tests."""
    instance = SqliteDataLayer(tmp_db_url)
    yield instance
    instance.clear_all()
    instance.close()


@pytest.fixture
def record_factory():
    def _make(id_="12345", type_="test_table", data_=None):
        data = {"field": "value"} if data_ is None else data_
        return Record(id_=id_, type_=type_, data_=data)

    return _make


@pytest.fixture
def created_record(dl, record_factory):
    rec = record_factory()
    dl.create(rec)
    return rec


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_database_initialization_creates_db_file(tmp_db_url):
    """Creating a file-backed SqliteDataLayer creates the SQLite file."""
    instance = SqliteDataLayer(tmp_db_url)
    # Extract path from "sqlite:///path/to/file.db"
    db_path = tmp_db_url.replace("sqlite:///", "")
    assert os.path.exists(db_path)
    instance.close()


def test_database_initialization_in_memory():
    """In-memory DataLayer can be created and is operational."""
    instance = SqliteDataLayer("sqlite:///:memory:")
    assert instance.ping()
    instance.close()


# ---------------------------------------------------------------------------
# create / read / get
# ---------------------------------------------------------------------------


def test_create_inserts_record(dl, record_factory):
    record = record_factory()
    dl.create(record)
    got = dl.get(record.type_, record.id_)
    assert got is not None
    assert got["id_"] == record.id_
    assert got["type_"] == record.type_
    assert got["data_"] == record.data_


def test_create_raises_on_duplicate_id(dl, record_factory):
    record = record_factory()
    dl.create(record)
    with pytest.raises(ValueError):
        dl.create(record)


def test_get_returns_none_for_nonexistent_type(dl):
    assert dl.get("nonexistent_table", "no_id") is None


def test_get_returns_none_for_missing_id(dl, record_factory):
    record = record_factory()
    dl.create(record)
    assert dl.get(record.type_, "no_such_id") is None


def test_read_returns_object(dl, record_factory):
    from vultron.wire.as2.vocab.base.objects.object_types import as_Note

    note = as_Note(content="Test Content")
    dl.save(note)
    result = dl.read(note.id_)
    assert result is not None
    assert result.id_ == note.id_  # type: ignore[union-attr]


def test_read_returns_none_for_missing_id(dl):
    assert dl.read("urn:uuid:does-not-exist") is None


def test_read_supports_bare_uuid(dl):
    from vultron.wire.as2.vocab.base.objects.object_types import as_Note

    note = as_Note(content="Bare UUID test")
    dl.save(note)
    # Strip the urn:uuid: prefix
    bare = note.id_.replace("urn:uuid:", "")
    result = dl.read(bare)
    assert result is not None
    assert result.id_ == note.id_  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# update / save / delete
# ---------------------------------------------------------------------------


def test_update_updates_existing_record_data(dl, created_record):
    rec = created_record
    new_data = rec.data_.copy()
    new_data["field"] = "new_value"
    updated_record = Record(id_=rec.id_, type_=rec.type_, data_=new_data)

    updated = dl.update(id_=updated_record.id_, record=updated_record)
    assert updated
    got = dl.get(updated_record.type_, updated_record.id_)
    assert got is not None
    assert got["data_"]["field"] == "new_value"


def test_update_returns_false_for_non_existing_id(dl, record_factory):
    non_existing = record_factory(id_="no_such_id")
    updated = dl.update(id_=non_existing.id_, record=non_existing)
    assert not updated


def test_save_inserts_new_object(dl):
    from vultron.wire.as2.vocab.base.objects.object_types import as_Note

    note = as_Note(content="Save test")
    dl.save(note)
    result = dl.read(note.id_)
    assert result is not None


def test_save_overwrites_existing_object(dl):
    from vultron.wire.as2.vocab.base.objects.object_types import as_Note

    note = as_Note(content="Original content")
    dl.save(note)
    # Change the content and save again
    note2 = as_Note(id_=note.id_, content="Updated content")
    dl.save(note2)
    result = dl.read(note.id_)
    assert result is not None
    assert result.content == "Updated content"  # type: ignore[union-attr]


def test_delete_removes_record_and_returns_true(dl, record_factory):
    record = record_factory()
    dl.create(record)
    deleted = dl.delete(record.type_, record.id_)
    assert deleted
    assert dl.get(record.type_, record.id_) is None


def test_delete_returns_false_for_nonexistent_record(dl, record_factory):
    record = record_factory()
    assert not dl.delete(record.type_, record.id_)


# ---------------------------------------------------------------------------
# all / get_all / by_type / count_all
# ---------------------------------------------------------------------------


def test_all_returns_all_records_for_table(dl, record_factory):
    record1 = record_factory(id_="id1", data_={"field": "value1"})
    record2 = record_factory(id_="id2", data_={"field": "value2"})
    dl.create(record1)
    dl.create(record2)

    all_records = dl.all("test_table")
    assert len(all_records) == 2
    ids = {rec.id_ for rec in all_records}  # type: ignore[union-attr]
    assert "id1" in ids
    assert "id2" in ids
    for rec in all_records:
        assert isinstance(rec, Record)


def test_all_without_table_returns_dict_of_objects(dl):
    from vultron.wire.as2.vocab.base.objects.object_types import as_Note

    note = as_Note(content="All test")
    dl.save(note)
    result = dl.all()
    assert isinstance(result, dict)
    assert note.id_ in result


def test_get_all_returns_list_of_dicts(dl, record_factory):
    rec = record_factory()
    dl.create(rec)
    result = dl.get_all("test_table")
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["id_"] == rec.id_


def test_by_type_returns_dict(dl, record_factory):
    rec = record_factory()
    dl.create(rec)
    result = dl.by_type("test_table")
    assert isinstance(result, dict)
    assert rec.id_ in result


def test_count_all_returns_dict_with_counts(dl, record_factory):
    rec = record_factory()
    dl.create(rec)
    counts = dl.count_all()
    assert isinstance(counts, dict)
    assert "_default" in counts
    assert counts["test_table"] == 1


# ---------------------------------------------------------------------------
# clear_table / clear_all
# ---------------------------------------------------------------------------


def test_clear_table_removes_all_records(dl, record_factory):
    record = record_factory()
    dl.create(record)
    dl.clear_table(record.type_)
    assert dl.get(record.type_, record.id_) is None
    assert len(dl.all(record.type_)) == 0


def test_clear_all_removes_all_records(dl, record_factory):
    record1 = record_factory(id_="id1", type_="table1")
    record2 = record_factory(id_="id2", type_="table2")
    dl.create(record1)
    dl.create(record2)
    dl.clear_all()
    assert dl.get(record1.type_, record1.id_) is None
    assert dl.get(record2.type_, record2.id_) is None


# ---------------------------------------------------------------------------
# exists / ping
# ---------------------------------------------------------------------------


def test_exists_returns_false_for_nonexistent_type(dl):
    assert not dl.exists("nonexistent_table", "no_id")


def test_exists_returns_true_after_create(dl, record_factory):
    record = record_factory()
    dl.create(record)
    assert dl.exists(record.type_, record.id_)


def test_exists_returns_false_for_missing_id(dl, record_factory):
    record = record_factory()
    dl.create(record)
    assert not dl.exists(record.type_, "no_such_id")


def test_exists_returns_false_after_delete(dl, record_factory):
    record = record_factory()
    dl.create(record)
    dl.delete(record.type_, record.id_)
    assert not dl.exists(record.type_, record.id_)


def test_ping_returns_true(dl):
    assert dl.ping() is True


# ---------------------------------------------------------------------------
# Inbox / outbox queue methods
# ---------------------------------------------------------------------------


def test_inbox_starts_empty(dl):
    assert dl.inbox_list() == []


def test_inbox_append_and_list(dl):
    dl.inbox_append("https://example.org/activities/001")
    assert "https://example.org/activities/001" in dl.inbox_list()


def test_inbox_pop_fifo_order(dl):
    dl.inbox_append("https://example.org/activities/001")
    dl.inbox_append("https://example.org/activities/002")
    assert dl.inbox_pop() == "https://example.org/activities/001"
    assert len(dl.inbox_list()) == 1


def test_inbox_pop_empty_returns_none(dl):
    assert dl.inbox_pop() is None


def test_outbox_starts_empty(dl):
    assert dl.outbox_list() == []


def test_outbox_append_and_list(dl):
    dl.outbox_append("https://example.org/activities/sent-001")
    assert "https://example.org/activities/sent-001" in dl.outbox_list()


def test_outbox_pop_fifo_order(dl):
    dl.outbox_append("https://example.org/activities/sent-001")
    dl.outbox_append("https://example.org/activities/sent-002")
    assert dl.outbox_pop() == "https://example.org/activities/sent-001"
    assert len(dl.outbox_list()) == 1


def test_outbox_pop_empty_returns_none(dl):
    assert dl.outbox_pop() is None


# ---------------------------------------------------------------------------
# Nested-object dehydration integration tests
# ---------------------------------------------------------------------------


def test_activity_with_nested_object_stores_id_reference_not_inline_copy(dl):
    """Storing an activity with a nested object writes only the nested ID."""
    from vultron.wire.as2.vocab.activities.report import RmSubmitReportActivity
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        VulnerabilityReport,
    )

    report = VulnerabilityReport(
        name="Test CVE",
        content="A critical vulnerability",
        attributed_to="https://example.org/finder",
    )
    offer = RmSubmitReportActivity(
        actor="https://example.org/finder",
        object_=report,
    )

    dl.create(report)
    dl.create(offer)

    raw = dl.get(offer.type_, offer.id_)
    assert raw is not None
    stored_object_field = raw["data_"]["object_"]
    assert isinstance(
        stored_object_field, str
    ), f"Expected object_ to be stored as ID string, got {type(stored_object_field)}"
    assert stored_object_field == report.id_


def test_activity_nested_object_retrievable_separately_after_dehydration(dl):
    from vultron.wire.as2.vocab.activities.report import RmSubmitReportActivity
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        VulnerabilityReport,
    )

    report = VulnerabilityReport(
        name="Test CVE 2",
        content="Another vulnerability",
        attributed_to="https://example.org/finder",
    )
    offer = RmSubmitReportActivity(
        actor="https://example.org/finder",
        object_=report,
    )

    dl.create(report)
    dl.create(offer)

    retrieved_report = dl.read(report.id_)
    assert retrieved_report is not None
    assert retrieved_report.id_ == report.id_  # type: ignore[union-attr]


def test_reading_activity_back_yields_expanded_nested_object(dl):
    """After DL-REHYDRATE, dl.read() expands dehydrated object_ fields.

    Previously ``dl.read()`` returned a string ID for the nested ``object_``
    field; after the rehydration pipeline the full typed object is returned.
    """
    from vultron.wire.as2.vocab.activities.report import RmSubmitReportActivity
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        VulnerabilityReport,
    )

    report = VulnerabilityReport(
        name="Test CVE 3",
        content="Yet another vulnerability",
        attributed_to="https://example.org/finder",
    )
    offer = RmSubmitReportActivity(
        actor="https://example.org/finder",
        object_=report,
    )

    dl.create(report)
    dl.create(offer)

    retrieved_offer = dl.read(offer.id_)
    assert retrieved_offer is not None
    # object_ is now a fully-expanded VulnerabilityReport, not a string ID
    assert isinstance(retrieved_offer.object_, VulnerabilityReport)  # type: ignore[union-attr]
    assert retrieved_offer.object_.id_ == report.id_  # type: ignore[union-attr]


def test_rehydration_restores_nested_object_from_datalayer(dl):
    from vultron.wire.as2.rehydration import rehydrate
    from vultron.wire.as2.vocab.activities.report import RmSubmitReportActivity
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        VulnerabilityReport,
    )

    report = VulnerabilityReport(
        name="Test CVE 4",
        content="One more vulnerability",
        attributed_to="https://example.org/finder",
    )
    offer = RmSubmitReportActivity(
        actor="https://example.org/finder",
        object_=report,
    )

    dl.create(report)
    dl.create(offer)

    stored_offer = dl.read(offer.id_)
    assert stored_offer is not None
    full_offer = rehydrate(stored_offer, dl=dl)
    assert full_offer.object_ is not None  # type: ignore[union-attr]
    assert full_offer.object_.id_ == report.id_  # type: ignore[union-attr]
    assert full_offer.object_.type_ == "VulnerabilityReport"  # type: ignore[union-attr]


def test_rehydration_does_not_mutate_stored_record(dl):
    from vultron.wire.as2.rehydration import rehydrate
    from vultron.wire.as2.vocab.activities.report import RmSubmitReportActivity
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        VulnerabilityReport,
    )

    report = VulnerabilityReport(
        name="Test CVE 5",
        content="Final vulnerability",
        attributed_to="https://example.org/finder",
    )
    offer = RmSubmitReportActivity(
        actor="https://example.org/finder",
        object_=report,
    )

    dl.create(report)
    dl.create(offer)

    stored_offer = dl.read(offer.id_)
    assert stored_offer is not None
    rehydrate(stored_offer, dl=dl)

    raw = dl.get(offer.type_, offer.id_)
    assert raw is not None
    stored_object_field = raw["data_"]["object_"]
    assert isinstance(stored_object_field, str)
    assert stored_object_field == report.id_


# ---------------------------------------------------------------------------
# find_case_by_report_id tests
# ---------------------------------------------------------------------------


def test_find_case_by_report_id_returns_case_when_report_stored_as_string(dl):
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        VulnerabilityCase,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        VulnerabilityReport,
    )

    report = VulnerabilityReport(
        name="CVE-2025-001",
        content="Test vulnerability",
        attributed_to="https://example.org/finder",
    )
    case = VulnerabilityCase()
    case.vulnerability_reports.append(report.id_)

    dl.create(report)
    dl.save(case)

    result = dl.find_case_by_report_id(report.id_)
    assert result is not None
    assert isinstance(result, VulnerabilityCase)
    assert result.id_ == case.id_


def test_find_case_by_report_id_returns_case_when_report_stored_as_object(dl):
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        VulnerabilityCase,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        VulnerabilityReport,
    )

    report = VulnerabilityReport(
        name="CVE-2025-002",
        content="Another vulnerability",
        attributed_to="https://example.org/finder",
    )
    case = VulnerabilityCase()
    case.vulnerability_reports.append(report)

    dl.create(report)
    dl.save(case)

    result = dl.find_case_by_report_id(report.id_)
    assert result is not None
    assert isinstance(result, VulnerabilityCase)
    assert result.id_ == case.id_


def test_find_case_by_report_id_returns_none_when_not_found(dl):
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        VulnerabilityCase,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        VulnerabilityReport,
    )

    report = VulnerabilityReport(
        name="CVE-2025-003",
        content="Unlinked vulnerability",
        attributed_to="https://example.org/finder",
    )
    case = VulnerabilityCase()

    dl.create(report)
    dl.save(case)

    result = dl.find_case_by_report_id(report.id_)
    assert result is None


def test_find_case_by_report_id_returns_none_when_no_cases(dl):
    result = dl.find_case_by_report_id("urn:uuid:nonexistent-report")
    assert result is None


def test_find_case_by_report_id_returns_none_for_unknown_id(dl):
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        VulnerabilityCase,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        VulnerabilityReport,
    )

    report = VulnerabilityReport(
        name="CVE-2025-004",
        content="Linked vulnerability",
        attributed_to="https://example.org/finder",
    )
    other_report = VulnerabilityReport(
        name="CVE-2025-005",
        content="Unlinked vulnerability",
        attributed_to="https://example.org/finder",
    )
    case = VulnerabilityCase()
    case.vulnerability_reports.append(report.id_)

    dl.create(report)
    dl.create(other_report)
    dl.save(case)

    result = dl.find_case_by_report_id(other_report.id_)
    assert result is None


# ---------------------------------------------------------------------------
# File-backed integration test
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_file_backed_store_and_retrieve(file_dl):
    """Data written to a file-backed DataLayer is readable from the same URL."""
    from vultron.wire.as2.vocab.base.objects.object_types import as_Note

    note = as_Note(content="Integration test note")
    file_dl.save(note)
    result = file_dl.read(note.id_)
    assert result is not None
    assert result.id_ == note.id_  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# DL-REHYDRATE: semantic type recovery tests
# ---------------------------------------------------------------------------


class TestRehydrateFields:
    """_rehydrate_fields expands dehydrated string IDs back to typed objects."""

    def test_offer_object_field_expanded_to_vulnerability_report(self, dl):
        """RmSubmitReportActivity.object_ is a VulnerabilityReport after read."""
        from vultron.wire.as2.vocab.activities.report import (
            RmSubmitReportActivity,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_report import (
            VulnerabilityReport,
        )

        report = VulnerabilityReport(name="CVE-TEST-001", content="Test body")
        offer = RmSubmitReportActivity(
            actor="https://alice.example.org", object_=report
        )
        dl.save(report)
        dl.save(offer)

        result = dl.read(offer.id_)

        assert isinstance(result, RmSubmitReportActivity)
        assert isinstance(result.object_, VulnerabilityReport)  # type: ignore[union-attr]
        assert result.object_.name == "CVE-TEST-001"  # type: ignore[union-attr]

    def test_missing_nested_object_keeps_string(self, dl):
        """When a referenced object is not in the DB, the string ID is kept."""
        from vultron.wire.as2.vocab.activities.report import (
            RmSubmitReportActivity,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_report import (
            VulnerabilityReport,
        )

        report = VulnerabilityReport(name="CVE-MISSING", content="Body")
        offer = RmSubmitReportActivity(
            actor="https://alice.example.org", object_=report
        )
        # Save offer but NOT the report — reference is dangling
        dl.save(offer)

        result = dl.read(offer.id_)

        # Object field keeps the string ID since the report cannot be resolved
        assert result is not None
        assert isinstance(result.object_, str)  # type: ignore[union-attr]


class TestCoerceToSemanticClass:
    """_coerce_to_semantic_class promotes base-vocab activities to subtypes."""

    def test_rm_submit_report_round_trip_returns_specific_class(self, dl):
        """dl.read returns RmSubmitReportActivity, not generic as_Offer."""
        from vultron.wire.as2.vocab.activities.report import (
            RmSubmitReportActivity,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_report import (
            VulnerabilityReport,
        )

        report = VulnerabilityReport(name="CVE-ROUND-TRIP", content="Body")
        offer = RmSubmitReportActivity(
            actor="https://alice.example.org", object_=report
        )
        dl.save(report)
        dl.save(offer)

        result = dl.read(offer.id_)

        assert type(result).__name__ == "RmSubmitReportActivity"

    def test_em_propose_embargo_round_trip_returns_specific_class(self, dl):
        """dl.read returns EmProposeEmbargoActivity with EmbargoEvent object_."""
        from vultron.wire.as2.vocab.activities.embargo import (
            EmProposeEmbargoActivity,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        case = VulnerabilityCase()
        embargo = EmbargoEvent(context=case.id_)
        proposal = EmProposeEmbargoActivity(
            actor="https://alice.example.org",
            object_=embargo,
            context=case.id_,
        )
        dl.save(case)
        dl.save(embargo)
        dl.save(proposal)

        result = dl.read(proposal.id_)

        assert type(result).__name__ == "EmProposeEmbargoActivity"
        assert isinstance(result.object_, EmbargoEvent)  # type: ignore[union-attr]

    def test_accept_invite_round_trip_returns_specific_class_from_generic_parse(
        self, dl
    ):
        """Generic inbound Accept(Invite(...)) reads back as RmAcceptInviteToCaseActivity."""
        from typing import cast

        from vultron.wire.as2.parser import parse_activity
        from vultron.wire.as2.vocab.activities.case import (
            RmAcceptInviteToCaseActivity,
            RmInviteToCaseActivity,
        )
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Accept,
        )
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization

        parsed = cast(
            as_Accept,
            parse_activity(
                {
                    "type": "Accept",
                    "id": "urn:uuid:accept-invite-roundtrip-1",
                    "actor": "https://example.org/actors/coordinator",
                    "inReplyTo": "urn:uuid:invite-roundtrip-1",
                    "object": {
                        "type": "Invite",
                        "id": "urn:uuid:invite-roundtrip-1",
                        "actor": "https://example.org/actors/vendor",
                        "object": {
                            "type": "Organization",
                            "id": "https://example.org/actors/coordinator",
                            "name": "Coordinator",
                        },
                        "target": {
                            "type": "VulnerabilityCase",
                            "id": "https://example.org/cases/case-roundtrip-1",
                        },
                        "to": ["https://example.org/actors/coordinator"],
                    },
                },
            ),
        )

        nested_invite = parsed.object_
        assert nested_invite is not None
        dl.save(
            as_Organization(
                id_="https://example.org/actors/coordinator",
                name="Coordinator",
            )
        )
        dl.save(nested_invite)
        dl.save(parsed)

        result = dl.read(parsed.id_)

        assert isinstance(result, RmAcceptInviteToCaseActivity)
        assert isinstance(result.object_, RmInviteToCaseActivity)
        assert result.object_.id_ == "urn:uuid:invite-roundtrip-1"
        assert result.in_reply_to == "urn:uuid:invite-roundtrip-1"

    def test_announce_log_entry_round_trip_returns_specific_class(self, dl):
        """dl.read returns AnnounceLogEntryActivity with CaseLogEntry object_."""
        from vultron.core.models.case_log import GENESIS_HASH, CaseLogEntry
        from vultron.core.use_cases.triggers.sync import _to_persistable_entry
        from vultron.wire.as2.vocab.activities.sync import (
            AnnounceLogEntryActivity,
        )
        from vultron.wire.as2.vocab.objects.case_log_entry import (
            CaseLogEntry as WireCaseLogEntry,
        )

        chain_entry = CaseLogEntry(
            case_id="https://example.org/cases/case-sync-1",
            log_index=0,
            object_id="https://example.org/activities/logged-1",
            event_type="log_entry_committed",
            payload_snapshot={"status": "ok"},
            prev_log_hash=GENESIS_HASH,
        )
        entry = _to_persistable_entry(chain_entry)
        announce = AnnounceLogEntryActivity(
            actor="https://example.org/actors/case-actor",
            object_=WireCaseLogEntry.from_core(entry),
            to=["https://example.org/actors/participant"],
        )
        dl.save(entry)
        dl.save(announce)

        result = dl.read(announce.id_)

        assert isinstance(result, AnnounceLogEntryActivity)
        assert isinstance(result.object_, WireCaseLogEntry)
        assert result.object_.case_id == entry.case_id
        assert result.object_.log_object_id == entry.log_object_id

    def test_non_activity_object_not_coerced(self, dl):
        """Non-activity objects (e.g. VulnerabilityReport) are returned as-is."""
        from vultron.wire.as2.vocab.objects.vulnerability_report import (
            VulnerabilityReport,
        )

        report = VulnerabilityReport(name="CVE-PLAIN", content="Body")
        dl.save(report)

        result = dl.read(report.id_)

        assert isinstance(result, VulnerabilityReport)
