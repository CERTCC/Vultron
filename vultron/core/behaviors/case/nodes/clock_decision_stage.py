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

"""The clock-decision stage of a received-side tree (CLP-10-025, ADR-0135).

A clock decision is a decision the CASE_MANAGER takes from its own clock or
local policy before it judges the received activity, such as an expiry
(CLP-07-013, CM-21-017, CM-28-009).  It is ledgered even when the activity
that prompted it is then admitted, so it cannot be a refusal effect, and it
must not wait for the activity's commit.

:func:`~vultron.core.behaviors.case.receive_activity_tree.create_receive_activity_tree`
builds the stage after the door guards and before the precondition guards
(CLP-10-010), inside a CASE_MANAGER gate (BT-17-001), from the case-wide
decisions every case tree takes
(:func:`~vultron.core.behaviors.case.case_clock_decisions.case_clock_decisions`,
the embargo end-time check) and the tree's own ``clock_decisions`` (an
expiry)::

    ClockDecisionsIfCaseManager (CaseManagerGate)
    └─ ClockDecisionStage (Sequence)
       ├─ ClockDecision(<decision 1>)
       └─ ClockDecision(<decision 2>) …

Each :class:`ClockDecision` turns its decision's ``FAILURE`` — a commit the
ledger refused, or any other failure the decision reports as a status — into
a WARNING and ``SUCCESS``, so the tree continues and the precondition guards
refuse what the unrecorded decision forbids.  An internal error is an
exception, which no node here catches, so it ends the tree as an internal
error (ADR-0095).  A node that catches its own error and returns ``FAILURE``
hides it from this stage as from the bridge (CONCERN #3019), so a new decision
should raise what it cannot attribute to the protocol.

A clock decision commits one CASE_MANAGER entry for each AS2 activity
needed to express what it decided, and nothing about the received activity
(CLP-10-025): an expiry is one entry, an end-time termination the
``Remove`` (whose register step cancels every open proposal) and each
status update and re-issued stub ``Invite`` it needs.

The factory owns this structure; a tree supplies only the decisions.  A
case-scoped trigger composes the same gated stage ahead of its own tree
(``SvcBTTriggerBase``), so an overdue embargo is ended whatever the entry
point; :func:`create_clock_decision_gate` builds it for both.
"""

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.role_gates import (
    CaseManagerGate,
    create_case_manager_gated_tree,
)
from vultron.core.behaviors.node_logger import node_logger

__all__ = [
    "CLOCK_DECISION_GATE_NAME",
    "ClockDecision",
    "ClockDecisionStage",
    "create_clock_decision_gate",
]

#: Name of the CASE_MANAGER gate around the clock-decision stage.
CLOCK_DECISION_GATE_NAME = "ClockDecisionsIfCaseManager"


class ClockDecision(py_trees.decorators.Decorator):
    """One clock decision; a refused commit never ends the tree.

    ``SUCCESS`` when the decision recorded nothing or committed its entry.
    When the decision fails — typically its commit was refused — the failure
    is logged at WARNING and reported as ``SUCCESS`` (CLP-10-025).  The child keeps
    its ``FAILURE`` status for inspection.  An exception the decision raises
    is not caught, so an internal error still ends the tree (ADR-0095).
    """

    def update(self) -> Status:
        child = self.decorated
        if child.status == Status.FAILURE:
            self.feedback_message = BTBridge.get_failure_reason(child)
            log = node_logger(self)
            log.warning(
                "%s: clock decision '%s' failed; the tree continues: %s",
                self.name,
                child.name,
                self.feedback_message,
            )
            return Status.SUCCESS
        return child.status


class ClockDecisionStage(py_trees.composites.Sequence):
    """The tree's clock decisions, each wrapped in a :class:`ClockDecision`.

    A plain ``Sequence`` in behaviour; the subclass names the stage, so the
    ordering ratchet can tell the one place a commit may precede the
    precondition guards (CLP-10-025).  Only
    :func:`create_clock_decision_gate` constructs one.
    """

    def __init__(
        self, name: str, decisions: list[py_trees.behaviour.Behaviour]
    ) -> None:
        super().__init__(
            name=name,
            memory=False,
            children=[
                ClockDecision(name=f"ClockDecision[{d.name}]", child=d)
                for d in decisions
            ],
        )

    @property
    def decisions(self) -> list[py_trees.behaviour.Behaviour]:
        """The decisions, unwrapped (for inspection)."""
        return [
            child.decorated
            for child in self.children
            if isinstance(child, ClockDecision)
        ]


def create_clock_decision_gate(
    case_id: str, decisions: list[py_trees.behaviour.Behaviour]
) -> CaseManagerGate:
    """The clock-decision stage for *case_id*, run only at its CASE_MANAGER.

    The gate reads a case this store does not hold as "not the CASE_MANAGER"
    at ``debug`` level: a replica, or an invitee holding only a stub, never
    computes a clock decision (CM-21-017, CM-28-014).  The received-tree
    factory places it after the door guards (CLP-10-025); a case-scoped
    trigger places it ahead of its own tree.
    """
    return create_case_manager_gated_tree(
        name=CLOCK_DECISION_GATE_NAME,
        case_id=case_id,
        children=[
            ClockDecisionStage(name="ClockDecisions", decisions=decisions)
        ],
        case_may_be_absent=True,
    )
