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

"""Every embargo received tree answers its precondition refusals (#4755).

When a precondition guard at the CASE_MANAGER refuses an embargo message, the
CASE_MANAGER sends the sender the refusal notice: one ``Reject`` of the
refused activity, inline, threaded by ``inReplyTo``, addressed to the sender
alone and carrying the guard's reason in ``summary`` (CLP-02-005,
CLP-05-001).  A repeat reported ``SKIPPED`` and a delivery a diversion
answers get none (CM-13-005, CLP-10-026).  The withdrawal refusals and the
signatory's Reject of the embargo in force are driven in
``test_embargo_withdrawal.py``.
"""

import json
from typing import Any, cast

import pytest

from test.support.refusal_notice import (
    assert_no_refusal_notice,
    assert_refusal_notice,
)
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.outbox_sealed_body import dump_outbound_body
from vultron.core.behaviors.embargo.nodes import (
    activation_commit,
    reject_proposed,
)
from vultron.core.behaviors.embargo.nodes.answer_record import (
    EmbargoAnswerAppliesNode,
)
from vultron.core.behaviors.embargo.nodes.teardown import (
    TerminationIsTimelyNode,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.embargo_termination import (
    OtherCause,
    TerminationCause,
    ThreatSignal,
    ThreatSignalCause,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.pending_assertion import (
    get_pending_assertion_store,
    record_pending_assertion,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import TerminationReason
from vultron.errors import (
    INTERNAL_FAULTS,
    VultronBTInternalError,
    VultronError,
)
from vultron.wire.as2.factories import (
    em_propose_embargo_activity,
    remove_embargo_from_case_activity,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

from ._ledger_network import (
    BYSTANDER,
    MANAGER,
    OWNER,
    LedgerNetwork,
)
from .test_embargo_answer_idempotency import _answer_body, _invited
from .test_embargo_relay_replay import _owner_decides, _propose, _set_pxa

_ACCEPT = MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE.value
_INVITE = MessageSemantics.INVITE_TO_EMBARGO_ON_CASE.value


def _net(tag: str, **kwargs: Any) -> LedgerNetwork:
    return LedgerNetwork(
        f"https://example.org/cases/embargo-refusal-{tag}", **kwargs
    )


def _entries(net: LedgerNetwork) -> int:
    return len(net.stores[MANAGER].list_objects("CaseLedgerEntry"))


def _decided(net: LedgerNetwork, tag: str) -> tuple[str, str]:
    """A revision BYSTANDER was invited to, then rejected by the owner.

    Returns ``(embargo_id, invite_id)``; the revision is ``REJECTED``.
    """
    embargo_id, invite_id = _invited(net, BYSTANDER, tag)
    verdict = _owner_decides(net, embargo_id, accept=False)
    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    return embargo_id, invite_id


# ---------------------------------------------------------------------------
# Accept / Reject(Invite(EmbargoEvent))
# ---------------------------------------------------------------------------


@pytest.mark.spec("CLP-05-001")
@pytest.mark.spec("MSM-07-004")
def test_a_reject_of_a_decided_proposal_gets_the_notice():
    net = _net("reject-decided")
    _, invite_id = _decided(net, "reject-decided")
    before = _entries(net)
    body = _answer_body(net, BYSTANDER, invite_id, accept=False, tag="late")

    verdict = net.receive(MANAGER, body)

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert "neither the active embargo nor" in (verdict.reason or "")
    assert _entries(net) == before
    assert_refusal_notice(
        net.stores[MANAGER],
        manager=MANAGER,
        refused_id=body["id"],
        asserter=BYSTANDER,
        reason="neither the active embargo nor an open proposal",
        case_id=net.case_id,
    )


@pytest.mark.spec("CLP-05-001")
@pytest.mark.spec("CM-18-003")
@pytest.mark.spec("MSM-07-012")
def test_an_accept_of_a_decided_proposal_is_refused_with_the_notice():
    """A row for a final register entry takes no trigger (CM-18-003)."""
    net = _net("accept-decided")
    _, invite_id = _decided(net, "accept-decided")
    before = _entries(net)
    body = _answer_body(net, BYSTANDER, invite_id, accept=True, tag="late")

    verdict = net.receive(MANAGER, body)

    assert verdict.disposition is HandlerDisposition.REFUSED, verdict.reason
    assert _entries(net) == before
    assert_refusal_notice(
        net.stores[MANAGER],
        manager=MANAGER,
        refused_id=body["id"],
        asserter=BYSTANDER,
        reason="nothing to accept (CM-18-003)",
        case_id=net.case_id,
    )


@pytest.mark.spec("CLP-05-001")
@pytest.mark.spec("CM-18-003")
@pytest.mark.spec("MSM-07-012")
def test_an_accept_of_an_embargo_missing_from_the_register_gets_the_notice():
    net = _net("accept-missing")
    _, invite_id = _invited(net, BYSTANDER, "accept-missing")
    before = _entries(net)
    body = _answer_body(net, BYSTANDER, invite_id, accept=True, tag="forged")
    unknown = f"{net.case_id}/embargo_events/never-proposed"
    proposed = dict(body["object"]["object"])
    proposed["id"] = unknown
    body["object"] = {**body["object"], "object": proposed}

    verdict = net.receive(MANAGER, body)

    assert verdict.disposition is HandlerDisposition.REFUSED, verdict.reason
    assert _entries(net) == before
    assert_refusal_notice(
        net.stores[MANAGER],
        manager=MANAGER,
        refused_id=body["id"],
        asserter=BYSTANDER,
        reason=f"Embargo '{unknown}' is neither the active embargo",
        case_id=net.case_id,
    )


@pytest.mark.spec("CLP-05-001")
@pytest.mark.spec("CM-13-005")
@pytest.mark.parametrize("accept", [True, False], ids=["accept", "reject"])
def test_a_repeat_answer_under_a_new_id_gets_no_notice(accept: bool):
    """A repeat is ``SKIPPED``, not refused (CM-13-005, CLP-10-022)."""
    net = _net(f"repeat-{accept}")
    _, invite_id = _invited(net, BYSTANDER, f"repeat-{accept}")
    first = _answer_body(net, BYSTANDER, invite_id, accept=accept, tag="1")
    applied = net.receive(MANAGER, first)
    assert applied.disposition is HandlerDisposition.APPLIED, applied.reason
    again = _answer_body(net, BYSTANDER, invite_id, accept=accept, tag="2")

    verdict = net.receive(MANAGER, again)

    assert verdict.disposition is HandlerDisposition.SKIPPED, verdict.reason
    for body in (first, again):
        assert_no_refusal_notice(
            net.stores[MANAGER], manager=MANAGER, refused_id=body["id"]
        )


@pytest.mark.spec("CLP-10-026")
@pytest.mark.spec("EMB-02-004")
def test_an_accept_answered_with_a_reject_gets_no_notice():
    """The P/X/A diversion answers the Accept itself (CLP-10-026)."""
    net = _net("pxa-accept")
    _, invite_id = _invited(net, BYSTANDER, "pxa-accept")
    _set_pxa(net, MANAGER)
    body = _answer_body(net, BYSTANDER, invite_id, accept=True, tag="pxa")

    verdict = net.receive(MANAGER, body)

    assert verdict.disposition is HandlerDisposition.REFUSED
    (er,) = net.queued(MANAGER, to=BYSTANDER, type_="Reject")
    assert er.id_ != body["id"]
    assert_no_refusal_notice(
        net.stores[MANAGER], manager=MANAGER, refused_id=body["id"]
    )


# ---------------------------------------------------------------------------
# The case owner's decision: Accept / Reject(EmbargoEvent, target=Case)
# ---------------------------------------------------------------------------


def _owner_decision(
    net: LedgerNetwork, embargo_id: str, *, accept: bool
) -> tuple[Any, str]:
    """OWNER sends its decision on *embargo_id* to the CASE_MANAGER.

    Returns the verdict and the decision's id.
    """
    adapter = TriggerActivityAdapter(net.stores[OWNER])
    build = (
        adapter.activate_embargo if accept else adapter.reject_embargo_proposal
    )
    activity_id, sealed = build(
        embargo_id=embargo_id, case_id=net.case_id, actor=OWNER, to=[MANAGER]
    )
    return net.receive(MANAGER, json.loads(sealed)), activity_id


@pytest.mark.spec("CLP-05-001")
@pytest.mark.spec("MSM-07-008")
@pytest.mark.spec("MSM-07-009")
@pytest.mark.parametrize("accept", [True, False], ids=["activate", "reject"])
def test_an_owner_decision_on_no_open_proposal_gets_the_notice(accept: bool):
    """The embargo in force is no open proposal: nothing to decide."""
    net = _net(f"owner-no-proposal-{accept}")
    before = _entries(net)

    verdict, decision_id = _owner_decision(
        net, net.initial_embargo_id, accept=accept
    )

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert _entries(net) == before
    assert_refusal_notice(
        net.stores[MANAGER],
        manager=MANAGER,
        refused_id=decision_id,
        asserter=OWNER,
        reason="is not an open proposal",
        case_id=net.case_id,
    )


@pytest.mark.spec("CLP-05-001")
@pytest.mark.spec("EMB-02-002")
def test_an_owner_activation_with_pxa_set_gets_the_notice():
    """EMB-02-002: refused before the commit; the only answer is the notice.

    The notice is a ``Reject`` of the refused activation, not a ``Reject`` of
    the Invite (CLP-05-001).
    """
    net = _net("owner-pxa")
    embargo_id = _propose(net, "owner-pxa", 90)
    net.deliver(MANAGER, to=OWNER, type_="Invite")
    _set_pxa(net, MANAGER)
    before = _entries(net)

    verdict, decision_id = _owner_decision(net, embargo_id, accept=True)

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert "EMB-02-002" in (verdict.reason or "")
    assert _entries(net) == before
    (notice,) = net.queued(MANAGER, to=OWNER, type_="Reject")
    assert (
        notice.id_
        == assert_refusal_notice(
            net.stores[MANAGER],
            manager=MANAGER,
            refused_id=decision_id,
            asserter=OWNER,
            reason="EMB-02-002",
            case_id=net.case_id,
        )["id"]
    )


# ---------------------------------------------------------------------------
# Invite(EmbargoEvent) and Remove(EmbargoEvent)
# ---------------------------------------------------------------------------


def _owner_remove(
    net: LedgerNetwork,
    *,
    reason: TerminationReason = TerminationReason.EARLY,
    cause: TerminationCause | None = None,
    tag: str = "remove",
) -> tuple[Any, str]:
    """OWNER asks the CASE_MANAGER to end the embargo in force."""
    embargo = net.stores[MANAGER].read(net.initial_embargo_id)
    assert isinstance(embargo, as_EmbargoEvent)
    activity = remove_embargo_from_case_activity(
        embargo,
        origin=net.case_id,
        context=net.case_id,
        actor=OWNER,
        to=[MANAGER],
        reason=reason,
        cause=cause,
        id_=f"{OWNER}/removes/{tag}",
    )
    body = activity.model_dump(mode="json", by_alias=True, exclude_none=True)
    return net.receive(MANAGER, body), body["id"]


@pytest.mark.spec("CLP-05-001")
@pytest.mark.spec("EMB-13-003")
def test_an_untimely_end_time_remove_gets_the_notice():
    """An END_TIME_REACHED claimed before the end time is refused."""
    net = _net("remove-untimely")
    before = _entries(net)

    verdict, remove_id = _owner_remove(
        net, reason=TerminationReason.END_TIME_REACHED
    )

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert net.case(MANAGER).em_state is EM.ACTIVE
    assert _entries(net) == before
    assert_refusal_notice(
        net.stores[MANAGER],
        manager=MANAGER,
        refused_id=remove_id,
        asserter=OWNER,
        reason="Refused termination",
        case_id=net.case_id,
    )


@pytest.mark.spec("CLP-05-001")
@pytest.mark.spec("EMB-13-005")
def test_an_owners_threat_signal_remove_gets_the_notice():
    """A threat signal comes as a case status update (EMB-13-005)."""
    net = _net("remove-threat")
    before = _entries(net)

    verdict, remove_id = _owner_remove(
        net, cause=ThreatSignalCause(signals=[ThreatSignal.X])
    )

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert _entries(net) == before
    assert_refusal_notice(
        net.stores[MANAGER],
        manager=MANAGER,
        refused_id=remove_id,
        asserter=OWNER,
        reason="case status update",
        case_id=net.case_id,
    )


def _bystander_proposes(net: LedgerNetwork, tag: str) -> dict[str, Any]:
    """BYSTANDER asks the CASE_MANAGER for new terms, its ask pending."""
    terms = as_EmbargoEvent(
        id_=f"{net.case_id}/embargo_events/{tag}",
        context=net.case_id,
        end_time=days_from_now_utc(90),
    )
    proposal = em_propose_embargo_activity(
        terms,
        context=net.case_id,
        actor=BYSTANDER,
        to=[MANAGER],
        id_=f"{BYSTANDER}/proposals/{tag}",
    )
    # The proposer keeps what it sent, and the trigger records its ask
    # (EP-09-008, SYNC-11-002).
    net.stores[BYSTANDER].create(proposal)
    record_pending_assertion(
        BYSTANDER, net.case_id, _INVITE, proposal.id_, subject_id=terms.id_
    )
    return cast(dict[str, Any], json.loads(dump_outbound_body(proposal)))


@pytest.mark.spec("CLP-05-001")
@pytest.mark.spec("EP-09-008")
@pytest.mark.spec("EP-09-001")
def test_an_invite_once_the_embargo_ended_gets_a_reject_of_it():
    """The notice of an Invite is a Reject(Invite), closing the ask."""
    net = _net("invite-exited")
    ended, _ = _owner_remove(net, cause=OtherCause(), tag="ends")
    assert ended.disposition is HandlerDisposition.APPLIED, ended.reason
    assert net.case(MANAGER).em_state is EM.EXITED
    before = _entries(net)
    body = _bystander_proposes(net, "too-late")

    verdict = net.receive(MANAGER, body)

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert _entries(net) == before
    notice = assert_refusal_notice(
        net.stores[MANAGER],
        manager=MANAGER,
        refused_id=body["id"],
        asserter=BYSTANDER,
        reason="admits no embargo proposal",
        case_id=net.case_id,
    )
    assert notice["object"]["type"] == "Invite"
    store = get_pending_assertion_store(BYSTANDER)
    assert store.is_suppressed(net.case_id, _INVITE, body["id"])

    delivered = net.deliver(MANAGER, to=BYSTANDER, type_="Reject")

    assert [type_ for type_, _ in delivered] == ["Reject"]
    assert not store.is_suppressed(net.case_id, _INVITE, body["id"])


@pytest.mark.spec("CLP-05-001")
def test_the_notice_of_a_refused_accept_closes_the_accepters_ask():
    """BYSTANDER reads the notice of its Accept as a refusal notice."""
    net = _net("accept-notice-read")
    _, invite_id = _decided(net, "accept-notice-read")
    body = _answer_body(net, BYSTANDER, invite_id, accept=True, tag="late")
    record_pending_assertion(
        BYSTANDER, net.case_id, _ACCEPT, body["id"], subject_id=invite_id
    )
    assert net.receive(MANAGER, body).disposition is (
        HandlerDisposition.REFUSED
    )

    ((type_, verdict),) = net.deliver(MANAGER, to=BYSTANDER, type_="Reject")

    assert type_ == "Reject"
    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    store = get_pending_assertion_store(BYSTANDER)
    assert not store.is_suppressed(net.case_id, _ACCEPT, body["id"])


# ---------------------------------------------------------------------------
# The CASE_MANAGER's Reject of the Invite to a participant's Accept (EMB-02-004)
# ---------------------------------------------------------------------------


@pytest.mark.spec("HP-01-006")
@pytest.mark.spec("EP-09-014")
@pytest.mark.spec("EMB-02-004")
@pytest.mark.spec("EP-09-017")
@pytest.mark.spec("EP-09-019")
def test_the_case_managers_reject_to_an_accept_closes_the_accepters_ask():
    """The ``Reject`` of the Invite reaches the participant and closes its ask."""
    net = _net("pxa-er-read")
    _, invite_id = _invited(net, BYSTANDER, "pxa-er-read")
    _set_pxa(net, MANAGER)
    body = _answer_body(net, BYSTANDER, invite_id, accept=True, tag="pxa")
    record_pending_assertion(
        BYSTANDER, net.case_id, _ACCEPT, body["id"], subject_id=invite_id
    )
    assert net.receive(MANAGER, body).disposition is (
        HandlerDisposition.REFUSED
    )
    store = get_pending_assertion_store(BYSTANDER)
    assert store.is_suppressed(net.case_id, _ACCEPT, body["id"])

    ((type_, verdict),) = net.deliver(MANAGER, to=BYSTANDER, type_="Reject")

    assert type_ == "Reject"
    # The sender guard admits the CASE_MANAGER at a participant (HP-01-006);
    # the replica records no consent from the Reject, since only the
    # CASE_MANAGER records an answer, so the tree still reports a refusal.
    assert verdict.disposition is HandlerDisposition.REFUSED
    assert "not the invitee" not in (verdict.reason or ""), verdict.reason
    assert not store.is_suppressed(net.case_id, _ACCEPT, body["id"])


# ---------------------------------------------------------------------------
# An internal failure is not a refusal (ADR-0095)
# ---------------------------------------------------------------------------


def _raising(fault: type[VultronError]) -> Any:
    def _raise(*_args: Any, **_kwargs: Any) -> Any:
        raise fault("a fault of ours, not a refusal")

    return _raise


_FAULTS = pytest.mark.parametrize(
    "fault", INTERNAL_FAULTS, ids=lambda f: f.__name__
)


@pytest.mark.spec("CLP-05-001")
@_FAULTS
def test_an_internal_failure_in_a_remove_guard_gets_no_notice(
    monkeypatch, fault: type[VultronError]
):
    net = _net(f"internal-remove-{fault.__name__}")
    monkeypatch.setattr(
        TerminationIsTimelyNode, "_violations", _raising(fault)
    )

    # The handler reports it as an internal error (ADR-0095).
    with pytest.raises(VultronBTInternalError, match=fault.__name__):
        _owner_remove(net, cause=OtherCause())

    assert net.queued(MANAGER, to=OWNER, type_="Reject") == []


@pytest.mark.spec("CLP-05-001")
@_FAULTS
@pytest.mark.parametrize("accept", [True, False], ids=["activate", "reject"])
def test_an_internal_failure_in_an_owner_decision_guard_gets_no_notice(
    monkeypatch, accept: bool, fault: type[VultronError]
):
    net = _net(f"internal-owner-{accept}-{fault.__name__}")
    embargo_id = _propose(net, f"internal-owner-{accept}", 90)
    net.deliver(MANAGER, to=OWNER, type_="Invite")
    module = activation_commit if accept else reject_proposed
    monkeypatch.setattr(module, "trial_apply", _raising(fault))

    # The handler reports it as an internal error (ADR-0095).
    with pytest.raises(VultronBTInternalError, match=fault.__name__):
        _owner_decision(net, embargo_id, accept=accept)

    assert net.queued(MANAGER, to=OWNER, type_="Reject") == []


@pytest.mark.spec("CLP-05-001")
@_FAULTS
def test_an_internal_failure_in_an_answer_guard_gets_no_notice(
    monkeypatch, fault: type[VultronError]
):
    net = _net(f"internal-answer-{fault.__name__}")
    _, invite_id = _invited(net, BYSTANDER, f"internal-{fault.__name__}")
    monkeypatch.setattr(EmbargoAnswerAppliesNode, "_decide", _raising(fault))
    body = _answer_body(net, BYSTANDER, invite_id, accept=True, tag="fault")

    # The handler reports it as an internal error (ADR-0095).
    with pytest.raises(VultronBTInternalError, match=fault.__name__):
        net.receive(MANAGER, body)

    assert_no_refusal_notice(
        net.stores[MANAGER], manager=MANAGER, refused_id=body["id"]
    )
