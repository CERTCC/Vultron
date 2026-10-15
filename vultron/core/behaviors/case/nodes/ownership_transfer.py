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

"""Trigger-side emit nodes and receive-side application nodes for the
ownership-transfer workflow (TRIG-11 / OT-02).

Provides:

- :class:`EmitOfferCaseOwnershipTransferNode` — emits
  ``Offer(VulnerabilityCase)`` (ownership transfer variant) from the
  offering actor to the specified transferee.
- :class:`EmitAcceptCaseOwnershipTransferNode`,
  :class:`EmitRejectCaseOwnershipTransferNode` and
  :class:`EmitWithdrawCaseOwnershipTransferNode` — the replies to an Offer,
  defined in ``ownership_offer_reply_emit.py`` and re-exported here.
- :class:`AcceptCaseOwnershipTransferNode` — applies the accepted
  ownership transfer to the DataLayer: updates ``case.attributed_to``,
  moves ``CVDRole.CASE_OWNER`` to the new owner's participant record, and
  commits each changed object as its own ledger entry (CLP-07-013).
- :class:`ForwardOfferToTransfereeNode` — CaseActor-only effect node that
  builds a new ``Offer(VulnerabilityCase)`` addressed to the transferee and
  queues it in the CaseActor's outbox (CM-21-005, ADR-0053).

These leaf nodes are assembled into trigger/receive trees in the parent
``actor_trigger_trees.py`` and ``ownership_transfer_tree.py`` modules per
BTND-07-003.
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from py_trees.common import Status

from vultron.core.behaviors.case.nodes.ownership_offer_reply_emit import (
    EmitAcceptCaseOwnershipTransferNode,
    EmitRejectCaseOwnershipTransferNode,
    EmitWithdrawCaseOwnershipTransferNode,
)
from vultron.core.behaviors.delegated_authorship import delegated_authorship
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    _EmitSingleActivityBase,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.behaviors.sync.commit_tree import commit_emitted_activity
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.participant_event_types import (
    UPDATE_CASE_OWNER_EVENT_TYPE,
    UPDATE_CASE_PARTICIPANT_EVENT_TYPE,
)
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.participants.ownership_offer import recorded_ownership_offer
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.enums.roles import CVDRole
from vultron.errors import VultronNotFoundError

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


class EmitOfferCaseOwnershipTransferNode(_EmitSingleActivityBase):
    """Emit ``Offer(VulnerabilityCase)`` (ownership transfer) to ``transferee_id``.

    Calls ``trigger_activity_factory.offer_case_ownership_transfer()`` with
    ``actor=self.actor_id``, ``case_id``, and ``transferee_id``, then queues
    the resulting activity in the actor's outbox (TRIG-11-001).  An
    ``end_time`` becomes the Offer's activity-level ``end_time``, the deadline
    to answer it (TRIG-11-007, CM-21-016); without one the Offer carries none.
    """

    def __init__(
        self,
        case_id: str,
        transferee_id: str,
        requesting_actor_id: str,
        content: str | None = None,
        captured: dict | None = None,
        name: str | None = None,
        end_time: datetime | None = None,
    ) -> None:
        super().__init__(captured=captured, name=name)
        self.case_id = case_id
        self.transferee_id = transferee_id
        self.content = content
        self.requesting_actor_id = requesting_actor_id
        self.end_time = end_time

    def _call_factory(self) -> tuple[str, str]:
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        assert self.datalayer is not None
        # Regime 3 (ADR-0087): the case is optional addressing enrichment, not
        # coordination state — a missing local case just leaves `to=None` (the
        # factory tolerates it); the Offer is still emitted. Unguarded by design
        # (conformance allowlist).
        case = self.datalayer.read_case(self.case_id)
        case_actor_id: list[str] | None = None
        if case is not None:
            cm_id = resolve_case_manager_id(case, self.datalayer)
            if cm_id:
                case_actor_id = [cm_id]
        authorship = delegated_authorship(
            doing_actor_id=self.actor_id,
            requesting_actor_id=self.requesting_actor_id,
        )
        return self.trigger_activity_factory.offer_case_ownership_transfer(
            actor=authorship.actor,
            case_id=self.case_id,
            transferee_id=self.transferee_id,
            content=self.content,
            to=case_actor_id,
            attributed_to=authorship.attributed_to,
            end_time=self.end_time,
        )

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        self.logger.info(
            "Actor '%s' offered case ownership transfer for case '%s' to '%s'",
            self.actor_id,
            self.case_id,
            self.transferee_id,
        )


class ForwardOfferToTransfereeNode(_EmitSingleActivityBase):
    """CaseActor effect node: build and enqueue a forwarded ownership-transfer Offer.

    Implements CM-21-005 / ADR-0053: after the CaseActor records the ledger
    entry for an incoming ``Offer(VulnerabilityCase)``, it MUST forward a new
    ``Offer(VulnerabilityCase, actor=case_actor, attributed_to=original_offerer,
    to=[transferee])`` to the transferee's inbox via the CaseActor's own outbox.

    Must be wrapped in ``create_case_manager_gated_tree`` so that non-CaseManager
    actors skip this node cleanly (they should never forward the offer).

    Logs WARNING and returns FAILURE when ``trigger_activity_factory`` is absent
    from the blackboard — this leaves all outboxes untouched.

    The forward carries the received Offer's ``end_time``, so the transferee,
    which holds and answers the forward, knows its deadline (CM-21-016).  The
    forward is an activity this node mints, so its timestamps serialise in
    UTC (CS-13-005); the received Offer's own offset stays on its ledger
    entry.
    """

    def __init__(
        self,
        case_id: str,
        transferee_id: str,
        original_actor_id: str,
        captured: dict | None = None,
        name: str | None = None,
        end_time: datetime | None = None,
    ) -> None:
        super().__init__(captured=captured, name=name)
        self.case_id = case_id
        self.transferee_id = transferee_id
        self.original_actor_id = original_actor_id
        self.end_time = end_time

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        if self.trigger_activity_factory is None:
            self.logger.warning(
                "%s: no trigger_activity port — cannot forward offer"
                " to transferee (CM-21-005)",
                self.name,
            )
            return Status.FAILURE
        try:
            activity_id, activity_blob = self._call_factory()
            self._emit_through_seam(activity_id, activity_blob)
        except Exception as e:  # noqa: BLE001  # ruff-baseline #3768
            self.feedback_message = f"ForwardOfferToTransfereeNode failed: {e}"
            self.logger.error("%s", self.feedback_message)  # noqa: TRY400  # ruff-baseline #3353
            return Status.FAILURE
        self._on_success(activity_id, activity_blob)
        return Status.SUCCESS

    def _call_factory(self) -> tuple[str, str]:
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        authorship = delegated_authorship(
            doing_actor_id=self.actor_id,
            requesting_actor_id=self.original_actor_id,
        )
        return self.trigger_activity_factory.offer_case_ownership_transfer(
            case_id=self.case_id,
            transferee_id=self.transferee_id,
            actor=authorship.actor,
            to=[self.transferee_id],
            attributed_to=authorship.attributed_to,
            end_time=self.end_time,
        )

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        self.logger.info(
            "%s: CaseActor '%s' forwarded ownership-transfer offer '%s'"
            " to transferee '%s' (CM-21-005)",
            self.name,
            self.actor_id,
            activity_id,
            self.transferee_id,
        )


class _TransferCaseOwnershipNode(DataLayerActionWithPorts, StateWriteCapable):
    """Apply an ownership-transfer acceptance to the case record.

    Enforces the at-most-one CASE_OWNER invariant atomically (CM-21-001,
    CM-21-004) by:

    1. Reading all objects that need mutation (case + affected participants).
    2. Applying all role changes in memory.
    3. Committing every mutated object in a single ``save_many`` call so
       no partial state is ever visible to other readers.
    4. Recording each changed object as its own CASE_MANAGER-authored ledger
       entry, after the ``Accept`` entry the commit tree wrote (CLP-07-013,
       ADR-0124): the previous owner's participant record, the new owner's,
       then the case.  Each entry is an ``Update`` carrying the object in
       full, so a replica copies it and derives nothing (CM-23-016).

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
    between them (CM-21-001).  A participant record the case does not index
    is not changed, so it has no entry.

    Idempotent: when the case is already owned by the new owner, returns
    ``SUCCESS`` without mutation.

    Returns ``FAILURE`` when the DataLayer is unavailable or the case is not
    found, when the new owner cannot be named, or when an entry does not
    commit; ``SUCCESS`` otherwise.  A missing trigger-activity port raises
    before anything is written: without it no entry can be built
    (ARCH-15-001).

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
        """Return the ``CaseParticipant`` for *actor_id*, or ``None``."""
        assert self.datalayer is not None
        participant_id = case.actor_participant_index.get(actor_id)
        if participant_id is None:
            self.logger.warning(
                "%s: actor '%s' not found in actor_participant_index for"
                " case '%s' — CVDRole.CASE_OWNER role update skipped",
                self.name,
                actor_id,
                self.case_id,
            )
            return None
        participant = self.datalayer.read(participant_id)
        if not isinstance(participant, CaseParticipant):
            self.logger.warning(
                "%s: actor '%s' has no CaseParticipant record in case '%s'"
                " — CVDRole.CASE_OWNER role update skipped",
                self.name,
                actor_id,
                self.case_id,
            )
            return None
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

        current_owner_id = _as_id(case.attributed_to)
        if current_owner_id == new_owner_id:
            self.logger.info(
                "%s: case '%s' already owned by '%s' — skipping (idempotent)",
                self.name,
                self.case_id,
                new_owner_id,
            )
            return Status.SUCCESS

        # Every change gets an entry, so the port that builds them must be
        # here before anything is written (CLP-07-013).
        trigger_activity = self._require_trigger_activity_port()

        # --- Read phase: collect every object that must change ---------------
        to_save: list[Any] = []

        old_participant: CaseParticipant | None = None
        if current_owner_id is not None:
            old_participant = self._resolve_participant(current_owner_id, case)

        new_participant = self._resolve_participant(new_owner_id, case)

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
        if new_participant is not None:
            new_participant.add_role(CVDRole.CASE_OWNER)
            to_save.append(new_participant)
            self.logger.info(
                "%s: will grant CVDRole.CASE_OWNER to participant '%s'"
                " (case '%s') — CM-21-002",
                self.name,
                case.actor_participant_index.get(new_owner_id),
                self.case_id,
            )

        # --- Commit phase: single atomic transaction (CM-21-004) -------------
        self.datalayer.save_many(to_save)  # type: ignore[union-attr]
        self.logger.info(
            "%s: atomically transferred ownership of case '%s' from '%s'"
            " to '%s' (%d object(s) saved) — CM-21-004",
            self.name,
            self.case_id,
            current_owner_id,
            new_owner_id,
            len(to_save),
        )

        # --- Record phase: one entry per changed object (CLP-07-013) ---------
        try:
            self._record_consequences(
                trigger_activity,
                [p for p in (old_participant, new_participant) if p],
            )
        except RuntimeError as exc:
            self.feedback_message = f"{self.name}: {exc}"
            self.logger.exception("%s", self.feedback_message)
            return Status.FAILURE
        return Status.SUCCESS

    def _record_consequences(
        self,
        trigger_activity: "TriggerActivityPort",
        participants: list[CaseParticipant],
    ) -> None:
        """Commit each changed participant record, then the case.

        Raises:
            RuntimeError: an entry did not commit (see
                :func:`~vultron.core.behaviors.sync.commit_tree.commit_emitted_activity`).
        """
        actor_id = cast(str, self.actor_id)
        cause_id = self._cause_id()
        for participant in participants:
            self._commit(
                UPDATE_CASE_PARTICIPANT_EVENT_TYPE,
                trigger_activity.record_case_participant_updated(
                    participant=participant,
                    case_id=self.case_id,
                    actor=actor_id,
                    cause_id=cause_id,
                ),
            )
        self._commit(
            UPDATE_CASE_OWNER_EVENT_TYPE,
            trigger_activity.record_case_owner_updated(
                case_id=self.case_id, actor=actor_id, cause_id=cause_id
            ),
        )

    def _commit(self, event_type: str, built: tuple[str, str]) -> None:
        """Commit one built ``(activity_id, sealed_blob)`` as *event_type*."""
        activity_id, blob = built
        commit_emitted_activity(
            datalayer=cast(CaseOutboxPersistence, self.datalayer),
            actor_id=cast(str, self.actor_id),
            case_id=self.case_id,
            activity_id=activity_id,
            activity_blob=blob,
            event_type=event_type,
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
    recorded, which *offer_id* names directly or through its forward
    (CM-21-005), never from the sender of the Accept (CM-21-011).  Runs only
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
            self.datalayer, self.case_id, self.offer_id, self.actor_id
        ).transferee_id

    def _cause_id(self) -> str:
        # _new_owner_id already refused an Accept naming no Offer.
        return cast(str, self.offer_id)


__all__ = [
    "AcceptCaseOwnershipTransferNode",
    "AcceptRecordedOwnershipOfferNode",
    "EmitAcceptCaseOwnershipTransferNode",
    "EmitOfferCaseOwnershipTransferNode",
    "EmitRejectCaseOwnershipTransferNode",
    "EmitWithdrawCaseOwnershipTransferNode",
    "ForwardOfferToTransfereeNode",
]
