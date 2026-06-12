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
    VulnerabilityCase,
)


class TestOwnershipTransferUseCases:
    """Tests for offer/accept/reject ownership transfer use cases."""

    def test_offer_case_ownership_transfer_persists_offer(
        self, monkeypatch, make_payload
    ):
        """OfferCaseOwnershipTransferReceivedUseCase persists the offer."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer("sqlite:///:memory:")

        case = VulnerabilityCase(
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
        self, monkeypatch, make_payload
    ):
        """AcceptCaseOwnershipTransferReceivedUseCase updates case.attributed_to to new owner."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        dl = SqliteDataLayer("sqlite:///:memory:")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_ot2",
            name="OT Case 2",
            attributed_to="https://example.org/users/vendor",
        )
        dl.create(case)

        offer = offer_case_ownership_transfer_activity(
            case,
            target="https://example.org/users/coordinator",
            actor="https://example.org/users/vendor",
            id_="https://example.org/activities/offer_ot2",
        )
        dl.create(offer)

        activity = accept_case_ownership_transfer_activity(
            offer,
            actor="https://example.org/users/coordinator",
        )
        event = make_payload(activity)

        AcceptCaseOwnershipTransferReceivedUseCase(dl, event).execute()

        updated_record = dl.get(case.type_.value, case.id_)
        assert updated_record is not None
        data = cast(Any, updated_record).get("data_", updated_record)
        assert (
            data.get("attributed_to")
            == "https://example.org/users/coordinator"
        )

    def test_reject_case_ownership_transfer_logs_rejection(
        self, monkeypatch, caplog, make_payload
    ):
        """RejectCaseOwnershipTransferReceivedUseCase logs rejection; ownership unchanged."""
        case = VulnerabilityCase(
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
