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
"""Every non-empty ratchet baseline under ``test/`` names an owner (ARCH-18-003).

A module-level constant named ``KNOWN_*``, ``*_BASELINE``, ``MAX_*`` or
``*_EXEMPTIONS`` that is not empty or zero carries ``# owner: #N`` (a ratchet)
or ``# permanent: <issue, ADR or spec ID>`` (a pinned exemption set,
ARCH-18-005). The marker parser is :mod:`vultron.metadata.ratchet_markers`;
this test feeds it the shared corpus's cached trees (TB-13-001, TB-13-003) and
makes no network call. Whether a cited owner is still open is a scheduled CI
check, which never fails the build (ARCH-18-004).
"""

import pytest

from test.architecture import _corpus
from vultron.metadata.ratchet_markers import Baseline, baselines_in, violations

_TEST_ROOT = _corpus.REPO_ROOT / "test"

#: Substrings every ratchet-named constant contains; a file with none of them
#: holds no baseline and is never parsed.
_FRAGMENTS = ("KNOWN_", "_BASELINE", "MAX_", "_EXEMPTIONS")


def _baselines() -> list[Baseline]:
    found: list[Baseline] = []
    for path, tree in _corpus.files_mentioning(*_FRAGMENTS, under=_TEST_ROOT):
        rel = path.relative_to(_corpus.REPO_ROOT)
        found += baselines_in(tree, _corpus.source_of(path), rel)
    return found


@pytest.mark.spec("ARCH-18-003")
def test_every_non_empty_baseline_names_an_owner() -> None:
    """ARCH-18-003: no non-empty ratchet baseline under ``test/`` is unowned."""
    problems = violations(_baselines())
    assert problems == [], (
        "Ratchet baselines without a valid owner marker (ARCH-18-003,"
        " notes/architecture-ratchet-corpus.md):\n"
        + "\n".join(f"  {p}" for p in problems)
    )


def test_the_scan_finds_baselines() -> None:
    """A scan that finds nothing would pass vacuously."""
    names = {b.name for b in _baselines()}
    assert {"KNOWN_ALLOWLIST", "ACTIVITY_TYPE_EXEMPTIONS"} <= names
