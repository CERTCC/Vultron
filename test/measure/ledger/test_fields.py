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

"""The dimension-state walker reads every depth and spelling (CEH-02-002, DRPT-02-003)."""

import json
from pathlib import Path

import pytest

from vultron.measure.ledger import (
    FLAT_SPELLINGS,
    Dimension,
    actor_uri,
    case_id_of,
    coerce_int,
    entry_hash_of,
    first_present,
    log_index_of,
    payload_of,
    read_dimension_state,
    read_ledger_file,
)


def _spellings(dimension: Dimension, state: str) -> list[dict]:
    """Every spelling of *state* for *dimension*, as a status-bearing dict."""
    return [
        {dimension.value: state},
        {dimension.value: {"state": state}},
        *({flat: state} for flat in FLAT_SPELLINGS[dimension]),
    ]


def _depths(status: dict) -> list[dict]:
    """Every depth a payload snapshot may carry *status* at."""
    return [
        status,
        {"type": "Add", "object": status},
        {"type": "Add", "object_": status},
        {"type": "Add", "object": {"caseStatus": status}},
        {"type": "Add", "object": {"case_status": status}},
        {"type": "Create", "object": {"caseStatuses": [{}, status]}},
        {"type": "Create", "object": {"case_statuses": [status]}},
    ]


def _write_fixture(path: Path, state: str) -> Path:
    """Write one ledger row per (dimension, depth, spelling) holding *state*."""
    lines: list[str] = []
    index = 0
    for dimension in Dimension:
        for status in _spellings(dimension, state):
            for snapshot in _depths(status):
                lines.append(
                    json.dumps(
                        {
                            "caseId": "urn:case:1",
                            "logIndex": index,
                            "entryHash": f"h{index}",
                            "dimension": dimension.value,
                            "payloadSnapshot": snapshot,
                        }
                    )
                )
                index += 1
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@pytest.mark.spec("CEH-02-002")
def test_every_depth_and_spelling_reads_the_same_state(tmp_path):
    ledger = read_ledger_file(_write_fixture(tmp_path / "f.jsonl", "ACCEPTED"))

    assert not ledger.unusable_rows
    expected_rows = sum(
        len(_spellings(d, "ACCEPTED")) * len(_depths({})) for d in Dimension
    )
    assert len(ledger.entries) == expected_rows
    for entry in ledger.entries:
        dimension = Dimension(entry["dimension"])
        assert read_dimension_state(payload_of(entry), dimension) == (
            "ACCEPTED"
        ), entry


@pytest.mark.spec("CEH-02-002")
@pytest.mark.parametrize("dimension", list(Dimension))
def test_a_dimension_absent_at_every_depth_reads_none(dimension):
    other = next(d for d in Dimension if d is not dimension)
    for snapshot in _depths({other.value: "X"}):
        assert read_dimension_state(snapshot, dimension) is None


def test_a_self_referencing_snapshot_terminates():
    snapshot: dict = {"type": "Add"}
    snapshot["object"] = snapshot
    assert read_dimension_state(snapshot, Dimension.RM) is None


def test_a_non_list_case_statuses_is_ignored():
    snapshot = {"object": {"caseStatuses": "corrupt"}, "pxaState": "pxa"}
    assert read_dimension_state(snapshot, Dimension.PXA) == "pxa"


class TestEnvelopeAccessors:
    @pytest.mark.spec("DRPT-02-003")
    def test_both_spellings_are_read(self):
        camel = {"caseId": "c", "logIndex": 3, "entryHash": "h"}
        snake = {"case_id": "c", "log_index": 3, "entry_hash": "h"}
        for entry in (camel, snake):
            assert case_id_of(entry) == "c"
            assert log_index_of(entry) == 3
            assert entry_hash_of(entry) == "h"

    @pytest.mark.parametrize("value", [None, -1, True, 1.0, "3"])
    def test_an_unusable_log_index_is_none(self, value):
        assert log_index_of({"logIndex": value}) is None

    @pytest.mark.parametrize("value", [None, "", "   ", 7])
    def test_a_blank_or_non_string_id_is_none(self, value):
        assert case_id_of({"caseId": value}) is None
        assert entry_hash_of({"entryHash": value}) is None

    def test_a_non_dict_payload_reads_as_empty(self):
        assert payload_of({"payloadSnapshot": "corrupt"}) == {}
        assert payload_of({}) == {}

    def test_first_present_skips_none(self):
        assert first_present({"a": None, "b": 2}, "a", "b") == 2
        assert first_present({}, "a", default="d") == "d"

    def test_coerce_int_falls_back(self):
        assert coerce_int("4", default=-1) == 4
        assert coerce_int("x", default=-1) == -1
        assert coerce_int(None, default=-1) == -1

    @pytest.mark.parametrize(
        ("actor", "expected"),
        [
            ("https://x/actors/a", "https://x/actors/a"),
            ("", None),
            ({"id": "https://x/actors/a"}, "https://x/actors/a"),
            ({"id_": "https://x/actors/a"}, "https://x/actors/a"),
            ({"type": "Person"}, None),
            (42, None),
        ],
    )
    def test_actor_uri_shapes(self, actor, expected):
        assert actor_uri(actor) == expected
