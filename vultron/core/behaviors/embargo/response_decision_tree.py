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

- **Flow B** — PEC-level invitation (InviteToEmbargoOnCase).  The caller
  passes the result of
  :func:`~vultron.core.behaviors.embargo.announce_teardown_tree.accept_invite_to_embargo_tree`
  as ``accept_bt`` and
  :func:`~vultron.core.behaviors.embargo.announce_teardown_tree.reject_invite_to_embargo_tree`
  as ``reject_bt``.  No counter arm; pass ``counter_bt=None`` (the default).

Tree structure (EMB-15, ADR-0046)::

    ResponseDecisionSelector (Selector)
    ├─ AcceptArm (Sequence)
    │  ├─ AuthorizeSelector (Selector)
    │  │  ├─ CheckIsCaseOwner          # EMB-15-002: gospel bypass
    │  │  └─ CaseOwnerApprovesEmbargoResponse  # call-out; default SUCCESS
    │  ├─ EvaluateEmbargoProposal      # call-out; default SUCCESS (EMB-15-001)
    │  └─ <accept_bt>                  # caller-supplied accept delegate
    ├─ CounterArm (Sequence) — Flow A only, omitted when counter_bt is None
    │  ├─ WillingToCounterEmbargoProposal  # call-out; default FAILURE (EMB-15-003)
    │  └─ <counter_bt>                 # caller-supplied propose delegate
    └─ <reject_bt>                     # EMB-15-004: always present as fallback

Spec: ``specs/em-behavior.yaml`` EMB-15 through EMB-15-004.
Per: ``docs/adr/0025-call-out-point-abstraction-layer.md`` (call-out injection),
     ``docs/adr/0046-received-status-authorization.md`` (two-seam authorization).
"""

import logging

import py_trees

__all__ = ["create_embargo_response_decision_tree"]

from vultron.core.behaviors.call_out.bundles.embargo import (
    EMBARGO_DETERMINISTIC,
    EmbargoCallOutBundle,
)
from vultron.core.behaviors.case.nodes.vfd_role_guards import (
    CheckIsCaseOwnerNode,
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

    **Authorization (EMB-15-002)**: a ``AuthorizeSelector`` (Fallback) puts
    ``CheckIsCaseOwnerNode`` first — when the **deciding** actor (the local
    actor processing the inbound overture and choosing how to respond) holds
    ``CVDRole.CASE_OWNER``, the response is gospel and no approval call-out
    is invoked.  Non-owners route through
    ``CaseOwnerApprovesEmbargoResponse`` (default SUCCESS).

    **Default-accept (EMB-15-001)**: ``EvaluateEmbargoProposal`` defaults to
    SUCCESS under :data:`EMBARGO_DETERMINISTIC`, so the accept arm is taken
    when no external adjudication backend is injected.

    **Counter arm (EMB-15-003, Flow A only)**: present when ``counter_bt`` is
    supplied.  Gated by ``WillingToCounterEmbargoProposal`` (default FAILURE),
    which is off-by-default.  Counter is implemented as re-propose — the caller
    supplies a ``propose_embargo_trigger_bt`` result.

    **Reject arm (EMB-15-004)**: the third child of the outer Selector, always
    present.  The caller supplies the flow-appropriate reject BT
    (``reject_embargo_trigger_bt`` for Flow A; ``reject_invite_to_embargo_tree``
    for Flow B).

    .. note::
        This tree does **not** enforce EMB-01-002 (mandatory rejection when
        CS is public/exploit/attacks).  Callers MUST check EMB-01-002 before
        invoking this tree and route directly to the flow-appropriate
        ``reject_bt`` (or skip the tree entirely) when that condition holds.

    Args:
        case_id: ID of the VulnerabilityCase.  Used to resolve CASE_OWNER
            status for the gospel-bypass guard.
        deciding_actor_id: Actor ID of the LOCAL actor that is processing the
            inbound overture and making the accept/counter/reject decision.
            Passed to ``CheckIsCaseOwnerNode`` — gospel bypass fires when THIS
            actor holds ``CVDRole.CASE_OWNER``, not when the remote proposer does.
        accept_bt: Pre-built BT to execute when the accept arm is taken.
            For Flow A: ``accept_embargo_trigger_bt(...)``.
            For Flow B: ``accept_invite_to_embargo_tree(...)``.
        reject_bt: Pre-built BT to execute when the reject arm is taken.
            For Flow A: ``reject_embargo_trigger_bt(...)``.
            For Flow B: ``reject_invite_to_embargo_tree(...)``.
        counter_bt: Pre-built BT to execute when the counter arm is taken.
            Supply ``propose_embargo_trigger_bt(...)`` for Flow A.
            Pass ``None`` (the default) for Flow B — omits the counter arm.
        call_out: Call-out backend bundle.  Defaults to
            :data:`EMBARGO_DETERMINISTIC` (accept by default, no counter).

    Returns:
        Root node of the ``ResponseDecisionSelector`` Selector.
    """
    # EMB-15-002: CASE_OWNER gospel bypass → non-owner adjudication call-out
    authorize_selector = py_trees.composites.Selector(
        name="AuthorizeSelector",
        memory=False,
        children=[
            CheckIsCaseOwnerNode(
                sender_actor_id=deciding_actor_id,
                case_id=case_id,
                name="CheckIsCaseOwner",
            ),
            call_out.case_owner_approves_embargo_response_factory(
                "CaseOwnerApprovesEmbargoResponse"
            ),
        ],
    )

    # EMB-15-001: default-accept arm
    accept_arm = py_trees.composites.Sequence(
        name="AcceptArm",
        memory=False,
        children=[
            authorize_selector,
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
