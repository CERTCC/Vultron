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

"""Resetting demo containers to a clean baseline before a run.

The reset clears every record on a node, the dedicated case-actor
container's CaseActor identity included, so :func:`reset_containers`
re-seeds that identity (:func:`seed_case_actor_identity`) afterwards.
"""

import logging
from collections.abc import Callable, Sequence

from vultron.demo.helpers.seeding.actors import _own_actor
from vultron.demo.utils import (
    DataLayerClient,
    case_actor_id_on,
    demo_check,
    demo_step,
    seed_actor,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor

logger = logging.getLogger(__name__)


def reset_containers(
    labeled_clients: Sequence[tuple[str, DataLayerClient]],
    reset_fn: Callable[..., object],
    case_actor_client: DataLayerClient | None = None,
) -> None:
    """Reset a set of labeled containers to a clean baseline.

    This generic helper iterates over *labeled_clients*, calling *reset_fn*
    on each, then verifies that no ``VulnerabilityCase`` records remain.
    When *case_actor_client* is given, the dedicated case-actor container is
    reset with the others and its CaseActor identity is then re-seeded
    (:func:`seed_case_actor_identity`).

    Keeping the reset loop here (rather than in a scenario module) allows any
    multi-container scenario to reuse it without importing from
    ``rv_demo``.  Callers are responsible for supplying the concrete
    ``reset_fn`` (typically ``reset_datalayer`` from their own module namespace
    so that test-suite mock patches continue to intercept the call).

    Args:
        labeled_clients: Sequence of ``(label, client)`` pairs, one per
            container.  *label* is used only in log and assertion messages.
        reset_fn: Callable invoked as ``reset_fn(client=<DataLayerClient>)``.
            Its return value is only logged, so the annotation is
            ``Callable[..., object]`` rather than ``Any``: the ellipsis is what
            admits the keyword call, and ``object`` says the result is never
            inspected (CS-11-001).
            Pass the module-local reference so test patches take effect.
        case_actor_client: Client for the dedicated case-actor container, bound
            to its CaseActor (:func:`~vultron.demo.utils.case_actor_id_on`).
            Every actor container proposes its cases to that CaseActor
            (CP-08-008, DEMOMA-06-004), so a run cannot start until the identity
            exists again.

    Raises:
        AssertionError: If any container still has ``VulnerabilityCase``
            records after the reset.

    Spec: D5-2, DEMOMA-01-003.
    """
    targets = list(labeled_clients)
    if case_actor_client is not None:
        targets.append(("CaseActor", case_actor_client))

    label = client = None
    with demo_step("Resetting actor containers to a clean baseline"):
        for label, client in targets:
            result = reset_fn(client=client)
            logger.debug("%s reset result: %s", label, result)

    with demo_check("All actor containers start with no persisted cases"):
        for label, client in targets:
            for actor_id in _actors_to_verify(label, client):
                cases = client.get(
                    client.dl_path("VulnerabilityCases/", actor_id=actor_id)
                )
                if cases:
                    raise AssertionError(
                        f"{label} container was not reset cleanly"
                        f" (actor {actor_id}): {cases}"
                    )

    if case_actor_client is not None:
        with demo_step("Re-seeding the dedicated case-actor identity"):
            seed_case_actor_identity(case_actor_client)


def seed_case_actor_identity(case_actor_client: DataLayerClient) -> as_Actor:
    """Re-create the dedicated case-actor container's CaseActor identity.

    Every actor container proposes its cases to
    ``http://case-actor:7999/api/v2/actors/case-actor`` (CP-08-008), and the
    inbox route answers 404 for an actor its node does not host (ADR-0073). The
    reset in :func:`reset_containers` clears every record on the node,
    including that identity, and no demo container seeds itself on startup, so
    without this every ``Create(CaseProposal)`` delivery 404s and the case never
    opens. Matches ``docker/seed-configs/seed-case-actor.yaml``.

    The identity is constant — one CaseActor serving every case (#1872) — so it
    is seeded before any report exists.

    Args:
        case_actor_client: Client connected to the dedicated case-actor
            container.

    Returns:
        The seeded (or pre-existing) CaseActor ``as_Actor``; ``POST /actors/``
        is idempotent.
    """
    actor = _own_actor(
        case_actor_client,
        seed_actor(
            client=case_actor_client,
            name="CaseActor",
            actor_type="Service",
            actor_id=case_actor_id_on(case_actor_client.base_url),
        ),
    )
    logger.info("CaseActor identity seeded: %s", actor.id_)
    return actor


def _actors_to_verify(label: str, client: DataLayerClient) -> list[str]:
    """Return the actor ids whose stores must be empty after a reset.

    A DataLayer read names an actor under ADR-0073, so "are there any cases?"
    cannot be asked of a node — only of an actor.  A client bound to an actor
    answers for that actor.

    An *unbound* client used to skip the check entirely, which is exactly the
    case a first run hits: the reset had just cleared every store on the node and
    nothing verified that it worked, so a container that failed to reset started
    the scenario dirty and the failure surfaced later as an unexplained
    pre-existing case.  The node itself knows which actors it hosts, so ask it
    (``/info``) instead of skipping.  An empty list is a legitimate answer on a
    first run — the node hosts nothing yet — and not a silent skip.
    """
    if client.actor_id:
        return [client.actor_id]
    hosted = client.get("/info").get("actors") or []
    logger.debug(
        "%s container not bound to an actor; verifying the %d actor(s) it"
        " reports hosting",
        label,
        len(hosted),
    )
    return list(hosted)
