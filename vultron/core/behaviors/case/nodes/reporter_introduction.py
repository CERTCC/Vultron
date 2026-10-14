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

from vultron.core.behaviors.helpers import (
    _EmitSingleActivityBase,
    resolve_case_replica,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.participants.recipients import (
    reporter_introduction_recipients,
)
from vultron.core.services.case_replica_seeding import (
    find_case_create_sent_by,
)
from vultron.errors import VultronError


class IntroduceCaseManagerToReporterNode(_EmitSingleActivityBase):
    """The report receiver introduces the CASE_MANAGER to the reporter.

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
    - no active reporter is on the roster (CM-10-004).

    When this actor already stored a ``Create`` for the case, the node
    queues that same activity again instead of building a new one.  The
    outbox does not queue an id that is still pending (OX-06-002), and the
    reporter discards a redelivered id (ID-02-001), so the reporter gets one
    introduction.  This is what makes the redelivery route retry an
    introduction whose first queueing failed.

    With *retry* (the redelivery route), a case this store does not hold
    means no first delivery seeded it, so there is nothing to retry and the
    node returns ``SUCCESS``; on the trusted route the case was just seeded,
    so its absence is a failure.

    Recipients come from the shared selection
    (:func:`~vultron.core.participants.recipients.reporter_introduction_recipients`,
    CM-10-007), never from the roster directly.
    """

    def __init__(
        self, case_id: str, *, retry: bool = False, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.retry = retry
        self._recipients: list[str] = []
        self._sent_id: str | None = None

    def _skip_reason(self, case: VulnerabilityCase) -> str | None:
        """Why no introduction is owed, or ``None`` when one is.

        Sets ``_sent_id`` when an introduction was already stored, and
        ``_recipients`` when a new one is to be built.
        """
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
        self._sent_id = find_case_create_sent_by(
            self.datalayer, self.actor_id, self.case_id
        )
        if self._sent_id is not None:
            return None
        self._recipients = reporter_introduction_recipients(
            case, self.datalayer, excluding={self.actor_id, manager_id}
        )
        if not self._recipients:
            return "no active reporter to introduce (CM-10-004)"
        return None

    def _call_factory(self) -> tuple[str, str]:
        if self._sent_id is not None:
            # No captured dict on this node, so the seam needs no body.
            return self._sent_id, ""
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        return self.trigger_activity_factory.create_case(
            case_id=self.case_id, actor=self.actor_id, to=self._recipients
        )

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        if self._sent_id is not None:
            self.logger.info(
                "%s: introduction '%s' of case '%s' was already made;"
                " queued it again (OX-06-002, ID-02-001)",
                self.name,
                activity_id,
                self.case_id,
            )
            return
        self.logger.info(
            "%s: introduced case '%s' and its CASE_MANAGER to %s with"
            " Create(VulnerabilityCase) '%s' (CBT-01-001, ADR-0132)",
            self.name,
            self.case_id,
            self._recipients,
            activity_id,
        )

    def _resolve_case(
        self,
    ) -> tuple[VulnerabilityCase | None, Status | None]:
        """The stored case, a failure, or neither when a retry has no case.

        On the redelivery route (Regime 2, ADR-0087) a store that never
        seeded the case has no first introduction to retry; on the trusted
        route the case was just seeded, so its absence is a failure.
        """
        if self.retry:
            return resolve_case_replica(self, self.case_id), None
        return self._require_case(self.case_id)

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        self._recipients = []
        self._sent_id = None
        case, failure = self._resolve_case()
        if failure is not None:
            return failure
        if case is None:
            return Status.SUCCESS
        try:
            reason = self._skip_reason(case)
        except VultronError as exc:
            self.feedback_message = (
                f"could not decide the introduction for case"
                f" '{self.case_id}': {exc}"
            )
            self.logger.exception("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        if reason is not None:
            self.logger.debug(
                "%s: no introduction for case '%s': %s",
                self.name,
                self.case_id,
                reason,
            )
            return Status.SUCCESS
        return super().update()
