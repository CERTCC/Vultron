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

"""Whether a ledger's end is confirmed (CEH-02-006, CEH-02-009).

A copy is selected by completeness relative to the input, so a replica cut off
at the tail passes when no fuller copy is handed over.  ``end_confirmed`` is
set only when the entries prove the last entry is the case's last.
"""

import json
from pathlib import Path

import pytest

from vultron.demo.recordings.layout import recording_path
from vultron.measure.ledger import (
    LedgerSource,
    case_manager_ids,
    ends_in_case_closure,
    read_case_ledgers,
    read_ledger_file,
)

_CASE = "urn:uuid:case-1"
_MANAGER = "https://example.org/actors/case-actor"
_VENDOR = "https://example.org/actors/vendor"

#: A committed recording: the CASE_MANAGER's own copy, ending in its closure.
_RECORDING = recording_path("rcv")


def _entry(
    index: int, semantic_type: str = "add_note", **payload: object
) -> dict:
    return {
        "caseId": _CASE,
        "logIndex": index,
        "entryHash": f"h{index}",
        "semanticType": semantic_type,
        "payloadSnapshot": payload,
    }


def _genesis() -> dict:
    """The genesis entry seating the CASE_MANAGER (CM-14-009)."""
    return _entry(
        0,
        "create_case",
        type="Create",
        actor=_MANAGER,
        object={
            "type": "VulnerabilityCase",
            "caseParticipants": [
                {
                    "type": "CaseParticipant",
                    "attributedTo": _MANAGER,
                    "caseRoles": ["coordinator", "case_manager"],
                },
                {
                    "type": "CaseParticipant",
                    "attributedTo": {"id": _VENDOR},
                    "caseRoles": ["vendor"],
                },
            ],
        },
    )


def _closure(index: int, actor: str) -> dict:
    """*actor*'s own ``RM.CLOSED`` status entry."""
    return _entry(
        index,
        "add_participant_status_to_participant",
        type="Add",
        actor=actor,
        object={
            "type": "ParticipantStatus",
            "attributedTo": actor,
            "rmState": "CLOSED",
        },
    )


def _write(path: Path, entries: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    return path


@pytest.mark.spec("CEH-02-006")
def test_a_recording_ending_in_its_closure_has_a_confirmed_end():
    case = next(iter(read_case_ledgers([_RECORDING]).cases.values()))

    assert case.source is LedgerSource.COMPLETE_COPY
    assert case.end_confirmed


@pytest.mark.spec("CEH-02-006")
@pytest.mark.spec("CEH-02-009")
def test_a_lone_replica_cut_off_at_the_tail_has_no_confirmed_end(tmp_path):
    # A participant whose report closed early holds a gapless prefix: it is
    # complete as far as the input shows, but its end is not the case's.
    prefix = read_ledger_file(_RECORDING).entries[:20]
    replica = tmp_path / "vendor.jsonl"
    replica.write_text("\n".join(json.dumps(e) for e in prefix) + "\n")

    case = next(iter(read_case_ledgers([replica]).cases.values()))

    assert case.source is LedgerSource.COMPLETE_COPY
    assert case.missing_log_indices == []
    assert not case.end_confirmed


def test_a_complete_copy_beside_a_truncated_replica_is_not_confirmed(tmp_path):
    entries = [_genesis(), _entry(1), _entry(2)]
    full = _write(tmp_path / "a.jsonl", entries)
    short = _write(tmp_path / "b.jsonl", entries[:2])

    case = read_case_ledgers([full, short]).cases[_CASE]

    assert case.complete_copy_path == full
    assert not case.end_confirmed


def test_two_copies_ending_on_the_same_entry_confirm_it(tmp_path):
    entries = [_genesis(), _entry(1), _entry(2)]
    first = _write(tmp_path / "a.jsonl", entries)
    second = _write(tmp_path / "b.jsonl", entries)

    case = read_case_ledgers([first, second]).cases[_CASE]

    assert case.source is LedgerSource.COMPLETE_COPY
    assert case.end_confirmed


def test_merged_replicas_ending_on_the_same_entry_confirm_it(tmp_path):
    first = _write(tmp_path / "a.jsonl", [_genesis(), _entry(2)])
    second = _write(tmp_path / "b.jsonl", [_entry(1), _entry(2)])

    case = read_case_ledgers([first, second]).cases[_CASE]

    assert case.merged
    assert case.end_confirmed


def test_conflicting_copies_never_confirm_an_end(tmp_path):
    first = _write(tmp_path / "a.jsonl", [_genesis(), _entry(1)])
    forked = {**_entry(1), "entryHash": "forked"}
    second = _write(tmp_path / "b.jsonl", [_genesis(), forked, _entry(2)])
    third = _write(tmp_path / "c.jsonl", [_genesis(), forked, _entry(2)])

    case = read_case_ledgers([first, second, third]).cases[_CASE]

    assert case.conflicting_log_indices == [1]
    assert not case.end_confirmed


class TestClosureEnd:
    def test_the_case_managers_own_closure_last_confirms_the_end(
        self, tmp_path
    ):
        path = _write(
            tmp_path / "a.jsonl",
            [_genesis(), _entry(1), _closure(2, _MANAGER)],
        )

        case = read_case_ledgers([path]).cases[_CASE]

        assert case.end_confirmed

    def test_a_participants_own_closure_does_not(self, tmp_path):
        path = _write(tmp_path / "a.jsonl", [_genesis(), _closure(1, _VENDOR)])

        assert not read_case_ledgers([path]).cases[_CASE].end_confirmed

    def test_a_closure_followed_by_entries_does_not(self, tmp_path):
        entries = [_genesis(), _closure(1, _MANAGER), _entry(2)]

        assert not ends_in_case_closure(entries)

    def test_a_closure_without_the_genesis_names_no_manager(self):
        assert case_manager_ids([_closure(3, _MANAGER)]) == set()
        assert not ends_in_case_closure([_closure(3, _MANAGER)])

    def test_the_manager_is_read_from_the_participant_records(self):
        assert case_manager_ids([_genesis()]) == {_MANAGER}

    def test_no_placed_entry_is_no_closure(self):
        assert not ends_in_case_closure([])
        assert not ends_in_case_closure([{"logIndex": "x"}])
