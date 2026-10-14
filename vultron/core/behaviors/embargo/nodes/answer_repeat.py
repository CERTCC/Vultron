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

"""The CASE_MANAGER's repeat guard for an answer to an embargo Invite (#4597).

An answer is idempotent per participant and invitation (CM-13-005,
HP-01-003): a second ``Accept`` or ``Reject`` of the same embargo Invite by
the same actor, whatever its activity id, changes no state, adds no ledger
entry and sends no message.  The consent row is the durable evidence of the
first answer, so the guard reads it.  A *different* answer is a consent change,
not a repeat, and is admitted.

Provides:

- :class:`EmbargoAnswerNotRecordedNode` — precondition guard that fails, with
  :attr:`~EmbargoAnswerNotRecordedNode.is_repeat` set, when the sender's row
  for the embargo already holds the answer.
- :func:`case_manager_admits_embargo_answer_guard` — the guard behind the
  CASE_MANAGER gate, for a received answer tree's ``precondition_guards`` and
  for the Accept handler's preflight.
"""

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)
from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.models.case import VulnerabilityCase
from vultron.core.services.embargo_lifecycle.pec import (
    find_actor_participant,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.errors import VultronWiringError

#: The row state each answer leaves behind: ``Accept`` → ``AGREED``,
#: ``Reject`` → ``DECLINED`` (CM-18-003).
ANSWER_STATES = frozenset(
    {EmbargoConsentState.AGREED, EmbargoConsentState.DECLINED}
)


class EmbargoAnswerNotRecordedNode(DataLayerConditionWithPorts):
    """Guard: the sender's consent row does not already hold this answer.

    SUCCESS when *answering_actor_id*'s row for *embargo_id* is in any state
    other than *answer* — the answer is new, or it changes the consent — and
    when the actor has no participant record or no row for the embargo here:
    no earlier answer is recorded, so this is not a repeat, and the effect
    path decides what such an answer means.

    FAILURE with :attr:`is_repeat` set when the row already holds *answer*:
    the sender answered this invitation this way before, so the commit would
    add an entry that records no change and the effects would re-announce it
    (CM-13-005, HP-01-003).  The handler reports the run as ``SKIPPED``.

    Keyed on the identity of the answer being adjudicated — the sender and the
    embargo its Invite proposed, the same key the effect writes — never on the
    activity id, which a repeat sent under a new id does not share.

    Read-only, so it runs in ``precondition_guards`` ahead of the guarded
    commit (CLP-10-006, CLP-10-009).
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        answering_actor_id: str,
        answer: EmbargoConsentState,
        name: str | None = None,
    ) -> None:
        if answer not in ANSWER_STATES:
            raise VultronWiringError(
                f"EmbargoAnswerNotRecordedNode: answer must be one of"
                f" {sorted(ANSWER_STATES)}, not '{answer}'"
            )
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.embargo_id = embargo_id
        self.answering_actor_id = answering_actor_id
        self.answer = answer
        self.is_repeat = False
        """``True`` when the last run found this answer already recorded: a
        benign no-op, not a refusal."""

    def _recorded_state(self) -> EmbargoConsentState | None:
        """The sender's row state for the embargo, or ``None`` when it has none."""
        assert self.datalayer is not None
        # The guards ahead of this one report a missing case (ADR-0087).
        case = self.datalayer.read(self.case_id)
        if not isinstance(case, VulnerabilityCase):
            return None
        resolved = find_actor_participant(
            self.datalayer, case, self.answering_actor_id
        )
        if resolved is None or resolved[1].missing_rows([self.embargo_id]):
            return None
        return resolved[1].consent_for(self.embargo_id)

    def update(self) -> Status:
        self.is_repeat = False
        if (f := self._require_datalayer()) is not None:
            return f
        if self._recorded_state() != self.answer:
            return Status.SUCCESS
        self.is_repeat = True
        verb = (
            "accepted"
            if self.answer is EmbargoConsentState.AGREED
            else "declined"
        )
        self.feedback_message = (
            f"'{self.answering_actor_id}' already {verb} embargo"
            f" '{self.embargo_id}' on case '{self.case_id}' — repeat,"
            " nothing to apply (CM-13-005, HP-01-003)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


def case_manager_admits_embargo_answer_guard(
    case_id: str,
    embargo_id: str,
    answering_actor_id: str,
    answer: EmbargoConsentState,
) -> py_trees.behaviour.Behaviour:
    """Precondition guard: at the CASE_MANAGER, the answer is not a repeat.

    A participant replica skips it as ``SUCCESS``: only the CASE_MANAGER
    records an answer (BT-17-001), and a replica turned away by the gate is
    reported as a refusal (HP-01-005), not as a repeat.  The CASE_MANAGER runs
    :class:`EmbargoAnswerNotRecordedNode`, so a repeat is neither committed
    nor announced.
    """
    return create_case_manager_gated_tree(
        name="EmbargoAnswerNotRecordedIfCaseManager",
        case_id=case_id,
        body_name="EmbargoAnswerNotRecorded",
        children=[
            EmbargoAnswerNotRecordedNode(
                case_id=case_id,
                embargo_id=embargo_id,
                answering_actor_id=answering_actor_id,
                answer=answer,
            )
        ],
    )


__all__ = [
    "ANSWER_STATES",
    "EmbargoAnswerNotRecordedNode",
    "case_manager_admits_embargo_answer_guard",
]
