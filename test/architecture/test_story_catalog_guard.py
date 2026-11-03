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
"""PR-only guard over the user-story page catalog (TRACE-03-002).

A story ID is permanent: a `stories:` entry must resolve for as long as any
revision of the citing spec exists, and a page whose file is deleted frees its
ID for a later story, which would silently repoint every citation of the old
one. A withdrawn or split story therefore keeps its page, marked superseded.

spec-lint cannot see this. It checks the *current* corpus against the
*current* catalog (TRACE-03-001), so deleting a page and the one citation that
named it passes it clean. This guard compares the catalog with the merge base
instead, and fails on a removal. No count is committed (#3984): additions never
fail, so concurrent PRs cannot race.

Spec: TRACE-03-002.
"""

import pytest

from test.architecture import _corpus
from vultron.metadata.specs.story_links import removed_story_pages


@pytest.mark.spec_corpus
@pytest.mark.spec("TRACE-03-002")
def test_no_pr_removes_a_story_page():
    """No story ID with a page at the merge base has lost it at the head."""
    check = removed_story_pages(_corpus.REPO_ROOT)
    if check.skipped:
        pytest.skip(check.skipped)
    assert not check.removed, check.failure_message()
