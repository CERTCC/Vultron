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

"""
Embargo composite subtrees for case behavior trees.

Provides tree-composition classes (``py_trees.composites.Sequence``
subclasses) that assemble groups of embargo leaf nodes into named
subtrees.  These composites belong here at the process-area root rather
than in the ``nodes/`` subpackage, which is reserved for leaf
``Behaviour`` subclasses (BTND-07-003).

Subtrees defined here:

- ``InitializeDefaultEmbargoNode`` — composed subtree for default embargo
  initialization on case creation.  Assembles the five leaf steps:
  resolve duration, create event, advance EM state, attach embargo to
  case, and seed owner as SIGNATORY.

Consumed by ``receive_report_case_tree.py``.

Per specs/case-management.yaml CM-02, OX-03-001, CM-14-003.
Per specs/behavior-tree-node-design.yaml BTND-07-003.
"""

import py_trees

from vultron.core.behaviors.case.nodes.embargo import (
    AdvanceEMStateToActiveNode,
    AttachEmbargoToCaseNode,
    CreateEmbargoEventNode,
    ResolveEmbargoDurationNode,
    SeedOwnerAsSignatoryNode,
)


class InitializeDefaultEmbargoNode(py_trees.composites.Sequence):
    """Composed subtree for default embargo initialization on case creation."""

    def __init__(self, name: str | None = None) -> None:
        super().__init__(
            name=name or self.__class__.__name__,
            memory=False,
            children=[
                ResolveEmbargoDurationNode(),
                CreateEmbargoEventNode(),
                AdvanceEMStateToActiveNode(),
                AttachEmbargoToCaseNode(),
                SeedOwnerAsSignatoryNode(),
            ],
        )
