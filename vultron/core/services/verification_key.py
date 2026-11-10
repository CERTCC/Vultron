#!/usr/bin/env python

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

"""Find the public key a proof names, in its author's actor profile.

A proof's ``verificationMethod`` is a key id, ``<actor id>#<fragment>``.  The
key that verifies the proof is read only from that actor's profile, fetched
from the actor's own URL with a plain ``GET`` (SIG-02-001, SIG-02-002), through
:class:`ActorProfileFetchPort`.  It is never derived from a seed (SIG-05-002)
and never read from a copy the receiver stores (SIG-02-003): a stored copy of a
peer's profile came from somewhere other than that peer, such as an activity
that embedded it, so a key in it proves nothing about the peer.  The fetched
profile is used for this lookup and not stored.

Actor ids are compared normalised, without a trailing slash (OID-01-006):
the key's actor, the profile's id and the key's ``controller`` all name the
actor however a sender spelled it.  The result is a core
:class:`~vultron.core.models.multikey.Multikey`; a verifier passes its
``publicKeyMultibase`` to ``vultron.wire.as2.signing.verify``.

Whether to pin the first key fetched (trust on first use), how a fetched key
is cached, and how a rotated key is found are #1184.
"""

from __future__ import annotations

import logging

from vultron.core.models.actor import CoreActor
from vultron.core.models.multikey import Multikey
from vultron.core.models.protocols import PersistableModel
from vultron.core.ports.actor_profile_fetch import ActorProfileFetchPort
from vultron.errors import (
    VultronActorProfileFetchError,
    VultronVerificationKeyError,
)
from vultron.primitives import normalise_actor_id

logger = logging.getLogger(__name__)


def _key_id_parts(key_id: str) -> tuple[str, str] | None:
    """*key_id* as its normalised actor id and fragment, or ``None``."""
    actor_id, hash_sign, fragment = key_id.partition("#")
    owner = normalise_actor_id(actor_id)
    if not hash_sign or not owner or not fragment:
        return None
    return owner, fragment


def _split_key_id(key_id: str) -> tuple[str, str]:
    """*key_id* as its normalised actor id and its fragment.

    Raises:
        VultronVerificationKeyError: *key_id* is not ``<actor id>#<fragment>``.
    """
    parts = _key_id_parts(key_id)
    if parts is None:
        raise VultronVerificationKeyError(
            f"verificationMethod {key_id!r} does not name a key in an actor"
            " profile, <actor id>#<fragment> (SIG-01-002)"
        )
    return parts


def key_owner_id(verification_method: str) -> str:
    """The actor whose profile lists the key *verification_method* names.

    The id is normalised (OID-01-006), so ``…/vendor/#main-key`` and
    ``…/vendor#main-key`` both name ``…/vendor``.

    Raises:
        VultronVerificationKeyError: *verification_method* is not
            ``<actor id>#<fragment>``.
    """
    return _split_key_id(verification_method)[0]


def published_key(
    profile: PersistableModel | None, verification_method: str
) -> Multikey | None:
    """The key *profile* lists that *verification_method* names, if any.

    The key must be listed under ``assertionMethod`` of a profile whose id is
    the key's actor, and its ``controller`` must be that actor (SIG-02-001),
    each compared normalised (OID-01-006).  Anything other than a
    :class:`CoreActor` lists no key.  The profile's validators already hold
    each key to its own actor, but a list changed by assignment or ``append``
    skips them (CM-27-001), so the key's id and ``controller`` are checked
    here again.

    Raises:
        VultronVerificationKeyError: *verification_method* is not
            ``<actor id>#<fragment>``.
    """
    owner, fragment = _split_key_id(verification_method)
    if not isinstance(profile, CoreActor):
        return None
    if normalise_actor_id(profile.id_) != owner:
        return None
    for key in profile.assertion_method:
        if normalise_actor_id(key.controller) != owner:
            continue
        if _key_id_parts(key.id_) == (owner, fragment):
            return key
    return None


async def resolve_verification_key(
    verification_method: str,
    *,
    author_id: str,
    fetcher: ActorProfileFetchPort,
    requester_id: str,
) -> Multikey:
    """The key *verification_method* names, from *author_id*'s profile.

    *author_id* is the actor the signed document says wrote it.  A key in
    any other actor's profile is refused before anything is fetched: a third
    actor's valid proof says nothing about the author (SIG-02-001).  The two
    ids are compared normalised (OID-01-006).

    The profile is always fetched through *fetcher*, from the author's own
    URL, on behalf of *requester_id*, the receiving actor; no stored copy is
    read (SIG-02-003).  Anything a fetcher raises other than
    :class:`~vultron.errors.VultronActorProfileFetchError` is a fault in the
    fetcher, not in the proof, and propagates.  A refusal names the key and
    its actor only, never what the fetch met, because it goes back to the
    sender, who chose the URL fetched; the log says why.

    Raises:
        VultronVerificationKeyError: *verification_method* names no key in an
            actor profile, names a key of an actor other than *author_id*,
            the profile could not be fetched, or it does not list the key.
            Each is a refusal of the proof (SIG-03-002).
    """
    owner = key_owner_id(verification_method)
    if normalise_actor_id(author_id) != owner:
        raise VultronVerificationKeyError(
            f"the proof names key {verification_method!r}, which is not in"
            f" the profile of its author {author_id!r} (SIG-02-001)"
        )
    try:
        fetched = await fetcher.fetch_profile(owner, requester_id)
    except VultronActorProfileFetchError as exc:
        # The refusal goes back to the sender, who chose the URL fetched, so
        # it says nothing of what the fetch met; the log and the chained
        # cause do.
        logger.warning(
            "Cannot read key %s: fetching the profile of %s for actor_id=%s"
            " failed: %s",
            verification_method,
            owner,
            requester_id,
            exc,
        )
        raise VultronVerificationKeyError(
            f"cannot read key {verification_method!r}: the profile of"
            f" {owner!r} could not be fetched (SIG-02-001)"
        ) from exc
    key = published_key(fetched, verification_method)
    if key is None:
        raise VultronVerificationKeyError(
            f"the profile of {owner!r} does not list key"
            f" {verification_method!r} under assertionMethod (SIG-02-001)"
        )
    logger.info(
        "Resolved key %s from the fetched profile of %s for actor_id=%s",
        verification_method,
        owner,
        requester_id,
    )
    return key


__all__ = [
    "key_owner_id",
    "published_key",
    "resolve_verification_key",
]
