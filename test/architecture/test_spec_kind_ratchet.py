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
"""Corpus ratchets for the MS-12 SpecKind decision tree (MS-12-006, MS-12-007).

Three layers enforce MS-12 and no single one is sufficient (issue #3600):

1. the check inside ``spec-lint``, which the pre-commit hook runs — but only
   when a ``specs/*.yaml`` file is staged, so editing the linter alone never
   triggers it locally;
2. unit tests in ``test/metadata/specs/test_lint.py`` on synthetic fixtures;
3. this module, which runs against the **live** corpus on every local pytest
   run regardless of what is staged.

:data:`MAX_MISSING_STORY_SUPPRESSIONS` is pinned to the live count and may only
be **lowered**. :func:`test_missing_story_suppression_ceiling_is_tight` fails
when the constant sits above the live count, mirroring
``test/metadata/test_agents_md_size_ratchet.py::test_known_overage_ceilings_are_tight``:
a test cannot otherwise notice its own constant being edited upward, and slack
is headroom the corpus regrows into.

Spec: MS-12-006, MS-12-007.
"""

import pytest

from test.architecture import _corpus
from vultron.metadata.specs.kind_classification import (
    check_protocol_kind_code_references,
    count_missing_story_suppressions,
)
from vultron.metadata.specs.registry import load_registry

_SPEC_DIR = _corpus.REPO_ROOT / "specs"

# ---------------------------------------------------------------------------
# Specs carrying ``lint_suppress: [missing_story_reference]`` — every carrier,
# whether or not SR-11-003 would fire on it (MS-12-007).
#
# Set to the live count when the MS-12-006 relabel landed (#3600): 328 before
# that pass, 109 after it. The remaining carriers are the story-less
# protocol specs whose statements name no code and need judgment (#3601), the
# four protocol MUST_NOTs #3601 adjudicates ahead of #2717 (AC-9), and
# MSM-05-006, whose suppression silences the live SR-11-004 advisory.
#
# Lower this as suppressions are removed; never raise it. Adding a suppression
# fails this ratchet unless another is removed — the usual fix for SR-11-003
# firing on a new entry is a corrected ``kind:``, not a suppression
# (``specs/AGENTS.md``).
# ---------------------------------------------------------------------------
MAX_MISSING_STORY_SUPPRESSIONS = 109


@pytest.mark.spec_corpus
@pytest.mark.spec("MS-12-006")
def test_live_corpus_has_no_unsuppressed_protocol_kind_code_references():
    """No story-less ``kind: protocol`` spec names a codebase construct.

    The same detector ``spec-lint`` runs, applied to the real ``specs/``
    tree. A failure lists the offending IDs; the fix is to apply the
    MS-12-001 → MS-12-005 tree to each, not to add a suppression.
    """
    registry = load_registry(_SPEC_DIR)
    errors = check_protocol_kind_code_references(registry)
    assert errors == [], (
        f"{len(errors)} story-less protocol spec(s) reference code "
        f"(MS-12-006). Apply the MS-12-001 → MS-12-005 decision tree to each:\n"
        + "\n".join(f"  {e}" for e in errors)
    )


@pytest.mark.spec_corpus
@pytest.mark.spec("MS-12-007")
def test_missing_story_suppressions_within_ceiling():
    """The suppression count MUST NOT exceed :data:`MAX_MISSING_STORY_SUPPRESSIONS`."""
    live = count_missing_story_suppressions(load_registry(_SPEC_DIR))
    assert live <= MAX_MISSING_STORY_SUPPRESSIONS, (
        f"{live} specs carry lint_suppress: [missing_story_reference], over "
        f"the ceiling of {MAX_MISSING_STORY_SUPPRESSIONS} (MS-12-007). Do not "
        f"raise the ceiling: a new suppression is almost always a "
        f"misclassified kind — apply the MS-12-001 → MS-12-005 tree instead."
    )


@pytest.mark.spec_corpus
@pytest.mark.spec("MS-12-007")
def test_missing_story_suppression_ceiling_is_tight():
    """The ceiling MUST NOT sit above the live count.

    Without this, the "may only be lowered" rule is unenforced between the
    live count and the constant: a pass that removes 40 suppressions and
    leaves the constant alone hands the corpus 40 suppressions of headroom.
    Lowering the constant alongside the cleanup is the whole ratchet.
    """
    live = count_missing_story_suppressions(load_registry(_SPEC_DIR))
    assert live >= MAX_MISSING_STORY_SUPPRESSIONS, (
        f"MAX_MISSING_STORY_SUPPRESSIONS ({MAX_MISSING_STORY_SUPPRESSIONS}) is "
        f"above the live count ({live}); lower it to {live}."
    )
