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
through ``EmbargoLifecycle``; :class:`AdoptRemovedEmbargoRevisionNode` first
activates the revision it names when that ``Remove`` overtook the revision's
own ``Announce``, so the notices end the same in either order (SYNC-19-001).
The sender check that admits only the
CASE_MANAGER at a replica is the use case's sender guard (ADR-0115,
PCR-03-001).
"""

from datetime import datetime
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
from vultron.core.models.embargo_termination import (
    EmbargoTermination,
    end_time_violations,
)
from vultron.core.participants.recipients import awaits_embargo_ending_notice
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.carried_embargo import (
    embargo_for_case,
    hold_embargo_for_case,
)
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    TransitionMode,
)
from vultron.core.states.embargo_register import (
    FINAL_REGISTER_STATUSES,
    TerminationReason,
)
from vultron.errors import INTERNAL_FAULTS, VultronError


def names_unadopted_revision(case: VulnerabilityCase, embargo_id: str) -> bool:
    """Whether a paused replica would adopt *embargo_id* before its teardown.

    True when *case* has an embargo in force other than *embargo_id*, and
    the register holds *embargo_id* at no status an activation leaves
    (``SUPERSEDED``, ``TERMINATED``, ``REJECTED``, ``CANCELLED``): the
    ``Remove`` names a revision that replaced the replica's embargo, which
    :class:`AdoptRemovedEmbargoRevisionNode` activates first (CM-31-042,
    SYNC-19-001).  False otherwise, a stale ``Remove`` included (ADR-0122).
    """
    current = case.active_embargo_id
    if current is None or current == embargo_id:
        return False
    entry = case.embargo_register_entry(embargo_id)
    return entry is None or entry.status not in FINAL_REGISTER_STATUSES


def adopted_revision_timing_violations(
    datalayer: CasePersistence,
    case: VulnerabilityCase,
    actor_id: str | None,
    embargo_id: str | None,
    embargo: EmbargoEvent | None,
    termination: EmbargoTermination,
    at: datetime | None,
) -> list[str] | None:
    """Judge a termination by the revision a paused replica adopts first.

    ``None`` unless *termination* is ``END_TIME_REACHED``, *actor_id* is a
    paused signatory (CM-31-010) and the ``Remove`` names a revision it
    would adopt (:func:`names_unadopted_revision`, CM-31-042).  Otherwise
    the reasons *termination*, claimed at *at*, may not end that revision,
    judged by its own end time: the stored record, else the ``Remove``'s
    inline copy (EMB-18-003), checked as the adoption checks it
    (EMB-18-004).  An ``EARLY`` termination has no time rule, so it reads
    nothing here and the adoption alone judges the named revision.

    The guard calling this runs on every path, while the adoption runs only
    off the CASE_MANAGER's; the two still agree, because the CASE_MANAGER is
    never a paused signatory of an embargo in force: it is never removed
    (CM-02-014), and it reaches RM ``CLOSED`` only on an owner close that an
    embargo in force blocks (CM-23-002, CM-23-011).

    Raises:
        VultronNotFoundError: the revision cannot be read.
        VultronValidationError: the revision belongs to another case.
    """
    if (
        termination.reason != TerminationReason.END_TIME_REACHED
        or embargo_id is None
        or actor_id is None
        or not names_unadopted_revision(case, embargo_id)
        or not awaits_embargo_ending_notice(case, datalayer, actor_id)
    ):
        return None
    named = embargo_for_case(
        datalayer, case, embargo if embargo is not None else embargo_id
    )
    return end_time_violations(termination, end_time=named.end_time, at=at)


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


class _ObservedRevisionActivationNode(
    DataLayerActionWithPorts, StateWriteCapable
):
    """Shared base: activate a revision the CASE_MANAGER told a paused replica of.

    Holds the inline ``EmbargoEvent`` the notice carries (EMB-18-003) and
    activates it through ``EmbargoLifecycle.activate_embargo`` in
    ``OBSERVED`` mode (EMB-18-001), which supersedes the embargo in force and
    carries its signatories over as the CASE_MANAGER did (EP-05-003).
    ``applied`` says whether this tick activated the revision.
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

    def _no_change(self, message: str) -> Status:
        self.feedback_message = message
        self.logger.debug("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS

    def _activate(
        self, datalayer: CasePersistence, current: str, why: str
    ) -> Status:
        """Activate the revision in place of *current*; FAILURE on refusal."""
        try:
            result = EmbargoLifecycle(persistence=datalayer).activate_embargo(
                case_id=self.case_id,
                embargo_id=self.embargo_id,
                actor_id=self.actor_id,
                transition_mode=TransitionMode.OBSERVED,
            )
        except INTERNAL_FAULTS:
            raise  # never a refusal, so never answered (ADR-0095)
        except VultronError as exc:
            return self._refuse(exc)
        self.applied = True
        self.feedback_message = (
            f"Applied revision '{self.embargo_id}' (replacing '{current}') on"
            f" case '{self.case_id}' {why}"
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

    def _refuse(self, exc: VultronError) -> Status:
        self.feedback_message = str(exc)
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


class ApplyAnnouncedEmbargoRevisionNode(_ObservedRevisionActivationNode):
    """Apply a shorter revision a paused replica was told of (CM-31-010).

    The CASE_MANAGER's ``Announce(EmbargoEvent)`` notice names the revision
    now in force.  When it ends no later than the replica's active embargo,
    the node stores the announced ``EmbargoEvent`` (when carried inline and
    not yet held, EMB-18-003) and activates it through
    ``EmbargoLifecycle.activate_embargo`` in ``OBSERVED`` mode (EMB-18-001),
    which carries the replica's signatories over as the CASE_MANAGER did
    (EP-05-003).

    Nothing is written, and the node succeeds, when the replica has no
    embargo in force, already has the announced one, or the announced one
    ends later: none of those is a shortening this replica is bound by.
    ``applied`` says whether the revision was applied.  An announced embargo
    that belongs to another case, or that cannot be read, fails the node.
    """

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
            return self._no_change(
                f"Case '{self.case_id}' has {current!r} in force — the"
                f" announced embargo '{self.embargo_id}' changes nothing"
            )
        try:
            self._hold_announced_embargo(datalayer, case)
            notice = embargo_ending_notice(
                datalayer,
                before=current,
                after=self.embargo_id,
                at=self._require_act_instant(),
            )
        except INTERNAL_FAULTS:
            raise  # never a refusal, so never answered (ADR-0095)
        except VultronError as exc:
            return self._refuse(exc)
        if notice is None:
            self.feedback_message = (
                f"Announced embargo '{self.embargo_id}' ends later than"
                f" '{current}' on case '{self.case_id}' — not a"
                " shortening, ignored (CM-31-030)"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS
        return self._activate(
            datalayer,
            current,
            "from the CASE_MANAGER's shorter-revision notice (CM-31-010)",
        )


class AdoptRemovedEmbargoRevisionNode(_ObservedRevisionActivationNode):
    """Activate the revision a paused replica's ``Remove`` names, if unseen.

    The CASE_MANAGER terminates only the embargo in force, so a
    ``Remove(EmbargoEvent)`` notice (CM-31-009) naming a revision this
    paused replica has not activated means that revision replaced the
    replica's embargo.  Either its ``Announce`` (CM-31-030) has not arrived
    yet, since per-recipient order is no guarantee (SYNC-19-003), or it was
    a longer revision, for which no ``Announce`` is owed.  The node
    activates that revision first, so the teardown that follows terminates
    it and the replica ends the same whichever notice arrives first
    (SYNC-19-001); a late ``Announce`` then finds no embargo in force and
    changes nothing.

    It runs ahead of the teardown in the paused replica's arm only.  Nothing
    is written, and the node succeeds, when the replica has no embargo in
    force, the named embargo is the one in force, or the register holds the
    named embargo at a status no activation leaves (``SUPERSEDED``,
    ``TERMINATED``, ``REJECTED``, ``CANCELLED``): such a ``Remove`` is stale
    and changes nothing (ADR-0122).  A named embargo that belongs to another
    case, or that cannot be read, fails the node.
    """

    def _nothing_to_adopt(self, case: VulnerabilityCase) -> str:
        current = case.active_embargo_id
        entry = case.embargo_register_entry(self.embargo_id)
        if current in (None, self.embargo_id) or entry is None:
            return (
                f"Case '{self.case_id}' has {current!r} in force — nothing to"
                f" adopt before removing '{self.embargo_id}'"
            )
        return (
            f"Embargo '{self.embargo_id}' is {entry.status} on case"
            f" '{self.case_id}' — a stale Remove changes nothing"
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
        if current is None or not names_unadopted_revision(
            case, self.embargo_id
        ):
            return self._no_change(self._nothing_to_adopt(case))
        try:
            self._hold_announced_embargo(datalayer, case)
        except INTERNAL_FAULTS:
            raise  # never a refusal, so never answered (ADR-0095)
        except VultronError as exc:
            return self._refuse(exc)
        return self._activate(
            datalayer,
            current,
            "ahead of the CASE_MANAGER's termination notice, which names a"
            " revision not yet applied here (CM-31-042, SYNC-19-001)",
        )


__all__ = [
    "AdoptRemovedEmbargoRevisionNode",
    "ApplyAnnouncedEmbargoRevisionNode",
    "AwaitsEmbargoEndingNoticeNode",
    "adopted_revision_timing_violations",
    "names_unadopted_revision",
]
