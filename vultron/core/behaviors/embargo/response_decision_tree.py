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

"""Inbound embargo-response decision seam (EMB-15).

Factory function :func:`create_embargo_response_decision_tree` builds a
three-arm response Selector that chooses *how* to respond to an inbound
embargo overture, then delegates to the appropriate mechanical BT.

Two overture flows are supported via caller-supplied delegate trees:

- **Flow A** — EM-level embargo proposal (EP).  The caller passes the
  result of :func:`~vultron.core.behaviors.embargo.trigger_tree.accept_embargo_trigger_bt`
  as ``accept_bt``,
  :func:`~vultron.core.behaviors.embargo.trigger_tree.reject_embargo_trigger_bt`
  as ``reject_bt``, and optionally
  :func:`~vultron.core.behaviors.embargo.trigger_tree.propose_embargo_trigger_bt`
  as ``counter_bt`` (counter = re-propose, no new mechanism, EMB-15-003).

- **Flow B** — PEC-level invitation
  (Invite(EmbargoEvent)[context=VulnerabilityCase]), answered by the invitee
  (EP-09-003, EP-09-025).  The caller passes a
  :class:`~vultron.core.behaviors.embargo.nodes.invite_answer.SendEmbargoInviteAnswerNode`
  with ``accept=True`` as ``accept_bt`` and one with ``accept=False`` as
  ``reject_bt``; each queues the answer to the CASE_MANAGER.  No counter arm;
  pass ``counter_bt=None`` (the default).  ``invite_to_embargo_on_case_tree``
  is the caller.

The deciding actor's answer is its own: no arm asks another actor to
approve it (EMB-15-013, BT-18-014).  A non-owner invitee's answer records
only its own consent row (CM-18, ADR-0122), so the Case Owner has nothing to
approve, and ``EvaluateEmbargoProposal`` alone decides it.

Tree structure (EMB-15)::

    ResponseDecisionSelector (Selector)
    ├─ AcceptArm (Sequence)
    │  ├─ EvaluateEmbargoProposal      # call-out; default SUCCESS (EMB-15-001)
    │  └─ <accept_bt>                  # caller-supplied accept delegate
    ├─ CounterArm (Sequence) — Flow A only, omitted when counter_bt is None
    │  ├─ WillingToCounterEmbargoProposal  # call-out; default FAILURE (EMB-15-003)
    │  └─ <counter_bt>                 # caller-supplied propose delegate
    └─ <reject_bt>                     # EMB-15-004: always present as fallback

Spec: ``specs/em-behavior.yaml`` EMB-15.
Per: ``docs/adr/0025-call-out-point-abstraction-layer.md`` (call-out injection).
"""

import logging

import py_trees

__all__ = ["create_embargo_response_decision_tree"]

from vultron.core.behaviors.call_out.bundles.embargo import (
    EMBARGO_DETERMINISTIC,
    EmbargoCallOutBundle,
)

logger = logging.getLogger(__name__)


def create_embargo_response_decision_tree(
    *,
    case_id: str,
    deciding_actor_id: str,
    accept_bt: py_trees.behaviour.Behaviour,
    reject_bt: py_trees.behaviour.Behaviour,
    counter_bt: py_trees.behaviour.Behaviour | None = None,
    call_out: EmbargoCallOutBundle = EMBARGO_DETERMINISTIC,
) -> py_trees.behaviour.Behaviour:
    """Build the inbound embargo-response decision seam (EMB-15).

    Constructs a three-arm ``ResponseDecisionSelector`` that chooses how to
    respond to an inbound embargo overture (Flow A: EP; Flow B:
    InviteToEmbargoOnCase) and delegates to the caller-supplied mechanical BTs.

    **No approval gate (EMB-15-013)**: the deciding actor's answer is its
    own, so the accept arm asks no other actor to approve it — whether or
    not that actor holds ``CVDRole.CASE_OWNER``.

    **Default-accept (EMB-15-001)**: ``EvaluateEmbargoProposal`` defaults to
    SUCCESS under :data:`EMBARGO_DETERMINISTIC`, so the accept arm is taken
    when no external adjudication backend is injected.

    **Counter arm (EMB-15-003, Flow A only)**: present when ``counter_bt`` is
    supplied.  Gated by ``WillingToCounterEmbargoProposal`` (default FAILURE),
    which is off-by-default.  Counter is implemented as re-propose — the caller
    supplies a ``propose_embargo_trigger_bt`` result.

    **Reject arm (EMB-15-004)**: the third child of the outer Selector, always
    present.  The caller supplies the flow-appropriate reject BT
    (``reject_embargo_trigger_bt`` for Flow A; ``SendEmbargoInviteAnswerNode``
    with ``accept=False`` for Flow B).

    .. note::
        This tree does **not** enforce EMB-01-002 (mandatory rejection when
        CS is public/exploit/attacks).  Callers MUST check EMB-01-002 before
        invoking this tree and route directly to the flow-appropriate
        ``reject_bt`` (or skip the tree entirely) when that condition holds.

    Args:
        case_id: ID of the VulnerabilityCase; logged as the tree's context.
        deciding_actor_id: Actor ID of the LOCAL actor that is processing the
            inbound overture and making the accept/counter/reject decision;
            logged as the tree's context.
        accept_bt: Pre-built BT to execute when the accept arm is taken.
            For Flow A: ``accept_embargo_trigger_bt(...)``.
            For Flow B: ``SendEmbargoInviteAnswerNode(..., accept=True)``.
        reject_bt: Pre-built BT to execute when the reject arm is taken.
            For Flow A: ``reject_embargo_trigger_bt(...)``.
            For Flow B: ``SendEmbargoInviteAnswerNode(..., accept=False)``.
        counter_bt: Pre-built BT to execute when the counter arm is taken.
            Supply ``propose_embargo_trigger_bt(...)`` for Flow A.
            Pass ``None`` (the default) for Flow B — omits the counter arm.
        call_out: Call-out backend bundle.  Defaults to
            :data:`EMBARGO_DETERMINISTIC` (accept by default, no counter).

    Returns:
        Root node of the ``ResponseDecisionSelector`` Selector.
    """
    # EMB-15-001: default-accept arm
    accept_arm = py_trees.composites.Sequence(
        name="AcceptArm",
        memory=False,
        children=[
            call_out.evaluate_embargo_proposal_factory(
                "EvaluateEmbargoProposal"
            ),
            accept_bt,
        ],
    )

    outer_children: list[py_trees.behaviour.Behaviour] = [accept_arm]

    # EMB-15-003: counter arm (Flow A only, off by default)
    if counter_bt is not None:
        counter_arm = py_trees.composites.Sequence(
            name="CounterArm",
            memory=False,
            children=[
                call_out.willing_to_counter_factory(
                    "WillingToCounterEmbargoProposal"
                ),
                counter_bt,
            ],
        )
        outer_children.append(counter_arm)

    # EMB-15-004: reject arm (always present as fallback)
    outer_children.append(reject_bt)

    logger.info(
        "Created ResponseDecisionSelector for case=%s deciding_actor=%s counter=%s",
        case_id,
        deciding_actor_id,
        "present" if counter_bt is not None else "absent",
    )

    return py_trees.composites.Selector(
        name="ResponseDecisionSelector",
        memory=False,
        children=outer_children,
    )
