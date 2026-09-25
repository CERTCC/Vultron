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

"""Initial-embargo eligibility and duration nodes for case creation.

The first two steps of ``InitializeDefaultEmbargoNode``: decide whether a
case may receive an embargo at all (EP-04-008), then resolve the duration it
is created with (EP-04-005 through EP-04-007, EP-04-010).  The remaining leaf
nodes live in the sibling ``embargo.py``.

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
from vultron.core.models.embargo_policy import EmbargoPolicy
from vultron.core.models.enums import VultronObjectType
from vultron.core.services.embargo_duration import (
    InitialEmbargoDuration,
    resolve_initial_embargo_duration,
    select_actor_default,
)
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.errors import VultronInvalidStateTransitionError


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
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case_id = self._try_get_input("case_id")
        if not isinstance(case_id, str):
            raise TypeError(
                f"{self.name}: case_id {case_id!r} is not a string; cannot"
                " decide embargo eligibility"
            )

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

    ``sender_proposed_embargo_duration`` is the seam for EP-04-004's embedded
    sender proposal; nothing writes it until that mechanism lands (#3392).
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
        "sender_proposed_embargo_duration": PortInformation(
            data_type=object, required=False
        ),
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
                "sender_proposed_embargo_duration",
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
        if sender_proposal is not None and not isinstance(
            sender_proposal, timedelta
        ):
            self.feedback_message = (
                f"sender_proposed_embargo_duration {sender_proposal!r}"
                " is not a timedelta"
            )
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        policies = [
            p
            for p in self.datalayer.list_objects(
                VultronObjectType.EMBARGO_POLICY
            )
            if isinstance(p, EmbargoPolicy)
        ]
        actor_default = select_actor_default(policies)
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
