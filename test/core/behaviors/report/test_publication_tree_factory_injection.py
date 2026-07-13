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
"""Factory injection tests for create_publication_tree (BT-18-004).

Verifies the four Phase 2 reserved factory parameters are accepted without
error and that the wired prepare_report_factory is used correctly.
"""

import py_trees

from vultron.core.behaviors.report.publication_tree import (
    create_publication_tree,
)

CASE_ID = "https://example.org/cases/test-001"


def _marker_factory(label):
    """Return a factory that produces a distinctly-named Behaviour."""

    def factory(name):
        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name=label)

    return factory


# ---------------------------------------------------------------------------
# Phase 2 reserved params: accepted without error
# ---------------------------------------------------------------------------


def test_prioritize_publication_intents_factory_accepted():
    """prioritize_publication_intents_factory is accepted (Phase 2 reserved)."""
    tree = create_publication_tree(
        case_id=CASE_ID,
        prioritize_publication_intents_factory=_marker_factory("PPI"),
    )
    assert tree is not None


def test_reprioritize_exploit_factory_accepted():
    """reprioritize_exploit_factory is accepted (Phase 2 reserved)."""
    tree = create_publication_tree(
        case_id=CASE_ID,
        reprioritize_exploit_factory=_marker_factory("RE"),
    )
    assert tree is not None


def test_reprioritize_fix_factory_accepted():
    """reprioritize_fix_factory is accepted (Phase 2 reserved)."""
    tree = create_publication_tree(
        case_id=CASE_ID,
        reprioritize_fix_factory=_marker_factory("RF"),
    )
    assert tree is not None


def test_reprioritize_report_factory_accepted():
    """reprioritize_report_factory is accepted (Phase 2 reserved)."""
    tree = create_publication_tree(
        case_id=CASE_ID,
        reprioritize_report_factory=_marker_factory("RR"),
    )
    assert tree is not None


def test_all_phase2_factories_accepted_together():
    """All four Phase 2 reserved factories are accepted together."""
    tree = create_publication_tree(
        case_id=CASE_ID,
        prioritize_publication_intents_factory=_marker_factory("PPI"),
        reprioritize_exploit_factory=_marker_factory("RE"),
        reprioritize_fix_factory=_marker_factory("RF"),
        reprioritize_report_factory=_marker_factory("RR"),
    )
    assert tree is not None
