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

import test.demo._helpers as helpers
from test.demo._helpers import (
    expect_trusted_introductions,
    route_exchange_demo_at_testclient,
)
from vultron.demo.exchange import (
    establish_embargo_demo as demo,
    initialize_case_demo as init_demo,
)


@pytest.fixture(scope="module")
def demo_env(client):
    """Routes the demo's clients at the in-process TestClient."""
    with route_exchange_demo_at_testclient(client, demo, init_demo):
        yield


def _negotiated_cases_rebuilt() -> list[list[str]]:
    """The ledger semantic types of each rebuilt case that activated an
    embargo.

    ``route_exchange_demo_at_testclient`` rebuilds every case a hosted actor
    manages from its ledger as the demo clears the node (#4294 AC-5), and the
    ``conftest`` fails the test on any rebuild failure.  This shows the check
    covered the negotiated case, embargo and consent entries included
    (CLP-07-013, CM-23-016).  Asserted on the demo run this module already
    makes rather than on a second run of the same demo (#5227).
    """
    assert helpers.REBUILD_FAILURES == []
    rebuilt = dict(helpers.REBUILT_CASES)
    assert rebuilt, "no case was rebuilt from its ledger"
    # The label check read every entry the rebuilt cases hold, and more
    # (#4724 AC-3): it reads every hosted store, replicas included.
    assert sum(helpers.LABELLED_ENTRIES) >= max(map(len, rebuilt.values()))
    return [
        semantic_types
        for semantic_types in rebuilt.values()
        if "activate_embargo_on_case" in semantic_types
    ]


@pytest.mark.spec("CLP-07-013")
@pytest.mark.spec("CM-23-016")
@pytest.mark.parametrize(
    ("demo_fn", "activates"),
    [
        (demo.demo_propose_embargo_accept, True),
        (demo.demo_propose_embargo_reject, False),
    ],
    ids=["embargo_accept", "embargo_reject"],
)
def test_demo(demo_env, demo_fn, activates, caplog):
    """
    Tests that the establish_embargo demo workflows complete successfully.

    For the accept path, verifies:
    - Case initialized with vendor and coordinator participants
    - Coordinator proposes embargo → vendor inbox
    - Vendor accepts and activates embargo
    - Vendor announces embargo
    - Case has ACTIVE embargo
    - The negotiated case rebuilds from its ledger, embargo and consent
      entries included

    For the reject path, verifies:
    - Case initialized with vendor and coordinator participants
    - Coordinator proposes embargo → vendor inbox
    - Vendor rejects embargo → coordinator inbox
    - Case has no active embargo
    """
    import logging

    # WARNING, not ERROR: a refused case introduction (CBT-01-011) is
    # logged at WARNING, and the run must log none (#4675).
    with (
        caplog.at_level(logging.WARNING),
        expect_trusted_introductions(caplog),
    ):
        demo.main(skip_health_check=True, demos=[demo_fn])

    assert "ERROR SUMMARY" not in caplog.text, (
        "Expected demo to succeed, but got errors:\n" + caplog.text
    )

    negotiated = _negotiated_cases_rebuilt()
    assert len(negotiated) == (1 if activates else 0), negotiated
    for semantic_types in negotiated:
        assert semantic_types[0] == "create_case"
        assert "create_embargo_consent" in semantic_types
        assert "update_embargo_consent" in semantic_types
