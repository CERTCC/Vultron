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

"""Shared helpers for demo test fixtures."""

from typing import Any

from fastapi.testclient import TestClient


def make_testclient_call(client: TestClient, base: str):
    """Returns a DataLayerClient.call method that routes through TestClient.

    Translates full-URL paths used by demo scripts into relative paths accepted
    by the TestClient, stripping the base URL prefix and ensuring the /api/v2
    prefix is present.
    """

    def testclient_call(self, method: str, path: Any, **kwargs) -> Any:
        url = str(path)
        if url.startswith(base):
            url = url[len(base) :]
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

    return testclient_call
