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

"""The ``vultron-case-history`` command (CEH-01-004, CEH-01-005, CEH-01-008, CEH-06-004)."""

import json
import subprocess
import sys
from importlib.metadata import entry_points
from pathlib import Path

import pytest

from vultron.demo.recordings.layout import recording_path
from vultron.measure.history.cli import EXIT_BAD_INPUT, main
from vultron.measure.history.render import TABLE_HEADERS

SCRIPT = "vultron-case-history"
RECORDING = recording_path("rv")


def _case_id(path: Path) -> str:
    first = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    return str(first["caseId"])


@pytest.mark.spec("CEH-01-004")
def test_the_console_script_is_registered_to_main():
    matches = [
        e for e in entry_points(group="console_scripts") if e.name == SCRIPT
    ]
    assert matches, f"{SCRIPT} is not in [project.scripts]"
    assert matches[0].value == "vultron.measure.history.cli:main"
    assert matches[0].load() is main


@pytest.mark.spec("CEH-01-004")
@pytest.mark.spec("CEH-01-005")
def test_the_table_format_writes_a_markdown_table(tmp_path):
    output = tmp_path / "history.md"
    assert main([str(RECORDING), "--format", "table", "-o", str(output)]) == 0
    lines = output.read_text(encoding="utf-8").splitlines()
    header = "| " + " | ".join(TABLE_HEADERS) + " |"
    at = lines.index(header)
    assert (
        lines[at + 1] == "| " + " | ".join(["---"] * len(TABLE_HEADERS)) + " |"
    )
    rows = [line for line in lines[at + 2 :] if line.startswith("| ")]
    assert rows
    assert all(row.count(" | ") == len(TABLE_HEADERS) - 1 for row in rows)


@pytest.mark.spec("CEH-01-005")
def test_the_json_format_writes_parsable_json(tmp_path):
    output = tmp_path / "history.json"
    case_id = _case_id(RECORDING)
    rc = main(
        [
            str(RECORDING),
            "--format",
            "json",
            "--case",
            case_id,
            "-o",
            str(output),
        ]
    )
    assert rc == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    assert list(data["histories"]) == [case_id]
    assert data["histories"][case_id]["events"]


def test_without_an_output_file_the_history_goes_to_stdout(capsys):
    assert main([str(RECORDING), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["histories"]


@pytest.mark.spec("CEH-01-008")
def test_a_missing_input_exits_non_zero(tmp_path):
    assert main([str(tmp_path / "missing.jsonl")]) == EXIT_BAD_INPUT != 0


@pytest.mark.spec("CEH-01-008")
@pytest.mark.parametrize("content", ["", "{not json\n[1, 2]\n"])
def test_an_input_with_no_ledger_entry_exits_non_zero(tmp_path, content):
    path = tmp_path / "empty.jsonl"
    path.write_text(content, encoding="utf-8")
    assert main([str(path)]) == EXIT_BAD_INPUT


@pytest.mark.spec("CEH-01-008")
def test_a_case_the_input_does_not_hold_exits_non_zero(tmp_path):
    output = tmp_path / "history.md"
    rc = main(
        [str(RECORDING), "--case", "urn:uuid:no-such-case", "-o", str(output)]
    )
    assert rc == EXIT_BAD_INPUT
    assert not output.exists()


def test_an_unwritable_output_exits_non_zero(tmp_path):
    output = tmp_path / "no-such-dir" / "history.md"
    assert main([str(RECORDING), "-o", str(output)]) == EXIT_BAD_INPUT


@pytest.mark.spec("CEH-06-004")
def test_the_registered_script_dumps_a_committed_recording(tmp_path):
    script = Path(sys.executable).with_name(SCRIPT)
    assert script.exists(), (
        f"{SCRIPT} is not installed beside {sys.executable}"
    )
    output = tmp_path / "history.md"
    done = subprocess.run(
        [str(script), str(RECORDING), "-o", str(output)],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr
    assert output.read_text(encoding="utf-8").startswith(
        "# Case event history"
    )


def test_a_failed_write_keeps_the_old_output_and_leaves_no_partial_file(
    tmp_path, monkeypatch
):
    output = tmp_path / "history.md"
    output.write_text("old dump", encoding="utf-8")
    real_write_text = Path.write_text

    def fail_partway(self, data, *args, **kwargs):
        real_write_text(self, data[:10], *args, **kwargs)
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", fail_partway)
    assert main([str(RECORDING), "-o", str(output)]) == EXIT_BAD_INPUT
    assert list(tmp_path.iterdir()) == [output]
    assert output.read_text(encoding="utf-8") == "old dump"


def test_a_failed_move_leaves_no_partial_file(tmp_path, monkeypatch):
    output = tmp_path / "history.md"

    def fail(self, *args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "replace", fail)
    assert main([str(RECORDING), "-o", str(output)]) == EXIT_BAD_INPUT
    assert list(tmp_path.iterdir()) == []


def test_another_runs_partial_file_is_left_alone(tmp_path):
    output = tmp_path / "history.md"
    other = tmp_path / ".history.md.partial"
    other.write_text("another run", encoding="utf-8")
    assert main([str(RECORDING), "-o", str(output)]) == 0
    assert other.read_text(encoding="utf-8") == "another run"
    assert sorted(tmp_path.iterdir()) == sorted([output, other])


def test_a_symlinked_output_is_written_through(tmp_path):
    target = tmp_path / "target.md"
    target.write_text("old dump", encoding="utf-8")
    link = tmp_path / "history.md"
    try:
        link.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"the filesystem refuses a symlink: {exc}")
    assert main([str(RECORDING), "-o", str(link)]) == 0
    assert link.is_symlink()
    assert target.read_text(encoding="utf-8").startswith(
        "# Case event history"
    )


def test_a_failed_write_to_stdout_names_standard_output(monkeypatch, caplog):
    def fail(_text):
        raise OSError("broken pipe")

    monkeypatch.setattr("sys.stdout.write", fail)
    with caplog.at_level("ERROR"):
        assert main([str(RECORDING)]) == EXIT_BAD_INPUT
    assert "cannot write standard output: broken pipe" in caplog.text
