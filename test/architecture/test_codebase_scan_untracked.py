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
"""Ratchet: the codebase-scan artifact must never be tracked by git.

``docs/reference/codebase/.codebase-scan.txt`` is a regenerable discovery
artifact written by the ``acquire-codebase-knowledge`` scan.  It is named in
``.gitignore``, but a committed file is not un-tracked by adding an ignore rule
after the fact — which is exactly how a 16 MB stale mirror of the rendered docs
site (including deleted pages) lived in the repo and poisoned ``git grep``
censuses with confident references to nonexistent pages.

This test fails if the artifact is ever tracked again, so a stray ``git add -A``
or ``git add -f`` cannot silently re-commit it.

Source: ISSUE-3443.
"""

import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).parents[2]
_SCAN_ARTIFACT = "docs/reference/codebase/.codebase-scan.txt"


def test_codebase_scan_artifact_is_not_tracked():
    """``.codebase-scan.txt`` is a generated artifact and MUST stay untracked.

    Source: ISSUE-3443.
    """
    result = subprocess.run(
        ["git", "ls-files", "--", _SCAN_ARTIFACT],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    tracked = result.stdout.strip()
    assert tracked == "", (
        f"{_SCAN_ARTIFACT} is tracked by git, but it is a regenerable scan "
        "artifact that must stay untracked (it is already named in .gitignore).\n"
        "Run `git rm --cached " + _SCAN_ARTIFACT + "` to un-track it; do not "
        "commit the file."
    )
