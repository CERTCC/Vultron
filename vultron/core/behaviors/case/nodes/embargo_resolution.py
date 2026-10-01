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

"""Initial-embargo guard, eligibility and duration nodes for case creation.

The first steps of ``InitializeDefaultEmbargoNode``: recognise a case whose
creation-time embargo already exists so a repeated proposal initializes
nothing twice, decide whether a case may receive an embargo at all
(EP-04-008), then resolve the duration it is created with (EP-04-005 through
EP-04-007, EP-04-010).  The remaining leaf nodes live in the sibling
``embargo.py``.

Per specs/embargo-policy.yaml EP-04 and ADR-0096.
"""

from datetime import timedelta

from py_trees.common import Status

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.actor import CoreActor
from vultron.core.services.embargo_duration import (
    InitialEmbargoDuration,
    actor_default_duration,
    resolve_initial_embargo_duration,
)
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.errors import (
    BtNodePreconditionError,
    VultronInvalidStateTransitionError,
)


def _refusal_arm_case_id(
    node: DataLayerConditionWithPorts, purpose: str
) -> str:
    """Return the ``case_id`` a refusal arm decides on, or raise.

    Shared by the guard arms of ``InitializeDefaultEmbargoNode``.  A missing
    store or an unusable ``case_id`` *raises* rather than returning FAILURE:
    in a Selector, FAILURE would run the creation arm, which persists an
    ``EmbargoEvent`` before anything re-checks (``notes/bt-pitfalls.md``
    § "A Refusal Arm in a Selector Fails Toward 'Admit'").
    """
    if node.datalayer is None:
        raise BtNodePreconditionError(
            f"{node.name}: DataLayer not available; cannot {purpose}"
        )
    case_id = node._try_get_input("case_id")
    if not isinstance(case_id, str):
        raise TypeError(
            f"{node.name}: case_id {case_id!r} is not a string; cannot"
            f" {purpose}"
        )
    return case_id


class CaseEmbargoAlreadyInitializedNode(DataLayerConditionWithPorts):
    """SUCCESS when the case already carries an active embargo — nothing to do.

    The idempotency arm of ``InitializeDefaultEmbargoNode``.  Creation-time
    initialization runs once, when the case is created; a later
    ``Create(CaseProposal)`` for the same report reuses the case (CP-05-006)
    and must not run it again.  Without this arm the creation arm re-ran on
    the existing case: the default path minted and stored a second, orphan
    ``EmbargoEvent``, and the contested path registered the losing candidate
    as a *second* pending revision (EP-04-003) — one revision per delivery of
    the same report (#3393).

    "Initialized" is read as "an active embargo is attached", the same
    evidence ``AdvanceEMStateToActiveNode`` and ``AttachEmbargoToCaseNode``
    read to skip their own step; it is a question about the case's embargo
    reference, not about the EM state machine, so no ``ReadEmStateNode`` is
    involved.  A case at ``EM.NONE`` after refusal (EP-04-008) has no active
    embargo and falls through to the eligibility arm, which refuses it again.

    Like every guard ahead of a write in a Selector, a missing case or store
    *raises*: returning FAILURE would run the creation arm against a case
    that cannot be read (``notes/bt-pitfalls.md`` § "A Refusal Arm in a
    Selector Fails Toward 'Admit'").
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id"}

    def update(self) -> Status:
        case_id = _refusal_arm_case_id(
            self, "tell whether the case already has an embargo"
        )
        # Regime 1 resolution through the shared helper (ADR-0087) for the
        # canonical log line; the FAILURE it hands back is then *raised*, not
        # returned, because this arm sits ahead of the creation arm's writes.
        case, failure = self._require_case(case_id)
        if failure is not None:
            raise BtNodePreconditionError(
                f"{self.name}: case '{case_id}' is not in this store; the"
                " creation-time embargo cannot be initialized for a case"
                " that cannot be read"
            )
        active_id = case.active_embargo_id
        if active_id is None:
            return Status.FAILURE
        self.logger.info(
            "Case '%s' already carries active embargo '%s'; creation-time"
            " initialization is not repeated",
            case_id,
            active_id,
        )
        return Status.SUCCESS


class CaseNotEmbargoEligibleNode(DataLayerConditionWithPorts):
    """SUCCESS when P/X/A is set on the case, so no embargo is created.

    The refusal arm of ``InitializeDefaultEmbargoNode`` (EP-04-008).  An
    eligible case is FAILURE, which runs the creation arm.

    Any other error — the case missing or the store unreadable — is raised,
    not returned as FAILURE: in a Selector, FAILURE would run the creation
    arm, which persists an ``EmbargoEvent`` before anything re-checks P/X/A.
    ``BTBridge`` turns the escaped exception into whole-tree FAILURE, the only
    outcome that neither creates an embargo nor silently skips one
    (``notes/bt-pitfalls.md`` § "A Refusal Arm in a Selector Fails Toward
    'Admit'").
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id"}

    def update(self) -> Status:
        case_id = _refusal_arm_case_id(self, "decide embargo eligibility")
        assert self.datalayer is not None  # narrowed by the helper's raise

        lifecycle = EmbargoLifecycle(persistence=self.datalayer)
        try:
            lifecycle.assert_embargo_eligible(
                case_id=case_id, operation="initialize default embargo"
            )
        except VultronInvalidStateTransitionError as exc:
            self.logger.info(
                "No embargo created for case '%s'; case remains EM.NONE"
                " (EP-04-008): %s",
                case_id,
                exc,
            )
            return Status.SUCCESS
        return Status.FAILURE


class ResolveEmbargoDurationNode(DataLayerActionWithPorts):
    """Resolve the initial embargo duration and publish it to the blackboard.

    Publishes the actor default and the protocol default under distinct keys
    (EP-04-010), and the resolved ``InitialEmbargoDuration`` — duration plus
    source — for ``CreateEmbargoEventNode``.

    The actor default comes only from ``owner_profile``: the case owner's
    actor profile, which the proposer sent inline on ``Create(CaseProposal)``
    (CP-01-010).  The CASE_MANAGER cannot read the owner's own store
    (PCR-01-003), and an owner record or policy that happens to sit in this
    store is never read: it may be left over from another proposal, and the
    profile on *this* proposal is the only statement of the owner's terms for
    this case.  A profile with no policy means the owner has no actor default.
    A missing profile, or one naming an actor other than the case owner
    (``attributed_to``), fails the node: the use case seeds the profile the
    parse edge checked, so either is a wiring fault, not a peer's.

    ``sender_proposed_embargo_duration`` is EP-04-004's sender proposal: the
    case-proposal use case derives it from the ``EmbargoEvent`` the Reporter
    embedded on the report Offer (carried on the proposal, CP-01-008) and
    seeds it on the blackboard alongside ``sender_proposed_embargo`` (#3392).
    """

    def __init__(
        self,
        actor_config: ActorConfig | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._actor_config = actor_config or ActorConfig()

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=True),
        "sender_proposed_embargo_duration": PortInformation(
            data_type=object, required=False
        ),
        "owner_profile": PortInformation(data_type=object, required=True),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "actor_default_embargo_duration": PortInformation(
            data_type=object, required=True
        ),
        "protocol_default_embargo_duration": PortInformation(
            data_type=timedelta, required=True
        ),
        "initial_embargo_duration": PortInformation(
            data_type=InitialEmbargoDuration, required=True
        ),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            key: f"/{key}"
            for key in (
                "case_id",
                "sender_proposed_embargo_duration",
                "owner_profile",
                "actor_default_embargo_duration",
                "protocol_default_embargo_duration",
                "initial_embargo_duration",
            )
        }

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        sender_proposal = self._try_get_input(
            "sender_proposed_embargo_duration"
        )
        if sender_proposal is not None and (
            not isinstance(sender_proposal, timedelta)
            or sender_proposal <= timedelta(0)
        ):
            self.feedback_message = (
                f"sender_proposed_embargo_duration {sender_proposal!r}"
                " is not a positive timedelta"
            )
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        case_id = self._try_get_input("case_id")
        case, failure = self._require_case(
            case_id if isinstance(case_id, str) else None
        )
        if failure is not None:
            return failure
        owner_id = _as_id(case.attributed_to)
        if owner_id is None:
            self.feedback_message = (
                f"case '{case_id}' has no owner; cannot select its actor"
                " default embargo"
            )
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        profile = self._try_get_input("owner_profile")
        if not isinstance(profile, CoreActor) or profile.id_ != owner_id:
            self.feedback_message = (
                f"no inline actor profile for case owner {owner_id!r} to read"
                f" the actor default from (got {profile!r}; CP-01-010)"
            )
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        actor_default = actor_default_duration(profile)
        protocol_default = self._actor_config.protocol_default_embargo_duration
        resolved = resolve_initial_embargo_duration(
            sender_proposal=sender_proposal,
            actor_default=actor_default,
            protocol_default=protocol_default,
        )
        self._set_output("actor_default_embargo_duration", actor_default)
        self._set_output("protocol_default_embargo_duration", protocol_default)
        self._set_output("initial_embargo_duration", resolved)
        self.logger.debug(
            "%s: initial embargo duration %s from %s",
            self.name,
            resolved.duration,
            resolved.source.value,
        )
        return Status.SUCCESS
