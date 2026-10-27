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
"""Tests for :func:`vultron.metadata.base.iter_tree_texts` and the
``mkdocs.yml`` readers."""

from __future__ import annotations

import pytest

from vultron.metadata.base import (
    iter_tree_texts,
    mkdocs_config,
    parse_mkdocs_config,
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
