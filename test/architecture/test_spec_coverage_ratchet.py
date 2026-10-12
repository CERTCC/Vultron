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
"""PR-only growth guard: @pytest.mark.spec coverage of implementer-kind specs.

No PR may add an uncovered ``kind: protocol`` or ``kind: foundation``
requirement (SR-05-005, ADR-0133). The guard evaluates
:func:`~vultron.metadata.specs.coverage.uncovered_implementer_ids` at the merge
base with the base branch and at the working tree, and fails on each ID
uncovered now that was covered, or was of neither kind, at the base: a new
protocol or foundation spec with no marker, the removal of an ID's last
marker, or a relabel into either kind without one. A relabel between the two
kinds keeps its marker; a relabel out of both, or a retired spec, leaves the
set and is never an addition.

No count is committed, so concurrent PRs cannot race on it (#4315,
``notes/testing-pitfalls.md`` § "A Two-Sided Count Pin Races Every Concurrent
PR"). ``spec-coverage`` prints the live uncovered total. When no base ref is
available the test skips with the reason; under GitHub Actions it fails.

A second guard, :func:`test_no_pr_drops_a_marker_while_changing_a_kind`,
holds the MS-12-011 rule: a spec whose kind changes keeps the markers it had,
whatever the destination kind.

Specs: SR-05-005, MS-12-011.
"""

import pytest

from test.architecture import _corpus
from vultron.metadata.specs.coverage import (
    kinds_and_markers,
    markers_dropped_by_kind_change,
    uncovered_implementer_ids,
)
from vultron.metadata.specs.growth_guard import (
    added_since_base,
    compare_with_base,
)

#: The trees :func:`uncovered_implementer_ids` reads.
_GUARDED_PATHS = ("specs", "test")
_TEST_ROOT = _corpus.REPO_ROOT / "test"


@pytest.mark.spec_corpus
@pytest.mark.spec("SR-05-005")
def test_no_pr_adds_an_uncovered_implementer_spec():
    """HEAD has no uncovered implementer-kind ID covered or absent at base."""
    # The head side reads test sources from the shared corpus (TB-13-001)
    # through the same extractor the base side runs on its materialized tree.
    head = uncovered_implementer_ids(
        _corpus.REPO_ROOT,
        test_sources=(
            source for _, source in _corpus.all_sources(under=_TEST_ROOT)
        ),
    )
    check = added_since_base(
        uncovered_implementer_ids,
        repo_root=_corpus.REPO_ROOT,
        paths=_GUARDED_PATHS,
        head=head,
    )
    if check.skipped:
        pytest.skip(check.skipped)
    assert not check.added, check.failure_message(
        "uncovered kind: protocol or kind: foundation spec(s)",
        'Add @pytest.mark.spec("<ID>") to the test that verifies each one, '
        "in this PR. If the behaviour is not built yet, use the strict-xfail "
        "pattern in notes/spec-authoring-rules.md § Marker Coverage Guard.",
    )


@pytest.mark.spec_corpus
@pytest.mark.spec("MS-12-011")
def test_no_pr_drops_a_marker_while_changing_a_kind():
    """No ID that changed kind since the base lost the marker it had there."""
    head = kinds_and_markers(
        _corpus.REPO_ROOT,
        test_sources=(
            source for _, source in _corpus.all_sources(under=_TEST_ROOT)
        ),
    )
    seen = compare_with_base(
        kinds_and_markers,
        repo_root=_corpus.REPO_ROOT,
        paths=_GUARDED_PATHS,
        head=head,
    )
    if seen.skipped is not None:
        pytest.skip(seen.skipped)
    assert seen.base_value is not None
    dropped = markers_dropped_by_kind_change(seen.base_value, head)
    assert not dropped, (
        f"{len(dropped)} spec(s) changed kind and lost the "
        f"@pytest.mark.spec marker they had at the merge base "
        f"(MS-12-011): {sorted(dropped)}. A kind change keeps the tests that "
        f"already verify a spec, whatever the destination kind: restore the "
        f"marker. If this lists specs the branch did not touch, run "
        f"`git fetch origin` and retry."
    )
