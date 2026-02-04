#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
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


@pytest.mark.xfail(
    reason="Demo may rely on external state not present in test environment"
)
def test_main_executes_without_raising(demo_env):
    """Tests that demo.main() can be executed without raising exceptions."""
    demo.main()
