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

Provides action nodes for the role delegation workflow:
auto-accepting and explicitly rejecting the delegation.

See SE-08-003, ADR-0039.
"""

import logging
from collections.abc import Callable
from typing import ClassVar, cast

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerAction,
    _EmitSingleActivityBase,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.behaviors.sync.commit_tree import commit_emitted_activity
from vultron.core.behaviors.sync.nodes.role_grant_effect import (
    grant_role_to_target,
)
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)


class _AnswerCaseParticipantRoleOfferBase(_EmitSingleActivityBase):
    """Send this actor's answer to an ``Offer(CaseParticipantRole)`` (ADR-0039).

    The one shape both arms of the ``AcceptOrReject`` Selector share.  The
    answer's id derives from the Offer it answers (OX-06-002), so a retry
    after a send whose commit failed rebuilds the same answer, which the
    outbox does not queue twice and the commit records once.

    Sent, then recorded (ADR-0119): the answer is queued first, and the
    commit follows **only when the executing actor holds**
    ``CVDRole.CASE_MANAGER`` **for the case**.  The actor a role is offered to
    is usually an ordinary participant, and a participant never commits
    (CLP-09-001): its answer goes out with no entry in its own ledger.  The
    CASE_MANAGER commits it on receipt (CM-33-006), which #4703 builds.

    Neither the outbox write nor the commit is caught: once the answer is
    queued a FAILURE would let the Selector send the contradictory answer
    after it, so a fault escapes to ``BTBridge`` as an internal error
    (BT-14-001, ARCH-15-001).  Only a missing input, a case this store does not
    hold, or a factory error returns FAILURE, before anything is written.

    Subclasses set ``_EVENT_TYPE`` (the ledger ``event_type`` and the kind
    label of the derived id) and ``_ANSWER`` (for logs), and implement
    :meth:`_factory_method`.
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
        self._case: VulnerabilityCase | None = None

    def _factory_method(self) -> Callable[..., tuple[str, str]]:
        """The ``TriggerActivityPort`` method that builds this answer."""
        raise NotImplementedError

    def _call_factory(self) -> tuple[str, str]:
        assert self.actor_id is not None
        return self._factory_method()(
            offer_id=self.offer_id,
            case_id=self.case_id,
            role=self.role,
            target_actor_id=self.target_actor_id,
            vendor_id=self.vendor_id,
            actor=self.actor_id,
            to=[self.vendor_id],
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
        # Resolved before anything is written (Regime 1, ADR-0087): an Accept
        # that cannot find the case fails, so the Selector answers with the
        # Reject, and the commit gate below reads the same case.
        self._case, failure = self._require_case(self.case_id)
        return failure

    def _executing_actor_is_case_manager(self) -> bool:
        """Whether the executing actor holds ``CVDRole.CASE_MANAGER`` here.

        The same answer :class:`CheckIsCaseManagerNode` gives (ADR-0088,
        ARCH-24-003): the canonical resolver names the CASE_MANAGER.
        """
        assert self._case is not None  # resolved by _validate_context
        return (
            resolve_case_manager_id(
                self._case, cast(CasePersistence, self.datalayer)
            )
            == self.actor_id
        )

    def _record_sent(self, activity_id: str, activity_blob: str) -> None:
        """Commit the queued answer when this actor is the CASE_MANAGER.

        Exact blob as snapshot (VM-08-003).  Raises when the commit fails.
        """
        assert self.datalayer is not None
        assert self.actor_id is not None
        if not self._executing_actor_is_case_manager():
            self.logger.info(
                "%s: '%s' does not hold CASE_MANAGER for case '%s' — %s '%s'"
                " sent with no ledger entry (CLP-09-001)",
                self.name,
                self.actor_id,
                self.case_id,
                self._ANSWER,
                activity_id,
            )
            return
        commit_emitted_activity(
            datalayer=cast(CaseOutboxPersistence, self.datalayer),
            actor_id=self.actor_id,
            case_id=self.case_id,
            activity_id=activity_id,
            activity_blob=activity_blob,
            event_type=self._EVENT_TYPE,
        )

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        self.logger.info(
            "%s: '%s' answered offer '%s' with %s '%s' to vendor '%s'",
            self.name,
            self.actor_id,
            self.offer_id,
            self._ANSWER,
            activity_id,
            self.vendor_id,
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
        self._record_sent(activity_id, activity_blob)
        self._on_success(activity_id, activity_blob)
        return Status.SUCCESS


class AutoAcceptCaseParticipantRoleNode(_AnswerCaseParticipantRoleOfferBase):
    """Auto-accept a CaseParticipantRole offer on behalf of the local actor (ADR-0039).

    When the local actor receives an ``Offer(CaseParticipantRole)`` it MUST
    auto-accept so the offering Vendor receives confirmation.  The send and
    the CASE_MANAGER-only commit are
    :class:`_AnswerCaseParticipantRoleOfferBase`'s.

    See SE-08-003, ADR-0039.
    """

    _EVENT_TYPE = "accept_case_participant_role"
    _ANSWER = "Accept"

    def _factory_method(self) -> Callable[..., tuple[str, str]]:
        assert self.trigger_activity_factory is not None
        return self.trigger_activity_factory.accept_case_participant_role


class GrantCaseParticipantRoleNode(DataLayerAction, StateWriteCapable):
    """Grant the offered role on the CASE_MANAGER's own case replica (ADR-0039).

    Runs as a ``manager_effects`` entry of the offer-received tree, so the
    factory's CASE_MANAGER gate (BT-17-008) fires it only at the CASE_MANAGER —
    the ledger holder, which excludes itself from the ``Announce`` fan-out and
    so never replays its own ``accept_case_participant_role`` entry. The CM
    therefore applies the grant to its own copy here; every other participant
    applies it from the ledger via
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
    """Emit a Reject(Offer(CaseParticipantRole)) to the offering Vendor (ADR-0039).

    Fallback branch of the ``AcceptOrReject`` Selector after
    :class:`AutoAcceptCaseParticipantRoleNode`.  When the local actor cannot
    auto-accept the role delegation offer, this node sends an explicit
    ``Reject`` so the offering Vendor is notified rather than receiving
    silence.  The send and the CASE_MANAGER-only commit are
    :class:`_AnswerCaseParticipantRoleOfferBase`'s.

    See SE-08-003, ADR-0039.
    """

    _EVENT_TYPE = "reject_case_participant_role"
    _ANSWER = "Reject"

    def _factory_method(self) -> Callable[..., tuple[str, str]]:
        assert self.trigger_activity_factory is not None
        return self.trigger_activity_factory.reject_case_participant_role
