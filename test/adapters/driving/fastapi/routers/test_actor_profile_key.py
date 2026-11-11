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
with a plain GET (SIG-02-002).
"""

from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import pytest

from test.adapters.driving.fastapi._redelivery import (
    get_from_store,
    served_store,
)
from test.support.objects import make
from test.support.signing import TEST_PROOF_CREATED, published_multikeys
from vultron.adapters.driven.actor_hosts import canonical_actor_uri
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.db_record import object_to_record
from vultron.core.models.actor import (
    CoreActor,
    VultronOrganization,
    hosted_endpoints,
)
from vultron.core.models.base.context import VULTRON_CONTEXT_URI
from vultron.core.models.multikey import Multikey
from vultron.wire.as2 import signing


def _get(store: Path, segment: str, path: str) -> dict[str, Any]:
    """What a fresh store at *store* serves at *path* for the actor at *segment*."""
    response = get_from_store(store, segment, path)
    assert response.status_code == 200, response.text
    return cast(dict[str, Any], response.json())


def _profile(store: Path, segment: str) -> dict[str, Any]:
    """The profile a fresh store at *store* serves for the actor at *segment*."""
    return _get(store, segment, f"/api/v2/actors/{segment}/profile")


@pytest.mark.spec("ENC-01-002")
@pytest.mark.spec("SIG-02-002")
def test_an_unsigned_get_returns_the_profile_with_its_key(tmp_path: Path):
    actor_id = canonical_actor_uri("profile-key-vendor")

    profile = _profile(tmp_path / "vendor.db", "profile-key-vendor")

    keys = published_multikeys(profile)
    assert len(keys) == 1, profile
    [key] = keys
    assert key.get("controller") == actor_id
    assert str(key.get("id", "")).startswith(f"{actor_id}#")
    assert str(key.get("publicKeyMultibase", "")).startswith("z")


@pytest.mark.spec("ENC-01-002")
def test_the_profile_context_defines_the_key_terms(tmp_path: Path):
    """The Multikey context follows the profile's own, which stays first.

    The Vultron context defines no ``assertionMethod``, ``Multikey``,
    ``controller`` or ``publicKeyMultibase``, so a JSON-LD-expanding verifier
    would drop the key without it.
    """
    profile = _profile(tmp_path / "context.db", "profile-key-context")

    context = profile["@context"]
    assert isinstance(context, list), context
    assert context[-1] == signing.MULTIKEY_CONTEXT
    assert context.count(signing.MULTIKEY_CONTEXT) == 1
    assert VULTRON_CONTEXT_URI in context[:-1]
    # A list context still validates as the core actor a peer stores.
    assert CoreActor.model_validate(profile).context_ == context


@pytest.mark.spec("SIG-05-001")
def test_an_actors_key_is_the_same_in_every_store(tmp_path: Path):
    first = published_multikeys(
        _profile(tmp_path / "first.db", "profile-key-finder")
    )
    again = published_multikeys(
        _profile(tmp_path / "again.db", "profile-key-finder")
    )
    other = published_multikeys(
        _profile(tmp_path / "other.db", "profile-key-coordinator")
    )

    assert first and other
    assert first == again
    assert first[0]["publicKeyMultibase"] != other[0]["publicKeyMultibase"]


@pytest.mark.spec("ENC-01-002")
def test_the_published_key_verifies_the_actors_proofs(tmp_path: Path):
    """The key a profile lists is the one the actor's proofs name and verify by."""
    actor_id = canonical_actor_uri("profile-key-signer")
    owner_key = signing.seeded_signing_key(actor_id)
    signed = signing.sign(
        {"id": f"{actor_id}/activities/1", "type": "Create"},
        owner_key,
        created=TEST_PROOF_CREATED,
    )

    [key] = published_multikeys(
        _profile(tmp_path / "signer.db", "profile-key-signer")
    )

    assert key["id"] == signing.proof_verification_method(signed)
    signing.verify(signed, key["publicKeyMultibase"])


@pytest.mark.spec("SIG-02-001")
def test_the_actor_id_dereferences_to_the_profile_with_its_key(
    tmp_path: Path,
):
    """A GET of the document a key id names finds the key there."""
    segment = "profile-key-deref"
    store = tmp_path / "deref.db"

    by_id = published_multikeys(
        _get(store, segment, f"/api/v2/actors/{segment}")
    )
    by_profile = published_multikeys(_profile(tmp_path / "again.db", segment))

    assert by_id
    assert by_id == by_profile


@pytest.mark.spec("SIG-02-001")
def test_the_actor_id_serves_the_whole_profile_with_its_endpoints(
    tmp_path: Path,
):
    """``/actors/{id}`` serves what ``/profile`` does, endpoints filled in.

    The stored record states no endpoints, so both routes publish the ones
    this node routes for the actor (ISSUE-3616).
    """
    segment = "profile-key-bare"
    actor_id = canonical_actor_uri(segment)
    dl = SqliteDataLayer(
        f"sqlite:///{tmp_path / 'bare.db'}", actor_id=actor_id
    )
    bare = make(VultronOrganization, id_=actor_id, name=segment)

    with served_store(dl, actor_id, segment, bare) as (client, _emitter):
        by_id = client.get(f"/api/v2/actors/{segment}")
        by_profile = client.get(f"/api/v2/actors/{segment}/profile")

    assert by_id.status_code == 200, by_id.text
    assert by_profile.status_code == 200, by_profile.text
    own = hosted_endpoints(actor_id)
    assert by_id.json()["inbox"] == own["inbox"]
    assert by_id.json()["outbox"] == own["outbox"]
    assert published_multikeys(by_id.json())
    assert by_id.json() == by_profile.json()


@pytest.mark.spec("ENC-01-002")
def test_the_hosted_actors_list_publishes_each_actors_key(tmp_path: Path):
    """``GET /actors/`` lists each hosted actor as the profile it publishes."""
    segment = "profile-key-listed"
    actor_id = canonical_actor_uri(segment)
    dl = SqliteDataLayer(
        f"sqlite:///{tmp_path / 'listed.db'}", actor_id=actor_id
    )

    with (
        patch(
            "vultron.adapters.driving.fastapi.routers.actors._routes"
            ".registry.actor_hosts.hosted_actor_ids",
            return_value=[actor_id],
        ),
        patch(
            "vultron.adapters.driving.fastapi.routers.actors._routes"
            ".registry.get_datalayer",
            return_value=dl,
        ),
        served_store(dl, actor_id, segment) as (client, _emitter),
    ):
        listed = client.get("/api/v2/actors/")
        profile = client.get(f"/api/v2/actors/{segment}/profile")

    assert listed.status_code == 200, listed.text
    [entry] = listed.json()
    assert published_multikeys(entry)
    assert entry == profile.json()


def test_a_stored_key_is_replaced_by_the_key_the_actor_signs_with(
    tmp_path: Path,
):
    """A hosted actor publishes the key its proofs verify by, not a stored one."""
    segment = "profile-key-stale"
    actor_id = canonical_actor_uri(segment)
    other_key = signing.seeded_signing_key(canonical_actor_uri("someone-else"))
    stored = make(
        VultronOrganization,
        id_=actor_id,
        name=segment,
        assertion_method=[
            Multikey(
                id_=f"{actor_id}#old-key",
                type_="Multikey",
                controller=actor_id,
                public_key_multibase=other_key.public_key_multibase,
            )
        ],
    )
    dl = SqliteDataLayer(
        f"sqlite:///{tmp_path / 'stale.db'}", actor_id=actor_id
    )

    with served_store(dl, actor_id, segment, stored) as (client, _emitter):
        response = client.get(f"/api/v2/actors/{segment}/profile")

    assert response.status_code == 200, response.text
    own = signing.seeded_signing_key(actor_id)
    assert [
        (key["id"], key["publicKeyMultibase"])
        for key in published_multikeys(response.json())
    ] == [(own.key_id, own.public_key_multibase)]


def test_a_held_peer_profile_keeps_its_key_through_the_store(tmp_path: Path):
    """A peer's profile copy is read back with the key it published."""
    holder_id = canonical_actor_uri("profile-key-holder")
    peer_id = "https://peer.example/actors/vendorco"
    peer_key = signing.published_multikey(
        signing.seeded_signing_key(peer_id), peer_id
    )
    dl = SqliteDataLayer(
        f"sqlite:///{tmp_path / 'holder.db'}", actor_id=holder_id
    )
    peer = make(
        VultronOrganization,
        id_=peer_id,
        name="VendorCo",
        assertion_method=[peer_key],
    )

    dl.create(object_to_record(peer))
    held = dl.read(peer_id)

    assert isinstance(held, VultronOrganization)
    assert held.assertion_method == [peer_key]
