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
"""Run the report receiver's two proposal nodes, as its tree composes them.

``ConvertReportToCaseProposalNode`` builds the core proposal and
``ProposeReportCaseToActorNode`` sends it (CP-01-026, CP-04-002).  *between*
runs between them, as a receiver that changes its proposal before sending
it would.
"""

from collections.abc import Sequence

import py_trees
from py_trees.common import Status

from test.support.act_runner import run_tree
from vultron.core.behaviors.act_key_scope import with_act_keys
from vultron.core.behaviors.act_keys import REPORT_ID
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes import (
    ConvertReportToCaseProposalNode,
    ProposeReportCaseToActorNode,
)
from vultron.core.models.case_proposal import CaseProposal
from vultron.core.models.report_claims import ClaimsReading
from vultron.core.ports.case_persistence import CasePersistence


def proposal_nodes(
    report_id: str,
    readings: Sequence[ClaimsReading] = (),
    between: Sequence[py_trees.behaviour.Behaviour] = (),
) -> py_trees.composites.Sequence:
    """The convert and send nodes for *report_id*, *between* in between."""
    return py_trees.composites.Sequence(
        name="ProposeReportCase",
        memory=False,
        children=[
            with_act_keys(
                ConvertReportToCaseProposalNode(readings=readings),
                {REPORT_ID: report_id},
            ),
            *between,
            ProposeReportCaseToActorNode(),
        ],
    )


def propose_report_case(
    bridge: BTBridge,
    datalayer: CasePersistence,
    actor_id: str,
    report_id: str,
) -> CaseProposal:
    """Convert and send *report_id*'s proposal; return the one stored."""
    tree = proposal_nodes(report_id)
    result = run_tree(bridge, tree=tree, actor_id=actor_id)
    assert result.status == Status.SUCCESS, result.feedback_message
    (proposal,) = [
        p
        for p in datalayer.list_objects("CaseProposal")
        if isinstance(p, CaseProposal)
    ]
    return proposal
