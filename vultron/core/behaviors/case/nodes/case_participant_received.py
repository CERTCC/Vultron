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

"""BT leaf nodes for the Case Owner's removal and reinstatement acts.

The Case Owner decides a removal or a reinstatement, so it sends the act
itself, to the CASE_MANAGER only: ``Remove(<Actor>, origin=<case>)`` or
``Add(<Actor>, target=<case>)`` (ADR-0199).  The act names the actor as a
typed reference, not its ``CaseParticipant``: the case has one record per
actor, read from ``actor_participant_index`` (CM-19-003).  Both moves share
one guard frame (:class:`ParticipantMoveGuardNode`) and one effect frame
(:class:`ParticipantMoveEffectNode`), and both announce the admitted act to
the actor it names (:class:`AnnounceParticipantMoveNode`).

The removal nodes (CM-31-004 through CM-31-008):

- read-only precondition guards: the named actor has a participant record
  on the case, holds neither ``CASE_MANAGER`` nor ``CASE_OWNER``, and is not
  already removed (the idempotency guard, read as ``SKIPPED``);
- one effect, :class:`RecordParticipantRemovalNode`, which sets the removal
  fact and keeps the record on the roster (CM-31-001, CM-31-015).

The reinstatement nodes (CM-31-011) are in
:mod:`~vultron.core.behaviors.case.nodes.participant_reinstatement` and reuse
both frames and the announcement.

Every node reads the case from ``/case_id`` and the named actor from
``/participant_actor_id`` (BTND-01-008); the received tree declares the
actor key, so the runner seeds it from the act (BT-25-007).

Composite tree factories assembling these nodes are in
``case_participant_received_tree.py`` at the process-area root per
BTND-07-003.
"""

from typing import Literal

import py_trees
from py_trees.common import Status
from py_trees.ports import PortInformation

from vultron.core.behaviors.act_key_ports import (
    act_key_ports,
    act_key_remappings,
    act_value,
)
from vultron.core.behaviors.act_keys import CASE_ID, PARTICIPANT_ACTOR_ID
from vultron.core.behaviors.case.nodes.announce_admitted_act import (
    EmitAnnounceAdmittedActNode,
)
from vultron.core.behaviors.case_id_scope import with_case_id
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
)
from vultron.core.behaviors.idempotency import SilentIdempotencyGuardMixin
from vultron.core.behaviors.node_logger import fail_with_reason
from vultron.core.behaviors.received_request import ReceivedRequestInputMixin
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.predicates.addressing import normalise_actor_id
from vultron.core.services.embargo_lifecycle.pec import find_actor_participant
from vultron.enums.roles import CVDRole
from vultron.errors import VultronNotFoundError

#: Roles a removal or a reinstatement may not name (CM-31-004, CM-31-036):
#: the CASE_MANAGER role is never unfilled (CM-02-014), and ownership is
#: transferred first (CM-21).
PROTECTED_ROLES: frozenset[CVDRole] = frozenset(
    {CVDRole.CASE_MANAGER, CVDRole.CASE_OWNER}
)

#: The two Case Owner moves the participant guards judge (ADR-0116), and the
#: requirement each refusal names.
ParticipantMove = Literal["removal", "reinstatement"]
_MOVE_SPEC: dict[ParticipantMove, str] = {
    "removal": "CM-31-004",
    "reinstatement": "CM-31-036",
}

#: The ports every node of a move reads: the case and the named actor.
_MOVE_KEYS = (CASE_ID, PARTICIPANT_ACTOR_ID)


class _NamedParticipantInputs:
    """Reads the case and the actor a move names, and resolves its record.

    Mixed into both frames.  The record is the one the case's
    ``actor_participant_index`` keys by the actor (CM-19-003).
    """

    datalayer: CasePersistence | None
    case_id: str
    named_actor_id: str

    def _read_move_inputs(self) -> None:
        self.case_id = act_value(self, CASE_ID, str)  # type: ignore[arg-type]
        # Normalised where it is read (OID-01-006): the index is keyed by
        # the actor id as the roster spells it.
        self.named_actor_id = normalise_actor_id(
            act_value(self, PARTICIPANT_ACTOR_ID, str)  # type: ignore[arg-type]
        )

    def _named_record(self, case: VulnerabilityCase) -> CaseParticipant:
        """The stored record of the actor the move names, on *case*.

        Raises:
            VultronNotFoundError: The actor has no participant record on
                *case* (CM-31-004, CM-31-036).
        """
        assert self.datalayer is not None
        found = find_actor_participant(
            self.datalayer, case, self.named_actor_id
        )
        if found is None:
            raise VultronNotFoundError(
                "CaseParticipant",
                f"'{self.named_actor_id}' is not a participant of case"
                f" '{case.id_}'",
            )
        return found[1]


class ParticipantMoveGuardNode(
    _NamedParticipantInputs, DataLayerConditionWithPorts
):
    """Shared frame of the read-only removal and reinstatement guards.

    Resolves the case and the named actor's record, then hands the record to
    :meth:`_check`.  An actor with no record on the case fails the guard
    with a refusal reason; ``FAILURE`` is read by the handler as ``REFUSED``
    unless a subclass is the idempotency guard.  Read-only, so every
    subclass precedes the guarded commit (CLP-10-006).  *move* names the
    Case Owner act being judged, a removal (CM-31-004) or a reinstatement
    (CM-31-036), for the refusal reason.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        **act_key_ports(*_MOVE_KEYS),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return act_key_remappings(*_MOVE_KEYS)

    def __init__(
        self,
        name: str | None = None,
        move: ParticipantMove = "removal",
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.move: ParticipantMove = move

    def initialise(self) -> None:
        super().initialise()
        self._read_move_inputs()

    def _refuse(self, reason: str) -> Status:
        """Fail the guard with *reason*, read as ``REFUSED`` by the handler."""
        return fail_with_reason(
            self,
            f"{reason} — {self.move} REFUSED ({_MOVE_SPEC[self.move]})",
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1: the CASE_MANAGER holds its case
        try:
            record = self._named_record(case)
        except VultronNotFoundError:
            return self._refuse(
                f"'{self.named_actor_id}' is not a participant of case"
                f" '{self.case_id}'"
            )
        return self._check(record)

    def _check(self, record: CaseParticipant) -> Status:
        """Judge the resolved *record*; subclasses implement it."""
        raise NotImplementedError


class NamedParticipantIsNotProtectedNode(ParticipantMoveGuardNode):
    """Guard: the named actor holds neither ``CASE_MANAGER`` nor ``CASE_OWNER``.

    The CASE_MANAGER role is never unfilled (CM-02-014) and ownership is
    transferred before its holder can leave (CM-21), so a removal naming
    either is refused (CM-31-004).  A reinstatement naming either is refused
    too: neither can have been removed (CM-31-036).
    """

    def _check(self, record: CaseParticipant) -> Status:
        protected = sorted(r.name for r in PROTECTED_ROLES & set(record.roles))
        if not protected:
            return Status.SUCCESS
        return self._refuse(
            f"'{self.named_actor_id}' holds {', '.join(protected)} on case"
            f" '{self.case_id}', so the Case Owner cannot remove or"
            " reinstate it"
        )


class ParticipantNotYetRemovedNode(
    SilentIdempotencyGuardMixin, ParticipantMoveGuardNode
):
    """Idempotency guard: the named participant does not carry the removal fact.

    A removal of an already-removed participant is a legitimate no-op
    (CM-31-022, HP-01-014): this guard fails silently before the guarded
    commit, so the repeat commits no ledger entry (CLP-13-001), and the
    handler reads its ``FAILURE`` as ``SKIPPED``.  The first removal stands;
    the participant is not sent a second announcement.
    """

    def _check(self, record: CaseParticipant) -> Status:
        if not record.removed:
            return Status.SUCCESS
        self.feedback_message = (
            f"'{self.named_actor_id}' was already removed from case"
            f" '{self.case_id}' by '{record.removal_activity}'"
        )
        return self._idempotent_failure(
            self.logger,
            "%s: %s — skipping (CLP-13-001)",
            self.name,
            self.feedback_message,
        )


def case_manager_admits_removal_guard(
    case_id: str,
) -> py_trees.composites.Sequence:
    """Precondition guard: the CASE_MANAGER admits the removal.

    A read-only ``Sequence`` for the received tree's ``precondition_guards``
    (CLP-10-009).  The removal declares the manager path alone, so the
    guards run as the tree's own work, not as a path branch (HP-01-038):
    the CASE_MANAGER runs them in order, so a removal it refuses or skips
    leaves no ledger entry (CM-31-004, CM-31-022, CLP-13-001).
    """
    return py_trees.composites.Sequence(
        name="RemovalAdmissible",
        memory=False,
        children=[
            with_case_id(NamedParticipantIsNotProtectedNode(), case_id),
            with_case_id(ParticipantNotYetRemovedNode(), case_id),
        ],
    )


class ParticipantMoveEffectNode(
    _NamedParticipantInputs, DataLayerActionWithPorts, StateWriteCapable
):
    """Shared frame of the removal and reinstatement effects.

    Resolves the named actor's record on the case, hands it to
    :meth:`_apply`, and saves it when that changed it.  Runs after the
    guarded commit, so the entry's fan-out has already selected its
    recipients from the record as it stood before this write.  ``FAILURE``
    when the record is gone: the guards found it moments earlier in the
    CASE_MANAGER's own store (Regime 1, ADR-0087), so the handler reads it
    as an internal fault, never a refusal — the entry is already committed.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        **act_key_ports(*_MOVE_KEYS),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return act_key_remappings(*_MOVE_KEYS)

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    def initialise(self) -> None:
        super().initialise()
        self._read_move_inputs()

    def _apply(self, record: CaseParticipant) -> bool:
        """Write the move onto *record*; ``True`` when it changed it."""
        raise NotImplementedError

    def _log_applied(self, record: CaseParticipant) -> None:
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
            record = self._named_record(case)
        except VultronNotFoundError as exc:
            self.feedback_message = str(exc)
            self.logger.exception("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        if self._apply(record):
            self.datalayer.save(record)
        self._log_applied(record)
        return Status.SUCCESS


class RecordParticipantRemovalNode(
    ReceivedRequestInputMixin, ParticipantMoveEffectNode
):
    """Set the removal fact on the named participant (CM-31-001).

    Records the Case Owner's ``Remove`` activity, the received act on the
    blackboard, through :meth:`CaseParticipant.record_removal`.  The record
    stays in ``case_participants`` and ``actor_participant_index``
    (CM-19-002), with its status history and embargo consent rows untouched
    (CM-31-008); the case-level active check now finds it inert.  The
    replica apply node records the same fact from the ledger entry
    (CM-31-007).

    The entry's fan-out, selected before this write, still reaches the
    removed participant (CM-31-027).
    """

    def initialise(self) -> None:
        super().initialise()
        self._removal_id = self._received_request_id()

    def update(self) -> Status:
        if self._removal_id is None:
            # Read before any write, so the effect fails whole: the run
            # carries no received act to record (BT-HELPER-01).
            self.feedback_message = (
                f"{self.name}: no received Remove on this run to record as"
                " the removal fact"
            )
            self.logger.error("%s", self.feedback_message)
            return Status.FAILURE
        return super().update()

    def _apply(self, record: CaseParticipant) -> bool:
        assert self._removal_id is not None
        return record.record_removal(self._removal_id)

    def _log_applied(self, record: CaseParticipant) -> None:
        self.logger.info(
            "%s: removed '%s' (participant '%s') from active participation"
            " in case '%s' by '%s'; the record stays on the roster"
            " (CM-31-015)",
            self.name,
            self.named_actor_id,
            record.id_,
            self.case_id,
            record.removal_activity,
        )


class AnnounceParticipantMoveNode(EmitAnnounceAdmittedActNode):
    """Announce the Case Owner's admitted removal or reinstatement to its actor.

    The CASE_MANAGER's ``Announce(<the Owner's act>)`` to the actor the act
    names (ADR-0199): the actor the move concerns, which the entry's
    fan-out may not reach.  It replaces the separate unledgered notice
    (CM-31-006, CM-31-044).  The removed participant also receives the
    removal entry by fan-out (CM-31-027); the reinstated one receives its
    entry by the admission backfill (CM-10-006).  Its replica applies the
    entry, never the ``Announce`` (CM-31-029, CM-31-045).
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **EmitAnnounceAdmittedActNode.INPUT_PORTS,
        **act_key_ports(PARTICIPANT_ACTOR_ID),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            **super()._domain_port_remappings(),
            **act_key_remappings(PARTICIPANT_ACTOR_ID),
        }

    def _recipients(self) -> list[str]:
        return [normalise_actor_id(act_value(self, PARTICIPANT_ACTOR_ID, str))]


__all__ = [
    "PROTECTED_ROLES",
    "AnnounceParticipantMoveNode",
    "NamedParticipantIsNotProtectedNode",
    "ParticipantMove",
    "ParticipantMoveEffectNode",
    "ParticipantMoveGuardNode",
    "ParticipantNotYetRemovedNode",
    "RecordParticipantRemovalNode",
    "case_manager_admits_removal_guard",
]
