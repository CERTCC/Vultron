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
"""An exchange demo's injected activity states a ledger position (SYNC-18-001).

The exchange demos post an activity straight to an actor's inbox in place of
a peer, so the post helper stamps the position of the receiver's own copy of
the case, as a peer in step with it would.
"""

from typing import Any
from unittest.mock import MagicMock

import httpx2 as httpx
import pytest

from vultron.core.models.ledger_position import LedgerPosition
from vultron.demo.utils import DataLayerClient, _stamped_as_in_step
from vultron.wire.as2.factories import add_note_to_case_activity
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

_CASE = "https://example.org/cases/demo-stamp"
_RECEIVER = "https://example.org/users/vendor"
_POSITION = {"logIndex": 2, "entryHash": "ab" * 32}


def _http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "http://testserver/api/v2/x")
    return httpx.HTTPStatusError(
        f"{status}",
        request=request,
        response=httpx.Response(status, request=request),
    )


def _client(stored: dict[str, Any]) -> MagicMock:
    """A client whose store holds *stored* (id -> record, or an error)."""
    client = MagicMock(spec=DataLayerClient)
    client.dl_path.side_effect = lambda key, actor_id=None: key

    def _get(path: str) -> Any:
        found = stored.get(path, _http_error(404))
        if isinstance(found, Exception):
            raise found
        return found

    client.get.side_effect = _get
    return client


def _note():
    return add_note_to_case_activity(
        as_Note(id_=f"{_CASE}/notes/1", content="n", context=_CASE),
        target=_CASE,
        actor="https://example.org/users/finder",
    )


@pytest.mark.spec("SYNC-18-001")
def test_the_receivers_case_position_is_stamped() -> None:
    client = _client(
        {_CASE: {"type": "VulnerabilityCase", "ledgerPosition": _POSITION}}
    )

    stamped = _stamped_as_in_step(client, _RECEIVER, _note())

    assert stamped.ledger_position == LedgerPosition.model_validate(_POSITION)


@pytest.mark.spec("SYNC-18-001")
def test_a_case_the_receiver_does_not_hold_stamps_nothing() -> None:
    note = _note()

    assert _stamped_as_in_step(_client({}), _RECEIVER, note) is note


@pytest.mark.spec("SYNC-18-001")
def test_a_stored_object_that_is_not_a_case_stamps_nothing() -> None:
    note = _note()
    client = _client({_CASE: {"type": "Note"}})

    assert _stamped_as_in_step(client, _RECEIVER, note) is note


@pytest.mark.spec("SYNC-18-001")
def test_a_case_with_no_position_stamps_nothing() -> None:
    note = _note()
    client = _client({_CASE: {"type": "VulnerabilityCase"}})

    assert _stamped_as_in_step(client, _RECEIVER, note) is note


@pytest.mark.spec("SYNC-18-001")
def test_a_read_failure_other_than_not_found_is_raised() -> None:
    client = _client({_CASE: _http_error(500)})

    with pytest.raises(httpx.HTTPStatusError):
        _stamped_as_in_step(client, _RECEIVER, _note())
