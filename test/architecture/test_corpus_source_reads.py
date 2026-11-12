#!/usr/bin/env python

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
"""The corpus's import-time reads skip a file they cannot decode.

Every cache in ``_corpus`` fills at import time, so an exception escaping one
read would fail every architecture ratchet at collection.  A non-UTF-8 file
raises ``UnicodeDecodeError``, which is not an ``OSError``, so the read must
catch both.

Spec: TB-13-001 (``specs/testability.yaml``).
"""

import ast
from pathlib import Path

import pytest

from test.architecture import _corpus


@pytest.mark.parametrize("name", ["module.py", "page.md", "spec.yaml"])
def test_a_non_utf8_file_is_skipped_not_raised(
    tmp_path: Path, name: str
) -> None:
    """A file that is not UTF-8 is left out of the cache, and nothing raises."""
    bad = tmp_path / name
    bad.write_bytes(b"x = '\xff\xfe'\n")
    cache: dict[Path, str] = {}
    _corpus._read_into(cache, bad)
    assert cache == {}


def test_a_missing_file_is_skipped_not_raised(tmp_path: Path) -> None:
    """A file that vanished between listing and reading is left out."""
    cache: dict[Path, str] = {}
    _corpus._read_into(cache, tmp_path / "gone.py")
    assert cache == {}


def test_a_readable_file_is_cached(tmp_path: Path) -> None:
    """The counter-case: a UTF-8 file is cached with its text unchanged.

    Without it, the two skip tests above would pass against a read that
    cached nothing at all.
    """
    good = tmp_path / "module.py"
    good.write_text("value = 'é'\n", encoding="utf-8")
    cache: dict[Path, str] = {}
    _corpus._read_into(cache, good)
    assert cache == {good: "value = 'é'\n"}


def test_every_corpus_read_goes_through_the_shared_helper() -> None:
    """``_corpus`` reads file text only inside ``_read_into``.

    The tests above pin the helper; this pins that the import-time loops use
    it, so a loop that went back to its own ``try``/``except OSError`` would
    fail here rather than at the next non-UTF-8 file.
    """
    tree = ast.parse(Path(_corpus.__file__).read_text(encoding="utf-8"))
    helper = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_read_into"
    )
    inside = {id(node) for node in ast.walk(helper)}
    stray = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and _corpus.callee_name(node.func) == "read_text"
        and id(node) not in inside
    ]
    assert stray == [], f"read_text outside _read_into at lines {stray}"
