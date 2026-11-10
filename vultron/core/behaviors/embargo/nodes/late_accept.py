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
:func:`late_accept_terms` names the terms a re-invite carries (EMB-17-003),
so the route and the re-invite read them the same way.
"""

from datetime import datetime
from enum import StrEnum

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.embargo.nodes.em_state import read_case_em_state
from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.behaviors.node_logger import node_logger
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_termination import has_reached_end_time
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.embargo_ordering import (
    earliest_ending,
    read_embargo_event,
)
from vultron.core.states.em import EM
from vultron.errors import VultronNotAnEmbargoError, VultronNotFoundError


class LateAcceptRoute(StrEnum):
    """How the CASE_MANAGER answers a late embargo ``Accept`` (EMB-17-001).

    - ``HONOUR`` — the case can still answer the accepted embargo: it is the
      Active Embargo or an open proposal, and the participant's row moves to
      ``AGREED`` (EMB-17-002, MSM-07-003).
    - ``REINVITE`` — the case cannot answer the accepted embargo, but holds
      terms of its own: the accepter is invited to them (EMB-17-003).
    - ``UNBOUND`` — the case holds no terms (EM ``EXITED`` or ``NONE``, or
      only proposals whose embargo has already ended): the Accept changes
      nothing, and nothing is recorded or sent (EMB-17-004).
    """

    HONOUR = "honour"
    REINVITE = "reinvite"
    UNBOUND = "unbound"


#: The EM states in which a case holds an embargo or a proposal of one.
_HOLDS_EMBARGO = frozenset({EM.PROPOSED, EM.ACTIVE, EM.REVISE})


def late_accept_route(
    em_state: EM, *, answerable: bool, has_terms: bool
) -> LateAcceptRoute:
    """The EMB-17 arm for a late Accept (EMB-17-001, EMB-17-012).

    Args:
        em_state: The case's EM state.
        answerable: The case can still answer the accepted embargo
            (:meth:`~vultron.core.models.case.VulnerabilityCase.can_answer_embargo`).
        has_terms: The case holds terms a re-invite can name
            (:func:`late_accept_terms` is not ``None``).
    """
    if em_state in _HOLDS_EMBARGO and answerable:
        return LateAcceptRoute.HONOUR
    if em_state in _HOLDS_EMBARGO and has_terms:
        return LateAcceptRoute.REINVITE
    return LateAcceptRoute.UNBOUND


def late_accept_terms(
    store: CasePersistence, case: VulnerabilityCase, now: datetime
) -> str | None:
    """The embargo a late accepter is re-invited to, or ``None`` (EMB-17-003).

    The case's Active Embargo; with none, its earliest-expiring open
    proposal among those whose embargo has not ended at *now*, chosen by the
    shared comparator (EP-08-002).  A proposal past its end time stays
    ``PROPOSED`` in the register until something closes it, but an Invite to
    it could carry no RSVP deadline the protocol allows (EP-07-002,
    EP-07-006), so it is no terms to invite to.  ``None`` when the case holds
    neither: there is nothing to invite to (EMB-17-004).

    Raises:
        RuntimeError: An open proposal does not resolve in *store* to an
            ``EmbargoEvent``.  The CASE_MANAGER holds its own case, so that
            is a fault in its own store, never the sender's (Regime 1,
            ADR-0087; EMB-18-003), and it is raised as the internal error it
            is.
    """
    if case.active_embargo_id is not None:
        return case.active_embargo_id
    try:
        proposals = [
            read_embargo_event(store, embargo_id)
            for embargo_id in case.proposed_embargo_ids
        ]
    except (VultronNotFoundError, VultronNotAnEmbargoError) as exc:
        raise RuntimeError(
            f"case '{case.id_}' names an open proposal its CASE_MANAGER's"
            f" store cannot read: {exc}"
        ) from exc
    live = [
        embargo
        for embargo in proposals
        if not has_reached_end_time(embargo.end_time, now)
    ]
    if not live:
        return None
    return earliest_ending(live, end=lambda e: e.end_time).id_


class LateAcceptRouteIsNode(DataLayerConditionWithPorts):
    """Condition: a late Accept of *embargo_id* takes the *route* arm.

    Reads the case's EM state through
    :func:`~vultron.core.behaviors.embargo.nodes.em_state.read_case_em_state`
    (AC-1, #1474), whether the case can still answer *embargo_id*
    (:meth:`~vultron.core.models.case.VulnerabilityCase.can_answer_embargo`,
    the test the Accept tree's ``IsAnswerableEmbargoNode`` makes) and the
    terms a re-invite would name at the act's instant
    (:func:`late_accept_terms`), when the node runs, after the Invite expiry
    has been recorded.  SUCCESS when
    :func:`late_accept_route` names *route*, logged at INFO; FAILURE
    otherwise.  Read-only.  A case or an open proposal the CASE_MANAGER
    cannot read raises an internal error: it holds its own case (Regime 1,
    ADR-0087), and a guess here would route the Accept to the wrong arm.
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        accepting_actor_id: str,
        route: LateAcceptRoute,
        *,
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
        answerable = case.can_answer_embargo(self._embargo_id)
        # The terms matter only to an Accept the case cannot answer.
        has_terms = (
            not answerable
            and late_accept_terms(
                self.datalayer, case, self._require_act_instant()
            )
            is not None
        )
        route = late_accept_route(
            em_state, answerable=answerable, has_terms=has_terms
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
    still bind (EM ``EXITED`` or ``NONE``, or only proposals whose embargo
    has already ended), so the Accept changes nothing at
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
    "late_accept_terms",
]
