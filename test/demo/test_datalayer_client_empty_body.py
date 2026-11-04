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

"""``DataLayerClient.call`` reads an empty answer as no data, not an error.

The inbox answers an accepted delivery with a 202 that carries no body
(IE-08-001), so the demo client meets an empty body on every inbox post.
"""

import logging

import httpx2 as httpx
import pytest

from vultron.demo.utils import DataLayerClient, client as utils


def _answer(status_code: int, content: bytes):
    def _request(method, url, **_kwargs):
        return httpx.Response(
            status_code, content=content, request=httpx.Request(method, url)
        )

    return _request


@pytest.mark.spec("IE-08-001")
def test_an_empty_202_returns_no_data_and_logs_no_error(monkeypatch, caplog):
    monkeypatch.setattr(utils.httpx, "request", _answer(202, b""))
    client = DataLayerClient(base_url="http://node.example")
    with caplog.at_level(logging.DEBUG, logger=utils.logger.name):
        data = client.post("/actors/vendor/inbox/", json={})
    assert data == {}
    assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []


def test_a_body_that_is_not_json_is_still_reported(monkeypatch, caplog):
    monkeypatch.setattr(utils.httpx, "request", _answer(200, b"<html>"))
    client = DataLayerClient(base_url="http://node.example")
    with caplog.at_level(logging.ERROR, logger=utils.logger.name):
        data = client.get("/health")
    assert data == {}
    assert any("Response text" in r.getMessage() for r in caplog.records)
