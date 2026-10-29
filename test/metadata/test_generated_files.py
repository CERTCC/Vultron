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
"""Tests for the shared generated-file comparison (CS-22-001)."""

from vultron.metadata.generated_files import (
    read_committed,
    serialize_json,
    stale_paths,
    write_generated,
)


def test_missing_file_reads_as_none_and_is_stale(tmp_path):
    assert read_committed(tmp_path / "absent.md") is None
    assert list(stale_paths(tmp_path, {"absent.md": "x\n"})) == ["absent.md"]


def test_identical_file_is_not_stale(tmp_path):
    (tmp_path / "a.md").write_bytes(b"one\ntwo\n")
    assert list(stale_paths(tmp_path, {"a.md": "one\ntwo\n"})) == []


def test_crlf_copy_is_stale(tmp_path):
    """``read_text`` would translate CRLF and call this copy current."""
    (tmp_path / "a.md").write_bytes(b"one\r\ntwo\r\n")
    assert list(stale_paths(tmp_path, {"a.md": "one\ntwo\n"})) == ["a.md"]


def test_write_uses_lf_and_creates_parents(tmp_path):
    target = tmp_path / "deep" / "dir" / "a.md"
    write_generated(target, "one\ntwo\n")
    assert target.read_bytes() == b"one\ntwo\n"
    assert list(stale_paths(tmp_path, {"deep/dir/a.md": "one\ntwo\n"})) == []


def test_serialize_json_is_indented_keeps_non_ascii_and_ends_in_newline():
    text = serialize_json({"b": ["→"], "a": 1})
    assert text == '{\n  "b": [\n    "→"\n  ],\n  "a": 1\n}\n'
