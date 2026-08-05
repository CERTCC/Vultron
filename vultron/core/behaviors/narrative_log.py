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

"""Narrative INFO log helpers for protocol state transitions (SL-04-006).

Every protocol-visible state change SHOULD emit exactly one INFO line
following the narrative template so that reading an actor's INFO log tells
the complete CVD protocol story without dropping to DEBUG:

.. code-block:: text

    Actor '<actor_id>' <verb> '<object_id>' (<STATE_A> → <STATE_B>)

The helpers here own that formatting so call sites cannot drift from the
template (CS-22-001).  See ``notes/structured-logging.md`` for the full verb
inventory and ``specs/structured-logging.yaml`` SL-04-001, SL-04-006.
"""

import logging

from vultron.core.states.cs import CS_pxa, CS_vfd
from vultron.core.states.em import EM
from vultron.core.states.rm import RM

#: Human-readable CS event labels keyed by the sub-dimension that flipped.
#:
#: Each entry maps ``(field_name, new_value)`` to the CVD event name for the
#: transition.  Values are the single-character state codes used by the
#: ``CS_vfd`` / ``CS_pxa`` named tuples.
_CS_EVENT_LABELS: dict[tuple[str, str], str] = {
    ("vendor_awareness", "V"): "vendor aware",
    ("fix_readiness", "F"): "fix ready",
    ("fix_deployment", "D"): "fix deployed",
    ("public_awareness", "P"): "publicly known",
    ("exploit_publication", "X"): "exploit public",
    ("attack_observation", "A"): "attacks observed",
}


#: Label used when a CS write moves *backward* (an event being un-done).
#:
#: CS events are monotonic by protocol definition, so this indicates a bug or
#: a state-sync override rather than a normal transition.
REGRESSION_LABEL = "state regression"

#: Label used when before == after (no sub-dimension moved).
NO_CHANGE_LABEL = "no change"


def cs_event_label(
    before: CS_vfd | CS_pxa,
    after: CS_vfd | CS_pxa,
) -> str:
    """Return the CVD event name(s) for a CS dimension transition.

    Compares the sub-dimension fields of *before* and *after* and names each
    one that advanced (e.g. ``Vfd`` → ``VFd`` is ``"fix ready"``).

    Returns:
        A comma-joined list of event labels; :data:`NO_CHANGE_LABEL` when the
        two states are equal; :data:`REGRESSION_LABEL` when a sub-dimension
        moved *backward* (CS events are monotonic, so this signals a bug or a
        state-sync override — never a normal transition).

    Raises:
        TypeError: If *before* and *after* are different CS dimensions (e.g. a
            ``CS_vfd`` compared against a ``CS_pxa``); their sub-dimension
            fields are not comparable.
    """
    if type(before) is not type(after):
        raise TypeError(
            "cs_event_label() requires both states from the same CS"
            f" dimension; got {type(before).__name__} and"
            f" {type(after).__name__}"
        )
    if before == after:
        return NO_CHANGE_LABEL

    labels: list[str] = []
    for field, new_value in zip(after.value._fields, after.value, strict=True):
        if getattr(before.value, field) == new_value:
            continue
        label = _CS_EVENT_LABELS.get((field, str(new_value)))
        if label is None:
            # The field changed but the *new* value is not an event-triggering
            # (uppercase) code — i.e. the dimension moved backward.
            return REGRESSION_LABEL
        labels.append(label)
    return ", ".join(labels)


def log_cs_transition(
    logger: logging.Logger,
    actor_id: str,
    case_id: str,
    before: CS_vfd | CS_pxa,
    after: CS_vfd | CS_pxa,
) -> None:
    """Log a CS (VFD or PXA) transition at INFO per SL-04-006.

    Emits nothing when *before* equals *after*: a no-op write is not a
    protocol event and would only add noise (SL-04-007).

    A *backward* move is logged at WARNING rather than INFO: CS events are
    monotonic by protocol definition, so a regression is an anomaly to
    investigate, not a milestone in the case narrative.

    Args:
        logger: Logger to emit on (usually the BT node's ``self.logger``).
        actor_id: Actor whose CS dimension changed.
        case_id: Case the transition applies to.
        before: CS state before the transition.
        after: CS state after the transition.
    """
    if before == after:
        return
    label = cs_event_label(before, after)
    level = logging.WARNING if label == REGRESSION_LABEL else logging.INFO
    logger.log(
        level,
        "Actor '%s' CS: %s → %s (%s) for case '%s'",
        actor_id,
        before.name,
        after.name,
        label,
        case_id,
    )


def log_rm_transition(
    logger: logging.Logger,
    actor_id: str,
    case_id: str,
    before: RM,
    after: RM,
) -> None:
    """Log a per-participant RM transition at INFO per SL-04-006.

    Emits nothing when *before* equals *after*: re-asserting the current RM
    state is bookkeeping, not a transition (SL-04-007).

    Args:
        logger: Logger to emit on.
        actor_id: Actor whose RM state changed.
        case_id: Case the transition applies to.
        before: RM state before the transition.
        after: RM state after the transition.
    """
    if before == after:
        return
    logger.info(
        "Actor '%s' RM: %s → %s for case '%s'",
        actor_id,
        before,
        after,
        case_id,
    )


def log_em_transition(
    logger: logging.Logger,
    actor_id: str,
    case_id: str,
    before: EM,
    after: EM,
) -> None:
    """Log an embargo (EM) lifecycle transition at INFO per SL-04-006.

    Emits nothing when *before* equals *after*.

    Args:
        logger: Logger to emit on.
        actor_id: Actor that caused the transition.
        case_id: Case the embargo belongs to.
        before: EM state before the transition.
        after: EM state after the transition.
    """
    if before == after:
        return
    logger.info(
        "Actor '%s' embargo %s → %s for case '%s'",
        actor_id,
        before,
        after,
        case_id,
    )


def log_case_engagement(
    logger: logging.Logger,
    actor_id: str,
    case_id: str,
    rm_before: RM,
    rm_after: RM,
) -> None:
    """Log a case engagement at INFO per SL-04-006.

    Emits nothing when *rm_before* equals *rm_after*: re-engaging a case the
    actor already engaged is an idempotent no-op, and claiming
    ``RM ACCEPTED → ACCEPTED`` would assert an engagement that did not happen
    (SL-04-007).

    Args:
        logger: Logger to emit on.
        actor_id: Actor that engaged the case.
        case_id: Case engaged.
        rm_before: Actor's RM state before engaging.
        rm_after: Actor's RM state after engaging, read back from storage.
    """
    if rm_before == rm_after:
        return
    logger.info(
        "Actor '%s' engaged case '%s' (RM %s → %s)",
        actor_id,
        case_id,
        rm_before,
        rm_after,
    )


def log_invite_received(
    logger: logging.Logger,
    actor_id: str,
    case_id: str,
    sender_id: str,
) -> None:
    """Log receipt of a case invitation at INFO per SL-04-006.

    Args:
        logger: Logger to emit on.
        actor_id: Actor that received the invite.
        case_id: Case the invite refers to.
        sender_id: Actor that sent the invite.
    """
    logger.info(
        "Actor '%s' received case invite for '%s' from '%s'",
        actor_id,
        case_id,
        sender_id,
    )


# NOTE: BT-execution failures are *not* logged from here.  AC-18 asked for a
# reason alongside the bare ``BT execution completed: Status.FAILURE`` line, and
# ``BTBridge.execute_tree`` folds ``get_failure_reason()`` into that existing
# record instead.  A second dedicated line would double-log, would fire for the
# many callers that treat FAILURE as an expected idempotent skip (and log their
# own explanation at DEBUG), and had no reliable ``case_id`` to report: no
# production ``execute_with_setup`` call site passes one.
