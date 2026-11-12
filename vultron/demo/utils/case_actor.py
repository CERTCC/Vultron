"""Locating, binding and provisioning the CaseActor a demo talks to."""

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

import logging
from urllib.parse import urlsplit

from vultron.core.behaviors.case.case_actor_identity import (
    case_actor_identity,
)
from vultron.core.models._helpers import authored_times
from vultron.demo import wall_clock
from vultron.demo.utils.client import DataLayerClient
from vultron.demo.utils.environment import seed_actor
from vultron.errors import DemoCaseActorUnconfiguredError
from vultron.wire.as2.vocab.base.objects.actors import as_Actor

# One logger for the whole package, so log records keep its name.
logger = logging.getLogger(__package__)


#: Slug a CaseActor is registered under on whichever container hosts it.  A CaseActor
#: is a role a container wears per CP-08-002/003, not a per-case object (#1872),
#: so the slug is a constant rather than something derived from a case or report.
CASE_ACTOR_SLUG = "case-actor"


def case_actor_id_on(base_url: str) -> str:
    """Return the canonical CaseActor URI hosted by the node at *base_url*.

    Demo inspection clients need this to bind ``DataLayerClient.actor_id``: the
    dedicated ``case-actor`` container hosts an actor whose store is the one a
    ``/datalayer/`` read has to name (ADR-0073), and the container's base URL is
    the only thing a demo entry point knows before any actor exists.

    Args:
        base_url: Base URL of the container hosting the CaseActor, e.g.
            ``http://case-actor:7999/api/v2``.

    Returns:
        ``{base_url}/actors/case-actor``.
    """
    return f"{base_url.rstrip('/')}/actors/{CASE_ACTOR_SLUG}"


def bound_case_actor_client(base_url: str) -> DataLayerClient:
    """Return a client for the CaseActor container at *base_url*, bound to it.

    The binding is what makes ``dl_path`` reads address the CaseActor's own
    store (ADR-0073); a scenario's entry point knows only the container's URL
    before any actor exists, so it binds from that (#1876).
    """
    return DataLayerClient(
        base_url=base_url, actor_id=case_actor_id_on(base_url)
    )


def configured_case_actor_id() -> str:
    """Return the configured CaseActor identity, or raise when none is set.

    The identity comes from ``ActorConfig.case_actor_service_url``
    (``VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL``) only, never from this node's
    own ``server.base_url`` (CP-08-001, CP-08-009). A single-container
    topology configures the variable to its own API base, as
    ``docker/docker-compose.yml`` does.

    Raises:
        DemoCaseActorUnconfiguredError: No CaseActor service URL is
            configured, so there is no CaseActor to propose a case to.
    """
    case_actor_id = case_actor_identity()
    if not case_actor_id:
        raise DemoCaseActorUnconfiguredError(
            "No CaseActor service is configured: set "
            "VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL to the API base URL of the "
            "CaseActor's container (CP-08-009)"
        )
    return case_actor_id


def case_actor_id_for_report(report_id: str) -> str:
    """Return the CaseActor URI a report's CaseProposal will be sent to.

    The same identity for every report, because a CaseActor is a container, not a
    per-case object (#1872). *report_id* is retained so call sites still read as
    "the CaseActor for this report" and so the signature survives if the mapping
    ever stops being constant.

    Raises:
        DemoCaseActorUnconfiguredError: No CaseActor service URL is configured
            (:func:`configured_case_actor_id`).
    """
    del report_id  # one CaseActor per container, not per report
    return configured_case_actor_id()


def _is_same_node(base_url: str, actor_id: str) -> bool:
    """True when *actor_id* is served by the node at *base_url*.

    Compared on scheme+host+port, because that is what decides whether a
    ``POST /actors/`` reaches the container that would host the actor. The path
    prefix is deliberately ignored: it varies (``/api/v2``) without changing which
    process answers.
    """
    a, b = urlsplit(base_url), urlsplit(actor_id)
    return (a.scheme, a.netloc) == (b.scheme, b.netloc)


def seed_case_actor(client: DataLayerClient) -> as_Actor:
    """Provision the CaseActor this container's reports are proposed to.

    ``ProposeReportCaseToActorNode`` sends ``Create(CaseProposal)`` to a CaseActor
    whose URI it derives from the report, and delivery is an ordinary HTTP POST to
    that actor's inbox (ADR-0042).  The inbox route resolves the actor from the
    store its URI names, so the CaseActor has to be a *hosted actor* before the
    proposal is delivered or the round-trip never starts.

    The identity is stable: one CaseActor per container, whatever the report
    (#1872, closed).  That is what lets a demo provision it *before* anything
    else happens -- before the ``submit-report`` trigger runs, when no report id
    exists yet -- instead of chasing a per-report id after the fact.  The
    trigger's own outbox is then the sole delivery of the ``Offer``; the demo
    never re-posts it.

    In the exchange demos one container plays both the participant node and the
    CaseActor service, so that container is the one that must host it.  Going
    through ``POST /actors/`` is what puts the record in the CaseActor's own
    store, since the route opens the store the id names (ADR-0073).

    Returns:
        The created (or pre-existing) CaseActor as an ``as_Actor``.
    """
    case_actor_id = case_actor_id_for_report("")

    # Co-located only. ``POST /actors/`` recomputes the canonical URI from the
    # *serving* node's base URL (ADR-0073 — which is why only the short segment
    # travels), so posting a remote CaseActor's id here does not provision that
    # container: it fabricates a local actor under the same slug. In the Docker
    # topology that produced a spurious ``http://vendor:7999/api/v2/actors/
    # case-actor`` alongside the real ``http://case-actor:7999/...`` one.
    #
    # A container hosting its own CaseActor provisions it from its own seed
    # config (``docker/seed-configs/seed-case-actor.yaml``), which is exactly
    # what a stable identity makes possible.
    if not _is_same_node(client.base_url, case_actor_id):
        logger.info(
            "CaseActor %s is hosted elsewhere; leaving provisioning to that"
            " container's own seed config",
            case_actor_id,
        )
        return as_Actor(
            id_=case_actor_id,
            name="CaseActor",
            **authored_times(wall_clock.now()),
        )

    actor = seed_actor(
        client=client,
        name="CaseActor",
        actor_type="Service",
        actor_id=case_actor_id,
    )
    logger.info("Provisioned CaseActor: %s", case_actor_id)
    return actor
