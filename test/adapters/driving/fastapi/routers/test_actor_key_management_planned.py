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
"""Key management `main` does not meet yet (ENC-01-001, -004, -005, -006).

Each test is a strict ``xfail``: `main` computes an actor's key pair from a
seed tied to its actor id (``signing.seeded_signing_key``, the ADR-0164
prototype carve-out) every time it needs one, and never generates, stores or
persists a key pair. Real per-actor keys are #1184. When they land, these
tests XPASS, ``strict=True`` fails the build, and the builder drops the
``xfail`` (``notes/spec-authoring-rules.md`` § "Use a Strict ``xfail`` for
Not-Yet-Implemented Specs").

Each test reads the key an actor publishes through a real app, as a peer
would (ENC-01-002). A precondition that does not hold calls ``pytest.fail``,
which the ``raises=AssertionError`` on each ``xfail`` does not accept, so a
test fails for its stated reason or not at all.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from test.adapters.driving.fastapi._redelivery import served_store
from vultron.adapters.driven.actor_hosts import canonical_actor_uri
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.app import create_app
from vultron.adapters.driving.fastapi.deps import get_actor_dl
from vultron.wire.as2 import signing

_SEEDED = (
    "main computes each actor's key pair from a seed tied to its actor id"
    " (seeded_signing_key, ADR-0164 prototype carve-out) and never"
    " generates, stores or persists one. Tracked by #1184."
)


def _store(path: Path, actor_id: str) -> SqliteDataLayer:
    """A store file for *actor_id*; a file, so a restart can reopen it."""
    return SqliteDataLayer(f"sqlite:///{path}", actor_id=actor_id)


def _key_from(client: TestClient, segment: str) -> str:
    """The ``publicKeyMultibase`` *client* serves for the actor at *segment*."""
    response = client.get(f"/api/v2/actors/{segment}/profile")
    if response.status_code != 200:
        pytest.fail(f"the profile was not served: {response.text}")
    methods = response.json().get("assertionMethod") or []
    keys = [
        method.get("publicKeyMultibase")
        for method in (methods if isinstance(methods, list) else [methods])
        if isinstance(method, dict) and method.get("type") == "Multikey"
    ]
    if len(keys) != 1 or not keys[0]:
        pytest.fail(f"the profile does not publish one key: {keys}")
    return str(keys[0])


def _provisioned_key(path: Path, segment: str) -> str:
    """Provision the actor at *segment* in a new store at *path*; its key."""
    actor_id = canonical_actor_uri(segment)
    dl = _store(path, actor_id)
    try:
        with served_store(dl, actor_id, segment) as (client, _emitter):
            return _key_from(client, segment)
    finally:
        dl.close()


@contextmanager
def _resumed(path: Path, segment: str) -> Iterator[TestClient]:
    """A new process serving the store at *path*, which already holds the actor."""
    actor_id = canonical_actor_uri(segment)
    dl = _store(path, actor_id)
    if dl.read(actor_id) is None:
        pytest.fail("the reopened store does not hold the provisioned actor")
    app = create_app(docs_url=None, openapi_url=None)
    app.dependency_overrides[get_actor_dl] = lambda actor_id: dl
    try:
        with TestClient(app) as client:
            yield client
    finally:
        dl.close()


def _seed_derivation(actor_id: str) -> str | None:
    """The public key a seed tied to *actor_id* gives, if `main` still seeds."""
    derive = getattr(signing, "seeded_signing_key", None)
    return None if derive is None else derive(actor_id).public_key_multibase


@pytest.mark.spec("ENC-01-001")
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=f"ENC-01-001: an actor is given no key pair of its own when it is"
    f" provisioned. {_SEEDED}",
)
def test_each_provisioning_generates_a_unique_key_pair(tmp_path: Path):
    """Two independent provisionings of one actor id get distinct key pairs.

    A key computed from the actor id is the same in every deployment that
    provisions that id, so it is unique to the id, not to the provisioning.
    """
    segment = "key-unique-vendor"

    first = _provisioned_key(tmp_path / "first.db", segment)
    second = _provisioned_key(tmp_path / "second.db", segment)

    assert first != second, "both provisionings published the same key pair"


@pytest.mark.spec("ENC-01-004")
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=f"ENC-01-004: no private key is stored, securely or at all; anyone"
    f" can compute it from the actor id. {_SEEDED}",
)
def test_the_private_key_cannot_be_computed_from_the_actor_id(tmp_path: Path):
    """The key an actor signs with is a secret its store keeps, not a derivation.

    A key pair anyone can compute from public information is not stored
    securely, whatever the store does: its private half is already known.
    """
    segment = "key-secret-vendor"

    published = _provisioned_key(tmp_path / "vendor.db", segment)

    assert published != _seed_derivation(canonical_actor_uri(segment)), (
        "the published key is the one a seed tied to the actor id gives"
    )


@pytest.mark.spec("ENC-01-005")
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=f"ENC-01-005: the key pair survives a restart only because it is"
    f" computed again from the actor id, not because it was persisted."
    f" {_SEEDED}",
)
def test_the_key_pair_is_persisted_and_reused_across_a_restart(
    tmp_path: Path,
):
    """A restarted process serves the key its store persisted.

    The same key after a restart shows reuse only if it came from the store:
    a store that holds no such actor must not give the same key.
    """
    segment = "key-persisted-vendor"
    store = tmp_path / "vendor.db"
    provisioned = _provisioned_key(store, segment)

    with _resumed(store, segment) as client:
        restarted = _key_from(client, segment)
    if restarted != provisioned:
        pytest.fail("the restarted process served a different key")
    elsewhere = _provisioned_key(tmp_path / "elsewhere.db", segment)

    assert restarted != elsewhere, (
        "a store that never held the actor gives the same key, so the key"
        " was not read from the persisted one"
    )


@pytest.mark.spec("ENC-01-006")
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=f"ENC-01-006: resuming an actor computes its key pair afresh from"
    f" the actor id instead of loading the persisted one. {_SEEDED}",
)
def test_resuming_an_actor_makes_no_new_key_pair(tmp_path: Path):
    """A resumed process loads the actor's key pair; it computes none.

    The spy watches the one way `main` makes a key pair. Once real keys
    replace the seeded ones (#1184) the function is gone, nothing is
    watched, and the test passes, so the strict ``xfail`` reports it.
    """
    segment = "key-resumed-vendor"
    store = tmp_path / "vendor.db"
    provisioned = _provisioned_key(store, segment)

    derive = getattr(signing, "seeded_signing_key", None)
    with _resumed(store, segment) as client:
        if derive is None:
            resumed = _key_from(client, segment)
            computed = 0
        else:
            with patch.object(
                signing, "seeded_signing_key", wraps=derive
            ) as spy:
                resumed = _key_from(client, segment)
            computed = spy.call_count
    if resumed != provisioned:
        pytest.fail("the resumed process served a different key")

    assert computed == 0, (
        f"resuming the actor computed its key pair {computed} time(s)"
    )
