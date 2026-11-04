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

"""The per-scenario ``seed_containers*`` helpers.

Each seeds one scenario's containers as a full mesh of mutually known peers
through :func:`~vultron.demo.helpers.seeding.actors._seed_mesh`; they differ
only in their cast.
"""

from vultron.demo.helpers.seeding.actors import (
    _MeshLogStyle,
    _MeshMember,
    _seed_mesh,
)
from vultron.demo.utils import DataLayerClient
from vultron.wire.as2.vocab.base.objects.actors import as_Actor


def seed_containers(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    reporter_actor_id: str | None = None,
    vendor_actor_id: str | None = None,
    case_actor_client: DataLayerClient | None = None,
) -> tuple[as_Actor, as_Actor]:
    """Seed both containers: create actor records and register cross-container peers.

    Seeded as a full mesh of peers by :func:`_seed_mesh`, so idempotent.

    Args:
        reporter_client: DataLayerClient connected to the Reporter container.
        vendor_client: DataLayerClient connected to the Vendor container.
        reporter_actor_id: Optional deterministic URI for the Reporter actor.
            When absent the server derives one from ``VULTRON_SERVER__BASE_URL``.
        vendor_actor_id: Optional deterministic URI for the Vendor actor.
            When absent the server derives one from ``VULTRON_SERVER__BASE_URL``.
        case_actor_client: Client for the dedicated case-actor container,
            whose address book gets every seeded actor
            (:func:`seed_case_actor_peers`).

    Returns:
        Tuple of ``(reporter, vendor)`` ``as_Actor`` objects as created on their
        respective containers.
    """
    reporter, vendor = _seed_mesh(
        [
            _MeshMember(
                reporter_client, "Reporter", "Person", reporter_actor_id
            ),
            _MeshMember(
                vendor_client, "Vendor", "Organization", vendor_actor_id
            ),
        ],
        case_actor_client,
        _MeshLogStyle.PER_PEER,
    )
    return reporter, vendor


def seed_containers_rvv(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    reporter_actor_id: str | None = None,
    vendor_actor_id: str | None = None,
    vendor2_actor_id: str | None = None,
    case_actor_client: DataLayerClient | None = None,
) -> tuple[as_Actor, as_Actor, as_Actor]:
    """Seed three containers for the RVV scenario: Reporter, Vendor1, Vendor2.

    Seeded as a full mesh of peers by :func:`_seed_mesh`, so idempotent.

    Args:
        reporter_client: DataLayerClient connected to the Reporter container.
        vendor_client: DataLayerClient connected to the Vendor1 container.
        vendor2_client: DataLayerClient connected to the Vendor2 container.
        reporter_actor_id: Optional deterministic URI for the Reporter actor.
        vendor_actor_id: Optional deterministic URI for the Vendor1 actor.
        vendor2_actor_id: Optional deterministic URI for the Vendor2 actor.
        case_actor_client: Client for the dedicated case-actor container,
            whose address book gets every seeded actor
            (:func:`seed_case_actor_peers`).

    Returns:
        Tuple of ``(reporter, vendor, vendor2)`` ``as_Actor`` objects as
        created on their respective containers.
    """
    reporter, vendor, vendor2 = _seed_mesh(
        [
            _MeshMember(
                reporter_client, "Reporter", "Person", reporter_actor_id
            ),
            _MeshMember(
                vendor_client,
                "Vendor",
                "Organization",
                vendor_actor_id,
                label="Vendor1",
            ),
            _MeshMember(
                vendor2_client, "Vendor2", "Organization", vendor2_actor_id
            ),
        ],
        case_actor_client,
    )
    return reporter, vendor, vendor2


def seed_containers_rvcv(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    reporter_actor_id: str | None = None,
    vendor_actor_id: str | None = None,
    coordinator_actor_id: str | None = None,
    vendor2_actor_id: str | None = None,
    case_actor_client: DataLayerClient | None = None,
) -> tuple[as_Actor, as_Actor, as_Actor, as_Actor]:
    """Seed four containers for the RVCV-extension scenario.

    Containers: Reporter, Vendor1 (CASE_OWNER), Coordinator, Vendor2.

    Seeded as a full mesh of peers by :func:`_seed_mesh`, so idempotent.

    Args:
        reporter_client: DataLayerClient connected to the Reporter container.
        vendor_client: DataLayerClient connected to the Vendor1 container.
        coordinator_client: DataLayerClient connected to the Coordinator container.
        vendor2_client: DataLayerClient connected to the Vendor2 container.
        reporter_actor_id: Optional deterministic URI for the Reporter actor.
        vendor_actor_id: Optional deterministic URI for the Vendor1 actor.
        coordinator_actor_id: Optional deterministic URI for the Coordinator actor.
        vendor2_actor_id: Optional deterministic URI for the Vendor2 actor.
        case_actor_client: Client for the dedicated case-actor container,
            whose address book gets every seeded actor
            (:func:`seed_case_actor_peers`).

    Returns:
        Tuple of ``(reporter, vendor, coordinator, vendor2)`` ``as_Actor`` objects
        as created on their respective containers.
    """
    reporter, vendor, coordinator, vendor2 = _seed_mesh(
        [
            _MeshMember(
                reporter_client, "Reporter", "Person", reporter_actor_id
            ),
            _MeshMember(
                vendor_client,
                "Vendor",
                "Organization",
                vendor_actor_id,
                label="Vendor1",
            ),
            _MeshMember(
                coordinator_client,
                "Coordinator",
                "Organization",
                coordinator_actor_id,
            ),
            _MeshMember(
                vendor2_client, "Vendor2", "Organization", vendor2_actor_id
            ),
        ],
        case_actor_client,
    )
    return reporter, vendor, coordinator, vendor2


def seed_containers_rccv(
    reporter_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    vendor_client: DataLayerClient,
    reporter_actor_id: str | None = None,
    c1_actor_id: str | None = None,
    c2_actor_id: str | None = None,
    vendor_actor_id: str | None = None,
    case_actor_client: DataLayerClient | None = None,
) -> tuple[as_Actor, as_Actor, as_Actor, as_Actor]:
    """Seed four containers for the RCCV-handoff scenario.

    Containers: Reporter (Person), C1 (Organization/Coordinator, initial
    CASE_OWNER), C2 (Organization/Coordinator, new CASE_OWNER after handoff),
    and Vendor (Organization).

    Seeded as a full mesh of peers by :func:`_seed_mesh`, so idempotent.

    Args:
        reporter_client: DataLayerClient connected to the Reporter container.
        c1_client: DataLayerClient connected to the C1 (Coordinator1) container.
        c2_client: DataLayerClient connected to the C2 (Coordinator2) container.
        vendor_client: DataLayerClient connected to the Vendor container.
        reporter_actor_id: Optional deterministic URI for the Reporter actor.
        c1_actor_id: Optional deterministic URI for the C1 actor.
        c2_actor_id: Optional deterministic URI for the C2 actor.
        vendor_actor_id: Optional deterministic URI for the Vendor actor.
        case_actor_client: Client for the dedicated case-actor container,
            whose address book gets every seeded actor
            (:func:`seed_case_actor_peers`).

    Returns:
        Tuple of ``(reporter, c1, c2, vendor)`` ``as_Actor`` objects as
        created on their respective containers.
    """
    reporter, c1, c2, vendor = _seed_mesh(
        [
            _MeshMember(
                reporter_client, "Reporter", "Person", reporter_actor_id
            ),
            _MeshMember(
                c1_client,
                "Coordinator1",
                "Organization",
                c1_actor_id,
                label="C1",
            ),
            _MeshMember(
                c2_client,
                "Coordinator2",
                "Organization",
                c2_actor_id,
                label="C2",
            ),
            _MeshMember(
                vendor_client, "Vendor", "Organization", vendor_actor_id
            ),
        ],
        case_actor_client,
    )
    return reporter, c1, c2, vendor


def seed_containers_rcv(
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    reporter_actor_id: str | None = None,
    coordinator_actor_id: str | None = None,
    vendor_actor_id: str | None = None,
    case_actor_client: DataLayerClient | None = None,
) -> tuple[as_Actor, as_Actor, as_Actor]:
    """Seed three containers for the RCV scenario: Reporter, Coordinator, Vendor.

    In RCV the Coordinator receives the Reporter's report and holds CASE_OWNER;
    a separate CaseActor container hosts the case-actor service actor. The
    CaseActor container does not need explicit cross-seeding here because the
    demo script registers it via peer records embedded in the Coordinator's
    docker seed-config YAML. All actor-to-actor peer registrations that the
    scenario needs are handled in Phase 2 below.

    Seeded as a full mesh of peers by :func:`_seed_mesh`, so idempotent.

    Args:
        reporter_client: DataLayerClient connected to the Reporter container.
        coordinator_client: DataLayerClient connected to the Coordinator container.
        vendor_client: DataLayerClient connected to the Vendor container.
        reporter_actor_id: Optional deterministic URI for the Reporter actor.
        coordinator_actor_id: Optional deterministic URI for the Coordinator actor.
        vendor_actor_id: Optional deterministic URI for the Vendor actor.
        case_actor_client: Client for the dedicated case-actor container,
            whose address book gets every seeded actor
            (:func:`seed_case_actor_peers`).

    Returns:
        Tuple of ``(reporter, coordinator, vendor)`` ``as_Actor`` objects as
        created on their respective containers.
    """
    reporter, coordinator, vendor = _seed_mesh(
        [
            _MeshMember(
                reporter_client, "Reporter", "Person", reporter_actor_id
            ),
            _MeshMember(
                coordinator_client,
                "Coordinator",
                "Organization",
                coordinator_actor_id,
            ),
            _MeshMember(
                vendor_client, "Vendor", "Organization", vendor_actor_id
            ),
        ],
        case_actor_client,
    )
    return reporter, coordinator, vendor


def seed_containers_rcvv(
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    reporter_actor_id: str | None = None,
    coordinator_actor_id: str | None = None,
    vendor_actor_id: str | None = None,
    vendor2_actor_id: str | None = None,
    case_actor_client: DataLayerClient | None = None,
) -> tuple[as_Actor, as_Actor, as_Actor, as_Actor]:
    """Seed four containers for the RCVV-embargo scenario.

    Containers: Reporter (Person), Coordinator (Organization, CASE_OWNER),
    Vendor1 and Vendor2 (Organizations).  Vendor1 is named ``Vendor``, as the
    one Vendor of ``rcv-embargo`` is, because the two scenarios share their
    path up to Vendor1's decision and their ledgers must match there
    (DEMOCI-11-017).  Every actor is created on its own
    container, then registered as a peer on each of the other three.  Seeded by
    :func:`_seed_mesh`, so idempotent, as the other ``seed_containers_*`` are.

    Args:
        reporter_client, coordinator_client, vendor_client, vendor2_client:
            DataLayerClients connected to each member's container.
        reporter_actor_id, coordinator_actor_id, vendor_actor_id,
        vendor2_actor_id: Optional deterministic URIs for each member.
        case_actor_client: Client for the dedicated case-actor container,
            whose address book gets every seeded actor
            (:func:`seed_case_actor_peers`).

    Returns:
        Tuple of ``(reporter, coordinator, vendor, vendor2)`` ``as_Actor``
        objects as created on their respective containers.
    """
    reporter, coordinator, vendor, vendor2 = _seed_mesh(
        [
            _MeshMember(
                reporter_client, "Reporter", "Person", reporter_actor_id
            ),
            _MeshMember(
                coordinator_client,
                "Coordinator",
                "Organization",
                coordinator_actor_id,
            ),
            _MeshMember(
                vendor_client, "Vendor", "Organization", vendor_actor_id
            ),
            _MeshMember(
                vendor2_client, "Vendor2", "Organization", vendor2_actor_id
            ),
        ],
        case_actor_client,
        _MeshLogStyle.SUMMARY,
    )
    return reporter, coordinator, vendor, vendor2


def seed_containers_rcvcv(
    reporter_client: DataLayerClient,
    c1_client: DataLayerClient,
    v1_client: DataLayerClient,
    c2_client: DataLayerClient,
    v2_client: DataLayerClient,
    reporter_actor_id: str | None = None,
    c1_actor_id: str | None = None,
    v1_actor_id: str | None = None,
    c2_actor_id: str | None = None,
    v2_actor_id: str | None = None,
    case_actor_client: DataLayerClient | None = None,
) -> tuple[as_Actor, as_Actor, as_Actor, as_Actor, as_Actor]:
    """Seed five containers for the RCVCV scenario.

    Containers: Reporter (Person), Coordinator1 (Organization), V1 (an
    Organization named ``Vendor``), Coordinator2 (Organization),
    VendorDeployer (Organization).  V1 is named as the one Vendor of ``rcv``
    is, because the two scenarios share their path up to C1's decision and
    their ledgers must match there (DEMOCI-11-017).

    Seeded as a full mesh of peers by :func:`_seed_mesh`, so idempotent.

    Args:
        reporter_client: DataLayerClient connected to the Reporter container.
        c1_client: DataLayerClient connected to the Coordinator1 container.
        v1_client: DataLayerClient connected to the Vendor1 container.
        c2_client: DataLayerClient connected to the Coordinator2 container.
        v2_client: DataLayerClient connected to the VendorDeployer container.
        reporter_actor_id: Optional deterministic URI for the Reporter actor.
        c1_actor_id: Optional deterministic URI for the Coordinator1 actor.
        v1_actor_id: Optional deterministic URI for the Vendor1 actor.
        c2_actor_id: Optional deterministic URI for the Coordinator2 actor.
        v2_actor_id: Optional deterministic URI for the VendorDeployer actor.
        case_actor_client: Client for the dedicated case-actor container,
            whose address book gets every seeded actor
            (:func:`seed_case_actor_peers`).

    Returns:
        Tuple of ``(reporter, c1, v1, c2, v2)`` ``as_Actor`` objects as
        created on their respective containers.
    """
    reporter, c1, v1, c2, v2 = _seed_mesh(
        [
            _MeshMember(
                reporter_client, "Reporter", "Person", reporter_actor_id
            ),
            _MeshMember(
                c1_client,
                "Coordinator1",
                "Organization",
                c1_actor_id,
                label="C1",
            ),
            _MeshMember(
                v1_client, "Vendor", "Organization", v1_actor_id, label="V1"
            ),
            _MeshMember(
                c2_client,
                "Coordinator2",
                "Organization",
                c2_actor_id,
                label="C2",
            ),
            _MeshMember(
                v2_client,
                "VendorDeployer",
                "Organization",
                v2_actor_id,
                label="V2",
            ),
        ],
        case_actor_client,
    )
    return reporter, c1, v1, c2, v2
