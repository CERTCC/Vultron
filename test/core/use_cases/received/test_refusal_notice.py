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

"""The refusal notice end to end: emitted by the factory, read by the sender.

A precondition guard at the CASE_MANAGER that refuses an assertion owes the
asserting participant one ``Reject`` of it (CLP-02-005, CLP-05-001,
ADR-0141).  The tree here composes the refusal notice as ``refusal_effects``
of :func:`create_receive_activity_tree` the way an adopting tree does, over
the received embargo answer the ledger network already builds, and checks
when the notice is sent and when it is not (CLP-10-022).  The participant's
side runs the real use case on the delivered notice (CLP-06-006).
"""

import json
from typing import Any, cast

import pytest
from py_trees.common import Status

from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.adapters.outbox_sealed_body import (
    dump_outbound_body,
    read_sealed_body_dict,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.refusal_notice import (
    EmitRefusalNoticeNode,
    refusal_notice,
)
from vultron.core.behaviors.case.nodes.refusal_stage import (
    PreconditionGuardStage,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    ReceivedActivityTree,
    create_receive_activity_tree,
)
from vultron.core.behaviors.embargo.nodes.answer_repeat import (
    case_manager_admits_embargo_answer_guard,
)
from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.behaviors.sender_check_context import SenderCheckContext
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.events.fault import RefusalNoticeReceivedEvent
from vultron.core.models.pending_assertion import (
    get_pending_assertion_store,
    record_pending_assertion,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.use_cases.received._bt_verdict import find_node
from vultron.core.use_cases.received.fault import RefusalNoticeReceivedUseCase
from vultron.errors import VultronWiringError
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import em_accept_embargo_activity
from vultron.wire.as2.parser import parse_activity

from ._ledger_network import BYSTANDER, MANAGER, OWNER, LedgerNetwork
from .test_embargo_relay_replay import _propose

STRANGER = "https://example.org/users/stranger"
REFUSAL = "the asserted precondition does not hold"
ACCEPT_EVENT = "accept_invite_to_embargo_on_case"


class _Refuses(DataLayerConditionWithPorts):
    """A precondition guard that refuses every delivery with :data:`REFUSAL`."""

    def update(self) -> Status:
        self.feedback_message = REFUSAL
        return Status.FAILURE


def _network(tag: str) -> tuple[LedgerNetwork, str, str]:
    """A network where BYSTANDER holds a relayed Invite to a revision.

    Returns ``(net, embargo_id, invite_id)``.
    """
    net = LedgerNetwork(f"https://example.org/cases/refusal-notice-{tag}")
    embargo_id = _propose(net, tag, 90)
    net.deliver(MANAGER, to=BYSTANDER, type_="Invite")
    invite_id = net.queued(MANAGER, to=BYSTANDER, type_="Invite")[-1].id_
    return net, embargo_id, invite_id


def _accept_event(
    net: LedgerNetwork,
    invite_id: str,
    *,
    sender: str = BYSTANDER,
    tag: str = "1",
    receiver: str = MANAGER,
) -> Any:
    """*sender*'s Accept of *invite_id* under a fresh id, as *receiver* routes it."""
    proposal = cast(Any, net.stores[BYSTANDER].read(invite_id))
    activity = em_accept_embargo_activity(
        proposal,
        context=net.case_id,
        actor=sender,
        to=sorted({MANAGER, receiver}),
        id_=f"{sender}/answers/{tag}",
    )
    body = json.loads(dump_outbound_body(activity))
    return extract_event(parse_activity(body)).model_copy(
        update={"receiving_actor_id": receiver}
    )


def _tree(
    case_id: str, sender: str, guard: Any = None
) -> ReceivedActivityTree:
    return create_receive_activity_tree(
        name="RefusalNoticeTestBT",
        case_id=case_id,
        sender_rule=SenderRule.in_case(SenderEntitlementKind.PARTICIPANT),
        sender_context=SenderCheckContext(sender_id=sender, case_id=case_id),
        precondition_guards=[
            guard if guard is not None else _Refuses(name="Refuses")
        ],
        refusal_effects=[refusal_notice(case_id)],
    )


def _run(net: LedgerNetwork, receiver: str, tree: Any, event: Any) -> Any:
    dl = net.stores[receiver]
    return BTBridge(
        datalayer=dl,
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute_with_setup(tree=tree, actor_id=receiver, activity=event)


def _notices(net: LedgerNetwork, sender: str, to: str) -> list[Any]:
    return list(net.queued(sender, to=to, type_="Reject"))


@pytest.mark.spec("CLP-05-001")
@pytest.mark.spec("CLP-02-005")
@pytest.mark.spec("CLP-10-022")
def test_a_precondition_refusal_queues_one_refusal_notice():
    net, _, invite_id = _network("queued")
    event = _accept_event(net, invite_id)
    tree = _tree(net.case_id, BYSTANDER)

    result = _run(net, MANAGER, tree, event)

    assert result.status == Status.FAILURE
    assert BTBridge.get_failure_reason(tree) == REFUSAL
    notices = _notices(net, MANAGER, BYSTANDER)
    assert len(notices) == 1
    notice_id = notices[0].id_
    assert notice_id == derived_activity_id(
        "refusal-notice", MANAGER, event.activity_id
    )
    body = read_sealed_body_dict(net.stores[MANAGER], notice_id)
    assert body is not None
    assert body["type"] == "Reject"
    assert body["actor"] == MANAGER
    assert body["to"] == [BYSTANDER]
    assert body["inReplyTo"] == event.activity_id
    assert body["summary"] == REFUSAL
    assert body["context"] == net.case_id
    assert body["object"]["id"] == event.activity_id
    assert body["object"]["type"] == "Accept"


@pytest.mark.spec("CLP-05-001")
@pytest.mark.spec("CLP-05-002")
def test_a_refusal_notice_commits_nothing():
    net, _, invite_id = _network("uncommitted")
    before = len(net.stores[MANAGER].list_objects("CaseLedgerEntry"))

    _run(
        net,
        MANAGER,
        _tree(net.case_id, BYSTANDER),
        _accept_event(net, invite_id),
    )

    assert len(net.stores[MANAGER].list_objects("CaseLedgerEntry")) == before


@pytest.mark.spec("CLP-05-001")
@pytest.mark.spec("CLP-02-005")
def test_a_sender_guard_refusal_queues_no_notice():
    net, _, invite_id = _network("sender-guard")
    event = _accept_event(net, invite_id, sender=STRANGER)
    tree = _tree(net.case_id, STRANGER)

    result = _run(net, MANAGER, tree, event)

    assert result.status == Status.FAILURE
    assert _notices(net, MANAGER, STRANGER) == []
    stage = find_node(tree, PreconditionGuardStage)
    assert stage is not None and stage.status == Status.INVALID


@pytest.mark.spec("CLP-05-001")
@pytest.mark.spec("CLP-10-022")
def test_a_skipped_repeat_answer_under_a_new_id_queues_no_notice():
    """A repeat answer is ``SKIPPED``, not refused, so no notice (AC-4)."""
    net, embargo_id, invite_id = _network("repeat")
    first = net.receive_event(MANAGER, _accept_event(net, invite_id, tag="1"))
    assert first.disposition is HandlerDisposition.APPLIED, first.reason
    guard = case_manager_admits_embargo_answer_guard(
        net.case_id, embargo_id, BYSTANDER, EmbargoConsentState.AGREED
    )
    tree = _tree(net.case_id, BYSTANDER, guard)

    result = _run(net, MANAGER, tree, _accept_event(net, invite_id, tag="2"))

    assert result.status == Status.FAILURE
    stage = find_node(tree, PreconditionGuardStage)
    assert stage is not None and stage.skipped_as_repeat
    assert _notices(net, MANAGER, BYSTANDER) == []


@pytest.mark.spec("CLP-05-001")
@pytest.mark.spec("CLP-10-022")
def test_a_redelivery_queues_no_second_notice():
    net, _, invite_id = _network("redelivery")
    event = _accept_event(net, invite_id)
    _run(net, MANAGER, _tree(net.case_id, BYSTANDER), event)
    first = _notices(net, MANAGER, BYSTANDER)
    assert len(first) == 1
    tree = _tree(net.case_id, BYSTANDER)

    _run(net, MANAGER, tree, event)

    stage = find_node(tree, PreconditionGuardStage)
    assert stage is not None and stage.skipped_as_redelivery
    emit = find_node(tree, EmitRefusalNoticeNode)
    assert emit is not None and emit.status == Status.INVALID
    assert _notices(net, MANAGER, BYSTANDER) == first


@pytest.mark.spec("CLP-05-001")
@pytest.mark.spec("CLP-10-022")
def test_a_replica_queues_no_notice():
    net, _, invite_id = _network("replica")
    event = _accept_event(net, invite_id, sender=OWNER, receiver=BYSTANDER)
    tree = _tree(net.case_id, OWNER)

    result = _run(net, BYSTANDER, tree, event)

    assert result.status == Status.FAILURE
    stage = find_node(tree, PreconditionGuardStage)
    assert stage is not None and stage.refusal_reason == REFUSAL
    emit = find_node(tree, EmitRefusalNoticeNode)
    assert emit is not None and emit.status == Status.INVALID
    assert _notices(net, BYSTANDER, OWNER) == []


def test_a_notice_outside_a_refusal_stage_fails_and_queues_nothing():
    net, _, invite_id = _network("loose")
    node = refusal_notice(net.case_id)

    result = _run(net, MANAGER, node, _accept_event(net, invite_id))

    assert result.status == Status.FAILURE
    assert "not a refusal effect" in node.feedback_message
    assert _notices(net, MANAGER, BYSTANDER) == []


def test_a_notice_with_no_received_activity_is_a_wiring_fault():
    node = refusal_notice("https://example.org/cases/1")

    with pytest.raises(VultronWiringError, match="no received activity"):
        node._call_factory()


# ---------------------------------------------------------------------------
# The participant's side (CLP-06-006)
# ---------------------------------------------------------------------------


def _refused_and_delivered(tag: str, *, pending: bool) -> tuple[Any, Any]:
    """BYSTANDER's Accept is refused; the notice is delivered back to it.

    Returns ``(net_and_event, verdict)``.
    """
    net, _, invite_id = _network(tag)
    event = _accept_event(net, invite_id)
    if pending:
        record_pending_assertion(
            BYSTANDER, net.case_id, ACCEPT_EVENT, event.activity_id
        )
    _run(net, MANAGER, _tree(net.case_id, BYSTANDER), event)
    verdicts = net.deliver(MANAGER, to=BYSTANDER, type_="Reject")
    assert len(verdicts) == 1
    return (net, event), verdicts[0][1]


@pytest.mark.spec("CLP-06-006")
@pytest.mark.spec("CLP-05-001")
def test_the_participant_closes_its_pending_assertion(caplog):
    with caplog.at_level("WARNING"):
        (net, event), verdict = _refused_and_delivered("closed", pending=True)

    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    assert not get_pending_assertion_store(BYSTANDER).is_suppressed(
        net.case_id, ACCEPT_EVENT, event.activity_id
    )
    warnings = [
        r.getMessage() for r in caplog.records if r.levelname == "WARNING"
    ]
    assert any(
        event.activity_id in m and BYSTANDER in m and REFUSAL in m
        for m in warnings
    ), warnings


@pytest.mark.spec("CLP-05-001")
def test_the_participant_writes_no_case_state_and_sends_nothing():
    net, _, invite_id = _network("no-writes")
    event = _accept_event(net, invite_id)
    _run(net, MANAGER, _tree(net.case_id, BYSTANDER), event)
    dl = net.stores[BYSTANDER]
    case_before = net.case(BYSTANDER).model_dump(exclude={"updated"})
    outbox_before = list(dl.outbox_list())
    entries_before = len(dl.list_objects("CaseLedgerEntry"))

    verdicts = net.deliver(MANAGER, to=BYSTANDER, type_="Reject")

    assert verdicts[0][1].disposition is HandlerDisposition.SKIPPED
    assert net.case(BYSTANDER).model_dump(exclude={"updated"}) == case_before
    assert list(dl.outbox_list()) == outbox_before
    assert len(dl.list_objects("CaseLedgerEntry")) == entries_before


@pytest.mark.spec("HP-01-006")
def test_a_notice_from_anyone_but_the_case_manager_is_refused():
    net, _, invite_id = _network("forged")
    event = _accept_event(net, invite_id)
    _run(net, MANAGER, _tree(net.case_id, BYSTANDER), event)
    notice_id = _notices(net, MANAGER, BYSTANDER)[0].id_
    body = cast(
        dict[str, Any], read_sealed_body_dict(net.stores[MANAGER], notice_id)
    )
    forged = {**body, "actor": OWNER, "id": f"{OWNER}/forged-notice"}
    record_pending_assertion(
        BYSTANDER, net.case_id, ACCEPT_EVENT, event.activity_id
    )

    verdict = net.receive(BYSTANDER, forged)

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert get_pending_assertion_store(BYSTANDER).is_suppressed(
        net.case_id, ACCEPT_EVENT, event.activity_id
    )


def test_the_notice_routes_to_the_refusal_notice_semantics():
    net, _, invite_id = _network("routing")
    event = _accept_event(net, invite_id)
    _run(net, MANAGER, _tree(net.case_id, BYSTANDER), event)
    notice_id = _notices(net, MANAGER, BYSTANDER)[0].id_
    body = read_sealed_body_dict(net.stores[MANAGER], notice_id)

    routed = extract_event(parse_activity(cast(dict[str, Any], body)))
    assert isinstance(routed, RefusalNoticeReceivedEvent)

    assert routed.semantic_type is MessageSemantics.REFUSAL_NOTICE
    assert routed.refused_activity_id == event.activity_id
    assert routed.case_id == net.case_id
    assert routed.reason == REFUSAL


@pytest.mark.spec("HP-01-006")
def test_a_notice_naming_no_case_is_refused():
    net, _, invite_id = _network("caseless")
    event = _accept_event(net, invite_id)
    _run(net, MANAGER, _tree(net.case_id, BYSTANDER), event)
    notice_id = _notices(net, MANAGER, BYSTANDER)[0].id_
    body = cast(
        dict[str, Any], read_sealed_body_dict(net.stores[MANAGER], notice_id)
    )
    caseless = {k: v for k, v in body.items() if k != "context"}
    caseless["object"] = {
        k: v for k, v in body["object"].items() if k != "context"
    }
    routed = extract_event(parse_activity(caseless)).model_copy(
        update={"receiving_actor_id": BYSTANDER}
    )
    assert isinstance(routed, RefusalNoticeReceivedEvent)
    assert routed.case_id is None

    verdict = RefusalNoticeReceivedUseCase(
        net.stores[BYSTANDER], routed
    ).execute()

    assert verdict.disposition is HandlerDisposition.REFUSED
