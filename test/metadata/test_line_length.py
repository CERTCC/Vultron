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

import tomllib
from pathlib import Path

import pytest
import yaml

from vultron.metadata.line_length import (
    LINE_LIMIT,
    is_overlong,
    overlong_python_doc_lines,
    overlong_spec_yaml_lines,
    python_doc_lines,
)

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
    def test_comments_and_docstrings_are_doc_lines(self):
        source = (
            '"""Module docstring\n\nsecond line.\n"""\n'
            "x = 1  # trailing comments are code lines\n"
            "# a comment line\n"
            "def f():\n"
            '    r"""One-line docstring."""\n'
            "    return 1\n"
        )
        assert list(python_doc_lines(source)) == [
            '"""Module docstring',
            "",
            "second line.",
            '"""',
            "# a comment line",
            '    r"""One-line docstring."""',
        ]

    def test_a_string_opened_mid_line_is_data(self):
        source = 'QUERY = """\nselect a long line of data\n"""\n# after\n'
        assert list(python_doc_lines(source)) == ["# after"]

    def test_the_license_header_is_skipped(self):
        source = f"#!/usr/bin/env python\n\n{_HEADER}\n# real comment\n"
        assert list(python_doc_lines(source)) == ["# real comment"]

    def test_a_leading_comment_without_the_notice_is_read(self):
        assert list(python_doc_lines("# plain\nx = 1\n")) == ["# plain"]

    def test_a_comment_right_after_the_notice_is_read(self):
        source = f"{_HEADER}# real comment\n"
        assert list(python_doc_lines(source)) == ["# real comment"]


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
            f"specs/a.yaml: {long_line} (#2)",
        }

    def test_a_moved_line_is_the_same_item(self, tmp_path):
        long_line = _words(100)
        _write(tmp_path, "specs/a.yaml", f"{long_line}\nshort\n")
        before = overlong_spec_yaml_lines(tmp_path)
        _write(tmp_path, "specs/a.yaml", f"short\nshorter\n{long_line}\n")
        assert overlong_spec_yaml_lines(tmp_path) == before

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
        found = {
            p.parent.relative_to(REPO_ROOT).as_posix()
            for p in REPO_ROOT.glob("**/.markdownlint-cli2.yaml")
            if ".venv" not in p.parts
            and "node_modules" not in p.parts
            and ".claude" not in p.parts
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
