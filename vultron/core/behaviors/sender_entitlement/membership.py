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

"""Participant-record checks: ``PARTICIPANT``, ``ACTIVE_PARTICIPANT``,
``LEDGER_PEER``, and the closed-sender door's check (CM-10-004,
CM-23-018).
"""

from typing import ClassVar

from py_trees.common import Status
from py_trees.ports import PortInformation

from vultron.core.behaviors.helpers import (
    DataLayerConditionWithPorts,
    FindParticipantByActorIdNode,
)
from vultron.core.behaviors.sender_entitlement.base import (
    SenderEntitlementConditionNode,
    refuse_by_placement,
)
from vultron.core.behaviors.sender_entitlement.declarations import (
    SenderEntitlementKind,
)
from vultron.core.behaviors.sync.nodes.replay_case import replay_case_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.participants.recipients import (
    closure_recorded,
    is_case_content_recipient,
    may_act_on_case,
)
from vultron.errors import VultronError

# ---------------------------------------------------------------------------
# Condition node: PARTICIPANT
# ---------------------------------------------------------------------------


class SenderIsParticipantNode(FindParticipantByActorIdNode):
    """Guard: sender must have a participant record on the case.

    Not a :class:`SenderEntitlementConditionNode`: it reuses the participant
    lookup of :class:`FindParticipantByActorIdNode`, so it names its kind
    itself and takes the family's refusal rule from the free function
    :func:`~vultron.core.behaviors.sender_entitlement.base.refuse_by_placement`
    rather than from the base method (SL-03-002, #5786).

    Returns ``SUCCESS`` when the case lists a participant record for the
    sender, whether or not that participant is active (CM-10-004): an inert
    invitee and a removed participant pass.  A participant whose closure the
    case records (RM ``CLOSED``) fails: it has left and may act on nothing
    further (CM-23-018; the same test as
    :func:`~vultron.core.participants.recipients.closure_recorded`, asked of
    the record the lookup found).
    Returns ``FAILURE`` otherwise, halting the parent ``Sequence`` with a
    REFUSED outcome.

    With no ``case_id`` there is no case to check the sender against, so it
    fails (DEMOMA-07-003 step 1); the status use case resolves the case from
    the stored status before it builds its tree.

    Merged from ``VerifySenderIsParticipantNode`` (ADR-0115, AC-2); it was
    ``SenderIsActiveParticipantNode`` until the ``PARTICIPANT`` kind split
    from ``ACTIVE_PARTICIPANT`` (#4437).

    Spec: HP-01-006, HP-01-009, DEMOMA-07-003.
    """

    guards_kind: ClassVar[SenderEntitlementKind | None] = (
        SenderEntitlementKind.PARTICIPANT
    )

    def __init__(
        self,
        sender_actor_id: str,
        case_id: str | None,
        name: str | None = None,
    ) -> None:
        super().__init__(
            case_id=case_id or "",
            target_actor_id=sender_actor_id,
            participant_key="sender_participant",
            name=name or self.__class__.__name__,
        )
        self.sender_actor_id = sender_actor_id
        self._case_id_hint = case_id or None

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f

        case_id = self._case_id_hint
        if case_id is None:
            return refuse_by_placement(
                self,
                f"No case in this store to check sender"
                f" '{self.sender_actor_id}' against — REFUSED"
                " (HP-01-006, DEMOMA-07-003 step 1)",
            )

        self.case_id = case_id
        result = super().update()
        if result == Status.FAILURE:
            return refuse_by_placement(
                self,
                f"Sender '{self.sender_actor_id}' is not a participant of"
                f" case '{case_id}' — REFUSED"
                " (HP-01-006, DEMOMA-07-003 step 1)",
            )

        # The record the lookup above found, not a second lookup through the
        # index, so the two can never disagree about which record is closed.
        record = self.found_participant
        if record is not None and record.rm_closed:
            return refuse_by_placement(
                self,
                f"Sender '{self.sender_actor_id}' has left case '{case_id}'"
                " (RM CLOSED) and may act on nothing further — REFUSED"
                " (HP-01-006, CM-23-018)",
            )

        self.logger.debug(
            "%s: sender '%s' is a participant in case '%s'"
            " (HP-01-006, DEMOMA-07-003 step 1)",
            self.name,
            self.sender_actor_id,
            case_id,
        )
        return Status.SUCCESS


# ---------------------------------------------------------------------------
# Condition node: ACTIVE_PARTICIPANT
# ---------------------------------------------------------------------------


class SenderIsActiveParticipantNode(SenderEntitlementConditionNode):
    """Guard: sender must be an active participant whose closure is not recorded.

    The guard of the ``ACTIVE_PARTICIPANT`` kind (CM-23-018, CM-23-020).  Active means
    joined, not removed, and a signatory to the embargo in force (CM-10-004);
    the sender must also not be at RM ``CLOSED``, because a participant that
    has left may act on nothing further.  Both are asked through the one
    shared predicate,
    :func:`~vultron.core.participants.recipients.may_act_on_case`.  An inert
    invitee, a removed participant, a closed participant and a sender the
    case does not list all fail.  A closed participant's resync request is
    the ``LEDGER_PEER`` kind's instead
    (:class:`SenderIsActiveLedgerParticipantNode`).  With no ``case_id``, or
    a case this store does not hold, there is no standing to check, so the
    sender is refused (Regime 1, ADR-0087).

    Spec: CM-23-018, CM-10-004, HP-01-006, HP-01-009.
    """

    guards_kind: ClassVar[SenderEntitlementKind | None] = (
        SenderEntitlementKind.ACTIVE_PARTICIPANT
    )

    def __init__(
        self,
        sender_actor_id: str,
        case_id: str | None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.sender_actor_id = sender_actor_id
        self.case_id = case_id or None

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        if self.case_id is None:
            # An activity that names no case is a routine refusal, as
            # SenderIsParticipantNode reports it, not a Regime 1 anomaly.
            return self._refuse_by_placement(
                f"No case in this store to check sender"
                f" '{self.sender_actor_id}' against — REFUSED (HP-01-006)"
            )
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1: no case, so no standing to check
        if may_act_on_case(case, self.datalayer, self.sender_actor_id):
            return Status.SUCCESS
        return self._refuse_by_placement(
            f"Sender '{self.sender_actor_id}' is not an active participant"
            f" of case '{self.case_id}', or has left it — REFUSED"
            " (HP-01-006, CM-10-004, CM-23-018)"
        )


# ---------------------------------------------------------------------------
# Condition node: LEDGER_PEER (ledger activity on the blackboard)
# ---------------------------------------------------------------------------


class SenderIsActiveLedgerParticipantNode(SenderEntitlementConditionNode):
    """Guard: sender must be an active participant of the ledger entry's case.

    The guard of the ``LEDGER_PEER`` kind, the standing of a
    ``Reject(CaseLedgerEntry)`` resync request (SYNC-03-005).
    Reads ``activity`` from the blackboard and takes the case from the
    ``CaseLedgerEntry`` it carries, or, for the ``Reject`` that names no entry
    because its sender holds none, from its ``target`` (SYNC-16-027).
    Returns ``SUCCESS`` only when the sender is an active participant of that
    case (:func:`~vultron.core.participants.recipients.is_case_content_recipient`,
    CM-10-004).
    An unknown case, a missing sender, an unlisted sender and an inert
    participant all return ``FAILURE``: there is nothing to replay to a sender
    the case cannot vouch for, so there is no bootstrap pass-through here.

    A participant at RM ``CLOSED`` passes: it may still ask for the entries
    that record its own closure, and the replay stops there
    (:func:`~vultron.core.participants.recipients.closed_participant_ledger_cutoff`,
    CM-23-004, CM-23-018).  This is the one participant guard that does not
    refuse a closed sender.

    Spec: SYNC-03-005, CM-10-004, CM-23-018, HP-01-006.
    """

    guards_kind: ClassVar[SenderEntitlementKind | None] = (
        SenderEntitlementKind.LEDGER_PEER
    )

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def initialise(self) -> None:
        super().initialise()
        self.activity = self.get_input("activity")

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        # The rejected entry's case, or the case the objectless genesis
        # Reject names as its target (SYNC-16-027).
        try:
            case_id = replay_case_id(self.activity, self.name)
        except VultronError as exc:
            self.logger.warning("%s: %s", self.name, exc)
            return Status.FAILURE
        sender_id = getattr(self.activity, "actor_id", None)
        if not sender_id:
            self.logger.warning("%s: activity has no actor_id", self.name)
            return Status.FAILURE

        # Regime 1: no case means no participant, so the sender is refused.
        case, failure = self._require_case(case_id)
        if failure is not None:
            return failure
        if not is_case_content_recipient(case, self.datalayer, sender_id):
            return self._refuse_by_placement(
                f"Sender '{sender_id}' is not an active participant in case"
                f" '{case_id}' — REFUSED (SYNC-03-005, CM-10-004)"
            )
        return Status.SUCCESS


# ---------------------------------------------------------------------------
# Condition node: the sender's closure is not recorded (CM-23-018)
# ---------------------------------------------------------------------------


class SenderClosureNotRecordedNode(DataLayerConditionWithPorts):
    """Guard: the case does not record the sender's closure (CM-23-018).

    A participant whose closure the case records (RM ``CLOSED``) may act on
    nothing further, except that a repeat of an act that would close it
    again changes nothing and is reported ``SKIPPED``, whatever its activity
    id (ID-05-003).  This node is the closed-sender door guard the
    receive-tree factory places
    (:func:`vultron.core.behaviors.sender_guard.closed_sender_door`), built
    by :func:`vultron.core.behaviors.sender_guard.closed_sender_guard`.
    The factory also composes it ahead of the ``CASE_OWNER`` kind's role
    check, which asks the role alone.

    SUCCESS when the sender is not at RM ``CLOSED`` here, or when this store
    holds no such case: the received tree decides what the act means.

    FAILURE with :attr:`sender_closed` set when the case records the
    sender's closure (:func:`~vultron.core.participants.recipients.closure_recorded`).
    The handler reports an act that would close the sender again as
    ``SKIPPED``, and any other act as ``REFUSED``
    (:func:`~vultron.core.use_cases.received._bt_verdict.closed_sender_verdict`).

    Keyed on the sender's recorded RM state, never on the activity id, which
    a repeat sent under a new id does not share.  Read-only.

    Its line stays at INFO, and does not take the placement rule the kinds'
    checks take (:func:`refuse_by_placement`, SL-03-002).  Three reasons,
    and the third is why DEBUG would cost something (#5786):

    - Its FAILURE is not a refusal.  The handler decides the verdict from
      the act: a repeat of an act that would close the sender again is
      ``SKIPPED`` (CM-23-049, ID-05-003), and only any other act is
      ``REFUSED``.  SL-03-002 picks the level of a *refusal reason*; this
      line reports a recorded state, which is INFO under SL-03-001.
    - It carries no ``REFUSED`` wording, so no reader and no matcher takes
      it as the tree's answer (SL-03-003 is met as it stands).
    - At the closed-sender door that lets a closing Case Owner through
      (:func:`vultron.core.behaviors.sender_guard.closed_sender_door` with
      ``case_owner_completes``) this check is the Selector's first arm, so
      the placement rule would read DEBUG — while the arm after it,
      :class:`~vultron.core.behaviors.sender_entitlement.case_owner.SenderIsCaseOwnerNode`,
      records its reason without logging it at all (#5845).  The door's
      refusal would then have no line above DEBUG anywhere.

    Spec: CM-23-018, ID-05-003, HP-01-007, SL-03-001.
    """

    def __init__(
        self, case_id: str, sender_actor_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.sender_actor_id = sender_actor_id
        self.sender_closed = False
        """``True`` when the last run found the sender's closure recorded."""

    def update(self) -> Status:
        self.sender_closed = False
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case = self.datalayer.read(self.case_id)
        if not isinstance(case, VulnerabilityCase) or not closure_recorded(
            case, self.datalayer, self.sender_actor_id
        ):
            return Status.SUCCESS
        self.sender_closed = True
        self.feedback_message = (
            f"'{self.sender_actor_id}' is already closed on case"
            f" '{self.case_id}' (CM-23-018)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE
