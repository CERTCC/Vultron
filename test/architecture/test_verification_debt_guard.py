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
"""PR-only growth guard over ``verification_debt`` markers (MS-10-016).

spec-lint checks each marker on its own (MS-10-006), so it cannot tell a new
unverified MUST that arrived with a marker from one that has carried it for
months. This guard can: a marker at the PR head that the requirement did not
carry at the merge base, or that names a different issue there, fails. A
re-pointed marker is the relabel MS-10-008 forbids — swapping in the
destination kind's owner — which spec-lint alone passes. A marker removed, or
moved with its requirement to another file, is not an addition, nor is the
marker of a new ID split off a requirement that carried it (MS-03-001). No
count is committed (#3984).

Spec: MS-10-016.
"""

import pytest

from test.architecture import _corpus
from vultron.metadata.specs.verification import debt_added_since_base


@pytest.mark.spec_corpus
@pytest.mark.spec("MS-10-016")
def test_no_pr_adds_a_verification_debt_marker():
    """No marker in HEAD that the merge base lacks."""
    check = debt_added_since_base(_corpus.REPO_ROOT)
    if check.skipped:
        pytest.skip(check.skipped)
    assert not check.added, check.failure_message(
        "verification_debt marker(s)",
        "Give each requirement a `verification:` criterion instead of a "
        "marker: new debt is not accepted, and a relabel replaces its marker "
        "rather than re-pointing it at another kind's owner (MS-10-007, "
        "MS-10-008). A new ID split off a marked requirement keeps its marker "
        "only when its own relationships: name that requirement.",
    )
