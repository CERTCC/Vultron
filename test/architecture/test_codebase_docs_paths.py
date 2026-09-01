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
"""Ratchet: every file path cited in docs/reference/codebase/*.md must exist.

Prevents phantom adapter or module references from silently reappearing in
agent-facing context files.  A row citing a non-existent path (e.g. a retired
adapter like ``asgi_emitter.py``) would mislead an agent into believing that
component is available when it is not.

Source: ISSUE-2552.
"""

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).parents[2]
_DOCS_ROOT = _REPO_ROOT / "docs" / "reference" / "codebase"

# Path prefixes that unambiguously identify filesystem paths in these docs.
# Strings starting with these prefixes and containing no whitespace or shell
# metacharacters are treated as path references that must exist on disk.
_PATH_PREFIXES = (
    "vultron/",
    "test/",
    "docs/",
    "notes/",
    "specs/",
    "plan/",
    "docker/",
    "AGENTS.md",
    ".github/",
    ".devcontainer/",
    ".flake8",
    ".env.example",
    ".pre-commit",
    "pyproject.toml",
    "integration_tests/",
)

_INVALID_CHARS = re.compile(r"[ ()*<>#]")
# Strip optional trailing :LINE or :LINE-LINE suffixes (e.g. "foo.py:18-19")
_LINE_SUFFIX = re.compile(r":\d+(-\d+)?$")


def _extract_paths(text: str) -> list[str]:
    """Return backtick-quoted strings that look like filesystem paths."""
    results = []
    for m in re.finditer(r"`([^`\n]+)`", text):
        candidate = m.group(1)
        # Strip trailing line-number annotations before prefix/char checks
        candidate = _LINE_SUFFIX.sub("", candidate)
        if not any(candidate.startswith(prefix) for prefix in _PATH_PREFIXES):
            continue
        if _INVALID_CHARS.search(candidate):
            continue
        results.append(candidate)
    return results


def test_codebase_docs_cited_paths_exist():
    """Every file path cited in docs/reference/codebase/*.md must resolve to an existing path.

    Source: ISSUE-2552.
    """
    missing: list[str] = []
    for doc_file in sorted(_DOCS_ROOT.glob("*.md")):
        text = doc_file.read_text(encoding="utf-8")
        for path_str in _extract_paths(text):
            if not (_REPO_ROOT / path_str).exists():
                missing.append(f"{doc_file.name}: {path_str!r}")

    assert missing == [], (
        "The following paths cited in docs/reference/codebase/ do not exist.\n"
        "Update the doc to reflect current paths, or remove the stale row:\n"
        + "\n".join(f"  {m}" for m in missing)
    )
