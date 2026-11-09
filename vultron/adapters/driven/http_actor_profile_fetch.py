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

"""Fetch an actor's profile over HTTP for the verification-key resolver.

Implements :class:`~vultron.core.ports.actor_profile_fetch.ActorProfileFetchPort`
over the object fetcher the inbox's dereference uses
(:class:`~vultron.adapters.driven.http_object_fetch.HttpObjectFetcher`): one
plain ``GET`` of ``{actor}/profile`` per attempt, bounded and backed off as
any object fetch is (AKM-05-008), with no proof on the request (SIG-02-002).
The actor id is the profile's URL, so the fetch reaches another container in
the multi-container demos as a delivery does.

The body is parsed here, at the edge, so core receives a typed
:class:`~vultron.core.models.actor.CoreActor` (ADR-0032).  A profile typed
``"Actor"`` is refused by name: this codebase reads that generic type
without its ``assertionMethod``, so it could never yield a key, and a
refusal saying the actor published no key would mislead.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

from vultron.adapters.driven.http_object_fetch import (
    HttpObjectFetcher,
    ObjectFetcher,
    default_object_fetcher,
    parse_fetched_object,
)
from vultron.config import get_config
from vultron.core.models.actor import CoreActor
from vultron.core.models.object_fetch import (
    ObjectFetchSource,
    ObjectFetchUse,
    ObjectReference,
)
from vultron.errors import (
    VultronActorProfileFetchError,
    VultronValidationError,
)

#: The AS2 actor type that parses without the profile's keys.
GENERIC_ACTOR_TYPE = "Actor"

#: The URL schemes a profile is fetched over.
_FETCH_SCHEMES = frozenset({"http", "https"})


def check_profile_fetch_target(actor_id: str) -> None:
    """Refuse an actor id that is not a URL a profile may be fetched from.

    The key lookup runs before the sender is verified, so the URL is the
    unverified sender's choice.  Only a plain ``http`` or ``https`` URL is
    fetched: no user info, query or fragment, and no host that is an IP
    literal outside the public address space (loopback, private,
    link-local such as a cloud metadata address, multicast, reserved or
    unspecified), in any spelling a resolver reads as an address, an IPv4
    address embedded in an IPv6 one included.  A host name is fetched: the
    multi-container demos name their peers by internal host names, and
    resolving a name to check it here would not bind the address the client
    then connects to.  A
    production allow-list or key cache is #1184.

    Raises:
        VultronActorProfileFetchError: *actor_id* is not such a URL; the
            message says which rule it breaks.
    """
    parts = urlsplit(actor_id)
    if parts.scheme not in _FETCH_SCHEMES or not parts.hostname:
        raise VultronActorProfileFetchError(
            f"{actor_id!r} is not an http or https URL with a host"
        )
    if parts.username is not None or parts.password is not None:
        raise VultronActorProfileFetchError(
            f"{actor_id!r} carries user info, which a profile URL may not"
        )
    if parts.query or parts.fragment:
        raise VultronActorProfileFetchError(
            f"{actor_id!r} carries a query or fragment, which a profile URL"
            " may not"
        )
    address = _host_address(parts.hostname.rstrip("."))
    if address is not None and not _is_public(address):
        raise VultronActorProfileFetchError(
            f"{actor_id!r} names a non-public address, which a profile is"
            " not fetched from"
        )


#: IPv6 prefixes that carry an IPv4 address in their last 32 bits (NAT64).
_NAT64_PREFIXES = (
    ipaddress.ip_network("64:ff9b::/96"),
    ipaddress.ip_network("64:ff9b:1::/48"),
)


def _host_address(
    host: str,
) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """The IP address *host* spells, in any form a resolver reads, or ``None``.

    Besides the canonical forms, the C resolver reads a legacy IPv4 spelling
    (``2852039166``, ``0xa9fea9fe``, ``0251.0376.0251.0376``, ``169.254.43518``)
    as an address, so those are read here the way ``inet_aton`` reads them.
    """
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass
    try:
        return ipaddress.IPv4Address(socket.inet_aton(host))
    except OSError:
        return None


def _is_public(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Whether *address*, and any IPv4 address it embeds, is public."""
    if not address.is_global:
        return False
    if isinstance(address, ipaddress.IPv6Address):
        embedded = [address.ipv4_mapped, address.sixtofour]
        if address.teredo is not None:
            embedded.extend(address.teredo)
        if any(address in prefix for prefix in _NAT64_PREFIXES):
            embedded.append(ipaddress.IPv4Address(int(address) & 0xFFFFFFFF))
        return all(v4.is_global for v4 in embedded if v4 is not None)
    return True


def verification_object_fetcher() -> HttpObjectFetcher:
    """The fetcher for a key lookup made before the sender is verified.

    One attempt, no retry, and a short timeout
    (``verification_key_fetch_timeout_seconds``): an unsigned or forged
    delivery must not buy the AKM-05-008 retries an object fetch gets.
    """
    return HttpObjectFetcher(
        max_attempts=1,
        timeout=get_config().verification_key_fetch_timeout_seconds,
    )


class HttpActorProfileFetchAdapter:
    """:class:`ActorProfileFetchPort` over an :class:`ObjectFetcher`.

    Args:
        fetcher: The fetcher to use; defaults to the configured HTTP fetcher
            (:func:`default_object_fetcher`), built on the first fetch.
    """

    def __init__(self, fetcher: ObjectFetcher | None = None) -> None:
        self._fetcher = fetcher

    async def fetch_profile(
        self, actor_id: str, requester_id: str
    ) -> CoreActor:
        """Fetch and parse *actor_id*'s profile on behalf of *requester_id*.

        Raises:
            VultronActorProfileFetchError: *actor_id* is not a URL to fetch
                from (:func:`check_profile_fetch_target`), the fetch failed,
                or the body is not *actor_id*'s profile as one of the
                concrete actor types.
        """
        check_profile_fetch_target(actor_id)
        if self._fetcher is None:
            self._fetcher = default_object_fetcher()
        try:
            reference = ObjectReference(
                object_id=actor_id,
                source=ObjectFetchSource.ACTOR_PROFILE,
                host_actor_id=actor_id,
                use=ObjectFetchUse.HAND_OFF,
            )
        except ValueError as exc:
            raise VultronActorProfileFetchError(
                f"{actor_id!r} is not an actor id a profile can be fetched"
                f" from: {exc}"
            ) from exc
        result = await self._fetcher.fetch(reference, requester_id)
        if result.body is None:
            raise VultronActorProfileFetchError(
                f"fetching the profile of {actor_id!r} failed after"
                f" {result.attempts} attempt(s): {result.failure}"
            )
        if result.body.get("type") == GENERIC_ACTOR_TYPE:
            raise VultronActorProfileFetchError(
                f"the profile of {actor_id!r} is typed"
                f" {GENERIC_ACTOR_TYPE!r}, which this receiver reads without"
                " its assertionMethod; a profile must use a concrete actor"
                " type, such as 'Person' or 'Organization', to publish a key"
            )
        try:
            parsed = parse_fetched_object(result.body, actor_id)
        except VultronValidationError as exc:
            raise VultronActorProfileFetchError(str(exc)) from exc
        if not isinstance(parsed, CoreActor):
            raise VultronActorProfileFetchError(
                f"the fetched {actor_id!r} is a {type(parsed).__name__}, not"
                " an actor profile"
            )
        return parsed


__all__ = [
    "GENERIC_ACTOR_TYPE",
    "HttpActorProfileFetchAdapter",
    "check_profile_fetch_target",
    "verification_object_fetcher",
]
