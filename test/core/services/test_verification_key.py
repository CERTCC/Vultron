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

"""The verification-key resolver reads a proof's key from its author's profile.

The held copy is read first, and a profile is fetched when the held copy
lists no key the proof names (SIG-02-001, AKM-05-012); ids are compared
normalised (OID-01-006).
"""

import ast
import asyncio
import inspect
import logging

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.actor import CoreActor, VultronOrganization
from vultron.core.models.base import CoreObject
from vultron.core.models.multikey import Multikey
from vultron.core.services import verification_key as vk
from vultron.errors import (
    VultronActorProfileFetchError,
    VultronProofVerificationError,
    VultronVerificationKeyError,
)
from vultron.wire.as2 import signing

RECEIVER = "https://receiver.example/api/v2/actors/receiver"
AUTHOR = "https://author.example/api/v2/actors/author"
METHOD = signing.key_id_for(AUTHOR)
AUTHOR_KEY = signing.published_multikey(
    signing.seeded_signing_key(AUTHOR), AUTHOR
)


class _FakeProfileFetch:
    """Answers each fetch with a fixed profile or failure, recording calls."""

    def __init__(
        self,
        profile: CoreActor | None = None,
        failure: str | None = None,
    ) -> None:
        self._profile = profile
        self._failure = failure
        self.asked: list[tuple[str, str]] = []

    async def fetch_profile(
        self, actor_id: str, requester_id: str
    ) -> CoreActor:
        self.asked.append((actor_id, requester_id))
        if self._profile is None:
            raise VultronActorProfileFetchError(self._failure or "no profile")
        return self._profile


def _store() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=RECEIVER)


def _profile(
    keys: list[Multikey] | None = None, actor_id: str = AUTHOR
) -> VultronOrganization:
    return VultronOrganization(
        id_=actor_id, name="Author", assertion_method=keys or []
    )


def _resolve(
    fetcher: _FakeProfileFetch,
    method: str = METHOD,
    author_id: str = AUTHOR,
) -> Multikey:
    return asyncio.run(
        vk.resolve_verification_key(
            method,
            author_id=author_id,
            fetcher=fetcher,
            requester_id=RECEIVER,
        )
    )


@pytest.mark.spec("SIG-02-003")
def test_only_the_fetched_key_is_returned():
    """A key in a stored copy came from somewhere other than the author.

    The resolver takes no store, so the planted key cannot reach it; the
    inbox-level test that stores one is
    ``test_signed_delivery_refusal.py::test_a_stored_peer_key_is_ignored``.
    """
    planted = Multikey(
        id_=METHOD,
        type_="Multikey",
        controller=AUTHOR,
        public_key_multibase=signing.seeded_signing_key(
            "https://forger.example/actors/forger"
        ).public_key_multibase,
    )
    fetcher = _FakeProfileFetch(_profile([AUTHOR_KEY]))

    key = _resolve(fetcher)

    assert key == AUTHOR_KEY
    assert key != planted
    assert fetcher.asked == [(AUTHOR, RECEIVER)]


@pytest.mark.spec("SIG-02-001")
def test_the_profile_is_fetched_from_the_author_and_not_stored():
    fetcher = _FakeProfileFetch(_profile([AUTHOR_KEY]))

    key = _resolve(fetcher)

    assert key == AUTHOR_KEY
    assert fetcher.asked == [(AUTHOR, RECEIVER)]


@pytest.mark.spec("SIG-02-003")
def test_the_resolver_takes_no_store():
    """No parameter could carry a stored copy to the lookup."""
    assert (
        "dl" not in inspect.signature(vk.resolve_verification_key).parameters
    )


@pytest.mark.spec("SIG-02-001")
@pytest.mark.spec("SIG-03-002")
def test_a_fetched_profile_without_the_key_refuses_the_proof():
    fetcher = _FakeProfileFetch(_profile())

    with pytest.raises(VultronVerificationKeyError) as caught:
        _resolve(fetcher)

    assert isinstance(caught.value, VultronProofVerificationError)
    assert METHOD in str(caught.value)
    assert "does not list key" in str(caught.value)


@pytest.mark.spec("SIG-03-002")
def test_a_failed_fetch_refuses_the_proof_and_logs_why(
    caplog: pytest.LogCaptureFixture,
):
    failure = "GET https://10.0.0.7:8080/profile: connection refused"
    fetcher = _FakeProfileFetch(failure=failure)

    with (
        caplog.at_level(logging.WARNING, logger=vk.__name__),
        pytest.raises(VultronVerificationKeyError) as caught,
    ):
        _resolve(fetcher)

    assert METHOD in str(caught.value)
    assert "could not be fetched" in str(caught.value)
    assert isinstance(caught.value.__cause__, VultronActorProfileFetchError)
    assert failure in caplog.text


def test_a_refusal_says_nothing_of_what_the_fetch_met():
    """The sender chose the URL, so the refusal it gets back is no probe."""
    failure = "GET https://10.0.0.7:8080/profile: connection refused"

    with pytest.raises(VultronVerificationKeyError) as caught:
        _resolve(_FakeProfileFetch(failure=failure))

    assert "10.0.0.7" not in str(caught.value)
    assert "connection refused" not in str(caught.value)


@pytest.mark.spec("OID-01-006")
def test_a_key_id_with_a_trailing_slash_fetches_the_normalised_actor():
    fetcher = _FakeProfileFetch(_profile([AUTHOR_KEY]))

    _resolve(fetcher, f"{AUTHOR}/#{signing.KEY_FRAGMENT}")

    assert fetcher.asked == [(AUTHOR, RECEIVER)]


@pytest.mark.spec("OID-01-006")
def test_an_author_spelled_with_a_trailing_slash_owns_its_key():
    fetcher = _FakeProfileFetch(_profile([AUTHOR_KEY]))

    key = _resolve(fetcher, author_id=f"{AUTHOR}/")

    assert key == AUTHOR_KEY


@pytest.mark.spec("SIG-02-001")
def test_a_key_of_another_actor_is_refused_without_a_fetch():
    """A bystander's valid key says nothing about who wrote the document."""
    bystander = "https://bystander.example/api/v2/actors/bystander"
    method = signing.key_id_for(bystander)
    bystander_key = signing.published_multikey(
        signing.seeded_signing_key(bystander), bystander
    )
    fetcher = _FakeProfileFetch(_profile([bystander_key], bystander))

    with pytest.raises(VultronVerificationKeyError) as caught:
        _resolve(fetcher, method)

    assert method in str(caught.value)
    assert AUTHOR in str(caught.value)
    assert fetcher.asked == []


@pytest.mark.spec("OID-01-006")
def test_a_controller_spelled_with_a_trailing_slash_names_the_same_actor():
    """A profile stored under ``…/author/`` lists the key ``…/author#…`` names."""
    slashed = f"{AUTHOR}/"
    key = Multikey(
        id_=f"{slashed}#{signing.KEY_FRAGMENT}",
        type_="Multikey",
        controller=slashed,
        public_key_multibase=AUTHOR_KEY.public_key_multibase,
    )

    assert vk.published_key(_profile([key], slashed), METHOD) == key


@pytest.mark.spec("SIG-02-001")
def test_a_profile_of_another_actor_lists_no_key_for_the_author():
    other_id = "https://other.example/api/v2/actors/other"
    other_key = signing.published_multikey(
        signing.seeded_signing_key(other_id), other_id
    )

    assert vk.published_key(_profile([other_key], other_id), METHOD) is None


@pytest.mark.spec("SIG-02-001")
def test_a_key_appended_past_validation_for_another_controller_is_not_used():
    """``append`` skips the profile's validators (CM-27-001)."""
    profile = _profile()
    other_id = "https://other.example/api/v2/actors/other"
    profile.assertion_method.append(
        Multikey.model_construct(
            id_=METHOD,
            type_="Multikey",
            controller=other_id,
            public_key_multibase=AUTHOR_KEY.public_key_multibase,
        )
    )

    assert vk.published_key(profile, METHOD) is None


@pytest.mark.spec("SIG-02-001")
def test_a_key_appended_past_validation_with_a_foreign_id_is_not_used():
    profile = _profile()
    profile.assertion_method.append(
        Multikey.model_construct(
            id_=f"https://other.example/x#{signing.KEY_FRAGMENT}",
            type_="Multikey",
            controller=AUTHOR,
            public_key_multibase=AUTHOR_KEY.public_key_multibase,
        )
    )

    assert vk.published_key(profile, METHOD) is None


def test_a_fault_in_the_fetcher_is_not_a_proof_refusal():
    """A fetcher bug propagates; only a failed fetch refuses the proof."""

    class _Raises(_FakeProfileFetch):
        async def fetch_profile(
            self, actor_id: str, requester_id: str
        ) -> CoreActor:
            raise RuntimeError("a bug in the fetcher")

    with pytest.raises(RuntimeError, match="a bug in the fetcher"):
        _resolve(_Raises())


def test_an_object_that_is_not_an_actor_lists_no_key():
    assert vk.published_key(None, METHOD) is None
    assert vk.published_key(CoreObject(id_=AUTHOR), METHOD) is None


@pytest.mark.spec("SIG-01-002")
@pytest.mark.parametrize(
    "method",
    [AUTHOR, f"{AUTHOR}#", "#main-key", "/#main-key"],
    ids=["no-fragment", "empty-fragment", "no-actor", "slash-only-actor"],
)
def test_a_method_naming_no_profile_key_is_refused_without_a_fetch(
    method: str,
):
    fetcher = _FakeProfileFetch(_profile([AUTHOR_KEY]))

    with pytest.raises(VultronVerificationKeyError):
        _resolve(fetcher, method)

    assert fetcher.asked == []


def test_the_key_owner_is_the_normalised_actor_id():
    assert vk.key_owner_id(f"{AUTHOR}/#main-key") == AUTHOR
    assert vk.key_owner_id(METHOD) == AUTHOR


@pytest.mark.spec("SIG-05-002")
@pytest.mark.parametrize(
    "module",
    [
        vk,
        pytest.importorskip(
            "vultron.adapters.driven.http_actor_profile_fetch"
        ),
        pytest.importorskip(
            "vultron.adapters.driving.fastapi.inbox_verification"
        ),
        pytest.importorskip("vultron.adapters.driving.fastapi.deps"),
    ],
    ids=["resolver", "fetch-adapter", "verification-stage", "fetch-wiring"],
)
def test_the_key_lookup_names_no_seed_function(module: object):
    """No seed function is named, however it might be imported or called."""
    tree = ast.parse(inspect.getsource(module))  # type: ignore[arg-type]
    names = (
        {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        | {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
        }
        | {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
    )

    assert not names & {"seeded_signing_key", "_seed_for", "SigningKey"}


@pytest.mark.spec("SIG-05-002")
def test_resolving_and_verifying_derives_no_key_from_a_seed(
    monkeypatch: pytest.MonkeyPatch,
):
    """The resolved key verifies the author's proof with no seed in sight."""
    signed = signing.sign(
        {"id": f"{AUTHOR}/activities/1", "type": "Create"},
        signing.seeded_signing_key(AUTHOR),
    )
    fetcher = _FakeProfileFetch(_profile([AUTHOR_KEY]))

    def _no_seed(actor_id: str) -> signing.SigningKey:
        raise AssertionError(f"derived {actor_id!r}'s key from its seed")

    monkeypatch.setattr(signing, "seeded_signing_key", _no_seed)
    monkeypatch.setattr(signing, "_seed_for", _no_seed)

    key = _resolve(fetcher, signing.proof_verification_method(signed))
    signing.verify(signed, key.public_key_multibase)
