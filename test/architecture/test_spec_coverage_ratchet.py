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
"""PR-only growth guard: @pytest.mark.spec coverage of protocol-kind specs.

No PR may add an uncovered ``kind: protocol`` requirement (SR-05-005). The
guard evaluates :func:`~vultron.metadata.specs.coverage.uncovered_protocol_ids`
at the merge base with the base branch and at the working tree, and fails on
each ID uncovered now that was covered, or was not a protocol spec, at the
base: a new protocol spec with no marker, the removal of an ID's last marker,
or a relabel into ``kind: protocol`` without one. A relabel out of protocol or
a retired spec leaves the set and is never an addition.

No count is committed, so concurrent PRs cannot race on it (#4315,
``notes/testing-pitfalls.md`` § "A Two-Sided Count Pin Races Every Concurrent
PR"). ``spec-coverage`` prints the live uncovered total. When no base ref is
available the test skips with the reason; under GitHub Actions it fails.

Spec: SR-05-005.
"""

import pytest

from test.architecture import _corpus
from vultron.metadata.specs.coverage import uncovered_protocol_ids
from vultron.metadata.specs.growth_guard import added_since_base

#: The trees :func:`uncovered_protocol_ids` reads.
_GUARDED_PATHS = ("specs", "test")
_TEST_ROOT = _corpus.REPO_ROOT / "test"


@pytest.mark.spec_corpus
@pytest.mark.spec("SR-05-005")
def test_no_pr_adds_an_uncovered_protocol_spec():
    """HEAD has no uncovered protocol ID that was covered or absent at base."""
    # The head side reads test sources from the shared corpus (TB-13-001)
    # through the same extractor the base side runs on its materialized tree.
    head = uncovered_protocol_ids(
        _corpus.REPO_ROOT,
        test_sources=(
            source for _, source in _corpus.all_sources(under=_TEST_ROOT)
        ),
    )
    check = added_since_base(
        uncovered_protocol_ids,
        repo_root=_corpus.REPO_ROOT,
        paths=_GUARDED_PATHS,
        head=head,
    )
    if check.skipped:
        pytest.skip(check.skipped)
    assert not check.added, check.failure_message(
        "uncovered kind: protocol spec(s)",
        'Add @pytest.mark.spec("<ID>") to the test that verifies each one, '
        "in this PR. If the behaviour is not built yet, use the strict-xfail "
        "pattern in notes/spec-authoring-rules.md § Protocol Coverage Guard.",
    )
