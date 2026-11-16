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

"""The Vultron case reader over a case-ledger file (#6441).

It satisfies ``CaseReader``, returns every entry of a committed recording
unchanged and in order with nothing untranslated, cites each entry by its own
ledger id, and refuses a missing, unreadable or malformed file whole, naming
the file.

Spec: CRD-01-001, CRD-01-003, CRD-01-004, CRD-01-005, CRD-02-001,
CRD-02-004.
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from test.support.case_reader import projected_history
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_reading import CaseReading, UnobservableFact
from vultron.core.ports.case_reader import CaseReader
from vultron.demo.recordings.layout import RECORDINGS_DIR
from vultron.errors import CaseLedgerFileError, VultronError
from vultron.shadow.readers import VultronCaseReader
from vultron.shadow.readers.vultron_ledger import _summary

_RECORDINGS = sorted(RECORDINGS_DIR.glob("*/case-actor.jsonl"))
_RECORDING = RECORDINGS_DIR / "rv" / "case-actor.jsonl"


def _rows(path: Path) -> list[dict[str, Any]]:
    """The file's rows, as written."""
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _write(path: Path, lines: list[str]) -> str:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def _read(case_id: str) -> CaseReading:
    return VultronCaseReader().read_case(case_id)


def test_there_are_committed_recordings_to_read():
    assert _RECORDING in _RECORDINGS


@pytest.mark.spec("CRD-01-001")
def test_the_vultron_case_reader_satisfies_the_port():
    assert isinstance(VultronCaseReader(), CaseReader)


@pytest.mark.spec("CRD-01-003")
@pytest.mark.parametrize("path", _RECORDINGS, ids=lambda p: p.parent.name)
def test_a_recording_reads_back_every_entry_unchanged_and_in_order(path):
    reading = _read(str(path))
    dumped = [
        entry.model_dump(by_alias=True, mode="json", exclude_none=True)
        for entry in reading.ledger
    ]
    assert dumped == _rows(path)


@pytest.mark.spec("CRD-01-003")
@pytest.mark.spec("CRD-01-005")
@pytest.mark.spec("CRD-02-001")
def test_a_recording_has_nothing_untranslated_inferred_or_unobservable():
    reading = _read(str(_RECORDING))
    assert reading.untranslated == ()
    assert reading.inferences == ()
    assert reading.unobservable == ()


@pytest.mark.spec("CRD-02-004")
def test_the_reading_copies_the_readers_declaration():
    declared = (UnobservableFact(fact="f", why="w"),)

    class _Declaring(VultronCaseReader):
        unobservable = declared

    assert _Declaring().read_case(str(_RECORDING)).unobservable == declared


@pytest.mark.spec("CRD-01-003")
def test_the_readings_ledger_is_one_the_projection_accepts():
    history = projected_history(_read(str(_RECORDING)))
    assert history.unreadable_entries == []
    assert history.missing_log_indices == []
    assert history.events


@pytest.mark.spec("CRD-01-004")
def test_each_entry_cites_itself_by_its_ledger_id():
    reading = _read(str(_RECORDING))
    assert [(c.entry_id, c.source_record) for c in reading.citations] == [
        (entry.id_, entry.id_) for entry in reading.ledger
    ]
    assert [entry.id_ for entry in reading.ledger] == [
        row["id"] for row in _rows(_RECORDING)
    ]


def test_a_missing_file_raises_a_domain_error_naming_it(tmp_path):
    missing = str(tmp_path / "no-such-ledger.jsonl")
    with pytest.raises(CaseLedgerFileError) as caught:
        _read(missing)
    assert isinstance(caught.value, VultronError)
    assert caught.value.path == missing
    assert missing in str(caught.value)


def test_an_unreadable_file_raises_a_domain_error_naming_it(tmp_path):
    path = tmp_path / "not-text.jsonl"
    path.write_bytes(b"\xff\xfe\x00not utf-8\n")
    with pytest.raises(CaseLedgerFileError, match=re.escape(str(path))):
        _read(str(path))


def test_a_directory_raises_a_domain_error_naming_it(tmp_path):
    with pytest.raises(CaseLedgerFileError, match=re.escape(str(tmp_path))):
        _read(str(tmp_path))


def test_an_empty_file_raises_rather_than_returning_no_case(tmp_path):
    path = _write(tmp_path / "empty.jsonl", [""])
    with pytest.raises(CaseLedgerFileError, match="no ledger entry"):
        _read(path)


def test_every_malformed_row_is_named_and_no_partial_ledger_returns(
    tmp_path,
):
    """Good rows around two bad ones: the whole file is refused, and the
    error names the file and both bad lines."""
    good = [json.dumps(row) for row in _rows(_RECORDING)]
    path = _write(
        tmp_path / "damaged.jsonl",
        [good[0], "{not json", good[1], "[1, 2]", *good[2:]],
    )
    with pytest.raises(CaseLedgerFileError) as caught:
        _read(path)
    assert caught.value.path == path
    problems = _problems(caught.value)
    assert len(problems) == 2
    assert problems[0].startswith(f"{path} line 2: Parse error")
    assert problems[1].startswith(f"{path} line 4: Parse error")
    assert all(problem in str(caught.value) for problem in problems)


def test_a_json_object_that_is_not_a_ledger_entry_is_refused(tmp_path):
    good = [json.dumps(row) for row in _rows(_RECORDING)]
    path = _write(
        tmp_path / "odd.jsonl", [good[0], json.dumps({"id": "x"}), good[1]]
    )
    with pytest.raises(CaseLedgerFileError) as caught:
        _read(path)
    [problem] = _problems(caught.value)
    assert problem.startswith(f"{path} line 2: not a case ledger entry")


def test_entries_out_of_log_index_order_are_refused(tmp_path):
    good = [json.dumps(row) for row in _rows(_RECORDING)]
    path = _write(tmp_path / "shuffled.jsonl", [good[1], good[0], *good[2:]])
    with pytest.raises(CaseLedgerFileError) as caught:
        _read(path)
    first, second = (_rows(_RECORDING)[i]["logIndex"] for i in (0, 1))
    assert _problems(caught.value) == [
        f"the ledger is not in log-index order: {first} follows {second}"
    ]


def test_entries_of_two_cases_are_refused(tmp_path):
    case_id = _rows(_RECORDING)[0]["caseId"]
    other = next(p for p in _RECORDINGS if _rows(p)[0]["caseId"] != case_id)
    rows = _rows(_RECORDING)[:2] + _rows(other)[2:3]
    path = _write(tmp_path / "mixed.jsonl", [json.dumps(r) for r in rows])
    with pytest.raises(CaseLedgerFileError, match="holds entries of"):
        _read(path)


def _problems(error: CaseLedgerFileError) -> list[str]:
    return [violation.message for violation in error.violations]


def test_both_kinds_of_bad_row_are_reported_in_line_order(tmp_path):
    good = [json.dumps(row) for row in _rows(_RECORDING)]
    path = _write(
        tmp_path / "both.jsonl",
        [good[0], json.dumps({"id": "x"}), "{not json", *good[1:]],
    )
    with pytest.raises(CaseLedgerFileError) as caught:
        _read(path)
    problems = _problems(caught.value)
    assert [p.split(":")[0] for p in problems] == [
        f"{path} line 2",
        f"{path} line 3",
    ]
    assert "not a case ledger entry" in problems[0]
    assert "Parse error" in problems[1]


def test_a_bad_row_and_an_out_of_order_pair_are_both_reported(tmp_path):
    good = [json.dumps(row) for row in _rows(_RECORDING)]
    path = _write(
        tmp_path / "worse.jsonl", ["{not json", good[1], good[0], *good[2:]]
    )
    with pytest.raises(CaseLedgerFileError) as caught:
        _read(path)
    problems = _problems(caught.value)
    assert len(problems) == 2
    assert problems[0].startswith(f"{path} line 1: Parse error")
    assert problems[1].startswith("the ledger is not in log-index order")


def test_a_path_outside_the_readers_root_is_refused_unopened(tmp_path):
    root = tmp_path / "ledgers"
    root.mkdir()
    outside = tmp_path / "elsewhere.jsonl"
    outside.write_bytes(_RECORDING.read_bytes())
    with pytest.raises(CaseLedgerFileError) as caught:
        VultronCaseReader(root=root).read_case(str(outside))
    assert _problems(caught.value) == [
        f"it is outside the ledger directory {root.resolve()}"
    ]
    escape = root / ".." / "elsewhere.jsonl"
    with pytest.raises(CaseLedgerFileError, match="outside the ledger"):
        VultronCaseReader(root=root).read_case(str(escape))


def test_a_path_inside_the_readers_root_is_read():
    reader = VultronCaseReader(root=RECORDINGS_DIR)
    assert reader.read_case(str(_RECORDING)).ledger


def test_a_symlink_inside_the_root_to_a_file_outside_it_is_refused(tmp_path):
    root = tmp_path / "ledgers"
    root.mkdir()
    outside = tmp_path / "elsewhere.jsonl"
    outside.write_bytes(_RECORDING.read_bytes())
    link = root / "link.jsonl"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("the filesystem refuses symbolic links")
    with pytest.raises(CaseLedgerFileError, match="outside the ledger"):
        VultronCaseReader(root=root).read_case(str(link))


def test_a_relative_case_id_is_taken_relative_to_the_root(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    reader = VultronCaseReader(root=RECORDINGS_DIR)
    relative = str(_RECORDING.relative_to(RECORDINGS_DIR))
    assert reader.read_case(relative).ledger == _read(str(_RECORDING)).ledger


@pytest.mark.parametrize("root", [None, "root"])
def test_a_path_with_a_nul_byte_raises_the_domain_error(tmp_path, root):
    reader = VultronCaseReader(root=tmp_path if root else None)
    with pytest.raises(CaseLedgerFileError) as caught:
        reader.read_case("bad\x00name.jsonl")
    assert _problems(caught.value)[0].startswith("it is not a usable path")


def test_a_repeated_row_is_reported_once(tmp_path):
    good = [json.dumps(row) for row in _rows(_RECORDING)]
    path = _write(tmp_path / "repeat.jsonl", [good[0], good[0], *good[1:]])
    with pytest.raises(CaseLedgerFileError) as caught:
        _read(path)
    problems = _problems(caught.value)
    assert len(problems) == 1
    assert problems[0].startswith("the ledger repeats entries")


def test_a_model_level_error_is_summarised_without_a_field():
    with pytest.raises(ValidationError) as caught:
        CaseLedgerEntry.model_validate([1])
    assert _summary(caught.value) == caught.value.errors()[0]["msg"]
