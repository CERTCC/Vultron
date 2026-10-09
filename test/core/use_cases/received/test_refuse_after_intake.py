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

"""``refuse_after_intake`` reports a leader skip as SKIPPED, not REFUSED (CLP-10-018)."""

from unittest.mock import MagicMock

import py_trees
import pytest

from vultron.core.behaviors.bridge import BTExecutionResult
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received import _store_only


@pytest.mark.spec("CLP-10-018")
def test_leader_skip_is_not_reported_as_a_refusal(monkeypatch):
    tree = py_trees.behaviours.Success(name="tree")
    skipped = BTExecutionResult(
        status=py_trees.common.Status.INVALID, leader_skipped=True
    )
    monkeypatch.setattr(
        _store_only, "run_store_only", lambda *a, **k: (tree, skipped)
    )

    result = _store_only.refuse_after_intake(
        MagicMock(),
        MagicMock(),
        "missing id",
        name="Test",
        sync_port=None,
        wire_render_port=None,
    )

    assert result.disposition is HandlerDisposition.SKIPPED
