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

"""Read a participant's RM states for a BT node, or signal FAILURE (ARCH-15)."""

from typing import overload

import py_trees

from vultron.core.behaviors.node_logger import node_logger
from vultron.core.models.participant_status import (
    participant_status_rm_state,
)
from vultron.core.states.rm import RM
from vultron.errors import VultronValidationError


@overload
def read_rm_states(
    node: py_trees.behaviour.Behaviour,
    status: object,
    /,
) -> tuple[RM] | None: ...


@overload
def read_rm_states(
    node: py_trees.behaviour.Behaviour,
    status: object,
    other: object,
    /,
) -> tuple[RM, RM] | None: ...


def read_rm_states(
    node: py_trees.behaviour.Behaviour,
    *statuses: object,
) -> tuple[RM, ...] | None:
    """Return the RM states of *statuses*, or ``None`` to signal FAILURE.

    A ``ParticipantStatus`` whose RM dimension is unreadable is a shape
    mismatch, not an absence.  Substituting a default (``RM.START``, ``None``)
    let an invalid transition through unchecked and silently reset a
    participant's RM ladder (#2264, a symptom of #2232), so ARCH-15-001 and
    ARCH-15-002 require FAILURE instead of a degraded SUCCESS.

    Callers for whom *absence* is legitimate (e.g. a participant with no
    recorded status) must handle that case before calling.

    The one- and two-status arities are declared as ``@overload``\\ s with
    fixed-length return tuples, so a caller that unpacks the result
    (``new, current = states``) is arity-checked statically instead of raising
    ``ValueError: too many values to unpack`` at runtime — where a BT node's
    blanket handler would report it only as an opaque FAILURE.

    Args:
        node: The calling BT node.  Its ``feedback_message`` and ``logger`` are
            used to report the mismatch, and its ``participant_id`` (when
            present) identifies the participant in the message.
        *statuses: Status objects to read, in the caller's preferred order.

    Returns:
        A tuple of :class:`RM` states positionally matching *statuses*, or
        ``None`` when any status is not core-shaped.  On ``None`` the caller
        must return ``Status.FAILURE``.
    """
    try:
        return tuple(participant_status_rm_state(s) for s in statuses)
    except VultronValidationError as exc:
        participant_id = getattr(node, "participant_id", "<unknown>")
        node.feedback_message = (
            "Non-canonical ParticipantStatus shape for participant"
            f" '{participant_id}': {exc}"
        )
        log = node_logger(node)
        log.error(  # noqa: TRY400  # ruff-baseline #3353
            "%s: %s", node.name, node.feedback_message
        )
        return None
