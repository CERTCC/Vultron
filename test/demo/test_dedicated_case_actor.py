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

"""The demo harness drives the dedicated case-actor container (#1876).

Every actor container proposes its cases to
``http://case-actor:7999/api/v2/actors/case-actor`` (CP-08-008,
DEMOMA-06-004).  Two harness obligations follow, both tested here:

- the reset that starts every scenario wipes that identity with every other
  record, so it must be re-seeded or every ``Create(CaseProposal)`` 404s
  (:func:`~vultron.demo.helpers.seeding.reset_containers`);
- the rv demo confirms the dedicated container holds the case, with its
  CaseActor as the ``CASE_MANAGER`` participant
  (:func:`~vultron.demo.helpers.verification.verify_case_actor_holds_records`).
"""

from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import httpx2 as httpx
import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi.testclient import TestClient

from test.demo._helpers import make_client, make_testclient_call
from vultron.demo.helpers.seeding import (
    reset_containers,
    seed_case_actor_identity,
)
from vultron.demo.helpers.verification import verify_case_actor_holds_records
from vultron.demo.utils import (
    DataLayerClient,
    case_actor_id_on,
    reset_datalayer,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant

_CA_BASE = "http://case-actor:7999/api/v2"
_CA_ID = case_actor_id_on(_CA_BASE)
_CASE_ID = "http://case-actor:7999/api/v2/cases/case-1876"
_PARTICIPANT_ID = f"{_CASE_ID}/participants/case-actor"


@pytest.fixture(scope="module")
def base(client: TestClient) -> str:
    """The single TestClient node's base URL, with the /api/v2 prefix."""
    return str(client.base_url).rstrip("/") + "/api/v2"


@pytest.fixture(scope="module", autouse=True)
def patch_datalayer_call(client: TestClient, base: str):
    """Route every DataLayerClient request through the module's TestClient."""
    mp = MonkeyPatch()
    try:
        mp.setattr(DataLayerClient, "call", make_testclient_call(client, base))
        yield
    finally:
        mp.undo()


def _hosted_actor_ids(client: DataLayerClient) -> set[str]:
    return {as_Actor.model_validate(a).id_ for a in client.get("/actors/")}


class TestSeedCaseActorIdentity:
    def test_hosts_the_case_actor_and_binds_the_client(self, base: str):
        ca_client = make_client(base)

        actor = seed_case_actor_identity(ca_client)

        assert actor.id_ == case_actor_id_on(base)
        assert actor.id_ in _hosted_actor_ids(ca_client)
        # Bound, so per-actor reads address the CaseActor's store (ADR-0073).
        assert ca_client.actor_id == actor.id_

    def test_is_idempotent(self, base: str):
        ca_client = make_client(base)

        first = seed_case_actor_identity(ca_client)
        second = seed_case_actor_identity(ca_client)

        assert first.id_ == second.id_


class TestResetReseedsTheCaseActor:
    def test_identity_survives_the_reset(self, base: str):
        """Without the re-seed the reset leaves no CaseActor to propose to."""
        ca_client = make_client(base, actor_id=case_actor_id_on(base))
        seed_case_actor_identity(ca_client)

        reset_containers(
            [], reset_fn=reset_datalayer, case_actor_client=ca_client
        )

        assert case_actor_id_on(base) in _hosted_actor_ids(ca_client)

    def test_reset_alone_removes_it(self, base: str):
        """Guard the guard: the reset really does wipe the identity."""
        ca_client = make_client(base, actor_id=case_actor_id_on(base))
        seed_case_actor_identity(ca_client)

        reset_containers([("CaseActor", ca_client)], reset_fn=reset_datalayer)

        assert case_actor_id_on(base) not in _hosted_actor_ids(ca_client)


def _http_error(path: str, status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", f"{_CA_BASE}{path}")
    return httpx.HTTPStatusError(
        f"{status} for {path}",
        request=request,
        response=httpx.Response(status, request=request),
    )


def _reads(
    case: dict[str, Any] | None,
    participant: as_CaseParticipant | None,
    case_status: int = 404,
) -> Callable[..., dict]:
    """A ``DataLayerClient.get`` double serving one case and one participant."""

    def fake_get(_client: DataLayerClient, path: str, **_: Any) -> dict:
        if "participants" in path:
            if participant is None:
                raise AssertionError("404 participant not found")
            return participant.model_dump(by_alias=True, mode="json")
        if case is None:
            raise _http_error(path, case_status)
        return case

    return fake_get


def _case(with_case_actor: bool = True) -> dict[str, Any]:
    index = {_CA_ID: _PARTICIPANT_ID} if with_case_actor else {}
    return {
        "id": _CASE_ID,
        "type": "VulnerabilityCase",
        "actorParticipantIndex": index,
    }


def _participant(roles: list[CVDRole]) -> as_CaseParticipant:
    return as_CaseParticipant(
        id_=_PARTICIPANT_ID,
        attributed_to=_CA_ID,
        context=_CASE_ID,
        case_roles=roles,
    )


class TestVerifyCaseActorHoldsRecords:
    def _verify(self, case, participant, case_status=404):
        client = DataLayerClient(base_url=_CA_BASE, actor_id=_CA_ID)
        with patch.object(
            DataLayerClient,
            "get",
            autospec=True,
            side_effect=_reads(case, participant, case_status),
        ):
            return verify_case_actor_holds_records(client, _CASE_ID)

    def test_passes_when_the_case_actor_is_the_case_manager(self):
        held = self._verify(
            _case(), _participant([CVDRole.CASE_MANAGER, CVDRole.COORDINATOR])
        )
        assert held.id_ == _CASE_ID

    def test_fails_when_the_dedicated_container_lacks_the_case(self):
        """The co-located shortcut: the receiver created the case locally."""
        with pytest.raises(AssertionError, match="does not hold case"):
            self._verify(None, None)

    def test_a_server_error_is_not_reported_as_an_absent_case(self):
        """A 500 is a different fault from "the case is not there"."""
        with pytest.raises(httpx.HTTPStatusError):
            self._verify(None, None, case_status=500)

    def test_fails_when_the_case_actor_is_not_a_participant(self):
        with pytest.raises(AssertionError, match="not a participant"):
            self._verify(_case(with_case_actor=False), None)

    def test_fails_when_the_case_actor_lacks_case_manager(self):
        with pytest.raises(AssertionError, match="not CASE_MANAGER"):
            self._verify(_case(), _participant([CVDRole.COORDINATOR]))

    def test_refuses_an_unbound_client(self):
        with pytest.raises(ValueError, match="bound to the CaseActor"):
            verify_case_actor_holds_records(
                DataLayerClient(base_url=_CA_BASE), _CASE_ID
            )
