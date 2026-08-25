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

"""Participant reads about a case must address the CaseActor's own store.

A self-hosted CaseActor shares its owner's *container* but not its *store*
(ADR-0072 decision 5, CP-08-003).  It is the CaseActor that applies a
participant's RM transition, and it emits no
``add_participant_status_to_participant`` ledger entry when it does — so the
host actor's replica of that participant never advances past the state it was
created in.  A check that reads the host's replica and calls the result "what
the CaseActor sees" therefore reports ``RM.START`` forever, which is how fcvcv
failed both its "CaseActor reflects … at RM.VALID" and "… at RM.ACCEPTED"
checks on a run whose invited vendor had in fact committed RM.VALID locally
within milliseconds.

Covers :func:`resolve_case_actor_store_id` and the ``dl_actor_id`` scope it
feeds through :func:`_fetch_participant` and the participant-status pollers.
"""

from typing import cast
from unittest.mock import MagicMock

import pytest

from vultron.core.states.rm import RM
from vultron.demo.helpers.polling import (
    resolve_case_actor_store_id,
    wait_for_participant_rm_state,
)
from vultron.demo.helpers.verification import _fetch_participant
from vultron.demo.utils import DataLayerClient

_CASE_ID = "urn:uuid:case-actor-scope-0001"
_HOST_ID = "http://coordinator:7999/api/v2/actors/coordinator"
_CASE_ACTOR_ID = "http://coordinator:7999/api/v2/actors/case-actor-scope"
_REMOTE_CASE_ACTOR_ID = "http://case-actor:7999/api/v2/actors/case-actor-scope"
_PEER_ID = "http://vendor:7999/api/v2/actors/vendor"

_PEER_PARTICIPANT_ID = "urn:uuid:p-vendor-scope"


def _case_payload(case_actor_id: str | None = _CASE_ACTOR_ID) -> dict:
    """A case whose participant index names the host, a peer, and a CaseActor."""
    index = {
        _HOST_ID: "urn:uuid:p-host-scope",
        _PEER_ID: _PEER_PARTICIPANT_ID,
    }
    if case_actor_id is not None:
        index[case_actor_id] = "urn:uuid:p-case-actor-scope"
    return {
        "id": _CASE_ID,
        "type": "VulnerabilityCase",
        "actorParticipantIndex": index,
    }


def _participant_payload(rm_state: RM) -> dict:
    return {
        "id": _PEER_PARTICIPANT_ID,
        "type": "CaseParticipant",
        "actor": _PEER_ID,
        "context": _CASE_ID,
        "participantStatuses": [
            {
                "id": "urn:uuid:ps-vendor-scope",
                "type": "ParticipantStatus",
                "context": _CASE_ID,
                "rm": {"state": rm_state.value},
            }
        ],
    }


class _StoreScopedClient:
    """Container client whose GETs answer per-actor, keyed by path segment.

    ``base_url``/``actor_id`` mirror the host actor; the CaseActor's store is a
    separate mapping, so a read that forgets to scope itself reads the host's
    stale copy exactly as it does against a live container.
    """

    def __init__(
        self,
        host_rm: RM = RM.START,
        case_actor_rm: RM = RM.VALID,
        case_actor_id: str | None = _CASE_ACTOR_ID,
        actor_id: str | None = _HOST_ID,
    ) -> None:
        self.base_url = "http://coordinator:7999/api/v2"
        self.actor_id = actor_id
        self.paths: list[str] = []
        self._case_actor_id = case_actor_id
        self._rm_by_segment = {
            "coordinator": host_rm,
            "case-actor-scope": case_actor_rm,
        }

    def dl_path(self, key: str = "", actor_id: str | None = None) -> str:
        """Delegate to the real client so the path shape cannot drift."""
        return DataLayerClient(
            base_url=self.base_url, actor_id=self.actor_id
        ).dl_path(key, actor_id=actor_id)

    def get(self, path: str) -> dict:
        self.paths.append(path)
        segment = path.split("/actors/", 1)[1].split("/", 1)[0]
        if path.endswith(f"/datalayer/{_CASE_ID}"):
            return _case_payload(self._case_actor_id)
        return _participant_payload(self._rm_by_segment[segment])


def _as_client(stub: object) -> DataLayerClient:
    """Cast a duck-typed stub to ``DataLayerClient`` (it is not a Protocol)."""
    return cast(DataLayerClient, stub)


class TestResolveCaseActorStoreId:
    def test_returns_the_case_actor_when_co_hosted(self):
        """The co-hosted CaseActor is addressable, so scope reads to it."""
        client = _StoreScopedClient()

        assert (
            resolve_case_actor_store_id(_as_client(client), _CASE_ID)
            == _CASE_ACTOR_ID
        )

    def test_returns_none_when_the_case_has_no_case_actor(self):
        """No CaseActor participant: the host actor *is* the authority."""
        client = _StoreScopedClient(case_actor_id=None)

        assert (
            resolve_case_actor_store_id(_as_client(client), _CASE_ID) is None
        )

    def test_returns_none_when_the_case_actor_is_another_container(self):
        """A CaseActor elsewhere is unreachable through this client.

        Scoping to it would 404 on every poll — strictly worse than reading the
        host's replica, which at least answers.
        """
        client = _StoreScopedClient(case_actor_id=_REMOTE_CASE_ACTOR_ID)

        assert (
            resolve_case_actor_store_id(_as_client(client), _CASE_ID) is None
        )

    def test_returns_none_when_the_client_names_no_actor(self):
        """Without a bound actor there is nothing to compare containers against."""
        client = _StoreScopedClient(actor_id=None)

        assert (
            resolve_case_actor_store_id(_as_client(client), _CASE_ID) is None
        )

    def test_returns_none_when_the_case_is_unreadable(self):
        """A failed case read must not raise out of a resolver used in a gate."""
        client = MagicMock()
        client.get.side_effect = RuntimeError("boom")

        assert resolve_case_actor_store_id(client, _CASE_ID) is None


class TestFetchParticipantHonoursTheStoreScope:
    def test_unscoped_read_returns_the_hosts_stale_copy(self):
        """The defect, pinned: no scope means the host's replica, not the truth."""
        client = _StoreScopedClient(host_rm=RM.START, case_actor_rm=RM.VALID)

        participant = _fetch_participant(
            _as_client(client), _CASE_ID, _PEER_ID
        )

        assert participant is not None
        assert participant.participant_status is not None
        assert participant.participant_status.rm_state == RM.START
        assert all("/actors/coordinator/" in p for p in client.paths)

    def test_scoped_read_returns_the_case_actors_view(self):
        """With the scope applied, every GET addresses the CaseActor's store."""
        client = _StoreScopedClient(host_rm=RM.START, case_actor_rm=RM.VALID)

        participant = _fetch_participant(
            _as_client(client),
            _CASE_ID,
            _PEER_ID,
            dl_actor_id=_CASE_ACTOR_ID,
        )

        assert participant is not None
        assert participant.participant_status is not None
        assert participant.participant_status.rm_state == RM.VALID
        assert all("/actors/case-actor-scope/" in p for p in client.paths)
        assert len(client.paths) == 2, "case read and participant read"


class TestWaitForParticipantRmStatePassesTheScopeThrough:
    def test_scoped_wait_sees_the_case_actors_state(self):
        client = _StoreScopedClient(host_rm=RM.START, case_actor_rm=RM.VALID)

        wait_for_participant_rm_state(
            client=_as_client(client),
            case_id=_CASE_ID,
            actor_id=_PEER_ID,
            expected_states={RM.VALID, RM.ACCEPTED},
            timeout_seconds=1.0,
            dl_actor_id=_CASE_ACTOR_ID,
        )

    def test_unscoped_wait_times_out_and_names_the_store_it_read(self):
        """The timeout must say whose store it polled, not just which container.

        Both stores live behind one ``base_url``, so the old message —
        ``(polled http://coordinator:7999/api/v2)`` — could not distinguish a
        genuinely stalled CaseActor from a read of the wrong replica.
        """
        client = _StoreScopedClient(host_rm=RM.START, case_actor_rm=RM.VALID)

        with pytest.raises(AssertionError, match=r"store of .*coordinator"):
            wait_for_participant_rm_state(
                client=_as_client(client),
                case_id=_CASE_ID,
                actor_id=_PEER_ID,
                expected_states={RM.VALID, RM.ACCEPTED},
                timeout_seconds=0.5,
                poll_interval=0.05,
            )
