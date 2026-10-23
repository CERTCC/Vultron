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

"""Embargo invitation and proposal workflow nodes."""

from typing import cast

from py_trees.common import Status
from py_trees.ports import PortInformation

from vultron.core.behaviors.embargo.decided_entries import (
    EmbargoDecision,
    commit_and_apply_decision,
)
from vultron.core.behaviors.embargo.nodes.answer_record import decide_answer
from vultron.core.behaviors.embargo.proposal_index import (
    record_embargo_proposal_index,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.models.case import VulnerabilityCase
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.services.embargo_lifecycle.pec import (
    find_actor_participant,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.errors import (
    VultronEntryRefusedError,
    VultronNotFoundError,
    VultronValidationError,
    VultronWiringError,
)

#: Opens the feedback of a :class:`RecordParticipantRejectionNode` FAILURE
#: that is a repeat of a Reject already recorded.  The received tree's repeat
#: guard stops a repeat before the commit (CM-13-005, HP-01-003).
ALREADY_DECLINED_PREFIX = "Already declined"


class IndexReceivedEmbargoProposalNode(DataLayerActionWithPorts):
    """Record ``embargo_id -> invite_id`` on the case once the Invite is applied.

    Lets the accept/reject triggers correlate an embargo with the Invite that
    proposed it without re-reading the wire activity (ADR-0035 DL-06).  It
    runs last among the effects, so the correlation is written only after
    every other half of the receipt has succeeded (ID-04-005).  A partial
    replica that holds no copy of the case keeps the Invite and indexes
    nothing (Regime 2, ADR-0087), so it still returns ``SUCCESS``.
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        invite_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._embargo_id = embargo_id
        self._invite_id = invite_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        try:
            record_embargo_proposal_index(
                self.datalayer,
                self._case_id,
                self._embargo_id,
                self._invite_id,
            )
        except VultronNotFoundError:
            self.feedback_message = (
                f"case '{self._case_id}' not held here — proposal"
                f" '{self._invite_id}' not indexed"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS
        self.feedback_message = (
            f"Indexed proposal '{self._invite_id}' for embargo"
            f" '{self._embargo_id}' on case '{self._case_id}'"
        )
        self.logger.debug("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class _RecordReceivedConsentNode(DataLayerActionWithPorts, StateWriteCapable):
    """Shared frame: record a received consent act under the copy model.

    The CASE_MANAGER has committed the received act (an ``Accept``,
    ``Reject`` or ``Leave``) at intake (ADR-0111).  The lifecycle operation
    decides on a staged store (:meth:`_decide`); every consent row the
    decision changes beyond what the act's own entry carries is then
    committed as the CASE_MANAGER's own ``Update(EmbargoConsent)`` entry,
    caused by the received act (``/activity``), and applied by copying
    (ADR-0124, CLP-07-013).  Every replica copies the same entries.  The
    tree's decision guard (``EmbargoDecisionAppliesNode``) refuses, before
    the commit, an act that would record nothing the case can take.

    A failed commit is not a refusal: it raises (BT-14-001).  A tree that
    supplies no received act is a composition fault, and raises too.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.embargo_id = embargo_id
        self._event: object | None = None

    def initialise(self) -> None:
        super().initialise()
        self._event = self._try_get_input("activity")

    def _received_id(self) -> str:
        """The id of the received act this node records.

        Raises:
            VultronWiringError: the tree put no received act on the
                blackboard.
        """
        received_id = getattr(self._event, "activity_id", None)
        if not isinstance(received_id, str) or not received_id:
            raise VultronWiringError(
                f"{self.name}: no received act on the blackboard to"
                f" record for embargo '{self.embargo_id}' (ARCH-15-001)"
            )
        return received_id

    def _decide(self, actor_id: str) -> EmbargoDecision:
        """*actor_id*'s act, decided on a staged store; nothing is written.

        Raises:
            VultronError: the lifecycle refused the act, or it records
                nothing the case can take.
        """
        raise NotImplementedError

    def _record(self, actor_id: str) -> EmbargoDecision:
        """Decide *actor_id*'s act; commit and apply each row it changes.

        The act's own entry, already committed, carries any change of its
        own (an answer's stated row); every other row the decision changes
        is its own entry (ADR-0122).

        Raises:
            VultronError: the lifecycle refused the act, the act records
                nothing the case can take, or the trial refused its entries;
                nothing is committed or written.
        """
        assert self.datalayer is not None
        assert self.actor_id is not None
        decision = self._decide(actor_id)
        commit_and_apply_decision(
            datalayer=cast(CaseOutboxPersistence, self.datalayer),
            decision=decision,
            trigger_activity=self._require_trigger_activity_port(),
            actor_id=self.actor_id,
            cause_id=self._received_id(),
        )
        return decision


class _RecordParticipantAnswerNode(_RecordReceivedConsentNode):
    """Shared frame: record a participant's answer to an embargo Invite.

    The answer's committed entry is the answerer's row's entry: the row it
    states (:meth:`ConsentRowChange.answer`) is applied by copying, and no
    second entry records it (ADR-0122, CLP-07-013).  The lifecycle operation
    must write exactly that row (:func:`decide_answer`).
    """

    #: ``True`` for an ``Accept``, ``False`` for a ``Reject``.
    _ACCEPT: bool

    def _decide(self, actor_id: str) -> EmbargoDecision:
        assert self.datalayer is not None
        return decide_answer(
            self.datalayer,
            case_id=self.case_id,
            embargo_id=self.embargo_id,
            actor_id=actor_id,
            accept=self._ACCEPT,
        )


class RecordParticipantAcceptanceNode(_RecordParticipantAnswerNode):
    """Record a participant's acceptance of an embargo Invite.

    Uses ``EmbargoLifecycle.accept_embargo_invite`` to decide the sender's
    own consent — the case owner's included — moving no register entry
    (MSM-07-003, ADR-0122), and applies the ``AGREED`` row the committed
    Accept states (:class:`_RecordParticipantAnswerNode`).

    ``accepting_actor_id`` names the message's actor: the tree executes as
    the receiving CASE_MANAGER (ADR-0022), which authors the row's entry,
    while the acceptance is recorded for the actual accepting actor.
    """

    _ACCEPT = True

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        accepting_actor_id: str,
        name: str | None = None,
    ):
        super().__init__(case_id=case_id, embargo_id=embargo_id, name=name)
        self.accepting_actor_id = accepting_actor_id

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        try:
            self._record(self.accepting_actor_id)
        except (VultronNotFoundError, VultronEntryRefusedError) as exc:
            # The case itself is missing, or it changed under the decision:
            # consent reads no embargo record (ADR-0122).
            self.feedback_message = str(exc)
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        self.feedback_message = (
            f"Recorded acceptance of embargo '{self.embargo_id}'"
            f" for case '{self.case_id}'"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class RecordParticipantRejectionNode(_RecordParticipantAnswerNode):
    """Record a participant's rejection of an embargo via EmbargoLifecycle.

    The received-side twin of :class:`RecordParticipantAcceptanceNode`:
    decides with ``EmbargoLifecycle.record_embargo_rejection`` so the
    received ``Reject(Invite(EmbargoEvent))`` tree applies the same
    MSM-07-004 rule as the trigger side — the named embargo's row becomes
    ``DECLINED``, as the committed Reject states, and nothing else moves.  A
    Reject never withdraws: one of the embargo in
    force from an ``AGREED`` row is refused (``RejectIsNotWithdrawalNode``
    guards it ahead of the commit), since withdrawal is
    ``Leave(EmbargoEvent)`` (MSM-07-010).  Moves no EM
    state: deciding the proposal is the CASE_MANAGER's adjudication
    (``DecideRejectedEmbargoProposalNode``, EP-09-005).

    ``rejecting_actor_id`` names the message's actor (the tree executes as the
    receiving actor, ADR-0022).  Returns SUCCESS when the rejection changes
    the row.  Returns FAILURE — so the handler reports a refusal — when the
    Reject names an embargo that is neither active nor an open proposal of
    the case (a protocol error, not a consent change), when it would withdraw
    the actor from the embargo in force, when the actor has no participant
    record here (the row it states cannot be written), when it repeats a
    rejection already recorded, or when the case is not found.
    """

    _ACCEPT = False

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        rejecting_actor_id: str,
        name: str | None = None,
    ):
        super().__init__(case_id=case_id, embargo_id=embargo_id, name=name)
        self.rejecting_actor_id = rejecting_actor_id

    def _already_declined(self, case: VulnerabilityCase) -> bool:
        """True when the rejecting actor's row for the embargo is already DECLINED."""
        assert self.datalayer is not None
        resolved = find_actor_participant(
            self.datalayer, case, self.rejecting_actor_id
        )
        return (
            resolved is not None
            and resolved[1].consent_for(self.embargo_id)
            == EmbargoConsentState.DECLINED
        )

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None

        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        try:
            decision = self._record(self.rejecting_actor_id)
        except (
            VultronNotFoundError,
            VultronValidationError,
            VultronEntryRefusedError,
        ) as exc:
            self.feedback_message = str(exc)
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        if decision.act is None and self._already_declined(case):
            # A repeat of a Reject already recorded (HP-01-003, #2255).  The
            # received tree's repeat guard stops one before the commit
            # (CM-13-005, #4597).
            self.feedback_message = (
                f"{ALREADY_DECLINED_PREFIX}: '{self.rejecting_actor_id}'"
                f" had declined embargo '{self.embargo_id}' on case"
                f" '{self.case_id}' before this Reject"
            )
            return Status.FAILURE

        self.feedback_message = (
            f"Recorded rejection of embargo '{self.embargo_id}' by"
            f" '{self.rejecting_actor_id}' on case '{self.case_id}'"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS
