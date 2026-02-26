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
from fastapi.testclient import TestClient

from vultron.api.main import app as api_app
from vultron.demo import manage_case_demo as demo


@pytest.fixture(scope="module")
def client():
    """Provides a TestClient instance for testing."""
    return TestClient(api_app)


@pytest.fixture(scope="module")
def demo_env(client):
    """Sets up the demo environment, patching BASE_URL and DataLayerClient.call."""
    mp = MonkeyPatch()
    try:
        base = str(client.base_url).rstrip("/") + "/api/v2"
        mp.setattr(demo, "BASE_URL", base)

        def testclient_call(self, method, path, **kwargs):
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
                    f"API call failed: {method.upper()} {url} --> "
                    f"{resp.status_code} {resp.text}"
                )
            try:
                return resp.json()
            except Exception:
                return resp.text

        mp.setattr(demo.DataLayerClient, "call", testclient_call)

        yield

    finally:
        mp.undo()
        importlib.reload(demo)


@pytest.mark.parametrize(
    "demo_fn",
    [
        demo.demo_engage_path,
        demo.demo_defer_reengage_path,
        demo.demo_invalidate_path,
    ],
    ids=[
        "engage_path",
        "defer_reengage_path",
        "invalidate_path",
    ],
)
def test_demo(demo_env, demo_fn, caplog):
    """
    Tests that each manage_case demo workflow completes successfully with no
    errors.

    Covers:
    - demo_engage_path: submit → validate → create_case → engage → close
    - demo_defer_reengage_path: submit → validate → create_case →
      defer → re-engage → close
    - demo_invalidate_path: submit → invalidate → close_report
    """
    import logging

    with caplog.at_level(logging.ERROR):
        demo.main(skip_health_check=True, demos=[demo_fn])

    assert "ERROR SUMMARY" not in caplog.text, (
        "Expected demo to succeed, but got errors:\n" + caplog.text
    )
