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

"""A CASE_MANAGER commit node with no trigger-activity port raises (#3743).

Its entry is the factory-built activity's sealed blob (VM-08-003), so without
the port there is nothing to commit.  That is a composition fault, never a
refusal: a FAILURE could be read by an enclosing Selector as a guard that did
not pass, so ``BTBridge`` must report it as an internal error and nothing may
be committed (ARCH-15-001).
"""

from collections.abc import Callable

import py_trees
import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.proposal_ledger import (
    CommitNativeLedgerEntriesNode,
)
from vultron.core.behaviors.case_status_snapshot import (
    EmitCaseStatusUpdateNode,
)
from vultron.core.behaviors.embargo.nodes.manager_commit import (
    CommitEmbargoDecisionNode,
)
from vultron.core.behaviors.helpers import TRIGGER_FACTORY_UNAVAILABLE
from vultron.core.behaviors.sync.demo_log_entry import CommitDemoLogEntryNode
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry

_ACTOR = "https://example.org/actors/case-manager"
_CASE = "https://example.org/cases/no-port"


def _unreachable(to: list[str] | None) -> tuple[str, str]:
    raise AssertionError("the builder must not run without the port")


NODES: dict[str, Callable[[], py_trees.behaviour.Behaviour]] = {
    "embargo decision": lambda: CommitEmbargoDecisionNode(
        case_id=_CASE, semantic_type="accept_embargo", builder=_unreachable
    ),
    "demo log entry": lambda: CommitDemoLogEntryNode(
        case_id=_CASE, object_id=_CASE, semantic_type="demo_event"
    ),
    "case status snapshot": lambda: EmitCaseStatusUpdateNode(case_id=_CASE),
    "case creation entries": lambda: CommitNativeLedgerEntriesNode(
        owner_uri=_ACTOR, report_id=None
    ),
}


@pytest.mark.spec("ARCH-15-001")
@pytest.mark.parametrize("node", sorted(NODES))
def test_a_missing_trigger_activity_port_is_an_internal_error(node):
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_ACTOR)
    dl.create(VulnerabilityCase(id_=_CASE, attributed_to=_ACTOR))

    result = BTBridge(
        datalayer=dl, wire_render_port=As2WireRenderAdapter()
    ).execute_with_setup(NODES[node](), actor_id=_ACTOR, case_id=_CASE)

    assert result.internal_error, result.feedback_message
    assert TRIGGER_FACTORY_UNAVAILABLE in result.feedback_message
    assert not [
        e
        for e in dl.list_objects("CaseLedgerEntry")
        if isinstance(e, CaseLedgerEntry)
    ]
