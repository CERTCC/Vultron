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

"""
CaseParticipantRole delegation action nodes for case behavior trees (ADR-0039).

Provides the nodes of the role delegation workflow (CM-33): the CASE_MANAGER's
forward of a recorded role Offer to its target, the target's check that it is
the actor the Offer names, and the target's Accept or Reject, addressed to the
CASE_MANAGER.

See SE-08-003, ADR-0039.
"""

import logging
from collections.abc import Callable
from typing import ClassVar, cast

from py_trees.common import Status

from vultron.core.behaviors.delegated_authorship import delegated_authorship
from vultron.core.behaviors.helpers import (
    DataLayerAction,
    DataLayerConditionWithPorts,
    _EmitSingleActivityBase,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.behaviors.sync.nodes.role_grant_effect import (
    grant_role_to_target,
)
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.protocol_pair import (
    ACCEPT_CASE_PARTICIPANT_ROLE_EVENT_TYPE,
    REJECT_CASE_PARTICIPANT_ROLE_EVENT_TYPE,
)
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.participants.role_offer import role_offer_forward_id
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.predicates.addressing import same_actor_id
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)


class ForwardRoleOfferToTargetNode(_EmitSingleActivityBase):
    """CASE_MANAGER effect: forward a recorded role Offer to its target.

    After the CASE_MANAGER commits the ``offer_case_participant_role`` entry
    for the Case Owner's Offer, it sends the target a new
    ``Offer(CaseParticipantRole)`` naming the same role, target and case
    (CM-33-001).  ``actor`` and ``attributed_to`` come from the delegated-
    authorship helper: the CASE_MANAGER forwards, on the Case Owner's behalf
    (CM-24-005).  The forward is addressed to the target only and carries
    ``in_reply_to`` set to the recorded Offer's id (the entry's
    ``log_object_id``), so an answer naming the forward resolves to the Offer
    it stands for (CM-33-005).

    The forward's id derives from the recorded Offer
    (:func:`~vultron.core.participants.role_offer.role_offer_forward_id`), so
    the guard can tell whether a redelivered Offer was already forwarded
    (OX-06-002).  It is not ledgered on its own: the entry it follows records
    the Offer.

    A ``manager_effects`` entry, so it runs only at the CASE_MANAGER
    (BT-17-008).  It runs after the commit, so a fault building or queuing
    the forward is the CASE_MANAGER's, never a refusal of the sender: it is
    not caught, and escapes to ``BTBridge`` as an internal error
    (ARCH-15-001).  A redelivery of the Offer then sends the forward, the
    commit reusing the recorded entry; a redelivery after the forward was
    stored sends nothing
    (:class:`~vultron.core.behaviors.case.nodes.role_offer_guard.RoleOfferAdmissibleNode`).
    Only a missing factory returns FAILURE, a wiring fault the handler also
    raises on.
    """

    def __init__(
        self,
        case_id: str,
        role: CVDRole,
        target_actor_id: str,
        offer_id: str,
        owner_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name)
        self.case_id = case_id
        self.role = role
        self.target_actor_id = target_actor_id
        self.offer_id = offer_id
        self.owner_id = owner_id

    def _call_factory(self) -> tuple[str, str]:
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        authorship = delegated_authorship(
            doing_actor_id=self.actor_id, requesting_actor_id=self.owner_id
        )
        return self.trigger_activity_factory.offer_case_participant_role(
            case_id=self.case_id,
            role=self.role,
            target_actor_id=self.target_actor_id,
            actor=authorship.actor,
            to=[self.target_actor_id],
            attributed_to=authorship.attributed_to,
            in_reply_to=self.offer_id,
            id_=role_offer_forward_id(
                self.actor_id, self.case_id, self.offer_id
            ),
        )

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        if (f := self._require_factory()) is not None:
            self.logger.error("%s", self.feedback_message)
            return f
        # Not caught: see the class docstring.
        activity_id, activity_blob = self._call_factory()
        self._emit_through_seam(activity_id, activity_blob)
        self._on_success(activity_id, activity_blob)
        return Status.SUCCESS

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        self.logger.info(
            "%s: CASE_MANAGER '%s' forwarded role offer '%s' (%s) to '%s'"
            " in reply to recorded offer '%s' from '%s' (CM-33-001)",
            self.name,
            self.actor_id,
            activity_id,
            self.role.value,
            self.target_actor_id,
            self.offer_id,
            self.owner_id,
        )


class IsRoleOfferTargetNode(DataLayerConditionWithPorts):
    """Condition: the executing actor is the target the role Offer names.

    Only the target answers a role Offer (CM-33-004), so the answer speaks
    for the executing actor (BT-17-008).  Any other actor that holds the
    Offer, at the door already shown to be one it is addressed to, refuses it
    with no answer sent.
    """

    def __init__(self, target_actor_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.target_actor_id = target_actor_id

    def update(self) -> Status:
        if self.actor_id is not None and same_actor_id(
            self.actor_id, self.target_actor_id
        ):
            return Status.SUCCESS
        self.feedback_message = (
            f"'{self.actor_id}' is not the target '{self.target_actor_id}'"
            " of the role Offer — not answered here (CM-33-004)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


class _AnswerCaseParticipantRoleOfferBase(_EmitSingleActivityBase):
    """Send the target's answer to an ``Offer(CaseParticipantRole)`` (ADR-0039).

    The one shape both arms of the ``AcceptOrReject`` Selector share.  The
    answer goes to the case's CASE_MANAGER only, resolved from the case,
    never to the Offer's ``actor`` or to the Case Owner that made it
    (CM-33-004, PCR-08-001, PCR-08-011).  The answer's id derives from the
    Offer it answers (OX-06-002), so a retry rebuilds the same answer, which
    the outbox does not queue twice.

    The target is a participant, never the CASE_MANAGER (the CASE_MANAGER
    refuses an Offer that names itself), and a participant never commits
    (CLP-09-001): its answer goes out with no entry in its own ledger, and
    this node tries no commit.  The CASE_MANAGER commits the answer on
    receipt and announces the entry (CM-33-006,
    ``vultron.core.behaviors.case.role_offer_answer_tree``).

    The outbox write is not caught: once the answer is queued a FAILURE would
    let the Selector send the contradictory answer after it, so a fault
    escapes to ``BTBridge`` as an internal error (BT-14-001, ARCH-15-001).
    Only a missing input, a case this store does not hold, a case that names
    no CASE_MANAGER, or a factory error returns FAILURE, before anything is
    written.

    ``vendor_id`` is the sender of the Offer being answered, which the port
    rebuilds as the ``actor`` of the Offer the answer carries.  At the target
    that sender is the CASE_MANAGER whose forward it answers (CM-33-004), not
    the Case Owner that made the Offer; the name is the port's.

    Subclasses set ``_EVENT_TYPE`` (the kind label of the derived id) and
    ``_ANSWER`` (for logs), and implement :meth:`_factory_method`.
    """

    _EVENT_TYPE: ClassVar[str]
    _ANSWER: ClassVar[str]

    def __init__(
        self,
        offer_id: str,
        case_id: str,
        role: CVDRole,
        target_actor_id: str,
        vendor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name)
        self.offer_id = offer_id
        self.case_id = case_id
        self.role = role
        self.target_actor_id = target_actor_id
        self.vendor_id = vendor_id
        self._case_manager_id: str | None = None

    def _factory_method(self) -> Callable[..., tuple[str, str]]:
        """The ``TriggerActivityPort`` method that builds this answer."""
        raise NotImplementedError

    def _call_factory(self) -> tuple[str, str]:
        assert self.actor_id is not None
        assert (
            self._case_manager_id is not None
        )  # resolved by _validate_context
        return self._factory_method()(
            offer_id=self.offer_id,
            case_id=self.case_id,
            role=self.role,
            target_actor_id=self.target_actor_id,
            vendor_id=self.vendor_id,
            actor=self.actor_id,
            to=[self._case_manager_id],
            id_=derived_activity_id(
                self._EVENT_TYPE, self.actor_id, self.case_id, self.offer_id
            ),
        )

    def _validate_context(self) -> Status | None:
        if (f := self._require_datalayer_and_actor()) is not None:
            self.logger.error(
                "%s: DataLayer or actor_id not available", self.name
            )
            return f
        if (f := self._require_factory()) is not None:
            self.logger.warning(
                "%s: factory unavailable — cannot answer offer '%s'",
                self.name,
                self.offer_id,
            )
            return f
        if not self.case_id or not self.target_actor_id:
            self.logger.warning(
                "%s: missing case_id/target_actor_id for offer '%s' — skip",
                self.name,
                self.offer_id,
            )
            return Status.FAILURE
        # Resolved before anything is written (Regime 1, ADR-0087): the
        # answer goes to the case's CASE_MANAGER or nowhere (PCR-08-011).
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure
        self._case_manager_id = resolve_case_manager_id(
            case, cast(CasePersistence, self.datalayer)
        )
        if self._case_manager_id is None:
            self.feedback_message = (
                f"case '{self.case_id}' names no CASE_MANAGER — cannot"
                f" answer role offer '{self.offer_id}' (PCR-08-011)"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        return None

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        self.logger.info(
            "%s: '%s' answered offer '%s' with %s '%s' to the CASE_MANAGER"
            " '%s'",
            self.name,
            self.actor_id,
            self.offer_id,
            self._ANSWER,
            activity_id,
            self._case_manager_id,
        )

    def update(self) -> Status:
        if (f := self._validate_context()) is not None:
            return f
        try:
            activity_id, activity_blob = self._call_factory()
        except Exception as exc:  # noqa: BLE001  # ruff-baseline #3768
            self.feedback_message = (
                f"error creating {self._ANSWER} for offer"
                f" '{self.offer_id}': {exc}"
            )
            self.logger.error("%s: %s", self.name, self.feedback_message)  # noqa: TRY400  # ruff-baseline #3353
            return Status.FAILURE
        self._emit_through_seam(activity_id, activity_blob)
        self._on_success(activity_id, activity_blob)
        return Status.SUCCESS


class AutoAcceptCaseParticipantRoleNode(_AnswerCaseParticipantRoleOfferBase):
    """Auto-accept a CaseParticipantRole offer on behalf of the local actor (ADR-0039).

    When the target receives the CASE_MANAGER's forward of an
    ``Offer(CaseParticipantRole)`` it accepts, and the CASE_MANAGER receives
    the answer (CM-33-004).  The send is
    :class:`_AnswerCaseParticipantRoleOfferBase`'s.

    See SE-08-003, ADR-0039.
    """

    _EVENT_TYPE = ACCEPT_CASE_PARTICIPANT_ROLE_EVENT_TYPE
    _ANSWER = "Accept"

    def _factory_method(self) -> Callable[..., tuple[str, str]]:
        assert self.trigger_activity_factory is not None
        return self.trigger_activity_factory.accept_case_participant_role


class GrantCaseParticipantRoleNode(DataLayerAction, StateWriteCapable):
    """Grant the offered role on the CASE_MANAGER's own case replica (ADR-0039).

    The grant is the CASE_MANAGER's committed ``accept_case_participant_role``
    entry, never the Offer's receipt (CM-33-001, CM-02-016), so no tree
    composes this node on the Offer; the target's Accept tree does, after the
    CASE_MANAGER commits the Accept (CM-33-006,
    ``vultron.core.behaviors.case.role_offer_answer_tree``).  It runs as a
    ``manager_effects`` entry, so the factory's CASE_MANAGER gate (BT-17-008)
    fires it only at the CASE_MANAGER — the ledger holder, which excludes
    itself from the ``Announce`` fan-out and so never replays its own
    ``accept_case_participant_role`` entry.  The CM therefore applies the
    grant to its own copy here; every other participant applies it from the
    ledger via
    :class:`~vultron.core.behaviors.sync.nodes.role_grant_effect.ApplyCaseParticipantRoleGrantFromLedgerNode`
    (CM-02-016).  Idempotent and non-fatal: an absent case or a target that is
    not a participant returns SUCCESS without writing.
    """

    def __init__(
        self,
        case_id: str,
        role: CVDRole,
        target_actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.role = role
        self.target_actor_id = target_actor_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case = self.datalayer.read(self.case_id)
        if not isinstance(case, VulnerabilityCase):
            return Status.SUCCESS
        granted = grant_role_to_target(
            cast(CasePersistence, self.datalayer),
            case,
            self.target_actor_id,
            self.role,
        )
        if granted:
            self.logger.info(
                "%s: granted %s to '%s' on the CASE_MANAGER's copy of"
                " case '%s' (CM-02-016)",
                self.name,
                self.role.value,
                self.target_actor_id,
                self.case_id,
            )
        else:
            self.logger.warning(
                "%s: '%s' is not a participant on the CASE_MANAGER's case"
                " '%s' — role %s not applied",
                self.name,
                self.target_actor_id,
                self.case_id,
                self.role.value,
            )
        return Status.SUCCESS


class EmitRejectCaseParticipantRoleNode(_AnswerCaseParticipantRoleOfferBase):
    """Emit a Reject(Offer(CaseParticipantRole)) to the CASE_MANAGER (ADR-0039).

    Fallback branch of the ``AcceptOrReject`` Selector after
    :class:`AutoAcceptCaseParticipantRoleNode`.  When the target cannot
    auto-accept the role delegation offer, this node sends an explicit
    ``Reject`` so the CASE_MANAGER, and through its ledger the Case Owner, is
    told rather than receiving silence (CM-33-004).  The send is
    :class:`_AnswerCaseParticipantRoleOfferBase`'s.

    See SE-08-003, ADR-0039.
    """

    _EVENT_TYPE = REJECT_CASE_PARTICIPANT_ROLE_EVENT_TYPE
    _ANSWER = "Reject"

    def _factory_method(self) -> Callable[..., tuple[str, str]]:
        assert self.trigger_activity_factory is not None
        return self.trigger_activity_factory.reject_case_participant_role
