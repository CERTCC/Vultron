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

import logging
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
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.use_cases.received.actor.ownership import (
    AcceptCaseOwnershipTransferReceivedUseCase,
    OfferCaseOwnershipTransferReceivedUseCase,
    RejectCaseOwnershipTransferReceivedUseCase,
)
from vultron.wire.as2.factories import (
    accept_case_ownership_transfer_activity,
    offer_case_ownership_transfer_activity,
    reject_case_ownership_transfer_activity,
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

    def test_reject_case_ownership_transfer_logs_rejection(
        self, caplog, make_payload
    ):
        """RejectCaseOwnershipTransferReceivedUseCase logs rejection; ownership unchanged."""
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_ot3",
            name="OT Case 3",
        )
        offer = offer_case_ownership_transfer_activity(
            case,
            target="https://example.org/users/coordinator",
            actor="https://example.org/users/vendor",
            id_="https://example.org/activities/offer_ot3",
        )
        activity = reject_case_ownership_transfer_activity(
            offer,
            actor="https://example.org/users/coordinator",
        )
        event = make_payload(activity)

        with caplog.at_level(logging.INFO):
            result = RejectCaseOwnershipTransferReceivedUseCase(
                MagicMock(),
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=MagicMock(spec=SyncActivityPort),
            ).execute()

        assert any("rejected" in r.message.lower() for r in caplog.records)
        # Nothing changes on a declined transfer (HP-01-003).
        assert result.disposition == HandlerDisposition.SKIPPED

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
    offerer=_VENDOR_ID)`` runs the received Offer use case and returns its
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
    ) -> tuple[HandlerDisposition, Any]:
        offer = offer_case_ownership_transfer_activity(
            case,
            target=as_Service(id_=transferee_id, name="Transferee"),
            actor=offerer,
            to=[_CASE_ACTOR_ID],
            id_=offer_id,
            end_time=end_time,
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
    return datetime.now(UTC) + timedelta(seconds=1)


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
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="CM-21-014: a second Offer is forwarded while the first is unanswered. #4475.",
)
def test_second_offer_while_first_is_unanswered_is_refused(make_payload):
    """Two pending Offers would let two transferees accept the same case."""
    _, deliver, trigger_activity = _ownership_offer_harness(
        make_payload, "https://example.org/cases/case_ot_one_open"
    )

    first, _ = deliver(
        _COORDINATOR_ID,
        "https://example.org/activities/offer_one_open_1",
    )
    second, _ = deliver(
        "https://example.org/users/vendor2",
        "https://example.org/activities/offer_one_open_2",
    )

    assert first is HandlerDisposition.APPLIED
    assert second is HandlerDisposition.REFUSED
    trigger_activity.offer_case_ownership_transfer.assert_called_once()


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


@pytest.mark.spec("CM-21-016")
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="CM-21-016: an Accept after the Offer's end_time is applied. #4491.",
)
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
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="CM-21-017: an expired Offer is never ledgered as expired. #4491.",
)
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
        assert again.reason is not None and "already answered" in again.reason
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


class TestAcceptAtAReplica:
    """PCR-03-001: a participant replica takes the change only from the CASE_MANAGER."""

    @staticmethod
    def _replica(case_id: str):
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

    @pytest.mark.spec("CM-21-011")
    @pytest.mark.spec("PCR-03-001")
    def test_accept_from_the_transferee_is_refused_at_a_replica(
        self, make_payload
    ):
        case_id = "https://example.org/cases/case_ot_replica_refused"
        dl, offer = self._replica(case_id)
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
        dl, offer = self._replica(case_id)

        result = _accept(dl, make_payload, offer, sender=_CASE_ACTOR_ID)

        assert result.disposition is not HandlerDisposition.REFUSED
        assert _owner(dl, case_id) == _VENDOR_ID
        assert _event_types(dl) == []
