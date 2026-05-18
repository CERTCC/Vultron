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

"""Actor action helpers for demo workflows.

Provides :func:`actor_notifies_state_change` as a generic trigger wrapper and
named aliases for each concrete CVD lifecycle notification, plus
:func:`actor_closes_case`.
"""

import logging

from vultron.demo.utils import (
    DataLayerClient,
    demo_step,
    post_to_trigger,
    ref_id,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor

logger = logging.getLogger(__name__)


def actor_notifies_state_change(
    client: DataLayerClient,
    actor: as_Actor,
    case_id: str,
    behavior: str,
    description: str,
) -> dict:
    """Generic wrapper: actor self-reports a CVD lifecycle state change.

    Posts to the ``demo`` trigger endpoint for *behavior* and logs a
    ``demo_step`` banner with *description*.

    Args:
        client: DataLayerClient connected to the actor's container.
        actor: The actor reporting the state change.
        case_id: Full URI of the ``VulnerabilityCase``.
        behavior: Trigger endpoint behaviour name
            (e.g. ``"notify-fix-ready"``).
        description: Human-readable description for the ``demo_step`` banner.

    Returns:
        Response dict from the trigger endpoint.
    """
    with demo_step(f"Actor {ref_id(actor)} {description}"):
        return post_to_trigger(
            client=client,
            actor_id=actor.id_,
            behavior=behavior,
            body={"case_id": case_id},
            path_prefix="demo",
        )


def actor_notifies_fix_ready(
    client: DataLayerClient,
    actor: as_Actor,
    case_id: str,
) -> dict:
    """Self-report fix ready (CS.VFd) via the demo trigger endpoint.

    Sends ``Add(ParticipantStatus(CS.VFd), target=Case)`` to the Case Manager
    so the Case Actor can update participant state and broadcast to peers.

    Args:
        client: DataLayerClient connected to the actor's container.
        actor: The actor that has a fix ready.
        case_id: Full URI of the ``VulnerabilityCase``.

    Returns:
        Response dict from the trigger endpoint.

    Spec: DEMOMA-07-001.
    """
    return actor_notifies_state_change(
        client, actor, case_id, "notify-fix-ready", "reports fix ready"
    )


def actor_notifies_fix_deployed(
    client: DataLayerClient,
    actor: as_Actor,
    case_id: str,
) -> dict:
    """Self-report fix deployed (CS.VFD) via the demo trigger endpoint.

    Args:
        client: DataLayerClient connected to the actor's container.
        actor: The actor that has deployed a fix.
        case_id: Full URI of the ``VulnerabilityCase``.

    Returns:
        Response dict from the trigger endpoint.

    Spec: DEMOMA-07-001.
    """
    return actor_notifies_state_change(
        client, actor, case_id, "notify-fix-deployed", "reports fix deployed"
    )


def actor_notifies_published(
    client: DataLayerClient,
    actor: as_Actor,
    case_id: str,
) -> dict:
    """Self-report vulnerability publicly disclosed via the demo trigger endpoint.

    When called by the CASE_OWNER (Vendor), the Case Actor automatically
    initiates embargo teardown on receipt (DEMOMA-07-003 step 4).

    Args:
        client: DataLayerClient connected to the actor's container.
        actor: The actor reporting publication.
        case_id: Full URI of the ``VulnerabilityCase``.

    Returns:
        Response dict from the trigger endpoint.

    Spec: DEMOMA-07-001.
    """
    return actor_notifies_state_change(
        client,
        actor,
        case_id,
        "notify-published",
        "reports vulnerability publicly disclosed",
    )


def actor_closes_case(
    client: DataLayerClient,
    actor: as_Actor,
    case_id: str,
) -> dict:
    """Self-report case closed (RM.CLOSED) via the demo trigger endpoint.

    When all participants report RM.CLOSED, the Case Actor automatically
    closes the case (DEMOMA-07-003 step 5).

    Args:
        client: DataLayerClient connected to the actor's container.
        actor: The actor closing the case.
        case_id: Full URI of the ``VulnerabilityCase``.

    Returns:
        Response dict from the trigger endpoint.

    Spec: DEMOMA-07-001.
    """
    with demo_step(f"Actor {ref_id(actor)} closes case"):
        return post_to_trigger(
            client=client,
            actor_id=actor.id_,
            behavior="close-case",
            body={"case_id": case_id},
            path_prefix="demo",
        )
