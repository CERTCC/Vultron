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

"""The VINCE translation follows the crosswalk, case by case (#6444).

Each synthetic fixture case (``test/fixtures/vince/``) is translated and
projected through the measures' event history, and the reading is checked
against the crosswalk rows for that case.

Spec: CRD-01-003 to CRD-01-006, CRD-02-001 to CRD-02-004, CRD-02-006,
CRD-03-001 to CRD-03-005.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from test.adapters.connectors.vince._support import (
    ACTIVE,
    CASES,
    COMM_URL,
    INACTIVE,
    UNKNOWN,
    actors_by_name,
    crosswalk_caveats,
    crosswalk_rows,
    projected,
    reads,
    records,
    translate,
)
from test.support.act_clock import no_clock, recorded_clock_reads
from vultron.adapters.connectors.vince import (
    INFERRED_ROWS,
    ISSUE_TRACKING_REL,
    READS,
    VINCE_UNOBSERVABLE,
    vince_case_url,
)
from vultron.adapters.connectors.vince.records import VinceCase
from vultron.core.models.case_reading import (
    CaseReading,
    UntranslatedReason as Reason,
)
from vultron.core.states.embargo_register import EmbargoRegisterStatus
from vultron.core.states.rm import RM

CERT = "CERT/CC"
COORDINATOR_ROLES = ("CASE_MANAGER", "CASE_OWNER", "COORDINATOR")


def _reached(reading: CaseReading) -> dict[str, tuple[RM, tuple[str, ...]]]:
    """Each participant's reached RM state and roles, by name."""
    history, reached = projected(reading)
    assert history.unreadable_entries == []
    assert history.excluded == []
    names = {actor: name for name, actor in actors_by_name(reading).items()}
    return {
        names[p.participant]: (p.rm, p.roles) for p in reached.participants
    }


def _untranslated(reading: CaseReading) -> set[tuple[str, str, Reason]]:
    return {(u.source_record, u.fact, u.reason) for u in reading.untranslated}


def _rules(reading: CaseReading, entry_id: str) -> list[str]:
    return [i.rule_id for i in reading.inferences if i.entry_id == entry_id]


# -- AC-1: participants, roles, RM, embargo and P, X, A by the rows --------


@pytest.mark.spec("CRD-03-001")
@pytest.mark.spec("CRD-01-003")
def test_the_active_embargoed_case_translates_by_its_rows():
    reading = translate(ACTIVE)
    assert _reached(reading) == {
        CERT: (RM.ACCEPTED, COORDINATOR_ROLES),  # RM-01, RM-02
        "Example Research Lab": (RM.ACCEPTED, ("REPORTER",)),  # PA-03, RM-03
        "Synthetic Vendor Alpha": (RM.ACCEPTED, ("VENDOR",)),  # RM-05
        "Synthetic Vendor Beta": (RM.INVALID, ("VENDOR",)),  # RM-06
        "Synthetic Vendor Gamma": (RM.RECEIVED, ("VENDOR",)),  # RM-07
    }
    history, reached = projected(reading)
    assert reached.pxa.name == "pxa"
    # VINCE-EM-01: one active embargo, ending at due_date.
    assert list(reached.embargo_register.values()) == [
        EmbargoRegisterStatus.ACTIVE
    ]
    (embargo,) = records(reading, "EmbargoEvent")
    assert embargo["endTime"].startswith("2026-04-06T00:00:00")
    # VINCE-EM-02: CERT/CC and every vendor agreed.
    agreed = {
        e.participant for e in history.events if e.kind == "consent_agreed"
    }
    by_name = actors_by_name(reading)
    assert agreed == {
        by_name[name]
        for name in (
            CERT,
            "Synthetic Vendor Alpha",
            "Synthetic Vendor Beta",
            "Synthetic Vendor Gamma",
        )
    }


@pytest.mark.spec("CRD-03-001")
def test_the_inactive_published_case_translates_by_its_rows():
    reading = translate(INACTIVE)
    assert _reached(reading) == {
        CERT: (RM.CLOSED, COORDINATOR_ROLES),  # CA-03
        "withheld": (RM.ACCEPTED, ("REPORTER",)),  # PA-04, RM-03
        # The one statement is a rule conflict, so Delta stays Received.
        "Synthetic Vendor Delta": (RM.RECEIVED, ("VENDOR",)),
    }
    _, reached = projected(reading)
    assert reached.pxa.name == "Pxa"  # VINCE-CS-04: the published note
    assert reached.embargo_register == {}  # no due_date, no embargo
    assert records(reading, "EmbargoEvent") == []
    # VINCE-CS-01 to VINCE-CS-03: the reporter states P, X and A.
    reporter = actors_by_name(reading)["withheld"]
    stated = [
        status["caseStatus"]["pxaState"]
        for status in records(reading, "ParticipantStatus")
        if status["attributedTo"] == reporter and "caseStatus" in status
    ]
    assert stated == ["PXA"]


@pytest.mark.spec("CRD-03-001")
def test_the_unknown_values_case_translates_by_its_rows():
    reading = translate(UNKNOWN)
    assert _reached(reading) == {
        CERT: (RM.ACCEPTED, COORDINATOR_ROLES),
        "Example Research Lab": (RM.ACCEPTED, ("REPORTER",)),
        # Its one status is unknown, so it stays at VINCE-RM-04's Received.
        "Synthetic Vendor Epsilon": (RM.RECEIVED, ("VENDOR",)),
        "Synthetic Vendor Zeta": (RM.RECEIVED, ("VENDOR",)),  # RM-07
    }
    _, reached = projected(reading)
    assert reached.pxa.name == "pxa"
    assert list(reached.embargo_register.values()) == [
        EmbargoRegisterStatus.ACTIVE
    ]


@pytest.mark.spec("CRD-03-001")
@pytest.mark.parametrize("stem", CASES)
def test_every_vul_and_post_with_a_counterpart_is_translated(stem):
    reading = translate(stem)
    raw = reads(stem)
    items = records(reading, "VulnerabilityItem")
    assert [item["title"] for item in items] == [
        v["name"] for v in raw["vuls"]
    ]
    assert [item.get("cve") for item in items] == [
        v["cve"] for v in raw["vuls"]
    ]
    orgs = set(actors_by_name(reading))
    assert [note["content"] for note in records(reading, "Note")] == [
        post["content"]
        for post in raw["posts"]
        if post["author"]["org"] in orgs
    ]


@pytest.mark.spec("CRD-01-006")
def test_each_entry_credits_the_participant_who_acted():
    reading = translate(ACTIVE)
    by_name = actors_by_name(reading)
    alpha, cert = by_name["Synthetic Vendor Alpha"], by_name[CERT]
    affected = [
        entry
        for entry in reading.ledger
        if "VINCE-RM-05" in _rules(reading, entry.id_)
    ]
    assert affected and {e.payload_snapshot["actor"] for e in affected} == {
        alpha
    }
    (alpha_post,) = [
        note
        for note in records(reading, "Note")
        if note["attributedTo"] == alpha
    ]
    assert alpha_post["content"] == "A fix is in progress."
    (genesis,) = [
        e for e in reading.ledger if e.semantic_type == "create_case"
    ]
    assert genesis.payload_snapshot["actor"] == cert


# -- AC-2: every inference names its crosswalk row -------------------------


@pytest.mark.spec("CRD-03-005")
@pytest.mark.spec("CRD-02-002")
@pytest.mark.parametrize("stem", CASES)
def test_every_inference_names_a_crosswalk_row_and_its_caveat(stem):
    reading = translate(stem)
    rows, caveats = crosswalk_rows(), crosswalk_caveats()
    assert reading.inferences
    for inference in reading.inferences:
        assert inference.rule_id in rows
        assert inference.caveat == caveats[inference.rule_id]


@pytest.mark.spec("CRD-03-005")
def test_the_inferred_rows_are_the_crosswalk_s_inferred_rows():
    rows, caveats = crosswalk_rows(), crosswalk_caveats()
    inferred = {row for row, cells in rows.items() if cells[3] == "Inferred"}
    assert set(INFERRED_ROWS) == inferred
    assert dict(INFERRED_ROWS) == {row: caveats[row] for row in inferred}


@pytest.mark.spec("CRD-03-005")
def test_the_fixtures_exercise_every_inferred_row():
    used = {
        inference.rule_id
        for stem in CASES
        for inference in translate(stem).inferences
    }
    assert used == set(INFERRED_ROWS)


def test_vince_rm_07_names_the_received_entry_of_vince_rm_04():
    reading = translate(ACTIVE)
    (entry_id,) = [
        i.entry_id for i in reading.inferences if i.rule_id == "VINCE-RM-07"
    ]
    assert _rules(reading, entry_id) == ["VINCE-RM-04", "VINCE-RM-07"]


# -- AC-3: untranslated facts, and the rest of the case still translates ---


@pytest.mark.spec("CRD-03-003")
@pytest.mark.spec("CRD-03-004")
@pytest.mark.spec("CRD-02-003")
def test_unknown_values_come_back_untranslated_with_the_rest_translated():
    reading = translate(UNKNOWN)
    assert _untranslated(reading) == {
        ("case/999903/", "status = Pending", Reason.UNKNOWN_VALUE),
        (
            "case/999903/vendors/vuls/[0]",
            "status = Fixed",
            Reason.UNKNOWN_VALUE,
        ),
    }
    assert len(_reached(reading)) == 4


@pytest.mark.spec("CRD-02-003")
def test_a_statement_dated_before_its_vendor_is_a_rule_conflict():
    assert _untranslated(translate(INACTIVE)) == {
        (
            "case/999902/vendors/vuls/[0]",
            "statement_date is earlier than the vendor's date_added",
            Reason.RULE_CONFLICT,
        ),
        ("case/999902/posts/[0]", "pinned = true", Reason.NO_COUNTERPART),
        ("case/999902/note/", "revision = 2", Reason.NO_COUNTERPART),
        (
            "case/999902/note/",
            "dateupdated = 2026-05-03T12:00:00+00:00",
            Reason.NO_COUNTERPART,
        ),
    }


@pytest.mark.spec("CRD-01-005")
@pytest.mark.spec("CRD-02-003")
def test_a_post_from_no_participant_has_no_counterpart():
    reading = translate(ACTIVE)
    assert _untranslated(reading) == {
        (
            "case/999901/posts/[2]",
            "post whose author's org matches no participant",
            Reason.NO_COUNTERPART,
        )
    }
    assert len(records(reading, "Note")) == 2


# -- AC-4: the unobservable declaration -------------------------------------


@pytest.mark.spec("CRD-02-004")
@pytest.mark.spec("CRD-02-001")
@pytest.mark.parametrize("stem", CASES)
def test_every_reading_carries_the_vince_unobservable_declaration(stem):
    assert translate(stem).unobservable == VINCE_UNOBSERVABLE


@pytest.mark.spec("CRD-02-004")
def test_the_declaration_is_the_crosswalk_s_unobservable_table():
    from test.adapters.connectors.vince._support import CROSSWALK

    text = CROSSWALK.read_text(encoding="utf-8").replace("`", "")
    table = text[text.index("## Unobservable") :].split("\n---")[0]
    for fact in VINCE_UNOBSERVABLE:
        assert f"| {fact.fact} | {fact.why} |" in table


# -- AC-5: every time is a VINCE time, and no clock is read ----------------


def _vince_times(raw: Any) -> set[datetime]:
    """Every time the VINCE records state."""
    found: set[datetime] = set()
    if isinstance(raw, dict):
        for value in raw.values():
            found |= _vince_times(value)
    elif isinstance(raw, list):
        for value in raw:
            found |= _vince_times(value)
    elif isinstance(raw, str):
        try:
            found.add(datetime.fromisoformat(raw))
        except ValueError:
            pass
    return found


_TIME_KEYS = {"published", "updated", "startTime", "endTime"}


def _payload_times(node: Any) -> list[datetime]:
    if isinstance(node, list):
        return [t for item in node for t in _payload_times(item)]
    if not isinstance(node, dict):
        return []
    times = [
        datetime.fromisoformat(value)
        for key, value in node.items()
        if key in _TIME_KEYS and isinstance(value, str)
    ]
    return times + [
        t for key, value in node.items() for t in _payload_times(value)
    ]


@pytest.mark.spec("CRD-02-006")
@pytest.mark.parametrize("stem", CASES)
def test_every_time_in_the_reading_is_a_vince_record_time(stem):
    times = _vince_times(reads(stem))
    reading = translate(stem)
    for entry in reading.ledger:
        assert entry.published in times
        assert entry.received_at in times
        assert entry.payload_snapshot[
            "published"
        ] == entry.published.isoformat(timespec="microseconds")
        assert set(_payload_times(entry.payload_snapshot)) <= times


@pytest.mark.spec("CRD-02-006")
@pytest.mark.parametrize("stem", CASES)
def test_translation_reads_no_clock_and_repeats_exactly(stem):
    with recorded_clock_reads() as clock_reads:
        first = translate(stem)
    with no_clock():
        second = translate(stem)
    assert clock_reads == []
    assert first == second


def test_the_entries_are_in_time_order():
    for stem in CASES:
        stamps = [entry.published for entry in translate(stem).ledger]
        assert stamps == sorted(stamps)


# -- AC-6: the issue-tracking reference -------------------------------------


@pytest.mark.spec("CRD-03-002")
@pytest.mark.parametrize("stem", CASES)
def test_each_case_carries_one_issue_tracking_reference_to_its_vince_url(stem):
    reading = translate(stem)
    case = VinceCase.model_validate(reads(stem)["case"])
    (genesis,) = records(reading, "VulnerabilityCase")
    (reference,) = genesis["caseReferences"]
    assert reference["url"]["rel"] == [ISSUE_TRACKING_REL]
    assert reference["url"]["href"] == vince_case_url(COMM_URL, case)
    assert reference["url"]["href"] == (f"{COMM_URL}/case/{case.pk}/")


# -- citations --------------------------------------------------------------


@pytest.mark.spec("CRD-01-004")
@pytest.mark.parametrize("stem", CASES)
def test_every_citation_names_a_record_present_in_the_input(stem):
    raw = reads(stem)
    vuid = raw["case"]["vuid"]
    reading = translate(stem)
    cited = [c.source_record for c in reading.citations] + [
        u.source_record for u in reading.untranslated
    ]
    for record in cited:
        assert record.startswith(f"case/{vuid}/")
        path = record.removeprefix(f"case/{vuid}/")
        read, _, index = path.partition("[")
        read = read.rstrip("/") or "case"
        assert read in READS
        assert raw[read] is not None
        if index:
            assert int(index.rstrip("]")) < len(raw[read])
