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

"""Payload-snapshot extraction for :class:`CommitCaseLedgerEntryNode`.

Split out of ``lifecycle.py`` (#3930) to keep that leaf under the BTND-07-004
line cap.  The snapshot is the ``WireRenderPort`` rendering of the received
activity (ARCH-20-001, CLP-07-009).
"""

from typing import TYPE_CHECKING, Any, cast

from vultron.core.models.base import CoreObject
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.use_cases._helpers import build_activity_payload_snapshot
from vultron.errors import VultronWiringError

if TYPE_CHECKING:
    from vultron.core.ports.wire_render import WireRenderPort


def _extract_payload_snapshot(
    activity: Any,
    dl: CasePersistence | None,
    wire_render_port: "WireRenderPort",
) -> dict[str, Any]:
    """Build a normalized payload snapshot for case-ledger commits.

    The AS2 shape comes from *wire_render_port* (ARCH-20-001, CLP-07-009).
    """
    event_activity = getattr(activity, "activity", None)
    if event_activity is not None:
        return cast(
            dict[str, Any],
            build_activity_payload_snapshot(
                event_activity, dl, wire_render_port=wire_render_port
            ),
        )
    if hasattr(activity, "model_dump") and not isinstance(
        activity, CoreObject
    ):
        # An event with no activity has nothing AS2-shaped to record: the port
        # would refuse it (ARCH-20-003), and a received handler would then
        # blame the sender.  The tree was composed without its input, so say
        # so as the composition fault it is (ARCH-15-001, ADR-0095).
        raise VultronWiringError(
            f"{type(activity).__name__} carries no activity, so there is"
            " nothing to record as the ledger payload snapshot (ARCH-15-001)"
        )
    snapshot = cast(
        dict[str, Any],
        build_activity_payload_snapshot(
            activity, dl, wire_render_port=wire_render_port
        ),
    )
    # Domain events serialize actor_id, not the wire-format actor URI.
    # Patch it in so the ledger schema's non-empty-URI check passes.
    if not snapshot.get("actor"):
        actor_id = getattr(activity, "actor_id", None)
        if actor_id:
            snapshot = dict(snapshot)
            snapshot["actor"] = actor_id
    return snapshot
