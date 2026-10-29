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
"""Tests for :func:`vultron.metadata.base.iter_tree_texts`,
:func:`~vultron.metadata.base.markdown_files`,
:func:`~vultron.metadata.base.relative_posix` and the ``mkdocs.yml`` readers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from vultron.metadata import base as base_module
from vultron.metadata.base import (
    GH_LOOKUP_ERRORS,
    gh_issue_missing,
    gh_issue_state,
    gh_lookup_failure,
    issue_number,
    iter_tree_texts,
    markdown_files,
    mkdocs_config,
    parse_mkdocs_config,
    relative_posix,
)
from vultron.metadata.file_loading import MetadataLoadError


def test_yields_sorted_relative_texts_under_each_directory(tmp_path):
    (tmp_path / "a" / "sub").mkdir(parents=True)
    (tmp_path / "a" / "sub" / "z.py").write_text("z")
    (tmp_path / "a" / "y.py").write_text("y")
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "x.py").write_text("x")
    (tmp_path / "b" / "x.txt").write_text("not matched")
    assert list(iter_tree_texts(tmp_path, ("a", "b"), "*.py")) == [
        ("a/sub/z.py", "z"),
        ("a/y.py", "y"),
        ("b/x.py", "x"),
    ]


def test_skips_pycache_unreadable_files_and_missing_directories(tmp_path):
    (tmp_path / "a" / "__pycache__").mkdir(parents=True)
    (tmp_path / "a" / "__pycache__" / "c.py").write_text("cached")
    (tmp_path / "a" / "bad.py").write_bytes(b"\xff\xfe")
    (tmp_path / "a" / "ok.py").write_text("ok")
    found = list(iter_tree_texts(tmp_path, ("a", "missing"), "*.py"))
    assert found == [("a/ok.py", "ok")]


def test_markdown_files_are_sorted_and_skip_pruned_directories(tmp_path):
    for rel in ("b.md", "a/z.md", "a/y.txt", "skip/x.md", "a/skip/w.md"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(rel)
    asked: list[str] = []

    def prune(directory):
        asked.append(directory.relative_to(tmp_path).as_posix())
        return directory.name == "skip"

    found = markdown_files(tmp_path, prune)

    assert found == sorted([tmp_path / "a" / "z.md", tmp_path / "b.md"])
    # A pruned directory is not descended, so nothing below it is asked about.
    assert sorted(asked) == ["a", "a/skip", "skip"]


def test_markdown_files_of_a_missing_directory_is_empty(tmp_path):
    assert markdown_files(tmp_path / "missing", lambda _d: False) == []


@pytest.mark.parametrize(
    ("path", "root"),
    [
        ("/r/a/b.py", "/r"),
        ("a/b.py", "."),
        ("a/b.py", "a"),
        ("/r", "/r"),
        (".", "."),
        ("specs/../a/b.py", "specs/.."),
    ],
)
def test_relative_posix_agrees_with_relative_to(path, root):
    expected = Path(path).relative_to(Path(root)).as_posix()

    assert relative_posix(Path(path), Path(root)) == expected


@pytest.mark.parametrize(("path", "root"), [("/s/a.py", "/r"), ("ab/c", "a")])
def test_relative_posix_refuses_a_path_outside_root(path, root):
    with pytest.raises(ValueError, match="is not in the subpath of"):
        relative_posix(Path(path), Path(root))


@pytest.mark.spec("MS-17-001")
class TestMkDocsConfigFaults:
    def test_unparsable_config_names_path_line_and_column(self, tmp_path):
        (tmp_path / "mkdocs.yml").write_text("nav:\n  - a: [b\n")

        with pytest.raises(MetadataLoadError) as info:
            mkdocs_config(tmp_path)

        assert str(info.value).startswith("mkdocs.yml:3:1 — YAML parse error")
        assert "<unicode string>" not in str(info.value)

    def test_missing_config_names_the_file(self, tmp_path):
        with pytest.raises(MetadataLoadError) as info:
            mkdocs_config(tmp_path)

        assert info.value.location == "mkdocs.yml"
        assert "does not exist" in str(info.value)

    def test_text_from_another_ref_is_attributed_to_its_name(self):
        with pytest.raises(MetadataLoadError) as info:
            parse_mkdocs_config("nav: [a\n", shown="abc123:mkdocs.yml")

        assert str(info.value).startswith("abc123:mkdocs.yml:2:1")

    def test_custom_tags_still_parse(self, tmp_path):
        (tmp_path / "mkdocs.yml").write_text(
            "x: !ENV FOO\ny: !!python/name:mod.attr\nnav: [a.md]\n"
        )

        assert mkdocs_config(tmp_path)["nav"] == ["a.md"]


# ---------------------------------------------------------------------------
# The shared single-issue gh lookup


def test_issue_number_strips_the_hash() -> None:
    assert issue_number("#4206") == 4206


def test_gh_issue_state_asks_gh_for_the_issue_number(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        assert kwargs["check"] is True
        return subprocess.CompletedProcess(
            argv, 0, stdout=json.dumps({"state": "CLOSED"}), stderr=""
        )

    monkeypatch.setattr(base_module.subprocess, "run", fake_run)
    assert gh_issue_state("#12") == "CLOSED"
    assert calls == [["gh", "issue", "view", "12", "--json", "state"]]


@pytest.mark.parametrize("stdout", ["[]", "not json", "{}"])
def test_gh_issue_state_raises_a_lookup_error_on_unexpected_output(
    monkeypatch, stdout: str
) -> None:
    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(base_module.subprocess, "run", fake_run)
    with pytest.raises(GH_LOOKUP_ERRORS):
        gh_issue_state("#12")


def test_gh_issue_missing_reads_only_gh_not_found() -> None:
    missing = subprocess.CalledProcessError(
        1,
        ["gh"],
        stderr="GraphQL: Could not resolve to an issue or pull request with"
        " the number of 9. (repository.issue)\n",
    )
    forbidden = subprocess.CalledProcessError(1, ["gh"], stderr="HTTP 403\n")
    assert gh_issue_missing(missing)
    assert not gh_issue_missing(forbidden)
    assert not gh_issue_missing(FileNotFoundError("gh"))


def test_gh_lookup_failure_adds_gh_stderr_when_present() -> None:
    exc = subprocess.CalledProcessError(1, ["gh"], stderr="HTTP 403: nope\n")
    assert gh_lookup_failure(exc).endswith(": HTTP 403: nope")
    assert gh_lookup_failure(FileNotFoundError("gh")) == "gh"
