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
- :class:`EmitAcceptCaseOwnershipTransferNode` — emits
  ``Accept(Offer(VulnerabilityCase))`` from the accepting actor back to
  the offering actor.
- :class:`AcceptCaseOwnershipTransferNode` — applies the accepted
  ownership transfer to the DataLayer: updates ``case.attributed_to``
  and grants ``CVDRole.CASE_OWNER`` to the new owner's participant record.
- :class:`ForwardOfferToTransfereeNode` — CaseActor-only effect node that
  builds a new ``Offer(VulnerabilityCase)`` addressed to the transferee and
  queues it in the CaseActor's outbox (CM-21-005, ADR-0053).

These leaf nodes are assembled into trigger/receive trees in the parent
``actor_trigger_trees.py`` and ``ownership_transfer_tree.py`` modules per
BTND-07-003.
"""

import logging
from typing import Any, cast

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    _EmitSingleActivityBase,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models._helpers import _as_id
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.use_cases._helpers import _resolve_case_manager_id
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)


class EmitOfferCaseOwnershipTransferNode(_EmitSingleActivityBase):
    """Emit ``Offer(VulnerabilityCase)`` (ownership transfer) to ``transferee_id``.

    Calls ``trigger_activity_factory.offer_case_ownership_transfer()`` with
    ``actor=self.actor_id``, ``case_id``, and ``transferee_id``, then queues
    the resulting activity in the actor's outbox (TRIG-11-001).
    """

    def __init__(
        self,
        case_id: str,
        transferee_id: str,
        content: str | None = None,
        attributed_to: str | None = None,
        captured: dict | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(captured=captured, name=name)
        self.case_id = case_id
        self.transferee_id = transferee_id
        self.content = content
        self.attributed_to = attributed_to

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
            cm_id = _resolve_case_manager_id(case, self.datalayer)
            if cm_id:
                case_actor_id = [cm_id]
        return self.trigger_activity_factory.offer_case_ownership_transfer(
            actor=self.actor_id,
            case_id=self.case_id,
            transferee_id=self.transferee_id,
            content=self.content,
            to=case_actor_id,
            attributed_to=self.attributed_to,
        )

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        self.logger.info(
            "Actor '%s' offered case ownership transfer for case '%s' to '%s'",
            self.actor_id,
            self.case_id,
            self.transferee_id,
        )


class EmitAcceptCaseOwnershipTransferNode(_EmitSingleActivityBase):
    """Emit ``Accept(Offer(VulnerabilityCase))`` (ownership transfer) to offerer.

    Calls ``trigger_activity_factory.accept_case_ownership_transfer()``
    with ``actor=self.actor_id`` and ``offer_id``, then queues the resulting
    activity in the actor's outbox (TRIG-11-002).
    """

    def __init__(
        self,
        offer_id: str,
        case_id: str,
        captured: dict | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(captured=captured, name=name)
        self.offer_id = offer_id
        self.case_id = case_id

    def _call_factory(self) -> tuple[str, str]:
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        assert self.datalayer is not None
        # Regime 3 (ADR-0087): optional addressing enrichment only — a missing
        # local case leaves `to=None` and the Accept is still emitted. Unguarded
        # by design (conformance allowlist).
        case = self.datalayer.read_case(self.case_id)
        case_actor_id: list[str] | None = None
        if case is not None:
            cm_id = _resolve_case_manager_id(case, self.datalayer)
            if cm_id:
                case_actor_id = [cm_id]
        return self.trigger_activity_factory.accept_case_ownership_transfer(
            actor=self.actor_id,
            offer_id=self.offer_id,
            to=case_actor_id,
        )

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        self.logger.info(
            "Actor '%s' accepted case ownership transfer offer '%s'",
            self.actor_id,
            self.offer_id,
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
    """

    def __init__(
        self,
        case_id: str,
        transferee_id: str,
        original_actor_id: str,
        captured: dict | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(captured=captured, name=name)
        self.case_id = case_id
        self.transferee_id = transferee_id
        self.original_actor_id = original_actor_id

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
            cast(CaseOutboxPersistence, self.datalayer).outbox_append(
                activity_id
            )
        except Exception as e:
            self.feedback_message = f"ForwardOfferToTransfereeNode failed: {e}"
            self.logger.error(self.feedback_message)
            return Status.FAILURE
        self._on_success(activity_id, activity_blob)
        return Status.SUCCESS

    def _call_factory(self) -> tuple[str, str]:
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        return self.trigger_activity_factory.offer_case_ownership_transfer(
            case_id=self.case_id,
            transferee_id=self.transferee_id,
            actor=self.actor_id,
            to=[self.transferee_id],
            attributed_to=self.original_actor_id,
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


class AcceptCaseOwnershipTransferNode(DataLayerActionWithPorts):
    """Apply an ownership-transfer acceptance to the case record.

    Enforces the at-most-one CASE_OWNER invariant atomically (CM-21-001,
    CM-21-004) by:

    1. Reading all objects that need mutation (case + affected participants).
    2. Applying all role changes in memory.
    3. Committing every mutated object in a single ``save_many`` call so
       no partial state is ever visible to other readers.

    Specifically:

    * Removes ``CVDRole.CASE_OWNER`` from the previous owner's participant
      record (CM-21-003).
    * Updates ``VulnerabilityCase.attributed_to`` to the new owner's ID.
    * Adds ``CVDRole.CASE_OWNER`` to the new owner's participant record
      (CM-21-002).

    The previous owner retains all other roles and remains a case participant.
    Role-gated nodes (e.g. :class:`PublicDisclosureBranchNode`) read
    ``CaseParticipant.case_roles`` — not ``attributed_to`` — so both fields
    must be kept in sync (CM-21-002).

    Idempotent: when the case is already owned by ``new_owner_id``, returns
    ``SUCCESS`` without mutation.

    Returns ``FAILURE`` when the DataLayer is unavailable or the case is not
    found; ``SUCCESS`` otherwise.
    """

    def __init__(
        self,
        case_id: str,
        new_owner_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.new_owner_id = new_owner_id

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

        case = self._read_case()
        if case is None:
            return Status.FAILURE

        current_owner_id = _as_id(case.attributed_to)
        if current_owner_id == self.new_owner_id:
            self.logger.info(
                "%s: case '%s' already owned by '%s' — skipping (idempotent)",
                self.name,
                self.case_id,
                self.new_owner_id,
            )
            return Status.SUCCESS

        # --- Read phase: collect every object that must change ---------------
        to_save: list[Any] = []

        old_participant: CaseParticipant | None = None
        if current_owner_id is not None:
            old_participant = self._resolve_participant(current_owner_id, case)

        new_participant = self._resolve_participant(self.new_owner_id, case)

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

        case.attributed_to = self.new_owner_id  # type: ignore[assignment]
        to_save.append(case)

        # CM-21-002: grant CASE_OWNER to the new owner.
        if new_participant is not None:
            new_participant.add_role(CVDRole.CASE_OWNER)
            to_save.append(new_participant)
            self.logger.info(
                "%s: will grant CVDRole.CASE_OWNER to participant '%s'"
                " (case '%s') — CM-21-002",
                self.name,
                case.actor_participant_index.get(self.new_owner_id),
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
            self.new_owner_id,
            len(to_save),
        )

        return Status.SUCCESS
