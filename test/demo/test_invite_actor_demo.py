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
from vultron.demo.exchange import invite_actor_demo as demo
from vultron.demo.exchange import initialize_case_demo as init_demo


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
        # Patch the default base_url so DataLayerClient() (no args) in
        # runner.py picks up the TestClient URL. _assert_client_hosts_actor
        # compares client.base_url against actor.id_, so the authorities must
        # match for trigger-endpoint calls to pass. Requires model_rebuild to
        # take effect (Pydantic v2 bakes defaults into compiled validators).
        _original_base_url_default = demo.DataLayerClient.model_fields[
            "base_url"
        ].default
        demo.DataLayerClient.model_fields["base_url"].default = base
        demo.DataLayerClient.model_rebuild(force=True)
        yield
    finally:
        demo.DataLayerClient.model_fields["base_url"].default = (
            _original_base_url_default
        )
        demo.DataLayerClient.model_rebuild(force=True)
        mp.undo()
        importlib.reload(demo)
        importlib.reload(init_demo)


@pytest.mark.parametrize(
    "demo_fn",
    [demo.demo_invite_actor_accept, demo.demo_invite_actor_reject],
    ids=["invite_accept", "invite_reject"],
)
def test_demo(demo_env, demo_fn, caplog):
    """
    Tests that the invite_actor demo workflows complete successfully.

    For the accept path, verifies:
    - Case initialized with report and finder participant
    - Invite sent to coordinator inbox
    - Coordinator acceptance sent to vendor inbox
    - Coordinator appears as a case participant

    For the reject path, verifies:
    - Case initialized with report and finder participant
    - Invite sent to coordinator inbox
    - Coordinator rejection sent to vendor inbox
    - Participant list unchanged (coordinator not added)
    """
    import logging

    with caplog.at_level(logging.ERROR):
        demo.main(skip_health_check=True, demos=[demo_fn])

    assert "ERROR SUMMARY" not in caplog.text, (
        "Expected demo to succeed, but got errors:\n" + caplog.text
    )


def test_setup_initialized_case_registers_case_manager(demo_env, client):
    """setup_initialized_case registers CASE_MANAGER via trigger endpoint (CM-02-014)."""
    from vultron.adapters.driven.datalayer_sqlite import get_datalayer
    from vultron.core.participants.authority import resolve_case_manager_id
    from vultron.demo.helpers.workflow import setup_initialized_case
    from vultron.demo.utils import (
        DataLayerClient,
        discover_actors,
        seed_exchange_actors,
    )

    base = str(client.base_url).rstrip("/") + "/api/v2"
    dl_client = DataLayerClient(base_url=base, actor_id=None)
    seed_exchange_actors(dl_client)
    finder, vendor, coordinator = discover_actors(dl_client)

    case = setup_initialized_case(dl_client, finder, vendor)

    vendor_dl = get_datalayer(vendor.id_)
    stored_case = vendor_dl.read_case(case.id_)
    assert stored_case is not None, "Case should be stored in vendor DataLayer"

    manager_id = resolve_case_manager_id(stored_case, vendor_dl)
    assert (
        manager_id is not None
    ), "CASE_MANAGER must be registered at case creation (CM-02-014, CM-02-015)"
