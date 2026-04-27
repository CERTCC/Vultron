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

"""BT nodes and factory for the SuggestActorToCase received use-case.

When a case owner receives a ``RecommendActorActivity`` (Offer) from a peer,
the local actor:

1. Verifies it is the case owner (precondition; silently skips otherwise).
2. Checks no invite for this actor+case already exists (idempotency guard).
3. Emits an ``AcceptActorRecommendationActivity`` to the recommender's outbox.
4. Emits an ``RmInviteToCaseActivity`` to the suggested actor's outbox.

Per specs/case-management.yaml CM-08 and specs/behavior-tree-integration.yaml.
"""

import logging
import uuid

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction, DataLayerCondition
from vultron.core.models.protocols import is_case_model
from vultron.core.use_cases._helpers import _as_id
from vultron.wire.as2.vocab.activities.actor import (
    AcceptActorRecommendationActivity,
    RecommendActorActivity,
)
from vultron.wire.as2.vocab.activities.case import RmInviteToCaseActivity
from vultron.wire.as2.vocab.base.objects.actors import as_Actor

logger = logging.getLogger(__name__)

_NAMESPACE = uuid.NAMESPACE_URL


def _deterministic_invite_id(
    case_id: str, invitee_id: str, actor_id: str
) -> str:
    """Return a stable invite ID for the (case, invitee, actor) triple.

    Using UUID v5 so the same inputs always produce the same ID, which
    lets the DataLayer reject a duplicate with ``ValueError`` on the second
    ``create()`` call and lets ``CheckNoExistingInviteNode`` detect the
    duplicate with a simple ``read()``.
    """
    name = f"{case_id}|invite|{invitee_id}|{actor_id}"
    return f"urn:uuid:{uuid.uuid5(_NAMESPACE, name)}"


def _deterministic_accept_id(recommendation_id: str, actor_id: str) -> str:
    """Return a stable accept ID for the (recommendation, actor) pair."""
    name = f"{recommendation_id}|accept|{actor_id}"
    return f"urn:uuid:{uuid.uuid5(_NAMESPACE, name)}"


class CheckIsCaseOwnerNode(DataLayerCondition):
    """Return SUCCESS when the current actor owns the case; FAILURE otherwise.

    Reads the case from the DataLayer and compares ``case.attributed_to``
    against ``actor_id`` from the blackboard.  If the local actor is not the
    owner the node returns FAILURE, which causes the parent Sequence to abort
    without executing downstream nodes (silent skip per CM-08 precondition).
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or "CheckIsCaseOwner")
        self.case_id = case_id

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            return Status.FAILURE
        case = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            self.logger.warning(
                "%s: case '%s' not found in DataLayer",
                self.name,
                self.case_id,
            )
            return Status.FAILURE
        owner_id = _as_id(case.attributed_to)
        if owner_id != self.actor_id:
            self.logger.info(
                "%s: local actor '%s' is not owner of case '%s' (owner: '%s')"
                " — skipping suggest-actor handling",
                self.name,
                self.actor_id,
                self.case_id,
                owner_id,
            )
            return Status.FAILURE
        return Status.SUCCESS


class CheckNoExistingInviteNode(DataLayerCondition):
    """Return SUCCESS when no invite for (invitee, case) already exists.

    Uses a deterministic invite ID so a DataLayer ``read()`` is sufficient
    to detect the duplicate.  Returns FAILURE (idempotent skip) if an invite
    is already present.
    """

    def __init__(
        self, invitee_id: str, case_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or "CheckNoExistingInvite")
        self.invitee_id = invitee_id
        self.case_id = case_id

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            return Status.FAILURE
        invite_id = _deterministic_invite_id(
            self.case_id, self.invitee_id, self.actor_id
        )
        if self.datalayer.read(invite_id) is not None:
            self.logger.info(
                "%s: invite for actor '%s' in case '%s' already exists"
                " — skipping (idempotent)",
                self.name,
                self.invitee_id,
                self.case_id,
            )
            return Status.FAILURE
        return Status.SUCCESS


class EmitAcceptRecommendationNode(DataLayerAction):
    """Create and queue an ``AcceptActorRecommendationActivity`` to the outbox.

    Reconstructs the original ``RecommendActorActivity`` from the
    constructor args (the activity was already persisted by the use case
    before the BT ran).  Derives a stable activity ID so a second execution
    of the node is idempotent.
    """

    def __init__(
        self,
        recommendation_id: str,
        recommender_id: str,
        invitee_id: str,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or "EmitAcceptRecommendation")
        self.recommendation_id = recommendation_id
        self.recommender_id = recommender_id
        self.invitee_id = invitee_id
        self.case_id = case_id

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            return Status.FAILURE

        recommendation = RecommendActorActivity(
            id_=self.recommendation_id,
            actor=self.recommender_id,
            object_=as_Actor(id_=self.invitee_id),
            target=self.case_id,
        )
        accept_id = _deterministic_accept_id(
            self.recommendation_id, self.actor_id
        )
        accept = AcceptActorRecommendationActivity(
            id_=accept_id,
            actor=self.actor_id,
            object_=recommendation,
            target=self.case_id,
            to=[self.recommender_id],
        )
        try:
            self.datalayer.create(accept)
        except ValueError:
            pass  # idempotent — accept already stored
        self.datalayer.outbox_append(accept.id_)
        self.logger.info(
            "%s: queued AcceptActorRecommendation '%s' to outbox for actor '%s'",
            self.name,
            accept.id_,
            self.actor_id,
        )
        return Status.SUCCESS


class EmitInviteToCaseNode(DataLayerAction):
    """Create and queue an ``RmInviteToCaseActivity`` to the outbox.

    Uses the same deterministic ID as ``CheckNoExistingInviteNode`` so that
    creating the invite a second time is rejected by the DataLayer and the
    already-queued outbox entry is reused (fully idempotent).
    """

    def __init__(
        self,
        invitee_id: str,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or "EmitInviteToCase")
        self.invitee_id = invitee_id
        self.case_id = case_id

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            return Status.FAILURE

        invite_id = _deterministic_invite_id(
            self.case_id, self.invitee_id, self.actor_id
        )
        invite = RmInviteToCaseActivity(
            id_=invite_id,
            actor=self.actor_id,
            object_=as_Actor(id_=self.invitee_id),
            target=self.case_id,
            to=[self.invitee_id],
        )
        try:
            self.datalayer.create(invite)
        except ValueError:
            pass  # idempotent — invite already stored
        self.datalayer.outbox_append(invite.id_)
        self.logger.info(
            "%s: queued RmInviteToCase '%s' to outbox for actor '%s'",
            self.name,
            invite.id_,
            self.actor_id,
        )
        return Status.SUCCESS


def create_suggest_actor_tree(
    recommendation_id: str,
    recommender_id: str,
    invitee_id: str,
    case_id: str,
) -> py_trees.composites.Sequence:
    """Return the BT for handling an inbound ``RecommendActorActivity``.

    The returned Sequence:

    1. ``CheckIsCaseOwnerNode``        — precondition: abort if not owner
    2. ``CheckNoExistingInviteNode``   — idempotency: abort if invite exists
    3. ``EmitAcceptRecommendationNode`` — queue Accept to outbox
    4. ``EmitInviteToCaseNode``        — queue Invite to outbox

    Args:
        recommendation_id: ID of the incoming ``RecommendActorActivity``.
        recommender_id: Actor ID of the peer who sent the recommendation.
        invitee_id: Actor ID of the suggested participant.
        case_id: ID of the VulnerabilityCase being referenced.

    Returns:
        Configured ``py_trees.composites.Sequence`` ready for execution via
        :class:`~vultron.core.behaviors.bridge.BTBridge`.
    """
    return py_trees.composites.Sequence(
        name="SuggestActorToCaseBT",
        memory=True,
        children=[
            CheckIsCaseOwnerNode(case_id=case_id),
            CheckNoExistingInviteNode(invitee_id=invitee_id, case_id=case_id),
            EmitAcceptRecommendationNode(
                recommendation_id=recommendation_id,
                recommender_id=recommender_id,
                invitee_id=invitee_id,
                case_id=case_id,
            ),
            EmitInviteToCaseNode(invitee_id=invitee_id, case_id=case_id),
        ],
    )


# Expose node classes for testing and external use
__all__ = [
    "CheckIsCaseOwnerNode",
    "CheckNoExistingInviteNode",
    "EmitAcceptRecommendationNode",
    "EmitInviteToCaseNode",
    "create_suggest_actor_tree",
]
