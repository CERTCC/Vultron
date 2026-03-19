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

import re
from pathlib import Path

DOCS_DIR = Path(__file__).parent.parent / "docs"
OLD_IMPORT = "vultron.scripts.vocab_examples"


def _find_docs_with_old_import():
    """Return list of (file, line_number, line) tuples for stale imports."""
    results = []
    for md_file in DOCS_DIR.rglob("*.md"):
        for lineno, line in enumerate(md_file.read_text().splitlines(), 1):
            if OLD_IMPORT in line:
                results.append((md_file, lineno, line.strip()))
    return results


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
