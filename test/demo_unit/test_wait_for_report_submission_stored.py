#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.

"""``wait_for_report_submission_stored`` polls the receiver's own store."""

from unittest.mock import MagicMock

import pytest

from vultron.demo.helpers.polling import wait_for_report_submission_stored

_RECEIVER = "http://vendor:7999/api/v2/actors/vendorco"
_REPORT = "urn:uuid:report"
_OFFER = "urn:uuid:offer"


def _client(present_after: dict[str, int]) -> MagicMock:
    """A client whose objects appear after N reads each."""
    reads: dict[str, int] = {}
    client = MagicMock()
    client.base_url = "http://vendor:7999/api/v2"
    client.dl_path.side_effect = lambda key="", actor_id=None: (
        f"{actor_id}|{key}"
    )

    def _get(path: str):
        _, key = path.split("|")
        reads[key] = reads.get(key, 0) + 1
        return {"id": key} if reads[key] > present_after.get(key, 0) else None

    client.get.side_effect = _get
    return client


def test_returns_once_both_are_stored_and_names_the_receiver():
    client = _client({_OFFER: 2})
    wait_for_report_submission_stored(
        client,
        _RECEIVER,
        _REPORT,
        _OFFER,
        timeout_seconds=2,
        poll_interval=0.01,
    )
    client.dl_path.assert_any_call(_OFFER, actor_id=_RECEIVER)
    client.dl_path.assert_any_call(_REPORT, actor_id=_RECEIVER)


def test_times_out_when_the_offer_never_lands():
    client = _client({_OFFER: 10**6})
    with pytest.raises(AssertionError, match="Timed out"):
        wait_for_report_submission_stored(
            client,
            _RECEIVER,
            _REPORT,
            _OFFER,
            timeout_seconds=0.1,
            poll_interval=0.02,
        )
