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

"""The P/X/A refusal tree's shape with and without its ER (BT-17-008).

The ER is an emit in ``replica_effects``, admitted by the
``EMBARGO_INVITE_REFUSAL`` exemption; the tree that answers nothing carries
no emit, so it names no exemption (the factory refuses a stale one).
"""

import pytest

from vultron.core.behaviors.embargo.nodes.invite_answer import (
    SendEmbargoInviteAnswerNode,
)
from vultron.core.behaviors.embargo.refusal_tree import (
    EmbargoInviteNotYetRefusedNode,
    embargo_invite_refusal_tree,
)
from vultron.core.behaviors.emit_capable import EmitCapable

_CASE = "https://example.org/cases/refusal"
_INVITE = "https://example.org/activities/invite-refusal"


def _types(tree) -> list[type]:
    return [type(node) for node in tree.iterate()]


@pytest.mark.spec("BT-17-008")
def test_answering_tree_guards_then_sends_the_er_last() -> None:
    tree = embargo_invite_refusal_tree(_CASE, _INVITE, None, store_invite=True)

    children = list(tree.children)
    assert type(children[1]) is EmbargoInviteNotYetRefusedNode
    assert type(children[-1]) is SendEmbargoInviteAnswerNode
    assert children[-1].name == "SendEmbargoRefusalER"


@pytest.mark.spec("BT-17-008")
def test_silent_tree_has_no_guard_and_no_emit() -> None:
    tree = embargo_invite_refusal_tree(
        _CASE, _INVITE, None, store_invite=True, answer=False
    )

    types = _types(tree)
    assert EmbargoInviteNotYetRefusedNode not in types
    assert not [t for t in types if issubclass(t, EmitCapable)]
