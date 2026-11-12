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

"""The case event history as a friendly-named table and as JSON (CEH-01-005, CEH-01-006).

The renderer tests run the library, never the command (CEH-01-003); the
command's own tests are in ``test_cli.py``.
"""

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from test.measure.history.builders import (
    CASE,
    CM,
    VENDOR,
    Ledger,
    participant,
    status,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.errors import CaseHistoryInputError
from vultron.measure.history import (
    CaseEvent,
    CaseEventHistories,
    CaseEventHistory,
    EventKind,
    ExcludedState,
    GapLabel,
    HistoryFormat,
    UnreadableEntry,
    case_history_report,
)
from vultron.measure.history.render import (
    CASE_SUBJECT,
    TABLE_HEADERS,
    event_row,
    label_names,
    render_table,
)
from vultron.measure.ledger import (
    MISSING_SLOT,
    UNNAMED_ACTOR,
    UNNAMED_OBJECT,
    CaseLedger,
    Dimension,
    LedgerSource,
    UnusableRow,
)

#: A bare URI or an opaque UUID, which no table cell may hold (DRPT-03-009).
_OPAQUE = re.compile(
    r"https?://|urn:|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{12}",
    re.IGNORECASE,
)

INVITEE = "https://example.org/actors/5b0c9d4e-0f6b-4c1d-9a3e-2c9d8e717699"
NOTE = "urn:uuid:9a3e2c9d-8e71-4c1d-9a3e-0f6b2c9d8e71"
AT = datetime(2026, 1, 1, tzinfo=UTC)


def _event(kind=EventKind.JOINED, participant=VENDOR, **fields) -> CaseEvent:
    return CaseEvent(
        kind=kind,
        participant=participant,
        semantic_type=MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE,
        log_index=3,
        committed_at=AT,
        **fields,
    )


def _accept(actor: object, invitee: object) -> dict:
    """An entry accepting an invitation of *invitee* to the case."""
    return {
        "caseId": CASE,
        "logIndex": 3,
        "semanticType": "accept_invite_actor_to_case",
        "payloadSnapshot": {
            "type": "Accept",
            "actor": actor,
            "object": {"type": "Invite", "object": invitee, "target": CASE},
        },
    }


@pytest.mark.spec("CEH-01-006")
@pytest.mark.spec("DRPT-03-009")
def test_a_row_names_its_actor_and_object_by_display_name():
    entry = _accept(
        {"id": VENDOR, "type": "Organization", "name": "Acme Vendor"},
        {"id": INVITEE, "type": "Organization", "name": "Invitee Inc"},
    )
    row = event_row(_event(), entry, label_names({"f": [entry]}), CASE)
    assert row.actor == "Acme Vendor"
    assert row.object == "Invitee Inc → case"
    assert row.participant == "Acme Vendor"
    assert row.activity == "Acme Vendor accepted the case invitation"
    for cell in (row.actor, row.object, row.participant, row.activity):
        assert not _OPAQUE.search(cell), cell


@pytest.mark.spec("CEH-01-006")
@pytest.mark.spec("DRPT-03-009")
def test_an_object_with_no_display_name_shows_the_fallback_not_its_uri():
    entry = _accept(INVITEE, {"id": INVITEE, "type": "Organization"})
    entry["payloadSnapshot"]["object"]["object"] = NOTE
    row = event_row(_event(), entry, label_names({"f": [entry]}), CASE)
    assert row.actor == UNNAMED_ACTOR
    assert row.object == f"{UNNAMED_OBJECT} → case"
    assert not _OPAQUE.search(row.actor + row.object + row.activity)


def test_a_participant_id_is_labelled_by_the_actor_it_stands_for():
    seat = {
        "payloadSnapshot": {
            "type": "Create",
            "actor": CM,
            "object": participant(VENDOR, [status("v-r", VENDOR, "RECEIVED")]),
        }
    }
    update = {
        "payloadSnapshot": {
            "type": "Add",
            "actor": CM,
            "object": {"type": "ParticipantStatus"},
            "target": f"{VENDOR}#participant",
        }
    }
    names = label_names({"f": [seat, update]})
    row = event_row(_event(), update, names, CASE)
    assert row.object == "participant status → Vendor"


def test_a_case_event_belongs_to_the_case_and_an_unknown_entry_reads_a_dash():
    event = CaseEvent(
        kind=EventKind.EMBARGO_START,
        semantic_type=MessageSemantics.CREATE_CASE,
        log_index=0,
        committed_at=AT,
        embargo_id="urn:uuid:embargo-1",
        gaps=[GapLabel.SEATED_AT_CREATION],
        deadline=AT,
    )
    row = event_row(event, None, {}, CASE)
    assert row.participant == CASE_SUBJECT
    assert (row.actor, row.object, row.claimed) == (MISSING_SLOT,) * 3
    assert row.gaps == (
        "seated_at_creation, deadline 2026-01-01T00:00:00.000000+00:00"
    )
    assert not row.activity.startswith(MISSING_SLOT)


def _write(ledger: Ledger, path: Path) -> Path:
    path.write_text(
        "\n".join(json.dumps(entry) for entry in ledger.entries) + "\n",
        encoding="utf-8",
    )
    return path


def _small_ledger() -> Ledger:
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add_status(
        CM, status("owner-v", "https://example.org/actors/owner", "VALID")
    )
    return ledger


def _table_rows(text: str) -> list[list[str]]:
    """The cells of every Markdown table row in *text*."""
    return [
        [cell.strip() for cell in line.strip("|").split(" | ")]
        for line in text.splitlines()
        if line.startswith("| ")
    ]


@pytest.mark.spec("CEH-01-003")
@pytest.mark.spec("CEH-01-005")
def test_the_table_renders_one_markdown_table_per_case(tmp_path):
    path = _write(_small_ledger(), tmp_path / "ledger.jsonl")
    text = case_history_report([path], fmt=HistoryFormat.TABLE)
    assert text.count(f"## Case `{CASE}`") == 1
    assert "- Source: complete_copy" in text
    rows = _table_rows(text)
    assert rows[0] == list(TABLE_HEADERS)
    assert rows[1] == ["---"] * len(TABLE_HEADERS)
    body = rows[2:]
    assert body
    assert all(len(row) == len(TABLE_HEADERS) for row in body)
    actor = TABLE_HEADERS.index("Actor")
    obj = TABLE_HEADERS.index("Object")
    assert {row[actor] for row in body} == {"Case Manager"}
    for row in body:
        assert not _OPAQUE.search(row[actor] + row[obj]), row


@pytest.mark.spec("CEH-01-003")
@pytest.mark.spec("CEH-01-005")
def test_the_json_form_is_the_history_model(tmp_path):
    path = _write(_small_ledger(), tmp_path / "ledger.jsonl")
    text = case_history_report([path], fmt=HistoryFormat.JSON, case_id=CASE)
    expected = CaseEventHistories(
        histories={CASE: _small_ledger().history()}
    ).model_dump(mode="json")
    assert json.loads(text) == expected
    assert expected["histories"][CASE]["events"]


@pytest.mark.spec("CEH-01-008")
def test_input_with_no_entry_or_without_the_named_case_is_refused(tmp_path):
    empty = tmp_path / "empty.jsonl"
    empty.write_text("{not json\n", encoding="utf-8")
    with pytest.raises(CaseHistoryInputError, match="no case ledger entry"):
        case_history_report([empty], fmt=HistoryFormat.TABLE)
    path = _write(_small_ledger(), tmp_path / "ledger.jsonl")
    with pytest.raises(CaseHistoryInputError, match="is not in the input"):
        case_history_report(
            [path], fmt=HistoryFormat.JSON, case_id="urn:uuid:other"
        )


def test_each_section_states_what_bounds_its_trust():
    history = CaseEventHistory(
        case_id=CASE,
        source=LedgerSource.MERGED_REPLICAS,
        end_confirmed=False,
        missing_log_indices=[2, 3],
        unusable_rows=[
            UnusableRow(path=Path("a.jsonl"), line=4, reason="no log index")
        ],
        excluded=[
            ExcludedState(
                log_index=5,
                semantic_type="add_participant_status_to_participant",
                participant=VENDOR,
                dimension=Dimension.RM,
                named="RECEIVED",
                reached="ACCEPTED",
            )
        ],
        unreadable_entries=[UnreadableEntry(log_index=6, reason="no stamp")],
    )
    ledger = CaseLedger(
        case_id=CASE,
        source=LedgerSource.MERGED_REPLICAS,
        rows=[],
        copies=[Path("a.jsonl")],
    )
    text = render_table([(history, ledger)], {})
    for line in (
        "- Source: merged_replicas",
        "- End confirmed: no",
        "- Missing log indices: 2, 3",
        "- Conflicting log indices: none",
        "- Events: 0",
        "- Unusable row: a.jsonl line 4: no log index",
        "- Excluded state at entry 5: rm RECEIVED is behind ACCEPTED",
        "- Unreadable entry 6: no stamp",
    ):
        assert line in text.splitlines(), line


def test_without_a_named_case_every_case_gets_its_own_section(tmp_path):
    first = _small_ledger()
    second = _small_ledger()
    for entry in second.entries:
        entry["caseId"] = "urn:uuid:case-0"
    path = tmp_path / "two.jsonl"
    path.write_text(
        "\n".join(json.dumps(e) for e in first.entries + second.entries),
        encoding="utf-8",
    )
    text = case_history_report([path], fmt=HistoryFormat.TABLE)
    headings = [line for line in text.splitlines() if line.startswith("## ")]
    assert headings == [
        "## Case `urn:uuid:case-0`",
        f"## Case `{CASE}`",
    ]


def test_a_pipe_or_line_break_in_a_name_cannot_break_the_table():
    entry = _accept(
        {"id": VENDOR, "type": "Organization", "name": "Acme | Co\r\nLtd"},
        {"id": INVITEE, "type": "Organization", "name": "Invitee\rInc"},
    )
    history = CaseEventHistory(
        case_id=CASE,
        source=LedgerSource.COMPLETE_COPY,
        end_confirmed=True,
        events=[_event()],
    )
    ledger = CaseLedger(
        case_id=CASE,
        source=LedgerSource.COMPLETE_COPY,
        rows=[],
        copies=[],
    )
    names = label_names({"f": [entry]})
    row = event_row(_event(), entry, names, CASE)
    assert row.actor == "Acme | Co\r\nLtd"
    text = render_table([(history, ledger)], names)
    assert "\r" not in text
    rows = _table_rows(text)
    assert all(len(r) == len(TABLE_HEADERS) for r in rows)


def test_a_row_in_no_case_is_listed_in_the_table_as_in_the_json(tmp_path):
    path = _write(_small_ledger(), tmp_path / "ledger.jsonl")
    with path.open("a", encoding="utf-8") as fh:
        fh.write("{not json\n")
    text = case_history_report([path], fmt=HistoryFormat.TABLE)
    data = json.loads(case_history_report([path], fmt=HistoryFormat.JSON))
    assert len(data["unusable_rows"]) == 1
    lines = text.splitlines()
    at = lines.index("## Rows in no case")
    assert lines[at + 2].startswith(f"- Unusable row: {path}")


def test_the_table_and_the_json_list_cases_in_one_order(tmp_path):
    first = _small_ledger()
    second = _small_ledger()
    for entry in second.entries:
        entry["caseId"] = "urn:uuid:case-0"
    path = tmp_path / "two.jsonl"
    path.write_text(
        "\n".join(json.dumps(e) for e in first.entries + second.entries),
        encoding="utf-8",
    )
    text = case_history_report([path], fmt=HistoryFormat.TABLE)
    data = json.loads(case_history_report([path], fmt=HistoryFormat.JSON))
    headings = [
        line.removeprefix("## Case `").removesuffix("`")
        for line in text.splitlines()
        if line.startswith("## Case ")
    ]
    assert headings == list(data["histories"])
