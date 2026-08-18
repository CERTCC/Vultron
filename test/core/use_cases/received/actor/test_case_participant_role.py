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
"""Tests for OfferCaseParticipantRoleReceivedUseCase (ADR-0039)."""

from vultron.core.use_cases.received.actor.case_participant_role import (
    OfferCaseParticipantRoleReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import offer_case_participant_role_activity


class TestOfferCaseParticipantRoleReceivedUseCase:
    """Tests for the canonical role-delegation received use case (ADR-0039).

    Offer(CaseParticipantRole, target=Actor, context=VulnerabilityCase)
    """

    _VENDOR_URI = "https://example.org/actors/vendor"
    _CASE_ACTOR_URI = "https://example.org/actors/case-actor"
    _CASE_URI = "https://example.org/cases/urn:uuid:test-case-role"

    def _make_offer(self, role: CVDRole = CVDRole.CASE_MANAGER):
        from vultron.wire.as2.vocab.base.objects.actors import as_Actor
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        case = as_VulnerabilityCase(id_=self._CASE_URI, name="ROLE-TEST")
        actor = as_Actor(id_=self._CASE_ACTOR_URI)
        return offer_case_participant_role_activity(
            role=role,
            target_actor=actor,
            case=case,
            actor=self._VENDOR_URI,
        )

    def test_offer_case_participant_role_persists_offer(self, make_payload):
        """OfferCaseParticipantRoleReceivedUseCase persists the offer activity."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        offer = self._make_offer()
        event = make_payload(offer, receiving_actor_id=self._CASE_ACTOR_URI)

        OfferCaseParticipantRoleReceivedUseCase(dl, event).execute()

        stored = dl.get(offer.type_.value, offer.id_)
        assert stored is not None

    def test_offer_case_participant_role_idempotent(self, make_payload):
        """Repeated execution of OfferCaseParticipantRoleReceivedUseCase is a no-op."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        offer = self._make_offer()
        event = make_payload(offer, receiving_actor_id=self._CASE_ACTOR_URI)

        OfferCaseParticipantRoleReceivedUseCase(dl, event).execute()
        OfferCaseParticipantRoleReceivedUseCase(dl, event).execute()

        stored = dl.get(offer.type_.value, offer.id_)
        assert stored is not None

    def test_offer_case_participant_role_skips_when_no_receiving_actor(
        self, make_payload
    ):
        """OfferCaseParticipantRoleReceivedUseCase skips when receiving_actor_id is None."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        offer = self._make_offer()
        event = make_payload(offer, receiving_actor_id=None)

        OfferCaseParticipantRoleReceivedUseCase(dl, event).execute()

        stored = dl.get(offer.type_.value, offer.id_)
        assert stored is None

    def test_offer_case_participant_role_coordinator_persists(
        self, make_payload
    ):
        """OfferCaseParticipantRoleReceivedUseCase works for any CVDRole, not just CASE_MANAGER."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        offer = self._make_offer(role=CVDRole.COORDINATOR)
        event = make_payload(offer, receiving_actor_id=self._CASE_ACTOR_URI)

        OfferCaseParticipantRoleReceivedUseCase(dl, event).execute()

        stored = dl.get(offer.type_.value, offer.id_)
        assert stored is not None

    def test_offer_case_participant_role_auto_accepts_when_trigger_given(
        self, make_payload
    ):
        """OfferCaseParticipantRoleReceivedUseCase auto-accepts when trigger_activity provided."""
        from unittest.mock import MagicMock
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        offer = self._make_offer()
        event = make_payload(offer, receiving_actor_id=self._CASE_ACTOR_URI)

        trigger = MagicMock()
        trigger.accept_case_manager_role.return_value = (
            "https://example.org/activities/accept-1",
            {"type": "Accept", "actor": self._CASE_ACTOR_URI},
        )

        OfferCaseParticipantRoleReceivedUseCase(
            dl, event, trigger_activity=trigger
        ).execute()

        trigger.accept_case_manager_role.assert_called_once()
        call_kwargs = trigger.accept_case_manager_role.call_args
        assert call_kwargs.kwargs["offer_id"] == offer.id_
        assert call_kwargs.kwargs["vendor_id"] == self._VENDOR_URI
