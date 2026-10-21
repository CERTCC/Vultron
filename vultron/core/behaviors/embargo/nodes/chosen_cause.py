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

"""The cause an actor's voluntary termination chose (EMB-14-001).

``create_terminate_active_embargo_tree`` asks three reason call-outs why the
actor ends the embargo.  The one that returns SUCCESS is followed by a
:class:`ChooseTerminationCauseNode`, which records the matching cause in the
tree's :class:`ChosenTermination`.  ``terminate_embargo_bt`` is given that
same :class:`ChosenTermination` and reads the cause at the write, so the
``Remove`` and the ``TERMINATED`` entry carry it (EMB-13-004).

The slot belongs to one tree instance, so nothing outlives the run, and the
choice and the termination it causes are one act.
"""

from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_termination import (
    EmbargoTermination,
    FixDeployedCause,
    FixReadyCause,
    OtherCause,
    TerminationCause,
    TerminationCauseKind,
    TerminationRequest,
)
from vultron.core.models.participant_status import (
    participant_status_vf_state,
)
from vultron.core.participants.recipients import case_content_participants
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.states.cs import is_vf_fix_ready
from vultron.core.states.embargo_register import TerminationReason
from vultron.errors import VultronWiringError
from vultron.primitives import NormalisedActorId


class ChosenTermination:
    """The termination a reason call-out chooses, read at the write.

    Every chosen cause is ``EARLY``.  It is set by
    :class:`ChooseTerminationCauseNode` and read by the termination's commit
    and ask nodes in the same run.
    """

    def __init__(self) -> None:
        self._termination: EmbargoTermination | None = None

    @property
    def reason(self) -> TerminationReason:
        """The what: a voluntary termination ends the embargo early."""
        return TerminationReason.EARLY

    def choose(self, cause: TerminationCause) -> None:
        """Record *cause* as the termination's why."""
        self._termination = EmbargoTermination(
            reason=TerminationReason.EARLY, cause=cause
        )

    @property
    def termination(self) -> EmbargoTermination:
        """The chosen termination.

        Raises:
            VultronWiringError: no reason call-out chose a cause before the
                termination ran, so the tree is composed wrongly.
        """
        if self._termination is None:
            raise VultronWiringError(
                "the termination ran before a reason call-out chose its"
                " cause (EMB-14-001)"
            )
        return self._termination


def resolve_chosen(
    termination: "TerminationRequest | ChosenTermination",
) -> TerminationRequest:
    """*termination*, with a :class:`ChosenTermination` read at the write."""
    if isinstance(termination, ChosenTermination):
        return termination.termination
    return termination


def fix_ready_vendors(
    dl: CasePersistence, case: VulnerabilityCase
) -> list[NormalisedActorId]:
    """The actor IDs of *case*'s active vendors whose fix is ready.

    Read from each active participant's latest status (a record is seeded
    with one, so it always has one): a participant has a
    ``vf`` dimension only when it is a vendor (ADR-0075), and an inert one
    is not part of the quorum (CM-10-004).  Sorted, so one quorum has one
    form.
    """
    vendors: list[NormalisedActorId] = []
    for actor_id, record in case_content_participants(case, dl):
        vf_state = participant_status_vf_state(record.participant_statuses[-1])
        if vf_state is not None and is_vf_fix_ready(vf_state):
            vendors.append(actor_id)
    return sorted(vendors)


class ChooseTerminationCauseNode(DataLayerAction):
    """Record the cause its reason call-out stands for (EMB-14-001).

    It follows one reason call-out in the reason Selector and sets *chosen*
    to the matching cause: ``FIX_DEPLOYED``, ``OTHER``, or ``FIX_READY``
    naming the case's fix-ready vendors (VP-09-007).  FAILURE when the
    reason is ``FIX_READY`` and no vendor in the case is fix-ready, so the
    Selector tries the next reason; nothing is written.
    """

    def __init__(
        self,
        case_id: str,
        kind: TerminationCauseKind,
        chosen: ChosenTermination,
        name: str | None = None,
    ) -> None:
        words = "".join(word.title() for word in kind.split("_"))
        super().__init__(name=name or f"Choose{words}Cause")
        if kind == TerminationCauseKind.THREAT_SIGNAL:
            raise VultronWiringError(
                "a voluntary termination cannot choose a THREAT_SIGNAL"
                " cause: only the CASE_MANAGER names one (EMB-13-005)"
            )
        self._case_id = case_id
        self._kind = kind
        self._chosen = chosen

    def _fix_ready_cause(self) -> FixReadyCause | Status:
        """The case's fix-ready vendors as a cause, or the FAILURE to return."""
        if (f := self._require_datalayer()) is not None:
            return f
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure
        vendors = fix_ready_vendors(
            cast(CasePersistence, self.datalayer), case
        )
        if not vendors:
            self.feedback_message = (
                f"No vendor in case '{self._case_id}' is fix-ready, so the"
                " embargo cannot end with a FIX_READY cause"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        return FixReadyCause(vendors=vendors)

    def update(self) -> Status:
        cause: TerminationCause
        if self._kind == TerminationCauseKind.FIX_DEPLOYED:
            cause = FixDeployedCause()
        elif self._kind == TerminationCauseKind.OTHER:
            cause = OtherCause()
        else:
            fix_ready = self._fix_ready_cause()
            if isinstance(fix_ready, Status):
                return fix_ready
            cause = fix_ready
        self._chosen.choose(cause)
        self.feedback_message = (
            f"Chose a {cause.kind} cause for ending the embargo on case"
            f" '{self._case_id}'"
        )
        self.logger.debug("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


__all__ = [
    "ChooseTerminationCauseNode",
    "ChosenTermination",
    "fix_ready_vendors",
    "resolve_chosen",
]
