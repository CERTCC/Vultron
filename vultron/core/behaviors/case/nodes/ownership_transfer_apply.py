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

"""The CASE_MANAGER's application of an accepted ownership transfer (CM-21).

- :class:`AcceptCaseOwnershipTransferNode` — transfers ownership to a named
  actor.
- :class:`AcceptRecordedOwnershipOfferNode` — transfers ownership to the
  transferee of the Offer the CASE_MANAGER recorded (CM-21-011).

Both move ``CVDRole.CASE_OWNER`` and ``attributed_to`` in one atomic write
(CM-21-004), then commit each changed object as its own ledger entry
(CLP-07-013, ADR-0124).  Re-exported from ``ownership_transfer``.
"""

import logging
from typing import TYPE_CHECKING, Any, cast

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.behaviors.sync.commit_tree import commit_emitted_activity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.participant_semantic_types import (
    UPDATE_CASE_OWNER_SEMANTIC_TYPE,
    UPDATE_CASE_PARTICIPANT_SEMANTIC_TYPE,
)
from vultron.core.participants.ownership_offer import recorded_ownership_offer
from vultron.core.participants.recipients import listed_participant_record
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.sync_helpers import at_stored_position
from vultron.enums.roles import CVDRole
from vultron.errors import (
    VultronBTInternalError,
    VultronError,
    VultronNotFoundError,
)

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


class _TransferCaseOwnershipNode(DataLayerActionWithPorts, StateWriteCapable):
    """Apply an ownership-transfer acceptance to the case record.

    Enforces the at-most-one CASE_OWNER invariant atomically (CM-21-001,
    CM-21-004) by:

    1. Reading all objects that need mutation (case + affected participants).
    2. Applying all role changes in memory.
    3. Recording each changed object as its own CASE_MANAGER-authored ledger
       entry, after the ``Accept`` entry the commit tree wrote (CLP-07-013,
       ADR-0124): the previous owner's participant record, the new owner's,
       then the case.  Each entry is an ``Update`` carrying the object in
       full, so a replica copies it and derives nothing (CM-23-016).  The
       entries commit before the change is saved, so a change is never made
       without its entry: when the first entry cannot be built or committed,
       nothing changes.
    4. Saving every mutated object in a single ``save_many`` call so no
       partial state is ever visible to other readers (CM-21-004).

    The entries' ids derive from the act they follow, so a run that commits
    an entry its earlier run committed records nothing new (ID-04-004).
    Entries that commit while a later one fails stay recorded with the change
    unsaved; making the act and all its consequences commit as one is the
    trial-apply step of ADR-0124 (#4532).

    Specifically:

    * Removes ``CVDRole.CASE_OWNER`` from the previous owner's participant
      record (CM-21-003).
    * Updates ``VulnerabilityCase.attributed_to`` to the new owner's ID.
    * Adds ``CVDRole.CASE_OWNER`` to the new owner's participant record
      (CM-21-002).

    The previous owner retains all other roles and remains a case participant.
    Role-gated nodes (e.g. ``create_case_manager_gated_tree``) read
    ``CaseParticipant.case_roles`` — not ``attributed_to`` — so both fields
    must be kept in sync (CM-21-002).

    The entries are recorded in that order so no replica holds two owners
    between them (CM-21-001).  A previous owner whose record the case does
    not index is not changed, so it has no entry.  A new owner with no
    record is a fault, not a skip: the strip would leave the case with no
    ``CASE_OWNER`` holder at all, so the node raises before it changes
    anything (CM-21-001, CM-21-004).  The Accept's guards admit only an
    active transferee (CM-21-021), so reaching it means the store lost the
    record the guards read.

    Idempotent: when the case is already owned by the new owner, returns
    ``SUCCESS`` without mutation.

    Returns ``FAILURE`` when the DataLayer is unavailable or the case is not
    found, when the new owner cannot be named, or when an entry cannot be
    built or does not commit; ``SUCCESS`` otherwise.  A missing
    trigger-activity port raises before this node changes anything: without
    it no entry can be built (ARCH-15-001).  So does a new owner with no
    participant record (``VultronBTInternalError``, above).  The node is an effect of the
    received ``Accept``, so that entry is already committed by then.

    Subclasses name the new owner through :meth:`_new_owner_id`, and the act
    the entries follow through :meth:`_cause_id`.
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def _new_owner_id(self) -> str:
        """The actor that becomes the Case Owner.

        Raises:
            VultronNotFoundError: the new owner cannot be named.
        """
        raise NotImplementedError

    def _cause_id(self) -> str:
        """The act the consequence entries follow; their ids derive from it.

        One transfer's change to one object is one entry, so a re-run names
        the entry its first run committed (ID-04-004).
        """
        raise NotImplementedError

    def _read_case(self) -> Any | None:
        # Regime 1 (ADR-0087): canonical FAILURE feedback+log via the helper;
        # this method maps the failure to its None → caller-FAILURE contract.
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return None
        return case

    def _resolve_participant(
        self, actor_id: str, case: VulnerabilityCase
    ) -> CaseParticipant | None:
        """Return the ``CaseParticipant`` for *actor_id*, or ``None``.

        Read through the lookup the Accept's active-transferee guard uses
        (:func:`~vultron.core.participants.recipients.listed_participant_record`),
        so a record the guard admitted, stored or carried inline, is the one
        this node changes (CM-21-021).
        """
        assert self.datalayer is not None
        if actor_id not in case.actor_participant_index:
            self.logger.warning(
                "%s: actor '%s' not found in actor_participant_index for"
                " case '%s' — CVDRole.CASE_OWNER role update skipped",
                self.name,
                actor_id,
                self.case_id,
            )
            return None
        participant = listed_participant_record(case, self.datalayer, actor_id)
        if participant is None:
            self.logger.warning(
                "%s: actor '%s' has no CaseParticipant record in case '%s'"
                " — CVDRole.CASE_OWNER role update skipped",
                self.name,
                actor_id,
                self.case_id,
            )
            return None
        return participant

    def _require_new_owner(
        self, new_owner_id: str, case: VulnerabilityCase
    ) -> CaseParticipant:
        """Return the new owner's ``CaseParticipant``; there must be one.

        Raises:
            VultronBTInternalError: *case* holds no record for the new
                owner, so granting it ``CASE_OWNER`` is impossible and the
                strip would leave the case with no owner (CM-21-001).
        """
        participant = self._resolve_participant(new_owner_id, case)
        if participant is None:
            raise VultronBTInternalError(
                f"{self.name}: new owner '{new_owner_id}' has no"
                f" CaseParticipant record in case '{self.case_id}'; moving"
                " ownership would leave the case with no CASE_OWNER"
                " (CM-21-001, CM-21-004)"
            )
        return participant

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            self.logger.error("%s: DataLayer not available", self.name)
            return f
        try:
            new_owner_id = self._new_owner_id()
        except VultronNotFoundError as exc:
            self.feedback_message = f"{self.name}: no new owner to name: {exc}"
            self.logger.warning("%s", self.feedback_message)
            return Status.FAILURE
        return self._transfer(new_owner_id)

    def _transfer(self, new_owner_id: str) -> Status:
        case = self._read_case()
        if case is None:
            return Status.FAILURE

        current_owner_id = case.attributed_to
        if current_owner_id == new_owner_id:
            self.logger.info(
                "%s: case '%s' already owned by '%s' — skipping (idempotent)",
                self.name,
                self.case_id,
                new_owner_id,
            )
            return Status.SUCCESS

        # Every change gets an entry, so the port that builds them must be
        # here before anything is changed (CLP-07-013).
        trigger_activity = self._require_trigger_activity_port()

        # --- Read phase: collect every object that must change ---------------
        to_save: list[Any] = []

        old_participant: CaseParticipant | None = None
        if current_owner_id is not None:
            old_participant = self._resolve_participant(current_owner_id, case)

        new_participant = self._require_new_owner(new_owner_id, case)

        # --- Mutate phase: all changes in memory, nothing written yet --------

        # CM-21-003: strip CASE_OWNER from the previous owner.
        if old_participant is not None:
            old_participant.remove_role(CVDRole.CASE_OWNER)
            to_save.append(old_participant)
            self.logger.info(
                "%s: will remove CVDRole.CASE_OWNER from participant '%s'"
                " (case '%s') — CM-21-003",
                self.name,
                case.actor_participant_index.get(current_owner_id),
                self.case_id,
            )

        # CM-21-002: update attributed_to.

        case.attributed_to = new_owner_id  # type: ignore[assignment]
        to_save.append(case)

        # CM-21-002: grant CASE_OWNER to the new owner.
        new_participant.add_role(CVDRole.CASE_OWNER)
        to_save.append(new_participant)
        self.logger.info(
            "%s: will grant CVDRole.CASE_OWNER to participant '%s'"
            " (case '%s') — CM-21-002",
            self.name,
            new_participant.id_,
            self.case_id,
        )

        # --- Record phase: one entry per changed object, before the change
        # is saved (CLP-07-013) ---------------------------------------------
        try:
            self._record_consequences(
                trigger_activity,
                [p for p in (old_participant, new_participant) if p],
                case,
            )
        except (RuntimeError, VultronError) as exc:
            self.feedback_message = f"{self.name}: {exc}"
            self.logger.exception("%s", self.feedback_message)
            return Status.FAILURE

        # --- Save phase: single atomic transaction (CM-21-004) ---------------
        # Saved at the position the commits above moved it to (SYNC-16-005).
        self.datalayer.save_many(  # type: ignore[union-attr]
            [
                (
                    at_stored_position(
                        obj, cast(CaseOutboxPersistence, self.datalayer)
                    )
                    if isinstance(obj, VulnerabilityCase)
                    else obj
                )
                for obj in to_save
            ]
        )
        self.logger.info(
            "%s: atomically transferred ownership of case '%s' from '%s'"
            " to '%s' (%d object(s) saved) — CM-21-004",
            self.name,
            self.case_id,
            current_owner_id,
            new_owner_id,
            len(to_save),
        )
        return Status.SUCCESS

    def _record_consequences(
        self,
        trigger_activity: "TriggerActivityPort",
        participants: list[CaseParticipant],
        case: VulnerabilityCase,
    ) -> None:
        """Commit each changed participant record, then the changed *case*.

        Raises:
            RuntimeError: an entry did not commit (see
                :func:`~vultron.core.behaviors.sync.commit_tree.commit_emitted_activity`).
            VultronError: an entry could not be built.
        """
        actor_id = cast(str, self.actor_id)
        cause_id = self._cause_id()
        for participant in participants:
            self._commit(
                UPDATE_CASE_PARTICIPANT_SEMANTIC_TYPE,
                trigger_activity.record_case_participant_updated(
                    participant=participant,
                    case_id=self.case_id,
                    actor=actor_id,
                    cause_id=cause_id,
                ),
            )
        # The participant entries moved the case's position; the case entry
        # carries the case at the position before it (SYNC-16-005).
        self._commit(
            UPDATE_CASE_OWNER_SEMANTIC_TYPE,
            trigger_activity.record_case_owner_updated(
                case=at_stored_position(
                    case, cast(CaseOutboxPersistence, self.datalayer)
                ),
                actor=actor_id,
                cause_id=cause_id,
            ),
        )

    def _commit(self, semantic_type: str, built: tuple[str, str]) -> None:
        """Commit one built ``(activity_id, sealed_blob)`` as *semantic_type*."""
        activity_id, blob = built
        commit_emitted_activity(
            datalayer=cast(CaseOutboxPersistence, self.datalayer),
            actor_id=cast(str, self.actor_id),
            case_id=self.case_id,
            activity_id=activity_id,
            activity_blob=blob,
            semantic_type=semantic_type,
        )


class AcceptCaseOwnershipTransferNode(_TransferCaseOwnershipNode):
    """Transfer the case's ownership to a named actor (CM-21-001 – CM-21-004).

    *cause_id* names the act the transfer answers, from which the
    consequence entries' ids derive (see :meth:`_cause_id`).
    """

    def __init__(
        self,
        case_id: str,
        new_owner_id: str,
        cause_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(case_id=case_id, name=name)
        self.new_owner_id = new_owner_id
        self.cause_id = cause_id

    def _new_owner_id(self) -> str:
        return self.new_owner_id

    def _cause_id(self) -> str:
        return self.cause_id


class AcceptRecordedOwnershipOfferNode(_TransferCaseOwnershipNode):
    """Transfer the case's ownership to the transferee of a recorded Offer.

    The new owner is read from the ownership-transfer Offer the CASE_MANAGER
    made and recorded, which *offer_id* names (CM-21-005), never from the
    sender of the Accept (CM-21-011).  Runs only
    at the CASE_MANAGER, so the executing actor is the Offer's issuer.  The
    consequence entries follow the Offer the Accept names.
    """

    def __init__(
        self,
        case_id: str,
        offer_id: str | None,
        name: str | None = None,
    ) -> None:
        super().__init__(case_id=case_id, name=name)
        self.offer_id = offer_id

    def _new_owner_id(self) -> str:
        assert self.datalayer is not None
        if self.offer_id is None or self.actor_id is None:
            raise VultronNotFoundError(
                "Ownership-transfer Offer", str(self.offer_id)
            )
        return recorded_ownership_offer(
            self.datalayer, self.case_id, self.offer_id
        ).transferee_id

    def _cause_id(self) -> str:
        # _new_owner_id already refused an Accept naming no Offer.
        return cast(str, self.offer_id)


__all__ = [
    "AcceptCaseOwnershipTransferNode",
    "AcceptRecordedOwnershipOfferNode",
    "_TransferCaseOwnershipNode",
]
