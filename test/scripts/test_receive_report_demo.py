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
#  Carnegie Mellon\u00ae, CERT\u00ae and CERT Coordination Center\u00ae are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
import importlib

import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi.testclient import TestClient

from vultron.api.main import app as api_app
from vultron.scripts import receive_report_demo as demo


@pytest.fixture(scope="module")
def client():
    """Provides a TestClient instance for testing."""
    return TestClient(api_app)


@pytest.fixture(scope="module")
def demo_env(client):
    """Sets up the demo environment for testing, including BASE_URL and the testclient_call function."""
    mp = MonkeyPatch()
    try:
        # Keep the same /api/v2 prefix the module expects
        base = str(client.base_url).rstrip("/") + "/api/v2"
        mp.setattr(demo, "BASE_URL", base)

        def testclient_call(self, method, path, **kwargs):
            # Accept either a path ("/...") or a full URL starting with demo.BASE_URL
            url = str(path)
            if url.startswith(demo.BASE_URL):
                url = url[len(demo.BASE_URL) :]
            if not url.startswith("/"):
                url = "/" + url
            if not url.startswith("/api/v2"):
                url = "/api/v2" + url

            resp = client.request(method.upper(), url, **kwargs)
            if resp.status_code >= 400:
                raise AssertionError(
                    f"API call failed: {method.upper()} {url} --> {resp.status_code} {resp.text}"
                )
            # return parsed JSON (or raw text if not JSON)
            try:
                return resp.json()
            except Exception:
                return resp.text

        # Patch the instance method on the DataLayerClient class
        mp.setattr(demo.DataLayerClient, "call", testclient_call)

        yield

    finally:
        mp.undo()
        importlib.reload(demo)


@pytest.mark.parametrize(
    "demo_fn",
    [
        demo.demo_validate_report,
        demo.demo_invalidate_report,
        demo.demo_invalidate_and_close_report,
    ],
    ids=[
        "validate_report",
        "invalidate_report",
        "invalidate_and_close_report",
    ],
)
def test_demo(demo_env, demo_fn, caplog):
    """
    Tests that each demo workflow completes successfully with no errors.

    Covers the complete inbox-to-inbox communication flow and indirectly
    verifies helper functions: get_offer_from_datalayer, post_to_inbox_and_wait,
    get_actor_by_id, verify_activity_in_inbox, find_case_by_report.

    Regression test for bug: setup_clean_environment does not clear ACTOR_IO_STORE,
    causing demos 2 and 3 to fail with KeyError when re-initializing actor IOs.
    """
    import logging

    with caplog.at_level(logging.ERROR):
        demo.main(skip_health_check=True, demos=[demo_fn])

    assert "ERROR SUMMARY" not in caplog.text, (
        "Expected demo to succeed, but got errors:\n" + caplog.text
    )
