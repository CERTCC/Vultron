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

A handler whose whole job is to record what arrived returns
:func:`run_intake_only` from ``execute()``.  The tree is
:func:`~vultron.core.behaviors.case.intake_only_received_tree.create_intake_only_received_tree`;
its docstring records why it commits nothing.  The run and its verdict are
the received-tree runner's
(:func:`~vultron.core.behaviors.case.received_run.run_received_tree`): a run
that got through its doors recorded the message, so it is ``APPLIED``.
"""

from vultron.core.behaviors.case.intake_only_received_tree import (
    create_intake_only_received_tree,
)
from vultron.core.behaviors.case.received_run import run_received_tree
from vultron.core.models.events.base import VultronEvent
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.wire_render import WireRenderPort


def run_intake_only(
    dl: CasePersistence,
    request: VultronEvent,
    *,
    name: str,
    sync_port: SyncActivityPort | None,
    wire_render_port: WireRenderPort | None,
) -> HandlerResult:
    """Build the intake-only tree *name*, run it once, and return its verdict."""
    return run_received_tree(
        create_intake_only_received_tree(name),
        dl=dl,
        request=request,
        label=name,
        sync_port=sync_port,
        wire_render_port=wire_render_port,
    )
