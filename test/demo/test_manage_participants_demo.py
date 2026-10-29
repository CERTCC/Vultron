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

import pytest

from test.demo._helpers import (
    expect_no_inbox_refusals,
    expect_no_sender_refusals,
    expect_trusted_introductions,
    route_exchange_demo_at_testclient,
)
from vultron.demo.exchange import (
    initialize_case_demo as init_demo,
    manage_participants_demo as demo,
)


@pytest.fixture(scope="module")
def demo_env(client):
    """Routes the demo's clients at the in-process TestClient."""
    with route_exchange_demo_at_testclient(client, demo, init_demo):
        yield


@pytest.mark.parametrize(
    "demo_fn",
    [
        demo.demo_manage_participants_accept,
        demo.demo_manage_participants_reject,
    ],
    ids=["manage_participants_accept", "manage_participants_reject"],
)
def test_demo(demo_env, demo_fn, caplog):
    """
    Tests that the manage_participants demo workflows complete successfully.

    For the accept path, verifies:
    - Case initialized with vendor as sole participant
    - Invite sent to coordinator inbox
    - Coordinator acceptance seats it through the stub Invite (no Add)
    - Coordinator participant status created and added
    - Coordinator participant removed from active participation, record kept
    - Coordinator reinstated by the Case Owner's Add(CaseParticipant)
    - No errors logged

    For the reject path, verifies:
    - Case initialized with vendor as sole participant
    - The CASE_MANAGER's stub Invite reaches the coordinator
    - The coordinator declines through its ``reject-case-invite`` trigger
    - The coordinator's inert record closes (CM-11-006, CM-11-007)
    - No errors logged
    """
    import logging

    # WARNING, not ERROR: a refused case introduction (CBT-01-011) is
    # logged at WARNING, and the run must log none (#4675).
    with (
        caplog.at_level(logging.WARNING),
        expect_trusted_introductions(caplog),
        expect_no_inbox_refusals(caplog),
        expect_no_sender_refusals(caplog),
    ):
        demo.main(skip_health_check=True, demos=[demo_fn])

    assert "ERROR SUMMARY" not in caplog.text, (
        "Expected demo to succeed, but got errors:\n" + caplog.text
    )
