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

"""The paused replica's side of the embargo-ending notices (CM-31-010).

:class:`AwaitsEmbargoEndingNoticeNode` tells a replica whether it is one the
CASE_MANAGER owes a notice — the recipient rule of
:mod:`~vultron.core.behaviors.embargo.nodes.ending_notice`, read about
itself — and :class:`ApplyAnnouncedEmbargoRevisionNode` applies a shorter
revision from the CASE_MANAGER's ``Announce(EmbargoEvent)`` through
``EmbargoLifecycle`` (EMB-18-001).  A termination notice is a
``Remove(EmbargoEvent)``, which the received teardown tree already applies
through ``EmbargoLifecycle``.  The sender check that admits only the
CASE_MANAGER at a replica is the use case's sender guard (ADR-0115,
PCR-03-001).
"""

from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.embargo.nodes.ending_notice import (
    embargo_ending_notice,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
)
from vultron.core.behaviors.narrative_log import log_em_transition
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.participants.recipients import awaits_embargo_ending_notice
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.carried_embargo import hold_embargo_for_case
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    TransitionMode,
)
from vultron.errors import VultronError


class AwaitsEmbargoEndingNoticeNode(DataLayerConditionWithPorts):
    """Condition: the executing actor can be owed a CM-31-009 notice.

    ``SUCCESS`` when the actor's own record in this replica is joined and
    a signatory of the embargo in force that the ledger fan-out no longer
    reaches — removed, or at RM ``CLOSED``
    (:func:`~vultron.core.participants.recipients.awaits_embargo_ending_notice`)
    — so a direct notice from the CASE_MANAGER is its only channel
    (CM-31-010).  ``FAILURE`` otherwise, a case this store does not hold
    included: an active replica takes embargo changes from the ledger
    (RSH-08-003), and a withheld one (CM-10-005) is bound by no embargo in
    force, so an ``Announce(EmbargoEvent)`` reaching it is the teardown
    announcement, never a shorter revision to apply.
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        datalayer = cast(CasePersistence, self.datalayer)
        # Regime 2 (ADR-0087): a store with no replica of the case is not a
        # paused participant of it, and that is not an anomaly.
        case = self._resolve_case_replica(self.case_id)
        if case is None:
            self.feedback_message = f"No replica of case '{self.case_id}'"
            return Status.FAILURE
        if awaits_embargo_ending_notice(
            case, datalayer, cast(str, self.actor_id)
        ):
            self.feedback_message = (
                f"'{self.actor_id}' is a signatory on case '{self.case_id}'"
                " that the ledger no longer reaches"
            )
            return Status.SUCCESS
        self.feedback_message = (
            f"'{self.actor_id}' is owed no embargo-ending notice on case"
            f" '{self.case_id}'"
        )
        return Status.FAILURE


class ApplyAnnouncedEmbargoRevisionNode(
    DataLayerActionWithPorts, StateWriteCapable
):
    """Apply a shorter revision a paused replica was told of (CM-31-010).

    The CASE_MANAGER's ``Announce(EmbargoEvent)`` notice names the revision
    now in force.  When it ends no later than the replica's active embargo,
    the node stores the announced ``EmbargoEvent`` (when carried inline and
    not yet held, EMB-18-003) and activates it through
    ``EmbargoLifecycle.activate_embargo`` in ``OBSERVED`` mode (EMB-18-001),
    which carries the replica's signatories over as the CASE_MANAGER did
    (EP-05-001).

    Nothing is written, and the node succeeds, when the replica has no
    embargo in force, already has the announced one, or the announced one
    ends later: none of those is a shortening this replica is bound by.
    ``applied`` says whether the revision was applied.  An announced embargo
    that belongs to another case, or that cannot be read, fails the node.
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        embargo: EmbargoEvent | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.embargo_id = embargo_id
        self._embargo = embargo
        self.applied = False

    def _hold_announced_embargo(
        self, datalayer: CasePersistence, case: VulnerabilityCase
    ) -> None:
        """Store the inline embargo if absent; refuse one from another case.

        The case check covers the stored record as well as the inline copy:
        an id the replica already holds for another case's embargo is
        refused too, unless it is about one of the case's reports
        (EP-04-009, EMB-18-004).
        """
        hold_embargo_for_case(
            datalayer,
            case,
            self._embargo if self._embargo is not None else self.embargo_id,
        )

    def update(self) -> Status:
        self.applied = False
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        datalayer = cast(CasePersistence, self.datalayer)
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure
        current = case.active_embargo_id
        if current is None or current == self.embargo_id:
            self.feedback_message = (
                f"Case '{self.case_id}' has {current!r} in force — the"
                f" announced embargo '{self.embargo_id}' changes nothing"
            )
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS
        try:
            self._hold_announced_embargo(datalayer, case)
            notice = embargo_ending_notice(
                datalayer, before=current, after=self.embargo_id
            )
            if notice is None:
                self.feedback_message = (
                    f"Announced embargo '{self.embargo_id}' ends later than"
                    f" '{current}' on case '{self.case_id}' — not a"
                    " shortening, ignored (CM-31-009)"
                )
                self.logger.warning("%s: %s", self.name, self.feedback_message)
                return Status.SUCCESS
            result = EmbargoLifecycle(persistence=datalayer).activate_embargo(
                case_id=self.case_id,
                embargo_id=self.embargo_id,
                actor_id=self.actor_id,
                transition_mode=TransitionMode.OBSERVED,
            )
        except VultronError as exc:
            self.feedback_message = str(exc)
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        self.applied = True
        self.feedback_message = (
            f"Applied shorter revision '{self.embargo_id}' (replacing"
            f" '{current}') on case '{self.case_id}' from the CASE_MANAGER's"
            " notice (CM-31-010)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        if result.em_after != result.em_before:
            log_em_transition(
                self.logger,
                cast(str, self.actor_id),
                self.case_id,
                result.em_before,
                result.em_after,
            )
        return Status.SUCCESS


__all__ = [
    "ApplyAnnouncedEmbargoRevisionNode",
    "AwaitsEmbargoEndingNoticeNode",
]
