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
key that verifies the proof is read only from that actor's profile
(SIG-02-001), never derived from a seed (SIG-05-002):

1. the receiver's held copy of the profile, when it lists the key;
2. otherwise the profile fetched from the actor with a plain ``GET``
   (SIG-02-002), through :class:`ActorProfileFetchPort`.

The held copy is tried first because a receiver keeps a held profile over a
fetched one (MV-10-003).  It is not trusted to be complete: the copy an
activity carries inline is the sender's own stored record, which lists no
key (AKM-05-005), so a held copy without the named key leads to a fetch, not
a refusal.  The fetched profile is used for this lookup and not stored.

Actor ids are compared normalised, without a trailing slash (OID-01-006):
the key's actor, the profile's id and the key's ``controller`` all name the
actor however a sender spelled it.  The result is a core
:class:`~vultron.core.models.multikey.Multikey`; a verifier passes its
``publicKeyMultibase`` to ``vultron.wire.as2.signing.verify``.

When a held copy goes stale and how a rotated key is found are #1184.
"""

from __future__ import annotations

import logging

from vultron.core.models.actor import CoreActor
from vultron.core.models.multikey import Multikey
from vultron.core.ports.actor_profile_fetch import ActorProfileFetchPort
from vultron.core.ports.case_persistence import CasePersistence
from vultron.errors import (
    VultronActorProfileFetchError,
    VultronVerificationKeyError,
)
from vultron.primitives import normalise_actor_id

logger = logging.getLogger(__name__)


def _split_key_id(key_id: str) -> tuple[str, str]:
    """*key_id* as its normalised actor id and its fragment.

    Raises:
        VultronVerificationKeyError: *key_id* is not ``<actor id>#<fragment>``.
    """
    actor_id, hash_sign, fragment = key_id.partition("#")
    owner = normalise_actor_id(actor_id)
    if not hash_sign or not owner or not fragment:
        raise VultronVerificationKeyError(
            f"verificationMethod {key_id!r} does not name a key in an actor"
            " profile, <actor id>#<fragment> (SIG-01-002)"
        )
    return owner, fragment


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
    profile: object, verification_method: str
) -> Multikey | None:
    """The key *profile* lists that *verification_method* names, if any.

    The key must be listed under ``assertionMethod`` of a profile whose id is
    the key's actor, and its ``controller`` must be that actor (SIG-02-001),
    each compared normalised (OID-01-006).  Anything other than a
    :class:`CoreActor` lists no key.

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
        if key.id_[len(key.controller) + 1 :] == fragment:
            return key
    return None


async def resolve_verification_key(
    verification_method: str,
    *,
    author_id: str,
    dl: CasePersistence,
    fetcher: ActorProfileFetchPort,
    requester_id: str,
) -> Multikey:
    """The key *verification_method* names, from *author_id*'s profile.

    *author_id* is the actor the signed document says wrote it.  A key in
    any other actor's profile is refused before anything is read or
    fetched: a third actor's valid proof says nothing about the author
    (SIG-02-001).  The two ids are compared normalised (OID-01-006).

    *dl* is the receiving actor's store, which holds its copies of other
    actors' profiles, and *requester_id* is the receiving actor, named on a
    fetch.  The held copy is read first; when it lists no key the proof
    names, the profile is fetched through *fetcher* (SIG-02-001).  A held
    copy stored under an unnormalised id is not found by the read; the
    fetch, made to the normalised id, still finds the key.

    Raises:
        VultronVerificationKeyError: *verification_method* names no key in an
            actor profile, names a key of an actor other than *author_id*,
            the profile could not be fetched, or neither copy
            lists the key.  Each is a refusal of the proof (SIG-03-002).
    """
    owner = key_owner_id(verification_method)
    if normalise_actor_id(author_id) != owner:
        raise VultronVerificationKeyError(
            f"the proof names key {verification_method!r}, which is not in"
            f" the profile of its author {author_id!r} (SIG-02-001)"
        )
    held = published_key(dl.read(owner), verification_method)
    if held is not None:
        logger.debug(
            "Resolved key %s from the held profile of actor_id=%s",
            verification_method,
            owner,
        )
        return held
    try:
        fetched = await fetcher.fetch_profile(owner, requester_id)
    except VultronActorProfileFetchError as exc:
        raise VultronVerificationKeyError(
            f"cannot read key {verification_method!r}: the held profile of"
            f" {owner!r} does not list it, and fetching the profile failed:"
            f" {exc}"
        ) from exc
    key = published_key(fetched, verification_method)
    if key is None:
        raise VultronVerificationKeyError(
            f"the profile of {owner!r} does not list key"
            f" {verification_method!r} under assertionMethod (SIG-02-001)"
        )
    logger.info(
        "Resolved key %s from the fetched profile of actor_id=%s for"
        " actor_id=%s",
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
