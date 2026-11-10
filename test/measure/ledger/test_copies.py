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

"""Canonical-copy selection, replica merge and gap reporting (CEH-02-003 to CEH-02-010)."""

import json
import shutil
from pathlib import Path

import pytest

from vultron.demo.recordings.layout import recording_path
from vultron.measure.ledger import (
    LedgerSource,
    case_ledgers_from_files,
    read_case_ledgers,
    read_ledger_file,
)

_CASE = "urn:uuid:case-1"
_OTHER_CASE = "urn:uuid:case-2"

#: A committed canonical recording: the CASE_MANAGER's own copy of a real run.
_RECORDING = recording_path("rcv")


def _entry(index: int, case_id: str = _CASE, **extra: object) -> dict:
    """A minimal ledger entry at *index* of *case_id*."""
    return {
        "caseId": case_id,
        "logIndex": index,
        "entryHash": f"{case_id}#{index}",
        "semanticType": "add_participant_status",
        "payloadSnapshot": {"rmState": "ACCEPTED"},
        **extra,
    }


def _write(path: Path, entries: list[dict], *raw_lines: str) -> Path:
    """Write *entries* (then any *raw_lines*) to *path* as JSONL."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(e) for e in entries] + list(raw_lines)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _indices(rows) -> list[int]:
    return [placed.log_index for placed in rows]


@pytest.mark.spec("CEH-02-003")
@pytest.mark.spec("CEH-02-010")
def test_both_naming_shapes_build_the_same_history(tmp_path):
    entries = [_entry(i) for i in range(4)]
    recording = _write(tmp_path / "rcv" / "case-actor.jsonl", entries)
    dump = _write(
        tmp_path / "demo" / "vendor" / "case-1-case-ledger.jsonl", entries
    )
    unfamiliar = _write(tmp_path / "x" / "ledger.data", entries)

    histories = [
        read_case_ledgers([path]).cases[_CASE]
        for path in (recording, dump, unfamiliar)
    ]

    assert {h.source for h in histories} == {LedgerSource.CANONICAL_COPY}
    assert all(h.entries == entries for h in histories)


@pytest.mark.spec("CEH-02-010")
def test_the_layer_reads_only_the_files_it_is_named(tmp_path):
    named = _write(tmp_path / "a.jsonl", [_entry(0)])
    _write(tmp_path / "b-case-ledger.jsonl", [_entry(0, _OTHER_CASE)])

    read = read_case_ledgers([named])

    assert list(read.cases) == [_CASE]


@pytest.mark.spec("CEH-02-009")
@pytest.mark.spec("CEH-02-004")
def test_a_renamed_and_moved_recording_is_still_canonical(tmp_path):
    original = read_ledger_file(_RECORDING).entries
    moved = tmp_path / "somewhere-else" / "not-a-ledger-name.txt"
    moved.parent.mkdir()
    shutil.copyfile(_RECORDING, moved)
    replica = _write(tmp_path / "vendor" / "x.jsonl", original[:5])

    read = read_case_ledgers([replica, moved])

    (case,) = read.cases.values()
    assert case.source is LedgerSource.CANONICAL_COPY
    assert case.canonical_path == moved
    assert case.entries == original
    assert case.missing_log_indices == []


@pytest.mark.spec("CEH-02-004")
def test_the_complete_copy_wins_over_a_truncated_replica(tmp_path):
    complete = [_entry(i) for i in range(6)]
    truncated = _write(tmp_path / "vendor.jsonl", complete[:3])
    manager = _write(tmp_path / "manager.jsonl", complete)

    case = read_case_ledgers([truncated, manager]).cases[_CASE]

    assert case.source is LedgerSource.CANONICAL_COPY
    assert not case.merged
    assert case.canonical_path == manager
    assert case.entries == complete
    assert case.copies == [truncated, manager]


@pytest.mark.spec("CEH-02-004")
def test_a_copy_with_a_gap_is_never_canonical(tmp_path):
    # A replica that missed a lapsed-consent window (CM-10-005) holds a gap.
    gapped = _write(
        tmp_path / "vendor.jsonl", [_entry(0), _entry(1), _entry(3)]
    )

    case = read_case_ledgers([gapped]).cases[_CASE]

    assert case.merged
    assert case.missing_log_indices == [2]


@pytest.mark.spec("CEH-02-005")
def test_overlapping_replicas_merge_each_entry_once(tmp_path):
    reporter = _write(tmp_path / "r.jsonl", [_entry(i) for i in (0, 1, 2)])
    vendor = _write(tmp_path / "v.jsonl", [_entry(i) for i in (2, 3)])
    # Each holds an entry the other lacks, so neither is the whole ledger.
    late = _write(tmp_path / "l.jsonl", [_entry(i) for i in (1, 2, 3, 4)])

    case = read_case_ledgers([reporter, vendor, late]).cases[_CASE]

    assert case.source is LedgerSource.MERGED_REPLICAS
    assert case.canonical_path is None
    assert _indices(case.rows) == [0, 1, 2, 3, 4]
    assert len({p.entry_hash for p in case.rows}) == 5
    assert case.missing_log_indices == []


@pytest.mark.spec("CEH-02-006")
@pytest.mark.spec("CEH-06-003")
def test_a_merge_reports_the_indices_no_replica_supplied(tmp_path):
    # Each replica is partial, and together they still miss 2 and 5.
    first = _write(tmp_path / "a.jsonl", [_entry(i) for i in (0, 1, 3)])
    second = _write(tmp_path / "b.jsonl", [_entry(i) for i in (3, 4, 6)])

    case = read_case_ledgers([first, second]).cases[_CASE]

    assert case.merged
    assert case.missing_log_indices == [2, 5]
    assert _indices(case.rows) == [0, 1, 3, 4, 6]


def test_a_complete_copy_with_an_unplaceable_row_is_not_canonical(tmp_path):
    bad_index = _entry(2, logIndex="2")
    path = _write(tmp_path / "a.jsonl", [_entry(0), _entry(1), bad_index])

    read = read_case_ledgers([path])

    case = read.cases[_CASE]
    assert case.merged
    assert case.missing_log_indices == []
    assert [r.line for r in case.unusable_rows] == [3]
    assert read.unusable_rows == case.unusable_rows


def test_an_unparseable_row_keeps_its_file_from_being_canonical(tmp_path):
    path = _write(tmp_path / "a.jsonl", [_entry(0), _entry(1)], "{cut off")

    read = read_case_ledgers([path])

    assert read.cases[_CASE].merged
    assert read.cases[_CASE].unusable_rows == []
    assert [r.line for r in read.unusable_rows] == [3]


def test_a_complete_copy_beside_a_damaged_replica_is_canonical(tmp_path):
    manager = _write(tmp_path / "m.jsonl", [_entry(i) for i in range(3)])
    replica = _write(tmp_path / "r.jsonl", [_entry(0)], "{cut off")

    case = read_case_ledgers([replica, manager]).cases[_CASE]

    assert case.source is LedgerSource.CANONICAL_COPY
    assert case.canonical_path == manager


def test_a_merge_reports_two_copies_disagreeing_at_one_index(tmp_path):
    first = _write(tmp_path / "a.jsonl", [_entry(0), _entry(1)])
    forked = _entry(1, entryHash="forked")
    second = _write(tmp_path / "b.jsonl", [_entry(0), forked])

    case = read_case_ledgers([first, second]).cases[_CASE]

    assert case.merged
    assert case.conflicting_log_indices == [1]
    assert _indices(case.rows) == [0, 1, 1]


def test_a_replica_contradicting_a_complete_copy_blocks_canonical(tmp_path):
    complete = _write(tmp_path / "a.jsonl", [_entry(i) for i in range(3)])
    corrupt = _write(tmp_path / "b.jsonl", [_entry(0), _entry(2, logIndex=1)])

    case = read_case_ledgers([complete, corrupt]).cases[_CASE]

    assert case.merged
    assert case.conflicting_log_indices == [1, 2]


@pytest.mark.parametrize("reverse", [False, True])
def test_one_hash_at_two_indices_is_a_conflict_in_any_order(tmp_path, reverse):
    first = _write(tmp_path / "p.jsonl", [_entry(0), _entry(2, entryHash="h")])
    second = _write(tmp_path / "q.jsonl", [_entry(1, entryHash="h")])
    paths = [second, first] if reverse else [first, second]

    case = read_case_ledgers(paths).cases[_CASE]

    assert case.merged
    assert case.conflicting_log_indices == [1, 2]
    assert case.missing_log_indices == []
    assert _indices(case.rows) == [0, 1, 2]


def test_a_single_copy_repeating_one_hash_is_not_canonical(tmp_path):
    path = _write(
        tmp_path / "a.jsonl", [_entry(0), _entry(1, entryHash=f"{_CASE}#0")]
    )

    case = read_case_ledgers([path]).cases[_CASE]

    assert case.merged
    assert case.conflicting_log_indices == [0, 1]


def test_a_file_named_twice_is_one_copy(tmp_path):
    path = _write(tmp_path / "a.jsonl", [_entry(0), _entry(1)])

    case = read_case_ledgers([path, path]).cases[_CASE]

    assert case.source is LedgerSource.CANONICAL_COPY
    assert case.copies == [path]
    assert _indices(case.rows) == [0, 1]


def test_a_file_named_twice_reports_its_bad_rows_once(tmp_path):
    path = _write(tmp_path / "a.jsonl", [_entry(0)], "{bad")
    same_file = tmp_path / "." / "a.jsonl"

    read = read_case_ledgers([path, same_file])

    assert [r.line for r in read.unusable_rows] == [2]
    assert (
        case_ledgers_from_files(
            [read_ledger_file(path), read_ledger_file(path)]
        ).unusable_rows
        == read.unusable_rows
    )


@pytest.mark.spec("CEH-02-007")
def test_two_cases_are_two_histories_never_interleaved(tmp_path):
    mixed = _write(
        tmp_path / "mixed.jsonl",
        [_entry(0), _entry(0, _OTHER_CASE), _entry(1), _entry(1, _OTHER_CASE)],
    )
    other = _write(tmp_path / "other.jsonl", [_entry(2, _OTHER_CASE)])

    read = read_case_ledgers([mixed, other])

    assert list(read.cases) == sorted([_CASE, _OTHER_CASE])
    for case_id, case in read.cases.items():
        assert {e["caseId"] for e in case.entries} == {case_id}
    assert _indices(read.cases[_CASE].rows) == [0, 1]
    assert _indices(read.cases[_OTHER_CASE].rows) == [0, 1, 2]
    assert read.cases[_OTHER_CASE].copies == [mixed, other]


@pytest.mark.spec("CEH-02-008")
def test_a_malformed_row_is_reported_and_the_rest_is_read(tmp_path):
    no_index = {k: v for k, v in _entry(9).items() if k != "logIndex"}
    path = _write(
        tmp_path / "a.jsonl",
        [_entry(0), _entry(1), no_index],
        "{truncated",
        json.dumps(_entry(2)),
    )

    read = read_case_ledgers([path])

    case = read.cases[_CASE]
    assert _indices(case.rows) == [0, 1, 2]
    # A damaged copy may be missing the entry its bad row was, so it is never
    # read as the whole ledger.
    assert case.merged
    assert [r.line for r in case.unusable_rows] == [3]
    assert [(r.line, r.reason.split(":")[0]) for r in read.unusable_rows] == [
        (3, "no usable logIndex (a ledger entry needs all three)"),
        (4, "Parse error"),
    ]


def test_an_entry_missing_every_key_names_all_three(tmp_path):
    path = _write(tmp_path / "a.jsonl", [{"semanticType": "x"}])

    read = read_case_ledgers([path])

    assert read.cases == {}
    (row,) = read.unusable_rows
    assert row.reason.startswith("no usable caseId, logIndex, entryHash")


def test_no_files_is_an_empty_read():
    read = case_ledgers_from_files([])
    assert read.cases == {}
    assert read.unusable_rows == []
