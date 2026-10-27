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
"""Tests for the MS-03 statement checks (:mod:`...specs.statement_style`).

The branch tests build a throwaway git repository whose ``base`` branch is the
merge base, then edit the working tree, which is the head side.

Specs: MS-03-001, MS-03-003, MS-03-007.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

from test.metadata._git_repo import commit_base, git
from test.metadata.specs.conftest import spec_file_data
from vultron.metadata.specs import lint as lint_module
from vultron.metadata.specs.branch_checks import BranchReport, check_branch
from vultron.metadata.specs.registry import load_registry
from vultron.metadata.specs.statement_style import (
    SENTENCE_WORD_LIMIT,
    compound_listing,
    is_compound,
    long_sentences,
    unexcused_compound_statements,
)

_ONE = "The CASE_MANAGER MUST send the case."
_TWO = "The CASE_MANAGER MUST send the case and MUST log it."
_QUOTED = "The CASE_MANAGER MUST send the case, as `SHOULD` names no rule."
_REASON = "# both keywords state one choice"


def _words(n: int) -> str:
    return "The CASE_MANAGER MUST " + " ".join(["send"] * (n - 3)) + "."


class TestIsCompound:
    def test_one_keyword_is_not_compound(self):
        assert not is_compound(_ONE)

    def test_two_keywords_are_compound(self):
        assert is_compound(_TWO)

    def test_a_negated_keyword_counts_once(self):
        assert not is_compound("A participant MUST NOT send it.")

    def test_a_keyword_in_backticks_is_a_quoted_name(self):
        assert not is_compound(_QUOTED)

    def test_a_lower_case_keyword_is_not_one(self):
        assert not is_compound("It MUST send what it may.")


class TestLongSentences:
    def test_a_sentence_at_the_limit_passes(self):
        assert long_sentences(_words(SENTENCE_WORD_LIMIT)) == []

    def test_a_sentence_over_the_limit_is_found(self):
        (found,) = long_sentences(_words(SENTENCE_WORD_LIMIT + 1))
        assert (found.number, found.words) == (1, SENTENCE_WORD_LIMIT + 1)
        assert found.opening.startswith("The CASE_MANAGER MUST")

    def test_each_sentence_is_counted_on_its_own(self):
        text = _words(20) + " " + _words(20)
        assert long_sentences(text) == []

    def test_the_second_sentence_is_numbered(self):
        text = _ONE + " " + _words(30)
        (found,) = long_sentences(text)
        assert found.number == 2

    def test_a_code_span_is_one_word_and_its_dots_end_nothing(self):
        span = "`spec-lint --changed-since origin/main. Then more words here`"
        text = f"The tool {span} " + " ".join(["runs"] * 23) + "."
        (found,) = long_sentences(text)
        assert found.words == 2 + 1 + 23

    @pytest.mark.parametrize("abbreviation", ["e.g.", "i.e.", "U.S.", "etc."])
    def test_an_abbreviation_ends_no_sentence(self, abbreviation):
        half = " ".join(["send"] * 12)
        text = f"It MUST {half}, {abbreviation} Then {half}."
        (found,) = long_sentences(text)
        assert found.words == 2 + 12 + 1 + 1 + 12

    def test_punctuation_alone_is_not_a_word(self):
        text = _words(SENTENCE_WORD_LIMIT - 1)[:-1] + " — end."
        assert long_sentences(text) == []


def _write_specs(root: Path, rows: list[tuple], reason: bool = True) -> None:
    """Write *rows*; each ``compound_statement`` entry gets a reason comment.

    ``yaml.dump`` writes no comments, so the reason is added to the text.
    """
    (root / "specs").mkdir(exist_ok=True)
    text = yaml.dump(spec_file_data(rows))
    if reason:
        text = text.replace(
            "- compound_statement\n", f"- compound_statement  {_REASON}\n"
        )
    (root / "specs" / "specs.yaml").write_text(text, encoding="utf-8")


def _row(spec_id: str, statement: str, **extra: object) -> tuple:
    return (spec_id, "SHOULD", "process", {"statement": statement, **extra})


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository whose ``base`` branch holds one plain, one compound spec."""
    _write_specs(
        tmp_path, [_row("TST-01-001", _ONE), _row("TST-01-002", _TWO)]
    )
    commit_base(tmp_path)
    git(tmp_path, "checkout", "-q", "-b", "work")
    return tmp_path


def _report(root: Path) -> BranchReport:
    return check_branch(load_registry(root / "specs"), root, "base")


@pytest.mark.spec("MS-03-007")
class TestChangedStatements:
    def test_a_reworded_compound_statement_fails(self, repo):
        _write_specs(
            repo,
            [_row("TST-01-001", _TWO), _row("TST-01-002", _TWO)],
        )
        (error,) = _report(repo).errors
        assert error.startswith("TST-01-001: statement holds more than one")
        assert "MUST, MUST" in error

    def test_a_new_compound_statement_fails(self, repo):
        _write_specs(
            repo,
            [
                _row("TST-01-001", _ONE),
                _row("TST-01-002", _TWO),
                _row("TST-01-003", _TWO),
            ],
        )
        (error,) = _report(repo).errors
        assert error.startswith("TST-01-003:")

    def test_a_keyword_in_backticks_passes(self, repo):
        _write_specs(
            repo,
            [_row("TST-01-001", _QUOTED), _row("TST-01-002", _TWO)],
        )
        assert _report(repo).errors == []

    def test_a_suppression_with_a_reason_passes(self, repo):
        _write_specs(
            repo,
            [
                _row("TST-01-001", _TWO, lint_suppress=["compound_statement"]),
                _row("TST-01-002", _TWO),
            ],
        )
        assert _report(repo).errors == []

    def test_a_suppression_without_a_reason_fails(self, repo):
        _write_specs(
            repo,
            [
                _row("TST-01-001", _TWO, lint_suppress=["compound_statement"]),
                _row("TST-01-002", _TWO),
            ],
            reason=False,
        )
        (error,) = _report(repo).errors
        assert "gives no reason" in error

    def test_an_unchanged_compound_statement_passes(self, repo):
        assert _report(repo) == BranchReport([], [])

    @pytest.mark.parametrize(
        "extra",
        [
            {"rationale": "It keeps the case in one place."},
            {
                "relationships": [
                    {"rel_type": "refines", "spec_id": "TST-01-001"}
                ]
            },
        ],
        ids=["rationale", "relationships"],
    )
    def test_a_change_outside_the_statement_passes(self, repo, extra):
        _write_specs(
            repo,
            [_row("TST-01-001", _ONE), _row("TST-01-002", _TWO, **extra)],
        )
        assert _report(repo).errors == []


@pytest.mark.spec("MS-03-003")
class TestLongSentenceWarning:
    def test_a_changed_long_sentence_warns(self, repo):
        long = _words(SENTENCE_WORD_LIMIT + 1)
        _write_specs(
            repo,
            [_row("TST-01-001", long), _row("TST-01-002", _TWO)],
        )
        report = _report(repo)
        assert report.errors == []
        (warning,) = report.warnings
        assert warning.startswith("[WARN] TST-01-001: statement sentence 1")
        assert "26 words" in warning

    def test_the_cli_exits_0_on_a_warning(self, repo, monkeypatch, capsys):
        long = _words(SENTENCE_WORD_LIMIT + 1)
        _write_specs(
            repo,
            [_row("TST-01-001", long), _row("TST-01-002", _TWO)],
        )
        assert _run(monkeypatch, repo, "--changed-since", "base") == 0
        assert "[WARN] TST-01-001: statement sentence 1" in (
            capsys.readouterr().out
        )

    def test_the_cli_exits_1_on_a_compound(self, repo, monkeypatch, capsys):
        _write_specs(
            repo,
            [_row("TST-01-001", _TWO), _row("TST-01-002", _TWO)],
        )
        assert _run(monkeypatch, repo, "--changed-since", "base") == 1
        assert "TST-01-001: statement holds" in capsys.readouterr().err


def _run(monkeypatch, root: Path, *args: str) -> int:
    monkeypatch.chdir(root)
    monkeypatch.setattr(sys, "argv", ["spec-lint", "specs", *args])
    with pytest.raises(SystemExit) as exc:
        lint_module.main()
    assert isinstance(exc.value.code, int)
    return exc.value.code


@pytest.mark.spec("MS-03-001")
class TestListCompound:
    def test_lists_compound_requirements_by_file(self, tmp_path):
        _write_specs(
            tmp_path,
            [
                _row("TST-01-001", _ONE),
                _row("TST-01-002", _TWO),
                _row("TST-01-003", _TWO, lint_suppress=["compound_statement"]),
            ],
        )
        lines = compound_listing(
            load_registry(tmp_path / "specs"), tmp_path / "specs"
        )
        assert lines == [
            "specs.yaml (1)",
            "  TST-01-002  2 keywords",
            "1 compound requirement(s) in 1 spec file(s) (MS-03-001)",
        ]

    def test_a_suppression_without_a_reason_is_still_listed(self, tmp_path):
        _write_specs(
            tmp_path,
            [_row("TST-01-001", _TWO, lint_suppress=["compound_statement"])],
            reason=False,
        )
        lines = compound_listing(
            load_registry(tmp_path / "specs"), tmp_path / "specs"
        )
        assert "  TST-01-001  2 keywords" in lines

    @pytest.mark.parametrize(
        "other",
        [
            ("--changed-since", "base"),
            ("--check-closing-pr", "1"),
            ("--check-debt-owners",),
            ("--list-unverified",),
        ],
    )
    def test_the_cli_refuses_another_check_beside_it(
        self, tmp_path, monkeypatch, capsys, other
    ):
        _write_specs(tmp_path, [_row("TST-01-001", _TWO)])
        assert _run(monkeypatch, tmp_path, "--list-compound", *other) == 2
        assert "--list-compound runs alone" in capsys.readouterr().err

    def test_the_cli_exits_0(self, tmp_path, monkeypatch, capsys):
        _write_specs(tmp_path, [_row("TST-01-001", _TWO)])
        assert _run(monkeypatch, tmp_path, "--list-compound") == 0
        assert "  TST-01-001  2 keywords" in capsys.readouterr().out


@pytest.mark.spec("MS-03-007")
class TestGuardItems:
    """The items the PR-only growth guard compares across the merge base."""

    def test_a_reworded_compound_statement_is_a_new_item(self, tmp_path):
        _write_specs(tmp_path, [_row("TST-01-001", _TWO)])
        before = unexcused_compound_statements(tmp_path)
        _write_specs(tmp_path, [_row("TST-01-001", _TWO + " Then stop.")])
        assert unexcused_compound_statements(tmp_path) - before

    def test_a_change_outside_the_statement_keeps_the_item(self, tmp_path):
        _write_specs(tmp_path, [_row("TST-01-001", _TWO)])
        before = unexcused_compound_statements(tmp_path)
        _write_specs(
            tmp_path, [_row("TST-01-001", _TWO, rationale="It keeps order.")]
        )
        assert unexcused_compound_statements(tmp_path) == before

    @pytest.mark.parametrize("drop", ["reason", "suppression"])
    def test_a_lost_excuse_is_a_new_item(self, tmp_path, drop):
        suppressed = _row(
            "TST-01-001", _TWO, lint_suppress=["compound_statement"]
        )
        _write_specs(tmp_path, [suppressed])
        before = unexcused_compound_statements(tmp_path)
        if drop == "reason":
            _write_specs(tmp_path, [suppressed], reason=False)
        else:
            _write_specs(tmp_path, [_row("TST-01-001", _TWO)])
        assert unexcused_compound_statements(tmp_path) - before == {
            f"TST-01-001: {_TWO}"
        }

    def test_only_unexcused_compound_statements_are_items(self, tmp_path):
        _write_specs(
            tmp_path,
            [
                _row("TST-01-001", _ONE),
                _row("TST-01-002", _QUOTED),
                _row("TST-01-003", _TWO, lint_suppress=["compound_statement"]),
                _row("TST-01-004", _TWO),
            ],
        )
        assert unexcused_compound_statements(tmp_path) == {
            f"TST-01-004: {_TWO}"
        }
