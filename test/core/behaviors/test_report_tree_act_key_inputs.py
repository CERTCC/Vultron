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

"""The report-tree nodes, and the end-time cascade nodes the run-time
clock-decision stage builds, read their per-act values from act keys
(BTND-01-008, #6476).

Each node takes only configuration in its constructor.  Ticked with no seed
for a key it requires, it raises a wiring error naming the key (BT-25-008)
rather than deciding anything without it.  Keys a node reads as optional
(``/case_id`` on ``AdjudicateRMDeclarationNode``, ``EmitRMGapNoteNode``,
``CommitParticipantStatusEntriesNode`` and ``CheckParticipantRMState``) are
not listed.
"""

import pytest

from test.support.act_key_inputs import (
    NodeBuild,
    assert_unseeded_key_raises,
    restored_act_keys,
    unseeded_key_case_ids,
    unseeded_key_cases,
)
from vultron.core.behaviors.act_keys import CASE_ID, SENDER_ID, ActKey
from vultron.core.behaviors.case.nodes.participant.status_entries import (
    CommitParticipantStatusEntriesNode,
)
from vultron.core.behaviors.case.nodes.stub_reissue import (
    ReissueStubInvitesNode,
)
from vultron.core.behaviors.embargo.nodes.conditions import (
    HasActiveEmbargoNode,
)
from vultron.core.behaviors.embargo.nodes.em_state import ReadEmbargoIdNode
from vultron.core.behaviors.report.nodes.conditions import (
    CheckParticipantRMState,
)
from vultron.core.behaviors.sender.nodes.actions import ResolveCaseManagerNode
from vultron.core.behaviors.status.nodes.rm_anomaly import EmitRMGapNoteNode
from vultron.core.behaviors.status.nodes.rm_declaration import (
    AdjudicateRMDeclarationNode,
)
from vultron.core.states.rm import RM

#: Each moved node, built from configuration alone, and the act keys it
#: cannot run without.
_NODES: list[tuple[NodeBuild, tuple[ActKey, ...]]] = [
    (lambda: HasActiveEmbargoNode(result_out={}), (CASE_ID,)),
    (ReadEmbargoIdNode, (CASE_ID,)),
    (ReissueStubInvitesNode, (CASE_ID,)),
    (ResolveCaseManagerNode, (CASE_ID,)),
    (lambda: AdjudicateRMDeclarationNode(declared_rm=RM.VALID), (SENDER_ID,)),
    (EmitRMGapNoteNode, (SENDER_ID,)),
    (lambda: CommitParticipantStatusEntriesNode(status_ids=[]), (SENDER_ID,)),
    (lambda: CheckParticipantRMState(target_rm=RM.VALID), (SENDER_ID,)),
]

_CASES = unseeded_key_cases(_NODES)


def test_every_listed_key_is_a_port_of_its_node() -> None:
    for build, keys in _NODES:
        remaps = type(build())._domain_port_remappings()  # type: ignore[attr-defined]
        assert {k.path for k in keys} <= set(remaps.values()), build


@pytest.mark.spec("BTND-01-008", "BT-25-008")
@pytest.mark.parametrize(
    ("build", "key", "keys"), _CASES, ids=unseeded_key_case_ids(_CASES)
)
def test_a_node_ticked_without_its_key_seeded_raises_naming_the_key(
    build: NodeBuild, key: ActKey, keys: tuple[ActKey, ...]
) -> None:
    with restored_act_keys():
        assert_unseeded_key_raises(build, key, keys)
