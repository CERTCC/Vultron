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
"""Tests for CaseParticipantRole received use cases (ADR-0039)."""

from unittest.mock import MagicMock

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.actor.case_participant_role import (
    OfferCaseParticipantRoleReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    offer_case_participant_role_activity,
)


def _archived_by_intake(dl, activity_id: str) -> bool:
    """True when intake archived *activity_id* under the receiver's key."""
    from vultron.core.models.received_activity_record import (
        ReceivedActivityRecord,
    )

    return isinstance(
        dl.read(ReceivedActivityRecord.build_id(activity_id)),
        ReceivedActivityRecord,
    )


class TestOfferCaseParticipantRoleReceivedUseCase:
    """Tests for the canonical role-delegation received use case (ADR-0039).

    Offer(CaseParticipantRole, target=Actor, context=VulnerabilityCase).  The
    routing through the CASE_MANAGER (CM-33) is covered in
    ``test_role_offer_routing.py``; these tests cover intake, the receiver's
    identity, and the target's answer.
    """

    _VENDOR_URI = "https://example.org/actors/vendor"
    _CASE_ACTOR_URI = "https://example.org/actors/case-actor"
    _TARGET_URI = "https://example.org/actors/coordinator"
    _CASE_URI = "https://example.org/cases/urn:uuid:test-case-role"

    def _make_offer(self, role: CVDRole = CVDRole.COORDINATOR):
        """The Case Owner's Offer, addressed to the CASE_MANAGER."""
        from vultron.wire.as2.vocab.base.objects.actors import as_Actor

        return offer_case_participant_role_activity(
            role=role,
            target_actor=as_Actor(id_=self._TARGET_URI),
            case=self._CASE_URI,
            actor=self._VENDOR_URI,
            to=[self._CASE_ACTOR_URI],
        )

    def _make_forward(self):
        """The CASE_MANAGER's forward of the Offer to the target."""
        from vultron.wire.as2.vocab.base.objects.actors import as_Actor

        return offer_case_participant_role_activity(
            role=CVDRole.COORDINATOR,
            target_actor=as_Actor(id_=self._TARGET_URI),
            case=self._CASE_URI,
            actor=self._CASE_ACTOR_URI,
            attributed_to=self._VENDOR_URI,
            to=[self._TARGET_URI],
            in_reply_to="https://example.org/activities/the-recorded-offer",
        )

    def _store(self, actor_id: str) -> SqliteDataLayer:
        """*actor_id*'s store, holding the case and its three participants."""
        from test.core.use_cases.received.conftest import (
            seed_case_manager_participant,
            seed_case_owner_participant,
            seed_case_participant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
        case = as_VulnerabilityCase(
            id_=self._CASE_URI,
            name="ROLE-TEST",
            attributed_to=self._VENDOR_URI,
        )
        seed_case_manager_participant(dl, case, self._CASE_ACTOR_URI)
        seed_case_owner_participant(dl, case, self._VENDOR_URI)
        seed_case_participant(dl, case, self._TARGET_URI)
        dl.create(case)
        return dl

    def _execute_at_case_manager(self, dl, event):
        """Run the handler wired as production wires the CASE_MANAGER."""
        from vultron.adapters.driven.trigger_activity_adapter import (
            TriggerActivityAdapter,
        )
        from vultron.adapters.driven.wire_render.as2 import (
            As2WireRenderAdapter,
        )

        return OfferCaseParticipantRoleReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            sync_port=MagicMock(),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

    def test_offer_case_participant_role_persists_offer(self, make_payload):
        """Intake archives the Offer the CASE_MANAGER receives (CLP-10-017)."""
        dl = self._store(self._CASE_ACTOR_URI)
        offer = self._make_offer()
        event = make_payload(offer, receiving_actor_id=self._CASE_ACTOR_URI)

        self._execute_at_case_manager(dl, event)

        assert _archived_by_intake(dl, offer.id_)

    @pytest.mark.spec("CLP-10-018")
    def test_a_refused_offer_is_still_archived(self, make_payload):
        """A store that does not hold the case refuses, and keeps what came."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:", actor_id=self._CASE_ACTOR_URI
        )
        offer = self._make_offer()
        event = make_payload(offer, receiving_actor_id=self._CASE_ACTOR_URI)

        result = OfferCaseParticipantRoleReceivedUseCase(
            dl, event, trigger_activity=MagicMock(), sync_port=MagicMock()
        ).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        assert _archived_by_intake(dl, offer.id_)

    def test_offer_case_participant_role_uses_store_owner_when_no_receiving_actor(
        self, make_payload
    ):
        """When receiving_actor_id is absent the store owner processes the offer."""
        dl = self._store(self._CASE_ACTOR_URI)
        offer = self._make_offer()
        event = make_payload(offer, receiving_actor_id=None)

        self._execute_at_case_manager(dl, event)

        # The BT runs under the store owner's identity, which is the Offer's
        # addressee, so intake archives it.
        assert _archived_by_intake(dl, offer.id_)

    @pytest.mark.spec("CM-33-004")
    def test_target_accepts_the_case_managers_forward(self, make_payload):
        """The target answers the forward it received, as its own answer."""
        from vultron.adapters.driven.trigger_activity_adapter import (
            TriggerActivityAdapter,
        )

        dl = self._store(self._TARGET_URI)
        forward = self._make_forward()
        event = make_payload(forward, receiving_actor_id=self._TARGET_URI)
        trigger = MagicMock(wraps=TriggerActivityAdapter(dl))

        result = OfferCaseParticipantRoleReceivedUseCase(
            dl, event, trigger_activity=trigger, sync_port=MagicMock()
        ).execute()

        assert result.disposition is HandlerDisposition.APPLIED
        trigger.accept_case_participant_role.assert_called_once()
        call_kwargs = trigger.accept_case_participant_role.call_args.kwargs
        assert call_kwargs["offer_id"] == forward.id_
        assert call_kwargs["actor"] == self._TARGET_URI
        assert call_kwargs["to"] == [self._CASE_ACTOR_URI]
        (queued,) = dl.outbox_list()
        assert getattr(dl.read(queued), "type_", None) == "Accept"

    @pytest.mark.spec("CLP-07-005")
    @pytest.mark.spec("CLP-10-006")
    def test_offer_at_case_manager_is_ledgered_and_applied(self, make_payload):
        """A role offer the CASE_MANAGER admits is ledgered (#3764).

        Before ``("Offer", "CaseParticipantRole")`` was a canonical signature,
        the guarded commit at the CASE_MANAGER failed and the handler reported
        ``REFUSED`` (#2255 surfaced the BT failure).  The CASE_MANAGER now
        commits the ``offer_case_participant_role`` entry and the receipt is
        ``APPLIED``.
        """
        from vultron.core.models.case_ledger_entry import CaseLedgerEntry

        dl = self._store(self._CASE_ACTOR_URI)
        offer = self._make_offer()
        event = make_payload(offer, receiving_actor_id=self._CASE_ACTOR_URI)

        result = self._execute_at_case_manager(dl, event)

        assert result.disposition is HandlerDisposition.APPLIED
        offer_entries = [
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry)
            and e.event_type == "offer_case_participant_role"
        ]
        assert len(offer_entries) == 1
        assert (
            offer_entries[0].payload_snapshot.get("actor") == self._VENDOR_URI
        )
        assert offer_entries[0].log_object_id == offer.id_

    @pytest.mark.spec("HP-01-003")
    def test_offer_case_participant_role_refused_when_neither_reply_sent(
        self, make_payload
    ):
        """When the target can neither Accept nor Reject, the offer is refused."""
        dl = self._store(self._TARGET_URI)
        event = make_payload(
            self._make_forward(), receiving_actor_id=self._TARGET_URI
        )

        trigger = MagicMock()
        trigger.accept_case_participant_role.side_effect = RuntimeError("down")
        trigger.reject_case_participant_role.side_effect = RuntimeError("down")

        result = OfferCaseParticipantRoleReceivedUseCase(
            dl, event, trigger_activity=trigger
        ).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason
        assert dl.outbox_list() == []
