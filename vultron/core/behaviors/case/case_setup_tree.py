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
Case setup composite subtrees.

Provides tree-composition classes (``py_trees.composites.Sequence`` /
``Selector`` subclasses) that assemble groups of case-setup leaf nodes
into named subtrees.  These composites belong here at the process-area
root rather than in the ``nodes/`` subpackage, which is reserved for
leaf ``Behaviour`` subclasses (BTND-07-003).

Subtrees defined here:

- ``RecordCaseCreationEvents`` — records offer_received and case_created
  events in sequence.
- ``CreateCaseActorNode`` — creates and registers the CaseActor service
  actor for a new case.

Both are consumed by ``create_tree.py`` and ``receive_report_case_tree.py``.

Per specs/case-management.yaml CM-02-001 and
specs/behavior-tree-node-design.yaml BTND-07-003.
"""

import py_trees

from vultron.core.behaviors.case.nodes.case_setup import (
    CreateCaseActorServiceNode,
    RecordCaseCreatedEventNode,
    RecordOfferReceivedEventNode,
    RegisterCaseActorParticipantNode,
    ResolveCaseActorUrlsNode,
    ReuseExistingCaseActorParticipantNode,
)
from vultron.core.models.vultron_types import VultronCase


class RecordCaseCreationEvents(py_trees.composites.Sequence):
    """Composed subtree that records offer_received (optional) and case_created."""

    def __init__(self, case_obj: VultronCase, name: str | None = None):
        self.case_obj = case_obj
        super().__init__(
            name=name or self.__class__.__name__,
            memory=False,
            children=[
                RecordOfferReceivedEventNode(),
                RecordCaseCreatedEventNode(),
            ],
        )


class CreateCaseActorNode(py_trees.composites.Sequence):
    """
    Composed subtree that creates and registers the CaseActor for a case.

    Per specs/case-management.yaml CM-02-001 and BTND-07-001.
    """

    def __init__(self, case_id: str | None = None, name: str | None = None):
        super().__init__(
            name=name or self.__class__.__name__,
            memory=False,
            children=[
                ResolveCaseActorUrlsNode(case_id=case_id),
                py_trees.composites.Selector(
                    name="EnsureCaseActorRegistered",
                    memory=False,
                    children=[
                        ReuseExistingCaseActorParticipantNode(),
                        py_trees.composites.Sequence(
                            name="CreateAndRegisterCaseActor",
                            memory=False,
                            children=[
                                CreateCaseActorServiceNode(),
                                RegisterCaseActorParticipantNode(),
                            ],
                        ),
                    ],
                ),
            ],
        )
