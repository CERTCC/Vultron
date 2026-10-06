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

"""Nodes of the received ``Create(VulnerabilityCase)`` bootstrap tree (#3874).

A ``Create(VulnerabilityCase)`` tells the receiver that *someone else* made
the case.  Whether to trust that depends on how the receiver came to expect it,
so the tree picks one of three routes (ADR-0041, CBT-01-005, CBT-01-006):

- ``trusted``: the receiver sent a report to the sender and holds a pending
  :class:`~vultron.core.models.report_case_link.VultronReportCaseLink` for it;
- ``redelivery``: a link already binds the case to the sender, so the
  bootstrap was accepted before;
- ``direct``: no link, so the sender is trusted only if the snapshot names it
  as the case's CASE_MANAGER (ADR-0041 AC-5).

:class:`ClassifyBootstrapRouteNode` makes that choice once and records it on a
shared :class:`BootstrapRoute`.  It cannot be re-derived later: the trusted
route's own write (binding the link) changes what the classifier would say.

The remaining nodes are the steps of those routes.  Each refusing node sets its
own ``feedback_message`` and returns ``FAILURE``; the embargo and participant
steps shared with the engage tree are in
:mod:`~vultron.core.behaviors.case.nodes.carried_snapshot`.

Per specs/case-bootstrap-trust.yaml CBT-01-003 through CBT-01-007, CBT-05-005.
"""

import logging
from dataclasses import dataclass
from typing import Any, Literal

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.services.case_replica_seeding import (
    find_pending_report_case_link,
    is_bootstrap_accepted,
)
from vultron.errors import VultronAlreadyExistsError

logger = logging.getLogger(__name__)

BootstrapRouteName = Literal["trusted", "redelivery", "direct"]


@dataclass
class BootstrapRoute:
    """What the classifier decided, and what the seed step then did."""

    name: BootstrapRouteName | None = None
    link: VultronReportCaseLink | None = None
    replica_stored: bool = False


class ClassifyBootstrapRouteNode(DataLayerActionWithPorts):
    """Choose the bootstrap route once, before any step of it writes.

    Always ``SUCCESS`` once the DataLayer is available: the choice is not a
    verdict.  The order is the order of trust: a pending link first, then a
    redelivery, then the direct-participant route.
    """

    def __init__(
        self,
        route: BootstrapRoute,
        sender_id: str,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.route = route
        self.sender_id = sender_id
        self.case_id = case_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        link = find_pending_report_case_link(self.datalayer, self.sender_id)
        if link is not None:
            self.route.name, self.route.link = "trusted", link
        elif is_bootstrap_accepted(
            self.datalayer, self.sender_id, self.case_id
        ):
            self.route.name = "redelivery"
        else:
            self.route.name = "direct"
        return Status.SUCCESS


class BootstrapRouteIsNode(py_trees.behaviour.Behaviour):
    """Condition: the classifier chose *expected*."""

    def __init__(
        self,
        route: BootstrapRoute,
        expected: BootstrapRouteName,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or f"BootstrapRouteIs_{expected}")
        self.route = route
        self.expected = expected

    def update(self) -> Status:
        return (
            Status.SUCCESS
            if self.route.name == self.expected
            else Status.FAILURE
        )


class CheckTrustedCreatorNode(DataLayerActionWithPorts):
    """Trusted route: the sender must be the creator the link expects.

    CBT-01-005.  A link with no recorded ``case_creator_id`` accepts
    unchecked, with a warning.
    """

    def __init__(
        self,
        route: BootstrapRoute,
        sender_id: str,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.route = route
        self.sender_id = sender_id
        self.case_id = case_id

    def update(self) -> Status:
        link = self.route.link
        if link is None:
            self.feedback_message = "no pending ReportCaseLink to check"
            return Status.FAILURE
        if link.case_creator_id is None:
            self.logger.warning(
                "%s: no case_creator_id in link for case '%s'; accepting"
                " bootstrap unchecked",
                self.name,
                self.case_id,
            )
            return Status.SUCCESS
        if self.sender_id != link.case_creator_id:
            self.feedback_message = (
                f"bootstrap of case '{self.case_id}' rejected: sender"
                f" '{self.sender_id}' is not the trusted case creator"
                " (CBT-01-005)"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        return Status.SUCCESS


class CheckInlineParticipantsNode(py_trees.behaviour.Behaviour):
    """Trusted route: every participant must be an inline typed object.

    Refuses before anything is persisted, so the bootstrap is atomic: the full
    payload is valid before any state is committed (CBT-01-007, CBT-05-008).
    """

    def __init__(
        self, case_obj: Any, case_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_obj = case_obj
        self.case_id = case_id

    def update(self) -> Status:
        participants = getattr(self.case_obj, "case_participants", []) or []
        bare = [p for p in participants if isinstance(p, str)]
        if not bare:
            return Status.SUCCESS
        self.feedback_message = (
            f"Bootstrap Create(VulnerabilityCase) for case '{self.case_id}'"
            f" contains {len(bare)} bare-URI participant reference(s);"
            f" inline typed objects required (CBT-01-007, CBT-05-008)"
        )
        logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


class CheckSenderIsSnapshotManagerNode(DataLayerActionWithPorts):
    """Direct route: the sender must be the snapshot's CASE_MANAGER.

    Under ADR-0041 AC-5 the CaseActor bootstraps reporters and finders directly
    by including them in the ``to`` of the Create.  They hold no
    ``ReportCaseLink``, so the only identity to trust is the CASE_MANAGER the
    snapshot itself names, and only if it is the sender.
    """

    def __init__(
        self,
        case_obj: Any,
        sender_id: str,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_obj = case_obj
        self.sender_id = sender_id
        self.case_id = case_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        manager_id = resolve_case_manager_id(self.case_obj, self.datalayer)
        if manager_id is not None and manager_id == self.sender_id:
            return Status.SUCCESS
        self.feedback_message = (
            f"untrusted Create of case '{self.case_id}': no ReportCaseLink and"
            f" sender '{self.sender_id}' is not its CASE_MANAGER"
            " (ADR-0041 AC-5)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


class SeedCaseReplicaNode(DataLayerActionWithPorts):
    """Persist the received case as this actor's replica, unless one exists.

    Idempotent (CBT-01-006, ID-04-004): a replica already held, or persisted
    concurrently, is left alone and ``route.replica_stored`` stays ``False``.
    Always ``SUCCESS``.
    """

    def __init__(
        self,
        route: BootstrapRoute,
        case_obj: Any,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.route = route
        self.case_obj = case_obj
        self.case_id = case_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        if self.datalayer.read(self.case_id) is not None:
            self.logger.info(
                "%s: case '%s' already exists as replica — skipping re-seed",
                self.name,
                self.case_id,
            )
            return Status.SUCCESS
        try:
            self.datalayer.create(self.case_obj)
        except VultronAlreadyExistsError:
            self.logger.info(
                "%s: case '%s' persisted concurrently — idempotent",
                self.name,
                self.case_id,
            )
            return Status.SUCCESS
        self.route.replica_stored = True
        self.logger.info(
            "%s: replica case '%s' persisted", self.name, self.case_id
        )
        return Status.SUCCESS


class BindReportCaseLinkNode(DataLayerActionWithPorts):
    """Trusted route: record the trust anchors on the link (CBT-01-006).

    Sets ``case_id`` and the CASE_MANAGER the snapshot names
    (``case_manager_id``, CBT-01-003).  A snapshot naming none is accepted, with
    a warning that Announce validation will be bypassed.  Idempotent, and
    re-applied when the replica was already seeded.
    """

    def __init__(
        self,
        route: BootstrapRoute,
        case_obj: Any,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.route = route
        self.case_obj = case_obj
        self.case_id = case_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        link = self.route.link
        if link is None:
            self.feedback_message = "no pending ReportCaseLink to bind"
            return Status.FAILURE
        manager_id = resolve_case_manager_id(self.case_obj, self.datalayer)
        if manager_id is None:
            self.logger.warning(
                "%s: no CASE_MANAGER participant in bootstrap snapshot for"
                " case '%s'; Announce validation will be bypassed",
                self.name,
                self.case_id,
            )
        link.case_id = self.case_id
        link.case_manager_id = manager_id
        self.datalayer.save(link)
        self.logger.info(
            "%s: ReportCaseLink updated with case_id='%s' and"
            " case_manager_id='%s' (CBT-01-006)",
            self.name,
            self.case_id,
            manager_id,
        )
        return Status.SUCCESS


class RefuseBootstrapNode(py_trees.behaviour.Behaviour):
    """Last child of the route Selector: carry the chosen route's refusal.

    A failed route makes the Selector move on, and every route after it fails
    at its own gate, so the failure the tree reports would be a gate's.  This
    node fails last with the reason the *chosen* route failed for, which is the
    one the sender is owed (HP-01-003).
    """

    def __init__(
        self,
        route: BootstrapRoute,
        routes: dict[BootstrapRouteName, py_trees.behaviour.Behaviour],
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.route = route
        self.routes = routes

    def update(self) -> Status:
        chosen = self.routes.get(self.route.name) if self.route.name else None
        self.feedback_message = (
            BTBridge.get_failure_reason(chosen)
            if chosen is not None
            else "no bootstrap route was chosen"
        )
        return Status.FAILURE
