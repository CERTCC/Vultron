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

"""The normal form two runs are compared in (DEMOCI-11-058 to DEMOCI-11-060).

The recording clock ticks 10 ms on every read and every id is drawn from one
seeded generator, so a shifted clock or one extra draw moves every later
timestamp, digest and id without changing what the scenario did.  These tests
hold the line between that and a real change: a changed note text, an added
entry and a changed check label all survive the normalizer.
"""

import json
import re
from dataclasses import replace

import pytest

from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.demo.recordings.traces import (
    CHECKS_FILENAME,
    DIGEST_KEY_SUFFIX,
    DIGEST_PLACEHOLDER,
    LEDGER_FILENAME,
    TIMESTAMP_PLACEHOLDER,
    ScenarioRun,
    normalize_run,
    prune_runs,
    read_runs,
    write_run,
)
from vultron.demo.utils.check_tree import (
    CheckKind,
    CheckNode,
    CheckOutcome,
)
from vultron.errors import DemoRecordingError

CASE_ID = "urn:uuid:ed045a61-5ca4-4c92-b278-3dff7bb2199f"
ACTIVITY_ID = "urn:uuid:04d8febf-f9aa-5967-a17f-54e8c633ea16"
VENDOR = "http://actor1:7999/api/v2/actors/actor1"
CASE_ACTOR = "http://case-actor:7999/api/v2/actors/case-actor"

#: A second draw of the same two ids, as a run with one extra draw before them
#: would make: different values, same order of first appearance.
OTHER_CASE_ID = "urn:uuid:11111111-1111-4111-8111-111111111111"
OTHER_ACTIVITY_ID = "urn:uuid:22222222-2222-4222-8222-222222222222"

#: A SHA-256 digest as a ledger entry carries one.
_DIGEST_VALUE = re.compile(r'"[0-9a-f]{64}"')


def _entry(
    index: int,
    *,
    case_id: str = CASE_ID,
    activity_id: str = ACTIVITY_ID,
    published: str = "2026-01-01T00:00:00.560000+00:00",
    note: str = "first contact",
    digest: str = "a" * 64,
) -> dict[str, object]:
    """One ledger entry, in the shape the recorder writes one."""
    return {
        "id": f"{case_id}/log/{index}",
        "type": "CaseLedgerEntry",
        "published": published,
        "receivedAt": published,
        "caseId": case_id,
        "logIndex": index,
        "logObjectId": case_id,
        "semanticType": "create_case",
        "payloadSnapshot": {
            "id": activity_id,
            "type": "Create",
            "published": published,
            "actor": CASE_ACTOR,
            "to": [VENDOR],
            "content": note,
        },
        "prevLogHash": "0" * 64,
        "entryHash": digest,
    }


def _ledger(*entries: dict[str, object]) -> str:
    return "".join(f"{json.dumps(entry)}\n" for entry in entries)


CHECKS = (
    CheckNode(
        kind=CheckKind.GATE,
        label=f"case {CASE_ID} reached RM.VALID",
        outcome=CheckOutcome.PASSED,
        reads=("actor1",),
        children=(
            CheckNode(
                kind=CheckKind.CHECK,
                label="the Vendor holds the case",
                outcome=CheckOutcome.PASSED,
                reads=("actor1",),
            ),
        ),
    ),
)


def _run(
    ledger: str | None = None, checks: tuple[CheckNode, ...] = CHECKS
) -> ScenarioRun:
    return ScenarioRun(
        "rv",
        ledger=_ledger(_entry(0), _entry(1)) if ledger is None else ledger,
        checks=checks,
    )


BASE = _run()


class TestWhatSurvivesNormalization:
    @pytest.mark.spec("DEMOCI-11-059")
    def test_a_shifted_clock_compares_equal(self):
        shifted = _run(
            _ledger(
                _entry(0, published="2026-03-04T09:17:21.110000+00:00"),
                _entry(
                    1,
                    published="2026-03-04T09:17:21.120000+00:00",
                    digest="b" * 64,
                ),
            )
        )
        assert normalize_run(shifted) == normalize_run(BASE)

    @pytest.mark.spec("DEMOCI-11-058")
    def test_an_extra_id_draw_compares_equal(self):
        redrawn = _run(
            _ledger(
                _entry(
                    0,
                    case_id=OTHER_CASE_ID,
                    activity_id=OTHER_ACTIVITY_ID,
                ),
                _entry(
                    1,
                    case_id=OTHER_CASE_ID,
                    activity_id=OTHER_ACTIVITY_ID,
                ),
            ),
            checks=(
                replace(
                    CHECKS[0],
                    label=f"case {OTHER_CASE_ID} reached RM.VALID",
                ),
            ),
        )
        assert normalize_run(redrawn) == normalize_run(BASE)

    @pytest.mark.spec("DEMOCI-11-060")
    def test_a_changed_note_text_compares_different(self):
        changed = _run(_ledger(_entry(0), _entry(1, note="second contact")))
        assert normalize_run(changed) != normalize_run(BASE)

    @pytest.mark.spec("DEMOCI-11-060")
    def test_an_added_entry_compares_different(self):
        added = _run(_ledger(_entry(0), _entry(1), _entry(2)))
        assert normalize_run(added) != normalize_run(BASE)
        assert len(normalize_run(added).ledger) == 3

    @pytest.mark.spec("DEMOCI-11-060")
    def test_a_changed_check_label_compares_different(self):
        moved = _run(checks=(replace(CHECKS[0], label="the Vendor answered"),))
        assert normalize_run(moved).ledger == normalize_run(BASE).ledger
        assert normalize_run(moved).checks != normalize_run(BASE).checks


class TestWhatTheNormalizerDoes:
    @pytest.mark.spec("DEMOCI-11-058")
    def test_ids_are_relabelled_by_first_appearance(self):
        first = json.loads(normalize_run(BASE).ledger[0])
        assert first["caseId"] == "urn:uuid:id-1"
        assert first["id"] == "urn:uuid:id-1/log/0"
        assert first["payloadSnapshot"]["id"] == "urn:uuid:id-2"

    @pytest.mark.spec("DEMOCI-11-058")
    def test_one_mapping_covers_the_ledger_and_the_check_labels(self):
        normalized = normalize_run(BASE)
        assert "urn:uuid:id-1" in normalized.ledger[0]
        assert normalized.checks[0].startswith(
            "gate case urn:uuid:id-1 reached RM.VALID -> passed"
        )

    @pytest.mark.spec("DEMOCI-11-060")
    def test_the_casts_actor_uris_are_left_as_they_are(self):
        """The cast is fixed (DEMOCI-11-020), so its ids never shift, and a
        diff that still names actor1 is a diff a person can read."""
        first = json.loads(normalize_run(BASE).ledger[0])
        assert first["payloadSnapshot"]["actor"] == CASE_ACTOR
        assert first["payloadSnapshot"]["to"] == [VENDOR]

    @pytest.mark.spec("DEMOCI-11-059")
    def test_timestamps_and_digests_are_dropped_wherever_they_sit(self):
        first = json.loads(normalize_run(BASE).ledger[0])
        assert first["published"] == TIMESTAMP_PLACEHOLDER
        assert first["receivedAt"] == TIMESTAMP_PLACEHOLDER
        assert first["payloadSnapshot"]["published"] == TIMESTAMP_PLACEHOLDER
        assert first["prevLogHash"] == DIGEST_PLACEHOLDER
        assert first["entryHash"] == DIGEST_PLACEHOLDER

    @pytest.mark.spec("DEMOCI-11-060")
    def test_nothing_else_is_touched(self):
        first = json.loads(normalize_run(BASE).ledger[0])
        assert first["logIndex"] == 0
        assert first["semanticType"] == "create_case"
        assert first["payloadSnapshot"]["content"] == "first contact"

    @pytest.mark.spec("DEMOCI-11-059")
    def test_no_hash_chain_digest_of_a_real_entry_survives(self):
        """Keyed on a digest's shape, not on the two field names.

        A guard that listed ``prevLogHash`` and ``entryHash`` would lose its
        subject to a rename: the list would shrink, the suffix assertion would
        still pass, and the renamed field would silently stop being dropped
        (#5535). A renamed field keeps its 64-character hex value, so it still
        fails here.
        """
        entry = CaseLedgerEntry(
            case_id=CASE_ID,
            log_index=0,
            log_object_id=CASE_ID,
            semantic_type="create_case",
            payload_snapshot={"id": ACTIVITY_ID, "type": "Create"},
            prev_log_hash="0" * 64,
            entry_hash="a" * 64,
        )
        line = json.dumps(
            entry.model_dump(by_alias=True, exclude_none=True, mode="json")
        )
        assert re.search(_DIGEST_VALUE, line), "the fixture holds no digest"

        [normalized] = normalize_run(_run(f"{line}\n")).ledger

        assert not re.search(_DIGEST_VALUE, normalized), (
            "a hash-chain digest survived normalization; every digest field "
            f"of a ledger entry must end in {DIGEST_KEY_SUFFIX!r}"
        )

    def test_a_ledger_line_that_is_not_an_entry_is_refused(self):
        with pytest.raises(DemoRecordingError, match="ledger line 2"):
            normalize_run(_run('{"logIndex": 0}\nnot json\n'))

    def test_a_ledger_line_that_is_not_an_object_is_refused(self):
        with pytest.raises(DemoRecordingError, match="not a ledger entry"):
            normalize_run(_run("[1, 2]\n"))


class TestWrittenRuns:
    def test_a_written_run_reads_back(self, tmp_path):
        write_run(BASE, tmp_path)
        assert read_runs(tmp_path) == {"rv": BASE}

    def test_only_the_two_traces_are_written(self, tmp_path):
        directory = write_run(BASE, tmp_path)
        assert sorted(path.name for path in directory.iterdir()) == sorted(
            (CHECKS_FILENAME, LEDGER_FILENAME)
        )

    def test_a_directory_of_runs_reads_back_by_name(self, tmp_path):
        write_run(BASE, tmp_path)
        write_run(replace(BASE, scenario="rvv"), tmp_path)
        assert sorted(read_runs(tmp_path)) == ["rv", "rvv"]

    def test_a_half_written_run_is_refused(self, tmp_path):
        (tmp_path / "rv").mkdir()
        (tmp_path / "rv" / LEDGER_FILENAME).write_text("{}\n")
        with pytest.raises(DemoRecordingError, match="incomplete"):
            read_runs(tmp_path)

    def test_an_unreadable_check_tree_is_refused(self, tmp_path):
        write_run(BASE, tmp_path)
        (tmp_path / "rv" / CHECKS_FILENAME).write_text("{oops")
        with pytest.raises(DemoRecordingError, match="not readable"):
            read_runs(tmp_path)

    @pytest.mark.parametrize("text", ["", "  \n"], ids=["zeroed", "blank"])
    def test_a_run_with_an_empty_ledger_is_refused(self, tmp_path, text):
        """A recorded run can never have an empty ledger, so two zeroed
        artifacts must not compare equal: that would be the gate passing over
        nothing rather than over no change."""
        write_run(BASE, tmp_path)
        (tmp_path / "rv" / LEDGER_FILENAME).write_text(text)
        with pytest.raises(
            DemoRecordingError, match=r"of 'rv' in .* empty ledger"
        ):
            read_runs(tmp_path)

    def test_a_check_tree_that_is_valid_json_but_no_tree_names_itself(
        self, tmp_path
    ):
        """`tree_from_json` raises `DemoRecordingError`, not `ValueError`, so
        this escaped naming neither the scenario nor the directory."""
        write_run(BASE, tmp_path)
        (tmp_path / "rv" / CHECKS_FILENAME).write_text('{"nodes": []}')
        with pytest.raises(
            DemoRecordingError, match=r"of 'rv' in .* not read"
        ):
            read_runs(tmp_path)

    def test_a_directory_holding_neither_trace_is_skipped(self, tmp_path):
        """A cache directory or a nested CI artifact is not a scenario, and
        must not take the whole comparison down naming itself as one."""
        write_run(BASE, tmp_path)
        (tmp_path / ".cache").mkdir()
        (tmp_path / ".cache" / "something").write_text("x")
        assert sorted(read_runs(tmp_path)) == ["rv"]

    def test_pruning_drops_the_runs_not_kept(self, tmp_path):
        write_run(BASE, tmp_path)
        write_run(replace(BASE, scenario="rvv"), tmp_path)
        (tmp_path / ".cache").mkdir()

        assert prune_runs(tmp_path, keep={"rv"}) == ["rvv"]

        assert sorted(read_runs(tmp_path)) == ["rv"]
        assert (tmp_path / ".cache").is_dir(), "pruning touched a non-run"

    def test_pruning_a_directory_that_does_not_exist_removes_nothing(
        self, tmp_path
    ):
        assert prune_runs(tmp_path / "missing", keep=set()) == []

    def test_a_path_that_is_not_a_directory_is_refused(self, tmp_path):
        with pytest.raises(DemoRecordingError, match="not a directory"):
            read_runs(tmp_path / "missing")
