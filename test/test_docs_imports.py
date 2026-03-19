#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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
"""Tests that docs markdown code blocks use current module import paths."""

import importlib
import re
from pathlib import Path

DOCS_DIR = Path(__file__).parent.parent / "docs"
OLD_IMPORT = "vultron.scripts.vocab_examples"

_MKDOCSTRINGS_RE = re.compile(r"^:::\s+([\w.]+)", re.MULTILINE)


def _find_docs_with_old_import():
    """Return list of (file, line_number, line) tuples for stale imports."""
    results = []
    for md_file in DOCS_DIR.rglob("*.md"):
        for lineno, line in enumerate(md_file.read_text().splitlines(), 1):
            if OLD_IMPORT in line:
                results.append((md_file, lineno, line.strip()))
    return results


def _collect_mkdocstrings_modules():
    """Return list of (file, module_name) for all ::: directives in docs."""
    results = []
    for md_file in DOCS_DIR.rglob("*.md"):
        text = md_file.read_text()
        for match in _MKDOCSTRINGS_RE.finditer(text):
            results.append((md_file, match.group(1)))
    return results


def test_mkdocstrings_module_references_are_importable():
    """All ::: module references in docs must be importable.

    mkdocstrings directives (lines starting with :::) reference Python
    modules that must exist.  A missing module causes mkdocs build to emit
    an ERROR and abort page generation.
    """
    failures = []
    for md_file, module_name in _collect_mkdocstrings_modules():
        try:
            importlib.import_module(module_name)
        except ImportError:
            failures.append((md_file, module_name))

    if failures:
        details = "\n".join(
            f"  {path.relative_to(DOCS_DIR.parent)}: {mod}"
            for path, mod in failures
        )
        raise AssertionError(
            f"Found {len(failures)} unresolvable mkdocstrings reference(s):\n"
            f"{details}"
        )


def test_no_stale_vocab_examples_imports_in_docs():
    """Docs markdown files must not import from the removed vultron.scripts.vocab_examples module.

    The module was refactored into vultron.wire.as2.vocab.examples.vocab_examples.
    All docs code blocks must use the new import path.
    """
    stale = _find_docs_with_old_import()
    if stale:
        details = "\n".join(
            f"  {path.relative_to(DOCS_DIR.parent)}:{lineno}: {line}"
            for path, lineno, line in stale
        )
        raise AssertionError(
            f"Found {len(stale)} stale import(s) of '{OLD_IMPORT}' in docs:\n{details}\n"
            f"Update to: vultron.wire.as2.vocab.examples.vocab_examples"
        )
