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

"""The addressee door guard of a received tree (HP-01-005, CLP-10-010).

The guard admits the sender and every ``to`` recipient, refuses every other
store with a reason naming the receiver and the ``to``, and never reads
``cc`` (ADR-0109).  The factory places it between the post-close boundary
and the sender guard.
"""

from unittest.mock import MagicMock

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.addressee import (
    ActivityAddressedToReceiverNode,
    unaddressed_copy_reason,
)
from vultron.core.behaviors.case.nodes.post_close import (
    CaseOpenToExternalWritesNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.behaviors.sender_guard import SenderCheckContext

_CASE = "https://example.org/cases/addressee"
_MANAGER = "https://example.org/users/coord"
_SENDER = "https://example.org/users/vendor"
_OTHER = "https://example.org/users/vendor-a"
_BYSTANDER = "https://example.org/users/vendor-b"


def _event(to: list[str], cc: list[str] | None = None) -> MagicMock:
    event = MagicMock()
    event.actor_id = _SENDER
    event.activity_id = f"{_CASE}/activities/a2"
    event.activity.to = to
    event.activity.cc = cc or []
    return event


class TestUnaddressedCopyReason:
    @pytest.mark.spec("HP-01-005")
    @pytest.mark.parametrize(
        "receiver, to",
        [
            (_SENDER, []),
            (_MANAGER, [_MANAGER]),
            (_MANAGER, [f"{_MANAGER}/"]),
        ],
        ids=["sender", "to", "trailing-slash"],
    )
    def test_admits_the_sender_and_each_recipient(self, receiver, to):
        assert (
            unaddressed_copy_reason(receiver, _event(to), label="Test") is None
        )

    @pytest.mark.spec("HP-01-005")
    @pytest.mark.spec("OX-08-001")
    def test_a_cc_value_does_not_make_a_recipient(self):
        """Only ``to`` addresses a Vultron recipient (ADR-0109)."""
        reason = unaddressed_copy_reason(
            _MANAGER, _event([_OTHER], [_MANAGER]), label="Test"
        )
        assert reason is not None
        assert "cc=" not in reason

    @pytest.mark.spec("HP-01-005")
    def test_refuses_an_event_with_no_activity(self):
        event = _event([])
        event.activity = None
        reason = unaddressed_copy_reason(_BYSTANDER, event, label="Test")
        assert reason is not None
        assert "(to=[])" in reason

    @pytest.mark.spec("HP-01-005")
    def test_the_reason_names_the_receiver_the_activity_and_its_to(self):
        reason = unaddressed_copy_reason(
            _BYSTANDER, _event([_MANAGER]), label="Remove(EmbargoEvent)"
        )
        assert reason == (
            f"'{_BYSTANDER}' is neither the sender nor a recipient of"
            f" Remove(EmbargoEvent) '{_CASE}/activities/a2'"
            f" (to=['{_MANAGER}']); an unaddressed copy is refused (HP-01-005)"
        )


def _run(event: object, actor_id: str) -> ActivityAddressedToReceiverNode:
    node = ActivityAddressedToReceiverNode(label="Test")
    tree = py_trees.composites.Sequence(
        name="Probe", memory=False, children=[node]
    )
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
    BTBridge(datalayer=dl).execute_with_setup(
        tree=tree, actor_id=actor_id, activity=event
    )
    return node


class TestActivityAddressedToReceiverNode:
    @pytest.mark.spec("HP-01-005")
    def test_an_addressed_copy_passes(self):
        assert _run(_event([_MANAGER]), _MANAGER).status is Status.SUCCESS

    @pytest.mark.spec("HP-01-005")
    def test_an_unaddressed_copy_fails_and_warns(self, caplog):
        with caplog.at_level("WARNING"):
            node = _run(_event([_MANAGER]), _BYSTANDER)

        assert node.status is Status.FAILURE
        assert "neither the sender nor a recipient" in node.feedback_message
        assert any(
            r.levelname == "WARNING" and _BYSTANDER in r.getMessage()
            for r in caplog.records
        )


@pytest.mark.spec("CLP-10-010")
@pytest.mark.spec("HP-01-005")
def test_the_factory_places_it_between_post_close_and_the_sender_guard():
    tree = create_receive_activity_tree(
        name="Probe",
        case_id=_CASE,
        addressee_check="Test",
        sender_rule=SenderRule.in_case(SenderEntitlementKind.PARTICIPANT),
        sender_context=SenderCheckContext(sender_id=_SENDER, case_id=_CASE),
        precondition_guards=[],
    )

    assert isinstance(tree.children[1], CaseOpenToExternalWritesNode)
    assert isinstance(tree.children[2], ActivityAddressedToReceiverNode)
    assert tree.children[2].label == "Test"


def test_the_factory_places_no_addressee_check_unless_asked():
    tree = create_receive_activity_tree(
        name="Probe", case_id=_CASE, precondition_guards=[]
    )

    assert not [
        n
        for n in tree.iterate()
        if isinstance(n, ActivityAddressedToReceiverNode)
    ]
