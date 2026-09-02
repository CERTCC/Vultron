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
from typing import Any, cast
from unittest.mock import MagicMock

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
        )
        event = make_payload(activity)

        OfferCaseOwnershipTransferReceivedUseCase(dl, event).execute()

        stored = dl.get(activity.type_.value, activity.id_)
        assert stored is not None

    def test_accept_case_ownership_transfer_updates_attributed_to(
        self, make_payload
    ):
        """AcceptCaseOwnershipTransferReceivedUseCase updates case.attributed_to to new owner.

        receiving_actor_id is the CaseActor (coordinator); the guarded-commit
        gate ensures the ledger entry is only written when the receiving actor
        is the case manager (ADR-0053, CM-21-007).
        """
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        coordinator_id = "https://example.org/users/coordinator"
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=coordinator_id,
        )
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_ot2",
            name="OT Case 2",
            attributed_to="https://example.org/users/vendor",
        )
        dl.create(case)

        offer = offer_case_ownership_transfer_activity(
            case,
            target=coordinator_id,
            actor="https://example.org/users/vendor",
            id_="https://example.org/activities/offer_ot2",
        )
        dl.create(offer)

        activity = accept_case_ownership_transfer_activity(
            offer,
            actor=coordinator_id,
        )
        # receiving_actor_id must be set so AcceptCaseOwnershipTransferReceivedUseCase
        # does not skip (CLP-10-005 guard). It represents the actor whose inbox
        # received the Accept — here the coordinator (future CASE_OWNER).
        event = make_payload(activity, receiving_actor_id=coordinator_id)

        AcceptCaseOwnershipTransferReceivedUseCase(dl, event).execute()

        updated_record = dl.get(case.type_.value, case.id_)
        assert updated_record is not None
        data = cast(Any, updated_record).get("data_", updated_record)
        assert (
            data.get("attributed_to")
            == "https://example.org/users/coordinator"
        )

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
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )
        from vultron.wire.as2.vocab.base.objects.actors import as_Service
        from vultron.enums.roles import CVDRole

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
            dl, event, trigger_activity=trigger_activity
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
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )
        from vultron.wire.as2.vocab.base.objects.actors import as_Service
        from vultron.enums.roles import CVDRole

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
            dl, event, trigger_activity=trigger_activity
        ).execute()

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
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )
        from vultron.wire.as2.vocab.base.objects.actors import as_Service
        from vultron.enums.roles import CVDRole

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
            dl, event, trigger_activity=trigger_activity
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
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )
        from vultron.wire.as2.vocab.base.objects.actors import as_Service
        from vultron.enums.roles import CVDRole

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
                dl, event, trigger_activity=trigger_activity
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
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )
        from vultron.wire.as2.vocab.base.objects.actors import as_Service
        from vultron.enums.roles import CVDRole

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
            id_="https://example.org/activities/offer_ot5",
        )
        event = make_payload(activity, receiving_actor_id=case_actor_id)

        with caplog.at_level("WARNING"):
            OfferCaseOwnershipTransferReceivedUseCase(
                dl,
                event,
                # trigger_activity intentionally omitted
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
            RejectCaseOwnershipTransferReceivedUseCase(
                MagicMock(), event
            ).execute()

        assert any("rejected" in r.message.lower() for r in caplog.records)

    def test_offer_case_ownership_transfer_uses_store_owner_when_no_receiving_actor(
        self, make_payload
    ):
        """When receiving_actor_id is absent the store owner processes the Offer.

        Absent-stamp path (CLP-10-005): resolve_receiving_actor_id falls back
        to dl.actor_id, so the offer is persisted rather than dropped.
        """
        import py_trees
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        actor_id = "https://example.org/actors/store-owner-ot"
        py_trees.blackboard.Blackboard.storage.clear()
        try:
            dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)

            case = as_VulnerabilityCase(
                id_="https://example.org/cases/case_ot_nostamp",
                name="OT No-Stamp Test",
            )
            activity = offer_case_ownership_transfer_activity(
                case,
                target="https://example.org/users/transferee",
                actor="https://example.org/users/vendor",
            )
            event = make_payload(activity, receiving_actor_id=None)

            OfferCaseOwnershipTransferReceivedUseCase(dl, event).execute()

            stored = dl.get(activity.type_.value, activity.id_)
            assert stored is not None, (
                "Offer must be persisted even when receiving_actor_id is absent"
                " (store-owner fallback, CLP-10-005)"
            )
        finally:
            py_trees.blackboard.Blackboard.storage.clear()

    def test_accept_case_ownership_transfer_uses_store_owner_when_no_receiving_actor(
        self, make_payload
    ):
        """When receiving_actor_id is absent the store owner runs the accept BT.

        Absent-stamp path (CLP-10-005): resolve_receiving_actor_id falls back
        to dl.actor_id (coordinator), so the ownership transfer is applied rather
        than dropped.
        """
        import py_trees
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        coordinator_id = "https://example.org/users/coordinator-nostamp"
        py_trees.blackboard.Blackboard.storage.clear()
        try:
            dl = SqliteDataLayer("sqlite:///:memory:", actor_id=coordinator_id)

            case = as_VulnerabilityCase(
                id_="https://example.org/cases/case_ot_acc_nostamp",
                name="OT Accept No-Stamp Test",
                attributed_to="https://example.org/users/vendor-nostamp",
            )
            dl.create(case)

            offer = offer_case_ownership_transfer_activity(
                case,
                target=coordinator_id,
                actor="https://example.org/users/vendor-nostamp",
                id_="https://example.org/activities/offer_ot_nostamp",
            )
            dl.create(offer)

            activity = accept_case_ownership_transfer_activity(
                offer, actor=coordinator_id
            )
            event = make_payload(activity, receiving_actor_id=None)

            AcceptCaseOwnershipTransferReceivedUseCase(dl, event).execute()

            updated = dl.get(case.type_.value, case.id_)
            assert updated is not None
            from typing import cast, Any

            data = cast(Any, updated).get("data_", updated)
            assert data.get("attributed_to") == coordinator_id, (
                "Store owner (coordinator) must become new owner when"
                " receiving_actor_id is absent (CLP-10-005)"
            )
        finally:
            py_trees.blackboard.Blackboard.storage.clear()
