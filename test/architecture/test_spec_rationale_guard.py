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
"""PR-only growth guard over requirements with no ``rationale:`` (MS-10-014).

Every requirement needs a rationale (MS-10-012), but the schema still admits a
missing one until the backfill reaches zero. This guard holds the gap from
growing meanwhile: a requirement with no rationale at the PR head that had one
at the merge base, or did not exist there, fails. A gap already present at the
base is the backfill's, never this branch's. No count is committed (#4315).

Spec: MS-10-014.
"""

import pytest

from test.architecture import _corpus
from vultron.metadata.specs.growth_guard import added_since_base
from vultron.metadata.specs.rationale import missing_rationale_ids


@pytest.mark.spec_corpus
@pytest.mark.spec("MS-10-014")
def test_no_pr_adds_a_requirement_without_a_rationale():
    """No requirement lacks a rationale it had, or was born without one."""
    check = added_since_base(
        missing_rationale_ids,
        repo_root=_corpus.REPO_ROOT,
        paths=("specs",),
    )
    if check.skipped:
        pytest.skip(check.skipped)
    assert not check.added, check.failure_message(
        "requirement(s) with no rationale",
        "Give each a `rationale:` that says why the requirement is necessary "
        "now, the problem it prevents or the property it guarantees, not how "
        "it came about (MS-10-012).",
    )
