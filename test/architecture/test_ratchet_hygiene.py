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
"""Hygiene ratchet: no sibling file may call ast.parse( or use .rglob( directly.

All architecture ratchets must route AST parsing through ``_corpus.parse_inline``
and file discovery through ``_corpus.files_mentioning``, ``_corpus.all_trees``,
``_corpus.all_sources``, or ``_corpus.sources_mentioning``.

Direct ``ast.parse(`` or ``.rglob(`` calls in sibling files bypass the shared
module-level corpus, re-read source files on every test run, and risk blowing
the 5-second per-test timeout budget.

Spec: TB-13-003.
"""

from pathlib import Path

_ARCH_DIR = Path(__file__).parent

_FORBIDDEN = ("ast.parse(", ".rglob(")

_EXEMPT = {"_corpus.py"}


def test_no_raw_ast_parse_or_rglob_in_siblings():
    """No sibling file (except _corpus.py) may use ast.parse( or .rglob(.

    Spec: TB-13-003.
    """
    violations: list[str] = []
    for py_file in sorted(_ARCH_DIR.glob("*.py")):
        if py_file.name in _EXEMPT:
            continue
        if py_file.name == Path(__file__).name:
            continue
        source = py_file.read_text(encoding="utf-8")
        for fragment in _FORBIDDEN:
            if fragment in source:
                violations.append(f"{py_file.name}: contains {fragment!r}")

    assert violations == [], (
        "The following files bypass the shared corpus (TB-13-003).\n"
        "Replace ast.parse( with _corpus.parse_inline( and\n"
        ".rglob( with _corpus.files_mentioning / all_trees / all_sources:\n"
        + "\n".join(f"  {v}" for v in violations)
    )
