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

"""The ``AUTHOR`` kind: the author of the object a sender sends or changes
(HP-01-009, CM-30-001, CP-05-010, RSH-08-007).
"""

from typing import ClassVar

from py_trees.common import Status

from vultron.core.behaviors.sender_entitlement.base import (
    SenderEntitlementConditionNode,
)
from vultron.core.behaviors.sender_entitlement.declarations import (
    SenderEntitlementKind,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_proposal_admission import (
    CaseProposalAdmissionRecord,
)
from vultron.core.models.case_proposal_decline import (
    CaseProposalDeclineRecord,
)
from vultron.core.participants.recipients import (
    may_act_on_case,
)
from vultron.core.predicates.addressing import (
    same_actor_id,
)


class SenderIsNoteAuthorNode(SenderEntitlementConditionNode):
    """Guard: sender must be the note's author and an active case participant.

    Reads the note from the executing actor's store and compares its
    ``attributed_to`` with the sender.
    Returns ``FAILURE`` for an unknown note, a note with no recorded author, a
    different sender, and an author who is no longer an active participant of
    the case: one that is not an active participant (CM-10-004) or whose
    closure the case records (CM-23-018), asked through
    :func:`~vultron.core.participants.recipients.may_act_on_case`.

    Only ``RefuseRemoveNoteBT`` composes it, through its CM-30-001 sender
    guard, and that tree then refuses every ``Remove(Note)`` (CM-30-003,
    #6430): the sender is judged before the removal is refused.

    Spec: CM-30-001, CM-10-004, CM-23-018, HP-01-006.
    """

    guards_kind: ClassVar[SenderEntitlementKind | None] = (
        SenderEntitlementKind.AUTHOR
    )

    def __init__(
        self,
        note_id: str,
        sender_actor_id: str,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.note_id = note_id
        self.sender_actor_id = sender_actor_id
        self.case_id = case_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1: the participant check needs the case

        note = self.datalayer.read(self.note_id)
        author = _as_id(getattr(note, "attributed_to", None))
        if (
            author is not None
            and same_actor_id(self.sender_actor_id, author)
            and may_act_on_case(case, self.datalayer, self.sender_actor_id)
        ):
            return Status.SUCCESS

        return self._refuse_by_placement(
            f"Sender '{self.sender_actor_id}' is not the author of note"
            f" '{self.note_id}' (author: '{author}') or not an active"
            f" participant of case '{self.case_id}' that has not left it"
            " — REFUSED (CM-30-001, CM-23-018, HP-01-006)"
        )


class SenderIsProposalAuthorNode(SenderEntitlementConditionNode):
    """Guard: the sender of a ``Create(CaseProposal)`` is the proposal's author.

    The proposal id is chosen by the sender, and every proposal-keyed record
    is keyed on it alone.  The CASE_MANAGER records the proposer when it
    admits the proposal (``CaseProposalAdmissionRecord``) or declines it
    (``CaseProposalDeclineRecord``), and it stores the proposal itself, whose
    ``attributed_to`` is the proposer, when it sends the ``Accept`` or
    ``Reject``.  CP-05-010 counts each of the three as recording the
    proposal, so all three are read.  A delivery of that proposal id is a
    redelivery only from that proposer (CP-05-006, CP-05-010).

    - Nothing recorded for the proposal id: ``SUCCESS``.  It is a new
      proposal, and the parse edge has already refused a proposal whose
      ``attributed_to`` is not its sender (CP-01-010).
    - Every recorded proposer is the sender: ``SUCCESS``, a redelivery.
    - Any recorded proposer is another actor: ``FAILURE``, so the tree ends
      ``REFUSED`` before any arm writes a record or sends an answer.

    A store error is not caught: it fails the tree, which refuses rather than
    admits (``notes/bt-pitfalls.md`` § "A Refusal Arm in a Selector Fails
    Toward 'Admit'").

    Spec: CP-05-006, CP-05-010, HP-01-006, HP-01-009.
    """

    guards_kind: ClassVar[SenderEntitlementKind | None] = (
        SenderEntitlementKind.AUTHOR
    )

    _RECORDS: ClassVar[
        tuple[
            type[CaseProposalAdmissionRecord | CaseProposalDeclineRecord],
            ...,
        ]
    ] = (CaseProposalAdmissionRecord, CaseProposalDeclineRecord)

    def __init__(
        self,
        proposal_id: str,
        sender_actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.proposal_id = proposal_id
        self.sender_actor_id = sender_actor_id

    def _recorded_proposers(self) -> list[str]:
        """Every proposer this store recorded for the proposal id."""
        assert self.datalayer is not None
        proposers: list[str] = []
        for record_type in self._RECORDS:
            record = self.datalayer.read(
                record_type.build_id(self.proposal_id)
            )
            if isinstance(record, record_type):
                proposers.append(record.proposer_uri)
        stored = self.datalayer.read(self.proposal_id)
        author = _as_id(getattr(stored, "attributed_to", None))
        if author:
            proposers.append(author)
        return proposers

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        for proposer in self._recorded_proposers():
            if same_actor_id(proposer, self.sender_actor_id):
                continue
            return self._refuse_by_placement(
                f"Sender '{self.sender_actor_id}' is not the author of"
                f" CaseProposal '{self.proposal_id}', which this store"
                f" recorded for '{proposer}' — REFUSED"
                " (CP-05-010, HP-01-006)"
            )
        return Status.SUCCESS


class SenderIsParticipantRecordSubjectNode(SenderEntitlementConditionNode):
    """Guard: the participant record a status is added to is the sender's own.

    The ``AUTHOR`` kind for a received ``Add(ParticipantStatus)``: participant
    status is self-declared, so the sender must be the participant the target
    record names (RSH-08-007).  It keeps the standing of
    :class:`SenderIsParticipantNode`, which this rule's ``AUTHOR`` replaces:

    - the case's participant index lists *participant_id* as the sender's own
      record, so the index and the record never disagree about whose status
      it is (CM-19-003);
    - the record names the sender (``attributed_to``);
    - the record is not at RM ``CLOSED``: a participant that has left the
      case may act on nothing further (CM-23-018).

    The record is read first, so the case is the tree's when it names one,
    else the record's own (HP-08-008).

    A pure read.  FAILURE names the record and the sender.

    Spec: RSH-08-007, HP-01-006, HP-01-009, CM-23-018.
    """

    guards_kind: ClassVar[SenderEntitlementKind | None] = (
        SenderEntitlementKind.AUTHOR
    )

    def __init__(
        self,
        participant_id: str,
        sender_actor_id: str,
        case_id: str | None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.participant_id = participant_id
        self.sender_actor_id = sender_actor_id
        self.case_id = case_id

    def _refuse_citing(self, why: str) -> Status:
        """Compose the reason around *why*, then refuse by placement.

        One ``_refuse_citing`` per citation across the family, never a
        ``_refuse``: see
        :meth:`SenderEntitlementConditionNode._refuse_by_placement`.
        """
        return self._refuse_by_placement(
            f"Sender '{self.sender_actor_id}' may not add a status to"
            f" participant record '{self.participant_id}': {why} — REFUSED"
            " (RSH-08-007, HP-01-006)"
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        record = self.datalayer.read(self.participant_id)
        if not isinstance(record, CaseParticipant):
            return self._refuse_citing("the receiver holds no such record")
        case_id = self.case_id or _as_id(record.context)
        case, failure = self._require_case(case_id)
        if failure is not None:
            return failure  # Regime 1: the index check needs the case
        assert case is not None

        own_id = case.actor_participant_index.get(self.sender_actor_id)
        if own_id != self.participant_id:
            return self._refuse_citing(
                f"case '{case_id}' lists '{own_id}' as the sender's"
                " record; a participant asserts only its own status"
            )
        if not same_actor_id(
            _as_id(record.attributed_to) or "", self.sender_actor_id
        ):
            return self._refuse_citing("the record does not name the sender")
        if record.rm_closed:
            return self._refuse_citing(
                f"the sender has left case '{case_id}' (RM CLOSED) and"
                " may act on nothing further (CM-23-018)"
            )
        return Status.SUCCESS
