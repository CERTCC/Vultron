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

"""Make the P, X or A embargo teardown fail, for the CSB-18 safety net.

Adopting a P, X or A value also authorizes the embargo teardown it calls for,
so on the authorized path the teardown ends the embargo in the same act
(ADR-0166).  The one way a case is left with P, X or A beside an embargo in
force is a teardown that fails for a reason of its own, such as a broken
dispatch; ``PxaEmInvariantDiagnosticNode`` reports that gap (CSB-18-002 to
CSB-18-004, #4829).  A test that needs that state, or the note, makes the
teardown fail with :func:`fail_pxa_teardown`.
"""

import py_trees
import pytest

import vultron.core.behaviors.status.add_participant_status_tree as tree_module


def fail_pxa_teardown(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the teardown in every ``add_participant_status_tree`` built
    while *monkeypatch* is active with a node that ticks ``FAILURE``.

    Pass a ``monkeypatch.context()`` to scope the failure to one delivery.
    """
    monkeypatch.setattr(
        tree_module,
        "ThreatTerminationBranchNode",
        lambda **_kwargs: py_trees.behaviours.Failure(name="TeardownFailed"),
    )
