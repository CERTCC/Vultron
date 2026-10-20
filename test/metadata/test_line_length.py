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
"""Tests for :mod:`vultron.metadata.line_length` and the configs that share it.

Specs: PD-10-001, PD-10-002, PD-10-003.
"""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml

from test.metadata._git_repo import commit_all, commit_base, git
from vultron.metadata import line_length
from vultron.metadata.line_length import (
    LINE_LIMIT,
    added_overlong_lines,
    is_overlong,
    new_lines,
    overlong_python_doc_lines,
    overlong_spec_yaml_lines,
)
from vultron.metadata.specs.growth_guard import GrowthCheck, compare_with_base

REPO_ROOT = Path(__file__).parents[2]

#: Directories where the root config's MD013 is switched off again.
MD013_EXEMPT_DIRS = (
    "docs",
    "plan/history",
    "plan/retired-specs",
    "archived_notes",
)

_HEADER = (
    "#  Copyright (c) 2026 Carnegie Mellon University and Contributors.\n"
    "#  - see ContributionInstructions.md for information on how you can "
    "Contribute to this project\n"
    "#  U.S. Patent and Trademark Office by Carnegie Mellon University\n"
)


def _words(n: int) -> str:
    """A line of *n* characters made of words, so it can be wrapped."""
    text = ("word " * n)[:n]
    return text if not text.endswith(" ") else text[:-1] + "x"


#: Doc text long enough to be overlong after any prefix the tests give it.
_LONG = _words(100)

#: :data:`_HEADER` with a notice line past the limit, as the real notice has.
_LONG_HEADER = _HEADER.replace(
    "Contribute to this project", f"Contribute to this project {_words(40)}"
)


@pytest.mark.spec("PD-10-002")
class TestIsOverlong:
    def test_a_line_at_the_limit_passes(self):
        assert not is_overlong(_words(LINE_LIMIT))

    def test_a_wrappable_line_past_the_limit_is_overlong(self):
        assert is_overlong(_words(LINE_LIMIT + 10))

    def test_one_unbreakable_token_past_the_limit_passes(self):
        url = "https://example.org/" + "a" * 120
        assert not is_overlong(f"    see {url}")

    def test_whitespace_after_the_unbreakable_overflow_is_overlong(self):
        url = "https://example.org/" + "a" * 120
        assert is_overlong(f"see {url} and more")

    def test_the_newline_is_not_counted(self):
        assert not is_overlong(_words(LINE_LIMIT) + "\n")


@pytest.mark.spec("PD-10-002")
class TestPythonDocLines:
    """Which lines of a module are doc lines, as ruff's ``W505`` reads them."""

    @staticmethod
    def _doc_lines(tmp_path: Path, source: str) -> set[str]:
        _write(tmp_path, "vultron/m.py", source)
        return {
            item.removeprefix("vultron/m.py: ")
            for item in overlong_python_doc_lines(tmp_path)
        }

    def test_comments_and_docstrings_are_doc_lines(self, tmp_path):
        source = (
            f'"""{_LONG}\n\n{_LONG}.\n"""\n'
            f"x = 1  # trailing comments are code lines {_LONG}\n"
            f"# {_LONG}\n"
            "def f():\n"
            f'    r"""{_LONG}"""\n'
            "    return 1\n"
        )
        assert self._doc_lines(tmp_path, source) == {
            f'"""{_LONG}',
            f"{_LONG}.",
            f"# {_LONG}",
            f'r"""{_LONG}"""',
        }

    def test_a_string_opened_mid_line_is_data(self, tmp_path):
        source = f'QUERY = """\n{_LONG}\n"""\n'
        assert self._doc_lines(tmp_path, source) == set()

    def test_a_string_passed_as_an_argument_is_data(self, tmp_path):
        source = f'node(\n    """{_LONG}""",\n)\n'
        assert self._doc_lines(tmp_path, source) == set()

    def test_a_string_in_a_larger_expression_is_data(self, tmp_path):
        assert self._doc_lines(tmp_path, f'"""{_LONG}""" + b\n') == set()

    def test_an_implicitly_joined_string_statement_is_a_doc(self, tmp_path):
        source = f'def f():\n    """One."""  """{_LONG}"""\n'
        assert self._doc_lines(tmp_path, source) == {
            f'"""One."""  """{_LONG}"""'
        }

    def test_source_that_does_not_parse_raises(self, tmp_path):
        with pytest.raises(SyntaxError, match=r"vultron/m\.py:1"):
            self._doc_lines(tmp_path, f'x = """never closed {_LONG}\n')

    def test_the_license_header_is_skipped(self, tmp_path):
        source = f"#!/usr/bin/env python\n\n{_LONG_HEADER}\n# {_LONG}\n"
        assert self._doc_lines(tmp_path, source) == {f"# {_LONG}"}

    def test_a_leading_comment_without_the_notice_is_read(self, tmp_path):
        assert self._doc_lines(tmp_path, f"# {_LONG}\nx = 1\n") == {
            f"# {_LONG}"
        }

    def test_a_comment_right_after_the_notice_is_read(self, tmp_path):
        source = f"{_LONG_HEADER}# {_LONG}\n"
        assert self._doc_lines(tmp_path, source) == {f"# {_LONG}"}

    def test_an_unbreakable_overflow_is_not_overlong(self, tmp_path):
        url = "https://example.org/" + "a" * 120
        assert self._doc_lines(tmp_path, f"# see {url}\n") == set()

    def test_a_noqa_comment_does_not_exempt_a_line(self, tmp_path):
        line = f"# {_LONG}  # noqa: W505"
        assert self._doc_lines(tmp_path, f"{line}\n") == {line}

    @pytest.mark.parametrize("pragma", ["# noqa: E501", "# type: ignore"])
    def test_an_early_pragma_does_not_shorten_a_comment(
        self, tmp_path, pragma
    ):
        """``W505`` measures a comment only up to its pragma; the guard does not."""
        line = f"# short  {pragma} {_LONG}"
        assert self._doc_lines(tmp_path, f"{line}\n") == {line}

    def test_a_pragma_lookalike_in_a_data_string_is_data(self, tmp_path):
        source = f'QUERY = """\n# short  # noqa: E501 {_LONG}\n"""\n'
        assert self._doc_lines(tmp_path, source) == set()

    def test_stub_and_notebook_files_are_not_read(self, tmp_path):
        _write(tmp_path, "vultron/m.pyi", f"# {_LONG}\n")
        _write(tmp_path, "vultron/n.ipynb", '{"cells": [], "metadata": {}}\n')
        assert overlong_python_doc_lines(tmp_path) == frozenset()

    def test_a_directory_ruff_excludes_by_default_is_read(self, tmp_path):
        _write(tmp_path, "vultron/dist/m.py", f"# {_LONG}\n")
        assert overlong_python_doc_lines(tmp_path) == {
            f"vultron/dist/m.py: # {_LONG}"
        }

    def test_a_tree_without_the_roots_has_no_doc_lines(self, tmp_path):
        assert overlong_python_doc_lines(tmp_path) == frozenset()

    def test_a_failing_ruff_raises(self, tmp_path, monkeypatch):
        """A guard that cannot run ruff must not read as a pass."""
        _write(tmp_path, "vultron/m.py", f"# {_LONG}\n")
        failed = subprocess.CompletedProcess([], 2, stdout="", stderr="boom")
        monkeypatch.setattr(
            line_length.subprocess, "run", lambda *a, **k: failed
        )
        with pytest.raises(RuntimeError, match="boom"):
            overlong_python_doc_lines(tmp_path)

    def test_the_tree_ruff_config_does_not_change_the_limit(self, tmp_path):
        _write(
            tmp_path,
            "pyproject.toml",
            "[tool.ruff.lint.pycodestyle]\nmax-doc-length = 200\n",
        )
        assert self._doc_lines(tmp_path, f"# {_LONG}\n") == {f"# {_LONG}"}

    def test_a_dot_directory_root_is_read(self, tmp_path):
        _write(tmp_path, ".agents/skills/x/s.py", f"# {_LONG}\n")
        assert overlong_python_doc_lines(tmp_path) == {
            f".agents/skills/x/s.py: # {_LONG}"
        }


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.mark.spec("PD-10-002")
class TestExtractors:
    def test_spec_yaml_items_name_file_and_text(self, tmp_path):
        long_line = "  statement: " + _words(100)
        _write(tmp_path, "specs/a.yaml", f"id: A\n{long_line}\n")
        assert overlong_spec_yaml_lines(tmp_path) == {
            f"specs/a.yaml: {long_line.strip()}"
        }

    def test_a_repeated_line_is_one_item_per_occurrence(self, tmp_path):
        long_line = _words(100)
        _write(tmp_path, "specs/a.yaml", f"{long_line}\n{long_line}\n")
        assert overlong_spec_yaml_lines(tmp_path) == {
            f"specs/a.yaml: {long_line}",
            f"specs/a.yaml (#2): {long_line}",
        }

    def test_a_moved_line_is_the_same_item(self, tmp_path):
        long_line = _words(100)
        _write(tmp_path, "specs/a.yaml", f"{long_line}\nshort\n")
        before = overlong_spec_yaml_lines(tmp_path)
        _write(tmp_path, "specs/a.yaml", f"short\nshorter\n{long_line}\n")
        assert overlong_spec_yaml_lines(tmp_path) == before

    def test_a_line_moved_to_another_file_is_not_new(self):
        line = _words(100)
        base = frozenset({f"specs/a.yaml: {line}"})
        assert new_lines(base, frozenset({f"specs/b.yaml: {line}"})) == set()

    def test_a_copy_of_a_line_is_new(self):
        line = _words(100)
        base = frozenset({f"specs/a.yaml: {line}"})
        head = base | {f"specs/b.yaml: {line}"}
        assert new_lines(base, head) == {f"specs/b.yaml: {line}"}

    def test_python_items_cover_doc_lines_only(self, tmp_path):
        long_doc = "# " + _words(100)
        long_code = "x = '" + _words(100) + "'"
        _write(tmp_path, "vultron/m.py", f"{_HEADER}{long_doc}\n{long_code}\n")
        assert overlong_python_doc_lines(tmp_path) == {
            f"vultron/m.py: {long_doc}"
        }

    def test_python_files_outside_the_roots_are_not_read(self, tmp_path):
        _write(tmp_path, "docs/_scripts/m.py", "# " + _words(100) + "\n")
        assert overlong_python_doc_lines(tmp_path) == frozenset()


def _markdownlint_config(rel_dir: str = "") -> dict:
    path = REPO_ROOT / rel_dir / ".markdownlint-cli2.yaml"
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


@pytest.mark.spec("PD-10-001")
class TestMarkdownlintConfig:
    def test_root_md013_is_on_at_the_limit(self):
        md013 = _markdownlint_config()["config"]["MD013"]
        assert md013["line_length"] == LINE_LIMIT

    def test_root_md013_exempts_tables_and_code_blocks_only(self):
        md013 = _markdownlint_config()["config"]["MD013"]
        assert md013["tables"] is False
        assert md013["code_blocks"] is False
        assert md013.get("headings", True) is True
        assert md013.get("strict", False) is False

    @pytest.mark.parametrize("rel_dir", MD013_EXEMPT_DIRS)
    def test_exempt_directories_turn_md013_off_and_nothing_else(self, rel_dir):
        assert _markdownlint_config(rel_dir) == {"config": {"MD013": False}}

    def test_no_other_directory_overrides_the_root_config(self):
        # Parts relative to the root: a checkout inside an agent worktree
        # (``.claude/worktrees/...``) must not exclude every file.
        found = {
            p.parent.relative_to(REPO_ROOT).as_posix()
            for p in REPO_ROOT.glob("**/.markdownlint-cli2.yaml")
            if not {".venv", "node_modules", ".claude"}
            & set(p.relative_to(REPO_ROOT).parts)
        }
        assert found == {".", *MD013_EXEMPT_DIRS}


@pytest.mark.spec("PD-10-003")
class TestLimitsAgree:
    def test_ruff_max_doc_length_is_the_limit(self):
        pyproject = tomllib.loads(
            (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        lint = pyproject["tool"]["ruff"]["lint"]
        assert lint["pycodestyle"]["max-doc-length"] == LINE_LIMIT

    def test_markdownlint_line_length_is_the_limit(self):
        md013 = _markdownlint_config()["config"]["MD013"]
        assert md013["line_length"] == LINE_LIMIT


@pytest.mark.spec("PD-10-003")
class TestAddedOverlongLines:
    def test_a_renamed_file_adds_no_line(self, tmp_path):
        long_line = _words(100)
        _write(tmp_path, "specs/a.yaml", f"{long_line}\n")
        commit_base(tmp_path)
        git(tmp_path, "checkout", "-q", "-b", "work")
        git(tmp_path, "mv", "specs/a.yaml", "specs/b.yaml")
        commit_all(tmp_path)
        check = added_overlong_lines(
            overlong_spec_yaml_lines,
            repo_root=tmp_path,
            paths=("specs",),
            base_ref="base",
            require_base=True,
        )
        assert check.added == frozenset()

    def test_an_edited_line_is_added(self, tmp_path):
        _write(tmp_path, "specs/a.yaml", f"{_words(100)}\n")
        commit_base(tmp_path)
        _write(tmp_path, "specs/a.yaml", f"{_words(101)}\n")
        check = added_overlong_lines(
            overlong_spec_yaml_lines,
            repo_root=tmp_path,
            paths=("specs",),
            base_ref="base",
            require_base=True,
        )
        assert check.added == {f"specs/a.yaml: {_words(101)}"}

    def test_a_copy_of_an_untouched_line_into_a_new_file_is_added(
        self, tmp_path
    ):
        long_line = _words(100)
        _write(tmp_path, "specs/a.yaml", f"{long_line}\n")
        commit_base(tmp_path)
        _write(tmp_path, "specs/b.yaml", f"{long_line}\n")
        check = _added_spec_lines(tmp_path)
        assert check.added == {f"specs/b.yaml: {long_line}"}

    def test_an_untracked_python_file_is_read(self, tmp_path):
        _write(tmp_path, "vultron/a.py", "x = 1\n")
        commit_base(tmp_path)
        _write(tmp_path, "vultron/b.py", f"# {_LONG}\n")
        check = added_overlong_lines(
            overlong_python_doc_lines,
            repo_root=tmp_path,
            paths=("vultron",),
            base_ref="base",
            require_base=True,
        )
        assert check.added == {f"vultron/b.py: # {_LONG}"}
        assert check.head_total is None

    def test_a_deleted_file_adds_no_line(self, tmp_path):
        _write(tmp_path, "specs/a.yaml", f"{_words(100)}\n")
        _write(tmp_path, "specs/b.yaml", "short\n")
        commit_base(tmp_path)
        (tmp_path / "specs/a.yaml").unlink()
        assert _added_spec_lines(tmp_path).added == frozenset()

    def test_reading_changed_files_only_matches_reading_the_whole_tree(
        self, tmp_path
    ):
        """Leaving untouched files out of both sides changes no result."""
        lines = [_words(90 + n) for n in range(6)]
        _write(tmp_path, "specs/kept.yaml", f"{lines[0]}\n{lines[1]}\n")
        _write(tmp_path, "specs/edited.yaml", f"{lines[2]}\n{lines[3]}\n")
        _write(tmp_path, "specs/moved.yaml", f"{lines[4]}\n")
        _write(tmp_path, "specs/gone.yaml", f"{lines[1]}\n")
        commit_base(tmp_path)
        git(tmp_path, "checkout", "-q", "-b", "work")
        _write(tmp_path, "specs/edited.yaml", f"{lines[3]}\n{lines[5]}\n")
        git(tmp_path, "mv", "specs/moved.yaml", "specs/renamed.yaml")
        git(tmp_path, "rm", "-q", "specs/gone.yaml")
        commit_all(tmp_path)
        _write(tmp_path, "specs/new.yaml", f"{lines[0]}\n{lines[2]}\n")
        _write(tmp_path, "specs/staged.yaml", f"{lines[1]}\n")
        git(tmp_path, "add", "specs/staged.yaml")

        whole = compare_with_base(
            overlong_spec_yaml_lines,
            repo_root=tmp_path,
            paths=("specs",),
            base_ref="base",
            require_base=True,
        )
        assert whole.base_value is not None
        expected = new_lines(whole.base_value, whole.head_value)
        assert expected  # the fixture exercises an addition
        assert _added_spec_lines(tmp_path).added == expected


def _added_spec_lines(root: Path) -> GrowthCheck:
    return added_overlong_lines(
        overlong_spec_yaml_lines,
        repo_root=root,
        paths=("specs",),
        base_ref="base",
        require_base=True,
    )
