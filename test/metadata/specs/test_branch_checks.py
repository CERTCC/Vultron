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
"""Tests for ``spec-lint --changed-since`` (:mod:`...specs.branch_checks`).

Each test builds a throwaway git repository whose ``base`` branch is the merge
base, then edits the working tree, which is the head side.

Specs: MS-10-011, PD-10-003, PAD-20-003.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

from test.metadata._git_repo import commit_base, git
from test.metadata.specs.conftest import spec_file_data
from vultron.metadata.specs import lint as lint_module
from vultron.metadata.specs.branch_checks import (
    changed_since,
    check_added_yaml_lines,
    check_branch,
)
from vultron.metadata.specs.growth_guard import BaseUnavailableError
from vultron.metadata.specs.registry import load_registry

_UNMARKED = "`test/test_unmarked.py` checks it."
_LONG = "statement words " * 8


def _write_specs(root: Path, rows: list[tuple]) -> None:
    (root / "specs").mkdir(exist_ok=True)
    text = yaml.dump(spec_file_data(rows), width=1000)
    (root / "specs" / "specs.yaml").write_text(text, encoding="utf-8")


def _row(spec_id: str, verification: str, kind: str = "protocol") -> tuple:
    return (spec_id, "MUST", kind, {"verification": verification})


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository whose ``base`` branch holds two unmarked specs."""
    (tmp_path / "test").mkdir()
    (tmp_path / "test" / "test_unmarked.py").write_text(
        "def test_it():\n    pass\n", encoding="utf-8"
    )
    _write_specs(
        tmp_path,
        [_row("TST-01-001", _UNMARKED), _row("TST-01-002", _UNMARKED)],
    )
    commit_base(tmp_path)
    git(tmp_path, "checkout", "-q", "-b", "work")
    return tmp_path


def _errors(root: Path) -> list[str]:
    return check_branch(load_registry(root / "specs"), root, "base")


@pytest.mark.spec("MS-10-011")
class TestChangedMarkers:
    def test_an_untouched_requirement_is_not_reported(self, repo):
        assert _errors(repo) == []

    def test_a_changed_requirement_is_reported(self, repo):
        _write_specs(
            repo,
            [
                _row("TST-01-001", _UNMARKED + " Reworded."),
                _row("TST-01-002", _UNMARKED),
            ],
        )
        (error,) = _errors(repo)
        assert error.startswith("TST-01-001: no test file")
        assert changed_since(repo, "base") == {"TST-01-001"}

    def test_a_new_requirement_is_reported(self, repo):
        _write_specs(
            repo,
            [
                _row("TST-01-001", _UNMARKED),
                _row("TST-01-002", _UNMARKED),
                _row("TST-01-003", _UNMARKED),
            ],
        )
        (error,) = _errors(repo)
        assert error.startswith("TST-01-003:")

    def test_marking_the_named_test_clears_it(self, repo):
        (repo / "test" / "test_unmarked.py").write_text(
            "import pytest\n\n\n"
            '@pytest.mark.spec("TST-01-001")\n'
            "def test_it():\n    pass\n",
            encoding="utf-8",
        )
        _write_specs(
            repo,
            [
                _row("TST-01-001", _UNMARKED + " Reworded."),
                _row("TST-01-002", _UNMARKED),
            ],
        )
        assert _errors(repo) == []

    def test_a_changed_requirement_of_another_kind_is_not_reported(self, repo):
        _write_specs(
            repo,
            [
                _row("TST-01-001", _UNMARKED + " Reworded.", "project"),
                _row("TST-01-002", _UNMARKED),
            ],
        )
        assert _errors(repo) == []


@pytest.mark.spec("PD-10-003")
class TestAddedYamlLines:
    def test_an_added_long_line_is_reported(self, repo):
        _write_specs(
            repo,
            [
                _row("TST-01-001", _UNMARKED + " " + _LONG),
                _row("TST-01-002", _UNMARKED),
            ],
        )
        (error,) = check_added_yaml_lines(repo, "base")
        assert error.startswith("PD-10-002: line over 88 characters added")
        assert "specs/specs.yaml: verification:" in error

    def test_a_long_line_already_on_the_base_is_not_reported(self, tmp_path):
        (tmp_path / "specs").mkdir()
        long_line = "description: " + _LONG
        (tmp_path / "specs" / "a.yaml").write_text(f"{long_line}\n")
        commit_base(tmp_path)
        (tmp_path / "specs" / "a.yaml").write_text(f"id: X\n{long_line}\n")
        assert check_added_yaml_lines(tmp_path, "base") == []


@pytest.mark.spec("PAD-20-003")
class TestCli:
    def _run(self, monkeypatch, root: Path, *args: str) -> int:
        monkeypatch.chdir(root)
        monkeypatch.setattr(
            sys, "argv", ["spec-lint", "specs", "--changed-since", *args]
        )
        with pytest.raises(SystemExit) as exc:
            lint_module.main()
        assert isinstance(exc.value.code, int)
        return exc.value.code

    def test_an_unresolvable_base_exits_2(self, repo, monkeypatch, capsys):
        assert self._run(monkeypatch, repo, "no-such-ref") == 2
        assert "--changed-since" in capsys.readouterr().err

    def test_the_branch_errors_fail_the_lint(self, repo, monkeypatch, capsys):
        _write_specs(
            repo,
            [
                _row("TST-01-001", _UNMARKED + " Reworded."),
                _row("TST-01-002", _UNMARKED),
            ],
        )
        assert self._run(monkeypatch, repo, "base") == 1
        assert "TST-01-001: no test file" in capsys.readouterr().err

    def test_check_branch_raises_without_a_base(self, repo):
        with pytest.raises(BaseUnavailableError):
            check_branch(load_registry(repo / "specs"), repo, "no-such-ref")
