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
Accept, Reject or Undo of the Offer, or a new Offer for the case — and commits
one distinct expiry entry behind its role gate, broadcast like any other; the
entry closes the Offer (CM-21-014).  A replica never computes an expiry.

An Offer whose deadline has already passed when it is delivered stands in
for one that expired while it waited, so no test sleeps.
"""

from datetime import timedelta
from typing import Any

import pytest

from test.core.use_cases.received.actor.test_ownership import (
    _CASE_ACTOR_ID,
    _COORDINATOR_ID,
    _VENDOR_ID,
    _accept,
    _announces,
    _event_types,
    _owner,
    _owner_roles,
    _ownership_offer_harness,
    _reject,
    _undo,
)
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.ownership_expiry_tree import (
    create_ownership_offer_expiry_tree,
)
from vultron.core.models._helpers import now_utc
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.protocol_pair import (
    OFFER_CASE_OWNERSHIP_TRANSFER_EXPIRED_EVENT_TYPE,
)
from vultron.core.models.use_case_result import HandlerDisposition

_EXPIRED = OFFER_CASE_OWNERSHIP_TRANSFER_EXPIRED_EVENT_TYPE


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
        if isinstance(entry, CaseLedgerEntry) and entry.event_type == _EXPIRED
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
        assert "accept_case_ownership_transfer" not in _event_types(dl)
        assert _event_types(dl).count(_EXPIRED) == 1
        # The expiry entry is broadcast as Announce(CaseLedgerEntry).
        assert _announces(dl, outbox_before)

    @pytest.mark.spec("CM-21-016")
    def test_late_reject_is_refused_and_not_ledgered(self, make_payload):
        case_id = "https://example.org/cases/case_dl_reject"
        dl, _, _, offer = _expired_offer(make_payload, case_id)

        result = _reject(dl, make_payload, offer)

        assert result.disposition is HandlerDisposition.REFUSED
        assert "reject_case_ownership_transfer" not in _event_types(dl)
        assert _event_types(dl).count(_EXPIRED) == 1

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
        assert _event_types(dl).count(_EXPIRED) == 1

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
        assert _EXPIRED not in _event_types(dl)

    @pytest.mark.spec("CM-21-016")
    def test_late_accept_is_refused_even_without_an_expiry_record(
        self, make_payload
    ):
        """The sender guard reads the deadline itself, so a lost expiry
        record cannot let a late answer through."""
        from vultron.core.behaviors.case.ownership_transfer_tree import (
            create_accept_ownership_transfer_tree,
        )

        case_id = "https://example.org/cases/case_dl_guard"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, offer = deliver(
            _COORDINATOR_ID, f"{case_id}/offer", end_time=_future()
        )
        from vultron.wire.as2.factories import (
            accept_case_ownership_transfer_activity,
        )

        accept = accept_case_ownership_transfer_activity(
            offer, actor=_COORDINATOR_ID, to=[_CASE_ACTOR_ID]
        )
        tree = create_accept_ownership_transfer_tree(
            case_id=case_id,
            offer_id=offer.id_,
            sender_id=_COORDINATOR_ID,
            answer_id=accept.id_,
            # Two hours on: past the deadline, but no expiry was ledgered.
            now=now_utc() + timedelta(hours=2),
        )
        result = BTBridge(
            datalayer=dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute_with_setup(
            tree=tree,
            actor_id=_CASE_ACTOR_ID,
            activity=make_payload(accept, receiving_actor_id=_CASE_ACTOR_ID),
        )

        assert result.status.name == "FAILURE"
        assert "CM-21-016" in (BTBridge.get_failure_reason(tree) or "")
        assert _owner(dl, case_id) == _VENDOR_ID
        assert "accept_case_ownership_transfer" not in _event_types(dl)


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
        assert "undo_case_ownership_transfer" not in _event_types(dl)
        assert _event_types(dl).count(_EXPIRED) == 1

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
        types = _event_types(dl)
        # The expiry is committed before the new Offer it makes room for.
        assert types.index(_EXPIRED) < len(types) - 1
        assert types[-1] == "offer_case_ownership_transfer"
        assert trigger_activity.offer_case_ownership_transfer.call_count == 2

    @pytest.mark.spec("CM-21-017")
    def test_expiry_entry_is_the_case_managers_expire_of_the_offer(
        self, make_payload
    ):
        """Distinct from the Reject entry: the CASE_MANAGER's Expire(Offer)."""
        case_id = "https://example.org/cases/case_dl_snapshot"
        dl, _, _, offer = _expired_offer(make_payload, case_id)

        _accept(dl, make_payload, offer)

        (entry,) = _expiry_entries(dl)
        snapshot = entry.payload_snapshot
        assert entry.log_object_id == offer.id_
        assert snapshot["type"] == "Expire"
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
        assert _EXPIRED not in _event_types(dl)

    @pytest.mark.spec("CM-21-017")
    @pytest.mark.spec("BT-17-001")
    def test_only_the_case_manager_computes_an_expiry(self, make_payload):
        """Run as any other actor, the expiry tree commits nothing."""
        case_id = "https://example.org/cases/case_dl_replica"
        dl, _, _, _ = _expired_offer(make_payload, case_id)
        tree = create_ownership_offer_expiry_tree(
            case_id=case_id, now=now_utc()
        )

        result = BTBridge(
            datalayer=dl, sync_port=SyncActivityAdapter(dl)
        ).execute_with_setup(tree=tree, actor_id=_COORDINATOR_ID)

        assert result.status.name == "SUCCESS"
        assert _expiry_entries(dl) == []


@pytest.mark.spec("CM-21-005")
@pytest.mark.spec("CM-21-016")
def test_forward_carries_the_offers_deadline(make_payload):
    """The transferee answers the forward, so the forward names the deadline."""
    case_id = "https://example.org/cases/case_dl_forward"
    _, deliver, trigger_activity = _ownership_offer_harness(
        make_payload, case_id
    )
    deadline = _future()

    deliver(_COORDINATOR_ID, f"{case_id}/offer", end_time=deadline)

    trigger_activity.offer_case_ownership_transfer.assert_called_once()
    _, kwargs = trigger_activity.offer_case_ownership_transfer.call_args
    assert kwargs["end_time"] == deadline


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
        entries_before = _event_types(dl)
        outbox_before = dl.outbox_list()

        result = reply(dl, make_payload, offer, sender=sender)

        assert result.disposition is HandlerDisposition.REFUSED
        assert _event_types(dl) == entries_before
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
        entries_before = _event_types(dl)
        unrecorded = offer_case_ownership_transfer_activity(
            as_VulnerabilityCase(id_=case_id),
            target=_COORDINATOR_ID,
            actor=_VENDOR_ID,
            to=[_CASE_ACTOR_ID],
            id_=f"{case_id}/never-recorded",
        )

        result = _accept(dl, make_payload, unrecorded)

        assert result.disposition is HandlerDisposition.REFUSED
        assert _event_types(dl) == entries_before

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
        assert _event_types(dl).count(_EXPIRED) == 1


@pytest.mark.spec("CM-23-013")
@pytest.mark.spec("CM-21-017")
def test_expiry_changes_nothing_once_the_case_is_fully_closed(make_payload):
    """After ``case_fully_closed`` the CASE_MANAGER commits no expiry."""
    from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
    from vultron.core.models.case_ledger import HashChainLedgerRecord

    case_id = "https://example.org/cases/case_dl_closed"
    dl, _, _, _ = _expired_offer(make_payload, case_id)
    dl.create(
        _to_persistable_entry(
            HashChainLedgerRecord(
                case_id=case_id,
                log_index=len(_event_types(dl)),
                object_id=f"{case_id}/owner-leave",
                event_type="case_fully_closed",
                payload_snapshot={"actor": _VENDOR_ID},
                prev_log_hash="0" * 64,
            )
        )
    )
    entries_before = _event_types(dl)
    tree = create_ownership_offer_expiry_tree(case_id=case_id, now=now_utc())

    result = BTBridge(
        datalayer=dl,
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
    ).execute_with_setup(tree=tree, actor_id=_CASE_ACTOR_ID)

    assert result.status.name == "SUCCESS"
    assert _event_types(dl) == entries_before
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
    from vultron.core.models.rsvp_deadline import EXPIRE_SNAPSHOT_TYPE

    case_id = "https://example.org/cases/case_dl_replica_admits"
    dl, _, _, offer = _expired_offer(make_payload, case_id)
    _accept(dl, make_payload, offer)
    (entry,) = _expiry_entries(dl)

    assert (EXPIRE_SNAPSHOT_TYPE, "Offer") in _CASE_AUTHORED_SIGNATURES
    _validate_canonical_entry(
        case_id=case_id,
        payload_snapshot=entry.payload_snapshot,
        event_type=entry.event_type,
    )
