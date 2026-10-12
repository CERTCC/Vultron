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
"""Corpus guards for the MS-12 SpecKind decision tree (MS-12-006/007/008).

Three layers enforce MS-12 and no single one is sufficient (issue #3600):

1. the check inside ``spec-lint``, which the pre-commit hook runs — but only
   when a ``specs/*.yaml`` file is staged, so editing the linter alone never
   triggers it locally;
2. unit tests in ``test/metadata/specs/test_lint.py`` on synthetic fixtures;
3. this module, which runs against the **live** corpus on every local pytest
   run regardless of what is staged.

No count is committed (#4315). MS-12-007 is a PR-only growth guard: a spec
that gains ``lint_suppress: [missing_story_reference]`` it lacked at the merge
base fails, and removals never do, so concurrent PRs cannot race on a shared
number. MS-12-008 holds ``protocol_kind_with_code_reference`` at its terminal
value — no carrier at all. ``spec-lint`` prints both live totals.

Spec: MS-12-006, MS-12-007, MS-12-008.
"""

import pytest

from test.architecture import _corpus
from vultron.metadata.specs.growth_guard import added_since_base
from vultron.metadata.specs.kind_classification import (
    check_protocol_kind_code_references,
    missing_story_suppression_carriers,
    suppression_carriers,
)
from vultron.metadata.specs.registry import load_registry
from vultron.metadata.specs.schema import LintWarningCode

_SPEC_DIR = _corpus.REPO_ROOT / "specs"


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
def test_no_pr_adds_a_missing_story_suppression():
    """No spec gains ``missing_story_reference`` it lacked at the merge base."""
    check = added_since_base(
        missing_story_suppression_carriers,
        repo_root=_corpus.REPO_ROOT,
        paths=("specs",),
    )
    if check.skipped:
        pytest.skip(check.skipped)
    assert not check.added, check.failure_message(
        "lint_suppress: [missing_story_reference] carrier(s)",
        "A new suppression is almost always a misclassified kind: apply the "
        "MS-12-001 → MS-12-005 tree, or map the spec to a user story.",
    )


@pytest.mark.spec_corpus
@pytest.mark.spec("MS-12-008")
def test_no_spec_carries_protocol_kind_with_code_reference():
    """MS-12-006's escape hatch has no carrier (its terminal value)."""
    carriers = suppression_carriers(
        load_registry(_SPEC_DIR),
        LintWarningCode.PROTOCOL_KIND_WITH_CODE_REFERENCE,
    )
    assert not carriers, (
        f"{len(carriers)} spec(s) carry lint_suppress: "
        f"[protocol_kind_with_code_reference]: {sorted(carriers)}. Apply the "
        f"MS-12-001 → MS-12-005 tree instead of suppressing MS-12-006."
    )
