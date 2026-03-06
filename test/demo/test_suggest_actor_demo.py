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
import importlib

import pytest
from _pytest.monkeypatch import MonkeyPatch

from test.demo._helpers import make_testclient_call
from vultron.demo import suggest_actor_demo as demo
from vultron.demo import initialize_case_demo as init_demo


@pytest.fixture(scope="module")
def demo_env(client):
    """Sets up the demo environment, patching BASE_URL and DataLayerClient.call."""
    mp = MonkeyPatch()
    base = str(client.base_url).rstrip("/") + "/api/v2"
    try:
        mp.setattr(demo, "BASE_URL", base)
        mp.setattr(init_demo, "BASE_URL", base)
        mp.setattr(
            demo.DataLayerClient, "call", make_testclient_call(client, base)
        )
        yield
    finally:
        mp.undo()
        importlib.reload(demo)
        importlib.reload(init_demo)


@pytest.mark.parametrize(
    "demo_fn",
    [demo.demo_suggest_actor_accept, demo.demo_suggest_actor_reject],
    ids=["suggest_accept", "suggest_reject"],
)
def test_demo(demo_env, demo_fn, caplog):
    """
    Tests that the suggest_actor demo workflows complete successfully.

    For the accept path, verifies:
    - Case initialized with finder participant
    - Finder recommends coordinator to vendor
    - Vendor accepts the recommendation
    - Acceptance stored in data layer

    For the reject path, verifies:
    - Case initialized with finder participant
    - Finder recommends coordinator to vendor
    - Vendor rejects the recommendation
    - Participant list unchanged after rejection
    """
    import logging

    with caplog.at_level(logging.ERROR):
        demo.main(skip_health_check=True, demos=[demo_fn])

    assert "ERROR SUMMARY" not in caplog.text, (
        "Expected demo to succeed, but got errors:\n" + caplog.text
    )
