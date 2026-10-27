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
"""The ownership-transfer Offer's binding deadline, read from the Offer itself.

CM-21-016: an Accept or Reject the CASE_MANAGER processes after the Offer's
``end_time`` is refused, with no role change and no answer entry.
CM-21-017: the CASE_MANAGER reads the expiry from the ledgered Offer's own
``end_time`` and its clock whenever it processes an Accept, Reject or Undo of
the Offer or a new proposal for the case.  The expiry is an observation, not
an act, so nothing is ledgered or sent for it (ADR-0152): an expired Offer is
closed (CM-21-014), a late reply is refused and a new proposal is admitted.

An Offer whose deadline has already passed when it is delivered stands in
for one that expired while it waited, so no test sleeps.
"""

from datetime import timedelta
from typing import Any

import pytest

from test.core.use_cases.received.actor.test_ownership import (
    _CASE_ACTOR_ID,
    _COORDINATOR_ID,
    _VENDOR2_ID,
    _VENDOR_ID,
    _accept,
    _announces,
    _owner,
    _owner_roles,
    _ownership_offer_harness,
    _reject,
    _semantic_types,
    _undo,
)
from test.support.ledger import commit_case_manager_closure
from vultron.core.models._helpers import now_utc
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.wire.as2.factories import (
    accept_case_ownership_transfer_activity,
)


def _past() -> Any:
    """A deadline that has already passed, at the clock's precision."""
    return now_utc() - timedelta(seconds=5)


def _future() -> Any:
    return now_utc() + timedelta(hours=1)


def _expired_offer(make_payload, case_id: str):
    """A CASE_MANAGER store holding one open Offer whose deadline passed."""
    dl, deliver, trigger_activity = _ownership_offer_harness(
        make_payload, case_id
    )
    disposition, offer = deliver(
        _COORDINATOR_ID, f"{case_id}/offer", end_time=_past()
    )
    assert disposition is HandlerDisposition.APPLIED
    return dl, deliver, trigger_activity, offer


def _trace(dl) -> tuple[list[str], list[str]]:
    """The CASE_MANAGER's ledger and outbox, to show a reply added neither."""
    return _semantic_types(dl), list(dl.outbox_list())


class TestLateAnswerIsRefused:
    """CM-21-016: the deadline binds both answers, and the expiry is not
    ledgered (CM-21-017, ADR-0152)."""

    @pytest.mark.spec("CM-21-016")
    @pytest.mark.spec("CM-21-017")
    def test_late_accept_moves_no_role_and_ledgers_nothing(self, make_payload):
        case_id = "https://example.org/cases/case_dl_accept"
        dl, _, _, offer = _expired_offer(make_payload, case_id)
        roles_before = _owner_roles(dl, case_id)
        before = _trace(dl)

        result = _accept(dl, make_payload, offer)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None and "CM-21-016" in result.reason
        assert "expired" in result.reason
        assert _owner(dl, case_id) == _VENDOR_ID
        assert _owner_roles(dl, case_id) == roles_before
        # Nothing records the expiry and nothing announces it.
        assert _semantic_types(dl) == before[0]
        assert _announces(dl, before[1]) == []

    @pytest.mark.spec("CM-21-016")
    def test_late_reject_is_refused_and_not_ledgered(self, make_payload):
        case_id = "https://example.org/cases/case_dl_reject"
        dl, _, _, offer = _expired_offer(make_payload, case_id)
        before = _trace(dl)

        result = _reject(dl, make_payload, offer)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None and "CM-21-016" in result.reason
        assert _semantic_types(dl) == before[0]
        assert _announces(dl, before[1]) == []

    @pytest.mark.spec("CM-21-016")
    @pytest.mark.spec("CM-21-017")
    def test_every_late_answer_is_refused_from_the_offers_end_time(
        self, make_payload
    ):
        """A second late answer is refused the same way: the deadline is read
        from the Offer each time, never from an entry an earlier one left."""
        case_id = "https://example.org/cases/case_dl_twice"
        dl, _, _, offer = _expired_offer(make_payload, case_id)
        before = _semantic_types(dl)

        first = _accept(dl, make_payload, offer)
        second = _reject(dl, make_payload, offer)

        assert first.disposition is HandlerDisposition.REFUSED
        assert second.disposition is HandlerDisposition.REFUSED
        assert second.reason is not None and "expired" in second.reason
        assert _semantic_types(dl) == before

    @pytest.mark.spec("CM-21-016")
    def test_answer_before_the_deadline_is_admitted(self, make_payload):
        """A deadline that has not passed changes nothing about the Accept."""
        case_id = "https://example.org/cases/case_dl_in_time"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, offer = deliver(
            _COORDINATOR_ID, f"{case_id}/offer", end_time=_future()
        )

        result = _accept(dl, make_payload, offer)

        assert result.disposition is HandlerDisposition.APPLIED
        assert _owner(dl, case_id) == _COORDINATOR_ID


class TestAnExpiredOfferIsClosed:
    """CM-21-014, CM-21-017: past its ``end_time`` the Offer is closed."""

    @pytest.mark.spec("CM-21-017")
    @pytest.mark.spec("CM-21-015")
    def test_withdrawal_of_an_expired_offer_is_refused(self, make_payload):
        """An expired Offer is closed, and a closed Offer cannot be withdrawn."""
        case_id = "https://example.org/cases/case_dl_undo"
        dl, _, _, offer = _expired_offer(make_payload, case_id)
        before = _trace(dl)

        result = _undo(dl, make_payload, offer)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None and "CM-21-017" in result.reason
        assert _semantic_types(dl) == before[0]
        assert _announces(dl, before[1]) == []

    @pytest.mark.spec("CM-21-017")
    @pytest.mark.spec("CM-21-014")
    def test_new_proposal_after_an_expired_offer_is_admitted(
        self, make_payload
    ):
        """The expired Offer does not block the next one, and nothing but the
        new proposal and its Offer is ledgered."""
        case_id = "https://example.org/cases/case_dl_reoffer"
        dl, deliver, trigger_activity, _ = _expired_offer(
            make_payload, case_id
        )
        before = _semantic_types(dl)

        second, _ = deliver(_VENDOR2_ID, f"{case_id}/offer2")

        assert second is HandlerDisposition.APPLIED
        assert _semantic_types(dl) == [
            *before,
            "propose_case_ownership_transfer",
            "offer_case_ownership_transfer",
        ]
        assert trigger_activity.offer_case_ownership_transfer.call_count == 2

    @pytest.mark.spec("CM-21-014")
    def test_new_proposal_while_an_offer_is_still_open_is_refused(
        self, make_payload
    ):
        """The deadline reading closes only an Offer that is past it."""
        case_id = "https://example.org/cases/case_dl_still_open"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        deliver(_COORDINATOR_ID, f"{case_id}/offer", end_time=_future())
        before = _semantic_types(dl)

        second, _ = deliver(_VENDOR2_ID, f"{case_id}/offer2")

        assert second is HandlerDisposition.REFUSED
        assert _semantic_types(dl) == before

    @pytest.mark.spec("CM-21-017")
    def test_an_offer_without_a_deadline_never_expires(self, make_payload):
        case_id = "https://example.org/cases/case_dl_none"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, offer = deliver(_COORDINATOR_ID, f"{case_id}/offer")

        result = _accept(dl, make_payload, offer)

        assert result.disposition is HandlerDisposition.APPLIED


class TestTheActivityIsNotTheEvidence:
    """CM-21-016: the reply names the Offer; the clock decides the deadline."""

    @pytest.mark.spec("CM-21-016")
    @pytest.mark.spec("CM-21-017")
    @pytest.mark.parametrize(
        "claimed_minutes",
        # Inside the ledger's clock-skew tolerance (CLP-14-006/007), and on
        # either side of each deadline below.
        [-4, 4],
        ids=["claims-before-deadline", "claims-after-deadline"],
    )
    @pytest.mark.parametrize(
        "deadline_seconds, expired",
        [(-5, True), (120, False)],
        ids=["deadline-passed", "deadline-ahead"],
    )
    def test_claimed_published_time_does_not_change_the_verdict(
        self, make_payload, claimed_minutes, deadline_seconds, expired
    ):
        """Whatever the Accept claims about when it was sent, its fate is
        decided from the CASE_MANAGER's clock and the Offer's end_time."""
        case_id = "https://example.org/cases/case_dl_published"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, offer = deliver(
            _COORDINATOR_ID,
            f"{case_id}/offer",
            end_time=now_utc() + timedelta(seconds=deadline_seconds),
        )
        accept = accept_case_ownership_transfer_activity(
            offer,
            actor=_COORDINATOR_ID,
            to=[_CASE_ACTOR_ID],
            published=now_utc() + timedelta(minutes=claimed_minutes),
        )

        result = _accept(dl, make_payload, offer, accept=accept)

        expected = (
            HandlerDisposition.REFUSED
            if expired
            else HandlerDisposition.APPLIED
        )
        assert result.disposition is expected, result.reason


@pytest.mark.spec("CM-21-005")
@pytest.mark.spec("CM-21-016")
def test_the_offer_carries_the_proposals_deadline(make_payload):
    """The proposal's inner Offer names the deadline, and the Offer the
    CASE_MANAGER makes, the one the transferee answers, carries it."""
    case_id = "https://example.org/cases/case_dl_forward"
    _, deliver, trigger_activity = _ownership_offer_harness(
        make_payload, case_id
    )
    deadline = _future()

    _, offer = deliver(_COORDINATOR_ID, f"{case_id}/offer", end_time=deadline)

    trigger_activity.offer_case_ownership_transfer.assert_called_once()
    _, kwargs = trigger_activity.offer_case_ownership_transfer.call_args
    assert kwargs["end_time"] == deadline
    assert offer.end_time == deadline


@pytest.mark.spec("HP-01-006")
@pytest.mark.spec("CM-21-016")
@pytest.mark.parametrize(
    "reply, sender",
    [
        # Not the transferee: an outsider, and the offerer itself.
        (_accept, "https://example.org/users/mallory"),
        (_reject, _VENDOR_ID),
        # Not the offerer: the transferee.
        (_undo, _COORDINATOR_ID),
    ],
)
def test_late_reply_from_a_non_party_ledgers_nothing(
    make_payload, reply, sender
):
    case_id = "https://example.org/cases/case_dl_non_party"
    dl, _, _, offer = _expired_offer(make_payload, case_id)
    before = _trace(dl)

    result = reply(dl, make_payload, offer, sender=sender)

    assert result.disposition is HandlerDisposition.REFUSED
    assert _semantic_types(dl) == before[0]
    assert _announces(dl, before[1]) == []
    assert _owner(dl, case_id) == _VENDOR_ID


@pytest.mark.spec("CM-23-013")
def test_a_late_reply_changes_nothing_once_the_case_is_fully_closed(
    make_payload,
):
    """After the CASE_MANAGER's own RM.CLOSED entry the door guard ends the
    tree before any guard reads the Offer."""
    case_id = "https://example.org/cases/case_dl_closed"
    dl, _, _, offer = _expired_offer(make_payload, case_id)
    commit_case_manager_closure(dl, case_id)
    before = _semantic_types(dl)

    result = _accept(dl, make_payload, offer)

    assert result.disposition is HandlerDisposition.REFUSED
    assert result.reason is not None and "CM-23-013" in result.reason
    assert _semantic_types(dl) == before


@pytest.mark.spec("CM-21-017")
@pytest.mark.spec("CLP-12-002")
def test_the_case_manager_authors_no_undo_of_an_offer():
    """No CASE_MANAGER entry withdraws an expired Offer, so a replica admits
    no CASE_MANAGER-authored ``Undo(Offer)`` (ADR-0152)."""
    from vultron.core.behaviors.sync.nodes.canonical_entry import (
        _CASE_AUTHORED_SIGNATURES,
    )

    assert ("Undo", "Offer") not in _CASE_AUTHORED_SIGNATURES


@pytest.mark.spec("CM-21-017")
@pytest.mark.spec("BT-17-001")
def test_a_replica_never_evaluates_the_offers_deadline(make_payload):
    """Run at the transferee's replica, the CASE_MANAGER's reply passes the
    open-Offer stage untouched: its CASE_MANAGER gate skips the deadline
    check, so a replica never judges the expiry (CM-21-017)."""
    from py_trees.common import Status

    from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
    from vultron.adapters.driven.sync_activity_adapter import (
        SyncActivityAdapter,
    )
    from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
    from vultron.core.behaviors.bridge import BTBridge
    from vultron.core.behaviors.case.nodes.ownership_offer_guard import (
        OwnershipOfferOpenNode,
    )
    from vultron.core.behaviors.case.ownership_transfer_tree import (
        create_accept_ownership_transfer_tree,
    )
    from vultron.core.use_cases.received._bt_verdict import find_node
    from vultron.core.use_cases.received.actor.ownership import (
        AcceptCaseOwnershipTransferReceivedUseCase,
    )

    case_id = "https://example.org/cases/case_dl_replica"
    dl, _, _, offer = _expired_offer(make_payload, case_id)
    # The transferee's replica: the case and its participant records, so the
    # CASE_MANAGER is known there (PCR-03-001).
    replica = SqliteDataLayer("sqlite:///:memory:", actor_id=_COORDINATOR_ID)
    for kind in ("VulnerabilityCase", "CaseParticipant"):
        for obj in dl.list_objects(kind):
            replica.create(obj)
    # A reply sent by the CASE_MANAGER, which a replica is entitled to
    # receive (PCR-03-001), after the Offer's end_time.
    reply = accept_case_ownership_transfer_activity(
        offer, actor=_CASE_ACTOR_ID, to=[_COORDINATOR_ID]
    )
    tree = create_accept_ownership_transfer_tree(
        case_id=case_id,
        offer_id=offer.id_,
        sender_id=_CASE_ACTOR_ID,
        answer_id=reply.id_,
        now=now_utc(),
        sender_rule=AcceptCaseOwnershipTransferReceivedUseCase.sender_entitlement,
    )

    BTBridge(
        datalayer=replica,
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(replica),
    ).execute_with_setup(
        tree=tree,
        actor_id=_COORDINATOR_ID,
        activity=make_payload(reply, receiving_actor_id=_COORDINATOR_ID),
    )

    check = find_node(tree, OwnershipOfferOpenNode)
    assert check is not None and check.status is Status.INVALID
    gate = next(
        n
        for n in tree.iterate()
        if n.name == "OwnershipOfferOpenIfCaseManager"
    )
    assert gate.status is Status.SUCCESS
