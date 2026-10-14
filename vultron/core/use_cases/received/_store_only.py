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

"""Run the shared intake-only tree for a received handler (#3871, CLP-10-005).

A handler whose whole job is to archive what arrived calls :func:`run_store_only`
from ``execute()`` and maps the run through
:func:`~vultron.core.use_cases.received._bt_verdict.intake_verdict`.  The tree is
:func:`~vultron.core.behaviors.case.store_only_received_tree.create_store_only_received_tree`;
its docstring records why it commits nothing.
"""

import py_trees

from vultron.core.behaviors.bridge import BTBridge, BTExecutionResult
from vultron.core.behaviors.case.store_only_received_tree import (
    create_store_only_received_tree,
)
from vultron.core.models.events.base import VultronEvent
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.use_cases._helpers import resolve_receiving_actor_id
from vultron.core.use_cases.received._bt_verdict import (
    applied_or_raise,
)


def run_store_only(
    dl: CasePersistence,
    request: VultronEvent,
    *,
    name: str,
    sync_port: SyncActivityPort | None,
    wire_render_port: WireRenderPort | None,
) -> tuple[py_trees.behaviour.Behaviour, BTExecutionResult]:
    """Build the intake-only tree and run it once as the receiving actor."""
    tree = create_store_only_received_tree(name)
    result = BTBridge(
        datalayer=dl,
        wire_render_port=wire_render_port,
        sync_port=sync_port,
    ).execute_with_setup(
        tree=tree,
        actor_id=resolve_receiving_actor_id(dl, request.receiving_actor_id),
        activity=request,
    )
    return tree, result


def refuse_after_intake(
    dl: CasePersistence,
    request: VultronEvent,
    reason: str,
    *,
    name: str,
    sync_port: SyncActivityPort | None,
    wire_render_port: WireRenderPort | None,
) -> HandlerResult:
    """Archive the activity, then refuse it.

    For a handler that turns a delivery away before it can build its real
    tree (a missing id, an untrusted sender): the refusal still leaves the
    receiver holding what arrived (CLP-10-018).  The intake-only tree writes
    nothing else.

    Raises:
        VultronBTInternalError: Intake itself failed (a local fault, not the
            sender's).
    """
    tree, result = run_store_only(
        dl,
        request,
        name=name,
        sync_port=sync_port,
        wire_render_port=wire_render_port,
    )
    verdict = applied_or_raise(tree, result, label=name)
    if verdict.disposition is HandlerDisposition.SKIPPED:
        return verdict  # leader skip: intake never ran, nothing was archived
    return HandlerResult.refused(reason)
