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
"""The ownership-transfer Offer's binding deadline and lazy expiry.

CM-21-016: an Accept or Reject the CASE_MANAGER processes after the Offer's
``end_time`` is refused, with no role change and no answer entry.
CM-21-017: the CASE_MANAGER finds the expiry lazily — when it processes an
Accept, Reject or Undo of the Offer, or a new proposal for the case — and commits
one distinct expiry entry behind its role gate, broadcast like any other; the
entry closes the Offer (CM-21-014).  A replica never computes an expiry.

An Offer whose deadline has already passed when it is delivered stands in
for one that expired while it waited, so no test sleeps.
"""

from datetime import datetime, timedelta
from typing import Any

import pytest
from py_trees.common import Status

from test.core.use_cases.received.actor.test_ownership import (
    _CASE_ACTOR_ID,
    _COORDINATOR_ID,
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
from test.support.ledger import commit_case_fully_closed
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.ownership_offer_expiry import (
    ExpireOverdueOwnershipOfferNode,
)
from vultron.core.behaviors.case.ownership_transfer_tree import (
    create_accept_ownership_transfer_tree,
)
from vultron.core.models._helpers import now_utc
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.protocol_pair import (
    OFFER_CASE_OWNERSHIP_TRANSFER_EXPIRED_SEMANTIC_TYPE,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received._bt_verdict import find_node
from vultron.core.use_cases.received.actor.ownership import (
    AcceptCaseOwnershipTransferReceivedUseCase,
)
from vultron.wire.as2.factories import (
    accept_case_ownership_transfer_activity,
)

_EXPIRED = OFFER_CASE_OWNERSHIP_TRANSFER_EXPIRED_SEMANTIC_TYPE


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


def _expiry_entries(dl) -> list[CaseLedgerEntry]:
    return [
        entry
        for entry in dl.list_objects("CaseLedgerEntry")
        if isinstance(entry, CaseLedgerEntry)
        and entry.semantic_type == _EXPIRED
    ]


class TestLateAnswerIsRefused:
    """CM-21-016: the deadline binds both answers."""

    @pytest.mark.spec("CM-21-016")
    @pytest.mark.spec("CM-21-017")
    def test_late_accept_moves_no_role_and_ledgers_only_the_expiry(
        self, make_payload
    ):
        case_id = "https://example.org/cases/case_dl_accept"
        dl, _, _, offer = _expired_offer(make_payload, case_id)
        roles_before = _owner_roles(dl, case_id)
        outbox_before = dl.outbox_list()

        result = _accept(dl, make_payload, offer)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None and "CM-21-016" in result.reason
        assert _owner(dl, case_id) == _VENDOR_ID
        assert _owner_roles(dl, case_id) == roles_before
        assert "accept_case_ownership_transfer" not in _semantic_types(dl)
        assert _semantic_types(dl).count(_EXPIRED) == 1
        # The expiry entry is broadcast as Announce(CaseLedgerEntry).
        assert _announces(dl, outbox_before)

    @pytest.mark.spec("CM-21-016")
    def test_late_reject_is_refused_and_not_ledgered(self, make_payload):
        case_id = "https://example.org/cases/case_dl_reject"
        dl, _, _, offer = _expired_offer(make_payload, case_id)

        result = _reject(dl, make_payload, offer)

        assert result.disposition is HandlerDisposition.REFUSED
        assert "reject_case_ownership_transfer" not in _semantic_types(dl)
        assert _semantic_types(dl).count(_EXPIRED) == 1

    @pytest.mark.spec("CM-21-016")
    @pytest.mark.spec("CM-21-017")
    def test_expiry_is_ledgered_once_however_many_late_answers_arrive(
        self, make_payload
    ):
        case_id = "https://example.org/cases/case_dl_twice"
        dl, _, _, offer = _expired_offer(make_payload, case_id)

        first = _accept(dl, make_payload, offer)
        second = _reject(dl, make_payload, offer)

        assert first.disposition is HandlerDisposition.REFUSED
        assert second.disposition is HandlerDisposition.REFUSED
        assert second.reason is not None and "expired" in second.reason
        assert _semantic_types(dl).count(_EXPIRED) == 1

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
        assert _EXPIRED not in _semantic_types(dl)

    @pytest.mark.spec("CM-21-016")
    @pytest.mark.spec("CLP-10-025")
    def test_late_accept_is_refused_even_without_an_expiry_record(
        self, make_payload, monkeypatch, caplog
    ):
        """The open-Offer guard reads the deadline itself, so a lost expiry
        record cannot let a late answer through: the clock decision whose
        commit is refused logs a warning and the tree goes on to refuse."""
        from py_trees.common import Status

        case_id = "https://example.org/cases/case_dl_guard"
        dl, _, _, offer = _expired_offer(make_payload, case_id)
        monkeypatch.setattr(
            ExpireOverdueOwnershipOfferNode,
            "_commit_expiry",
            lambda self, offer, now: Status.FAILURE,
        )

        with caplog.at_level("WARNING"):
            result = _accept(dl, make_payload, offer)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None and "CM-21-016" in result.reason
        assert _owner(dl, case_id) == _VENDOR_ID
        assert _expiry_entries(dl) == []
        assert "accept_case_ownership_transfer" not in _semantic_types(dl)
        assert any(
            "clock decision" in r.getMessage() and r.levelname == "WARNING"
            for r in caplog.records
        )


class TestLazyExpiry:
    """CM-21-017: the CASE_MANAGER records the expiry when it next acts."""

    @pytest.mark.spec("CM-21-017")
    @pytest.mark.spec("CM-21-015")
    def test_withdrawal_of_an_expired_offer_ledgers_the_expiry_and_is_refused(
        self, make_payload
    ):
        """An expired Offer is closed, and a closed Offer cannot be withdrawn."""
        case_id = "https://example.org/cases/case_dl_undo"
        dl, _, _, offer = _expired_offer(make_payload, case_id)

        result = _undo(dl, make_payload, offer)

        assert result.disposition is HandlerDisposition.REFUSED
        assert "undo_case_ownership_transfer" not in _semantic_types(dl)
        assert _semantic_types(dl).count(_EXPIRED) == 1

    @pytest.mark.spec("CM-21-017")
    @pytest.mark.spec("CM-21-014")
    def test_new_offer_after_an_expired_one_is_admitted_after_the_expiry(
        self, make_payload
    ):
        case_id = "https://example.org/cases/case_dl_reoffer"
        dl, deliver, trigger_activity, _ = _expired_offer(
            make_payload, case_id
        )

        second, _ = deliver(
            "https://example.org/users/vendor2", f"{case_id}/offer2"
        )

        assert second is HandlerDisposition.APPLIED
        types = _semantic_types(dl)
        # The expiry is committed before the new Offer it makes room for.
        assert types.index(_EXPIRED) < len(types) - 1
        assert types[-1] == "offer_case_ownership_transfer"
        assert trigger_activity.offer_case_ownership_transfer.call_count == 2

    @pytest.mark.spec("CM-21-017")
    def test_expiry_entry_is_the_case_managers_undo_of_the_offer(
        self, make_payload
    ):
        """Distinct from the Reject entry: the CASE_MANAGER's Undo(Offer)."""
        case_id = "https://example.org/cases/case_dl_snapshot"
        dl, _, _, offer = _expired_offer(make_payload, case_id)

        _accept(dl, make_payload, offer)

        (entry,) = _expiry_entries(dl)
        snapshot = entry.payload_snapshot
        assert entry.log_object_id == snapshot["id"]
        assert snapshot["type"] == "Undo"
        assert snapshot["actor"] == _CASE_ACTOR_ID
        assert snapshot["context"] == case_id
        assert snapshot["object"]["type"] == "Offer"
        assert snapshot["object"]["id"] == offer.id_
        assert "endTime" in snapshot["object"]

    @pytest.mark.spec("CM-21-017")
    def test_an_offer_without_a_deadline_never_expires(self, make_payload):
        case_id = "https://example.org/cases/case_dl_none"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, offer = deliver(_COORDINATOR_ID, f"{case_id}/offer")

        result = _accept(dl, make_payload, offer)

        assert result.disposition is HandlerDisposition.APPLIED
        assert _EXPIRED not in _semantic_types(dl)

    @pytest.mark.spec("CM-21-017")
    @pytest.mark.spec("BT-17-001")
    def test_only_the_case_manager_computes_an_expiry(self, make_payload):
        """Run at a replica, the reply's tree reaches the clock-decision
        stage and its CASE_MANAGER gate skips the expiry."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        case_id = "https://example.org/cases/case_dl_replica"
        dl, _, _, offer = _expired_offer(make_payload, case_id)
        # The transferee's replica of the case: the case and its participant
        # records, so the CASE_MANAGER is known there (PCR-03-001).
        replica = SqliteDataLayer(
            "sqlite:///:memory:", actor_id=_COORDINATOR_ID
        )
        for kind in ("VulnerabilityCase", "CaseParticipant"):
            for obj in dl.list_objects(kind):
                replica.create(obj)
        # A reply sent by the CASE_MANAGER: what a replica is entitled to
        # receive (PCR-03-001), so the door guards pass.
        reply = accept_case_ownership_transfer_activity(
            offer, actor=_CASE_ACTOR_ID, to=[_COORDINATOR_ID]
        )
        tree = create_accept_ownership_transfer_tree(
            case_id=case_id,
            offer_id=offer.id_,
            sender_id=_CASE_ACTOR_ID,
            answer_id=reply.id_,
            now=now_utc(),
            sender_rule=(
                AcceptCaseOwnershipTransferReceivedUseCase.sender_entitlement
            ),
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

        gate = next(
            c for c in tree.children if c.name == "ClockDecisionsIfCaseManager"
        )
        decision = find_node(tree, ExpireOverdueOwnershipOfferNode)
        assert gate.status is Status.SUCCESS
        assert decision is not None and decision.status is Status.INVALID
        assert _expiry_entries(replica) == []
        assert _expiry_entries(dl) == []


class TestTheActivityIsNotTheEvidence:
    """CLP-10-025: the reply prompts the expiry, the clock decides it."""

    @pytest.mark.spec("CLP-10-025")
    @pytest.mark.spec("CM-21-017")
    @pytest.mark.parametrize(
        "claimed",
        # Inside the ledger's clock-skew tolerance (CLP-14-006/007), and on
        # either side of each deadline below.
        [timedelta(minutes=-4), timedelta(minutes=4)],
        ids=["claims-before-deadline", "claims-after-deadline"],
    )
    @pytest.mark.parametrize(
        "deadline, expires",
        [(timedelta(seconds=-5), True), (timedelta(minutes=2), False)],
        ids=["deadline-passed", "deadline-ahead"],
    )
    def test_claimed_published_time_does_not_change_the_expiry_verdict(
        self, make_payload, claimed, deadline, expires
    ):
        """Whatever the Accept claims about when it was sent, the expiry is
        decided from the CASE_MANAGER's clock, and its entry carries that
        clock's reading, not the claim."""
        case_id = "https://example.org/cases/case_dl_published"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, offer = deliver(
            _COORDINATOR_ID, f"{case_id}/offer", end_time=now_utc() + deadline
        )
        claimed_published = now_utc() + claimed
        accept = accept_case_ownership_transfer_activity(
            offer,
            actor=_COORDINATOR_ID,
            to=[_CASE_ACTOR_ID],
            published=claimed_published,
        )

        result = _accept(dl, make_payload, offer, accept=accept)

        if expires:
            assert result.disposition is HandlerDisposition.REFUSED
            (entry,) = _expiry_entries(dl)
            # Stamped with the CASE_MANAGER's clock, not the Accept's claim.
            stamped = datetime.fromisoformat(
                entry.payload_snapshot["published"]
            )
            assert abs(stamped - now_utc()) < timedelta(minutes=1)
        else:
            assert result.disposition is HandlerDisposition.APPLIED
            assert _expiry_entries(dl) == []


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


class TestOnlyThePartyPromptsTheExpiry:
    """HP-01-006: a sender with no standing never makes the CASE_MANAGER
    write, so only a reply from the Offer's party prompts the expiry."""

    @pytest.mark.spec("HP-01-006")
    @pytest.mark.spec("CM-21-017")
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
        self, make_payload, reply, sender
    ):
        case_id = "https://example.org/cases/case_dl_non_party"
        dl, _, _, offer = _expired_offer(make_payload, case_id)
        entries_before = _semantic_types(dl)
        outbox_before = dl.outbox_list()

        result = reply(dl, make_payload, offer, sender=sender)

        assert result.disposition is HandlerDisposition.REFUSED
        assert _semantic_types(dl) == entries_before
        assert _announces(dl, outbox_before) == []
        assert _owner(dl, case_id) == _VENDOR_ID

    @pytest.mark.spec("HP-01-006")
    @pytest.mark.spec("CM-21-017")
    def test_late_reply_naming_an_unrecorded_offer_ledgers_nothing(
        self, make_payload
    ):
        """The transferee's reply prompts the expiry only for the open Offer."""
        from vultron.wire.as2.factories import (
            offer_case_ownership_transfer_activity,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        case_id = "https://example.org/cases/case_dl_other_offer"
        dl, _, _, _ = _expired_offer(make_payload, case_id)
        entries_before = _semantic_types(dl)
        unrecorded = offer_case_ownership_transfer_activity(
            as_VulnerabilityCase(id_=case_id),
            target=_COORDINATOR_ID,
            actor=_VENDOR_ID,
            to=[_CASE_ACTOR_ID],
            id_=f"{case_id}/never-recorded",
        )

        result = _accept(dl, make_payload, unrecorded)

        assert result.disposition is HandlerDisposition.REFUSED
        assert _semantic_types(dl) == entries_before

    @pytest.mark.spec("CM-21-017")
    def test_the_partys_late_reply_after_a_non_partys_still_ledgers_it(
        self, make_payload
    ):
        """A refused outsider leaves the expiry for the party's reply."""
        case_id = "https://example.org/cases/case_dl_party_after"
        dl, _, _, offer = _expired_offer(make_payload, case_id)

        _accept(dl, make_payload, offer, sender="https://example.org/u/eve")
        result = _accept(dl, make_payload, offer)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None and "CM-21-016" in result.reason
        assert _semantic_types(dl).count(_EXPIRED) == 1


@pytest.mark.spec("CM-23-013")
@pytest.mark.spec("CM-21-017")
def test_expiry_changes_nothing_once_the_case_is_fully_closed(make_payload):
    """After ``case_fully_closed`` the door guard ends the tree before the
    clock decision, so the CASE_MANAGER commits no expiry."""
    case_id = "https://example.org/cases/case_dl_closed"
    dl, _, _, offer = _expired_offer(make_payload, case_id)
    commit_case_fully_closed(dl, case_id, _VENDOR_ID)
    entries_before = _semantic_types(dl)

    result = _accept(dl, make_payload, offer)

    assert result.disposition is HandlerDisposition.REFUSED
    assert result.reason is not None and "CM-23-013" in result.reason
    assert _semantic_types(dl) == entries_before
    assert _expiry_entries(dl) == []


@pytest.mark.spec("HP-01-006")
@pytest.mark.spec("CM-21-019")
@pytest.mark.spec("CM-21-017")
def test_an_offer_from_a_non_owner_ledgers_no_expiry(make_payload):
    """The Offer's sender guard runs before the clock decision, so a sender
    that is not the Case Owner never makes the CASE_MANAGER ledger the open
    Offer's expiry."""
    case_id = "https://example.org/cases/case_dl_non_owner_offer"
    dl, deliver, _, _ = _expired_offer(make_payload, case_id)
    entries_before = _semantic_types(dl)

    second, _ = deliver(
        "https://example.org/users/vendor2",
        f"{case_id}/offer2",
        offerer="https://example.org/users/mallory",
    )

    assert second is HandlerDisposition.REFUSED
    assert _semantic_types(dl) == entries_before
    assert _expiry_entries(dl) == []


@pytest.mark.spec("CM-21-017")
@pytest.mark.spec("CLP-12-002")
def test_a_replica_admits_the_expiry_entry_the_case_manager_commits(
    make_payload,
):
    """A replica learns the expiry from the entry, so its canonical-entry
    check must admit the entry as the CASE_MANAGER wrote it."""
    from vultron.core.behaviors.sync.nodes.canonical_entry import (
        _CASE_AUTHORED_SIGNATURES,
        _validate_canonical_entry,
    )

    case_id = "https://example.org/cases/case_dl_replica_admits"
    dl, _, _, offer = _expired_offer(make_payload, case_id)
    _accept(dl, make_payload, offer)
    (entry,) = _expiry_entries(dl)

    assert ("Undo", "Offer") in _CASE_AUTHORED_SIGNATURES
    _validate_canonical_entry(
        case_id=case_id,
        payload_snapshot=entry.payload_snapshot,
        semantic_type=entry.semantic_type,
    )
