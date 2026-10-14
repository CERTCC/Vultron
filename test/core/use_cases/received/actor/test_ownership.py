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
"""Tests for ownership transfer received use cases."""

import time
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_owner_participant,
    seed_case_participant,
)
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.case.nodes.store_received_object import (
    StoreReceivedObjectNode,
)
from vultron.core.models._helpers import now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.protocol_pair import (
    OFFER_CASE_OWNERSHIP_TRANSFER_EXPIRED_EVENT_TYPE,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.actor.ownership import (
    AcceptCaseOwnershipTransferReceivedUseCase,
    OfferCaseOwnershipTransferReceivedUseCase,
    RejectCaseOwnershipTransferReceivedUseCase,
    UndoCaseOwnershipTransferReceivedUseCase,
)
from vultron.wire.as2.factories import (
    accept_case_ownership_transfer_activity,
    offer_case_ownership_transfer_activity,
    reject_case_ownership_transfer_activity,
    undo_case_ownership_transfer_activity,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)


class TestOwnershipTransferUseCases:
    """Tests for offer/accept/reject ownership transfer use cases."""

    def test_offer_case_ownership_transfer_persists_offer(self, make_payload):
        """OfferCaseOwnershipTransferReceivedUseCase persists the offer."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )

        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_ot1",
            name="OT Case 1",
        )
        activity = offer_case_ownership_transfer_activity(
            case,
            target="https://example.org/users/coordinator",
            actor="https://example.org/users/vendor",
            to=["https://test.example/api/v2/actors/test-actor"],
        )
        event = make_payload(activity)

        result = OfferCaseOwnershipTransferReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        stored = dl.get(activity.type_.value, activity.id_)
        assert stored is not None
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
        assert "accept_case_ownership_transfer" in _event_types(dl)

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
            id_="https://example.org/cases/case_ot_missing", name="Missing"
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
        ).execute()

        # Nothing to establish the sender's standing against, so it is
        # refused (HP-01-006); the case was never held and is still absent.
        assert result.disposition == HandlerDisposition.REFUSED
        assert dl.read("https://example.org/cases/case_ot_missing") is None

    @pytest.mark.spec("HP-01-003")
    def test_accept_ownership_transfer_without_case_is_refused(self):
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://example.org/users/coordinator",
        )
        event = MagicMock(case_id=None, receiving_actor_id=None)

        result = AcceptCaseOwnershipTransferReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition == HandlerDisposition.REFUSED

    def test_offer_cascade_forwards_to_transferee_via_case_actor_outbox(
        self, make_payload
    ):
        """CaseActor builds a new forwarded Offer and queues it in its own outbox.

        When the receiving actor is the CaseActor (CASE_MANAGER), the use case
        must NOT re-queue the original offer in the transferee's outbox slot.
        Instead it builds a new Offer(VulnerabilityCase, actor=case_actor_id,
        attributed_to=vendor_id, to=[transferee_id]) and enqueues it in the
        CaseActor's outbox so the registered outbox monitor delivers it to
        the transferee's inbox (CM-21-005, ADR-0053).
        """
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.base.objects.actors import as_Service
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

        case_actor_id = "https://example.org/actors/case-actor"
        vendor_id = "https://example.org/users/vendor"
        transferee_id = "https://example.org/users/coordinator"
        forwarded_id = "https://example.org/activities/offer_ot4_fwd"

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=case_actor_id,
        )

        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_ot4",
            name="OT Cascade Case",
            attributed_to=vendor_id,
        )
        # Seed CASE_MANAGER participant so _resolve_case_manager_id succeeds.
        case_manager_participant = as_CaseParticipant(
            attributed_to=case_actor_id,
            context=case.id_,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        case.actor_participant_index[case_actor_id] = (
            case_manager_participant.id_
        )
        case.case_participants.append(case_manager_participant.id_)
        dl.create(case)
        dl.create(case_manager_participant)

        transferee_actor = as_Service(id_=transferee_id, name="Coordinator")
        activity = offer_case_ownership_transfer_activity(
            case,
            target=transferee_actor,
            actor=vendor_id,
            to=[case_actor_id],
            id_="https://example.org/activities/offer_ot4",
        )
        event = make_payload(activity, receiving_actor_id=case_actor_id)

        # TriggerActivityPort mock: returns (forwarded_id, {}) when called.
        trigger_activity = MagicMock()
        trigger_activity.offer_case_ownership_transfer.return_value = (
            forwarded_id,
            {},
        )

        OfferCaseOwnershipTransferReceivedUseCase(
            dl,
            event,
            trigger_activity=trigger_activity,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        # trigger_activity.offer_case_ownership_transfer must be called with
        # actor=case_actor_id, to=[transferee_id], attributed_to=vendor_id.
        trigger_activity.offer_case_ownership_transfer.assert_called_once_with(
            case_id=case.id_,
            transferee_id=transferee_id,
            actor=case_actor_id,
            to=[transferee_id],
            attributed_to=vendor_id,
            # The Offer named no deadline, so the forward carries none.
            end_time=None,
        )

        # Forwarded offer must land in CaseActor's outbox (not transferee's slot).
        case_actor_outbox = dl.clone_for_actor(case_actor_id).outbox_list()
        assert forwarded_id in case_actor_outbox

        # Original offer must NOT be in the transferee's outbox slot.
        transferee_outbox = dl.clone_for_actor(transferee_id).outbox_list()
        assert activity.id_ not in transferee_outbox

    def test_offer_cascade_forward_lives_in_the_bt_not_in_execute(
        self, make_payload, monkeypatch
    ):
        """The CM-21-005 forward is owned by the BT, not by ``execute()``.

        ``execute()`` must build exactly one tree —
        ``create_offer_ownership_transfer_tree`` — and hand the
        ``TriggerActivityPort`` to ``BTBridge`` so
        ``ForwardOfferToTransfereeNode`` can emit inside the tree
        (CLP-10-005, CM-21-005, ADR-0022).

        Regression guard: the procedural ``add_activity_to_outbox`` call that
        PR #2882 removed was silently restored by the conflict resolution in
        PR #2909's catch-up merge.  Both shapes queue the same activity id in
        the same outbox, so every behavioural assertion above kept passing —
        only the tree identity distinguishes them.
        """
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.use_cases.received.actor import ownership
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.base.objects.actors import as_Service
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

        assert not hasattr(ownership, "add_activity_to_outbox"), (
            "OfferCaseOwnershipTransferReceivedUseCase must not import"
            " add_activity_to_outbox — the outbox write belongs to"
            " ForwardOfferToTransfereeNode (CLP-10-005)"
        )

        case_actor_id = "https://example.org/actors/case-actor-bt"
        vendor_id = "https://example.org/users/vendor-bt"
        transferee_id = "https://example.org/users/coordinator-bt"

        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=case_actor_id)

        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_ot6",
            name="OT BT-Wiring Case",
            attributed_to=vendor_id,
        )
        case_manager_participant = as_CaseParticipant(
            attributed_to=case_actor_id,
            context=case.id_,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        case.actor_participant_index[case_actor_id] = (
            case_manager_participant.id_
        )
        case.case_participants.append(case_manager_participant.id_)
        dl.create(case)
        dl.create(case_manager_participant)

        activity = offer_case_ownership_transfer_activity(
            case,
            target=as_Service(id_=transferee_id, name="Coordinator BT"),
            actor=vendor_id,
            to=[case_actor_id],
            id_="https://example.org/activities/offer_ot6",
        )
        event = make_payload(activity, receiving_actor_id=case_actor_id)

        calls: list[dict] = []
        real_factory = ownership.create_offer_ownership_transfer_tree

        def _spy(**kwargs):
            calls.append(kwargs)
            return real_factory(**kwargs)

        monkeypatch.setattr(
            ownership, "create_offer_ownership_transfer_tree", _spy
        )

        trigger_activity = MagicMock()
        trigger_activity.offer_case_ownership_transfer.return_value = (
            "https://example.org/activities/offer_ot6_fwd",
            {},
        )

        OfferCaseOwnershipTransferReceivedUseCase(
            dl,
            event,
            trigger_activity=trigger_activity,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        # The Offer the accept trigger reads back by id is written by a store
        # node of the same tree, not by execute() (CLP-10-005, AC-4).
        assert all(
            isinstance(c.pop("store_offer", None), StoreReceivedObjectNode)
            for c in calls
        )
        assert calls == [
            {
                "case_id": case.id_,
                "transferee_id": transferee_id,
                "original_actor_id": vendor_id,
                # The Offer's own id, so the CM-21-014 guard does not read a
                # redelivery as an earlier open Offer.
                "offer_id": activity.id_,
                # No end_time on the Offer, so none for the forward to carry.
                "answer_deadline": None,
            }
        ], (
            "execute() must build the ownership-transfer tree once, with the"
            " transferee and original offerer, so the forward runs inside the"
            f" CM-gated effect section. Calls: {calls!r}"
        )
        # The port has to reach the node through BTBridge, or the tree runs
        # with no factory and the forward silently degrades to a WARNING.
        trigger_activity.offer_case_ownership_transfer.assert_called_once()

    def test_forwarded_offer_attributes_the_requesting_participant(
        self, make_payload
    ):
        """The forwarded Offer must carry the vendor, not the CaseActor.

        A delegated ownership-transfer Offer arrives with ``actor`` = CaseActor
        and ``attributed_to`` = the participant who asked for the transfer
        (CM-24-001, CM-24-002).  When the CaseActor forwards it, the forwarded
        Offer's ``attributed_to`` must still name that participant — otherwise
        the CaseActor attributes the vendor's intent to itself and no receiver,
        nor any replica materialising the offer from the ledger snapshot, can
        recover who offered.
        """
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.base.objects.actors import as_Service
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

        case_actor_id = "https://example.org/actors/case-actor-attr"
        vendor_id = "https://example.org/users/vendor-attr"
        transferee_id = "https://example.org/users/coordinator-attr"

        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=case_actor_id)

        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_ot7",
            name="OT Attribution Case",
            attributed_to=vendor_id,
        )
        case_manager_participant = as_CaseParticipant(
            attributed_to=case_actor_id,
            context=case.id_,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        case.actor_participant_index[case_actor_id] = (
            case_manager_participant.id_
        )
        case.case_participants.append(case_manager_participant.id_)
        dl.create(case)
        dl.create(case_manager_participant)

        # The delegated shape: CaseActor sends, vendor is attributed.
        activity = offer_case_ownership_transfer_activity(
            case,
            target=as_Service(id_=transferee_id, name="Coordinator Attr"),
            actor=case_actor_id,
            to=[case_actor_id],
            attributed_to=vendor_id,
            id_="https://example.org/activities/offer_ot7",
        )
        event = make_payload(activity, receiving_actor_id=case_actor_id)
        assert event.activity.attributed_to == vendor_id, (
            "the extractor must carry attributed_to onto the activity snapshot,"
            " or the delegated author is unrecoverable downstream (CM-24-002)"
        )

        trigger_activity = MagicMock()
        trigger_activity.offer_case_ownership_transfer.return_value = (
            "https://example.org/activities/offer_ot7_fwd",
            {},
        )

        OfferCaseOwnershipTransferReceivedUseCase(
            dl,
            event,
            trigger_activity=trigger_activity,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        kwargs = (
            trigger_activity.offer_case_ownership_transfer.call_args.kwargs
        )
        assert kwargs["attributed_to"] == vendor_id, (
            "forwarded Offer must attribute the vendor who asked for the"
            f" transfer, not the CaseActor that relayed it. Got: {kwargs!r}"
        )
        assert kwargs["actor"] == case_actor_id

    def test_forwarded_offer_ignores_attributed_to_from_a_non_case_actor(
        self, make_payload, caplog
    ):
        """A peer may not name another actor as the offerer of record.

        `attributed_to` is honoured only in the delegated shape CM-24-001
        defines — an Offer the CaseActor sent on a participant's behalf.  Here a
        participant sends the Offer under its *own* identity while naming
        another participant in `attributed_to`.  Relaying that unchecked would
        let any participant forge who offered the transfer, and nothing
        downstream re-checks it: CLP-07-003 validates `payloadSnapshot.actor`,
        not `attributed_to`.
        """
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.base.objects.actors import as_Service
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

        case_actor_id = "https://example.org/actors/case-actor-spoof"
        vendor1_id = "https://example.org/users/vendor1-spoof"
        vendor2_id = "https://example.org/users/vendor2-spoof"
        transferee_id = "https://example.org/users/coordinator-spoof"

        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=case_actor_id)

        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_ot8",
            name="OT Spoof Case",
            attributed_to=vendor1_id,
        )
        case_manager_participant = as_CaseParticipant(
            attributed_to=case_actor_id,
            context=case.id_,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        case.actor_participant_index[case_actor_id] = (
            case_manager_participant.id_
        )
        case.case_participants.append(case_manager_participant.id_)
        dl.create(case)
        dl.create(case_manager_participant)

        # vendor2 sends under its own identity but claims vendor1's intent.
        activity = offer_case_ownership_transfer_activity(
            case,
            target=as_Service(id_=transferee_id, name="Coordinator Spoof"),
            actor=vendor2_id,
            to=[case_actor_id],
            attributed_to=vendor1_id,
            id_="https://example.org/activities/offer_ot8",
        )
        event = make_payload(activity, receiving_actor_id=case_actor_id)

        trigger_activity = MagicMock()
        trigger_activity.offer_case_ownership_transfer.return_value = (
            "https://example.org/activities/offer_ot8_fwd",
            {},
        )

        with caplog.at_level("WARNING"):
            OfferCaseOwnershipTransferReceivedUseCase(
                dl,
                event,
                trigger_activity=trigger_activity,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            ).execute()

        kwargs = (
            trigger_activity.offer_case_ownership_transfer.call_args.kwargs
        )
        assert kwargs["attributed_to"] == vendor2_id, (
            "the sender is the offerer of record when the Offer is not"
            f" delegated by the CaseActor. Got: {kwargs!r}"
        )
        assert any(
            "ignoring attributed_to" in r.message for r in caplog.records
        ), "the refusal must be logged, not silent"

    def test_offer_cascade_warns_when_trigger_activity_absent(
        self, make_payload, caplog
    ):
        """Warns when trigger_activity port is absent after BT commit.

        Seeds a full case with a CASE_MANAGER participant so the guarded-commit
        BT can succeed, then omits trigger_activity. The use case must emit a
        WARNING and leave all outboxes empty (CM-21-005 forwarding skipped).
        """
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.base.objects.actors import as_Service
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

        case_actor_id = "https://example.org/actors/case-actor-w"
        vendor_id = "https://example.org/users/vendor-w"
        transferee_id = "https://example.org/users/coordinator-w"

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=case_actor_id,
        )

        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_ot5",
            name="OT Warning Case",
            attributed_to=vendor_id,
        )
        case_manager_participant = as_CaseParticipant(
            attributed_to=case_actor_id,
            context=case.id_,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        case.actor_participant_index[case_actor_id] = (
            case_manager_participant.id_
        )
        case.case_participants.append(case_manager_participant.id_)
        dl.create(case)
        dl.create(case_manager_participant)

        transferee_actor = as_Service(id_=transferee_id, name="Coordinator-W")
        activity = offer_case_ownership_transfer_activity(
            case,
            target=transferee_actor,
            actor=vendor_id,
            to=[case_actor_id],
            id_="https://example.org/activities/offer_ot5",
        )
        event = make_payload(activity, receiving_actor_id=case_actor_id)

        with caplog.at_level("WARNING"):
            OfferCaseOwnershipTransferReceivedUseCase(
                dl,
                event,
                # trigger_activity intentionally omitted,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            ).execute()

        assert any("no trigger_activity" in r.message for r in caplog.records)
        # No activity should have landed in any outbox.
        case_actor_outbox = dl.clone_for_actor(case_actor_id).outbox_list()
        assert len(case_actor_outbox) == 0

    def test_offer_case_ownership_transfer_uses_store_owner_when_no_receiving_actor(
        self, make_payload
    ):
        """When receiving_actor_id is absent the store owner processes the Offer.

        Absent-stamp path (CLP-10-005): resolve_receiving_actor_id falls back
        to dl.actor_id, so the offer is persisted rather than dropped.
        """

        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        actor_id = "https://example.org/actors/store-owner-ot"
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)

        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_ot_nostamp",
            name="OT No-Stamp Test",
        )
        activity = offer_case_ownership_transfer_activity(
            case,
            target="https://example.org/users/transferee",
            actor="https://example.org/users/vendor",
            to=[actor_id],
        )
        event = make_payload(activity, receiving_actor_id=None)

        OfferCaseOwnershipTransferReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        stored = dl.get(activity.type_.value, activity.id_)
        assert stored is not None, (
            "Offer must be persisted even when receiving_actor_id is absent"
            " (store-owner fallback, CLP-10-005)"
        )

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
            id_="https://example.org/cases/case_ot_nocase", name="no case"
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


_CASE_ACTOR_ID = "https://example.org/actors/case-actor"
_VENDOR_ID = "https://example.org/users/vendor"
_COORDINATOR_ID = "https://example.org/users/coordinator"


def _ownership_offer_harness(make_payload, case_id: str, forward=False):
    """A CASE_MANAGER store holding one case, and a function delivering an Offer.

    The roster holds the CASE_MANAGER, the vendor as Case Owner and the
    coordinator as a plain participant.  Returns ``(dl, deliver,
    trigger_activity)``; ``deliver(transferee_id, offer_id, end_time=None,
    offerer=_VENDOR_ID, attributed_to=None)`` runs the received Offer use case and returns its
    disposition with the Offer as sent.  With ``forward=True`` the real
    trigger adapter mints and stores the forwarded Offer (CM-21-005) in
    place of the mock.
    """
    from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
    from vultron.adapters.driven.trigger_activity_adapter import (
        TriggerActivityAdapter,
    )
    from vultron.wire.as2.vocab.base.objects.actors import as_Service

    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_ID)
    case = as_VulnerabilityCase(
        id_=case_id, name="One open offer", attributed_to=_VENDOR_ID
    )
    seed_case_manager_participant(dl, case, _CASE_ACTOR_ID)
    seed_case_owner_participant(dl, case, _VENDOR_ID)
    seed_case_participant(dl, case, _COORDINATOR_ID)
    dl.create(case)
    trigger_activity: Any
    if forward:
        trigger_activity = TriggerActivityAdapter(dl)
    else:
        trigger_activity = MagicMock()
        trigger_activity.offer_case_ownership_transfer.return_value = (
            "https://example.org/activities/forwarded",
            {},
        )

    def deliver(
        transferee_id: str,
        offer_id: str,
        end_time: datetime | None = None,
        offerer: str = _VENDOR_ID,
        attributed_to: str | None = None,
    ) -> tuple[HandlerDisposition, Any]:
        extra = (
            {} if attributed_to is None else {"attributed_to": attributed_to}
        )
        offer = offer_case_ownership_transfer_activity(
            case,
            target=as_Service(id_=transferee_id, name="Transferee"),
            actor=offerer,
            to=[_CASE_ACTOR_ID],
            id_=offer_id,
            end_time=end_time,
            **extra,
        )
        result = OfferCaseOwnershipTransferReceivedUseCase(
            dl,
            make_payload(offer, receiving_actor_id=_CASE_ACTOR_ID),
            trigger_activity=trigger_activity,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()
        return result.disposition, offer

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


def _accept(dl, make_payload, offer, sender=_COORDINATOR_ID, accept=None):
    """Deliver the transferee's (or *sender*'s) Accept of *offer* to *dl*."""
    if accept is None:
        accept = accept_case_ownership_transfer_activity(
            offer, actor=sender, to=[_CASE_ACTOR_ID]
        )
    return AcceptCaseOwnershipTransferReceivedUseCase(
        dl,
        make_payload(accept, receiving_actor_id=dl.actor_id),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
    ).execute()


def _owner(dl, case_id: str) -> str | None:
    case = dl.read(case_id)
    assert isinstance(case, VulnerabilityCase)
    return cast(str | None, case.attributed_to)


def _event_types(dl) -> list[str]:
    return [
        entry.event_type
        for entry in dl.list_objects("CaseLedgerEntry")
        if isinstance(entry, CaseLedgerEntry)
    ]


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
    entries_after_first = _event_types(dl)
    second, _ = deliver(
        "https://example.org/users/vendor2",
        "https://example.org/activities/offer_one_open_2",
    )

    assert first is HandlerDisposition.APPLIED
    assert second is HandlerDisposition.REFUSED
    trigger_activity.offer_case_ownership_transfer.assert_called_once()
    # Refused before the commit: no entry, so no replica learns of it.
    assert _event_types(dl) == entries_after_first


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


def _redeliver_offer(dl, make_payload, offer, trigger_activity):
    """Deliver the same Offer activity *offer* to the CASE_MANAGER again."""
    return OfferCaseOwnershipTransferReceivedUseCase(
        dl,
        make_payload(offer, receiving_actor_id=_CASE_ACTOR_ID),
        trigger_activity=trigger_activity,
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
    ).execute()


@pytest.mark.spec("HP-01-003")
@pytest.mark.spec("CM-21-014")
def test_redelivered_open_offer_is_skipped_and_not_forwarded_again(
    make_payload,
):
    """The open Offer, delivered again, is not an earlier Offer for itself."""
    dl, deliver, trigger_activity = _ownership_offer_harness(
        make_payload, "https://example.org/cases/case_ot_offer_again"
    )
    first, offer = deliver(
        _COORDINATOR_ID, "https://example.org/activities/offer_again_1"
    )
    entries_after_first = _event_types(dl)

    again = _redeliver_offer(dl, make_payload, offer, trigger_activity)

    assert first is HandlerDisposition.APPLIED
    assert again.disposition is HandlerDisposition.SKIPPED
    assert _event_types(dl) == entries_after_first
    # The forward already went out; a duplicate does not send it twice.
    trigger_activity.offer_case_ownership_transfer.assert_called_once()


@pytest.mark.spec("HP-01-003")
@pytest.mark.spec("CM-21-014")
def test_redelivered_answered_offer_is_skipped_while_a_newer_one_is_open(
    make_payload,
):
    """A late copy of an answered Offer is a duplicate, not a second Offer."""
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
    entries_before = _event_types(dl)

    late = _redeliver_offer(dl, make_payload, first, trigger_activity)

    assert late.disposition is HandlerDisposition.SKIPPED
    assert _event_types(dl) == entries_before
    assert trigger_activity.offer_case_ownership_transfer.call_count == 2


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
def test_new_offer_after_an_expired_one_ledgers_the_expiry(make_payload):
    """The CASE_MANAGER finds the expiry lazily and records it before admitting."""
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
    event_types = [
        entry.event_type
        for entry in dl.list_objects("CaseLedgerEntry")
        if isinstance(entry, CaseLedgerEntry)
    ]
    assert any("expir" in event_type for event_type in event_types), (
        event_types
    )


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
    assert _event_types(dl) == entries_before


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
        entries_before = _event_types(dl)
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
    def test_accept_of_the_forwarded_offer_is_applied(self, make_payload):
        """The transferee answers the copy the CASE_MANAGER forwarded to it.

        The forward is a new activity with its own id (CM-21-005); it stands
        for the Offer the CASE_MANAGER recorded, so accepting it transfers
        ownership to the transferee that Offer names.
        """
        case_id = "https://example.org/cases/case_ot_forwarded"
        from vultron.wire.as2.vocab.base.objects.actors import as_Service

        dl, deliver, _ = _ownership_offer_harness(
            make_payload, case_id, forward=True
        )
        # In the CASE_MANAGER's address book, so the ledger snapshot can
        # inline the forward's bare-id target (CLP-07).
        dl.create(as_Service(id_=_COORDINATOR_ID, name="Coordinator"))
        disposition, offer = deliver(
            _COORDINATOR_ID, "https://example.org/activities/offer_fwd"
        )
        assert disposition is HandlerDisposition.APPLIED
        (forwarded,) = [
            item
            for item in (dl.read(i) for i in dl.outbox_list())
            if getattr(getattr(item, "type_", None), "value", None) == "Offer"
        ]
        assert forwarded is not None and forwarded.id_ != offer.id_

        result = _accept(dl, make_payload, forwarded)

        assert result.disposition is HandlerDisposition.APPLIED
        assert _owner(dl, case_id) == _COORDINATOR_ID
        assert _owner_roles(dl, case_id)[_COORDINATOR_ID] is True
        assert _owner_roles(dl, case_id)[_VENDOR_ID] is False

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
        entries_after_first = _event_types(dl)

        again = _accept(dl, make_payload, offer)

        assert again.disposition is HandlerDisposition.REFUSED
        assert again.reason is not None and "already closed" in again.reason
        assert _event_types(dl) == entries_after_first

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
        entries_after_first = _event_types(dl)

        again = _accept(dl, make_payload, offer, accept=accept)

        assert first.disposition is HandlerDisposition.APPLIED
        assert again.disposition is HandlerDisposition.SKIPPED
        assert _event_types(dl) == entries_after_first
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
        entries_before = _event_types(dl)
        outbox_before = dl.outbox_list()

        replay = _accept(dl, make_payload, first, accept=old_accept)

        assert replay.disposition is HandlerDisposition.SKIPPED
        _assert_nothing_changed(dl, case_id, roles_before, entries_before)
        assert dl.outbox_list() == outbox_before

    @staticmethod
    def _plant_forged_forward(dl, case_id: str, target: str, forward_id: str):
        """Store an Offer that claims the CASE_MANAGER forwarded it.

        Inbound inline objects are stored by id, so a sender can plant one.
        """
        case = dl.read(case_id)
        assert isinstance(case, VulnerabilityCase)
        from vultron.wire.as2.vocab.base.objects.actors import as_Service

        forged = offer_case_ownership_transfer_activity(
            case,
            target=as_Service(id_=target, name="Forged"),
            actor=_CASE_ACTOR_ID,
            id_=forward_id,
        )
        dl.create(forged)
        return forged

    @pytest.mark.spec("CM-21-011")
    def test_forged_forward_naming_the_impostor_is_refused(self, make_payload):
        """A planted 'forward' stands for no Offer the CASE_MANAGER recorded."""
        case_id = "https://example.org/cases/case_ot_forged_self"
        impostor = "https://example.org/users/mallory"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        deliver(_COORDINATOR_ID, "https://example.org/activities/offer_fs")
        forged = self._plant_forged_forward(
            dl, case_id, impostor, "https://example.org/activities/forged_fs"
        )
        roles_before = _owner_roles(dl, case_id)
        entries_before = _event_types(dl)
        outbox_before = dl.outbox_list()

        result = _accept(dl, make_payload, forged, sender=impostor)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None and "never recorded" in result.reason
        _assert_nothing_changed(dl, case_id, roles_before, entries_before)
        assert dl.outbox_list() == outbox_before

    @pytest.mark.spec("CM-21-011")
    def test_forged_forward_naming_the_transferee_is_refused(
        self, make_payload
    ):
        """A planted 'forward' of a real Offer still needs its transferee."""
        case_id = "https://example.org/cases/case_ot_forged_other"
        impostor = "https://example.org/users/mallory"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        deliver(_COORDINATOR_ID, "https://example.org/activities/offer_fo")
        forged = self._plant_forged_forward(
            dl,
            case_id,
            _COORDINATOR_ID,
            "https://example.org/activities/forged_fo",
        )
        roles_before = _owner_roles(dl, case_id)
        entries_before = _event_types(dl)
        outbox_before = dl.outbox_list()

        result = _accept(dl, make_payload, forged, sender=impostor)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None
        assert "is not the transferee" in result.reason
        _assert_nothing_changed(dl, case_id, roles_before, entries_before)
        assert dl.outbox_list() == outbox_before

    @pytest.mark.spec("CM-21-011")
    @pytest.mark.xfail(
        strict=True,
        raises=AssertionError,
        reason="The ownership-transfer Offer is not sender-checked, so an"
        " actor can record an Offer naming itself and accept it. Tracked by"
        " #4540.",
    )
    def test_offer_from_a_non_owner_cannot_win_ownership(self, make_payload):
        """An actor off the roster offers the case to itself, then accepts."""
        case_id = "https://example.org/cases/case_ot_self_offer"
        impostor = "https://example.org/users/mallory"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, offer = deliver(
            impostor,
            "https://example.org/activities/offer_self",
            offerer=impostor,
        )

        _accept(dl, make_payload, offer, sender=impostor)

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

        result = _accept(dl, make_payload, offer)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None and "CASE_MANAGER" in result.reason
        _assert_nothing_changed(dl, case_id, roles_before, [])
        assert dl.outbox_list() == []

    @pytest.mark.spec("PCR-03-001")
    def test_accept_from_the_case_manager_is_admitted_at_a_replica(
        self, make_payload
    ):
        """Admitted, but a replica still applies the change only from the
        ledger fan-out (RSH-08-003), so ownership is unchanged here."""
        case_id = "https://example.org/cases/case_ot_replica_admitted"
        dl, offer = _vendor_replica(case_id)

        result = _accept(dl, make_payload, offer, sender=_CASE_ACTOR_ID)

        assert result.disposition is not HandlerDisposition.REFUSED
        assert _owner(dl, case_id) == _VENDOR_ID
        assert _event_types(dl) == []


# ---------------------------------------------------------------------------
# CM-21-012 – CM-21-014: the transferee's Reject is ledgered, sender-checked,
# and closes the Offer, after which the case may be offered again.
# ---------------------------------------------------------------------------


def _reject(dl, make_payload, offer, sender=_COORDINATOR_ID, reject=None):
    """Deliver the transferee's (or *sender*'s) Reject of *offer* to *dl*."""
    if reject is None:
        reject = reject_case_ownership_transfer_activity(
            offer, actor=sender, to=[_CASE_ACTOR_ID]
        )
    return RejectCaseOwnershipTransferReceivedUseCase(
        dl,
        make_payload(reject, receiving_actor_id=dl.actor_id),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
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
        assert _event_types(dl).count("reject_case_ownership_transfer") == 1
        assert _announces(dl, outbox_before), (
            "the Reject's entry must be broadcast as Announce(CaseLedgerEntry)"
        )
        assert _owner(dl, case_id) == _VENDOR_ID
        assert _owner_roles(dl, case_id) == roles_before

    @pytest.mark.spec("CM-21-005")
    @pytest.mark.spec("CM-21-012")
    def test_reject_of_the_forwarded_offer_is_ledgered(self, make_payload):
        """The transferee declines the copy the CASE_MANAGER forwarded."""
        case_id = "https://example.org/cases/case_ot_reject_fwd"
        from vultron.wire.as2.vocab.base.objects.actors import as_Service

        dl, deliver, _ = _ownership_offer_harness(
            make_payload, case_id, forward=True
        )
        dl.create(as_Service(id_=_COORDINATOR_ID, name="Coordinator"))
        disposition, offer = deliver(
            _COORDINATOR_ID, "https://example.org/activities/offer_rj_fwd"
        )
        assert disposition is HandlerDisposition.APPLIED
        (forwarded,) = [
            item
            for item in (dl.read(i) for i in dl.outbox_list())
            if getattr(getattr(item, "type_", None), "value", None) == "Offer"
        ]
        assert forwarded is not None and forwarded.id_ != offer.id_

        result = _reject(dl, make_payload, forwarded)

        assert result.disposition is HandlerDisposition.APPLIED
        assert "reject_case_ownership_transfer" in _event_types(dl)
        assert _owner(dl, case_id) == _VENDOR_ID

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
        entries_before = _event_types(dl)
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
        entries_after_first = _event_types(dl)
        outbox_after_first = dl.outbox_list()

        again = _reject(dl, make_payload, offer, reject=reject)

        assert first.disposition is HandlerDisposition.APPLIED
        assert again.disposition is HandlerDisposition.SKIPPED
        assert _event_types(dl) == entries_after_first
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
        entries_before = _event_types(dl)

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
        entries_before = _event_types(dl)

        late = _reject(dl, make_payload, offer)

        assert late.disposition is HandlerDisposition.REFUSED
        assert late.reason is not None and "already closed" in late.reason
        assert _event_types(dl) == entries_before
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

    def test_reject_naming_no_case_is_refused(self, make_payload):
        dl, _, _ = _ownership_offer_harness(
            make_payload, "https://example.org/cases/case_ot_reject_nocase"
        )
        # Only the fields the use case reads before refusing.
        event = MagicMock(
            case_id=None,
            receiving_actor_id=None,
            activity_id="https://example.org/activities/reject_nocase",
            actor_id=_COORDINATOR_ID,
        )

        result = RejectCaseOwnershipTransferReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None and "names no case" in result.reason
        assert _event_types(dl) == []


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

        result = _reject(dl, make_payload, offer)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None and "CASE_MANAGER" in result.reason
        _assert_nothing_changed(dl, case_id, roles_before, [])
        assert dl.outbox_list() == []

    @pytest.mark.spec("CM-21-012")
    @pytest.mark.spec("PCR-03-001")
    def test_reject_from_the_case_manager_changes_nothing_at_a_replica(
        self, make_payload
    ):
        """Admitted, but a replica commits nothing and keeps the owner."""
        case_id = "https://example.org/cases/case_ot_rj_replica_admitted"
        dl, offer = _vendor_replica(case_id)
        roles_before = _owner_roles(dl, case_id)

        result = _reject(dl, make_payload, offer, sender=_CASE_ACTOR_ID)

        assert result.disposition is HandlerDisposition.APPLIED
        _assert_nothing_changed(dl, case_id, roles_before, [])


@pytest.mark.spec("CM-21-005")
@pytest.mark.spec("CM-21-014")
def test_transferee_takes_the_forward_of_an_open_offer(make_payload):
    """The one-open-Offer rule is the CASE_MANAGER's alone.

    The transferee's replica holds the ledgered Offer the forward stands
    for, still open; judged there, the forward would read as a second Offer.
    """
    from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

    case_id = "https://example.org/cases/case_ot_forward_at_transferee"
    cm, deliver, _ = _ownership_offer_harness(make_payload, case_id)
    assert (
        deliver(_COORDINATOR_ID, "https://example.org/activities/offer_ft")[0]
        is HandlerDisposition.APPLIED
    )
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
    assert "offer_case_ownership_transfer" in _event_types(transferee)
    forward = offer_case_ownership_transfer_activity(
        case,
        target=_COORDINATOR_ID,
        actor=_CASE_ACTOR_ID,
        attributed_to=_VENDOR_ID,
        to=[_COORDINATOR_ID],
        id_="https://example.org/activities/offer_ft_forwarded",
    )

    result = OfferCaseOwnershipTransferReceivedUseCase(
        transferee,
        make_payload(forward, receiving_actor_id=_COORDINATOR_ID),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(transferee),
    ).execute()

    assert result.disposition is HandlerDisposition.APPLIED
    assert transferee.read(forward.id_) is not None


# ---------------------------------------------------------------------------
# CM-21-015: the offerer withdraws an open Offer with Undo(Offer); the
# withdrawal is ledgered, sender-checked, and closes the Offer (CM-21-014).
# ---------------------------------------------------------------------------


def _undo(dl, make_payload, offer, sender=_VENDOR_ID, undo=None):
    """Deliver the offerer's (or *sender*'s) Undo of *offer* to *dl*."""
    if undo is None:
        undo = undo_case_ownership_transfer_activity(
            offer, actor=sender, to=[_CASE_ACTOR_ID]
        )
    return UndoCaseOwnershipTransferReceivedUseCase(
        dl,
        make_payload(undo, receiving_actor_id=dl.actor_id),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
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
        assert _event_types(dl).count("undo_case_ownership_transfer") == 1
        assert _announces(dl, outbox_before), (
            "the Undo's entry must be broadcast as Announce(CaseLedgerEntry)"
        )
        assert _owner(dl, case_id) == _VENDOR_ID
        assert _owner_roles(dl, case_id) == roles_before

    @pytest.mark.spec("CM-21-015")
    @pytest.mark.spec("CM-24-002")
    def test_delegated_offer_is_withdrawn_by_the_participant_it_speaks_for(
        self, make_payload
    ):
        """The offer trigger sends the Offer as the CASE_MANAGER, attributed
        to the Case Owner; that Case Owner is the one who may withdraw it."""
        case_id = "https://example.org/cases/case_ot_undo_delegated"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        disposition, offer = deliver(
            _COORDINATOR_ID,
            "https://example.org/activities/offer_undo_delegated",
            offerer=_CASE_ACTOR_ID,
            attributed_to=_VENDOR_ID,
        )
        assert disposition is HandlerDisposition.APPLIED

        result = _undo(dl, make_payload, offer)

        assert result.disposition is HandlerDisposition.APPLIED
        assert "undo_case_ownership_transfer" in _event_types(dl)

    @pytest.mark.spec("CM-21-015")
    @pytest.mark.spec("CM-24-002")
    def test_attributed_to_on_a_direct_offer_does_not_move_the_offerer(
        self, make_payload
    ):
        """An Offer the Case Owner sent itself speaks for its ``actor``.

        An ``attributedTo`` it carries is a claim nothing checks, so the
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
        entries_before = _event_types(dl)
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
        assert "undo_case_ownership_transfer" in _event_types(dl)

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
        entries_before = _event_types(dl)
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
        """Only a Case Owner withdraws: an Offer made by a non-owner (which
        the CASE_MANAGER does not yet refuse, #4540) cannot be withdrawn by
        it."""
        case_id = "https://example.org/cases/case_ot_undo_not_owner"
        dl, deliver, _ = _ownership_offer_harness(make_payload, case_id)
        _, offer = deliver(
            "https://example.org/users/vendor2",
            "https://example.org/activities/offer_undo_not_owner",
            offerer=_COORDINATOR_ID,
        )
        entries_before = _event_types(dl)

        result = _undo(dl, make_payload, offer, sender=_COORDINATOR_ID)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None
        assert "does not hold CASE_OWNER" in result.reason
        assert _event_types(dl) == entries_before

    @pytest.mark.spec("CM-21-015")
    def test_withdrawal_of_an_offer_never_recorded_is_refused(
        self, make_payload
    ):
        case_id = "https://example.org/cases/case_ot_undo_unrecorded"
        dl, _, _ = _ownership_offer_harness(make_payload, case_id)
        case = dl.read_case(case_id)
        assert case is not None
        offer = offer_case_ownership_transfer_activity(
            case,
            target=_COORDINATOR_ID,
            actor=_VENDOR_ID,
            id_="https://example.org/activities/offer_undo_unrecorded",
        )

        result = _undo(dl, make_payload, offer)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None
        assert "never recorded" in result.reason
        assert _event_types(dl) == []

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
            offer, actor=_VENDOR_ID, to=[_CASE_ACTOR_ID]
        )
        first = _undo(dl, make_payload, offer, undo=undo)
        entries_after_first = _event_types(dl)
        outbox_after_first = dl.outbox_list()

        again = _undo(dl, make_payload, offer, undo=undo)

        assert first.disposition is HandlerDisposition.APPLIED
        assert again.disposition is HandlerDisposition.SKIPPED
        assert _event_types(dl) == entries_after_first
        assert dl.outbox_list() == outbox_after_first

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
        entries_before = _event_types(dl)
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
        assert _event_types(dl) == entries_before
        assert dl.outbox_list() == outbox_before

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
        entries_before = _event_types(dl)

        second = _undo(dl, make_payload, offer)

        assert second.disposition is HandlerDisposition.REFUSED
        assert second.reason is not None
        assert "already closed" in second.reason
        assert _event_types(dl) == entries_before

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
        entries_before = _event_types(dl)

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

    def test_withdrawal_naming_no_case_is_refused(self, make_payload):
        dl, _, _ = _ownership_offer_harness(
            make_payload, "https://example.org/cases/case_ot_undo_nocase"
        )
        # Only the fields the use case reads before refusing.
        event = MagicMock(
            case_id=None,
            receiving_actor_id=None,
            activity_id="https://example.org/activities/undo_nocase",
            actor_id=_VENDOR_ID,
        )

        result = UndoCaseOwnershipTransferReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None and "names no case" in result.reason
        assert _event_types(dl) == []


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

        result = _undo(dl, make_payload, offer)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None and "CASE_MANAGER" in result.reason
        _assert_nothing_changed(dl, case_id, roles_before, [])
        assert dl.outbox_list() == []

    @pytest.mark.spec("CM-21-015")
    @pytest.mark.spec("PCR-03-001")
    def test_withdrawal_from_the_case_manager_changes_nothing_at_a_replica(
        self, make_payload
    ):
        """Admitted, but a replica commits nothing and keeps the owner."""
        case_id = "https://example.org/cases/case_ot_undo_replica_admitted"
        dl, offer = _vendor_replica(case_id)
        roles_before = _owner_roles(dl, case_id)

        result = _undo(dl, make_payload, offer, sender=_CASE_ACTOR_ID)

        assert result.disposition is HandlerDisposition.APPLIED
        _assert_nothing_changed(dl, case_id, roles_before, [])


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
        entries_before = _event_types(dl)

        result = send(dl, make_payload, offer, sender=_STRANGER_ID)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None
        assert no_standing in result.reason
        assert "already closed" not in result.reason
        assert _event_types(dl) == entries_before

    @pytest.mark.spec("CM-21-013")
    @pytest.mark.spec("HP-01-006")
    @pytest.mark.parametrize("reply", sorted(_REPLIES))
    def test_a_stranger_replying_to_an_expired_offer_is_refused_for_standing(
        self, make_payload, reply
    ):
        send, _party, no_standing = _REPLIES[reply]
        case_id = f"https://example.org/cases/case_ot_stranger_late_{reply}"
        dl, offer = _expired_offer(make_payload, case_id)

        result = send(dl, make_payload, offer, sender=_STRANGER_ID)

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None
        assert no_standing in result.reason
        assert "too late" not in result.reason
        # A sender with no standing never makes the CASE_MANAGER ledger the
        # expiry (HP-01-006).
        assert OFFER_CASE_OWNERSHIP_TRANSFER_EXPIRED_EVENT_TYPE not in (
            _event_types(dl)
        )
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
        assert _owner(dl, case_id) == _VENDOR_ID
