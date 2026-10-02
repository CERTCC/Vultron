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

"""The report-with-embargo exchange demo: the negotiated path (EP-04-003).

Each run ends at a different settled outcome, so each is asserted on its
own rather than only on "no ERROR SUMMARY" — a demo whose checks silently
stopped running would otherwise still pass (#2241).
"""

import importlib
import logging

import pytest
from _pytest.monkeypatch import MonkeyPatch

from test.demo._helpers import make_client, make_testclient_call
from vultron.demo.exchange import report_with_embargo_demo as demo
from vultron.demo.helpers import runner


@pytest.fixture(scope="module")
def demo_env(client):
    """Route the demo's client at the in-process TestClient.

    Besides patching ``DataLayerClient.call``, the runner's client has to be
    *built* with the test server's base URL: this demo drives the Reporter
    through ``ActorSession``, which refuses a client whose base URL is not the
    authority that hosts the actor (DEMOMA-26-002), and the actors here are
    hosted under the TestClient's ``http://testserver``.
    """
    mp = MonkeyPatch()
    base = str(client.base_url).rstrip("/") + "/api/v2"
    try:
        mp.setattr(demo, "BASE_URL", base)
        mp.setattr(
            demo.DataLayerClient, "call", make_testclient_call(client, base)
        )
        mp.setattr(runner, "DataLayerClient", lambda: make_client(base))
        yield
    finally:
        mp.undo()
        importlib.reload(demo)


@pytest.mark.spec("EP-04-003")
@pytest.mark.spec("EP-04-004")
@pytest.mark.spec("EP-04-006")
@pytest.mark.spec("EP-04-007")
@pytest.mark.spec("EP-04-009")
@pytest.mark.spec("EP-04-011")
@pytest.mark.parametrize(
    "demo_fn, verified",
    [
        (
            demo.demo_reporter_proposes_shorter,
            [
                "Reporter's terms are the active embargo",
                "Shortest-wins: active",
            ],
        ),
        (
            demo.demo_reporter_proposes_longer,
            [
                "Reporter's terms are the active embargo",
                "Accepted revision settled the case",
            ],
        ),
        (
            demo.demo_receiver_has_no_default,
            [
                "Reporter's terms are the active embargo",
                "No actor default competed",
            ],
        ),
    ],
    ids=["reporter-shorter", "reporter-longer", "no-actor-default"],
)
def test_demo(demo_env, demo_fn, verified, caplog):
    """Each run completes with no accumulated failure and reaches its outcome.

    The demo's own ``demo_check`` blocks assert the EM state, which event is
    active, which is pending, and that the pending one is about the case; a
    failed check surfaces here as an ``ERROR SUMMARY``.  The *verified* lines
    are logged only by the verification that ran to its end, so a run whose
    ``demo_gate`` never opened cannot pass by silence (#2241).
    """
    with caplog.at_level(logging.INFO):
        demo.main(skip_health_check=True, demos=[demo_fn])

    assert "ERROR SUMMARY" not in caplog.text, (
        "Expected demo to succeed, but got errors:\n" + caplog.text
    )
    for line in verified:
        assert line in caplog.text, f"verification never logged {line!r}"


def test_every_run_is_registered():
    """All three outcomes run under ``vultron-demo report-with-embargo``."""
    registered = [fn for _, fn in demo._ALL_DEMOS]
    assert registered == [
        demo.demo_reporter_proposes_shorter,
        demo.demo_reporter_proposes_longer,
        demo.demo_receiver_has_no_default,
    ]
