"""
Tests for GET /examples/actors/{subtype} endpoints.
"""

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

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from vultron.adapters.driving.fastapi.routers import (
    examples as examples_router,
)


@pytest.fixture
def client_examples():
    app = FastAPI()
    app.include_router(examples_router.router)
    return TestClient(app)


class TestActorSubtypeExampleEndpoints:
    """Each actor-subtype GET endpoint returns a valid, typed example actor."""

    _BASE = "https://example.org/actors"

    @pytest.mark.parametrize(
        "path, expected_type, slug",
        [
            ("/examples/actors/person", "Person", "alice"),
            ("/examples/actors/organization", "Organization", "acme-inc"),
            ("/examples/actors/service", "Service", "vultron-bot"),
            ("/examples/actors/application", "Application", "vultron-app"),
            ("/examples/actors/group", "Group", "security-team"),
        ],
    )
    def test_status_ok(self, client_examples, path, expected_type, slug):
        resp = client_examples.get(path)
        assert resp.status_code == 200

    @pytest.mark.parametrize(
        "path, expected_type, slug",
        [
            ("/examples/actors/person", "Person", "alice"),
            ("/examples/actors/organization", "Organization", "acme-inc"),
            ("/examples/actors/service", "Service", "vultron-bot"),
            ("/examples/actors/application", "Application", "vultron-app"),
            ("/examples/actors/group", "Group", "security-team"),
        ],
    )
    def test_correct_actor_type(
        self, client_examples, path, expected_type, slug
    ):
        data = client_examples.get(path).json()
        assert (
            data["type"] == expected_type
        ), f"Expected type={expected_type!r}, got {data.get('type')!r}"

    @pytest.mark.parametrize(
        "path, expected_type, slug",
        [
            ("/examples/actors/person", "Person", "alice"),
            ("/examples/actors/organization", "Organization", "acme-inc"),
            ("/examples/actors/service", "Service", "vultron-bot"),
            ("/examples/actors/application", "Application", "vultron-app"),
            ("/examples/actors/group", "Group", "security-team"),
        ],
    )
    def test_embargo_policy_present(
        self, client_examples, path, expected_type, slug
    ):
        data = client_examples.get(path).json()
        policy = data.get("embargoPolicy")
        assert policy is not None, "embargoPolicy should be present"
        assert policy["type"] == "EmbargoPolicy"

    @pytest.mark.parametrize(
        "path, expected_type, slug",
        [
            ("/examples/actors/person", "Person", "alice"),
            ("/examples/actors/organization", "Organization", "acme-inc"),
            ("/examples/actors/service", "Service", "vultron-bot"),
            ("/examples/actors/application", "Application", "vultron-app"),
            ("/examples/actors/group", "Group", "security-team"),
        ],
    )
    def test_embargo_policy_actor_id_matches(
        self, client_examples, path, expected_type, slug
    ):
        data = client_examples.get(path).json()
        actor_id = data.get("id")
        policy = data.get("embargoPolicy", {})
        assert actor_id is not None
        assert policy.get("actorId") == actor_id, (
            f"embargoPolicy.actorId {policy.get('actorId')!r} "
            f"should match actor id {actor_id!r}"
        )
        assert policy.get("inbox") == f"{actor_id}/inbox"
        assert "preferredDuration" in policy
