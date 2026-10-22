#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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
"""Tests for ownership transfer received use cases (CM-21, ADR-0148).

The Case Owner proposes a transfer to the CASE_MANAGER as
``Offer(Offer(VulnerabilityCase))``; the CASE_MANAGER makes the one
``Offer(VulnerabilityCase)`` the transferee answers, under an id it derives
from the proposal.  The harness delivers proposals and hands back that Offer.
"""

import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from test.core.use_cases.received._archived_redelivery import (
    archived_redelivery_as,
)
from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_owner_participant,
    seed_case_participant,
)
from test.support.case_owner import CASE_OWNER_ID
from test.support.received import (
    assert_held_only_as_received,
    received_record,
)
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models._helpers import now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.events.actor import (
    ProposeCaseOwnershipTransferReceivedEvent,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.participants.ownership_offer import ownership_offer_id
from vultron.core.use_cases.received.actor.ownership import (
    AcceptCaseOwnershipTransferReceivedUseCase,
    OfferCaseOwnershipTransferReceivedUseCase,
    ProposeCaseOwnershipTransferReceivedUseCase,
    RejectCaseOwnershipTransferReceivedUseCase,
    UndoCaseOwnershipTransferReceivedUseCase,
)
from vultron.errors import VultronBTInternalError
from vultron.wire.as2.factories import (
    accept_case_ownership_transfer_activity,
    offer_case_ownership_transfer_activity,
    propose_case_ownership_transfer_activity,
    reject_case_ownership_transfer_activity,
    undo_case_ownership_transfer_activity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)


class TestOwnershipTransferUseCases:
    """Tests for offer/accept/reject ownership transfer use cases."""

    @pytest.mark.spec("DL-06-006")
    @pytest.mark.spec("CLP-10-017")
    def test_offer_case_ownership_transfer_persists_offer(self, make_payload):
        """The transferee keeps the CASE_MANAGER's Offer as received.

        The store holds no ingress row: the Offer is held only as intake
        archived it, never under the id its sender chose (DL-06-006).
        """
        dl, case = _transferee_replica("https://example.org/cases/case_ot1")
        activity = offer_case_ownership_transfer_activity(
            case,
            target=_COORDINATOR_ID,
            actor=_CASE_ACTOR_ID,
            to=[_COORDINATOR_ID],
        )
        event = make_payload(activity, receiving_actor_id=_COORDINATOR_ID)

        result = OfferCaseOwnershipTransferReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert_held_only_as_received(dl, activity.id_)
        assert result.disposition == HandlerDisposition.APPLIED

        # HP-01-003: a redelivered Offer stores nothing new.
        again = OfferCaseOwnershipTransferReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()
        assert again.disposition == HandlerDisposition.SKIPPED

    def test_offer_ownership_unresolvable_receiver_writes_nothing(
        self, make_payload, anonymous_store
    ):
        """No receiver → the Offer is not persisted (#2667).

        The Offer used to be stored before ``resolve_receiving_actor_id`` ran,
        so a refusal left it behind in a store no actor owned (CM-01-001).
        """
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.errors import VultronValidationError

        inner = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case = as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID,
            id_="https://example.org/cases/case_ot_anon",
            name="OT Case anon",
        )
        activity = offer_case_ownership_transfer_activity(
            case,
            target="https://example.org/users/coordinator",
            actor="https://example.org/users/vendor",
        )
        event = make_payload(activity, receiving_actor_id=None)

        with pytest.raises(VultronValidationError):
            OfferCaseOwnershipTransferReceivedUseCase(
                anonymous_store(inner),
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(anonymous_store(inner)),
            ).execute()

        assert inner.get(activity.type_.value, activity.id_) is None

    @pytest.mark.spec("CM-21-002")
    @pytest.mark.spec("CM-21-011")
    def test_accept_case_ownership_transfer_updates_attributed_to(
        self, make_payload
    ):
        """The transferee of a recorded Offer accepts it; the CASE_MANAGER
        moves ownership to the transferee (CM-21-002) and ledgers the Accept
        (CM-21-007, ADR-0053)."""
        dl, deliver, _ = _ownership_offer_harness(
            make_payload, "https://example.org/cases/case_ot2"
        )
        disposition, offer = deliver(
            _COORDINATOR_ID, "https://example.org/activities/offer_ot2"
        )
        assert disposition is HandlerDisposition.APPLIED

        result = _accept(dl, make_payload, offer)

        assert result.disposition == HandlerDisposition.APPLIED
        assert _owner(dl, "https://example.org/cases/case_ot2") == (
            _COORDINATOR_ID
        )
        assert "accept_case_ownership_transfer" in _semantic_types(dl)

    @pytest.mark.spec("HP-01-003")
    def test_accept_ownership_transfer_for_unknown_case_writes_nothing(
        self, make_payload
    ):
        """An Accept(ownership) for a case this actor does not hold changes
        no ownership: the receiver has no case to check the sender's standing
        against, so it refuses and writes no case state (HP-01-006,
        CM-21-011).  The transfer, if it is this actor's to learn of, arrives
        through the ledger (RSH-08-003, #3814)."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        coordinator_id = "https://example.org/users/coordinator"
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=coordinator_id)
        case = as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID,
            id_="https://example.org/cases/case_ot_missing",
            name="Missing",
        )
        offer = offer_case_ownership_transfer_activity(
            case,
            target=coordinator_id,
            actor="https://example.org/users/vendor",
            id_="https://example.org/activities/offer_ot_missing",
        )
        event = make_payload(
            accept_case_ownership_transfer_activity(
                offer, actor=coordinator_id
            ),
            receiving_actor_id=coordinator_id,
        )

        result = AcceptCaseOwnershipTransferReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        # Nothing to establish the sender's standing against, so it is
        # refused (HP-01-006); the case was never held and is still absent.
        assert result.disposition == HandlerDisposition.REFUSED
        assert dl.read("https://example.org/cases/case_ot_missing") is None

    @pytest.mark.spec("HP-01-003")
    @pytest.mark.spec("CLP-10-018")
    def test_accept_ownership_transfer_without_case_is_refused(
        self, make_payload
    ):
        """Intake archives it; nothing else runs (CLP-10-018)."""
        dl, _, _ = _ownership_offer_harness(
            make_payload, "https://example.org/cases/case_ot_accept_nocase"
        )
        event = _reply_naming_no_case(
            dl,
            make_payload,
            accept_case_ownership_transfer_activity,
            _COORDINATOR_ID,
        )

        result = AcceptCaseOwnershipTransferReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason is not None and "names no case" in result.reason
        assert _semantic_types(dl) == []
        assert _archived(dl, event.activity_id)

    @pytest.mark.spec("CM-21-005")
    @pytest.mark.spec("CM-24-001")
    @pytest.mark.spec("CM-24-002")
    def test_proposal_makes_one_offer_minted_by_the_case_manager(
        self, make_payload
    ):
        """One Offer leaves the CASE_MANAGER, under an id it derived, with
        ``actor`` itself and ``attributedTo`` the owner (ADR-0148)."""
        case_id = "https://example.org/cases/case_ot_made"
        dl, deliver, trigger_activity = _ownership_offer_harness(
            make_payload, case_id
        )
        proposal_id = "https://example.org/activities/proposal_made"

        disposition, offer = deliver(_COORDINATOR_ID, proposal_id)

        assert disposition is HandlerDisposition.APPLIED
        made_id = ownership_offer_id(
            _CASE_ACTOR_ID, case_id, proposal_id, _VENDOR_ID
        )
        trigger_activity.offer_case_ownership_transfer.assert_called_once_with(
            case_id=case_id,
            transferee_id=_COORDINATOR_ID,
            actor=_CASE_ACTOR_ID,
            to=[_COORDINATOR_ID],
            attributed_to=_VENDOR_ID,
            # The proposal named no deadline, so the Offer carries none.
            end_time=None,
            id_=made_id,
        )
        assert offer.id_ == made_id != proposal_id
        assert offer.actor == _CASE_ACTOR_ID
        assert offer.attributed_to == _VENDOR_ID
        assert made_id in dl.outbox_list()
        # Exactly one Offer of the case is queued: the one the CASE_MANAGER
        # made, never the owner's proposal.
        queued_offers = [
            getattr(item, "id_", None)
            for item in (dl.read(i) for i in dl.outbox_list())
            if getattr(getattr(item, "type_", None), "value", None) == "Offer"
        ]
        assert queued_offers == [made_id]

    @pytest.mark.spec("CM-21-005")
    @pytest.mark.spec("SYNC-09-002")
    def test_the_offer_entry_snapshot_is_the_emitted_offer(self, make_payload):
        """The ledgered Offer is the one sent, recorded once it was queued."""
        case_id = "https://example.org/cases/case_ot_snapshot"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        proposal_id = "https://example.org/activities/proposal_snapshot"

        _, offer = deliver(_COORDINATOR_ID, proposal_id)

        entries = _entries(dl)
        assert [e.semantic_type for e in entries] == [
            "propose_case_ownership_transfer",
            "offer_case_ownership_transfer",
        ]
        proposal_entry, offer_entry = entries
        assert proposal_entry.log_object_id == proposal_id
        assert proposal_entry.payload_snapshot["actor"] == _VENDOR_ID
        assert offer_entry.log_object_id == offer.id_
        snapshot = offer_entry.payload_snapshot
        assert snapshot["id"] == offer.id_
        assert snapshot["actor"] == _CASE_ACTOR_ID
        assert snapshot["attributedTo"] == _VENDOR_ID
        assert snapshot["target"]["id"] == _COORDINATOR_ID
        assert snapshot["to"] == [_COORDINATOR_ID]

    @pytest.mark.spec("CM-21-005")
    def test_the_inner_offers_id_actor_and_to_are_ignored(self, make_payload):
        """The CASE_MANAGER validates the inner Offer and copies none of the
        sender's own fields: an inner id naming a stored object, an inner
        ``actor`` and an inner ``to`` change nothing (ADR-0148)."""
        case_id = "https://example.org/cases/case_ot_inner_ignored"
        dl, _deliver, trigger_activity = _ownership_offer_harness(
            make_payload, case_id
        )
        case = _read_case(dl, case_id)
        # The case file: the Offer's own entry moves the case's ledger
        # position, which is part of applying it, not a change (CLP-07-013).
        case_before = case.model_dump(exclude={"ledger_position"})
        proposal_id = "https://example.org/activities/proposal_inner"
        proposal = propose_case_ownership_transfer_activity(
            case,
            target=as_Service(id_=_COORDINATOR_ID, name="Transferee"),
            actor=_VENDOR_ID,
            to=[_CASE_ACTOR_ID],
            id_=proposal_id,
        )
        # The inner Offer claims the case's own id, another actor and
        # another recipient.
        proposal = proposal.model_copy(
            update={
                "object_": cast(Any, proposal.object_).model_copy(
                    update={
                        "id_": case_id,
                        "actor": _MALLORY_ID,
                        "to": [_MALLORY_ID],
                    }
                )
            }
        )

        result = _propose(dl, make_payload, proposal, trigger_activity)

        assert result.disposition is HandlerDisposition.APPLIED
        kwargs = (
            trigger_activity.offer_case_ownership_transfer.call_args.kwargs
        )
        assert kwargs["id_"] == ownership_offer_id(
            _CASE_ACTOR_ID, case_id, proposal_id, _VENDOR_ID
        )
        assert kwargs["actor"] == _CASE_ACTOR_ID
        assert kwargs["attributed_to"] == _VENDOR_ID
        assert kwargs["to"] == [_COORDINATOR_ID]
        assert (
            _read_case(dl, case_id).model_dump(exclude={"ledger_position"})
            == case_before
        )

    @pytest.mark.spec("CM-21-005")
    @pytest.mark.parametrize(
        ("label", "reason"),
        [
            ("another_case", "names case"),
            ("no_transferee", "names no transferee"),
            ("case_manager", "the CASE_MANAGER"),
            ("proposer", "names the proposer"),
        ],
    )
    def test_an_inner_offer_the_case_manager_cannot_make_is_refused(
        self, make_payload, label, reason
    ):
        """The inner Offer must name this case and an actor the CASE_MANAGER
        can address; otherwise nothing is ledgered and no Offer is made."""
        case_id = f"https://example.org/cases/case_ot_inner_{label}"
        dl, _, trigger_activity = _ownership_offer_harness(
            make_payload, case_id
        )
        case = _read_case(dl, case_id)
        target: Any = {
            "another_case": as_Service(id_=_COORDINATOR_ID, name="T"),
            "no_transferee": None,
            "case_manager": as_Service(id_=_CASE_ACTOR_ID, name="CM"),
            "proposer": as_Service(id_=_VENDOR_ID, name="Owner"),
        }[label]
        proposal = propose_case_ownership_transfer_activity(
            case,
            target=target,
            actor=_VENDOR_ID,
            to=[_CASE_ACTOR_ID],
            id_=f"https://example.org/activities/proposal_inner_{label}",
        )
        if label == "another_case":
            another = as_VulnerabilityCase(
                attributed_to=CASE_OWNER_ID,
                id_="https://example.org/cases/another",
                name="Another",
            )
            proposal = proposal.model_copy(
                update={
                    "object_": cast(Any, proposal.object_).model_copy(
                        update={"object_": another}
                    )
                }
            )
        roles_before = _owner_roles(dl, case_id)

        result = _propose(dl, make_payload, proposal, trigger_activity)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None and reason in result.reason
        _assert_nothing_changed(dl, case_id, roles_before, [])
        trigger_activity.offer_case_ownership_transfer.assert_not_called()

    def test_the_offer_is_made_in_the_bt_not_in_execute(
        self, make_payload, monkeypatch
    ):
        """``execute()`` builds exactly one tree, and the Offer is made by
        ``MakeOwnershipTransferOfferNode`` inside it (CLP-10-005)."""
        from vultron.core.use_cases.received.actor import ownership

        assert not hasattr(ownership, "add_activity_to_outbox"), (
            "the outbox write belongs to MakeOwnershipTransferOfferNode"
            " (CLP-10-005)"
        )
        case_id = "https://example.org/cases/case_ot_bt"
        dl, _, trigger_activity = _ownership_offer_harness(
            make_payload, case_id
        )
        calls: list[dict] = []
        real_factory = ownership.create_propose_ownership_transfer_tree

        def _spy(**kwargs):
            calls.append(kwargs)
            return real_factory(**kwargs)

        monkeypatch.setattr(
            ownership, "create_propose_ownership_transfer_tree", _spy
        )
        proposal = _proposal(
            _read_case(dl, case_id),
            _COORDINATOR_ID,
            "https://example.org/activities/proposal_bt",
        )

        _propose(dl, make_payload, proposal, trigger_activity)

        assert all(
            c.pop("sender_rule", None)
            is ProposeCaseOwnershipTransferReceivedUseCase.sender_entitlement
            and c.pop("sender_id", None) == _VENDOR_ID
            for c in calls
        )
        # The clock decision compares the open Offer's deadline against the
        # CASE_MANAGER's clock, read once by execute() (CLP-10-025).
        assert all(isinstance(c.pop("now", None), datetime) for c in calls)
        assert calls == [
            {
                "case_id": case_id,
                "proposed_case_id": case_id,
                "transferee_id": _COORDINATOR_ID,
                "proposal_id": proposal.id_,
                "answer_deadline": None,
            }
        ], calls
        trigger_activity.offer_case_ownership_transfer.assert_called_once()

    @pytest.mark.spec("CM-21-019")
    @pytest.mark.spec("HP-01-006")
    def test_an_offer_of_the_case_sent_to_the_case_manager_is_refused(
        self, make_payload
    ):
        """At the CASE_MANAGER no sender is admitted for ``Offer(Case)``:
        the owner proposes, it does not offer, and the CASE_MANAGER sends
        itself no Offer (CM-21-019, ADR-0148)."""
        case_id = "https://example.org/cases/case_ot_offer_at_cm"
        dl, _, trigger_activity = _ownership_offer_harness(
            make_payload, case_id
        )
        case = _read_case(dl, case_id)
        for sender in (_VENDOR_ID, _CASE_ACTOR_ID):
            activity = offer_case_ownership_transfer_activity(
                case,
                target=_COORDINATOR_ID,
                actor=sender,
                to=[_CASE_ACTOR_ID],
                attributed_to=_VENDOR_ID,
            )

            result = OfferCaseOwnershipTransferReceivedUseCase(
                dl,
                make_payload(activity, receiving_actor_id=_CASE_ACTOR_ID),
                trigger_activity=trigger_activity,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            ).execute()

            assert result.disposition is HandlerDisposition.REFUSED
            assert result.reason is not None
            assert "No sender is entitled" in result.reason
        assert _semantic_types(dl) == []
        trigger_activity.offer_case_ownership_transfer.assert_not_called()
        assert _owner(dl, case_id) == _VENDOR_ID

    @pytest.mark.spec("CM-24-002")
    def test_attributed_to_on_the_proposal_is_not_the_offerer(
        self, make_payload
    ):
        """The owner that sends the proposal is the one the Offer speaks for;
        an ``attributedTo`` it writes on the proposal is a claim nothing
        checks (CLP-07-003), so the Offer is attributed to the sender."""
        case_id = "https://example.org/cases/case_ot_claimed"
        _dl, deliver, trigger_activity = _ownership_offer_harness(
            make_payload, case_id
        )

        disposition, offer = deliver(
            _COORDINATOR_ID,
            "https://example.org/activities/proposal_claimed",
            attributed_to="https://example.org/actors/someone_else",
        )

        assert disposition is HandlerDisposition.APPLIED
        kwargs = (
            trigger_activity.offer_case_ownership_transfer.call_args.kwargs
        )
        assert kwargs["attributed_to"] == _VENDOR_ID
        assert offer.attributed_to == _VENDOR_ID

    def test_a_missing_trigger_port_is_an_internal_error(self, make_payload):
        """The CASE_MANAGER cannot make the Offer without its factory: that is
        a wiring fault, never a refusal of the owner, and no Offer is sent."""
        case_id = "https://example.org/cases/case_ot_no_port"
        dl, _, _ = _ownership_offer_harness(make_payload, case_id)
        proposal = _proposal(
            _read_case(dl, case_id),
            _COORDINATOR_ID,
            "https://example.org/activities/proposal_no_port",
        )

        with pytest.raises(VultronBTInternalError):
            _propose(dl, make_payload, proposal, trigger_activity=None)

        assert "offer_case_ownership_transfer" not in _semantic_types(dl)
        queued = [dl.read(item) for item in dl.outbox_list()]
        assert "Offer" not in [
            getattr(getattr(q, "type_", None), "value", None) for q in queued
        ]

    @pytest.mark.spec("CLP-07-015")
    def test_an_offer_whose_commit_fails_is_not_sent(
        self, make_payload, monkeypatch
    ):
        """The Offer is built, queued and committed in one transaction, so a
        failed commit leaves no Offer in the outbox for a ledger that does
        not record it (ADR-0146)."""
        from vultron.core.behaviors.case.nodes import ownership_transfer

        case_id = "https://example.org/cases/case_ot_commit_fails"
        dl, _, trigger_activity = _ownership_offer_harness(
            make_payload, case_id
        )
        proposal_id = "https://example.org/activities/proposal_commit_fails"

        def _refuse(**_kwargs):
            raise RuntimeError("ledger refused the commit")

        monkeypatch.setattr(
            ownership_transfer, "commit_emitted_activity", _refuse
        )

        with pytest.raises(VultronBTInternalError):
            _propose(
                dl,
                make_payload,
                _proposal(
                    _read_case(dl, case_id), _COORDINATOR_ID, proposal_id
                ),
                trigger_activity,
            )

        made_id = ownership_offer_id(
            _CASE_ACTOR_ID, case_id, proposal_id, _VENDOR_ID
        )
        assert made_id not in dl.outbox_list()
        assert dl.read(made_id) is None
        assert "offer_case_ownership_transfer" not in _semantic_types(dl)

    def test_proposal_uses_store_owner_when_no_receiving_actor(
        self, make_payload
    ):
        """When receiving_actor_id is absent the store owner processes the
        proposal (CLP-10-005): it is archived, never stored under its id."""
        case_id = "https://example.org/cases/case_ot_nostamp"
        dl, _, trigger_activity = _ownership_offer_harness(
            make_payload, case_id
        )
        proposal = _proposal(
            _read_case(dl, case_id),
            _COORDINATOR_ID,
            "https://example.org/activities/proposal_nostamp",
        )

        result = _propose(
            dl,
            make_payload,
            proposal,
            trigger_activity,
            receiving_actor_id=None,
        )

        assert result.disposition is HandlerDisposition.APPLIED
        assert_held_only_as_received(dl, proposal.id_)

    def test_proposal_unresolvable_receiver_writes_nothing(
        self, make_payload, anonymous_store
    ):
        """No receiver → the proposal is not persisted (#2667)."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.errors import VultronValidationError

        inner = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        proposal = _proposal(
            as_VulnerabilityCase(
                attributed_to=CASE_OWNER_ID,
                id_="https://example.org/cases/case_ot_proposal_anon",
                name="anon",
            ),
            _COORDINATOR_ID,
            "https://example.org/activities/proposal_anon",
        )

        with pytest.raises(VultronValidationError):
            ProposeCaseOwnershipTransferReceivedUseCase(
                anonymous_store(inner),
                make_payload(proposal, receiving_actor_id=None),
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(anonymous_store(inner)),
            ).execute()

        assert inner.get(proposal.type_.value, proposal.id_) is None

    def test_accept_case_ownership_transfer_uses_store_owner_when_no_receiving_actor(
        self, make_payload
    ):
        """When receiving_actor_id is absent the store owner runs the accept BT.

        Absent-stamp path (CLP-10-005): resolve_receiving_actor_id falls back
        to dl.actor_id (the CASE_MANAGER), so the ownership transfer is applied
        rather than dropped.
        """
        case_id = "https://example.org/cases/case_ot_acc_nostamp"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, offer = deliver(
            _COORDINATOR_ID, "https://example.org/activities/offer_ot_nostamp"
        )
        accept = accept_case_ownership_transfer_activity(
            offer, actor=_COORDINATOR_ID, to=[_CASE_ACTOR_ID]
        )

        AcceptCaseOwnershipTransferReceivedUseCase(
            dl,
            make_payload(accept, receiving_actor_id=None),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        assert _owner(dl, case_id) == _COORDINATOR_ID, (
            "The store owner (the CASE_MANAGER) must apply the transfer when"
            " receiving_actor_id is absent (CLP-10-005)"
        )


class TestOwnershipOfferAtNonRecipient:
    """A copy of Offer(ownership transfer) at an actor it does not name (#3752).

    Two receivers are entitled to the Offer: the CASE_MANAGER it is addressed
    to (CM-21-005) and the transferee the CASE_MANAGER forwards it to.  Anyone
    else holds a misaddressed copy, refuses, and stores nothing (HP-01-005).
    """

    @pytest.mark.spec("HP-01-005")
    def test_bystander_refuses_and_stores_nothing(self, make_payload):
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        bystander_id = "https://example.org/actors/bystander-ot"
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=bystander_id)
        case = as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID,
            id_="https://example.org/cases/case_ot_bystander",
            name="OT Bystander",
        )
        activity = offer_case_ownership_transfer_activity(
            case,
            target="https://example.org/users/coordinator",
            actor="https://example.org/users/vendor",
            to=["https://example.org/actors/case-actor"],
        )
        event = make_payload(activity, receiving_actor_id=bystander_id)

        result = OfferCaseOwnershipTransferReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason is not None and bystander_id in result.reason
        assert dl.get(activity.type_.value, activity.id_) is None, (
            "a refused Offer must not be left behind in the bystander's store"
        )


class TestOwnershipProposalOwnCopy:
    """The Case Owner's own copy of its proposal, at its own replica (#4832).

    The addressee door guard admits a sender's own copy (HP-01-005), so the
    sender guard decides it: a proposal is sent to the CASE_MANAGER alone,
    so a participant admits no sender, and the copy commits, stores and
    sends nothing (CM-21-019).
    """

    @pytest.mark.spec("HP-01-005")
    @pytest.mark.spec("CM-21-019")
    def test_own_copy_is_refused_by_the_sender_guard(self, make_payload):
        case_id = "https://example.org/cases/case_ot_own_copy"
        dl, _ = _vendor_replica(case_id)
        proposal = _proposal(
            _read_case(dl, case_id),
            _COORDINATOR_ID,
            "https://example.org/activities/proposal_own_copy",
        )

        result = _propose(
            dl,
            make_payload,
            proposal,
            trigger_activity=None,
            receiving_actor_id=_VENDOR_ID,
        )

        assert result.disposition is HandlerDisposition.REFUSED
        assert "No sender is entitled" in (result.reason or "")
        assert dl.get(proposal.type_.value, proposal.id_) is None
        assert dl.list_objects("CaseLedgerEntry") == []
        assert dl.outbox_list() == []


class TestOwnershipOfferNamingNoCase:
    """An Offer that names no case is refused but still kept (CLP-10-018)."""

    def test_refused_and_the_offer_is_archived(self, make_payload):
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.models.received_activity_record import (
            ReceivedActivityRecord,
        )

        receiver = "https://test.example/api/v2/actors/test-actor"
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=receiver)
        case = as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID,
            id_="https://example.org/cases/case_ot_nocase",
            name="no case",
        )
        offer = offer_case_ownership_transfer_activity(
            case,
            target="https://example.org/users/coordinator",
            actor="https://example.org/users/vendor",
            to=[receiver],
        )
        event = make_payload(offer, receiving_actor_id=receiver)
        # The Offer arrives naming no case.
        event = event.model_copy(
            update={
                "activity": event.activity.model_copy(update={"object_": None})
            }
        )

        result = OfferCaseOwnershipTransferReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason and "names no case" in result.reason
        assert dl.read(ReceivedActivityRecord.build_id(offer.id_)) is not None
        # Only the archive keeps it: the refused Offer is not stored (#4737).
        assert dl.get(offer.type_.value, offer.id_) is None

    @pytest.mark.spec("CLP-10-018")
    def test_a_proposal_naming_no_case_is_refused_and_archived(
        self, make_payload
    ):
        dl, _, trigger_activity = _ownership_offer_harness(
            make_payload, "https://example.org/cases/case_ot_proposal_nocase"
        )
        proposal = _proposal(
            _read_case(
                dl, "https://example.org/cases/case_ot_proposal_nocase"
            ),
            _COORDINATOR_ID,
            "https://example.org/activities/proposal_nocase",
        )
        event = make_payload(proposal, receiving_actor_id=_CASE_ACTOR_ID)
        event = event.model_copy(update={"context": None})
        assert event.case_id is None

        result = ProposeCaseOwnershipTransferReceivedUseCase(
            dl,
            event,
            trigger_activity=trigger_activity,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason and "names no case" in result.reason
        assert _archived(dl, proposal.id_)
        assert _semantic_types(dl) == []
        trigger_activity.offer_case_ownership_transfer.assert_not_called()


_CASE_ACTOR_ID = "https://example.org/actors/case-actor"
_VENDOR_ID = "https://example.org/users/vendor"
_COORDINATOR_ID = "https://example.org/users/coordinator"
_MALLORY_ID = "https://example.org/users/mallory"


#: The owner's proposal each Offer the CASE_MANAGER made came from, by the
#: Offer's id, so a test withdraws the proposal behind the Offer it holds.
_PROPOSAL_OF: dict[str, Any] = {}


def _proposal(
    case,
    transferee: Any,
    proposal_id: str,
    end_time: datetime | None = None,
    proposer: str = _VENDOR_ID,
    **extra: Any,
):
    """The *proposer*'s Offer(Offer(Case)) to the CASE_MANAGER (ADR-0148)."""
    if isinstance(transferee, str):
        transferee = as_Service(id_=transferee, name="Transferee")
    return propose_case_ownership_transfer_activity(
        case,
        target=transferee,
        end_time=end_time,
        actor=proposer,
        to=[_CASE_ACTOR_ID],
        id_=proposal_id,
        **extra,
    )


def _propose(
    dl,
    make_payload,
    proposal,
    trigger_activity,
    receiving_actor_id: str | None = _CASE_ACTOR_ID,
):
    """Deliver *proposal* to *dl* and return the handler's result."""
    return ProposeCaseOwnershipTransferReceivedUseCase(
        dl,
        make_payload(proposal, receiving_actor_id=receiving_actor_id),
        trigger_activity=trigger_activity,
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
    ).execute()


def _made_offer(dl, case_id: str, proposal):
    """The Offer the CASE_MANAGER made from *proposal*, or ``None``."""
    made = dl.read(
        ownership_offer_id(
            _CASE_ACTOR_ID, case_id, proposal.id_, str(proposal.actor)
        )
    )
    if made is not None:
        _PROPOSAL_OF[made.id_] = proposal
    return made


def _ownership_offer_harness(make_payload, case_id: str):
    """A CASE_MANAGER store holding one case, and a function delivering a proposal.

    The roster holds the CASE_MANAGER, the vendor as Case Owner and the
    coordinator as a plain participant.  Returns ``(dl, deliver,
    trigger_activity)``; ``deliver(transferee_id, proposal_id, end_time=None,
    offerer=_VENDOR_ID, attributed_to=None)`` delivers the *offerer*'s
    proposal and returns its disposition with the Offer the CASE_MANAGER
    made from it, which the transferee answers, or the proposal when no
    Offer was made.  The trigger port is the real adapter, wrapped so a test
    can count the Offers it built.
    """
    from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_ID)
    case = as_VulnerabilityCase(
        id_=case_id, name="One open offer", attributed_to=_VENDOR_ID
    )
    seed_case_manager_participant(dl, case, _CASE_ACTOR_ID)
    seed_case_owner_participant(dl, case, _VENDOR_ID)
    seed_case_participant(dl, case, _COORDINATOR_ID)
    dl.create(case)
    trigger_activity = MagicMock(wraps=TriggerActivityAdapter(dl))

    def deliver(
        transferee_id: str,
        proposal_id: str,
        end_time: datetime | None = None,
        offerer: str = _VENDOR_ID,
        attributed_to: str | None = None,
    ) -> tuple[HandlerDisposition, Any]:
        extra = (
            {} if attributed_to is None else {"attributed_to": attributed_to}
        )
        proposal = _proposal(
            case, transferee_id, proposal_id, end_time, offerer, **extra
        )
        result = _propose(dl, make_payload, proposal, trigger_activity)
        made = _made_offer(dl, case_id, proposal)
        return result.disposition, made if made is not None else proposal

    return dl, deliver, trigger_activity


def _deadline_shortly() -> datetime:
    """A deadline a second away, at the second precision of the clock.

    The CASE_MANAGER reads ``now_utc()``, which drops microseconds, so a
    deadline with a fraction of a second could still read as not passed
    just after it.
    """
    return now_utc() + timedelta(seconds=1)


def _wait_past(deadline: datetime) -> None:
    time.sleep(max(0.0, (deadline - datetime.now(UTC)).total_seconds()) + 0.05)


def _accept(
    dl, make_payload, offer, sender=_COORDINATOR_ID, accept=None, to=None
):
    """Deliver the transferee's (or *sender*'s) Accept of *offer* to *dl*."""
    if accept is None:
        accept = accept_case_ownership_transfer_activity(
            offer, actor=sender, to=to or [_CASE_ACTOR_ID]
        )
    return AcceptCaseOwnershipTransferReceivedUseCase(
        dl,
        make_payload(accept, receiving_actor_id=dl.actor_id),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
        trigger_activity=TriggerActivityAdapter(dl),
    ).execute()


def _read_case(dl, case_id: str) -> VulnerabilityCase:
    case = dl.read(case_id)
    assert isinstance(case, VulnerabilityCase)
    return case


def _owner(dl, case_id: str) -> str | None:
    case = dl.read(case_id)
    assert isinstance(case, VulnerabilityCase)
    return cast(str | None, case.attributed_to)


def _semantic_types(dl) -> list[str]:
    return [
        entry.semantic_type
        for entry in dl.list_objects("CaseLedgerEntry")
        if isinstance(entry, CaseLedgerEntry)
    ]


def _archived(dl, activity_id: str) -> bool:
    """True when intake archived *activity_id* under the receiver's key."""
    from vultron.core.models.received_activity_record import (
        ReceivedActivityRecord,
    )

    return isinstance(
        dl.read(ReceivedActivityRecord.build_id(activity_id)),
        ReceivedActivityRecord,
    )


def _entries(dl) -> list[CaseLedgerEntry]:
    return sorted(
        (
            entry
            for entry in dl.list_objects("CaseLedgerEntry")
            if isinstance(entry, CaseLedgerEntry)
        ),
        key=lambda entry: entry.log_index,
    )


def _reply_naming_no_case(dl, make_payload, build, sender: str) -> Any:
    """A reply to an ownership-transfer Offer whose Offer names no case.

    The factories cannot build one, so the case is dropped from the
    extracted event: the shape a peer could send.
    """
    offer = offer_case_ownership_transfer_activity(
        case=as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID,
            id_="https://example.org/cases/elsewhere",
        ),
        target=_COORDINATOR_ID,
        actor=_CASE_ACTOR_ID,
        to=[_COORDINATOR_ID],
    )
    reply = build(offer, actor=sender, to=[_CASE_ACTOR_ID])
    event = make_payload(reply, receiving_actor_id=dl.actor_id)
    event = event.model_copy(update={"inner_object": None})
    assert event.case_id is None
    return event


@pytest.mark.spec("CM-21-014")
def test_second_offer_while_first_is_unanswered_is_refused(make_payload):
    """Two pending Offers would let two transferees accept the same case."""
    dl, deliver, trigger_activity = _ownership_offer_harness(
        make_payload, "https://example.org/cases/case_ot_one_open"
    )

    first, _ = deliver(
        _COORDINATOR_ID,
        "https://example.org/activities/offer_one_open_1",
    )
    entries_after_first = _semantic_types(dl)
    second, _ = deliver(
        "https://example.org/users/vendor2",
        "https://example.org/activities/offer_one_open_2",
    )

    assert first is HandlerDisposition.APPLIED
    assert second is HandlerDisposition.REFUSED
    trigger_activity.offer_case_ownership_transfer.assert_called_once()
    # Refused before the commit: no entry, so no replica learns of it.
    assert _semantic_types(dl) == entries_after_first


@pytest.mark.spec("CM-21-014")
def test_new_offer_after_the_first_is_answered_is_admitted(make_payload):
    """Once an Offer is answered, the case may be offered again to anyone."""
    dl, deliver, trigger_activity = _ownership_offer_harness(
        make_payload, "https://example.org/cases/case_ot_reoffer"
    )
    disposition, first = deliver(
        _COORDINATOR_ID, "https://example.org/activities/offer_reoffer_1"
    )
    assert disposition is HandlerDisposition.APPLIED

    answered = _accept(dl, make_payload, first)
    assert answered.disposition is HandlerDisposition.APPLIED

    # The coordinator now owns the case and offers it on.
    second, _ = deliver(
        "https://example.org/users/vendor2",
        "https://example.org/activities/offer_reoffer_2",
        offerer=_COORDINATOR_ID,
    )

    assert second is HandlerDisposition.APPLIED
    assert trigger_activity.offer_case_ownership_transfer.call_count == 2


def _redeliver_proposal(dl, make_payload, offer, trigger_activity):
    """Deliver the proposal behind *offer* (or *offer* itself, a proposal)
    to the CASE_MANAGER again."""
    return _propose(
        dl, make_payload, _PROPOSAL_OF.get(offer.id_, offer), trigger_activity
    )


@pytest.mark.spec("HP-01-003")
@pytest.mark.spec("CM-21-014")
def test_redelivered_proposal_is_skipped_and_its_offer_not_made_again(
    make_payload,
):
    """The proposal behind the open Offer, delivered again, is no new one."""
    dl, deliver, trigger_activity = _ownership_offer_harness(
        make_payload, "https://example.org/cases/case_ot_offer_again"
    )
    first, offer = deliver(
        _COORDINATOR_ID, "https://example.org/activities/offer_again_1"
    )
    entries_after_first = _semantic_types(dl)
    outbox_after_first = dl.outbox_list()

    again = _redeliver_proposal(dl, make_payload, offer, trigger_activity)

    assert first is HandlerDisposition.APPLIED
    assert again.disposition is HandlerDisposition.SKIPPED
    assert _semantic_types(dl) == entries_after_first
    assert dl.outbox_list() == outbox_after_first
    # The Offer already went out; a duplicate does not make it twice.
    trigger_activity.offer_case_ownership_transfer.assert_called_once()


@pytest.mark.spec("HP-01-003")
@pytest.mark.spec("CM-21-014")
@pytest.mark.spec("CM-21-019")
def test_redelivered_proposal_of_an_answered_offer_is_skipped_while_a_newer_one_is_open(
    make_payload,
):
    """A late copy of a proposal whose Offer was answered is a duplicate."""
    dl, deliver, trigger_activity = _ownership_offer_harness(
        make_payload, "https://example.org/cases/case_ot_offer_late_copy"
    )
    _, first = deliver(
        _COORDINATOR_ID, "https://example.org/activities/offer_late_copy_1"
    )
    assert (
        _accept(dl, make_payload, first).disposition
        is HandlerDisposition.APPLIED
    )
    newer, _ = deliver(
        "https://example.org/users/vendor2",
        "https://example.org/activities/offer_late_copy_2",
        offerer=_COORDINATOR_ID,
    )
    assert newer is HandlerDisposition.APPLIED
    entries_before = _semantic_types(dl)

    late = _redeliver_proposal(dl, make_payload, first, trigger_activity)

    assert late.disposition is HandlerDisposition.SKIPPED
    assert _semantic_types(dl) == entries_before
    assert trigger_activity.offer_case_ownership_transfer.call_count == 2


@pytest.mark.spec("CM-21-019")
@pytest.mark.spec("HP-01-003")
def test_a_new_owner_reusing_an_old_proposal_id_makes_a_new_offer(
    make_payload,
):
    """A proposal id is the proposer's: the next owner reusing it proposes
    anew, so it is judged and its own Offer made, never skipped as the old
    owner's redelivery."""
    case_id = "https://example.org/cases/case_ot_reused_by_new_owner"
    dl, deliver, trigger_activity = _ownership_offer_harness(
        make_payload, case_id
    )
    proposal_id = "https://example.org/activities/proposal_reused"
    _, first = deliver(_COORDINATOR_ID, proposal_id)
    assert (
        _accept(dl, make_payload, first).disposition
        is HandlerDisposition.APPLIED
    )

    again, second = deliver(_VENDOR_ID, proposal_id, offerer=_COORDINATOR_ID)

    assert again is HandlerDisposition.APPLIED
    assert second.id_ != first.id_
    assert trigger_activity.offer_case_ownership_transfer.call_count == 2


@pytest.mark.spec("CM-21-005")
@pytest.mark.spec("HP-01-003")
def test_an_offer_that_fails_after_the_proposal_entry_is_made_on_redelivery(
    make_payload,
):
    """The fault is the CASE_MANAGER's, not a refusal.  The proposal's entry
    and the Offer are one act, so the fault keeps neither, and a redelivery
    of the proposal commits it and makes the Offer, under the same derived
    id (CLP-07-015, OX-06-002)."""
    case_id = "https://example.org/cases/case_ot_offer_fails"
    dl, _, trigger_activity = _ownership_offer_harness(make_payload, case_id)
    factory = trigger_activity.offer_case_ownership_transfer
    factory.side_effect = RuntimeError("down")
    proposal = _proposal(
        _read_case(dl, case_id),
        _COORDINATOR_ID,
        "https://example.org/activities/proposal_fails",
    )

    with pytest.raises(VultronBTInternalError):
        _propose(dl, make_payload, proposal, trigger_activity)
    assert _semantic_types(dl) == []

    factory.side_effect = None  # the real adapter again
    # The inbox routes the redelivery as the copy intake archived
    # (IE-10-001), not as the resent body.
    again = ProposeCaseOwnershipTransferReceivedUseCase(
        dl,
        archived_redelivery_as(
            dl,
            proposal.id_,
            ProposeCaseOwnershipTransferReceivedEvent,
            receiving_actor_id=_CASE_ACTOR_ID,
        ),
        trigger_activity=trigger_activity,
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
    ).execute()

    assert again.disposition is HandlerDisposition.APPLIED
    assert _semantic_types(dl) == [
        "propose_case_ownership_transfer",
        "offer_case_ownership_transfer",
    ]
    made_id = ownership_offer_id(
        _CASE_ACTOR_ID, case_id, proposal.id_, _VENDOR_ID
    )
    assert [c.kwargs["id_"] for c in factory.call_args_list] == [
        made_id,
        made_id,
    ]
    assert made_id in dl.outbox_list()


@pytest.mark.spec("CM-21-016")
def test_accept_after_the_offer_deadline_is_refused(make_payload):
    """A transfer deadline is binding: a late answer changes nothing."""
    dl, deliver, _ = _ownership_offer_harness(
        make_payload, "https://example.org/cases/case_ot_deadline"
    )
    deadline = _deadline_shortly()
    disposition, offer = deliver(
        _COORDINATOR_ID,
        "https://example.org/activities/offer_deadline_1",
        end_time=deadline,
    )
    assert disposition is HandlerDisposition.APPLIED
    _wait_past(deadline)

    late = _accept(dl, make_payload, offer)

    assert late.disposition is HandlerDisposition.REFUSED
    case = dl.read("https://example.org/cases/case_ot_deadline")
    assert isinstance(case, VulnerabilityCase)
    assert case.attributed_to == _VENDOR_ID


@pytest.mark.spec("CM-21-017")
@pytest.mark.spec("CM-21-014")
def test_new_offer_after_an_expired_one_ledgers_no_expiry(make_payload):
    """An Offer past its end_time is closed, so a new one is admitted, and
    nothing records the expiry (ADR-0152)."""
    dl, deliver, _ = _ownership_offer_harness(
        make_payload, "https://example.org/cases/case_ot_expired"
    )
    deadline = _deadline_shortly()
    first, _ = deliver(
        _COORDINATOR_ID,
        "https://example.org/activities/offer_expired_1",
        end_time=deadline,
    )
    assert first is HandlerDisposition.APPLIED
    _wait_past(deadline)

    second, _ = deliver(
        "https://example.org/users/vendor2",
        "https://example.org/activities/offer_expired_2",
    )

    assert second is HandlerDisposition.APPLIED
    semantic_types = [
        entry.semantic_type
        for entry in dl.list_objects("CaseLedgerEntry")
        if isinstance(entry, CaseLedgerEntry)
    ]
    assert not any(
        "expir" in semantic_type for semantic_type in semantic_types
    ), semantic_types
    assert semantic_types.count("offer_case_ownership_transfer") == 2


# ---------------------------------------------------------------------------
# CM-21-011: the Accept is acted on only from the transferee of an open,
# recorded Offer; a replica takes the change only from the CASE_MANAGER.
# ---------------------------------------------------------------------------


def _owner_roles(dl, case_id: str) -> dict[str, bool]:
    """Each participant's actor id, and whether it holds ``CASE_OWNER``."""
    from vultron.core.models.case_participant import CaseParticipant
    from vultron.enums.roles import CVDRole

    case = dl.read(case_id)
    assert isinstance(case, VulnerabilityCase)
    held: dict[str, bool] = {}
    for actor_id, participant_id in case.actor_participant_index.items():
        participant = dl.read(participant_id)
        assert isinstance(participant, CaseParticipant)
        held[actor_id] = CVDRole.CASE_OWNER in participant.roles
    return held


def _assert_nothing_changed(dl, case_id: str, roles_before, entries_before):
    assert _owner(dl, case_id) == _VENDOR_ID
    assert _owner_roles(dl, case_id) == roles_before
    assert _semantic_types(dl) == entries_before


def _plant_offer(
    dl,
    case_id: str,
    target: str,
    offer_id: str,
    in_reply_to: str | None = None,
):
    """Store an Offer that claims the CASE_MANAGER made it.

    Inbound inline objects are stored by id, so a sender can plant one, even
    linked by *in_reply_to* to the Offer the CASE_MANAGER recorded.  No link
    is followed (ADR-0148): only the recorded Offer's own id names it.
    """
    case = dl.read(case_id)
    assert isinstance(case, VulnerabilityCase)
    planted = offer_case_ownership_transfer_activity(
        case,
        target=as_Service(id_=target, name="Planted"),
        actor=_CASE_ACTOR_ID,
        id_=offer_id,
        **({} if in_reply_to is None else {"in_reply_to": in_reply_to}),
    )
    dl.create(planted)
    return planted


class TestAcceptIsActedOnOnlyFromTheTransferee:
    """CM-21-011, HP-01-006: the sender rule of the ownership-transfer Accept."""

    @pytest.mark.spec("CM-21-011")
    @pytest.mark.spec("HP-01-006")
    def test_accept_from_a_non_transferee_changes_nothing(self, make_payload):
        """The Offer names the coordinator; the vendor itself accepts it."""
        case_id = "https://example.org/cases/case_ot_impostor"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, offer = deliver(
            _COORDINATOR_ID, "https://example.org/activities/offer_impostor"
        )
        roles_before = _owner_roles(dl, case_id)
        entries_before = _semantic_types(dl)
        outbox_before = dl.outbox_list()

        result = _accept(dl, make_payload, offer, sender=_VENDOR_ID)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None
        assert "is not the transferee" in result.reason
        _assert_nothing_changed(dl, case_id, roles_before, entries_before)
        assert dl.outbox_list() == outbox_before

    @pytest.mark.spec("CM-21-002")
    @pytest.mark.spec("CM-21-005")
    @pytest.mark.spec("CM-21-011")
    def test_accept_of_the_case_managers_offer_is_applied(self, make_payload):
        """The transferee answers the one Offer of the transfer, which the
        CASE_MANAGER made under its own id: no link to resolve (ADR-0148)."""
        case_id = "https://example.org/cases/case_ot_made_accept"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        proposal_id = "https://example.org/activities/proposal_made_accept"
        disposition, offer = deliver(_COORDINATOR_ID, proposal_id)
        assert disposition is HandlerDisposition.APPLIED
        assert offer.id_ == ownership_offer_id(
            _CASE_ACTOR_ID, case_id, proposal_id, _VENDOR_ID
        )
        assert getattr(offer, "in_reply_to", None) is None

        result = _accept(dl, make_payload, offer)

        assert result.disposition is HandlerDisposition.APPLIED
        assert _owner(dl, case_id) == _COORDINATOR_ID
        assert _owner_roles(dl, case_id)[_COORDINATOR_ID] is True
        assert _owner_roles(dl, case_id)[_VENDOR_ID] is False

    @pytest.mark.spec("CM-21-011")
    def test_accept_naming_the_proposal_is_refused(self, make_payload):
        """The owner's proposal is not the Offer the transferee answers."""
        case_id = "https://example.org/cases/case_ot_accept_proposal"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        proposal_id = "https://example.org/activities/proposal_accept"
        deliver(_COORDINATOR_ID, proposal_id)
        case = _read_case(dl, case_id)
        named = offer_case_ownership_transfer_activity(
            case,
            target=as_Service(id_=_COORDINATOR_ID, name="Transferee"),
            actor=_VENDOR_ID,
            id_=proposal_id,
        )
        roles_before = _owner_roles(dl, case_id)
        entries_before = _semantic_types(dl)

        result = _accept(dl, make_payload, named)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None and "never recorded" in result.reason
        _assert_nothing_changed(dl, case_id, roles_before, entries_before)

    @pytest.mark.spec("CM-21-011")
    def test_accept_of_an_offer_never_recorded_is_refused(self, make_payload):
        """An Offer held but never ledgered is not one the CASE_MANAGER recorded."""
        case_id = "https://example.org/cases/case_ot_unrecorded"
        dl, _, _ = _ownership_offer_harness(make_payload, case_id)
        case = dl.read(case_id)
        assert isinstance(case, VulnerabilityCase)
        from vultron.wire.as2.vocab.base.objects.actors import as_Service

        offer = offer_case_ownership_transfer_activity(
            case,
            target=as_Service(id_=_COORDINATOR_ID, name="Transferee"),
            actor=_VENDOR_ID,
            id_="https://example.org/activities/offer_unrecorded",
        )
        dl.create(offer)
        roles_before = _owner_roles(dl, case_id)

        result = _accept(dl, make_payload, offer)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None and "never recorded" in result.reason
        _assert_nothing_changed(dl, case_id, roles_before, [])
        assert dl.outbox_list() == []

    @pytest.mark.spec("CM-21-011")
    @pytest.mark.spec("CM-21-014")
    def test_second_accept_of_an_answered_offer_is_refused(self, make_payload):
        """Once an Accept closed the Offer, another Accept of it is not re-applied."""
        case_id = "https://example.org/cases/case_ot_twice"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, offer = deliver(
            _COORDINATOR_ID, "https://example.org/activities/offer_twice"
        )
        assert (
            _accept(dl, make_payload, offer).disposition
            is HandlerDisposition.APPLIED
        )
        entries_after_first = _semantic_types(dl)

        again = _accept(dl, make_payload, offer)

        assert again.disposition is HandlerDisposition.REFUSED
        assert again.reason is not None and "already closed" in again.reason
        assert _semantic_types(dl) == entries_after_first

    @pytest.mark.spec("HP-01-003")
    def test_redelivered_accept_is_skipped(self, make_payload):
        """The Accept that closed the Offer, delivered again, is the same answer."""
        case_id = "https://example.org/cases/case_ot_redelivered"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, offer = deliver(
            _COORDINATOR_ID, "https://example.org/activities/offer_redeliver"
        )
        accept = accept_case_ownership_transfer_activity(
            offer, actor=_COORDINATOR_ID, to=[_CASE_ACTOR_ID]
        )
        first = _accept(dl, make_payload, offer, accept=accept)
        entries_after_first = _semantic_types(dl)

        again = _accept(dl, make_payload, offer, accept=accept)

        assert first.disposition is HandlerDisposition.APPLIED
        assert again.disposition is HandlerDisposition.SKIPPED
        assert _semantic_types(dl) == entries_after_first
        assert _owner(dl, case_id) == _COORDINATOR_ID

    @pytest.mark.spec("CM-21-011")
    @pytest.mark.spec("HP-01-003")
    def test_replayed_accept_does_not_undo_a_later_transfer(
        self, make_payload
    ):
        """An old Accept, replayed after ownership moved on, changes nothing.

        The vendor offers the case to the coordinator, who accepts; the
        coordinator then offers it back, and the vendor accepts.  The
        coordinator's first Accept, delivered again, must not hand the case
        back to it: the ledger records the vendor as owner, so re-applying the
        old Accept would split the case record from the ledger.
        """
        case_id = "https://example.org/cases/case_ot_replay"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, first = deliver(
            _COORDINATOR_ID, "https://example.org/activities/offer_replay_1"
        )
        old_accept = accept_case_ownership_transfer_activity(
            first, actor=_COORDINATOR_ID, to=[_CASE_ACTOR_ID]
        )
        assert (
            _accept(dl, make_payload, first, accept=old_accept).disposition
            is HandlerDisposition.APPLIED
        )
        _, second = deliver(
            _VENDOR_ID,
            "https://example.org/activities/offer_replay_2",
            offerer=_COORDINATOR_ID,
        )
        assert (
            _accept(dl, make_payload, second, sender=_VENDOR_ID).disposition
            is HandlerDisposition.APPLIED
        )
        roles_before = _owner_roles(dl, case_id)
        entries_before = _semantic_types(dl)
        outbox_before = dl.outbox_list()

        replay = _accept(dl, make_payload, first, accept=old_accept)

        assert replay.disposition is HandlerDisposition.SKIPPED
        _assert_nothing_changed(dl, case_id, roles_before, entries_before)
        assert dl.outbox_list() == outbox_before

    @pytest.mark.spec("CM-21-011")
    @pytest.mark.parametrize(
        ("label", "target", "reason"),
        [
            ("impostor", _MALLORY_ID, "never recorded"),
            ("transferee", _COORDINATOR_ID, "never recorded"),
        ],
    )
    def test_a_planted_offer_linked_to_the_recorded_one_is_refused(
        self, make_payload, label, target, reason
    ):
        """An Offer claiming the CASE_MANAGER, linked by ``inReplyTo`` to the
        recorded Offer, stands for nothing: no back-link is followed."""
        case_id = f"https://example.org/cases/case_ot_planted_{label}"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, recorded = deliver(
            _COORDINATOR_ID, f"https://example.org/activities/proposal_{label}"
        )
        planted = _plant_offer(
            dl,
            case_id,
            target,
            f"https://example.org/activities/planted_{label}",
            in_reply_to=recorded.id_,
        )
        roles_before = _owner_roles(dl, case_id)
        entries_before = _semantic_types(dl)
        outbox_before = dl.outbox_list()

        result = _accept(dl, make_payload, planted, sender=target)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None and reason in result.reason
        _assert_nothing_changed(dl, case_id, roles_before, entries_before)
        assert dl.outbox_list() == outbox_before

    @pytest.mark.spec("CM-21-011")
    @pytest.mark.spec("CM-21-019")
    def test_proposal_from_a_non_owner_cannot_win_ownership(
        self, make_payload
    ):
        """An actor off the roster proposes the case to itself: no Offer is
        made, so there is nothing for it to accept."""
        case_id = "https://example.org/cases/case_ot_self_offer"
        dl, deliver, trigger_activity = _ownership_offer_harness(
            make_payload, case_id
        )
        disposition, proposal = deliver(
            _MALLORY_ID,
            "https://example.org/activities/offer_self",
            offerer=_MALLORY_ID,
        )

        assert disposition is HandlerDisposition.REFUSED
        assert _made_offer(dl, case_id, proposal) is None
        trigger_activity.offer_case_ownership_transfer.assert_not_called()
        assert _owner(dl, case_id) == _VENDOR_ID

    @pytest.mark.spec("CM-21-014")
    def test_accept_of_a_later_offer_is_applied_after_an_earlier_answer(
        self, make_payload
    ):
        """An answer to an earlier Offer does not close the next one."""
        case_id = "https://example.org/cases/case_ot_sequential"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, first = deliver(
            _COORDINATOR_ID, "https://example.org/activities/offer_seq_1"
        )
        assert (
            _accept(dl, make_payload, first).disposition
            is HandlerDisposition.APPLIED
        )
        _, second = deliver(
            _VENDOR_ID,
            "https://example.org/activities/offer_seq_2",
            offerer=_COORDINATOR_ID,
        )

        result = _accept(dl, make_payload, second, sender=_VENDOR_ID)

        assert result.disposition is HandlerDisposition.APPLIED
        assert _owner(dl, case_id) == _VENDOR_ID


class TestProposalIsAdmittedOnlyFromTheCaseOwner:
    """CM-21-019, HP-01-006: the sender rule of the ownership-transfer proposal.

    At the CASE_MANAGER only the Case Owner may propose to offer the case.
    Any other sender is refused before anything is written: no ledger entry,
    no Offer, and the owner unchanged.
    """

    def _assert_refused_and_nothing_written(
        self, dl, trigger_activity, case_id, proposal, before
    ):
        roles_before, entries_before, outbox_before = before
        _assert_nothing_changed(dl, case_id, roles_before, entries_before)
        assert dl.outbox_list() == outbox_before
        trigger_activity.offer_case_ownership_transfer.assert_not_called()
        assert dl.read(proposal.id_) is None, (
            "a refused proposal must not be stored under its sender's id"
        )
        assert _made_offer(dl, case_id, proposal) is None

    @staticmethod
    def _before(dl, case_id):
        return (
            _owner_roles(dl, case_id),
            _semantic_types(dl),
            dl.outbox_list(),
        )

    @pytest.mark.spec("CM-21-019")
    @pytest.mark.spec("HP-01-006")
    def test_offer_from_an_actor_off_the_roster_is_refused(self, make_payload):
        case_id = "https://example.org/cases/case_ot_offer_stranger"
        dl, deliver, trigger_activity = _ownership_offer_harness(
            make_payload, case_id
        )
        before = self._before(dl, case_id)

        disposition, offer = deliver(
            _MALLORY_ID,
            "https://example.org/activities/offer_stranger",
            offerer=_MALLORY_ID,
        )

        assert disposition is HandlerDisposition.REFUSED
        self._assert_refused_and_nothing_written(
            dl, trigger_activity, case_id, offer, before
        )

    @pytest.mark.spec("CM-21-019")
    @pytest.mark.spec("HP-01-006")
    def test_offer_from_a_participant_that_is_not_case_owner_is_refused(
        self, make_payload
    ):
        """A participant on the roster without ``CASE_OWNER`` cannot offer."""
        case_id = "https://example.org/cases/case_ot_offer_participant"
        dl, deliver, trigger_activity = _ownership_offer_harness(
            make_payload, case_id
        )
        before = self._before(dl, case_id)

        disposition, offer = deliver(
            "https://example.org/users/vendor2",
            "https://example.org/activities/offer_participant",
            offerer=_COORDINATOR_ID,
        )

        assert disposition is HandlerDisposition.REFUSED
        self._assert_refused_and_nothing_written(
            dl, trigger_activity, case_id, offer, before
        )

    @pytest.mark.spec("CM-21-019")
    def test_refusal_names_the_case_owner_standing(self, make_payload):
        case_id = "https://example.org/cases/case_ot_offer_reason"
        dl, _, trigger_activity = _ownership_offer_harness(
            make_payload, case_id
        )
        proposal = _proposal(
            _read_case(dl, case_id),
            _COORDINATOR_ID,
            "https://example.org/activities/offer_reason",
            proposer=_MALLORY_ID,
        )

        result = _propose(dl, make_payload, proposal, trigger_activity)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None
        assert "is not the Case Owner" in result.reason

    @pytest.mark.spec("CM-21-019")
    @pytest.mark.spec("CM-21-017")
    @pytest.mark.spec("HP-01-006")
    def test_a_refused_offer_after_an_overdue_one_writes_nothing(
        self, make_payload
    ):
        """An Offer that has expired makes no room for a sender with no
        standing: it is refused before the CASE_MANAGER writes."""
        case_id = "https://example.org/cases/case_ot_offer_stranger_expiry"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        deadline = _deadline_shortly()
        first, _ = deliver(
            _COORDINATOR_ID,
            "https://example.org/activities/offer_stranger_expiry_1",
            end_time=deadline,
        )
        assert first is HandlerDisposition.APPLIED
        _wait_past(deadline)
        entries_before = _semantic_types(dl)

        refused, _ = deliver(
            _MALLORY_ID,
            "https://example.org/activities/offer_stranger_expiry_2",
            offerer=_MALLORY_ID,
        )

        assert refused is HandlerDisposition.REFUSED
        assert _semantic_types(dl) == entries_before

    @pytest.mark.spec("CM-21-019")
    @pytest.mark.spec("HP-01-003")
    def test_a_recorded_offer_id_resent_by_another_sender_is_refused(
        self, make_payload
    ):
        """Only the owner the CASE_MANAGER made the Offer for redelivers the
        proposal behind it."""
        case_id = "https://example.org/cases/case_ot_offer_reused_id"
        dl, deliver, trigger_activity = _ownership_offer_harness(
            make_payload, case_id
        )
        offer_id = "https://example.org/activities/offer_reused_id"
        first, _ = deliver(_COORDINATOR_ID, offer_id)
        assert first is HandlerDisposition.APPLIED
        entries_before = _semantic_types(dl)

        again, _ = deliver(_MALLORY_ID, offer_id, offerer=_MALLORY_ID)

        assert again is HandlerDisposition.REFUSED
        assert _semantic_types(dl) == entries_before
        trigger_activity.offer_case_ownership_transfer.assert_called_once()


def _transferee_replica(case_id: str, *, holds_case: bool = True):
    """The transferee's (coordinator's) store, holding a replica of the case."""
    from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_COORDINATOR_ID)
    case = as_VulnerabilityCase(
        id_=case_id, name="Replica", attributed_to=_VENDOR_ID
    )
    if holds_case:
        seed_case_manager_participant(dl, case, _CASE_ACTOR_ID)
        seed_case_owner_participant(dl, case, _VENDOR_ID)
        seed_case_participant(dl, case, _COORDINATOR_ID)
        dl.create(case)
    return dl, case


def _offer_at_transferee(dl, make_payload, case, sender, offer_id):
    """Deliver an Offer of *case* to the coordinator, sent by *sender*."""
    offer = offer_case_ownership_transfer_activity(
        case,
        target=_COORDINATOR_ID,
        actor=sender,
        to=[_COORDINATOR_ID],
        id_=offer_id,
    )
    result = OfferCaseOwnershipTransferReceivedUseCase(
        dl,
        make_payload(offer, receiving_actor_id=_COORDINATOR_ID),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
    ).execute()
    return result, offer


class TestOfferAtTheTransferee:
    """CM-21-019, PCR-03-001: the transferee takes the Offer only from the
    CASE_MANAGER, which made it from the owner's proposal."""

    @pytest.mark.spec("CM-21-019")
    @pytest.mark.spec("PCR-03-001")
    def test_transferee_takes_the_case_managers_offer(self, make_payload):
        case_id = "https://example.org/cases/case_ot_transferee_cm"
        dl, case = _transferee_replica(case_id)

        result, offer = _offer_at_transferee(
            dl,
            make_payload,
            case,
            _CASE_ACTOR_ID,
            "https://example.org/activities/offer_transferee_cm",
        )

        assert result.disposition is HandlerDisposition.APPLIED
        assert_held_only_as_received(dl, offer.id_)

    @pytest.mark.spec("CM-21-019")
    @pytest.mark.spec("PCR-03-001")
    @pytest.mark.parametrize("sender", [_VENDOR_ID, _MALLORY_ID])
    def test_transferee_refuses_an_offer_not_from_the_case_manager(
        self, make_payload, sender
    ):
        """Even an Offer from the Case Owner itself is refused: the owner
        proposes to the CASE_MANAGER, which makes the Offer."""
        case_id = "https://example.org/cases/case_ot_transferee_direct"
        dl, case = _transferee_replica(case_id)

        result, offer = _offer_at_transferee(
            dl,
            make_payload,
            case,
            sender,
            "https://example.org/activities/offer_transferee_direct",
        )

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None and "CASE_MANAGER" in result.reason
        assert dl.read(offer.id_) is None
        assert dl.outbox_list() == []

    @pytest.mark.spec("CM-21-019")
    @pytest.mark.spec("PCR-03-001")
    def test_transferee_holding_no_case_refuses_the_offer(self, make_payload):
        """With no replica there is no CASE_MANAGER to recognise."""
        case_id = "https://example.org/cases/case_ot_transferee_no_case"
        dl, case = _transferee_replica(case_id, holds_case=False)

        result, offer = _offer_at_transferee(
            dl,
            make_payload,
            case,
            _CASE_ACTOR_ID,
            "https://example.org/activities/offer_transferee_no_case",
        )

        assert result.disposition is HandlerDisposition.REFUSED
        assert dl.read(offer.id_) is None


#: A copy the CASE_MANAGER relays to the vendor's replica names the replica
#: too, so the addressee door admits it and the sender guard decides (HP-01-005).
_REPLICA_TO = [_CASE_ACTOR_ID, _VENDOR_ID]


def _vendor_replica(case_id: str):
    """The vendor's replica of a case managed by another actor, and an Offer."""
    from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_VENDOR_ID)
    case = as_VulnerabilityCase(
        id_=case_id, name="Replica", attributed_to=_VENDOR_ID
    )
    seed_case_manager_participant(dl, case, _CASE_ACTOR_ID)
    seed_case_owner_participant(dl, case, _VENDOR_ID)
    seed_case_participant(dl, case, _COORDINATOR_ID)
    dl.create(case)
    offer = offer_case_ownership_transfer_activity(
        case,
        target=_COORDINATOR_ID,
        actor=_CASE_ACTOR_ID,
        id_=f"{case_id}/offer",
    )
    # The vendor's own proposal behind it, which a withdrawal names.
    _PROPOSAL_OF[offer.id_] = _proposal(
        case, _COORDINATOR_ID, f"{case_id}/proposal"
    )
    return dl, offer


class TestAcceptAtAReplica:
    """PCR-03-001: a participant replica takes the change only from the CASE_MANAGER."""

    @pytest.mark.spec("CM-21-011")
    @pytest.mark.spec("PCR-03-001")
    def test_accept_from_the_transferee_is_refused_at_a_replica(
        self, make_payload
    ):
        case_id = "https://example.org/cases/case_ot_replica_refused"
        dl, offer = _vendor_replica(case_id)
        roles_before = _owner_roles(dl, case_id)

        result = _accept(dl, make_payload, offer, to=_REPLICA_TO)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None and "CASE_MANAGER" in result.reason
        _assert_nothing_changed(dl, case_id, roles_before, [])
        assert dl.outbox_list() == []

    @pytest.mark.spec("PCR-03-001")
    @pytest.mark.spec("HP-01-005")
    def test_accept_from_the_case_manager_is_refused_at_a_replica(
        self, make_payload
    ):
        """The sender guard admits it, but a replica is not the CASE_MANAGER
        it was addressed to: it applies the change only from the ledger
        fan-out (RSH-08-003), so it refuses the copy (HP-01-005)."""
        case_id = "https://example.org/cases/case_ot_replica_admitted"
        dl, offer = _vendor_replica(case_id)

        result = _accept(
            dl, make_payload, offer, sender=_CASE_ACTOR_ID, to=_REPLICA_TO
        )

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None
        assert "not the CASE_MANAGER" in result.reason
        assert dl.outbox_list() == []
        assert _owner(dl, case_id) == _VENDOR_ID
        assert _semantic_types(dl) == []


# ---------------------------------------------------------------------------
# CM-21-012 – CM-21-014: the transferee's Reject is ledgered, sender-checked,
# and closes the Offer, after which the case may be offered again.
# ---------------------------------------------------------------------------


def _reject(
    dl, make_payload, offer, sender=_COORDINATOR_ID, reject=None, to=None
):
    """Deliver the transferee's (or *sender*'s) Reject of *offer* to *dl*."""
    if reject is None:
        reject = reject_case_ownership_transfer_activity(
            offer, actor=sender, to=to or [_CASE_ACTOR_ID]
        )
    return RejectCaseOwnershipTransferReceivedUseCase(
        dl,
        make_payload(reject, receiving_actor_id=dl.actor_id),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
        trigger_activity=TriggerActivityAdapter(dl),
    ).execute()


def _announces(dl, outbox_before: list[str]) -> list[Any]:
    """The ``Announce`` activities queued since *outbox_before*."""
    return [
        item
        for item in (
            dl.read(i) for i in dl.outbox_list() if i not in outbox_before
        )
        if getattr(getattr(item, "type_", None), "value", None) == "Announce"
    ]


class TestRejectOfOwnershipTransfer:
    """CM-21-012 – CM-21-014: the ownership-transfer Reject at the CASE_MANAGER."""

    @pytest.mark.spec("CM-21-012")
    @pytest.mark.spec("CLP-02-012")
    def test_transferee_reject_is_ledgered_and_broadcast(self, make_payload):
        """The decline commits an entry and announces it; ownership stays."""
        case_id = "https://example.org/cases/case_ot_reject"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, offer = deliver(
            _COORDINATOR_ID, "https://example.org/activities/offer_reject"
        )
        roles_before = _owner_roles(dl, case_id)
        outbox_before = dl.outbox_list()

        result = _reject(dl, make_payload, offer)

        assert result.disposition is HandlerDisposition.APPLIED
        assert _semantic_types(dl).count("reject_case_ownership_transfer") == 1
        assert _announces(dl, outbox_before), (
            "the Reject's entry must be broadcast as Announce(CaseLedgerEntry)"
        )
        assert _owner(dl, case_id) == _VENDOR_ID
        assert _owner_roles(dl, case_id) == roles_before

    @pytest.mark.spec("CM-21-013")
    @pytest.mark.spec("HP-01-006")
    def test_reject_from_a_non_transferee_changes_nothing(self, make_payload):
        """The Offer names the coordinator; the vendor itself declines it."""
        case_id = "https://example.org/cases/case_ot_reject_impostor"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, offer = deliver(
            _COORDINATOR_ID, "https://example.org/activities/offer_rj_imp"
        )
        roles_before = _owner_roles(dl, case_id)
        entries_before = _semantic_types(dl)
        outbox_before = dl.outbox_list()

        result = _reject(dl, make_payload, offer, sender=_VENDOR_ID)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None
        assert "is not the transferee" in result.reason
        _assert_nothing_changed(dl, case_id, roles_before, entries_before)
        assert dl.outbox_list() == outbox_before
        # The Offer is still open: its transferee may still accept it.
        assert (
            _accept(dl, make_payload, offer).disposition
            is HandlerDisposition.APPLIED
        )

    @pytest.mark.spec("HP-01-003")
    def test_redelivered_reject_is_skipped(self, make_payload):
        """The Reject that closed the Offer, delivered again, is the same answer."""
        case_id = "https://example.org/cases/case_ot_reject_again"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, offer = deliver(
            _COORDINATOR_ID, "https://example.org/activities/offer_rj_again"
        )
        reject = reject_case_ownership_transfer_activity(
            offer, actor=_COORDINATOR_ID, to=[_CASE_ACTOR_ID]
        )
        first = _reject(dl, make_payload, offer, reject=reject)
        entries_after_first = _semantic_types(dl)
        outbox_after_first = dl.outbox_list()

        again = _reject(dl, make_payload, offer, reject=reject)

        assert first.disposition is HandlerDisposition.APPLIED
        assert again.disposition is HandlerDisposition.SKIPPED
        assert _semantic_types(dl) == entries_after_first
        assert dl.outbox_list() == outbox_after_first

    @pytest.mark.spec("CM-21-011")
    @pytest.mark.spec("CM-21-014")
    def test_accept_after_a_reject_is_refused(self, make_payload):
        """A declined Offer is closed: its transferee can no longer accept it."""
        case_id = "https://example.org/cases/case_ot_reject_then_accept"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, offer = deliver(
            _COORDINATOR_ID, "https://example.org/activities/offer_rj_acc"
        )
        assert (
            _reject(dl, make_payload, offer).disposition
            is HandlerDisposition.APPLIED
        )
        roles_before = _owner_roles(dl, case_id)
        entries_before = _semantic_types(dl)

        late = _accept(dl, make_payload, offer)

        assert late.disposition is HandlerDisposition.REFUSED
        assert late.reason is not None and "already closed" in late.reason
        _assert_nothing_changed(dl, case_id, roles_before, entries_before)

    @pytest.mark.spec("CM-21-013")
    @pytest.mark.spec("CM-21-014")
    def test_reject_after_an_accept_is_refused(self, make_payload):
        """An accepted Offer is closed: a later Reject of it is refused."""
        case_id = "https://example.org/cases/case_ot_accept_then_reject"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, offer = deliver(
            _COORDINATOR_ID, "https://example.org/activities/offer_acc_rj"
        )
        assert (
            _accept(dl, make_payload, offer).disposition
            is HandlerDisposition.APPLIED
        )
        entries_before = _semantic_types(dl)

        late = _reject(dl, make_payload, offer)

        assert late.disposition is HandlerDisposition.REFUSED
        assert late.reason is not None and "already closed" in late.reason
        assert _semantic_types(dl) == entries_before
        assert _owner(dl, case_id) == _COORDINATOR_ID

    @pytest.mark.spec("CM-21-014")
    def test_new_offer_after_a_reject_is_admitted_even_to_the_decliner(
        self, make_payload
    ):
        """No memory of who declined: the case may be offered to it again."""
        case_id = "https://example.org/cases/case_ot_reoffer_decliner"
        dl, deliver, trigger_activity = _ownership_offer_harness(
            make_payload, case_id
        )
        _, first = deliver(
            _COORDINATOR_ID, "https://example.org/activities/offer_rj_re_1"
        )
        assert (
            _reject(dl, make_payload, first).disposition
            is HandlerDisposition.APPLIED
        )

        second, offer = deliver(
            _COORDINATOR_ID, "https://example.org/activities/offer_rj_re_2"
        )

        assert second is HandlerDisposition.APPLIED
        assert trigger_activity.offer_case_ownership_transfer.call_count == 2
        # And the new Offer is open: its transferee may accept it.
        assert (
            _accept(dl, make_payload, offer).disposition
            is HandlerDisposition.APPLIED
        )
        assert _owner(dl, case_id) == _COORDINATOR_ID

    @pytest.mark.spec("CLP-10-018")
    def test_reject_naming_no_case_is_refused(self, make_payload):
        dl, _, _ = _ownership_offer_harness(
            make_payload, "https://example.org/cases/case_ot_reject_nocase"
        )
        event = _reply_naming_no_case(
            dl,
            make_payload,
            reject_case_ownership_transfer_activity,
            _COORDINATOR_ID,
        )

        result = RejectCaseOwnershipTransferReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None and "names no case" in result.reason
        assert _semantic_types(dl) == []
        assert _archived(dl, event.activity_id)


class TestRejectAtAReplica:
    """PCR-03-001: a replica takes the Reject only from the CASE_MANAGER."""

    @pytest.mark.spec("CM-21-013")
    @pytest.mark.spec("PCR-03-001")
    def test_reject_from_the_transferee_is_refused_at_a_replica(
        self, make_payload
    ):
        case_id = "https://example.org/cases/case_ot_rj_replica_refused"
        dl, offer = _vendor_replica(case_id)
        roles_before = _owner_roles(dl, case_id)

        result = _reject(dl, make_payload, offer, to=_REPLICA_TO)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None and "CASE_MANAGER" in result.reason
        _assert_nothing_changed(dl, case_id, roles_before, [])
        assert dl.outbox_list() == []

    @pytest.mark.spec("CM-21-012")
    @pytest.mark.spec("PCR-03-001")
    @pytest.mark.spec("HP-01-005")
    def test_reject_from_the_case_manager_is_refused_at_a_replica(
        self, make_payload
    ):
        """Admitted, but a replica is not the CASE_MANAGER: it refuses the
        copy, commits nothing and keeps the owner (HP-01-005)."""
        case_id = "https://example.org/cases/case_ot_rj_replica_admitted"
        dl, offer = _vendor_replica(case_id)
        roles_before = _owner_roles(dl, case_id)

        result = _reject(
            dl, make_payload, offer, sender=_CASE_ACTOR_ID, to=_REPLICA_TO
        )

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None
        assert "not the CASE_MANAGER" in result.reason
        _assert_nothing_changed(dl, case_id, roles_before, [])
        assert dl.outbox_list() == []


@pytest.mark.spec("CM-21-005")
@pytest.mark.spec("CM-21-014")
def test_transferee_takes_the_offer_its_replica_holds_open(make_payload):
    """The one-open-Offer rule is the CASE_MANAGER's alone.

    The transferee's replica holds the ledgered Offer, still open; judged
    there, the Offer it is sent would read as a second one.
    """
    from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

    case_id = "https://example.org/cases/case_ot_offer_at_transferee"
    cm, deliver, _ = _ownership_offer_harness(make_payload, case_id)
    disposition, offer = deliver(
        _COORDINATOR_ID, "https://example.org/activities/offer_ft"
    )
    assert disposition is HandlerDisposition.APPLIED
    transferee = SqliteDataLayer(
        "sqlite:///:memory:", actor_id=_COORDINATOR_ID
    )
    case = as_VulnerabilityCase(
        id_=case_id, name="Replica", attributed_to=_VENDOR_ID
    )
    seed_case_manager_participant(transferee, case, _CASE_ACTOR_ID)
    seed_case_owner_participant(transferee, case, _VENDOR_ID)
    seed_case_participant(transferee, case, _COORDINATOR_ID)
    transferee.create(case)
    for entry in cm.list_objects("CaseLedgerEntry"):
        transferee.create(entry)
    assert "offer_case_ownership_transfer" in _semantic_types(transferee)

    result = OfferCaseOwnershipTransferReceivedUseCase(
        transferee,
        make_payload(offer, receiving_actor_id=_COORDINATOR_ID),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(transferee),
    ).execute()

    assert result.disposition is HandlerDisposition.APPLIED
    assert_held_only_as_received(transferee, offer.id_)


# ---------------------------------------------------------------------------
# CM-21-015: the owner withdraws its proposal with Undo; the CASE_MANAGER
# ledgers the withdrawal of the Offer it made from it, which closes the Offer
# (CM-21-014, ADR-0148).
# ---------------------------------------------------------------------------


def _undo(dl, make_payload, offer, sender=_VENDOR_ID, undo=None, to=None):
    """Deliver the owner's (or *sender*'s) Undo of the proposal behind
    *offer* to *dl*; *offer* may be the proposal itself."""
    if undo is None:
        undo = undo_case_ownership_transfer_activity(
            _PROPOSAL_OF.get(offer.id_, offer),
            actor=sender,
            to=to or [_CASE_ACTOR_ID],
        )
    return UndoCaseOwnershipTransferReceivedUseCase(
        dl,
        make_payload(undo, receiving_actor_id=dl.actor_id),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
        trigger_activity=TriggerActivityAdapter(dl),
    ).execute()


class TestWithdrawalOfOwnershipTransfer:
    """CM-21-015: the ownership-transfer Undo at the CASE_MANAGER."""

    @pytest.mark.spec("CM-21-015")
    def test_offerer_withdrawal_is_ledgered_and_broadcast(self, make_payload):
        """The withdrawal commits an entry and announces it; ownership stays."""
        case_id = "https://example.org/cases/case_ot_undo"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, offer = deliver(
            _COORDINATOR_ID, "https://example.org/activities/offer_undo"
        )
        roles_before = _owner_roles(dl, case_id)
        outbox_before = dl.outbox_list()

        result = _undo(dl, make_payload, offer)

        assert result.disposition is HandlerDisposition.APPLIED
        assert _semantic_types(dl).count("undo_case_ownership_transfer") == 1
        assert _announces(dl, outbox_before), (
            "the Undo's entry must be broadcast as Announce(CaseLedgerEntry)"
        )
        assert _owner(dl, case_id) == _VENDOR_ID
        assert _owner_roles(dl, case_id) == roles_before

    @pytest.mark.spec("CM-21-015")
    @pytest.mark.spec("CM-24-002")
    def test_attributed_to_on_the_proposal_does_not_move_the_offerer(
        self, make_payload
    ):
        """The Offer speaks for the owner that sent the proposal.

        An ``attributedTo`` on the proposal is a claim nothing checks, so the
        offerer is still the sender: its withdrawal is admitted, and the
        actor named in ``attributedTo`` is not the offerer.
        """
        case_id = "https://example.org/cases/case_ot_undo_claimed"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        disposition, offer = deliver(
            _COORDINATOR_ID,
            "https://example.org/activities/offer_undo_claimed",
            attributed_to="https://example.org/actors/someone_else",
        )
        assert disposition is HandlerDisposition.APPLIED
        entries_before = _semantic_types(dl)
        roles_before = _owner_roles(dl, case_id)

        claimed = _undo(
            dl,
            make_payload,
            offer,
            sender="https://example.org/actors/someone_else",
        )

        assert claimed.disposition is HandlerDisposition.REFUSED
        assert claimed.reason is not None
        assert "is not the offerer" in claimed.reason
        _assert_nothing_changed(dl, case_id, roles_before, entries_before)

        result = _undo(dl, make_payload, offer)

        assert result.disposition is HandlerDisposition.APPLIED
        assert "undo_case_ownership_transfer" in _semantic_types(dl)

    @pytest.mark.spec("CM-21-015")
    @pytest.mark.spec("HP-01-006")
    def test_withdrawal_from_a_non_offerer_changes_nothing(self, make_payload):
        """The transferee cannot withdraw the Offer made to it."""
        case_id = "https://example.org/cases/case_ot_undo_impostor"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, offer = deliver(
            _COORDINATOR_ID, "https://example.org/activities/offer_undo_imp"
        )
        roles_before = _owner_roles(dl, case_id)
        entries_before = _semantic_types(dl)
        outbox_before = dl.outbox_list()

        result = _undo(dl, make_payload, offer, sender=_COORDINATOR_ID)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None
        assert "is not the offerer" in result.reason
        _assert_nothing_changed(dl, case_id, roles_before, entries_before)
        assert dl.outbox_list() == outbox_before
        # The Offer is still open: its transferee may still accept it.
        assert (
            _accept(dl, make_payload, offer).disposition
            is HandlerDisposition.APPLIED
        )

    @pytest.mark.spec("CM-21-015")
    def test_withdrawal_from_an_offerer_that_is_not_case_owner_is_refused(
        self, make_payload
    ):
        """Only a Case Owner withdraws: the offerer, once it no longer holds
        ``CASE_OWNER``, cannot withdraw the Offer it made."""
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.enums.roles import CVDRole

        case_id = "https://example.org/cases/case_ot_undo_not_owner"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, offer = deliver(
            "https://example.org/users/vendor2",
            "https://example.org/activities/offer_undo_not_owner",
        )
        # The offerer loses the role while its Offer is open.
        case = dl.read(case_id)
        assert isinstance(case, VulnerabilityCase)
        record = dl.read(case.actor_participant_index[_VENDOR_ID])
        assert isinstance(record, CaseParticipant)
        record.remove_role(CVDRole.CASE_OWNER)
        dl.save(record)
        entries_before = _semantic_types(dl)

        result = _undo(dl, make_payload, offer, sender=_VENDOR_ID)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None
        assert "does not hold CASE_OWNER" in result.reason
        assert _semantic_types(dl) == entries_before

    @pytest.mark.spec("CM-21-015")
    def test_withdrawal_of_a_proposal_never_made_into_an_offer_is_refused(
        self, make_payload
    ):
        case_id = "https://example.org/cases/case_ot_undo_unrecorded"
        dl, _, _ = _ownership_offer_harness(make_payload, case_id)
        proposal = _proposal(
            _read_case(dl, case_id),
            _COORDINATOR_ID,
            "https://example.org/activities/offer_undo_unrecorded",
        )

        result = _undo(dl, make_payload, proposal)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None
        assert "never recorded" in result.reason
        assert _semantic_types(dl) == []

    @pytest.mark.spec("CM-21-015")
    def test_withdrawal_closes_the_offer_made_from_the_proposal(
        self, make_payload
    ):
        """The Undo names the proposal; the entry closes the CASE_MANAGER's
        Offer, so the transferee can no longer accept it (ADR-0148)."""
        from vultron.core.participants.ownership_offer import (
            recorded_ownership_offer,
        )

        case_id = "https://example.org/cases/case_ot_undo_closes"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, offer = deliver(
            _COORDINATOR_ID, "https://example.org/activities/offer_undo_closes"
        )
        assert (
            recorded_ownership_offer(dl, case_id, offer.id_).answer_id is None
        )

        undo = undo_case_ownership_transfer_activity(
            _PROPOSAL_OF[offer.id_], actor=_VENDOR_ID, to=[_CASE_ACTOR_ID]
        )
        assert cast(Any, undo.object_).id_ != offer.id_
        result = _undo(dl, make_payload, offer, undo=undo)

        assert result.disposition is HandlerDisposition.APPLIED
        closed = recorded_ownership_offer(dl, case_id, offer.id_)
        assert closed.answer_id == undo.id_
        assert closed.closed_by_semantic_type == "undo_case_ownership_transfer"

    @pytest.mark.spec("HP-01-003")
    @pytest.mark.spec("CM-21-015")
    def test_redelivered_withdrawal_is_skipped(self, make_payload):
        """The Undo that closed the Offer, delivered again, changes nothing."""
        case_id = "https://example.org/cases/case_ot_undo_again"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, offer = deliver(
            _COORDINATOR_ID, "https://example.org/activities/offer_undo_again"
        )
        undo = undo_case_ownership_transfer_activity(
            _PROPOSAL_OF[offer.id_], actor=_VENDOR_ID, to=[_CASE_ACTOR_ID]
        )
        first = _undo(dl, make_payload, offer, undo=undo)
        entries_after_first = _semantic_types(dl)
        outbox_after_first = dl.outbox_list()

        again = _undo(dl, make_payload, offer, undo=undo)

        assert first.disposition is HandlerDisposition.APPLIED
        assert again.disposition is HandlerDisposition.SKIPPED
        assert _semantic_types(dl) == entries_after_first
        assert dl.outbox_list() == outbox_after_first

    @pytest.mark.spec("HP-01-003")
    @pytest.mark.spec("CM-21-015")
    def test_redelivered_withdrawal_is_skipped_after_ownership_moved_on(
        self, make_payload
    ):
        """A redelivered Undo is a duplicate, not a new withdrawal: it is
        ``SKIPPED`` even once a later Offer has moved ownership away from the
        offerer, so the offerer's lost CASE_OWNER role does not refuse it."""
        case_id = "https://example.org/cases/case_ot_undo_again_moved"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, first_offer = deliver(_COORDINATOR_ID, f"{case_id}/offer-1")
        undo = undo_case_ownership_transfer_activity(
            _PROPOSAL_OF[first_offer.id_],
            actor=_VENDOR_ID,
            to=[_CASE_ACTOR_ID],
        )
        assert (
            _undo(dl, make_payload, first_offer, undo=undo).disposition
            is HandlerDisposition.APPLIED
        )
        _, second_offer = deliver(_COORDINATOR_ID, f"{case_id}/offer-2")
        assert (
            _accept(dl, make_payload, second_offer).disposition
            is HandlerDisposition.APPLIED
        )
        assert _owner(dl, case_id) == _COORDINATOR_ID
        entries_before = _semantic_types(dl)
        outbox_before = dl.outbox_list()

        again = _undo(dl, make_payload, first_offer, undo=undo)

        assert again.disposition is HandlerDisposition.SKIPPED
        assert _semantic_types(dl) == entries_before
        assert dl.outbox_list() == outbox_before
        assert _owner(dl, case_id) == _COORDINATOR_ID

    @pytest.mark.spec("CM-21-015")
    @pytest.mark.parametrize("answer", ["accept", "reject"])
    def test_withdrawal_of_an_answered_offer_is_refused(
        self, make_payload, answer
    ):
        """An Offer already closed by its transferee cannot be withdrawn."""
        case_id = f"https://example.org/cases/case_ot_{answer}_then_undo"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, offer = deliver(
            _COORDINATOR_ID,
            f"https://example.org/activities/offer_{answer}_undo",
        )
        reply = _accept if answer == "accept" else _reject
        assert (
            reply(dl, make_payload, offer).disposition
            is HandlerDisposition.APPLIED
        )
        entries_before = _semantic_types(dl)
        outbox_before = dl.outbox_list()

        late = _undo(dl, make_payload, offer)

        assert late.disposition is HandlerDisposition.REFUSED
        # After a Reject the offerer is still the Case Owner and learns the
        # Offer is closed; after an Accept it no longer holds CASE_OWNER, so
        # it is refused for standing before the Offer's state is read
        # (decision 2 of #4437).
        expected = (
            "does not hold CASE_OWNER"
            if answer == "accept"
            else "already closed"
        )
        assert late.reason is not None and expected in late.reason
        assert _semantic_types(dl) == entries_before
        # A refusal by a precondition guard (the Offer is already closed) is
        # answered with one refusal notice to the offerer; a refusal by the
        # sender guard (no CASE_OWNER standing) gets none (CLP-05-001,
        # ADR-0141).  Nothing else is queued.
        queued = [
            dl.read(i) for i in dl.outbox_list() if i not in outbox_before
        ]
        assert len(queued) == (0 if answer == "accept" else 1), queued
        assert all(
            getattr(getattr(a, "type_", None), "value", None) == "Reject"
            and getattr(a, "to", None) == [_VENDOR_ID]
            for a in queued
        )

    @pytest.mark.spec("CM-21-015")
    def test_second_withdrawal_of_a_withdrawn_offer_is_refused(
        self, make_payload
    ):
        """A different Undo of an Offer already withdrawn is not a redelivery."""
        case_id = "https://example.org/cases/case_ot_undo_twice"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, offer = deliver(
            _COORDINATOR_ID, "https://example.org/activities/offer_undo_twice"
        )
        assert (
            _undo(dl, make_payload, offer).disposition
            is HandlerDisposition.APPLIED
        )
        entries_before = _semantic_types(dl)

        second = _undo(dl, make_payload, offer)

        assert second.disposition is HandlerDisposition.REFUSED
        assert second.reason is not None
        assert "already closed" in second.reason
        assert _semantic_types(dl) == entries_before

    @pytest.mark.spec("CM-21-014")
    @pytest.mark.spec("CM-21-015")
    @pytest.mark.parametrize("answer", ["accept", "reject"])
    def test_answer_after_a_withdrawal_is_refused(self, make_payload, answer):
        """A withdrawn Offer is closed: its transferee can no longer answer."""
        case_id = f"https://example.org/cases/case_ot_undo_then_{answer}"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, offer = deliver(
            _COORDINATOR_ID,
            f"https://example.org/activities/offer_undo_{answer}",
        )
        assert (
            _undo(dl, make_payload, offer).disposition
            is HandlerDisposition.APPLIED
        )
        roles_before = _owner_roles(dl, case_id)
        entries_before = _semantic_types(dl)

        reply = _accept if answer == "accept" else _reject
        late = reply(dl, make_payload, offer)

        assert late.disposition is HandlerDisposition.REFUSED
        assert late.reason is not None and "already closed" in late.reason
        _assert_nothing_changed(dl, case_id, roles_before, entries_before)

    @pytest.mark.spec("CM-21-014")
    @pytest.mark.spec("CM-21-015")
    def test_new_offer_after_a_withdrawal_is_admitted(self, make_payload):
        """A withdrawal closes the Offer, so the case may be offered again."""
        case_id = "https://example.org/cases/case_ot_undo_reoffer"
        dl, deliver, trigger_activity = _ownership_offer_harness(
            make_payload, case_id
        )
        _, first = deliver(
            _COORDINATOR_ID, "https://example.org/activities/offer_undo_re_1"
        )
        assert (
            _undo(dl, make_payload, first).disposition
            is HandlerDisposition.APPLIED
        )

        second, offer = deliver(
            "https://example.org/users/vendor2",
            "https://example.org/activities/offer_undo_re_2",
        )

        assert second is HandlerDisposition.APPLIED
        assert trigger_activity.offer_case_ownership_transfer.call_count == 2
        assert (
            _accept(
                dl,
                make_payload,
                offer,
                sender="https://example.org/users/vendor2",
            ).disposition
            is HandlerDisposition.APPLIED
        )

    @pytest.mark.spec("CLP-10-018")
    def test_withdrawal_naming_no_case_is_refused(self, make_payload):
        dl, _, _ = _ownership_offer_harness(
            make_payload, "https://example.org/cases/case_ot_undo_nocase"
        )
        proposal = _proposal(
            as_VulnerabilityCase(
                attributed_to=CASE_OWNER_ID,
                id_="https://example.org/cases/elsewhere",
            ),
            _COORDINATOR_ID,
            "https://example.org/activities/proposal_undo_nocase",
        )
        undo = undo_case_ownership_transfer_activity(
            proposal, actor=_VENDOR_ID, to=[_CASE_ACTOR_ID]
        )
        event = make_payload(undo, receiving_actor_id=dl.actor_id)
        event = event.model_copy(update={"inner_context": None})
        assert event.case_id is None

        result = UndoCaseOwnershipTransferReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None and "names no case" in result.reason
        assert _semantic_types(dl) == []
        assert _archived(dl, event.activity_id)


class TestWithdrawalAtAReplica:
    """PCR-03-001: a replica takes the Undo only from the CASE_MANAGER."""

    @pytest.mark.spec("CM-21-015")
    @pytest.mark.spec("PCR-03-001")
    def test_withdrawal_from_the_offerer_is_refused_at_a_replica(
        self, make_payload
    ):
        case_id = "https://example.org/cases/case_ot_undo_replica_refused"
        dl, offer = _vendor_replica(case_id)
        roles_before = _owner_roles(dl, case_id)

        result = _undo(dl, make_payload, offer, to=_REPLICA_TO)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None and "CASE_MANAGER" in result.reason
        _assert_nothing_changed(dl, case_id, roles_before, [])
        assert dl.outbox_list() == []

    @pytest.mark.spec("CM-21-015")
    @pytest.mark.spec("PCR-03-001")
    @pytest.mark.spec("HP-01-005")
    def test_withdrawal_from_the_case_manager_is_refused_at_a_replica(
        self, make_payload
    ):
        """Admitted, but a replica is not the CASE_MANAGER: it refuses the
        copy, commits nothing and keeps the owner (HP-01-005)."""
        case_id = "https://example.org/cases/case_ot_undo_replica_admitted"
        dl, offer = _vendor_replica(case_id)
        roles_before = _owner_roles(dl, case_id)

        result = _undo(
            dl, make_payload, offer, sender=_CASE_ACTOR_ID, to=_REPLICA_TO
        )

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None
        assert "not the CASE_MANAGER" in result.reason
        _assert_nothing_changed(dl, case_id, roles_before, [])
        assert dl.outbox_list() == []


_STRANGER_ID = "https://example.org/users/stranger"


def _closed_offer(make_payload, case_id: str):
    """A CASE_MANAGER store whose one Offer the transferee's Reject closed.

    A Reject leaves the offerer the Case Owner, so each party still has
    standing to reply.
    """
    dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
    _, offer = deliver(_COORDINATOR_ID, f"{case_id}/offer")
    assert _reject(dl, make_payload, offer).disposition is (
        HandlerDisposition.APPLIED
    )
    return dl, offer


def _expired_offer(make_payload, case_id: str):
    """A CASE_MANAGER store whose one Offer's deadline has passed."""
    dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
    deadline = _deadline_shortly()
    _, offer = deliver(_COORDINATOR_ID, f"{case_id}/offer", end_time=deadline)
    _wait_past(deadline)
    return dl, offer


#: Each reply, the sender with standing to send it, and the words naming
#: the standing a stranger lacks.
_REPLIES = {
    "accept": (_accept, _COORDINATOR_ID, "is not the transferee"),
    "reject": (_reject, _COORDINATOR_ID, "is not the transferee"),
    "undo": (_undo, _VENDOR_ID, "is not the offerer"),
}


class TestStandingIsCheckedBeforeTheOfferState:
    """A sender with no standing is refused for that, before the Offer's
    state is read; the rightful party still learns the Offer is closed or
    expired, and a redelivery is still ``SKIPPED`` (HP-01-006, #4437)."""

    @pytest.mark.spec("CM-21-013")
    @pytest.mark.spec("HP-01-006")
    @pytest.mark.parametrize("reply", sorted(_REPLIES))
    def test_a_stranger_replying_to_a_closed_offer_is_refused_for_standing(
        self, make_payload, reply
    ):
        send, _party, no_standing = _REPLIES[reply]
        case_id = f"https://example.org/cases/case_ot_stranger_closed_{reply}"
        dl, offer = _closed_offer(make_payload, case_id)
        entries_before = _semantic_types(dl)

        result = send(dl, make_payload, offer, sender=_STRANGER_ID)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None
        assert no_standing in result.reason
        assert "already closed" not in result.reason
        assert _semantic_types(dl) == entries_before

    @pytest.mark.spec("CM-21-013")
    @pytest.mark.spec("HP-01-006")
    @pytest.mark.parametrize("reply", sorted(_REPLIES))
    def test_a_stranger_replying_to_an_expired_offer_is_refused_for_standing(
        self, make_payload, reply
    ):
        send, _party, no_standing = _REPLIES[reply]
        case_id = f"https://example.org/cases/case_ot_stranger_late_{reply}"
        dl, offer = _expired_offer(make_payload, case_id)
        entries_before = _semantic_types(dl)

        result = send(dl, make_payload, offer, sender=_STRANGER_ID)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None
        assert no_standing in result.reason
        assert "too late" not in result.reason
        # A sender with no standing never makes the CASE_MANAGER write
        # (HP-01-006).
        assert _semantic_types(dl) == entries_before
        assert _owner(dl, case_id) == _VENDOR_ID

    @pytest.mark.spec("CM-21-014")
    @pytest.mark.parametrize("reply", sorted(_REPLIES))
    def test_the_rightful_party_is_refused_for_a_closed_offer(
        self, make_payload, reply
    ):
        send, party, _no_standing = _REPLIES[reply]
        case_id = f"https://example.org/cases/case_ot_party_closed_{reply}"
        dl, offer = _closed_offer(make_payload, case_id)

        result = send(dl, make_payload, offer, sender=party)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None and "already closed" in result.reason

    @pytest.mark.spec("CM-21-016")
    @pytest.mark.parametrize("reply", sorted(_REPLIES))
    def test_the_rightful_party_is_refused_for_an_expired_offer(
        self, make_payload, reply
    ):
        send, party, _no_standing = _REPLIES[reply]
        case_id = f"https://example.org/cases/case_ot_party_late_{reply}"
        dl, offer = _expired_offer(make_payload, case_id)

        result = send(dl, make_payload, offer, sender=party)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None and "too late" in result.reason
        assert f"from '{party}' came too late" in result.reason
        assert _owner(dl, case_id) == _VENDOR_ID


def _close_coordinator(dl, case_id: str) -> None:
    """Record the coordinator's closure: it left the case (RM ``CLOSED``)."""
    from vultron.core.models.case_participant import CaseParticipant
    from vultron.core.models.dimensions import RmDimension
    from vultron.core.models.participant_status import ParticipantStatus
    from vultron.core.states.rm import RM

    case = dl.read(case_id)
    assert isinstance(case, VulnerabilityCase)
    record = dl.read(case.actor_participant_index[_COORDINATOR_ID])
    assert isinstance(record, CaseParticipant)
    record.participant_statuses.append(
        ParticipantStatus(
            context=case_id,
            attributed_to=_COORDINATOR_ID,
            rm=RmDimension(state=RM.CLOSED),
        )
    )
    dl.save(record)


@pytest.mark.spec("CM-23-018")
@pytest.mark.spec("CM-21-011")
@pytest.mark.parametrize("answer", ["accept", "reject"])
def test_a_closed_transferees_answer_is_refused(make_payload, answer):
    """A transferee that left the case after the Offer answers nothing.

    Its answer is REFUSED: ownership does not move, no answer is ledgered
    and nothing is sent (CM-23-018).
    """
    case_id = f"https://example.org/cases/case_ot_closed_{answer}"
    dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
    disposition, offer = deliver(_COORDINATOR_ID, f"{case_id}/offer")
    assert disposition is HandlerDisposition.APPLIED
    _close_coordinator(dl, case_id)
    entries_before = _semantic_types(dl)
    outbox_before = list(dl.outbox_list())

    result = {"accept": _accept, "reject": _reject}[answer](
        dl, make_payload, offer
    )

    assert result.disposition is HandlerDisposition.REFUSED, result.reason
    assert "CM-23-018" in (result.reason or "")
    assert _owner(dl, case_id) == _VENDOR_ID
    assert _semantic_types(dl) == entries_before
    assert list(dl.outbox_list()) == outbox_before


@pytest.mark.spec("OID-01-006")
def test_a_slash_spelled_transferee_is_offered_to_canonically(make_payload):
    """The inner Offer's ``target`` is extracted as the transferee without
    its trailing slash: the Offer names the actor the roster stores."""
    case_id = "https://example.org/cases/case_ot_slash_transferee"
    _dl, deliver, trigger_activity = _ownership_offer_harness(
        make_payload, case_id
    )

    disposition, _ = deliver(_COORDINATOR_ID + "/", f"{case_id}/offer")

    assert disposition is HandlerDisposition.APPLIED
    kwargs = trigger_activity.offer_case_ownership_transfer.call_args.kwargs
    assert kwargs["transferee_id"] == _COORDINATOR_ID
    assert kwargs["to"] == [_COORDINATOR_ID]


@pytest.mark.spec("OID-01-006")
@pytest.mark.spec("CM-24-002")
def test_a_slash_spelled_attribution_is_taken_and_filed_as_received(
    make_payload,
):
    """The transferee takes the CASE_MANAGER's Offer whose ``attributed_to``
    carries a trailing slash, and files it as received: the stored Offer
    keeps the sender's spelling (OID-01-006)."""
    case_id = "https://example.org/cases/case_ot_slash_delegated"
    dl, case = _transferee_replica(case_id)
    offer = offer_case_ownership_transfer_activity(
        case,
        target=_COORDINATOR_ID,
        actor=_CASE_ACTOR_ID,
        to=[_COORDINATOR_ID],
        attributed_to=_VENDOR_ID + "/",
        id_=f"{case_id}/offer",
    )

    result = OfferCaseOwnershipTransferReceivedUseCase(
        dl,
        make_payload(offer, receiving_actor_id=_COORDINATOR_ID),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
    ).execute()

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    assert_held_only_as_received(dl, offer.id_)
    record = received_record(dl, offer.id_)
    assert record is not None
    # Filed as received: the archived body keeps the sender's spelling.
    assert json.loads(record.received_body)["attributedTo"] == _VENDOR_ID + "/"
    assert _owner(dl, case_id) == _VENDOR_ID


@pytest.mark.spec("OID-01-006")
@pytest.mark.spec("CM-21-005")
@pytest.mark.spec("CM-21-011")
def test_accept_of_the_offer_to_a_slash_spelled_transferee_is_applied(
    make_payload,
):
    """The owner names the transferee with a trailing slash; the Offer the
    CASE_MANAGER makes names it canonically, and the transferee's Accept
    makes it the owner, stored without the slash."""
    case_id = "https://example.org/cases/case_ot_slash_accept"
    dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
    disposition, offer = deliver(
        _COORDINATOR_ID + "/", "https://example.org/activities/offer_slash"
    )
    assert disposition is HandlerDisposition.APPLIED

    result = _accept(dl, make_payload, offer)

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    assert _owner(dl, case_id) == _COORDINATOR_ID
    roles = _owner_roles(dl, case_id)
    assert roles[_COORDINATOR_ID] is True
    assert _COORDINATOR_ID + "/" not in roles
    assert roles[_VENDOR_ID] is False
