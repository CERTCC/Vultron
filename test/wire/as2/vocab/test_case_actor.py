#!/usr/bin/env python
"""
Tests for as_CaseActor wire object, including from_core conversions.
"""

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

import unittest
from datetime import datetime, timezone

from vultron.core.models.case_actor import CaseActor as CoreCaseActor
from vultron.wire.as2.vocab.objects.case_actor import as_CaseActor

ACTOR_ID = "https://example.org/case-actors/svc-1"
CASE_ID = "https://example.org/cases/case-001"
OWNER_ID = "https://example.org/actors/alice"


class TestFromCorePreservesPublished(unittest.TestCase):
    """as_CaseActor IS CaseActor (ADR-0099 detail 3, issue #3487).

    The paired wire class was deleted; as_CaseActor is now an alias for the
    core CaseActor class.  Verify that CaseActor preserves the provided
    published time (regression guard for issue #2554).
    """

    _FIXED_TIME = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    def test_as_case_actor_from_core_preserves_published(self):
        core = CoreCaseActor(
            id_=ACTOR_ID,
            context=CASE_ID,
            attributed_to=OWNER_ID,
            published=self._FIXED_TIME,
        )
        # as_CaseActor IS the core class; direct instantiation replaces from_core()
        self.assertIs(as_CaseActor, CoreCaseActor)
        self.assertEqual(self._FIXED_TIME, core.published)


if __name__ == "__main__":
    unittest.main()
