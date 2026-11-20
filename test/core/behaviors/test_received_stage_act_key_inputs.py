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

"""The shared received-stage doors and sender checks read their per-act
values from act keys (BTND-01-008, #6572).

Each node takes only configuration in its constructor.  Ticked with no seed
for a key it requires, it raises a wiring error naming the key (BT-25-008)
rather than deciding anything without it.  Keys a node reads as optional
(``SenderIsOfferAddresseeNode``'s ``/offer_id``, ``SenderIsInviteeNode``'s
``/invite_id`` and ``/case_id``, ``SenderIsCaseManagerNode``'s keys) are not
listed.
"""

import pytest

from test.support.act_key_inputs import (
    NodeBuild,
    assert_unseeded_key_raises,
    restored_act_keys,
    unseeded_key_case_ids,
    unseeded_key_cases,
)
from vultron.core.behaviors.act_keys import (
    CASE_ID,
    EXPECTED_SENDER_SEQUENCE,
    NOTE_ID,
    PARTICIPANT_ID,
    PROPOSAL_ID,
    REFUSED_ACTIVITY_ID,
    REPORT_ID,
    SENDER_ID,
    ActKey,
)
from vultron.core.behaviors.case.nodes.ledgered_repeat import (
    ActivityNotYetLedgeredNode,
)
from vultron.core.behaviors.case.nodes.received_path import (
    ReplicaRefusalNode,
)
from vultron.core.behaviors.case.nodes.refusal_notice import (
    ClearRefusedAssertionNode,
    ResumeOutboundSequenceNode,
)
from vultron.core.behaviors.sender_entitlement.addressee import (
    SenderIsExpectedCaseCreatorNode,
    SenderIsOfferAddresseeNode,
    SenderIsProposalAddresseeNode,
)
from vultron.core.behaviors.sender_entitlement.author import (
    SenderIsNoteAuthorNode,
    SenderIsParticipantRecordSubjectNode,
    SenderIsProposalAuthorNode,
)
from vultron.core.behaviors.sender_entitlement.case_owner import (
    SenderIsCaseOwnerNode,
)
from vultron.core.behaviors.sender_entitlement.invitee import (
    SenderIsInviteeNode,
    SenderIsRoleOfferTargetNode,
)
from vultron.core.behaviors.sender_entitlement.membership import (
    SenderClosureNotRecordedNode,
    SenderIsActiveParticipantNode,
    SenderIsParticipantNode,
)

#: Each moved node, built from configuration alone, and the act keys it
#: cannot run without.
_NODES: list[tuple[NodeBuild, tuple[ActKey, ...]]] = [
    (ActivityNotYetLedgeredNode, (CASE_ID,)),
    (ReplicaRefusalNode, (CASE_ID,)),
    (
        ClearRefusedAssertionNode,
        (CASE_ID, REFUSED_ACTIVITY_ID, SENDER_ID),
    ),
    (
        ResumeOutboundSequenceNode,
        (CASE_ID, SENDER_ID, EXPECTED_SENDER_SEQUENCE),
    ),
    (SenderIsExpectedCaseCreatorNode, (SENDER_ID, CASE_ID)),
    (SenderIsOfferAddresseeNode, (SENDER_ID,)),
    (SenderIsProposalAddresseeNode, (SENDER_ID, REPORT_ID)),
    (SenderIsNoteAuthorNode, (NOTE_ID, SENDER_ID, CASE_ID)),
    (SenderIsParticipantRecordSubjectNode, (PARTICIPANT_ID, SENDER_ID)),
    (SenderIsProposalAuthorNode, (PROPOSAL_ID, SENDER_ID)),
    (SenderIsCaseOwnerNode, (SENDER_ID,)),
    (SenderIsInviteeNode, (SENDER_ID,)),
    (SenderIsRoleOfferTargetNode, (SENDER_ID, CASE_ID)),
    (SenderClosureNotRecordedNode, (CASE_ID, SENDER_ID)),
    (SenderIsActiveParticipantNode, (SENDER_ID,)),
    (SenderIsParticipantNode, (SENDER_ID,)),
]

_CASES = unseeded_key_cases(_NODES)


def test_every_listed_key_is_a_port_of_its_node() -> None:
    for build, keys in _NODES:
        remaps = type(build())._domain_port_remappings()  # type: ignore[attr-defined]
        assert {k.path for k in keys} <= set(remaps.values()), build


@pytest.mark.spec("BTND-01-008")
@pytest.mark.parametrize(
    ("build", "key", "keys"), _CASES, ids=unseeded_key_case_ids(_CASES)
)
def test_a_node_ticked_without_its_key_seeded_raises_naming_the_key(
    build: NodeBuild, key: ActKey, keys: tuple[ActKey, ...]
) -> None:
    with restored_act_keys():
        assert_unseeded_key_raises(build, key, keys)
