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

"""Actor-participation emit nodes for case behavior trees.

Provides leaf action nodes that emit outbound activities for actor
invitation workflows, and for applying received ownership-transfer
decisions to the case record.

Also provides :class:`EvaluateDefaultRolesNode`, the ADR-0024 Evaluator
call-out point that assigns default roles for a suggested actor (CM-16-003).

Invite-response nodes (Accept / Reject) live in the sibling
``invite_response.py`` module and are re-exported here for backwards
compatibility (BTND-07-004: 500-line leaf-module limit).

Composite subtrees assembling these leaf nodes are defined in the sibling
``actor_trigger_trees.py`` and ``ownership_transfer_tree.py`` modules at
the process-area root per BTND-07-003:

- ``accept_case_invite_trigger_bt``
- ``reject_case_invite_trigger_bt``
- ``create_accept_ownership_transfer_tree``
"""

import logging
from typing import Any

from py_trees.common import Status
from py_trees.ports import BehaviourWithPorts, PortInformation

from vultron.core.behaviors.case.nodes.invite_actor_emit import (  # noqa: F401
    EmitInviteActorToCaseNode,
)
from vultron.core.behaviors.case.nodes.invite_response import (  # noqa: F401
    EmitAcceptCaseInviteNode,
    EmitRejectCaseInviteNode,
)
from vultron.core.behaviors.case.nodes.participant.roles import (
    suggested_roles_key,
)
from vultron.core.behaviors.node_logger import node_logger
from vultron.enums.roles import CVDRole


class EvaluateDefaultRolesNode(BehaviourWithPorts):
    """Assign default CVD roles for a suggested actor (CM-16-003).

    ADR-0024 Evaluator shape.  Writes ``suggested_roles_{id_segment}``
    (namespaced by ``recommendation_id``, BTND-03-004) to the blackboard.
    When ``injected_roles`` is provided those roles are used directly;
    otherwise falls back to ``_compute_roles()`` (default: ``[CVDRole.VENDOR]``).
    Subclasses may override ``_compute_roles()``; an empty return produces
    ``FAILURE`` (AC-1).

    The physical blackboard key is execution-scoped (BTND-03-013): the stable
    logical port name ``suggested_roles`` is declared in ``OUTPUT_PORTS`` and
    wired to the physical key ``suggested_roles_{id_segment}`` in ``setup()``
    using an instance-computed remapping.
    """

    logger: logging.Logger  # type: ignore[assignment]

    def __init__(
        self,
        suggested_actor_id: str,
        case_id: str,
        recommendation_id: str,
        injected_roles: list[str] | None = None,
        name: str | None = None,
        require_explicit_roles: bool = False,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.suggested_actor_id = suggested_actor_id
        self.case_id = case_id
        self.recommendation_id = recommendation_id
        self.logger = node_logger(self)  # type: ignore[assignment]
        self._injected_roles = self._coerce_injected_roles(injected_roles)
        self._roles_key = suggested_roles_key(recommendation_id)
        self._require_explicit_roles = require_explicit_roles

    def _coerce_injected_roles(
        self, injected_roles: list[str] | None
    ) -> list[CVDRole] | None:
        """Coerce caller-supplied role strings to ``CVDRole``, keeping valid ones.

        An unrecognized role string is dropped with a warning rather than
        discarding the whole list: falling back to the hardcoded default would
        silently substitute roles the caller did not ask for, which CM-16-003
        forbids.  ``None`` is returned only when nothing usable remains, in
        which case ``_compute_roles()`` legitimately owns the decision.
        """
        if not injected_roles:
            return None
        coerced: list[CVDRole] = []
        for raw in injected_roles:
            try:
                coerced.append(CVDRole(raw))
            except ValueError:
                self.logger.warning(
                    "%s: ignoring unrecognized injected role %r for actor"
                    " '%s' in case '%s'",
                    self.name,
                    raw,
                    self.suggested_actor_id,
                    self.case_id,
                )
        if not coerced:
            self.logger.warning(
                "%s: no injected role in %r was recognized for actor '%s';"
                " falling back to _compute_roles()",
                self.name,
                injected_roles,
                self.suggested_actor_id,
            )
            return None
        return coerced

    INPUT_PORTS: dict[str, PortInformation] = {}

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "suggested_roles": PortInformation(data_type=list, required=True),
    }

    def setup(self, **kwargs: Any) -> None:
        self.setup_ports(
            port_remappings={"suggested_roles": f"/{self._roles_key}"}
        )

    def _compute_roles(self) -> list[CVDRole]:
        """Return default roles for the suggested actor (CM-16-003).

        When ``require_explicit_roles`` is ``False`` (the default), returns
        ``[CVDRole.VENDOR]`` — the protocol default for a participant
        recommendation (CM-16-003), so the suggest-actor path works without
        the recommender specifying roles.

        When ``require_explicit_roles`` is ``True``, returns ``[]``, causing
        FAILURE so that the caller (e.g., the Case Owner's direct invite path)
        is forced to supply roles explicitly (CM-11-019).  Set this flag for
        the ``owner_direct_invite`` sub-tree; leave it unset for the
        ``fresh_path`` sub-tree that handles participant recommendations.
        """
        return [] if self._require_explicit_roles else [CVDRole.VENDOR]

    def update(self) -> Status:
        roles = (
            self._injected_roles
            if self._injected_roles
            else self._compute_roles()
        )
        if not roles:
            if self._require_explicit_roles and not self._injected_roles:
                self.feedback_message = (
                    f"{self.name}: no roles specified for actor"
                    f" '{self.suggested_actor_id}'"
                    f" — inviter must give the invitee's roles (CM-11-019)"
                )
            else:
                self.feedback_message = (
                    f"{self.name}: _compute_roles() returned an empty list"
                    f" for actor '{self.suggested_actor_id}'"
                    f" — cannot assign roles"
                )
            self.logger.error("%s", self.feedback_message)
            return Status.FAILURE
        self._set_output("suggested_roles", roles)
        self.logger.debug(
            "%s: assigned roles %s for actor '%s' in case '%s'",
            self.name,
            roles,
            self.suggested_actor_id,
            self.case_id,
        )
        return Status.SUCCESS
