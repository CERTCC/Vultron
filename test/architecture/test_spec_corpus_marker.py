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
"""Architecture ratchet: spec_corpus marker required on all spec-reading tests.

Any test function in test/ that reads from the actual specs/ YAML corpus
MUST carry ``@pytest.mark.spec_corpus`` so that spec-check.yml can run it
via ``pytest -m spec_corpus`` on specs/** PRs.

Detection criteria (AST-based, no raw ast.parse calls — TB-13-003):
- Function has ``real_registry`` as a parameter (the session-scoped fixture
  that loads ``load_registry(actual_specs_dir)``), OR
- Function body references ``_SPEC_DIR`` or ``_SPECS_DIR`` by name (module-level
  constants that resolve to the repo's real specs/ directory).

Without this marker, a specs-only PR that adds uncovered ``kind: protocol``
specs goes green on that PR and surfaces as a red ratchet on the next
unrelated PR (Bug #2903).

conftest.py files are excluded — they define fixtures, not test functions.
"""

import ast

from test.architecture import _corpus

_TEST_ROOT = _corpus.REPO_ROOT / "test"

# Prefilter fragments for _corpus.files_mentioning; broad enough to include
# all candidate files.  False positives (e.g. _DOCS_SPECS_DIR) are resolved
# precisely at the AST-node level in _func_reads_spec_corpus.
_PREFILTER_FRAGMENTS = ("real_registry", "_SPEC_DIR", "_SPECS_DIR")

# The exact ast.Name ids that identify a real-specs-corpus reference.
_SPEC_NAME_IDS: frozenset[str] = frozenset({"_SPEC_DIR", "_SPECS_DIR"})

_MARKER_NAME = "spec_corpus"


def _func_reads_spec_corpus(func: ast.FunctionDef) -> bool:
    """Return True when *func* reads from the actual specs/ corpus.

    Checks via AST nodes only — no source text scanning — so that
    ``_DOCS_SPECS_DIR`` (which contains ``_SPECS_DIR`` as a substring) does
    not produce a false positive.
    """
    # real_registry as a parameter
    param_names = {arg.arg for arg in func.args.args}
    if "real_registry" in param_names:
        return True
    # _SPEC_DIR or _SPECS_DIR referenced in the function body
    for node in ast.walk(func):
        if isinstance(node, ast.Name) and node.id in _SPEC_NAME_IDS:
            return True
    return False


def _has_spec_corpus_decorator(func: ast.FunctionDef) -> bool:
    """Return True when *func* carries @pytest.mark.spec_corpus."""
    for dec in func.decorator_list:
        if not isinstance(dec, ast.Attribute):
            continue
        if dec.attr != _MARKER_NAME:
            continue
        if not isinstance(dec.value, ast.Attribute):
            continue
        if dec.value.attr != "mark":
            continue
        if not isinstance(dec.value.value, ast.Name):
            continue
        if dec.value.value.id == "pytest":
            return True
    return False


def test_spec_reading_tests_carry_spec_corpus_marker() -> None:
    """Every test function that reads from specs/ MUST have @pytest.mark.spec_corpus.

    Violation means a specs-only PR will silently skip that test, potentially
    missing a regression in the coverage ratchet or lint check (Bug #2903).
    """
    violations: list[str] = []

    for path, tree in _corpus.files_mentioning(
        *_PREFILTER_FRAGMENTS, under=_TEST_ROOT
    ):
        if path.name == "conftest.py":
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if not node.name.startswith("test_"):
                continue
            if not _func_reads_spec_corpus(node):
                continue
            if not _has_spec_corpus_decorator(node):
                rel = path.relative_to(_corpus.REPO_ROOT)
                violations.append(f"{rel}::{node.name}")

    assert not violations, (
        f"{len(violations)} test function(s) read from the specs/ corpus but "
        f"lack @pytest.mark.spec_corpus:\n"
        + "\n".join(f"  {v}" for v in sorted(violations))
        + "\n\nAdd @pytest.mark.spec_corpus to each function above so "
        "spec-check.yml runs it on specs/** PRs (Bug #2903)."
    )
