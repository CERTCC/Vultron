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

"""The VINCE translation's edges: records a row cannot place (#6444).

Each test edits one read of a committed fixture and checks the fact comes
back untranslated with its reason while the rest of the case translates
(CRD-01-005, CRD-02-003), or that a case no row can place is refused.

Spec: CRD-01-005, CRD-02-003, CRD-03-003, EH-07-001, VSD-01-003.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import pytest

from test.adapters.connectors.vince._support import (
    ACTIVE,
    AS_OF,
    AT_DUE_DATE,
    COMM_URL,
    INACTIVE,
    UNKNOWN,
    actors_by_name,
    projected,
    reads,
    records,
)
from vultron.adapters.connectors.vince import translate_case
from vultron.core.models.case_reading import (
    CaseReading,
    UntranslatedReason as Reason,
)
from vultron.core.states.rm import RM
from vultron.errors import VinceCaseRecordsError


def _translate(
    raw: dict[str, Any], *, as_of: datetime = AS_OF[ACTIVE]
) -> CaseReading:
    return translate_case(raw, comm_url=COMM_URL, as_of=as_of)


def _facts(reading: CaseReading) -> set[tuple[str, str, Reason]]:
    return {(u.source_record, u.fact, u.reason) for u in reading.untranslated}


def _clean(reading: CaseReading) -> None:
    """The reading projects with nothing unreadable or excluded."""
    history, _ = projected(reading)
    assert history.unreadable_entries == []
    assert history.excluded == []


@pytest.mark.parametrize("missing", ["case", "vuid", "pk", "created"])
def test_a_case_no_row_can_place_is_refused_naming_the_problem(missing):
    raw = reads(ACTIVE)
    if missing == "case":
        del raw["case"]
    else:
        del raw["case"][missing]
    with pytest.raises(VinceCaseRecordsError) as caught:
        _translate(raw)
    assert caught.value.violations
    assert missing in str(caught.value)


def test_a_refusal_quotes_no_vince_value():
    raw = reads(ACTIVE)
    raw["case"]["created"] = "SECRET-not-a-time"
    with pytest.raises(VinceCaseRecordsError) as caught:
        _translate(raw)
    assert "SECRET" not in str(caught.value)
    assert caught.value.vuid == "999901"


def test_a_case_with_no_report_seats_no_reporter():
    raw = reads(ACTIVE)
    raw["report"] = None
    reading = _translate(raw)
    _clean(reading)
    assert "Example Research Lab" not in actors_by_name(reading)
    _, reached = projected(reading)
    cert = actors_by_name(reading)["CERT/CC"]
    (state,) = [p.rm for p in reached.participants if p.participant == cert]
    assert state is RM.ACCEPTED
    # VINCE-RM-02 passes CERT/CC through Received and Valid at created.
    opening = [
        i.entry_id for i in reading.inferences if i.rule_id == "VINCE-RM-02"
    ]
    assert len(opening) == 3


def test_a_report_with_no_date_is_untranslated_with_no_time():
    raw = reads(ACTIVE)
    raw["report"]["date_submitted"] = None
    reading = _translate(raw)
    assert (
        "case/999901/report/",
        "report with no date_submitted",
        Reason.NO_TIME,
    ) in _facts(reading)
    _clean(reading)


def test_a_report_submitted_after_the_case_opened_is_a_rule_conflict():
    raw = reads(ACTIVE)
    raw["report"]["date_submitted"] = "2026-01-06T00:00:00Z"
    reading = _translate(raw)
    assert (
        "case/999901/report/",
        "date_submitted is later than the case's created",
        Reason.RULE_CONFLICT,
    ) in _facts(reading)
    _clean(reading)


@pytest.mark.parametrize(
    ("read", "field", "fact"),
    [
        ("vendors", "date_added", "vendor with no date_added"),
        ("vuls", "date_added", "vul with no date_added"),
        ("posts", "created", "post with no created"),
    ],
)
def test_an_undated_item_is_untranslated_with_no_time(read, field, fact):
    raw = reads(ACTIVE)
    raw[read][0][field] = None
    reading = _translate(raw)
    assert (f"case/999901/{read}/[0]", fact, Reason.NO_TIME) in _facts(reading)
    _clean(reading)


def test_statuses_of_an_unseated_vendor_have_no_counterpart():
    raw = reads(ACTIVE)
    raw["vendors"][0]["date_added"] = None
    facts = _facts(_translate(raw))
    for index in (0, 1):
        assert (
            f"case/999901/vendors/vuls/[{index}]",
            "status of a vendor that is not on the case",
            Reason.NO_COUNTERPART,
        ) in facts


def test_an_affected_status_with_no_date_is_untranslated_with_no_time():
    raw = reads(ACTIVE)
    raw["vendors/vuls"][0]["statement_date"] = None
    reading = _translate(raw)
    assert (
        "case/999901/vendors/vuls/[0]",
        "status = Affected with no statement_date",
        Reason.NO_TIME,
    ) in _facts(reading)
    # Alpha's other status is Unknown, so it stays Received (VINCE-RM-07).
    rules = {i.rule_id for i in reading.inferences}
    assert "VINCE-RM-05" not in rules


def test_a_vendor_listed_twice_is_a_rule_conflict():
    raw = reads(ACTIVE)
    raw["vendors"].append(dict(raw["vendors"][0]))
    reading = _translate(raw)
    assert (
        "case/999901/vendors/[3]",
        "vendor listed more than once on the case",
        Reason.RULE_CONFLICT,
    ) in _facts(reading)
    _clean(reading)


def test_an_item_that_does_not_parse_is_an_unknown_value():
    raw = reads(ACTIVE)
    raw["vendors"][1]["vendor"] = 42
    raw["vuls"] = {"not": "a list"}
    reading = _translate(raw)
    facts = {(source, reason) for source, _, reason in _facts(reading)}
    assert ("case/999901/vendors/[1]", Reason.UNKNOWN_VALUE) in facts
    assert ("case/999901/vuls/", Reason.UNKNOWN_VALUE) in facts
    assert records(reading, "VulnerabilityItem") == []
    _clean(reading)


def test_a_malformed_cve_is_untranslated_and_the_vul_kept():
    raw = reads(ACTIVE)
    raw["vuls"][0]["cve"] = "CVE-nope"
    reading = _translate(raw)
    assert (
        "case/999901/vuls/[0]",
        "cve = CVE-nope",
        Reason.UNKNOWN_VALUE,
    ) in _facts(reading)
    assert [
        item.get("cve") for item in records(reading, "VulnerabilityItem")
    ] == [
        None,
        None,
    ]


def test_an_inactive_case_with_no_modified_time_is_untranslated():
    raw = reads(INACTIVE)
    raw["case"]["modified"] = None
    reading = _translate(raw)
    assert (
        "case/999902/",
        "status = Inactive with no modified",
        Reason.NO_TIME,
    ) in _facts(reading)
    assert "VINCE-CA-03" not in {i.rule_id for i in reading.inferences}


def test_a_closure_before_cert_cc_s_last_step_is_a_rule_conflict():
    raw = reads(INACTIVE)
    raw["case"]["modified"] = "2026-01-04T00:00:00Z"
    reading = _translate(raw)
    assert (
        "case/999902/",
        "modified is earlier than CERT/CC's last RM step",
        Reason.RULE_CONFLICT,
    ) in _facts(reading)
    _clean(reading)


def test_a_published_note_with_no_date_is_untranslated():
    raw = reads(INACTIVE)
    raw["note"]["datefirstpublished"] = None
    reading = _translate(raw)
    assert (
        "case/999902/note/",
        "published = true with no datefirstpublished",
        Reason.NO_TIME,
    ) in _facts(reading)
    _, reached = projected(reading)
    assert reached.pxa.name == "pxa"


def test_a_published_note_on_an_embargoed_case_translates():
    raw = reads(INACTIVE)
    raw["case"]["due_date"] = "2026-06-01T00:00:00Z"
    reading = _translate(raw)
    _clean(reading)
    _, reached = projected(reading)
    assert reached.pxa.name == "Pxa"


def test_the_translation_logs_no_case_content(caplog):
    caplog.set_level(logging.DEBUG)
    raw = reads(ACTIVE)
    _translate(raw)
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "999901" in logged
    for content in (
        raw["case"]["title"],
        raw["posts"][0]["content"],
        raw["report"]["contact_email"],
        raw["vendors"][0]["vendor"],
    ):
        assert content not in logged


@pytest.mark.parametrize(
    ("stem", "read", "value", "source"),
    [
        (ACTIVE, "report", "not a record", "case/999901/report/"),
        (INACTIVE, "note", {"revision": "two"}, "case/999902/note/"),
        (
            ACTIVE,
            "vendors/vuls",
            [{"status": "Affected"}],
            "case/999901/vendors/vuls/[0]",
        ),
        (ACTIVE, "posts", "not a list", "case/999901/posts/"),
    ],
)
def test_a_read_that_does_not_parse_is_an_unknown_value(
    stem, read, value, source
):
    raw = reads(stem)
    raw[read] = value
    reading = _translate(raw)
    assert (source, Reason.UNKNOWN_VALUE) in {
        (s, reason) for s, _, reason in _facts(reading)
    }
    _clean(reading)


def test_a_post_with_no_content_has_no_counterpart():
    raw = reads(ACTIVE)
    raw["posts"][0]["content"] = ""
    assert (
        "case/999901/posts/[0]",
        "post with no content",
        Reason.NO_COUNTERPART,
    ) in _facts(_translate(raw))


def test_a_case_with_no_status_adds_nothing():
    raw = reads(UNKNOWN)
    raw["case"]["status"] = None
    reading = _translate(raw)
    assert all(u.source_record != "case/999903/" for u in reading.untranslated)


def _two_of_each(raw: dict[str, Any]) -> dict[str, Any]:
    """999901 with Gamma Affected like Alpha and a second all-Not-Affected
    vendor like Beta, so two vendors take each of VINCE-RM-05 and -06."""
    raw["vendors"].append({**raw["vendors"][1], "vendor": "Synthetic Beta 2"})
    for row in list(raw["vendors/vuls"]):
        if row["vendor"] == "Synthetic Vendor Gamma":
            row["status"] = "Affected"
        if row["vendor"] == "Synthetic Vendor Beta":
            raw["vendors/vuls"].append({**row, "vendor": "Synthetic Beta 2"})
    return raw


def test_every_entry_and_status_has_its_own_id():
    reading = _translate(_two_of_each(reads(ACTIVE)))
    rules = [i.rule_id for i in reading.inferences]
    assert rules.count("VINCE-RM-05") == 4  # Valid and Accepted, twice
    assert rules.count("VINCE-RM-06") == 2
    activity_ids = [entry.log_object_id for entry in reading.ledger]
    assert len(set(activity_ids)) == len(activity_ids)
    status_ids = {s["id"] for s in records(reading, "ParticipantStatus")}
    statuses = [
        entry.payload_snapshot["object"]["id"]
        for entry in reading.ledger
        if entry.semantic_type == "add_participant_status_to_participant"
    ]
    assert len(set(statuses)) == len(statuses)
    assert set(statuses) <= status_ids
    _clean(reading)


@pytest.mark.parametrize("absent", ["null", "missing"])
def test_a_list_read_vince_answered_404_holds_nothing(absent):
    raw = reads(ACTIVE)
    if absent == "null":
        raw["posts"] = None
    else:
        del raw["posts"]
    reading = _translate(raw)
    assert records(reading, "Note") == []
    assert all("posts" not in u.source_record for u in reading.untranslated)


def test_an_unpublished_note_states_no_public_awareness():
    raw = reads(INACTIVE)
    raw["note"]["published"] = False
    reading = _translate(raw)
    _, reached = projected(reading)
    assert reached.pxa.name == "pxa"
    assert all(
        entry.semantic_type != "add_case_status_to_case"
        for entry in reading.ledger
    )


@pytest.mark.parametrize(
    ("cleared", "name"),
    [
        ((), "Example Research Lab"),
        (("contact_org",), "Synthetic Reporter"),
        (("contact_org", "contact_name"), "reporter@example.org"),
        (("contact_org", "contact_name", "contact_email"), "reporter"),
    ],
)
def test_a_shared_reporter_is_named_by_its_contact(cleared, name):
    raw = reads(ACTIVE)
    for key in cleared:
        raw["report"][key] = ""
    reading = _translate(raw)
    assert name in actors_by_name(reading)
    assert "VINCE-PA-04" not in {i.rule_id for i in reading.inferences}


def test_the_reporter_s_id_carries_no_contact_detail():
    shared = reads(ACTIVE)
    other = reads(ACTIVE)
    other["report"]["contact_email"] = "someone.else@example.org"
    withheld = reads(ACTIVE)
    for key in (
        "contact_name",
        "contact_email",
        "contact_phone",
        "contact_org",
    ):
        del withheld["report"][key]

    def reporter(raw: dict[str, Any]) -> str:
        (record,) = [
            r
            for r in records(_translate(raw), "CaseParticipant")
            if r["caseRoles"] == ["reporter"]
        ]
        return str(record["attributedTo"])

    assert reporter(shared) == reporter(other)
    assert reporter(shared) != reporter(withheld)


def test_a_vul_with_no_description_has_no_notes():
    raw = reads(ACTIVE)
    raw["vuls"][0]["description"] = None
    items = records(_translate(raw), "VulnerabilityItem")
    assert "notes" not in items[0] or items[0]["notes"] == []


def test_a_vul_listed_twice_is_a_rule_conflict():
    raw = reads(ACTIVE)
    raw["vuls"].append(dict(raw["vuls"][0]))
    reading = _translate(raw)
    assert (
        "case/999901/vuls/[2]",
        "vul listed more than once on the case",
        Reason.RULE_CONFLICT,
    ) in _facts(reading)
    assert len(records(reading, "VulnerabilityItem")) == 2


def test_a_blank_vendor_name_does_not_parse():
    raw = reads(ACTIVE)
    raw["vendors"][2]["vendor"] = "   "
    facts = {(s, reason) for s, _, reason in _facts(_translate(raw))}
    assert ("case/999901/vendors/[2]", Reason.UNKNOWN_VALUE) in facts


# -- VINCE-EM-03 and the rows that meet it ----------------------------------


def _agreed(reading: CaseReading) -> set[str]:
    history, _ = projected(reading)
    return {
        str(e.participant)
        for e in history.events
        if e.kind == "consent_agreed"
    }


@pytest.mark.parametrize(
    ("added", "agrees"),
    [("2026-04-06T00:00:00Z", True), ("2026-04-07T00:00:00Z", False)],
)
def test_a_vendor_added_after_the_embargo_ended_agrees_to_nothing(
    added, agrees
):
    raw = reads(ACTIVE)
    raw["vendors"].append(dict(raw["vendors"][0], vendor="Late Vendor"))
    raw["vendors"][-1]["date_added"] = added
    reading = _translate(raw, as_of=AT_DUE_DATE + timedelta(days=30))
    _clean(reading)
    late = actors_by_name(reading)["Late Vendor"]
    assert (late in _agreed(reading)) is agrees
    # A vendor added at due_date agrees before the embargo ends.
    kinds = [
        e.kind
        for e in projected(reading)[0].events
        if e.kind in ("consent_agreed", "embargo_exit")
    ]
    assert kinds[-1] == "embargo_exit"


@pytest.mark.parametrize(
    ("as_of", "em"),
    [(AT_DUE_DATE - timedelta(days=1), "ACTIVE"), (AT_DUE_DATE, "EXITED")],
)
def test_a_case_status_after_the_embargo_ended_states_it_exited(as_of, em):
    raw = reads(ACTIVE)
    raw["note"] = dict(reads(INACTIVE)["note"], dateupdated=None)
    raw["note"]["datefirstpublished"] = "2026-04-06T00:00:00Z"
    reading = _translate(raw, as_of=as_of)
    _clean(reading)
    (published,) = [
        entry.payload_snapshot["object"]
        for entry in reading.ledger
        if entry.semantic_type == "add_case_status_to_case"
    ]
    assert published["emState"] == em
