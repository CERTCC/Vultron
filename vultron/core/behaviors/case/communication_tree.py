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
Communication composite subtrees for case behavior trees.

Provides tree-composition classes (``py_trees.composites.Sequence``
subclasses) that assemble groups of communication leaf nodes into named
subtrees.  These composites belong here at the process-area root rather
than in the ``nodes/`` subpackage, which is reserved for leaf
``Behaviour`` subclasses (BTND-07-003).

Subtrees defined here:

- ``EmitCreateCaseActivity`` — emits the Create(Case) activity in two
  explicit leaf steps (collect addressees, then build/persist activity).

Consumed by ``create_tree.py`` and related trees.

Per specs/behavior-tree-node-design.yaml BTND-07-003.
"""

import py_trees

from vultron.core.behaviors.case.nodes.communication import (
    CollectCaseAddresseesNode,
    CreateAndPersistCaseActivityNode,
)


class EmitCreateCaseActivity(py_trees.composites.Sequence):
    """Composed subtree that emits CreateCaseActivity in explicit steps."""

    def __init__(self, name: str | None = None):
        py_trees.composites.Sequence.__init__(
            self,
            name=name or self.__class__.__name__,
            memory=False,
            children=[
                CollectCaseAddresseesNode(),
                CreateAndPersistCaseActivityNode(),
            ],
        )
