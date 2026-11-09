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
persists a key pair. Real per-actor keys are #1184. When they land, the
build goes red either way: a test XPASSes and ``strict=True`` fails it, or a
test that probes the seeded key function finds it gone and fails as a setup
error. The builder then drops the ``xfail`` or rewrites the probe
(``notes/spec-authoring-rules.md`` § "Use a Strict ``xfail`` for
Not-Yet-Implemented Specs").

Each test reads the key an actor publishes through a real app, as a peer
would (ENC-01-002). A precondition that does not hold calls ``pytest.fail``,
which the ``raises=AssertionError`` on each ``xfail`` does not accept, so a
test fails for its stated reason or not at all.
"""

from collections.abc import Callable
from pathlib import Path
from typing import cast
from unittest.mock import patch

import httpx2 as httpx
import pytest

from test.adapters.driving.fastapi._redelivery import get_from_store
from test.support.signing import published_multikeys
from vultron.adapters.driven.actor_hosts import canonical_actor_uri
from vultron.wire.as2 import signing

_SEEDED = (
    "main computes each actor's key pair from a seed tied to its actor id"
    " (seeded_signing_key, ADR-0164 prototype carve-out) and never"
    " generates, stores or persists one. Tracked by #1184."
)


def _key_from(response: httpx.Response) -> str:
    """The one ``publicKeyMultibase`` the profile in *response* publishes."""
    if response.status_code != 200:
        pytest.fail(f"the profile was not served: {response.text}")
    keys = [
        key.get("publicKeyMultibase")
        for key in published_multikeys(response.json())
    ]
    if len(keys) != 1 or not keys[0]:
        pytest.fail(f"the profile does not publish one key: {keys}")
    return str(keys[0])


def _provisioned_key(path: Path, segment: str) -> str:
    """Provision the actor at *segment* in a new store at *path*; its key."""
    return _key_from(
        get_from_store(path, segment, f"/api/v2/actors/{segment}/profile")
    )


def _seeded_signing_key() -> Callable[[str], signing.SigningKey]:
    """`main`'s seeded key function; its absence is a probe to replace.

    Once #1184 removes or renames it, this fails the test as a setup
    error, which the ``raises=AssertionError`` on the ``xfail`` reports
    rather than counting as the expected failure, so the builder rewrites
    the probe against the real key store instead of it passing silently.
    """
    derive = getattr(signing, "seeded_signing_key", None)
    if derive is None:
        pytest.fail(
            "signing.seeded_signing_key is gone: rewrite this probe against"
            " the stored key (#1184)"
        )
    return cast(Callable[[str], signing.SigningKey], derive)


def _resumed_key(path: Path, segment: str) -> str:
    """The key a new process serving the store at *path* publishes.

    The store already holds the actor, as it does when its process restarts;
    a store that does not hold it serves no profile, which fails the test.
    """
    return _key_from(
        get_from_store(
            path, segment, f"/api/v2/actors/{segment}/profile", existing=True
        )
    )


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

    derived = _seeded_signing_key()(canonical_actor_uri(segment))

    assert published != derived.public_key_multibase, (
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

    restarted = _resumed_key(store, segment)
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
    """A resumed process loads the actor's key pair; it makes none.

    Two spies watch the ways a key pair is made: generating a fresh one,
    and `main`'s computing one from the actor id.
    """
    segment = "key-resumed-vendor"
    store = tmp_path / "vendor.db"
    provisioned = _provisioned_key(store, segment)
    derive = _seeded_signing_key()

    with (
        # Reached through the signing module, the one module that imports
        # the primitives (SIG-05-003).
        patch.object(
            signing.Ed25519PrivateKey,
            "generate",
            wraps=signing.Ed25519PrivateKey.generate,
        ) as generated,
        patch.object(signing, "seeded_signing_key", wraps=derive) as computed,
    ):
        resumed = _resumed_key(store, segment)
    if resumed != provisioned:
        pytest.fail("the resumed process served a different key")

    assert generated.call_count == 0, "resuming the actor generated a key pair"
    assert computed.call_count == 0, (
        f"resuming the actor computed its key pair {computed.call_count}"
        " time(s) from its actor id"
    )
