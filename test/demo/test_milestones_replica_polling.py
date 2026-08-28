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

"""Regression tests for reporter-replica polling in milestone helpers.

Covers two async race patterns (Bugs #2134-adjacent and #2376):

1. ``verify_case_active`` — reporter's case replica arrives via an async
   outbox delivery, so the helper must poll rather than read once.
2. ``verify_publicly_disclosed`` — after ``actor_notifies_published`` returns
   HTTP 202, the CaseActor's ``Add(CaseStatus)`` broadcast may not have
   reached the reporter's DataLayer yet.  ``verify_publicly_disclosed`` must
   poll for the reporter's pxa_state before asserting it (ADR-0058).
3. ``wait_for_participant_pxa_state`` — underlying pxa polling helper must
   retry until pxa_state is public-aware and raise on timeout.
"""

from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from vultron.core.states.cs import CS_pxa
from vultron.demo.helpers.milestones import (
    verify_case_active,
    verify_publicly_disclosed,
)
from vultron.demo.helpers.polling import (
    _is_ownership_transfer_offer_for,
    find_ownership_transfer_offer_for_actor,
    wait_for_initialized_case,
    wait_for_participant_pxa_state,
)
from vultron.demo.utils import DataLayerClient
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

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


def _real_dl_path(base_url: str, actor_id: str, key: str = "") -> str:
    """Build a DataLayer path with the *real* client, for use by stubs.

    Stubs below delegate here rather than hard-coding ``/datalayer/...``: a stub
    that spells the path itself keeps answering after the production path changes
    shape, which is how these stubs survived the move to
    ``/actors/{segment}/datalayer/`` unnoticed.

    Delegation rather than borrowing ``DataLayerClient.dl_path`` as an unbound
    method — which is what these stubs used to do. That passed a non-client
    ``self`` to a method annotated for ``DataLayerClient``, which mypy rejects
    when run over ``test/`` as CI does. The anti-drift property is the same,
    because the real implementation is still what computes the path.
    """
    return DataLayerClient(base_url=base_url, actor_id=actor_id).dl_path(key)


class _LateReporterClient:
    """Reporter client whose replica appears only after *delay* GET calls."""

    def dl_path(self, key: str = "") -> str:
        """Delegate to the real client; see :func:`_real_dl_path`."""
        return _real_dl_path(self.base_url, self.actor_id, key)

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

    def dl_path(self, key: str = "") -> str:
        """Delegate to the real client; see :func:`_real_dl_path`."""
        return _real_dl_path(self.base_url, self.actor_id, key)

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


# ---------------------------------------------------------------------------
# Bug #2376: pxa_state race in verify_publicly_disclosed
# ---------------------------------------------------------------------------

_PXA_CASE_ID = "urn:uuid:pxa-case-0001"
_PXA_RECEIVER_ID = "http://coordinator:7999/api/v2/actors/coordinator"


def _pxa_case_payload(em_state: str = "EXITED") -> dict:
    """Minimal case payload with EM.EXITED and no participants (participants polled separately)."""
    return {
        "id": _PXA_CASE_ID,
        "type": "VulnerabilityCase",
        "actorParticipantIndex": {},
        "caseStatuses": [
            {
                "id": "urn:uuid:cs-pxa-1",
                "type": "CaseStatus",
                "context": _PXA_CASE_ID,
                "em": {"state": em_state},
                "pxa": {"state": "PXA"},
            }
        ],
    }


def _public_aware_participant(actor_id: str) -> MagicMock:
    """A participant whose latest status has a public-aware pxa_state."""
    p = MagicMock()
    p.id_ = f"urn:uuid:participant-{actor_id.split('/')[-1]}"
    p.case_roles = []
    status = MagicMock()
    cs = MagicMock()
    cs.pxa_state = CS_pxa.PXA
    status.case_status = cs
    p.participant_status = status
    p.participant_statuses = [status]
    return p


class TestWaitForParticipantPxaState:
    """wait_for_participant_pxa_state polls until pxa_state is public-aware."""

    def test_returns_immediately_when_already_public_aware(self):
        participant = _public_aware_participant(_PXA_RECEIVER_ID)
        with patch(
            "vultron.demo.helpers.verification._fetch_participant",
            return_value=participant,
        ):
            wait_for_participant_pxa_state(
                client=cast(DataLayerClient, MagicMock(base_url="http://x")),
                case_id=_PXA_CASE_ID,
                actor_id=_PXA_RECEIVER_ID,
                timeout_seconds=5.0,
                poll_interval=0.05,
            )

    def test_polls_until_pxa_becomes_public_aware(self):
        """pxa_state arrives on the 3rd call; helper must retry."""
        call_count = 0
        none_participant = MagicMock()
        none_participant.case_roles = []
        none_status = MagicMock()
        none_cs = MagicMock()
        none_cs.pxa_state = None
        none_status.case_status = none_cs
        none_participant.participant_status = none_status
        none_participant.participant_statuses = [none_status]

        public_participant = _public_aware_participant(_PXA_RECEIVER_ID)

        def _fetch(client, case_id, actor_id):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return none_participant
            return public_participant

        with patch(
            "vultron.demo.helpers.verification._fetch_participant",
            side_effect=_fetch,
        ):
            wait_for_participant_pxa_state(
                client=cast(DataLayerClient, MagicMock(base_url="http://x")),
                case_id=_PXA_CASE_ID,
                actor_id=_PXA_RECEIVER_ID,
                timeout_seconds=5.0,
                poll_interval=0.05,
            )

        assert call_count >= 3

    def test_raises_assertion_error_on_timeout(self):
        none_participant = MagicMock()
        none_status = MagicMock()
        none_cs = MagicMock()
        none_cs.pxa_state = None
        none_status.case_status = none_cs
        none_participant.participant_status = none_status
        none_participant.participant_statuses = [none_status]

        with patch(
            "vultron.demo.helpers.verification._fetch_participant",
            return_value=none_participant,
        ):
            with pytest.raises(AssertionError, match="Timed out"):
                wait_for_participant_pxa_state(
                    client=cast(
                        DataLayerClient, MagicMock(base_url="http://x")
                    ),
                    case_id=_PXA_CASE_ID,
                    actor_id=_PXA_RECEIVER_ID,
                    timeout_seconds=0.1,
                    poll_interval=0.5,
                )


class TestVerifyPubliclyDisclosedPollsReporterPxa:
    """verify_publicly_disclosed must poll reporter's pxa_state before asserting (Bug #2376)."""

    def test_calls_wait_for_participant_pxa_state_on_reporter(self):
        """The pxa polling gate must be called with the reporter client, not the receiver."""
        receiver_client = MagicMock(name="receiver_client")
        reporter_client = MagicMock(name="reporter_client")
        receiver_client.get.return_value = _pxa_case_payload()
        reporter_client.get.return_value = _pxa_case_payload()

        participant = _public_aware_participant(_PXA_RECEIVER_ID)

        with (
            patch(
                "vultron.demo.helpers.milestones.wait_for_participant_pxa_state"
            ) as mock_poll,
            patch(
                "vultron.demo.helpers.milestones._fetch_participant",
                return_value=participant,
            ),
        ):
            verify_publicly_disclosed(
                receiver_client=cast(DataLayerClient, receiver_client),
                reporter_client=cast(DataLayerClient, reporter_client),
                case_id=_PXA_CASE_ID,
                receiver_actor_id=_PXA_RECEIVER_ID,
            )

        mock_poll.assert_called_once_with(
            client=cast(DataLayerClient, reporter_client),
            case_id=_PXA_CASE_ID,
            actor_id=_PXA_RECEIVER_ID,
        )


_IC_REPORT_ID = "urn:uuid:test-report-ic-0001"
_IC_CASE_ACTOR_ID = "http://coordinator:7999/api/v2/actors/case-actor-1"
_IC_CASE_ID = "urn:uuid:test-case-ic-0001"
_IC_PARTICIPANT_ID = "urn:uuid:test-participant-ic-0001"

_IC_INITIALIZED_CASE = {
    "id": _IC_CASE_ID,
    "type": "VulnerabilityCase",
    "case_participants": [
        {"id": _IC_PARTICIPANT_ID, "type": "CaseParticipant"}
    ],
}
_IC_EMPTY_CASE = {
    "id": _IC_CASE_ID,
    "type": "VulnerabilityCase",
    "case_participants": [],
}


class _LateInitializedCaseClient:
    """CaseActor container where the initialized case appears after *delay* GET calls."""

    def dl_path(self, key: str = "", actor_id: str | None = None) -> str:
        return _real_dl_path(self.base_url, actor_id or self.actor_id, key)

    def __init__(self, delay: int, empty_before_init: bool = False) -> None:
        self.base_url = "http://coordinator:7999/api/v2"
        self.actor_id = _IC_CASE_ACTOR_ID
        self._delay = delay
        self._empty_before_init = empty_before_init
        self.calls = 0

    def get(self, path: str) -> dict | None:
        expected = self.dl_path(
            "VulnerabilityCases/", actor_id=_IC_CASE_ACTOR_ID
        )
        if path == expected:
            self.calls += 1
            if self.calls <= self._delay:
                if self._empty_before_init:
                    return {_IC_CASE_ID: _IC_EMPTY_CASE}
                return {}
            return {_IC_CASE_ID: _IC_INITIALIZED_CASE}
        return None


class TestWaitForInitializedCase:
    """wait_for_initialized_case polls the CaseActor's store until participants appear (ISSUE-2359)."""

    def _run(self, client: _LateInitializedCaseClient) -> as_VulnerabilityCase:
        with patch(
            "vultron.demo.utils.case_actor_id_for_report",
            return_value=_IC_CASE_ACTOR_ID,
        ):
            return wait_for_initialized_case(
                client=cast(DataLayerClient, client),
                report_id=_IC_REPORT_ID,
                timeout_seconds=5.0,
                poll_interval=0.05,
            )

    def test_returns_case_immediately_when_present(self):
        """First poll finds an initialized case — returns it without retrying."""
        client = _LateInitializedCaseClient(delay=0)
        result = self._run(client)
        assert result.id_ == _IC_CASE_ID
        assert client.calls == 1

    def test_returns_case_when_arrives_late(self):
        """Polls until the case with participants appears."""
        client = _LateInitializedCaseClient(delay=3)
        result = self._run(client)
        assert result.id_ == _IC_CASE_ID
        assert client.calls > 3, "must have polled more than once"

    def test_skips_cases_without_participants(self):
        """A case dict present but with empty case_participants is not returned."""
        client = _LateInitializedCaseClient(delay=2, empty_before_init=True)
        result = self._run(client)
        assert result.id_ == _IC_CASE_ID
        assert (
            client.calls > 2
        ), "must have polled past the empty-participants case"

    def test_raises_on_timeout_when_no_initialized_case(self):
        """Raises AssertionError when no initialized case appears within timeout."""
        client = _LateInitializedCaseClient(delay=10**6)
        with pytest.raises(AssertionError, match="Timed out"):
            with patch(
                "vultron.demo.utils.case_actor_id_for_report",
                return_value=_IC_CASE_ACTOR_ID,
            ):
                wait_for_initialized_case(
                    client=cast(DataLayerClient, client),
                    report_id=_IC_REPORT_ID,
                    timeout_seconds=0.1,
                    poll_interval=0.5,
                )
