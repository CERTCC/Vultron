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
"""An actor profile publishes the key that verifies its proofs (ADR-0164).

Each test serves one actor's store with a real app and fetches its profile
with a plain GET.  No profile carries a key yet, so each test is a strict
``xfail`` naming the Task that turns it green (#5381).
"""

from pathlib import Path
from typing import Any, cast

import pytest

from test.adapters.driving.fastapi._redelivery import served_store
from vultron.adapters.driven.actor_hosts import canonical_actor_uri
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

_NO_KEY = "actor profiles do not publish a key yet. Tracked by #5381."


def _profile(store: Path, segment: str) -> dict[str, Any]:
    """The profile a fresh store at *store* serves for the actor at *segment*."""
    actor_id = canonical_actor_uri(segment)
    # A file per store: two in-memory stores for one actor id share their
    # rows, so the second would find the first one's actor record.
    dl = SqliteDataLayer(f"sqlite:///{store}", actor_id=actor_id)
    with served_store(dl, actor_id, segment) as (client, _emitter):
        response = client.get(f"/api/v2/actors/{segment}/profile")
    assert response.status_code == 200, response.text
    return cast(dict[str, Any], response.json())


def _multikeys(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """The ``Multikey`` entries *profile* lists under ``assertionMethod``."""
    methods = profile.get("assertionMethod") or []
    return [
        method
        for method in (methods if isinstance(methods, list) else [methods])
        if isinstance(method, dict) and method.get("type") == "Multikey"
    ]


@pytest.mark.xfail(strict=True, reason=f"ENC-01-002, SIG-02-002: {_NO_KEY}")
@pytest.mark.spec("ENC-01-002")
@pytest.mark.spec("SIG-02-002")
def test_an_unsigned_get_returns_the_profile_with_its_key(tmp_path: Path):
    actor_id = canonical_actor_uri("profile-key-vendor")

    profile = _profile(tmp_path / "vendor.db", "profile-key-vendor")

    keys = _multikeys(profile)
    assert len(keys) == 1, profile
    [key] = keys
    assert key.get("controller") == actor_id
    assert str(key.get("id", "")).startswith(f"{actor_id}#")
    assert str(key.get("publicKeyMultibase", "")).startswith("z")


@pytest.mark.xfail(
    strict=True,
    reason=f"SIG-05-001: {_NO_KEY} Seeded keys: #5380.",
)
@pytest.mark.spec("SIG-05-001")
def test_an_actors_key_is_the_same_in_every_store(tmp_path: Path):
    first = _multikeys(_profile(tmp_path / "first.db", "profile-key-finder"))
    again = _multikeys(_profile(tmp_path / "again.db", "profile-key-finder"))
    other = _multikeys(
        _profile(tmp_path / "other.db", "profile-key-coordinator")
    )

    assert first and other
    assert first == again
    assert first[0]["publicKeyMultibase"] != other[0]["publicKeyMultibase"]
