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
from vultron.demo import initialize_case_demo as demo


@pytest.fixture(scope="module")
def demo_env(client):
    """Sets up the demo environment, patching BASE_URL and DataLayerClient.call."""
    mp = MonkeyPatch()
    base = str(client.base_url).rstrip("/") + "/api/v2"
    try:
        mp.setattr(demo, "BASE_URL", base)
        mp.setattr(
            demo.DataLayerClient, "call", make_testclient_call(client, base)
        )
        yield
    finally:
        mp.undo()
        importlib.reload(demo)


def test_demo(demo_env, caplog):
    """
    Tests that the initialize_case demo workflow completes successfully.

    Verifies the full case initialization sequence:
    - Report submitted and validated
    - Case created with CreateCase
    - Vendor (case creator) added as VendorParticipant before finder
    - Report linked via AddReportToCase
    - Finder participant created via CreateParticipant
    - Finder participant added via AddParticipantToCase
    - No errors logged during execution
    """
    import logging

    with caplog.at_level(logging.INFO):
        demo.main(skip_health_check=True)

    assert "ERROR SUMMARY" not in caplog.text, (
        "Expected demo to succeed, but got errors:\n" + caplog.text
    )
    assert (
        "Vendor added as participant to case" in caplog.text
    ), "Expected vendor (case creator) to be added as a case participant"
