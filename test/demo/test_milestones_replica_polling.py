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

"""Regression tests for reporter-replica polling in ``verify_case_active``.

The reporter's case replica arrives via the receiver's outbox, which runs as a
background task.  The receiver-side participant count can reach its target tens
of milliseconds before the reporter has processed
``Create(VulnerabilityCase)``, so ``verify_case_active`` must poll for the
replica rather than read once.  Reading once produced an intermittent
``404 Not Found`` on ``/datalayer/<case_id>`` at the fcv M1 milestone.

Scenarios that already call ``wait_for_case_on_container`` themselves are
unaffected — the extra poll returns on its first attempt.
"""

from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from vultron.demo.helpers.milestones import verify_case_active
from vultron.demo.helpers.polling import (
    _is_ownership_transfer_offer_for,
    find_ownership_transfer_offer_for_actor,
)
from vultron.demo.utils import DataLayerClient

_CASE_ID = "urn:uuid:test-case-replica-0001"
_RECEIVER_ID = "http://coordinator:7999/api/v2/actors/coordinator"
_REPORTER_ID = "http://finder:7999/api/v2/actors/finder"
_CASE_ACTOR_ID = "http://coordinator:7999/api/v2/actors/case-actor-1"


def _receiver_case_payload() -> dict:
    """Minimal receiver-side case satisfying the pre-replica assertions."""
    return {
        "id": _CASE_ID,
        "type": "VulnerabilityCase",
        "actorParticipantIndex": {
            _RECEIVER_ID: "urn:uuid:p-receiver",
            _REPORTER_ID: "urn:uuid:p-reporter",
            _CASE_ACTOR_ID: "urn:uuid:p-case-actor",
        },
        "caseStatuses": [
            {
                "id": "urn:uuid:cs-1",
                "type": "CaseStatus",
                "context": _CASE_ID,
                "em": {"state": "ACTIVE"},
                "pxa": {"state": "pxa"},
            }
        ],
        "activeEmbargo": "urn:uuid:embargo-1",
    }


def _reporter_case_payload() -> dict:
    payload = _receiver_case_payload()
    payload["caseStatuses"] = []
    return payload


def _receiver_client() -> MagicMock:
    client = MagicMock()
    client.get.return_value = _receiver_case_payload()
    return client


class _LateReporterClient:
    """Reporter client whose replica appears only after *delay* GET calls."""

    #: Borrowed from the real client so the stub cannot drift from the path the
    #: helpers actually request.  A stub that hard-codes ``/datalayer/...`` keeps
    #: answering after the production path changes shape, which is how these
    #: stubs survived the move to ``/actors/{segment}/datalayer/`` unnoticed.
    dl_path = DataLayerClient.dl_path

    def __init__(self, delay: int) -> None:
        self.base_url = "http://finder:7999/api/v2"
        self.actor_id = _REPORTER_ID
        self._delay = delay
        self.calls = 0

    def get(self, path: str) -> dict | None:
        if path.endswith("/VulnerabilityCases/"):
            self.calls += 1
            if self.calls <= self._delay:
                return {}
            return {_CASE_ID: {}}
        return _reporter_case_payload() if self.calls > self._delay else None


def _as_client(stub: object) -> DataLayerClient:
    """Cast a duck-typed stub to ``DataLayerClient``.

    ``DataLayerClient`` is a concrete Pydantic model rather than a Protocol, so
    a stub cannot subclass it without inheriting the httpx machinery these
    tests exist to avoid.
    """
    return cast(DataLayerClient, stub)


class TestVerifyCaseActivePollsForReporterReplica:
    def test_succeeds_when_replica_arrives_late(self):
        """A replica that lands after the first poll must not fail M1."""
        reporter = _LateReporterClient(delay=2)

        verify_case_active(
            receiver_client=_as_client(_receiver_client()),
            reporter_client=_as_client(reporter),
            case_id=_CASE_ID,
            receiver_actor_id=_RECEIVER_ID,
            reporter_actor_id=_REPORTER_ID,
        )

        assert reporter.calls > 2, "helper must have polled more than once"

    def test_still_fails_when_replica_never_arrives(self):
        """The poll must not mask a genuinely missing replica."""
        reporter = _LateReporterClient(delay=10**6)

        with patch(
            "vultron.demo.helpers.milestones.wait_for_case_on_container",
            side_effect=AssertionError("Timed out waiting for case"),
        ):
            with pytest.raises(AssertionError, match="Timed out waiting"):
                verify_case_active(
                    receiver_client=_as_client(_receiver_client()),
                    reporter_client=_as_client(reporter),
                    case_id=_CASE_ID,
                    receiver_actor_id=_RECEIVER_ID,
                    reporter_actor_id=_REPORTER_ID,
                )


# ---------------------------------------------------------------------------
# Bug #2178: forwarded-Offer polling helpers for ownership transfer
# ---------------------------------------------------------------------------

_OT_CASE_ID = "urn:uuid:ot-case-0001"
_OT_TRANSFEREE_ID = "http://coordinator:7999/api/v2/actors/coordinator"
_OT_FORWARDED_OFFER_ID = "urn:uuid:forwarded-offer-0001"
_OT_ORIGINAL_OFFER_ID = "urn:uuid:original-offer-0001"
_OT_CASE_ACTOR_ID = "http://vendor:7999/api/v2/actors/case-actor-1"


def _forwarded_offer_payload() -> dict:
    """Wire payload of a forwarded Offer(VulnerabilityCase) from CaseActor to transferee."""
    return {
        "type": "Offer",
        "target": _OT_TRANSFEREE_ID,
        "object": {"id": _OT_CASE_ID, "type": "VulnerabilityCase"},
    }


class TestIsOwnershipTransferOfferFor:
    """Unit tests for the _is_ownership_transfer_offer_for discriminator (Bug #2178)."""

    def test_matches_forwarded_offer_with_dict_object(self):
        obj = _forwarded_offer_payload()
        assert _is_ownership_transfer_offer_for(
            obj, _OT_CASE_ID, _OT_TRANSFEREE_ID
        )

    def test_matches_offer_with_bare_string_object(self):
        obj = {
            "type": "Offer",
            "target": _OT_TRANSFEREE_ID,
            "object": _OT_CASE_ID,
        }
        assert _is_ownership_transfer_offer_for(
            obj, _OT_CASE_ID, _OT_TRANSFEREE_ID
        )

    def test_matches_offer_with_dict_target(self):
        obj = {
            "type": "Offer",
            "target": {"id": _OT_TRANSFEREE_ID, "type": "Service"},
            "object": {"id": _OT_CASE_ID, "type": "VulnerabilityCase"},
        }
        assert _is_ownership_transfer_offer_for(
            obj, _OT_CASE_ID, _OT_TRANSFEREE_ID
        )

    def test_rejects_wrong_activity_type(self):
        obj = {
            "type": "Accept",
            "target": _OT_TRANSFEREE_ID,
            "object": {"id": _OT_CASE_ID},
        }
        assert not _is_ownership_transfer_offer_for(
            obj, _OT_CASE_ID, _OT_TRANSFEREE_ID
        )

    def test_rejects_wrong_transferee(self):
        obj = {
            "type": "Offer",
            "target": "http://other:7999/api/v2/actors/other",
            "object": {"id": _OT_CASE_ID},
        }
        assert not _is_ownership_transfer_offer_for(
            obj, _OT_CASE_ID, _OT_TRANSFEREE_ID
        )

    def test_rejects_wrong_case_id(self):
        obj = {
            "type": "Offer",
            "target": _OT_TRANSFEREE_ID,
            "object": {"id": "urn:uuid:different-case"},
        }
        assert not _is_ownership_transfer_offer_for(
            obj, _OT_CASE_ID, _OT_TRANSFEREE_ID
        )

    def test_original_offer_to_case_actor_not_matched(self):
        """The ORIGINAL Offer addressed to the CaseActor must not match (wrong target)."""
        original = {
            "type": "Offer",
            "target": _OT_CASE_ACTOR_ID,  # addressed to CaseActor, not transferee
            "object": {"id": _OT_CASE_ID, "type": "VulnerabilityCase"},
        }
        assert not _is_ownership_transfer_offer_for(
            original, _OT_CASE_ID, _OT_TRANSFEREE_ID
        )


class _LateOTOfferClient:
    """Coordinator client where the forwarded Offer appears only after *delay* GET calls."""

    dl_path = DataLayerClient.dl_path

    def __init__(self, delay: int) -> None:
        self.base_url = "http://coordinator:7999/api/v2"
        self.actor_id = _OT_TRANSFEREE_ID
        self._delay = delay
        self.calls = 0

    def get(self, path: str) -> dict | None:
        if path == self.dl_path():
            self.calls += 1
            if self.calls <= self._delay:
                return {}
            return {_OT_FORWARDED_OFFER_ID: _forwarded_offer_payload()}
        return None


class TestFindOwnershipTransferOfferForActor:
    """find_ownership_transfer_offer_for_actor polls Coordinator for the forwarded Offer (Bug #2178)."""

    def test_returns_forwarded_offer_id_immediately(self):
        client = _LateOTOfferClient(delay=0)
        result = find_ownership_transfer_offer_for_actor(
            client=cast(DataLayerClient, client),
            case_id=_OT_CASE_ID,
            transferee_id=_OT_TRANSFEREE_ID,
            timeout_seconds=5.0,
            poll_interval=0.05,
        )
        assert result == _OT_FORWARDED_OFFER_ID

    def test_returns_forwarded_offer_id_when_arrives_late(self):
        client = _LateOTOfferClient(delay=2)
        result = find_ownership_transfer_offer_for_actor(
            client=cast(DataLayerClient, client),
            case_id=_OT_CASE_ID,
            transferee_id=_OT_TRANSFEREE_ID,
            timeout_seconds=5.0,
            poll_interval=0.05,
        )
        assert result == _OT_FORWARDED_OFFER_ID
        assert (
            client.calls > 2
        ), "helper must have polled more than once before finding offer"

    def test_raises_assertion_error_on_timeout(self):
        client = _LateOTOfferClient(delay=10**6)
        with pytest.raises(AssertionError, match="Timed out"):
            find_ownership_transfer_offer_for_actor(
                client=cast(DataLayerClient, client),
                case_id=_OT_CASE_ID,
                transferee_id=_OT_TRANSFEREE_ID,
                timeout_seconds=0.1,
                poll_interval=0.5,
            )

    def test_does_not_match_original_offer_sent_to_case_actor(self):
        """Original Offer (target=CaseActor) must never satisfy the poll — Bug #2178 root cause."""
        client = MagicMock()
        client.base_url = "http://coordinator:7999/api/v2"
        client.get.return_value = {
            _OT_ORIGINAL_OFFER_ID: {
                "type": "Offer",
                "target": _OT_CASE_ACTOR_ID,  # sent to CaseActor, NOT to transferee
                "object": {"id": _OT_CASE_ID, "type": "VulnerabilityCase"},
            }
        }
        with pytest.raises(AssertionError, match="Timed out"):
            find_ownership_transfer_offer_for_actor(
                client=cast(DataLayerClient, client),
                case_id=_OT_CASE_ID,
                transferee_id=_OT_TRANSFEREE_ID,
                timeout_seconds=0.1,
                poll_interval=0.5,
            )
