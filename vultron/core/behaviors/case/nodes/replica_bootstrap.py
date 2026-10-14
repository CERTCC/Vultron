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
from collections.abc import Collection
from dataclasses import dataclass
from typing import Any, Literal

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    _EmitSingleActivityBase,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.participants.recipients import (
    reporter_introduction_recipients,
)
from vultron.core.services.case_replica_seeding import (
    find_any_pending_report_case_link,
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
        report_ids: Collection[str] = (),
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.route = route
        self.sender_id = sender_id
        self.case_id = case_id
        self.report_ids = tuple(report_ids)

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        link = find_pending_report_case_link(
            self.datalayer, self.sender_id, self.report_ids
        )
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


class CheckReportReferenceNode(py_trees.behaviour.Behaviour):
    """Trusted route: the case must name the report the link was written for.

    CBT-01-005: the bootstrap is trusted only when it references the report
    the receiver sent (or, at a Case Owner, proposed).  The sender named in
    the link is not enough on its own: it may hold a case for another report.
    """

    def __init__(
        self,
        route: BootstrapRoute,
        report_ids: Collection[str],
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.route = route
        self.report_ids = tuple(report_ids)
        self.case_id = case_id

    def update(self) -> Status:
        link = self.route.link
        if link is None:
            self.feedback_message = "no pending ReportCaseLink to check"
            return Status.FAILURE
        if link.report_id in self.report_ids:
            return Status.SUCCESS
        self.feedback_message = (
            f"bootstrap of case '{self.case_id}' rejected: it does not"
            f" reference the submitted report '{link.report_id}'"
            " (CBT-01-005)"
        )
        logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


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

    ADR-0132 moves the reporter's bootstrap to the report receiver, so a
    receiver that holds a pending ``ReportCaseLink`` has an anchor of its own
    naming the actor it expects; any other sender is refused here, whatever
    the snapshot says (CBT-01-011).  #4472 deletes the route.
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
        anchor = find_any_pending_report_case_link(self.datalayer)
        if anchor is not None:
            # The receiver wrote down whom it expects its bootstrap from, and
            # it is not this sender: a snapshot naming the sender CASE_MANAGER
            # cannot outrank that anchor (CBT-01-011, ADR-0132).
            self.feedback_message = (
                f"untrusted Create of case '{self.case_id}': the bootstrap is"
                f" expected from '{anchor.case_creator_id}', not"
                f" '{self.sender_id}'; a snapshot naming its sender"
                " CASE_MANAGER does not make it trusted (CBT-01-011)"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
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


class SeedCaseReplicaNode(DataLayerActionWithPorts, StateWriteCapable):
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


class IntroduceCaseManagerToReporterNode(_EmitSingleActivityBase):
    """Trusted route: the report receiver introduces the CASE_MANAGER.

    After the report receiver (the Case Owner) accepts the CASE_MANAGER's
    ``Create(VulnerabilityCase)``, it sends the reporter a
    ``Create(VulnerabilityCase)`` as itself (CBT-01-001, CM-12-003, ADR-0132).
    The reporter trusts it because it comes from the actor the reporter sent
    its report to (CBT-01-005); the snapshot names the CASE_MANAGER, so the
    reporter then records it (CBT-01-006).  The factory carries the stored
    case with its participants, reports and active embargo inline
    (CBT-01-007), which relays the completed snapshot (CBT-01-009).

    Sends nothing, and returns ``SUCCESS``, when:

    - the executing actor is not the case's owner: it is the reporter, or
      another participant, receiving an introduction, not making one;
    - the executing actor is itself the CASE_MANAGER: its own ``Create`` is
      the reporter's only one (CBT-02-001, CM-02-010);
    - the snapshot names no CASE_MANAGER, so there is nobody to introduce;
    - no active reporter is on the roster (CM-10-004);
    - this actor already sent a ``Create`` for the case.

    Recipients come from the shared selection
    (:func:`~vultron.core.participants.recipients.reporter_introduction_recipients`,
    CM-10-007), never from the roster directly.
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self._recipients: list[str] = []

    def _already_introduced(self) -> bool:
        assert self.datalayer is not None
        return any(
            getattr(obj, "type_", None) == "Create"
            and _as_id(getattr(obj, "actor", None)) == self.actor_id
            and _as_id(getattr(obj, "object_", None)) == self.case_id
            for obj in self.datalayer.list_objects("Create")
        )

    def _skip_reason(self, case: VulnerabilityCase) -> str | None:
        """Why no introduction is owed, or ``None`` when one is."""
        assert self.datalayer is not None
        assert self.actor_id is not None
        if _as_id(case.attributed_to) != self.actor_id:
            return "this actor is not the case owner"
        manager_id = resolve_case_manager_id(case, self.datalayer)
        if manager_id is None:
            self.logger.warning(
                "%s: case '%s' names no CASE_MANAGER; the reporter cannot be"
                " introduced to one (CBT-01-001)",
                self.name,
                self.case_id,
            )
            return "the case names no CASE_MANAGER"
        if manager_id == self.actor_id:
            return "this actor is the CASE_MANAGER (CBT-02-001)"
        if self._already_introduced():
            return "the reporter was already introduced"
        self._recipients = reporter_introduction_recipients(
            case, self.datalayer, excluding={self.actor_id, manager_id}
        )
        if not self._recipients:
            return "no active reporter to introduce (CM-10-004)"
        return None

    def _call_factory(self) -> tuple[str, str]:
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        return self.trigger_activity_factory.create_case(
            case_id=self.case_id, actor=self.actor_id, to=self._recipients
        )

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        self.logger.info(
            "%s: introduced case '%s' and its CASE_MANAGER to %s with"
            " Create(VulnerabilityCase) '%s' (CBT-01-001, ADR-0132)",
            self.name,
            self.case_id,
            self._recipients,
            activity_id,
        )

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        self._recipients = []
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure
        reason = self._skip_reason(case)
        if reason is not None:
            self.logger.debug(
                "%s: no introduction for case '%s': %s",
                self.name,
                self.case_id,
                reason,
            )
            return Status.SUCCESS
        return super().update()


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
