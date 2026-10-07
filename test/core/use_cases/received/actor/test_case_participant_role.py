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

import json
import logging
from unittest.mock import MagicMock

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.actor.accept_reject_case_participant_role import (
    AcceptCaseParticipantRoleReceivedUseCase,
    RejectCaseParticipantRoleReceivedUseCase,
)
from vultron.core.use_cases.received.actor.case_participant_role import (
    OfferCaseParticipantRoleReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    accept_case_participant_role_activity,
    offer_case_participant_role_activity,
    reject_case_participant_role_activity,
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

    def _execute(self, dl, event):
        """Run the handler wired as production wires it: with a trigger port.

        Without one the tree cannot answer the offer, which is a wiring fault
        that raises rather than a refusal (#2255).
        """
        trigger = MagicMock()
        trigger.accept_case_participant_role.return_value = (
            "https://example.org/activities/accept-1",
            json.dumps({"type": "Accept", "actor": self._CASE_ACTOR_URI}),
        )
        return OfferCaseParticipantRoleReceivedUseCase(
            dl, event, trigger_activity=trigger
        ).execute()

    def _seed_case(self, dl):
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        dl.create(
            as_VulnerabilityCase(
                id_=self._CASE_URI,
                name="ROLE-TEST",
                attributed_to=self._VENDOR_URI,
            )
        )

    def test_offer_case_participant_role_persists_offer(self, make_payload):
        """OfferCaseParticipantRoleReceivedUseCase persists the offer activity."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=self._CASE_ACTOR_URI,
        )
        offer = self._make_offer()
        event = make_payload(offer, receiving_actor_id=self._CASE_ACTOR_URI)

        self._execute(dl, event)

        assert _archived_by_intake(dl, offer.id_)

    def test_offer_case_participant_role_idempotent(self, make_payload):
        """Repeated execution of OfferCaseParticipantRoleReceivedUseCase is a no-op."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=self._CASE_ACTOR_URI,
        )
        offer = self._make_offer()
        event = make_payload(offer, receiving_actor_id=self._CASE_ACTOR_URI)

        self._execute(dl, event)
        self._execute(dl, event)

        assert _archived_by_intake(dl, offer.id_)

    def test_offer_case_participant_role_uses_store_owner_when_no_receiving_actor(
        self, make_payload
    ):
        """When receiving_actor_id is absent the store owner processes the offer."""

        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=self._CASE_ACTOR_URI,
        )
        offer = self._make_offer()
        event = make_payload(offer, receiving_actor_id=None)

        self._execute(dl, event)

        # The BT runs under the store owner's identity; the tree stores the
        # offer idempotently regardless of receiving_actor_id stamp.
        assert _archived_by_intake(dl, offer.id_)

    def test_offer_case_participant_role_coordinator_persists(
        self, make_payload
    ):
        """OfferCaseParticipantRoleReceivedUseCase works for any CVDRole, not just CASE_MANAGER."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=self._CASE_ACTOR_URI,
        )
        offer = self._make_offer(role=CVDRole.COORDINATOR)
        event = make_payload(offer, receiving_actor_id=self._CASE_ACTOR_URI)

        self._execute(dl, event)

        assert _archived_by_intake(dl, offer.id_)

    def test_offer_case_participant_role_auto_accepts_when_trigger_given(
        self, make_payload
    ):
        """OfferCaseParticipantRoleReceivedUseCase auto-accepts when trigger_activity provided."""
        from unittest.mock import MagicMock

        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=self._CASE_ACTOR_URI,
        )
        offer = self._make_offer()
        event = make_payload(offer, receiving_actor_id=self._CASE_ACTOR_URI)

        trigger = MagicMock()
        # The port returns the payload snapshot as a JSON string.
        trigger.accept_case_participant_role.return_value = (
            "https://example.org/activities/accept-1",
            json.dumps({"type": "Accept", "actor": self._CASE_ACTOR_URI}),
        )

        OfferCaseParticipantRoleReceivedUseCase(
            dl, event, trigger_activity=trigger
        ).execute()

        trigger.accept_case_participant_role.assert_called_once()
        call_kwargs = trigger.accept_case_participant_role.call_args
        assert call_kwargs.kwargs["offer_id"] == offer.id_
        assert call_kwargs.kwargs["vendor_id"] == self._VENDOR_URI

    @pytest.mark.spec("HP-01-003")
    def test_offer_case_participant_role_auto_accept_is_applied(
        self, make_payload
    ):
        """An auto-accepted, ledgered and queued Accept is APPLIED."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.adapters.driven.trigger_activity_adapter import (
            TriggerActivityAdapter,
        )

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=self._CASE_ACTOR_URI,
        )
        self._seed_case(dl)
        offer = self._make_offer()
        event = make_payload(offer, receiving_actor_id=self._CASE_ACTOR_URI)

        result = OfferCaseParticipantRoleReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        assert result.disposition is HandlerDisposition.APPLIED
        assert len(dl.outbox_list()) == 1

    @pytest.mark.spec("HP-01-003")
    def test_offer_case_participant_role_refused_when_neither_reply_sent(
        self, make_payload
    ):
        """When the actor can neither Accept nor Reject, the offer is refused."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=self._CASE_ACTOR_URI,
        )
        offer = self._make_offer()
        event = make_payload(offer, receiving_actor_id=self._CASE_ACTOR_URI)

        trigger = MagicMock()
        trigger.accept_case_participant_role.side_effect = RuntimeError("down")
        trigger.reject_case_participant_role.side_effect = RuntimeError("down")

        result = OfferCaseParticipantRoleReceivedUseCase(
            dl, event, trigger_activity=trigger
        ).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason


class TestAcceptCaseParticipantRoleReceivedUseCase:
    """Tests for AcceptCaseParticipantRoleReceivedUseCase (ADR-0039, SE-08-003)."""

    _VENDOR_URI = "https://example.org/actors/vendor"
    _CASE_ACTOR_URI = "https://example.org/actors/case-actor"
    _CASE_URI = "https://example.org/cases/urn:uuid:test-case-role"

    def _make_offer(self):
        from vultron.wire.as2.vocab.base.objects.actors import as_Actor
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        case = as_VulnerabilityCase(id_=self._CASE_URI, name="ROLE-TEST")
        actor = as_Actor(id_=self._CASE_ACTOR_URI)
        return offer_case_participant_role_activity(
            role=CVDRole.CASE_MANAGER,
            target_actor=actor,
            case=case,
            actor=self._VENDOR_URI,
        )

    def test_accept_case_participant_role_persists_acceptance(
        self, make_payload
    ):
        """AcceptCaseParticipantRoleReceivedUseCase persists the Accept activity."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        # The Accept is authored by the case actor and received by the vendor
        # that made the offer, so this is the *vendor's* own store: with no
        # receiving_actor_id on the payload, the receiving actor resolves to
        # whoever owns the store we hand in (ADR-0073).
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=self._VENDOR_URI)
        offer = self._make_offer()
        accept = accept_case_participant_role_activity(
            offer, actor=self._CASE_ACTOR_URI
        )
        event = make_payload(accept)

        result = AcceptCaseParticipantRoleReceivedUseCase(dl, event).execute()

        assert result.disposition is HandlerDisposition.APPLIED
        assert _archived_by_intake(dl, accept.id_)

    def test_accept_case_participant_role_idempotent(self, make_payload):
        """Repeated AcceptCaseParticipantRoleReceivedUseCase execution is a no-op."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        # The Accept is authored by the case actor and received by the vendor
        # that made the offer, so this is the *vendor's* own store: with no
        # receiving_actor_id on the payload, the receiving actor resolves to
        # whoever owns the store we hand in (ADR-0073).
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=self._VENDOR_URI)
        offer = self._make_offer()
        accept = accept_case_participant_role_activity(
            offer, actor=self._CASE_ACTOR_URI
        )
        event = make_payload(accept)

        first = AcceptCaseParticipantRoleReceivedUseCase(dl, event).execute()
        second = AcceptCaseParticipantRoleReceivedUseCase(dl, event).execute()

        assert first.disposition is HandlerDisposition.APPLIED
        assert second.disposition is HandlerDisposition.SKIPPED

        assert _archived_by_intake(dl, accept.id_)

    def test_accept_case_participant_role_logs_acceptance(
        self, caplog, make_payload
    ):
        """AcceptCaseParticipantRoleReceivedUseCase logs acceptance at INFO level."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        # The Accept is authored by the case actor and received by the vendor
        # that made the offer, so this is the *vendor's* own store: with no
        # receiving_actor_id on the payload, the receiving actor resolves to
        # whoever owns the store we hand in (ADR-0073).
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=self._VENDOR_URI)
        offer = self._make_offer()
        accept = accept_case_participant_role_activity(
            offer, actor=self._CASE_ACTOR_URI
        )
        event = make_payload(accept)

        with caplog.at_level(logging.INFO):
            AcceptCaseParticipantRoleReceivedUseCase(dl, event).execute()

        assert any("accepted" in r.message.lower() for r in caplog.records)


class TestRejectCaseParticipantRoleReceivedUseCase:
    """Tests for RejectCaseParticipantRoleReceivedUseCase (ADR-0039, SE-08-003)."""

    _VENDOR_URI = "https://example.org/actors/vendor"
    _CASE_ACTOR_URI = "https://example.org/actors/case-actor"
    _CASE_URI = "https://example.org/cases/urn:uuid:test-case-role"

    def _make_offer(self):
        from vultron.wire.as2.vocab.base.objects.actors import as_Actor
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        case = as_VulnerabilityCase(id_=self._CASE_URI, name="ROLE-TEST")
        actor = as_Actor(id_=self._CASE_ACTOR_URI)
        return offer_case_participant_role_activity(
            role=CVDRole.CASE_MANAGER,
            target_actor=actor,
            case=case,
            actor=self._VENDOR_URI,
        )

    def test_reject_case_participant_role_logs_warning(
        self, caplog, make_payload
    ):
        """RejectCaseParticipantRoleReceivedUseCase logs a warning without raising."""
        offer = self._make_offer()
        reject = reject_case_participant_role_activity(
            offer, actor=self._CASE_ACTOR_URI
        )
        event = make_payload(reject)
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=self._VENDOR_URI)

        with caplog.at_level(logging.WARNING):
            result = RejectCaseParticipantRoleReceivedUseCase(
                dl, event
            ).execute()

        assert any("rejected" in r.message.lower() for r in caplog.records)
        # A declined offer leaves nothing on this side to change.
        assert result.disposition is HandlerDisposition.SKIPPED
        # The run still archives the Reject that arrived (CLP-10-017).
        assert _archived_by_intake(dl, reject.id_)
