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

"""A case reading is built whole or refused (#6358, CRD-02-001).

Spec: CRD-01-004, CRD-02-001, CRD-02-002, CRD-02-003.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from test.support.case_reader import FAKE_CASE, FakeCaseReader, OutsideRecord
from vultron.core.models.case_reading import (
    CaseReading,
    EntryCitation,
    Inference,
    UnobservableFact,
    UntranslatedFact,
    UntranslatedReason,
)

_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _reading(case_id: str = FAKE_CASE, records: int = 2) -> CaseReading:
    return FakeCaseReader(
        {
            case_id: [
                OutsideRecord(f"rec-{i}", "case_opened", "urn:x:cm", _AT)
                for i in range(records)
            ]
        }
    ).read_case(case_id)


@pytest.mark.spec("CRD-02-001")
def test_an_empty_reading_is_valid():
    reading = CaseReading(ledger=(), citations=())
    assert reading.inferences == ()
    assert reading.untranslated == ()
    assert reading.unobservable == ()


@pytest.mark.spec("CRD-01-004")
def test_an_entry_with_no_citation_is_refused():
    reading = _reading()
    with pytest.raises(ValidationError, match="have no citation"):
        CaseReading(ledger=reading.ledger, citations=reading.citations[:1])


@pytest.mark.spec("CRD-01-004")
def test_an_entry_cited_twice_is_refused():
    reading = _reading()
    extra = EntryCitation(
        entry_id=reading.ledger[0].id_, source_record="rec-other"
    )
    with pytest.raises(ValidationError, match="cited more than once"):
        CaseReading(
            ledger=reading.ledger, citations=(*reading.citations, extra)
        )


@pytest.mark.spec("CRD-01-004")
def test_a_citation_of_no_entry_is_refused():
    reading = _reading()
    stray = EntryCitation(entry_id="urn:uuid:nowhere", source_record="rec-x")
    with pytest.raises(ValidationError, match="name no entry"):
        CaseReading(
            ledger=reading.ledger, citations=(*reading.citations, stray)
        )


@pytest.mark.spec("CRD-02-002")
def test_an_inference_of_no_entry_is_refused():
    reading = _reading()
    stray = Inference(
        entry_id="urn:uuid:nowhere", rule_id="FAKE-1", caveat="Guessed."
    )
    with pytest.raises(ValidationError, match="name no entry"):
        CaseReading(
            ledger=reading.ledger,
            citations=reading.citations,
            inferences=(stray,),
        )


def test_a_ledger_of_two_cases_is_refused():
    one = _reading(records=1)
    other = _reading("urn:uuid:case-2", records=1)
    with pytest.raises(ValidationError, match="holds entries of"):
        CaseReading(
            ledger=(*one.ledger, *other.ledger),
            citations=(*one.citations, *other.citations),
        )


def test_a_repeated_entry_is_refused():
    reading = _reading(records=1)
    with pytest.raises(ValidationError, match="repeats entries"):
        CaseReading(
            ledger=(*reading.ledger, *reading.ledger),
            citations=reading.citations,
        )


def test_a_ledger_out_of_log_index_order_is_refused():
    reading = _reading()
    with pytest.raises(ValidationError, match="not in log-index order"):
        CaseReading(
            ledger=tuple(reversed(reading.ledger)),
            citations=reading.citations,
        )


def test_every_problem_is_reported_at_once():
    reading = _reading()
    stray = EntryCitation(entry_id="urn:uuid:nowhere", source_record="rec-x")
    with pytest.raises(ValidationError) as caught:
        CaseReading(ledger=reading.ledger, citations=(stray,))
    message = str(caught.value)
    assert "have no citation" in message
    assert "name no entry" in message


def test_a_reading_is_frozen():
    reading = _reading()
    with pytest.raises(ValidationError):
        reading.inferences = ()  # type: ignore[misc]


@pytest.mark.spec("CRD-02-003")
def test_an_untranslated_fact_needs_one_of_the_four_reasons():
    assert {r.value for r in UntranslatedReason} == {
        "unknown_value",
        "no_counterpart",
        "rule_conflict",
        "no_time",
    }
    with pytest.raises(ValidationError):
        UntranslatedFact(source_record="r", fact="f", reason="other")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("model", "fields"),
    [
        (EntryCitation, {"entry_id": "", "source_record": "r"}),
        (EntryCitation, {"entry_id": "e", "source_record": ""}),
        (Inference, {"entry_id": "e", "rule_id": "", "caveat": "c"}),
        (Inference, {"entry_id": "e", "rule_id": "r", "caveat": ""}),
        (
            UntranslatedFact,
            {"source_record": "r", "fact": "", "reason": "no_time"},
        ),
        (UnobservableFact, {"fact": "", "why": "w"}),
        (UnobservableFact, {"fact": "f", "why": ""}),
    ],
)
def test_a_blank_string_part_is_refused(model, fields):
    with pytest.raises(ValidationError):
        model(**fields)


def test_an_unknown_key_is_refused():
    with pytest.raises(ValidationError):
        UnobservableFact(fact="f", why="w", note="extra")  # type: ignore[call-arg]
