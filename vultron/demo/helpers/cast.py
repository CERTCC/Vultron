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
"""The fixed cast every demo scenario runs on (DEMOCI-11-020, DEMOCI-11-021).

Every registered scenario runs on the same containers: :data:`CAST`, five
role-neutral actor containers (``actor0`` to ``actor4``), plus the dedicated
:data:`CASE_ACTOR` container.  Each member has one container slot, one local
port and one actor id in every scenario, so two scenarios that tell the same
opening record the same bytes for it (DEMOCI-11-018).

Members 0, 1 and 2 always play the first Reporter, first Vendor and first
Coordinator a scenario seats (:data:`FIRST_OF_ROLE`).  A scenario without one
of these roles leaves that member unused (``rv`` has no Coordinator).  Members
3 and up are character actors: each scenario gives them their role through the
act that seats them (the Invite and its offered role), not through container
settings.

A scenario seats each of its actors in a slot with an ``ActorRole``
(:mod:`vultron.demo.helpers.actor_roles`), so it declares no URL, port or
actor id of its own.  The Docker Compose file
(``docker/docker-compose-multi-actor.yml``) defines one service per slot, named
:attr:`ContainerSlot.name`; ``test/demo_unit/test_cast.py`` checks that the two
agree.

Design: ``notes/demo-scenario-tree.md`` § "Composition".
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from vultron.demo.utils import CASE_ACTOR_SLUG
from vultron.enums.roles import CVDRole
from vultron.errors import DemoActorRoleError

#: Compose service name spelling: lowercase alphanumerics separated by single
#: hyphens.  The name is the container's host name, the slug of the one actor
#: it hosts, and the stem of its ``VULTRON_*_BASE_URL`` env var, so anything
#: else breaks one of the three.
_SLOT_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*\Z")

#: The port every actor container serves on inside the compose network.
CONTAINER_PORT = 7999


@dataclass(frozen=True, slots=True)
class ContainerSlot:
    """One container of the cast: its compose service, local port and actor.

    The compose service name is also the container's host name and the slug of
    the one actor it hosts, so the actor id at a base URL is
    ``{base_url}/actors/{name}``.  Locally (no compose network), the container
    listens on ``localhost:{port}``.
    """

    #: Compose service name, host name and actor slug, e.g. ``"actor0"``.
    name: str
    #: Port of the container when it runs on the host rather than in compose.
    port: int

    def __post_init__(self) -> None:
        # Every derivation below reads `name`, so an empty or malformed one
        # yields a legal-looking `VULTRON__BASE_URL` and an actor id ending in
        # a bare slash, both of which fail far from here.
        if not _SLOT_NAME_RE.match(self.name):
            raise DemoActorRoleError(
                f"cast container name {self.name!r} is not a usable compose "
                "service name; expected lowercase alphanumerics separated by "
                "single hyphens, because the name is the container's host "
                "name, its actor slug and the stem of its env var."
            )
        if not isinstance(self.port, int) or not 1 <= self.port <= 65535:
            raise DemoActorRoleError(
                f"cast container {self.name!r} has port {self.port!r}, which "
                "is not a TCP port; it is what the container publishes when it "
                "runs on the host rather than in compose."
            )

    @property
    def url_env(self) -> str:
        """Env var naming this container's base URL, e.g. ``VULTRON_ACTOR0_BASE_URL``."""
        return f"VULTRON_{self.name.upper().replace('-', '_')}_BASE_URL"

    @property
    def default_url(self) -> str:
        """Base URL when :attr:`url_env` is unset: the local port."""
        return f"http://localhost:{self.port}/api/v2"

    @property
    def id_env(self) -> str:
        """Env var naming the actor this container hosts.

        Backs each scenario's ``--<name>-id`` option, so the compose
        environment can hand a container's actor id to the scenario that drives
        it (DEMOMA-14-008) without the scenario naming either.
        """
        return f"VULTRON_{self.name.upper().replace('-', '_')}_ACTOR_ID"

    @property
    def compose_url(self) -> str:
        """Base URL of this container on the compose network."""
        return f"http://{self.name}:{CONTAINER_PORT}/api/v2"

    @property
    def url(self) -> str:
        """This container's base URL: :attr:`url_env` or :attr:`default_url`."""
        return os.environ.get(self.url_env, self.default_url)

    def actor_id(self, base_url: str) -> str:
        """Return the id of the actor this container hosts at *base_url*."""
        return f"{base_url.rstrip('/')}/actors/{self.name}"


#: How many actor containers the cast has: the three fixed-role members plus
#: the character actors the widest scenario needs (``rcvcv`` seats five).
CAST_SIZE = 5

#: The actor containers, in cast order.  Local ports run from 7901.
CAST: tuple[ContainerSlot, ...] = tuple(
    ContainerSlot(name=f"actor{index}", port=7901 + index)
    for index in range(CAST_SIZE)
)

#: The dedicated CaseActor container every scenario proposes its cases to
#: (CP-08-008, DEMOMA-06-004).  It is not a cast member: it plays no CVD role
#: of its own choosing.
CASE_ACTOR = ContainerSlot(name=CASE_ACTOR_SLUG, port=7901 + CAST_SIZE)

#: The cast member that plays the first actor of each fixed role
#: (DEMOCI-11-021).  Members not named here are character actors.
FIRST_OF_ROLE: Mapping[CVDRole, ContainerSlot] = MappingProxyType(
    {
        CVDRole.REPORTER: CAST[0],
        CVDRole.VENDOR: CAST[1],
        CVDRole.COORDINATOR: CAST[2],
    }
)

#: Convenience names for the fixed-role members.
REPORTER_SLOT = FIRST_OF_ROLE[CVDRole.REPORTER]
VENDOR_SLOT = FIRST_OF_ROLE[CVDRole.VENDOR]
COORDINATOR_SLOT = FIRST_OF_ROLE[CVDRole.COORDINATOR]

#: :data:`FIRST_OF_ROLE` read the other way: the fixed role of a container,
#: by slot name.  A character actor's slot is absent, because its role comes
#: from the act that seats it and not from the container (DEMOCI-11-021).
ROLE_OF_SLOT: Mapping[str, CVDRole] = MappingProxyType(
    {slot.name: role for role, slot in FIRST_OF_ROLE.items()}
)

#: The character-actor members, in cast order.
CHARACTER_SLOTS: tuple[ContainerSlot, ...] = tuple(
    slot for slot in CAST if slot.name not in ROLE_OF_SLOT
)

#: Every container a scenario may name: the cast, then the CaseActor.
ALL_SLOTS: tuple[ContainerSlot, ...] = (*CAST, CASE_ACTOR)


def slot_for(base_url: str) -> ContainerSlot | None:
    """The cast container served at *base_url*, or ``None`` for none of them.

    Matches the three addresses one container answers on — its compose URL, its
    local URL and whatever :attr:`ContainerSlot.url_env` currently says — so a
    caller holding only a base URL can name the actor that container hosts.
    ``http://localhost:7901/api/v2`` is ``actor0``, which is the answer a
    hostname alone cannot give.
    """
    wanted = base_url.rstrip("/")
    for slot in ALL_SLOTS:
        if wanted in {
            slot.compose_url,
            slot.default_url,
            slot.url.rstrip("/"),
        }:
            return slot
    return None


__all__ = [
    "ALL_SLOTS",
    "CASE_ACTOR",
    "CAST",
    "CAST_SIZE",
    "CHARACTER_SLOTS",
    "CONTAINER_PORT",
    "COORDINATOR_SLOT",
    "ContainerSlot",
    "FIRST_OF_ROLE",
    "REPORTER_SLOT",
    "ROLE_OF_SLOT",
    "slot_for",
    "VENDOR_SLOT",
]
