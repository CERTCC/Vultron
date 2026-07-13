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
"""Tests for case manager role delegation received use cases."""

import logging
from unittest.mock import MagicMock

from vultron.core.use_cases.received.actor.case_manager_role import (
    AcceptCaseManagerRoleReceivedUseCase,
    OfferCaseManagerRoleReceivedUseCase,
    RejectCaseManagerRoleReceivedUseCase,
)
from vultron.wire.as2.factories import (
    accept_case_manager_role_activity,
    offer_case_manager_role_activity,
    reject_case_manager_role_activity,
)


class TestCaseManagerRoleDelegationUseCases:
    """Tests for offer/accept/reject CASE_MANAGER role delegation use cases.

    DEMOMA-08-002: CASE_MANAGER delegation is distinct from ownership transfer.
    """

    _VENDOR_URI = "https://example.org/actors/vendor"
    _CASE_ACTOR_URI = "https://example.org/actors/case-actor"
    _CASE_URI = "https://example.org/cases/urn:uuid:test-case-mgr"
    _PARTICIPANT_URI = (
        "https://example.org/participants/urn:uuid:case-actor-participant"
    )

    def _make_offer(self):
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        case = VulnerabilityCase(id_=self._CASE_URI, name="CASE-MGR-TEST")
        participant = CaseParticipant(
            id_=self._PARTICIPANT_URI,
            attributed_to=self._CASE_ACTOR_URI,
            context=self._CASE_URI,
        )
        return offer_case_manager_role_activity(
            case,
            target=participant,
            actor=self._VENDOR_URI,
        )

    def test_offer_case_manager_role_persists_offer(self, make_payload):
        """OfferCaseManagerRoleReceivedUseCase persists the offer activity."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer("sqlite:///:memory:")
        offer = self._make_offer()
        event = make_payload(offer, receiving_actor_id=self._CASE_ACTOR_URI)

        OfferCaseManagerRoleReceivedUseCase(dl, event).execute()

        stored = dl.get(offer.type_.value, offer.id_)
        assert stored is not None

    def test_offer_case_manager_role_idempotent(self, make_payload):
        """Repeated execution of OfferCaseManagerRoleReceivedUseCase is a no-op."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer("sqlite:///:memory:")
        offer = self._make_offer()
        event = make_payload(offer, receiving_actor_id=self._CASE_ACTOR_URI)

        OfferCaseManagerRoleReceivedUseCase(dl, event).execute()
        OfferCaseManagerRoleReceivedUseCase(dl, event).execute()

        stored = dl.get(offer.type_.value, offer.id_)
        assert stored is not None

    def test_accept_case_manager_role_persists_acceptance(self, make_payload):
        """AcceptCaseManagerRoleReceivedUseCase persists the acceptance activity."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer("sqlite:///:memory:")
        offer = self._make_offer()
        accept = accept_case_manager_role_activity(
            offer, actor=self._CASE_ACTOR_URI
        )
        event = make_payload(accept)

        AcceptCaseManagerRoleReceivedUseCase(dl, event).execute()

        stored = dl.get(accept.type_.value, accept.id_)
        assert stored is not None

    def test_accept_case_manager_role_logs_acceptance(
        self, caplog, make_payload
    ):
        """AcceptCaseManagerRoleReceivedUseCase logs acceptance without raising."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer("sqlite:///:memory:")
        offer = self._make_offer()
        accept = accept_case_manager_role_activity(
            offer, actor=self._CASE_ACTOR_URI
        )
        event = make_payload(accept)

        with caplog.at_level(logging.INFO):
            AcceptCaseManagerRoleReceivedUseCase(dl, event).execute()

        assert any("accepted" in r.message.lower() for r in caplog.records)

    def test_reject_case_manager_role_logs_warning(self, caplog, make_payload):
        """RejectCaseManagerRoleReceivedUseCase logs a warning without raising."""
        offer = self._make_offer()
        reject = reject_case_manager_role_activity(
            offer, actor=self._CASE_ACTOR_URI
        )
        event = make_payload(reject)

        with caplog.at_level(logging.WARNING):
            RejectCaseManagerRoleReceivedUseCase(MagicMock(), event).execute()

        assert any("rejected" in r.message.lower() for r in caplog.records)

    def test_offer_case_manager_role_auto_accepts_when_trigger_given(
        self, make_payload
    ):
        """OfferCaseManagerRoleReceivedUseCase auto-accepts when trigger_activity provided."""
        from unittest.mock import MagicMock
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer("sqlite:///:memory:")

        offer = self._make_offer()
        event = make_payload(offer, receiving_actor_id=self._CASE_ACTOR_URI)

        trigger = MagicMock()
        trigger.accept_case_manager_role.return_value = (
            "https://example.org/activities/accept-1"
        )

        OfferCaseManagerRoleReceivedUseCase(
            dl, event, trigger_activity=trigger
        ).execute()

        trigger.accept_case_manager_role.assert_called_once()
        call_kwargs = trigger.accept_case_manager_role.call_args
        assert call_kwargs.kwargs["offer_id"] == offer.id_
        assert call_kwargs.kwargs["vendor_id"] == self._VENDOR_URI

    def test_offer_case_manager_role_no_auto_accept_without_trigger(
        self, make_payload
    ):
        """OfferCaseManagerRoleReceivedUseCase skips auto-accept when trigger_activity is None."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer("sqlite:///:memory:")
        offer = self._make_offer()
        event = make_payload(offer, receiving_actor_id=self._CASE_ACTOR_URI)

        # No trigger_activity — should not raise
        OfferCaseManagerRoleReceivedUseCase(dl, event).execute()

        stored = dl.get(offer.type_.value, offer.id_)
        assert stored is not None

    def test_accept_case_manager_role_sends_bootstrap_when_reporter_found(
        self, make_payload
    ):
        """AcceptCaseManagerRoleReceivedUseCase sends Create(Case) to Reporter on accept."""
        from unittest.mock import MagicMock, patch
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization
        from vultron.core.models.vultron_types import VultronParticipant
        from vultron.core.states.roles import CVDRole
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        vendor = as_Organization(id_=self._VENDOR_URI)
        reporter_id = "https://example.org/actors/reporter"
        reporter_participant_id = f"{self._CASE_URI}/participants/reporter"
        reporter_participant = VultronParticipant(
            id_=reporter_participant_id,
            attributed_to=reporter_id,
            context=self._CASE_URI,
            name="Reporter",
            case_roles=[CVDRole.FINDER, CVDRole.REPORTER],
        )
        case = VulnerabilityCase(id_=self._CASE_URI, name="BOOTSTRAP-TEST")
        case.actor_participant_index[reporter_id] = reporter_participant_id
        dl.create(vendor)
        dl.create(reporter_participant)
        dl.create(case)

        offer = self._make_offer()
        accept = accept_case_manager_role_activity(
            offer, actor=self._CASE_ACTOR_URI
        )
        event = make_payload(accept)

        trigger = MagicMock()
        trigger.create_case.return_value = (
            "https://example.org/activities/create-1",
            {},
        )

        with patch("vultron.core.use_cases._helpers.add_activity_to_outbox"):
            AcceptCaseManagerRoleReceivedUseCase(
                dl, event, trigger_activity=trigger
            ).execute()

        trigger.create_case.assert_called_once()
        call_kwargs = trigger.create_case.call_args
        assert call_kwargs.kwargs.get("to") == [reporter_id] or (
            len(call_kwargs.args) >= 3 and reporter_id in call_kwargs.args
        )

    def test_accept_case_manager_role_no_bootstrap_without_trigger(
        self, make_payload
    ):
        """AcceptCaseManagerRoleReceivedUseCase skips bootstrap when trigger_activity is None."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer("sqlite:///:memory:")
        offer = self._make_offer()
        accept = accept_case_manager_role_activity(
            offer, actor=self._CASE_ACTOR_URI
        )
        event = make_payload(accept)

        # No trigger_activity — should not raise
        AcceptCaseManagerRoleReceivedUseCase(dl, event).execute()

        stored = dl.get(accept.type_.value, accept.id_)
        assert stored is not None

    def test_offer_case_manager_role_reject_emitted_when_accept_fails(
        self, make_payload
    ):
        """When auto-accept raises, EmitRejectCaseManagerRoleNode fires instead."""
        from unittest.mock import MagicMock
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")

        # Seed DL so EmitRejectCaseManagerRoleNode can reconstruct the offer
        case = VulnerabilityCase(id_=self._CASE_URI, name="REJECT-TEST")
        participant = CaseParticipant(
            id_=self._PARTICIPANT_URI,
            attributed_to=self._CASE_ACTOR_URI,
            context=self._CASE_URI,
        )
        dl.create(case)
        dl.create(participant)

        offer = self._make_offer()
        event = make_payload(offer, receiving_actor_id=self._CASE_ACTOR_URI)

        reject_id = "https://example.org/activities/reject-cm-fallback"
        trigger = MagicMock()
        trigger.accept_case_manager_role.side_effect = RuntimeError(
            "accept unavailable"
        )
        trigger.reject_case_manager_role.return_value = reject_id

        OfferCaseManagerRoleReceivedUseCase(
            dl, event, trigger_activity=trigger
        ).execute()

        trigger.reject_case_manager_role.assert_called_once_with(
            offer_id=offer.id_,
            case_id=self._CASE_URI,
            participant_id=self._PARTICIPANT_URI,
            vendor_id=self._VENDOR_URI,
            actor=self._CASE_ACTOR_URI,
            to=[self._VENDOR_URI],
        )

    def test_offer_case_manager_role_outbox_failure_does_not_emit_reject(
        self, make_payload
    ):
        """Outbox failure after Accept is persisted must NOT trigger Reject.

        Regression for the broad-exception anti-pattern: when
        accept_case_manager_role() succeeds (Accept written to DataLayer) but
        record_outbox_item() then fails, the exception must propagate through
        py_trees (bypassing the AcceptOrReject Selector fallback) so that
        BTBridge fails the tree hard without emitting a contradictory Reject.
        """
        from unittest.mock import MagicMock, patch
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        case = VulnerabilityCase(id_=self._CASE_URI, name="OUTBOX-FAIL-TEST")
        participant = CaseParticipant(
            id_=self._PARTICIPANT_URI,
            attributed_to=self._CASE_ACTOR_URI,
            context=self._CASE_URI,
        )
        dl.create(case)
        dl.create(participant)

        offer = self._make_offer()
        event = make_payload(offer, receiving_actor_id=self._CASE_ACTOR_URI)

        trigger = MagicMock()
        trigger.accept_case_manager_role.return_value = (
            "https://example.org/activities/accept-outbox-fail"
        )

        # Accept creation succeeds, but outbox enqueue fails.
        with patch.object(
            dl,
            "record_outbox_item",
            side_effect=RuntimeError("outbox unavailable"),
        ):
            # BTBridge swallows the exception; execute() must not raise.
            OfferCaseManagerRoleReceivedUseCase(
                dl, event, trigger_activity=trigger
            ).execute()

        # The Reject must NOT have been emitted — Accept was already persisted.
        trigger.reject_case_manager_role.assert_not_called()

    def test_offer_case_manager_role_reject_uses_adapter_when_accept_fails(
        self, make_payload
    ):
        """reject_case_manager_role adapter method is called with correct args."""
        from unittest.mock import MagicMock
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )
        from vultron.adapters.driven.trigger_activity_adapter import (
            TriggerActivityAdapter,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        case = VulnerabilityCase(id_=self._CASE_URI, name="ADAPTER-REJECT")
        participant = CaseParticipant(
            id_=self._PARTICIPANT_URI,
            attributed_to=self._CASE_ACTOR_URI,
            context=self._CASE_URI,
        )
        dl.create(case)
        dl.create(participant)

        offer = self._make_offer()
        event = make_payload(offer, receiving_actor_id=self._CASE_ACTOR_URI)

        # Use a real adapter wrapped so accept raises but reject succeeds
        real_adapter = TriggerActivityAdapter(dl)
        patched = MagicMock(wraps=real_adapter)
        patched.accept_case_manager_role.side_effect = RuntimeError(
            "accept unavailable"
        )

        OfferCaseManagerRoleReceivedUseCase(
            dl, event, trigger_activity=patched
        ).execute()

        patched.reject_case_manager_role.assert_called_once()
        kwargs = patched.reject_case_manager_role.call_args.kwargs
        assert kwargs["offer_id"] == offer.id_
        assert kwargs["vendor_id"] == self._VENDOR_URI
