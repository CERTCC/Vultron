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

"""Run a received tree once, as the receiver, and read its verdict (ADR-0195).

A received use case builds its one tree (CLP-10-005) and hands it to
:func:`run_received_tree`.  The runner wires the bridge and the ports, runs
the tree once as the receiving actor (BT-17-005, BT-17-009), and reads the
``HandlerResult`` from what the tree's nodes recorded
(:func:`~vultron.core.behaviors.case.received_run.reading.read_outcome`).
Nothing in it reads or writes the DataLayer around the run: a verdict that
needs a fact the tree did not record needs a node, not code here.
"""

import logging
from typing import TYPE_CHECKING, Any

import py_trees

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.received_run.reading import (
    OutcomeReader,
    ReceivedOutcome,
    read_outcome,
)
from vultron.core.models.events.base import VultronEvent
from vultron.core.models.refusal_wording import with_refusal_group
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.receiving_actor import resolve_receiving_actor_id

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

logger = logging.getLogger(__name__)


def run_received_tree(
    tree: py_trees.behaviour.Behaviour,
    *,
    dl: CasePersistence,
    request: VultronEvent,
    label: str,
    trigger_activity: TriggerActivityPort | None = None,
    sync_port: SyncActivityPort | None = None,
    wire_render_port: WireRenderPort | None = None,
    reader: OutcomeReader | None = None,
    judges: bool = True,
    **context: Any,
) -> HandlerResult:
    """Run *tree* once as the receiver of *request* and return its verdict.

    Args:
        tree: The received tree the use case built.
        dl: The receiving actor's store.
        request: The received event; placed on the blackboard as
            ``/activity``.
        label: Names the handler's step in a reason, e.g. ``"EngageCaseBT"``.
        trigger_activity: Port for building outbound activities.
        sync_port: Port for ledger replication fan-out.
        wire_render_port: Port for rendering core objects to wire shape.
        reader: The handler's own reading of the finished run, asked after
            the doors (see ``read_outcome``).  It receives only the run.
        judges: ``False`` for a tree that only stores or commits what the
            handler accepted; a failure no door, reader or declared repeat
            answers then raises.
        **context: Further blackboard keys for the run.

    Raises:
        VultronValidationError: No receiving actor can be resolved.
        VultronBTInternalError: The run failed on an internal error.
    """
    receiving_actor_id = resolve_receiving_actor_id(
        dl, request.receiving_actor_id
    )
    result = BTBridge(
        datalayer=dl,
        trigger_activity=trigger_activity,
        sync_port=sync_port,
        wire_render_port=wire_render_port,
    ).execute_with_setup(
        tree=tree,
        actor_id=receiving_actor_id,
        activity=request,
        **context,
    )
    verdict = read_outcome(
        ReceivedOutcome.of(tree, result, label), reader=reader, judges=judges
    )
    # A REFUSED HandlerResult always carries its reason (validated at
    # construction), so the second test only narrows the type.
    if (
        verdict.disposition is HandlerDisposition.REFUSED
        and verdict.reason is not None
    ):
        _log_refusal(label, request, receiving_actor_id, verdict.reason)
    return verdict


def _log_refusal(
    label: str, request: VultronEvent, receiving_actor_id: str, reason: str
) -> None:
    """Log the delivery's one ``REFUSED`` line, with the reason reported.

    The runner is the only writer of this line: it alone knows the verdict,
    so a node whose FAILURE a later arm overrules, or a skip the reading
    reports ``SKIPPED``, can never be mistaken for a refusal (SL-03-002).
    The reason is logged as the handler reports it, given the HP-01-003
    group when it carries none, so every refused delivery has exactly one
    record a reader greps and the demo matchers key on (SL-03-003).
    """
    logger.warning(
        "%s refused activity '%s' from '%s' at '%s': %s",
        label,
        request.activity_id,
        request.actor_id,
        receiving_actor_id,
        with_refusal_group(reason),
    )


__all__ = ["run_received_tree"]
