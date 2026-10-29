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

import contextlib
import logging

import pytest

from test.demo._helpers import (
    expect_no_inbox_refusals,
    expect_no_sender_refusals,
    expect_trusted_introductions,
    route_exchange_demo_at_testclient,
    run_real_full_case_reply,  # noqa: F401 (fixture override)
)
from vultron.demo.exchange import (
    initialize_case_demo as init_demo,
    suggest_actor_demo as demo,
)


@pytest.fixture(scope="module")
def demo_env(client):
    """Routes the demo's clients at the in-process TestClient."""
    with route_exchange_demo_at_testclient(client, demo, init_demo):
        yield


@pytest.mark.parametrize(
    ("demo_fn", "inbox_refusal_free"),
    [
        (demo.demo_suggest_actor_accept, True),
        # The reject path still posts the Case Owner's Reject into its own
        # inbox, which refuses it: no trigger sends it yet (#5459).
        (demo.demo_suggest_actor_reject, False),
    ],
    ids=["suggest_accept", "suggest_reject"],
)
def test_demo(demo_env, demo_fn, inbox_refusal_free, caplog):
    """
    Tests that the suggest_actor demo workflows complete successfully.

    For the accept path, verifies, every act through its actor's trigger:
    - Case initialized with reporter participant
    - Reporter recommends coordinator to the CASE_MANAGER
    - Case Owner accepts the forwarded recommendation
    - The CASE_MANAGER invites the coordinator
    - No inbox refuses an activity (#5438)

    For the reject path, verifies:
    - Case initialized with reporter participant
    - Reporter recommends coordinator to vendor
    - Vendor rejects the recommendation
    - Participant list unchanged after rejection
    """
    # WARNING, not ERROR: a refused case introduction (CBT-01-011) is
    # logged at WARNING, and the run must log none (#4675).
    with (
        caplog.at_level(logging.WARNING),
        expect_trusted_introductions(caplog),
        expect_no_sender_refusals(caplog),
        (
            expect_no_inbox_refusals(caplog)
            if inbox_refusal_free
            else contextlib.nullcontext()
        ),
    ):
        demo.main(skip_health_check=True, demos=[demo_fn])

    assert "ERROR SUMMARY" not in caplog.text, (
        "Expected demo to succeed, but got errors:\n" + caplog.text
    )
