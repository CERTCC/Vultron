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

"""The CASE_MANAGER's routing of a late embargo Accept (EMB-17).

An ``Accept(Invite(EmbargoEvent))`` the Invite expiry found late is not an
answer (EMB-17-001).  The CASE_MANAGER routes it by its compatibility with the
case's embargo, one arm per outcome, each a diversion of the Accept tree
(CLP-10-026): :class:`LateAcceptRouteIsNode` names the arm, and
:class:`LateAcceptChangesNothingNode` is the answer when the case holds no
embargo for the Accept to bind: nothing is recorded or sent (EMB-17-004).
"""

from enum import StrEnum

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.embargo.nodes.em_state import read_case_em_state
from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.behaviors.node_logger import node_logger
from vultron.core.states.em import EM


class LateAcceptRoute(StrEnum):
    """How the CASE_MANAGER answers a late embargo ``Accept`` (EMB-17-001).

    - ``HONOUR`` — the accepted embargo is the case's current one: the
      participant's row moves to ``AGREED`` (EMB-17-002).
    - ``REINVITE`` — the case has a current embargo, but not the accepted
      one: the accepter is invited to it (EMB-17-003).
    - ``UNBOUND`` — the case holds no embargo (EM ``EXITED`` or
      ``NONE``): the Accept changes nothing, and nothing is recorded or
      sent (EMB-17-004).
    """

    HONOUR = "honour"
    REINVITE = "reinvite"
    UNBOUND = "unbound"


def late_accept_route(
    em_state: EM, active_embargo_id: str | None, embargo_id: str
) -> LateAcceptRoute:
    """The EMB-17 arm for a late Accept of *embargo_id* (EMB-17-001)."""
    if em_state in (EM.ACTIVE, EM.REVISE) and active_embargo_id == embargo_id:
        return LateAcceptRoute.HONOUR
    if em_state in (EM.ACTIVE, EM.REVISE, EM.PROPOSED):
        return LateAcceptRoute.REINVITE
    return LateAcceptRoute.UNBOUND


class LateAcceptRouteIsNode(DataLayerConditionWithPorts):
    """Condition: a late Accept of *embargo_id* takes the *route* arm.

    Reads the case's EM state through
    :func:`~vultron.core.behaviors.embargo.nodes.em_state.read_case_em_state`
    (AC-1, #1474) and its embargo in force when the node runs, after the
    Invite expiry has been recorded.  SUCCESS when
    :func:`late_accept_route` names *route*, logged at INFO; FAILURE
    otherwise.  Read-only.  A case the CASE_MANAGER cannot
    read raises: it holds its own case (Regime 1, ADR-0087), and a guess
    here would route the Accept to the wrong arm.
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        accepting_actor_id: str,
        route: LateAcceptRoute,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._embargo_id = embargo_id
        self._accepting_actor_id = accepting_actor_id
        self.route = route

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        em_state = read_case_em_state(self.datalayer, self._case_id)
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure
        route = late_accept_route(
            em_state, case.active_embargo_id, self._embargo_id
        )
        if route is not self.route:
            return Status.FAILURE
        self.feedback_message = (
            f"late Accept of embargo '{self._embargo_id}' by"
            f" '{self._accepting_actor_id}' on case '{self._case_id}'"
            f" (EM {em_state.name}): {route.value} (EMB-17-001)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class LateAcceptChangesNothingNode(py_trees.behaviour.Behaviour):
    """Answer a late Accept the case has no embargo for, by doing nothing.

    The Invite had expired and the case holds no embargo the Accept could
    still bind (EM ``EXITED`` or ``NONE``), so the Accept changes nothing at
    the CASE_MANAGER or at any replica: no ledger entry is committed, nothing
    is sent and no consent row moves (EMB-17-004, ADR-0152).  Anything that
    holds the case and its ledger can see that the Accept named an embargo
    the case no longer holds, so the CASE_MANAGER records no observation of
    it (CLP-02-013).  A redelivery takes the same arm and gets the same
    result, whether or not it carries its received body, because nothing is
    built from it.

    Always SUCCESS; the no-op is logged at INFO.
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        accepting_actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._embargo_id = embargo_id
        self._accepting_actor_id = accepting_actor_id

    def update(self) -> Status:
        self.feedback_message = (
            f"late Accept of embargo '{self._embargo_id}' by"
            f" '{self._accepting_actor_id}' on case '{self._case_id}': the"
            " case holds no embargo for it to bind, so nothing is recorded"
            " or sent (EMB-17-004)"
        )
        node_logger(self).info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


__all__ = [
    "LateAcceptChangesNothingNode",
    "LateAcceptRoute",
    "LateAcceptRouteIsNode",
    "late_accept_route",
]
