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

"""BT leaf nodes for received Add/Remove CaseParticipant activities.

Both messages are Case Owner requests to the CASE_MANAGER (ADR-0116), and
share one guard frame (:class:`ParticipantMoveGuardNode`), one effect frame
(:class:`ParticipantMoveEffectNode`) and one notice frame
(:class:`EmitParticipantMoveNoticeNode`).

The removal nodes implement the Case Owner's ``Remove(CaseParticipant)``
(CM-31-004 through CM-31-008):

- three read-only precondition guards — the named participant is on the
  case's roster, holds neither ``CASE_MANAGER`` nor ``CASE_OWNER``, and is
  not already removed (the idempotency guard, read as ``SKIPPED``);
- one effect, :class:`RemoveCaseParticipantFromCaseReceivedNode`, which sets
  the removal fact and keeps the record on the roster (CM-31-001), on the
  shared effect frame (:class:`ParticipantMoveEffectNode`);
- the direct notice to the removed participant,
  :class:`EmitParticipantRemovalNoticeNode`, which is not ledgered
  (CM-31-006).

The reinstatement nodes, for its ``Add(CaseParticipant)`` (CM-31-011), are in
:mod:`~vultron.core.behaviors.case.nodes.participant_reinstatement` and reuse
both frames.

Composite tree factories assembling these nodes are in
``case_participant_received_tree.py`` at the process-area root per
BTND-07-003.
"""

from typing import Literal

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)
from vultron.core.behaviors.delegated_authorship import delegated_authorship
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
    _EmitSingleActivityBase,
)
from vultron.core.behaviors.idempotency import SilentIdempotencyGuardMixin
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.enums.roles import CVDRole
from vultron.errors import VultronNotFoundError

#: Roles a removal may not take away (CM-31-004): the CASE_MANAGER role is
#: never unfilled (CM-24-006), and ownership is transferred first (CM-21).
PROTECTED_ROLES: frozenset[CVDRole] = frozenset(
    {CVDRole.CASE_MANAGER, CVDRole.CASE_OWNER}
)


def require_roster_record(
    dl: CasePersistence, case: VulnerabilityCase, participant_id: str
) -> CaseParticipant:
    """The stored record *participant_id* names on *case*'s roster.

    The canonical set is ``case_participants`` (CM-19-003); a record that
    is not on it, or that the store cannot read, names no participant of
    the case.

    Raises:
        VultronNotFoundError: *participant_id* names no participant of
            *case* (CM-31-004).
    """
    if participant_id in [_as_id(p) for p in case.case_participants]:
        record = dl.read(participant_id)
        if isinstance(record, CaseParticipant):
            return record
    raise VultronNotFoundError(
        "CaseParticipant",
        f"'{participant_id}' is not a participant of case '{case.id_}'",
    )


#: The two Case Owner moves the participant guards judge (ADR-0116), and the
#: requirement each refusal names.
ParticipantMove = Literal["removal", "reinstatement"]
_MOVE_SPEC: dict[ParticipantMove, str] = {
    "removal": "CM-31-004",
    "reinstatement": "CM-31-011",
}


class ParticipantMoveGuardNode(DataLayerConditionWithPorts):
    """Shared frame of the read-only removal and reinstatement guards.

    Resolves the case and the named record, then hands the record to
    :meth:`_check`.  A record that names no participant of the case fails
    the guard with a refusal reason; ``FAILURE`` is read by the handler as
    ``REFUSED`` unless a subclass is the idempotency guard.  Read-only, so
    every subclass precedes the guarded commit (CLP-10-006).  *move* names
    the Case Owner request being judged — a removal (CM-31-004) or a
    reinstatement (CM-31-011) — for the refusal reason.
    """

    def __init__(
        self,
        participant_id: str,
        case_id: str,
        name: str | None = None,
        move: ParticipantMove = "removal",
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.participant_id = participant_id
        self.case_id = case_id
        self.move: ParticipantMove = move

    def _refuse(self, reason: str) -> Status:
        """Fail the guard with *reason*, read as ``REFUSED`` by the handler."""
        self.feedback_message = (
            f"{reason} — {self.move} REFUSED ({_MOVE_SPEC[self.move]})"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1: the CASE_MANAGER holds its case
        try:
            record = require_roster_record(
                self.datalayer, case, self.participant_id
            )
        except VultronNotFoundError:
            return self._refuse(
                f"'{self.participant_id}' is not a participant of case"
                f" '{self.case_id}'"
            )
        return self._check(record)

    def _check(self, record: CaseParticipant) -> Status:
        """Judge the resolved *record*; subclasses implement it."""
        raise NotImplementedError


class MoveNamesCaseParticipantNode(ParticipantMoveGuardNode):
    """Guard: the ``Remove`` or ``Add(CaseParticipant)`` names a participant of the case.

    The frame already refuses a record that is not on the case's roster
    (CM-31-004, CM-31-011).  The inline participant must also name the
    stored record's actor when it names one: the ledger entry carries the
    activity as received, and a replica resolves its own copy of the record
    by that actor (CM-31-007), so an ``attributedTo`` that disagrees with the
    record would move a different participant on every replica than the one
    judged here — possibly the CASE_MANAGER or the Case Owner.
    """

    def __init__(
        self,
        participant_id: str,
        case_id: str,
        claimed_actor_id: str | None = None,
        name: str | None = None,
        move: ParticipantMove = "removal",
    ) -> None:
        super().__init__(
            participant_id=participant_id,
            case_id=case_id,
            name=name,
            move=move,
        )
        self.claimed_actor_id = claimed_actor_id

    def _check(self, record: CaseParticipant) -> Status:
        record_actor_id = _as_id(record.attributed_to)
        if (
            self.claimed_actor_id is None
            or self.claimed_actor_id == record_actor_id
        ):
            return Status.SUCCESS
        return self._refuse(
            f"the {self.move} names participant '{self.participant_id}' as"
            f" '{self.claimed_actor_id}', but that record belongs to"
            f" '{record_actor_id}' on case '{self.case_id}'"
        )


class RemovalTargetIsRemovableNode(ParticipantMoveGuardNode):
    """Guard: the named participant holds neither ``CASE_MANAGER`` nor ``CASE_OWNER``.

    The CASE_MANAGER role is never unfilled (CM-24-006) and ownership is
    transferred before its holder can leave (CM-21), so a removal naming
    either is refused (CM-31-004).
    """

    def _check(self, record: CaseParticipant) -> Status:
        protected = sorted(r.name for r in PROTECTED_ROLES & set(record.roles))
        if not protected:
            return Status.SUCCESS
        return self._refuse(
            f"participant '{self.participant_id}' holds"
            f" {', '.join(protected)} on case '{self.case_id}' and cannot"
            " be removed"
        )


class ParticipantNotYetRemovedNode(
    SilentIdempotencyGuardMixin, ParticipantMoveGuardNode
):
    """Idempotency guard: the named participant does not carry the removal fact.

    A removal of an already-removed participant is a legitimate no-op
    (CM-31-004, HP-01-003): this guard fails silently before the guarded
    commit, so the repeat commits no ledger entry (CLP-13-001), and the
    handler reads its ``FAILURE`` as ``SKIPPED``.  The first removal stands;
    the participant is not sent a second notice.
    """

    def _check(self, record: CaseParticipant) -> Status:
        if not record.removed:
            return Status.SUCCESS
        self.feedback_message = (
            f"participant '{self.participant_id}' was already removed"
            f" from case '{self.case_id}' by '{record.removal_activity}'"
        )
        return self._idempotent_failure(
            self.logger,
            "%s: %s — skipping (CLP-13-001)",
            self.name,
            self.feedback_message,
        )


def case_manager_admits_removal_guard(
    participant_id: str,
    case_id: str,
    claimed_actor_id: str | None = None,
) -> py_trees.composites.Selector:
    """Precondition guard: when this actor is the CASE_MANAGER, the removal is admissible.

    A read-only composite for the received tree's ``precondition_guards``
    (CLP-10-009), in the shape of ``case_manager_admits_proposal_guard``: a
    replica skips it as ``SUCCESS`` (it writes nothing, RSH-08-003), and the
    CASE_MANAGER runs the three removal guards in order, so a removal it
    refuses or skips leaves no ledger entry (CM-31-004, CLP-13-001).
    *claimed_actor_id* is the actor the inline participant is attributed
    to, when it names one.
    """
    return create_case_manager_gated_tree(
        name="RemovalAdmissibleIfCaseManager",
        case_id=case_id,
        body_name="RemovalAdmissible",
        children=[
            MoveNamesCaseParticipantNode(
                participant_id=participant_id,
                case_id=case_id,
                claimed_actor_id=claimed_actor_id,
            ),
            RemovalTargetIsRemovableNode(
                participant_id=participant_id, case_id=case_id
            ),
            ParticipantNotYetRemovedNode(
                participant_id=participant_id, case_id=case_id
            ),
        ],
    )


class ParticipantMoveEffectNode(DataLayerActionWithPorts):
    """Shared frame of the removal and reinstatement effects.

    Resolves the named record on the case's roster, hands it to
    :meth:`_apply`, and saves it when that changed it.  Runs after the
    guarded commit, so the entry's fan-out has already selected its
    recipients from the record as it stood before this write.  ``FAILURE``
    when the record is gone: the guards found it moments earlier in the
    CASE_MANAGER's own store (Regime 1, ADR-0087), so the handler reads it
    as an internal fault, never a refusal — the entry is already committed.
    """

    def __init__(
        self,
        participant_id: str,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.participant_id = participant_id
        self.case_id = case_id

    def _apply(self, record: CaseParticipant) -> bool:
        """Write the move onto *record*; ``True`` when it changed it."""
        raise NotImplementedError

    def _log_applied(self) -> None:
        """Log the applied move; subclasses name it and its spec."""
        raise NotImplementedError

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1: case must exist (ADR-0087)
        try:
            record = require_roster_record(
                self.datalayer, case, self.participant_id
            )
        except VultronNotFoundError as exc:
            self.feedback_message = str(exc)
            self.logger.exception("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        if self._apply(record):
            self.datalayer.save(record)
        self._log_applied()
        return Status.SUCCESS


class RemoveCaseParticipantFromCaseReceivedNode(ParticipantMoveEffectNode):
    """Set the removal fact on the named participant (CM-31-001).

    Records *removal_activity_id* — the Case Owner's ``Remove`` activity —
    through :meth:`CaseParticipant.record_removal`.  The record stays in
    ``case_participants`` and ``actor_participant_index`` (CM-19-002), with
    its status history and embargo consent rows untouched (CM-31-008); the
    case-level active check now finds it inert.  The replica apply node
    records the same fact from the ledger entry (CM-31-007).

    The entry's fan-out, selected before this write, still reaches the
    removed participant (CM-31-006).
    """

    def __init__(
        self,
        participant_id: str,
        case_id: str,
        removal_activity_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(
            participant_id=participant_id, case_id=case_id, name=name
        )
        self.removal_activity_id = removal_activity_id

    def _apply(self, record: CaseParticipant) -> bool:
        return record.record_removal(self.removal_activity_id)

    def _log_applied(self) -> None:
        self.logger.info(
            "%s: removed participant '%s' from active participation in"
            " case '%s' by '%s'; the record stays on the roster (CM-31-001)",
            self.name,
            self.participant_id,
            self.case_id,
            self.removal_activity_id,
        )


class EmitParticipantMoveNoticeNode(_EmitSingleActivityBase):
    """Send the moved participant a direct notice of the Case Owner's move.

    The shared frame of the removal and reinstatement notices.  The
    CASE_MANAGER is the ``actor`` and the Case Owner who asked for the move
    is ``attributedTo`` (CM-24-001, CM-24-002, from
    :func:`delegated_authorship`); the one recipient is the participant the
    move names.  The notice is delivery, not a record: it is queued on the
    outbox and never committed to the ledger.  The participant learns the
    move as case state from the ledger entry, and its replica applies that
    entry, not this notice (RSH-08-003).

    The handler treats a ``FAILURE`` here as an internal fault, never a
    refusal: by now the move is committed and applied.
    """

    #: The move the notice reports, for the log line.
    _MOVE: ParticipantMove

    def __init__(
        self,
        participant_id: str,
        case_id: str,
        requesting_actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name)
        self.participant_id = participant_id
        self.case_id = case_id
        self.requesting_actor_id = requesting_actor_id

    def _send(
        self,
        trigger_activity: TriggerActivityPort,
        actor: str,
        attributed_to: str,
        to: list[str],
    ) -> tuple[str, str]:
        """Build and persist the notice through the port; subclasses pick it."""
        raise NotImplementedError

    def _call_factory(self) -> tuple[str, str]:
        assert self.datalayer is not None
        assert self.actor_id is not None
        assert self.trigger_activity_factory is not None
        record = self.datalayer.read(self.participant_id)
        if not isinstance(record, CaseParticipant):
            raise VultronNotFoundError("CaseParticipant", self.participant_id)
        moved_actor_id = _as_id(record.attributed_to)
        if not moved_actor_id:
            raise ValueError(
                f"{self.name}: participant '{self.participant_id}' names no"
                " actor to notify"
            )
        authorship = delegated_authorship(
            doing_actor_id=self.actor_id,
            requesting_actor_id=self.requesting_actor_id,
        )
        return self._send(
            self.trigger_activity_factory,
            actor=authorship.actor,
            attributed_to=authorship.attributed_to,
            to=[moved_actor_id],
        )

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        self.logger.info(
            "%s: sent %s notice '%s' for participant '%s' of case '%s'",
            self.name,
            self._MOVE,
            activity_id,
            self.participant_id,
            self.case_id,
        )


class EmitParticipantRemovalNoticeNode(EmitParticipantMoveNoticeNode):
    """Send the removed participant its direct ``Remove(CaseParticipant)`` notice.

    The removed participant learns the removal as case state from the
    removal entry's fan-out, which it is still sent (CM-31-006); its replica
    applies that entry, not this notice (CM-31-007, RSH-08-003).
    """

    _MOVE: ParticipantMove = "removal"

    def _send(
        self,
        trigger_activity: TriggerActivityPort,
        actor: str,
        attributed_to: str,
        to: list[str],
    ) -> tuple[str, str]:
        return trigger_activity.remove_participant_from_case(
            participant_id=self.participant_id,
            case_id=self.case_id,
            actor=actor,
            attributed_to=attributed_to,
            to=to,
        )
