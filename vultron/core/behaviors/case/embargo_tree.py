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

- ``InitializeDefaultEmbargoNode`` — composed subtree for initial embargo
  set-up on case creation.  A case with P/X/A set gets no embargo and stays
  EM.NONE (EP-04-008); any other case runs the leaf steps: resolve
  duration, create event, advance EM state to ACTIVE with the embargo
  attached (one write, EP-04-002), seed owner as SIGNATORY, and register a
  longer creation-time proposal as a pending revision (EP-04-003).

Consumed by ``case_proposal_received_tree.py``.

Per specs/case-management.yaml CM-02, OX-03-001, CM-14-003.
Per specs/embargo-policy.yaml EP-04-005 through EP-04-008 (ADR-0096).
Per specs/behavior-tree-node-design.yaml BTND-07-003.
"""

import py_trees

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.case.nodes.embargo import (
    AdvanceEMStateToActiveNode,
    CreateEmbargoEventNode,
    SeedOwnerAsSignatoryNode,
)
from vultron.core.behaviors.case.nodes.embargo_resolution import (
    CaseEmbargoAlreadyInitializedNode,
    CaseNotEmbargoEligibleNode,
    ResolveEmbargoDurationNode,
)
from vultron.core.behaviors.case.nodes.embargo_revision import (
    RegisterLongerProposalAsRevisionNode,
)


class InitializeDefaultEmbargoNode(py_trees.composites.Selector):
    """Composed subtree for initial embargo set-up on case creation.

    The first arm succeeds, doing nothing, when the case's EM state has left
    ``EM.NONE``: initialization ran when the case was created, and a
    redelivered proposal that reuses the case (CP-05-006) must not run it
    again in any later state, ``EXITED`` included (EP-04-012).  The EM state,
    not the active-embargo reference, is the evidence — termination clears the
    reference but never returns the state to ``NONE``.  A case still at
    ``NONE`` was never initialized, so the arm falls through.  The second
    arm succeeds, creating nothing, when the case is not embargo eligible
    (EP-04-008).  Otherwise the creation arm runs, and its failure is the
    subtree's failure — neither guard arm masks it.

    Args:
        actor_config: Source of the protocol default embargo duration
            (EP-04-005).  ``None`` uses the ``ActorConfig`` defaults.
        name: Optional node name.
    """

    def __init__(
        self,
        actor_config: ActorConfig | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(
            name=name or self.__class__.__name__,
            memory=False,
            children=[
                CaseEmbargoAlreadyInitializedNode(),
                CaseNotEmbargoEligibleNode(),
                py_trees.composites.Sequence(
                    name="CreateInitialEmbargo",
                    memory=False,
                    children=[
                        ResolveEmbargoDurationNode(actor_config=actor_config),
                        CreateEmbargoEventNode(),
                        # EP-04-002: propose and activate are one write, so
                        # EM.PROPOSED is never persisted.
                        AdvanceEMStateToActiveNode(),
                        SeedOwnerAsSignatoryNode(),
                        # EP-04-003: the longer creation-time candidate becomes
                        # a pending revision (ACTIVE → REVISE) when both
                        # parties proposed.
                        RegisterLongerProposalAsRevisionNode(),
                    ],
                ),
            ],
        )
