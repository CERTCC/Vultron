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

"""The report receiver introduces the CASE_MANAGER to the reporter (ADR-0132).

The last step of the trusted route of the received
``Create(VulnerabilityCase)`` bootstrap tree
(:func:`~vultron.core.behaviors.case.create_case_received_tree.create_create_case_received_tree`).

Per specs/case-bootstrap-trust.yaml CBT-01-001, CBT-01-007, CBT-01-009 and
specs/case-management.yaml CM-12-003.
"""

from py_trees.common import Status

from vultron.core.behaviors.helpers import _EmitSingleActivityBase
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.participants.recipients import (
    reporter_introduction_recipients,
)


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
