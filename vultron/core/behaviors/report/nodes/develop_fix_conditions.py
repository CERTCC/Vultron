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
"""Fix-development guard/condition BT nodes.

Two condition nodes implement the ``DevelopFixBT`` entry guards:

- :class:`CheckIsVendorRoleNode` — short-circuit: actor is not a vendor
- :class:`CheckCSFixNotYetReady` — short-circuit: fix is already ready

These are the precondition-check complements to the action nodes in
:mod:`develop_fix`.

References
----------
- Issue: #2604 (split from ``develop_fix.py`` at BTND-07-004 size cap)
- Specs: ``specs/behavior-tree-node-design.yaml`` BTND-07-004, BTND-07-006
- Issue #1812: original implementation context
"""

import logging

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.behaviors.case.nodes.participant.common import (
    resolve_participant_state_from_dl,
)
from vultron.core.behaviors.case.nodes.vfd_role_guards import (
    _resolve_actor_roles,
)
from vultron.core.models.dimensions import VfDimension
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)


class CheckIsVendorRoleNode(DataLayerConditionWithPorts):
    """Gate: actor MUST hold CVDRole.VENDOR to proceed with fix development.

    Returns ``SUCCESS`` when the actor holds ``CVDRole.VENDOR`` — allowing
    the fix-development workflow to continue.  Returns ``FAILURE`` for any
    non-vendor actor so the Fallback short-circuits and reports SUCCESS to
    the parent (non-vendors are excused from fix development).

    Note: in the DevelopFixBT Fallback, SUCCESS here means "not a vendor,
    skip fix development". FAILURE here means "is a vendor, proceed to inner
    Sequence".  The semantics are those of a short-circuit guard:
    non-vendors succeed early; vendors fall through to the creation sequence.

    Per AC-7 (issue #1812).
    """

    def __init__(
        self,
        case_id: str,
        actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._actor_id = actor_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        roles = _resolve_actor_roles(
            self.datalayer, self._case_id, self._actor_id, self.name
        )
        if roles is None:
            self.feedback_message = (
                f"Could not resolve roles for actor '{self._actor_id}'"
                f" in case '{self._case_id}'"
            )
            return Status.FAILURE

        if CVDRole.VENDOR in roles:
            self.logger.debug(
                "%s: actor '%s' is a vendor — proceed to fix development",
                self.name,
                self._actor_id,
            )
            return Status.FAILURE

        self.logger.debug(
            "%s: actor '%s' is not a vendor — short-circuit SUCCESS",
            self.name,
            self._actor_id,
        )
        return Status.SUCCESS


class CheckCSFixNotYetReady(DataLayerConditionWithPorts):
    """Short-circuit guard: fix already ready means nothing to do.

    Returns ``SUCCESS`` when the actor's VF state is already fix-ready (VF=VF)
    (``vf_state=VF``) — the Fallback short-circuits and
    reports SUCCESS to the parent.  Returns ``FAILURE`` when fix is NOT yet
    ready, allowing the inner Sequence to proceed.

    Per AC-7 (issue #1812).
    """

    def __init__(
        self,
        case_id: str,
        actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._actor_id = actor_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case = self.datalayer.read_case(self._case_id)
        if case is None:
            self.logger.warning(
                "%s: case '%s' not found", self.name, self._case_id
            )
            return Status.FAILURE

        participant_id = case.actor_participant_index.get(self._actor_id)
        if participant_id is None:
            self.logger.warning(
                "%s: actor '%s' not in case '%s'",
                self.name,
                self._actor_id,
                self._case_id,
            )
            return Status.FAILURE

        _, vf_state, _ = resolve_participant_state_from_dl(
            self.datalayer, participant_id
        )

        is_ready = (
            vf_state is not None and VfDimension(state=vf_state).is_fix_ready()
        )
        if is_ready:
            self.logger.debug(
                "%s: VF state=%s is fix-ready — short-circuit SUCCESS",
                self.name,
                vf_state,
            )
            return Status.SUCCESS

        self.logger.debug(
            "%s: VF state=%s is not fix-ready — proceed to creation",
            self.name,
            vf_state,
        )
        return Status.FAILURE


__all__ = [
    "CheckIsVendorRoleNode",
    "CheckCSFixNotYetReady",
]
