#!/usr/bin/env python

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

"""The ``CaseReader`` port: declared in core, read-only, and its shape (#6358).

A fake in-memory reader (``test/support/case_reader.py``) satisfies the port,
and the ledger it returns is one the event-history projection reads.

Spec: CRD-01-001 through CRD-01-006, CRD-02-001 through CRD-02-004,
CRD-02-006.
"""

from typing import get_protocol_members

import pytest

from test.measure.history.builders import (
    VENDOR,
)
from test.support.case_reader import (
    FAKE_CASE,
    FAKE_UNOBSERVABLE,
    FakeCaseReader,
    fake_case_records,
    projected_history,
)
from vultron.core.models.case_reading import CaseReading, UntranslatedReason
from vultron.core.ports.case_reader import CaseReader
from vultron.core.states.cs_invariants import CSEvent
from vultron.errors import VultronNotFoundError
from vultron.measure.history import EventKind

#: The port's members, written out: one read method and the declaration
#: every reading copies.  Any member added to the port fails the test below.
READ_METHODS = {"read_case"}
DECLARATIONS = {"unobservable"}


def _entry_of(reading: CaseReading, record_id: str):
    by_record = {c.source_record: c.entry_id for c in reading.citations}
    return next(e for e in reading.ledger if e.id_ == by_record[record_id])


@pytest.fixture
def reading() -> CaseReading:
    return FakeCaseReader({FAKE_CASE: fake_case_records()}).read_case(
        FAKE_CASE
    )


@pytest.mark.spec("CRD-01-001")
def test_case_reader_is_declared_under_core_ports():
    assert CaseReader.__module__ == "vultron.core.ports.case_reader"
    assert isinstance(FakeCaseReader({}), CaseReader)


@pytest.mark.spec("CRD-01-002")
def test_case_reader_declares_no_write_method():
    """The port's members equal the read members written out here."""
    assert get_protocol_members(CaseReader) == READ_METHODS | DECLARATIONS
    for method in READ_METHODS:
        assert callable(getattr(CaseReader, method))


@pytest.mark.spec("CRD-01-001")
@pytest.mark.spec("CRD-01-003")
def test_the_fake_readers_ledger_is_one_the_projection_accepts(reading):
    history = projected_history(reading)
    assert history.unreadable_entries == []
    assert history.missing_log_indices == []
    vendor_kinds = [e.kind for e in history.for_participant(VENDOR)]
    assert EventKind.REPORT_RECEIVED in vendor_kinds
    assert CSEvent.V in vendor_kinds


@pytest.mark.spec("CRD-01-006")
def test_an_entry_names_the_participant_who_acted_as_its_actor(reading):
    assert _entry_of(reading, "rec-status").payload_snapshot["actor"] == VENDOR


@pytest.mark.spec("CRD-02-001")
def test_a_reading_carries_all_five_parts(reading):
    assert set(CaseReading.model_fields) == {
        "ledger",
        "citations",
        "inferences",
        "untranslated",
        "unobservable",
    }
    assert len(reading.ledger) == 4
    assert reading.citations
    assert reading.inferences
    assert reading.untranslated
    assert reading.unobservable


@pytest.mark.spec("CRD-01-004")
def test_every_entry_cites_a_source_record_present_in_the_input(reading):
    source_ids = {record.record_id for record in fake_case_records()}
    cited = {c.entry_id: c.source_record for c in reading.citations}
    assert set(cited) == {entry.id_ for entry in reading.ledger}
    assert set(cited.values()) <= source_ids


@pytest.mark.spec("CRD-02-002")
def test_an_inference_names_its_entry_rule_and_caveat(reading):
    entry_ids = {entry.id_ for entry in reading.ledger}
    named = {(i.entry_id, i.rule_id) for i in reading.inferences}
    assert named == {
        (_entry_of(reading, "rec-vendor").id_, "FAKE-RM-01"),
        (_entry_of(reading, "rec-undated").id_, "FAKE-RM-01"),
        (_entry_of(reading, "rec-undated").id_, "FAKE-TIME-01"),
    }
    assert all(
        i.entry_id in entry_ids and i.caveat for i in reading.inferences
    )


@pytest.mark.spec("CRD-01-005")
@pytest.mark.spec("CRD-02-003")
def test_each_untranslated_fact_carries_its_reason(reading):
    reasons = {f.source_record: f.reason for f in reading.untranslated}
    assert reasons == {
        "rec-odd": UntranslatedReason.UNKNOWN_VALUE,
        "rec-pinned": UntranslatedReason.NO_COUNTERPART,
        "rec-early": UntranslatedReason.RULE_CONFLICT,
        "rec-untimed": UntranslatedReason.NO_TIME,
    }


@pytest.mark.spec("CRD-02-004")
def test_a_reading_copies_the_readers_unobservable_declaration(reading):
    reader = FakeCaseReader({FAKE_CASE: fake_case_records()})
    assert reader.unobservable == FAKE_UNOBSERVABLE
    assert reading.unobservable == reader.unobservable


@pytest.mark.spec("CRD-02-006")
def test_an_entrys_times_are_its_source_records_time(reading):
    """A dated record keeps its time; an undated one takes the time its
    rule names, the case's opening, and is listed as an inference."""
    times = {r.record_id: r.at for r in fake_case_records()}
    times["rec-undated"] = times["rec-open"]
    for citation in reading.citations:
        entry = next(e for e in reading.ledger if e.id_ == citation.entry_id)
        assert entry.published == times[citation.source_record]
        assert entry.received_at == times[citation.source_record]
    undated = _entry_of(reading, "rec-undated").id_
    assert ("FAKE-TIME-01", undated) in {
        (i.rule_id, i.entry_id) for i in reading.inferences
    }


def test_a_case_the_source_does_not_hold_raises_a_domain_error():
    with pytest.raises(VultronNotFoundError, match="urn:uuid:missing"):
        FakeCaseReader({}).read_case("urn:uuid:missing")
