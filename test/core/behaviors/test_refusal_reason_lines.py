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

"""A guard's refusal reason is a DEBUG fact; only the runner logs REFUSED.

Each guard family that fails through ``fail_with_reason`` is ticked, or its
refusal helper called, with every record captured from DEBUG up.  Its line
keeps the facts and drops the ``REFUSED (IDs)`` group, while the
``feedback_message`` the handler reports keeps it (SL-03-003, SL-03-004,
#6477).  The inbox stage line that repeats a reason is pinned here too.
"""

import logging
from collections.abc import Callable

import py_trees
import pytest
from py_trees.common import Status

from test.support.act_clock import ACT_AT
from test.support.act_runner import run_tree
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.activity_context import (
    ActivityContextMatchesObjectNode,
)
from vultron.core.behaviors.case.nodes.carried_object_case import (
    CarriedObjectInTargetCaseNode,
)
from vultron.core.behaviors.case.nodes.case_participant_received import (
    MoveNamesCaseParticipantNode,
)
from vultron.core.behaviors.case.nodes.full_case_invite import (
    CheckFullCaseReplyNode,
)
from vultron.core.behaviors.case.nodes.ownership_offer_guard import (
    OwnershipProposalAdmissibleNode,
)
from vultron.core.behaviors.case.nodes.ownership_reply_guard import (
    OwnershipOfferOpenNode,
)
from vultron.core.behaviors.case.nodes.refusal_notice import (
    ClearRefusedAssertionNode,
    EmitRefusalNoticeNode,
)
from vultron.core.behaviors.case.nodes.role_offer_guard import (
    RoleOfferAdmissibleNode,
    RoleOfferOpenNode,
)
from vultron.core.behaviors.case.nodes.stub_invite_lifetime import (
    StubInviteAnswerableNode,
)
from vultron.core.behaviors.case.nodes.suggest_actor.admission import (
    refusal_status,
)
from vultron.core.behaviors.embargo.nodes.activation_commit import (
    CommitAndApplyEmbargoActivationNode,
)
from vultron.core.behaviors.embargo.nodes.ending_notice_replica import (
    ApplyAnnouncedEmbargoRevisionNode,
)
from vultron.core.behaviors.embargo.nodes.teardown import (
    ClearActiveEmbargoNode,
)
from vultron.core.behaviors.embargo.nodes.termination_commit import (
    CommitAndApplyEmbargoTerminationNode,
)
from vultron.core.behaviors.inbox.models import InboxOutcomeStatus
from vultron.core.behaviors.inbox.nodes.pipeline import ParsePayloadNode
from vultron.core.behaviors.node_logger import fail_with_reason, node_logger
from vultron.core.behaviors.status.nodes.target_participant import (
    TargetParticipantInCaseNode,
)
from vultron.core.models.refusal_wording import carries_refusal_group
from vultron.errors import VultronError

_CASE = "https://example.org/cases/refusal-lines"
_OTHER = "https://example.org/cases/other"


def _bare[N: py_trees.behaviour.Behaviour](cls: type[N], **attrs: object) -> N:
    """An instance of *cls* carrying only what its refusal helper reads."""
    node = cls.__new__(cls)
    py_trees.behaviour.Behaviour.__init__(node, name=cls.__name__)
    for key, value in attrs.items():
        setattr(node, key, value)
    return node


def _with_store[N: py_trees.behaviour.Behaviour](node: N) -> N:
    node.datalayer = SqliteDataLayer(  # type: ignore[attr-defined]
        "sqlite:///:memory:", actor_id="https://example.org/actors/r"
    )
    return node


#: (label, a callable that makes one node refuse and returns it).
_REFUSALS: list[tuple[str, Callable[[], py_trees.behaviour.Behaviour]]] = []


def _case(label: str):
    def register(make: Callable[[], py_trees.behaviour.Behaviour]):
        _REFUSALS.append((label, make))
        return make

    return register


@_case("activity-context")
def _activity_context() -> py_trees.behaviour.Behaviour:
    node = ActivityContextMatchesObjectNode(_CASE, _OTHER, "urn:obj")
    assert node.update() is Status.FAILURE
    return node


@_case("carried-object")
def _carried_object() -> py_trees.behaviour.Behaviour:
    node = _with_store(
        CarriedObjectInTargetCaseNode("urn:obj", object(), _CASE)
    )
    assert node.update() is Status.FAILURE
    return node


@_case("target-participant")
def _target_participant() -> py_trees.behaviour.Behaviour:
    node = _with_store(TargetParticipantInCaseNode("urn:participant", _CASE))
    assert node.update() is Status.FAILURE
    return node


@_case("participant-move")
def _participant_move() -> py_trees.behaviour.Behaviour:
    node = _bare(MoveNamesCaseParticipantNode, move="removal")
    assert node._refuse("p is not on the roster") is Status.FAILURE
    return node


@_case("role-offer-admissible")
def _role_offer_admissible() -> py_trees.behaviour.Behaviour:
    node = _bare(RoleOfferAdmissibleNode, offer_id="urn:offer")
    assert node._refuse("names no role") is Status.FAILURE
    return node


@_case("role-offer-open")
def _role_offer_open() -> py_trees.behaviour.Behaviour:
    node = _bare(RoleOfferOpenNode)
    assert node._refuse("the Offer is closed") is Status.FAILURE
    return node


@_case("ownership-offer")
def _ownership_offer() -> py_trees.behaviour.Behaviour:
    node = _bare(OwnershipProposalAdmissibleNode)
    assert node._refuse("no transferee") is Status.FAILURE
    return node


@_case("ownership-reply")
def _ownership_reply() -> py_trees.behaviour.Behaviour:
    node = _bare(OwnershipOfferOpenNode)
    assert node._refuse("answered", "CM-21-022") is Status.FAILURE
    return node


@_case("stub-invite")
def _stub_invite() -> py_trees.behaviour.Behaviour:
    node = _bare(StubInviteAnswerableNode)
    assert node._refuse("replaced — REFUSED (CM-11-050)") is Status.FAILURE
    return node


@_case("suggest-actor")
def _suggest_actor() -> py_trees.behaviour.Behaviour:
    node = _bare(RoleOfferOpenNode)
    status = refusal_status(node, "not invitable — REFUSED (CM-31-013)")  # type: ignore[arg-type]
    assert status is Status.FAILURE
    return node


@_case("full-case-reply")
def _full_case_reply() -> py_trees.behaviour.Behaviour:
    node = _bare(CheckFullCaseReplyNode)
    assert node._refuse("stale — REFUSED (CM-11-020)") is Status.FAILURE
    return node


_REGISTER_REFUSAL = VultronError("the register refuses — REFUSED (EP-08-004)")


@_case("embargo-activation-commit")
def _activation_commit() -> py_trees.behaviour.Behaviour:
    node = _bare(CommitAndApplyEmbargoActivationNode, _result_out={})
    assert node._refuse(_REGISTER_REFUSAL) is Status.FAILURE
    return node


@_case("embargo-termination-commit")
def _termination_commit() -> py_trees.behaviour.Behaviour:
    node = _bare(CommitAndApplyEmbargoTerminationNode, _result_out={})
    assert node._refuse(_REGISTER_REFUSAL) is Status.FAILURE
    return node


@_case("embargo-teardown")
def _teardown() -> py_trees.behaviour.Behaviour:
    node = _bare(ClearActiveEmbargoNode)
    assert node._refuse(_REGISTER_REFUSAL) is Status.FAILURE
    return node


@_case("embargo-revision-replica")
def _revision_replica() -> py_trees.behaviour.Behaviour:
    node = _bare(ApplyAnnouncedEmbargoRevisionNode)
    assert node._refuse(_REGISTER_REFUSAL) is Status.FAILURE
    return node


@_case("fail-with-reason")
def _plain() -> py_trees.behaviour.Behaviour:
    node = py_trees.behaviours.Success(name="Probe")
    assert fail_with_reason(node, "x — REFUSED (HP-01-006)") is Status.FAILURE
    return node


@pytest.mark.spec("SL-03-003", "SL-03-004", "BT-13-001")
@pytest.mark.parametrize(
    "make",
    [make for _, make in _REFUSALS],
    ids=[label for label, _ in _REFUSALS],
)
def test_a_guards_refusal_is_one_debug_fact_without_the_group(
    caplog: pytest.LogCaptureFixture,
    make: Callable[[], py_trees.behaviour.Behaviour],
) -> None:
    with caplog.at_level(logging.DEBUG):
        node = make()
    assert carries_refusal_group(node.feedback_message), node.feedback_message
    lines = [
        r
        for r in caplog.records
        if r.funcName == fail_with_reason.__name__
        and r.name.endswith(type(node).__name__)
    ]
    assert [r.levelno for r in lines] == [logging.DEBUG]
    assert node.name in lines[0].getMessage()
    assert not [
        r.getMessage()
        for r in caplog.records
        if carries_refusal_group(r.getMessage())
    ]


@pytest.mark.spec("SL-03-004")
def test_an_inbox_stage_outcome_line_drops_the_group(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An inbox stage repeats a rejected outcome's reason at INFO; the
    received runner already logged the refusal, so the line keeps the facts
    without the group."""
    node = ParsePayloadNode.__new__(ParsePayloadNode)
    py_trees.behaviour.Behaviour.__init__(node, name="ParsePayload")
    node.logger = node_logger(node)  # type: ignore[assignment]
    node._set_output = lambda *_: None  # type: ignore[method-assign]
    with caplog.at_level(logging.DEBUG):
        status = node._record_outcome(
            InboxOutcomeStatus.REJECTED, "not yours — REFUSED (HP-01-006)"
        )
    assert status is Status.FAILURE
    assert node.feedback_message == "not yours — REFUSED (HP-01-006)"
    messages = [r.getMessage() for r in caplog.records]
    assert any("not yours" in m for m in messages), messages
    assert not [m for m in messages if carries_refusal_group(m)]


@pytest.mark.spec("SL-03-004", "CLP-05-001")
def test_the_sent_refusal_notice_line_drops_the_group(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The notice going out is logged with the facts of the refusal it
    carries, not with the group the runner's line already carried."""
    node = _bare(
        EmitRefusalNoticeNode,
        actor_id="urn:manager",
        _asserter="urn:asserter",
        _refused_id="urn:refused",
        _case_id=_CASE,
        _reason="stale — REFUSED (HP-01-006)",
    )
    node.logger = node_logger(node)  # type: ignore[assignment]
    with caplog.at_level(logging.DEBUG):
        node._on_success("urn:notice", "{}")
    messages = [r.getMessage() for r in caplog.records]
    assert any("stale" in m for m in messages), messages
    assert not [m for m in messages if carries_refusal_group(m)]


@pytest.mark.spec("SL-03-004", "CLP-06-006")
def test_the_received_refusal_notice_line_drops_the_group(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The asserter logs the CASE_MANAGER's refusal as a fact the notice
    carried; that refusal is the CASE_MANAGER's runner line, not this one."""
    node = ClearRefusedAssertionNode(
        case_id=_CASE,
        refused_activity_id="urn:refused",
        reason="stale — REFUSED (HP-01-006)",
        sender_id="urn:manager",
    )
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id="urn:asserter")
    with caplog.at_level(logging.DEBUG):
        result = run_tree(
            BTBridge(datalayer=dl), node, actor_id="urn:asserter", at=ACT_AT
        )
    assert result.status == Status.SUCCESS
    messages = [r.getMessage() for r in caplog.records]
    assert any("stale" in m and "refused activity" in m for m in messages)
    assert not [m for m in messages if carries_refusal_group(m)]
