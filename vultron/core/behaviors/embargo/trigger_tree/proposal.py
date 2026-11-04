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

"""Trigger trees that propose an embargo or a revision of one.

The CASE_MANAGER's own proposal takes the shape of one it receives
(EP-09-001, EP-09-002); any other participant asks the manager.
"""

import py_trees

from vultron.core.behaviors.embargo.nodes import (
    EMBARGO_INVITE_SEMANTIC_TYPE,
    CollectEmbargoInviteRecipientsNode,
    CommitEmbargoProposalNode,
    EmbargoActivityBuilder,
    IndexOwnEmbargoProposalNode,
    PersistEmbargoEventNode,
    ProposeEmbargoLifecycleNode,
    RelayEmbargoInviteToEachNode,
    ValidateEmbargoProposalStateNode,
    ValidateEmbargoRevisionStateNode,
)
from vultron.core.behaviors.embargo.trigger_tree._arms import (
    _asserting,
    _by_role,
    _make_emit_node,
)
from vultron.core.behaviors.sender.nodes import (
    ConstructActivitiesNode,
    QueueToOutboxNode,
    ResolveCaseManagerNode,
)
from vultron.core.models.embargo_event import EmbargoEvent


def _propose_arms(
    name: str,
    case_id: str,
    actor_id: str,
    embargo: EmbargoEvent,
    result_out: dict[str, object],
    activity_builder: EmbargoActivityBuilder,
) -> list[py_trees.behaviour.Behaviour]:
    """Manager: adjudicate and relay its own terms; otherwise: ask.

    The CASE_MANAGER's own proposal takes the shape of one it receives
    (EP-09-001, EP-09-002): collect the invitees before deciding
    (BT-19-001), decide ``STRICT`` on a staged store, commit the proposal —
    the ``Invite(EmbargoEvent)`` whose entry is the ``PROPOSE`` step —
    then one ``Create(EmbargoConsent)`` per participant's new row (the
    proposer's ``AGREED``, every other one ``UNINVITED``), apply them by
    copying (ADR-0124, CLP-07-013), relay one ``Invite`` per participant,
    and only then index the proposal the manager will answer (ID-04-005).
    The factory renders the stored ``EmbargoEvent``, the object and not case
    state (EP-09-003): in the manager arm ``CommitEmbargoProposalNode``
    stores it as it builds the proposal and takes it back out when the
    proposal does not commit; in the other arm ``PersistEmbargoEventNode``
    runs after the CASE_MANAGER is resolved.  Neither a refused or failed
    proposal nor a failed routing guard leaves an orphan record (BT-19-001).
    """
    return _by_role(
        name,
        case_id,
        as_case_manager=[
            CollectEmbargoInviteRecipientsNode(
                case_id=case_id, proposer_id=actor_id
            ),
            ProposeEmbargoLifecycleNode(
                case_id=case_id,
                embargo_id=embargo.id_,
                result_out=result_out,
                embargo=embargo,
            ).deciding(),
            CommitEmbargoProposalNode(
                case_id=case_id,
                semantic_type=EMBARGO_INVITE_SEMANTIC_TYPE,
                builder=activity_builder,
                embargo=embargo,
                result_out=result_out,
            ),
            _make_emit_node(case_id),
            RelayEmbargoInviteToEachNode(
                case_id=case_id,
                embargo_id=embargo.id_,
                proposer_id=actor_id,
                # The manager's own proposal is the request each relayed
                # Invite answers.  An Invite whose commit fails is rolled
                # back with the proposal itself: the arm is one act
                # (ADR-0146).
                answers=embargo.id_,
            ),
            IndexOwnEmbargoProposalNode(
                case_id=case_id,
                embargo_id=embargo.id_,
                result_out=result_out,
            ),
        ],
        otherwise=[
            ResolveCaseManagerNode(case_id=case_id),
            PersistEmbargoEventNode(embargo=embargo),
            ConstructActivitiesNode(
                activity_builder=_asserting(activity_builder, result_out)
            ),
            QueueToOutboxNode(),
        ],
    )


def propose_embargo_trigger_bt(
    *,
    case_id: str,
    actor_id: str,
    embargo: EmbargoEvent,
    result_out: dict[str, object],
    activity_builder: EmbargoActivityBuilder,
) -> py_trees.behaviour.Behaviour:
    """Build trigger-side BT for proposing an embargo (EP-09-008).

    ``ValidateEmbargoProposalStateNode`` refuses an ``EXITED`` case before
    either arm runs, so a participant that is not the CASE_MANAGER fails
    fast rather than asking for a proposal the manager will not take.
    """
    return py_trees.composites.Sequence(
        name="ProposeEmbargoTriggerBT",
        memory=False,
        children=[
            ValidateEmbargoProposalStateNode(
                case_id=case_id, result_out=result_out
            ),
            *_propose_arms(
                "ProposeEmbargo",
                case_id,
                actor_id,
                embargo,
                result_out,
                activity_builder,
            ),
        ],
    )


def propose_embargo_revision_trigger_bt(
    *,
    case_id: str,
    actor_id: str,
    embargo: EmbargoEvent,
    result_out: dict[str, object],
    activity_builder: EmbargoActivityBuilder,
) -> py_trees.behaviour.Behaviour:
    """Build trigger-side BT for proposing an embargo revision.

    Differs from :func:`propose_embargo_trigger_bt` by first asserting that
    the case EM state is ACTIVE or REVISE (a revision requires an existing
    active embargo).  The role arms are otherwise identical.
    """
    return py_trees.composites.Sequence(
        name="ProposeEmbargoRevisionTriggerBT",
        memory=False,
        children=[
            ValidateEmbargoRevisionStateNode(
                case_id=case_id,
                result_out=result_out,
            ),
            *_propose_arms(
                "ProposeEmbargoRevision",
                case_id,
                actor_id,
                embargo,
                result_out,
                activity_builder,
            ),
        ],
    )
