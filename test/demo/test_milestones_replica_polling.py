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

    def __init__(self, delay: int) -> None:
        self.base_url = "http://finder:7999/api/v2"
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
