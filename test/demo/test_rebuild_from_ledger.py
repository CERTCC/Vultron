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

"""Every exchange demo's cases rebuild from their ledgers (#4294 AC-5).

``route_exchange_demo_at_testclient`` rebuilds every case a hosted actor
manages before each demo's teardown clears the node, and the conftest fails
the test that left a case its ledger cannot rebuild (CLP-07-013, CM-23-016).
This module shows the check runs: an embargo demo's negotiated case is
rebuilt, embargo and consent entries included.  The multi-container scenario
demos (``rcv-embargo``, ``rcvv-embargo`` and the ``fcv`` family) need Docker;
their in-process equivalents are the per-actor-store scenarios under
``test/core/use_cases/received/``, each rebuilt by that package's conftest.
"""

import pytest

import test.demo._helpers as helpers
from test.demo._helpers import route_exchange_demo_at_testclient
from vultron.demo.exchange import (
    establish_embargo_demo as demo,
    initialize_case_demo as init_demo,
)


@pytest.fixture(scope="module")
def demo_env(client):
    with route_exchange_demo_at_testclient(client, demo, init_demo):
        yield


@pytest.mark.spec("CLP-07-013")
@pytest.mark.spec("CM-23-016")
def test_an_embargo_demo_case_is_rebuilt_from_its_ledger(demo_env):
    demo.main(skip_health_check=True, demos=[demo.demo_propose_embargo_accept])

    rebuilt = dict(helpers.REBUILT_CASES)
    negotiated = [
        event_types
        for event_types in rebuilt.values()
        if "activate_embargo_on_case" in event_types
    ]
    assert negotiated, f"no negotiated case was rebuilt: {rebuilt}"
    (event_types,) = negotiated
    assert event_types[0] == "create_case"
    assert "create_embargo_consent" in event_types
    assert "update_embargo_consent" in event_types
    assert helpers.REBUILD_FAILURES == []
