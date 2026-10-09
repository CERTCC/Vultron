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

"""The received-side RM anomaly rule (RSH-06-003, RSH-06-006).

One function, :func:`rm_anomaly`, judges whether a received RM declaration is
anomalous, logs it, and returns the record the RSH-06-004 note emitter reads.
Both the ``Add(ParticipantStatus)`` filter and the activity-typed RM handlers
call it, so the two paths cannot drift apart.  It sits in its own leaf module
because both of its callers' modules import each other's neighbours.
"""

import logging
from typing import Literal, TypedDict

from vultron.core.states.rm import (
    RM,
    RMDeclaration,
    classify_rm_declaration,
)


class RMAnomaly(TypedDict):
    """The RSH-06 anomaly record published on ``BB_RM_ANOMALY``.

    Read by
    :class:`~vultron.core.behaviors.status.nodes.rm_anomaly.EmitRMGapNoteNode`
    to compose the RSH-06-005 note fields.
    """

    anomaly_type: Literal["gap", "regression"]
    from_rm: RM
    to_rm: RM


def rm_anomaly(
    current: RM,
    declared: RM,
    *,
    sender_actor_id: str,
    log: logging.Logger | logging.LoggerAdapter,
    node_name: str,
) -> RMAnomaly | None:
    """Return the RSH-06 anomaly record for an RM declaration, or ``None``.

    The single place a received-side RM declaration is judged anomalous, shared
    by the ``Add(ParticipantStatus)`` filter and the activity-typed RM handlers
    so the two cannot drift (RSH-06-006).  A non-adjacent forward move is a
    ``gap`` and a refused move a ``regression``; each is logged at WARNING
    naming the sender, the state before and after, and the anomaly type
    (RSH-06-003).  A confirmation — the declared state is the recorded one, a
    restated ``CLOSED`` included — is not an anomaly (RSH-08-002).

    The returned dict is what
    :class:`~vultron.core.behaviors.status.nodes.rm_anomaly.EmitRMGapNoteNode`
    reads from ``BB_RM_ANOMALY`` to post the RSH-06-004 clarification note
    (:class:`RMAnomaly`).
    """
    verdict = classify_rm_declaration(current, declared)
    anomaly_type: Literal["gap", "regression"]
    if verdict is RMDeclaration.GAP:
        anomaly_type = "gap"
        outcome = "accepting the sender-authoritative state (RSH-06-001)"
    elif verdict is RMDeclaration.REGRESSION:
        anomaly_type = "regression"
        outcome = "refusing it and keeping the recorded state (RSH-06-002)"
    else:
        return None
    log.warning(
        "%s: RM %s declared by '%s': %s → %s; %s",
        node_name,
        anomaly_type,
        sender_actor_id,
        current,
        declared,
        outcome,
    )
    return RMAnomaly(
        anomaly_type=anomaly_type, from_rm=current, to_rm=declared
    )
