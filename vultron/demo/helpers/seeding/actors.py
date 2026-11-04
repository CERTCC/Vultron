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

"""Actor look-ups and the shared actor-seeding steps.

Provides :func:`dl_key` for safe DataLayer path encoding,
:func:`get_actor_by_id` for actor look-ups, and :func:`_seed_mesh`, the
two-phase sequence every ``seed_containers*`` helper runs: create each
container's own actor, then register every actor as a peer on every other
container and on the CaseActor (:func:`seed_case_actor_peers`).
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, auto
from urllib.parse import quote

from vultron.demo.utils import (
    DataLayerClient,
    case_actor_id_on,
    seed_actor,
    seed_peer,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor

logger = logging.getLogger(__name__)


def dl_key(key: str) -> str:
    """URL-encode a DataLayer key for safe embedding in an API path segment.

    Encodes characters that are illegal in URL path segments (e.g., colons in
    URN-style keys like ``urn:uuid:...``) and slashes in HTTP URL keys.
    The DataLayer ``/{key:path}`` route accepts percent-encoded slashes and
    correctly reconstructs the original key before the DataLayer lookup.
    """
    return quote(str(key), safe="")


def get_actor_by_id(client: DataLayerClient, actor_id: str) -> as_Actor:
    """Fetch an actor record from a container by its full URI.

    Args:
        client: DataLayerClient connected to the target container.
        actor_id: Full URI of the actor to fetch.

    Returns:
        The ``as_Actor`` object.

    Raises:
        ValueError: If the actor is not found.
    """
    actors = client.get("/actors/")
    for a in actors:
        actor = as_Actor.model_validate(a)
        if actor.id_ == actor_id:
            return actor
    raise ValueError(f"Actor {actor_id!r} not found in container")


def _own_actor(client: DataLayerClient, actor: as_Actor) -> as_Actor:
    """Record on *client* which actor's store its DataLayer reads address.

    Under ADR-0073 ``base_url`` names a *container*, which no longer says whose
    replica a read is about: a container may host more than one actor — the
    dedicated case-actor container's CaseActor, or a CaseActor co-hosted in a
    single-container exchange demo.  ``DataLayerClient.dl_path`` refuses to guess, so the
    binding has to happen where the fact is learned — here, as the container's
    *own* actor is created.  The scenario entry points cannot do it, because they
    build their clients for the health check before any actor exists.

    Deliberately not folded into :func:`seed_actor`: that helper also registers
    *peers*, so binding there would leave each client addressing whichever peer
    was seeded last — the store of an actor the container does not host, which is
    the confusion ADR-0073#peer-records-in-knowers-store makes easy to fall into.

    Returns *actor* so the call can wrap ``seed_actor(...)`` in place.
    """
    client.actor_id = actor.id_
    logger.debug(
        "DataLayer reads via %s now address actor %s",
        client.base_url,
        actor.id_,
    )
    return actor


def seed_case_actor_peers(
    case_actor_client: DataLayerClient | None, actors: Sequence[as_Actor]
) -> None:
    """Register every seeded demo actor in the CaseActor's address book.

    The CaseActor names the participants in the activities it sends (the stub
    and full-case Invites among them) and carries each as it holds it: a seeded
    peer as its profile, an actor known only by URI as an id-and-type reference
    (AKM-05-005, AKM-05-017, ADR-0159).  The demo reset clears its address book with every
    other record and :func:`seed_case_actor_identity` re-creates only the
    identity, so the peers ``docker/seed-configs/seed-case-actor.yaml`` gives it
    at startup are registered again here.  A ``None`` client (a topology with
    no dedicated case-actor container) registers nothing.

    Raises:
        ValueError: When a seeded actor carries no name to register it under.
    """
    if case_actor_client is None:
        return
    case_actor_id = case_actor_id_on(case_actor_client.base_url)
    for actor in actors:
        if not actor.name:
            raise ValueError(
                f"seeded actor {actor.id_!r} has no name to register with"
                " the CaseActor"
            )
        actor_type = getattr(actor.type_, "value", actor.type_)
        seed_peer(
            client=case_actor_client,
            local_actor_id=case_actor_id,
            peer_id=actor.id_,
            name=actor.name,
            actor_type=str(actor_type),
        )
    logger.info(
        "%d demo actor(s) registered as peers on the CaseActor container",
        len(actors),
    )


@dataclass(frozen=True)
class _MeshMember:
    """One container of a seeded mesh and the actor it hosts.

    Attributes:
        client: DataLayerClient connected to the member's container.
        name: The actor's name, on its own container and as a peer.
        actor_type: The actor's ActivityStreams type.
        actor_id: Optional deterministic URI for the actor; when absent the
            server derives one from ``VULTRON_SERVER__BASE_URL``.
        label: How the log lines name the member, when not by *name*.
    """

    client: DataLayerClient
    name: str
    actor_type: str
    actor_id: str | None
    label: str | None = None

    @property
    def log_label(self) -> str:
        """The member's name in log lines."""
        return self.label or self.name


def _and_list(labels: Sequence[str]) -> str:
    """Join *labels* as prose: ``A``, ``A and B``, ``A, B, and C``."""
    if len(labels) <= 2:
        return " and ".join(labels)
    return ", ".join(labels[:-1]) + ", and " + labels[-1]


class _MeshLogStyle(Enum):
    """How :func:`_seed_mesh` words its INFO lines.

    Each ``seed_containers*`` helper keeps the log lines it wrote before the
    seeding was shared, so the demo output is unchanged.

    Attributes:
        PER_CONTAINER: ``"<label> actor seeded: <id>"`` per actor, then
            ``"<peers> registered as peers on <label> container"`` per
            container.
        PER_PEER: ``"<label> actor seeded on <label> container: <id>"`` per
            actor, then ``"<peer> peer registered on <label> container: <id>"``
            per peer registration.
        SUMMARY: ``"<label> actor seeded: <id>"`` per actor, then one line once
            every peer is registered.
    """

    PER_CONTAINER = auto()
    PER_PEER = auto()
    SUMMARY = auto()


def _seed_mesh(
    members: Sequence[_MeshMember],
    case_actor_client: DataLayerClient | None,
    log_style: _MeshLogStyle = _MeshLogStyle.PER_CONTAINER,
) -> list[as_Actor]:
    """Seed *members*' containers as a full mesh of mutually known peers.

    The seeding is done in two phases to avoid ordering issues:

    1. Create the local actor on each container independently, and bind the
       container's client to it (:func:`_own_actor`).
    2. Register every actor as a known peer on every other container, and
       every actor on the dedicated case-actor container
       (:func:`seed_case_actor_peers`).

    Idempotent: re-running it returns existing actors unchanged (both
    ``POST /actors/`` and ``POST /actors/{id}/peers/`` are idempotent).

    Args:
        members: The mesh's containers and actors, in seeding order.
        case_actor_client: Client for the dedicated case-actor container, or
            ``None`` when the topology has none.
        log_style: How the INFO lines are worded (:class:`_MeshLogStyle`).

    Returns:
        The seeded actors, in *members* order.
    """
    logger.info("Phase 1: creating local actors on each container...")
    actors: list[as_Actor] = []
    for member in members:
        actor = _own_actor(
            member.client,
            seed_actor(
                client=member.client,
                name=member.name,
                actor_type=member.actor_type,
                actor_id=member.actor_id,
            ),
        )
        if log_style is _MeshLogStyle.PER_PEER:
            logger.info(
                "%s actor seeded on %s container: %s",
                member.log_label,
                member.log_label,
                actor.id_,
            )
        else:
            logger.info("%s actor seeded: %s", member.log_label, actor.id_)
        actors.append(actor)

    logger.info("Phase 2: registering cross-container peers...")
    for local_member, local in zip(members, actors, strict=True):
        registered: list[str] = []
        for peer_member, peer in zip(members, actors, strict=True):
            if peer.id_ == local.id_:
                continue
            seed_peer(
                client=local_member.client,
                local_actor_id=local.id_,
                peer_id=peer.id_,
                name=peer_member.name,
                actor_type=peer_member.actor_type,
            )
            if log_style is _MeshLogStyle.PER_PEER:
                logger.info(
                    "%s peer registered on %s container: %s",
                    peer_member.log_label,
                    local_member.log_label,
                    peer.id_,
                )
            registered.append(peer_member.log_label)
        if log_style is _MeshLogStyle.PER_CONTAINER:
            logger.info(
                "%s registered as peers on %s container",
                _and_list(registered),
                local_member.log_label,
            )
    if log_style is _MeshLogStyle.SUMMARY:
        logger.info("Every actor registered as a peer on the other containers")

    seed_case_actor_peers(case_actor_client, actors)
    return actors
