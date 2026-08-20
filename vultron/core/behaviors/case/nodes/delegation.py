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
from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)


class AutoAcceptCaseParticipantRoleNode(DataLayerAction):
    """Auto-accept a CaseParticipantRole offer on behalf of the local actor (ADR-0039).

    When the local actor receives an ``Offer(CaseParticipantRole)`` it MUST
    auto-accept so the offering Vendor receives confirmation.  This node
    creates the ``Accept`` activity via ``trigger_activity_factory`` and
    queues it in the local actor's outbox.

    See SE-08-003, ADR-0039.
    """

    def __init__(
        self,
        offer_id: str,
        case_id: str,
        role: CVDRole,
        target_actor_id: str,
        vendor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.offer_id = offer_id
        self.case_id = case_id
        self.role = role
        self.target_actor_id = target_actor_id
        self.vendor_id = vendor_id

    def _call_factory(self) -> tuple[str, dict]:
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        return self.trigger_activity_factory.accept_case_participant_role(
            offer_id=self.offer_id,
            case_id=self.case_id,
            role=self.role,
            target_actor_id=self.target_actor_id,
            vendor_id=self.vendor_id,
            actor=self.actor_id,
            to=[self.vendor_id],
        )

    def _enqueue_accept(self, accept_id: str) -> None:
        cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(  # type: ignore[union-attr]
            self.actor_id, accept_id  # type: ignore[arg-type]
        )

    def _validate_context(self) -> Status | None:
        if (f := self._require_datalayer_and_actor()) is not None:
            self.logger.error(
                "%s: DataLayer or actor_id not available", self.name
            )
            return f
        if (f := self._require_factory()) is not None:
            self.logger.warning(
                "%s: factory unavailable — cannot auto-accept offer '%s'",
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
        return None

    def _commit_accept_to_ledger(
        self, accept_id: str, payload_snapshot: dict
    ) -> bool:
        assert self.datalayer is not None
        assert self.actor_id is not None
        if payload_snapshot.get("context") != self.case_id:
            payload_snapshot = dict(payload_snapshot)
            payload_snapshot["context"] = self.case_id
        commit_tree = create_commit_log_entry_tree(
            case_id=self.case_id,
            object_id=accept_id,
            event_type="accept_case_participant_role",
            payload_snapshot=payload_snapshot,
            disposition="recorded",
        )
        result = BTBridge(
            datalayer=cast(CaseOutboxPersistence, self.datalayer)
        ).execute_with_setup(
            tree=commit_tree,
            actor_id=self.actor_id,
        )
        if result.status != Status.SUCCESS:
            self.logger.error(
                "%s: ledger commit failed for Accept '%s' on offer '%s'",
                self.name,
                accept_id,
                self.offer_id,
            )
            return False
        return True

    def update(self) -> Status:
        if (f := self._validate_context()) is not None:
            return f
        try:
            accept_id, payload_snapshot = self._call_factory()
        except Exception as exc:
            self.logger.error(
                "%s: error creating Accept for offer '%s': %s",
                self.name,
                self.offer_id,
                exc,
            )
            return Status.FAILURE
        if not self._commit_accept_to_ledger(accept_id, payload_snapshot):
            return Status.FAILURE
        self._enqueue_accept(accept_id)
        self.logger.info(
            "%s: auto-accepted offer '%s' as '%s'; ledgered and queued"
            " Accept '%s'",
            self.name,
            self.offer_id,
            self.actor_id,
            accept_id,
        )
        return Status.SUCCESS


class EmitRejectCaseParticipantRoleNode(DataLayerAction):
    """Emit a Reject(Offer(CaseParticipantRole)) to the offering Vendor (ADR-0039).

    Fallback branch of the ``AcceptOrReject`` Selector after
    :class:`AutoAcceptCaseParticipantRoleNode`.  When the local actor cannot
    auto-accept the role delegation offer, this node sends an explicit
    ``Reject`` so the offering Vendor is notified rather than receiving silence.

    Returns ``FAILURE`` on any error so callers can observe the failure.

    See SE-08-003, ADR-0039.
    """

    def __init__(
        self,
        offer_id: str,
        case_id: str,
        role: CVDRole,
        target_actor_id: str,
        vendor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.offer_id = offer_id
        self.case_id = case_id
        self.role = role
        self.target_actor_id = target_actor_id
        self.vendor_id = vendor_id

    def _call_factory(self) -> str:
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        return self.trigger_activity_factory.reject_case_participant_role(
            offer_id=self.offer_id,
            case_id=self.case_id,
            role=self.role,
            target_actor_id=self.target_actor_id,
            vendor_id=self.vendor_id,
            actor=self.actor_id,
            to=[self.vendor_id],
        )

    def _emit(self) -> None:
        reject_id = self._call_factory()
        cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(  # type: ignore[union-attr]
            self.actor_id, reject_id  # type: ignore[arg-type]
        )
        self.logger.info(
            "%s: emitted Reject '%s' to vendor '%s' for offer '%s'",
            self.name,
            reject_id,
            self.vendor_id,
            self.offer_id,
        )

    def _validate_context(self) -> Status | None:
        if (f := self._require_datalayer_and_actor()) is not None:
            self.logger.error(
                "%s: DataLayer or actor_id not available", self.name
            )
            return f
        if (f := self._require_factory()) is not None:
            self.logger.warning(
                "%s: factory unavailable — cannot emit Reject for offer '%s'",
                self.name,
                self.offer_id,
            )
            return f
        if not self.case_id or not self.target_actor_id:
            self.logger.warning(
                "%s: missing case_id or target_actor_id for offer '%s'"
                " — cannot emit Reject",
                self.name,
                self.offer_id,
            )
            return Status.FAILURE
        return None

    def update(self) -> Status:
        if (f := self._validate_context()) is not None:
            return f
        try:
            self._emit()
            return Status.SUCCESS
        except Exception as exc:
            self.logger.error(
                "%s: error emitting Reject for offer '%s': %s",
                self.name,
                self.offer_id,
                exc,
            )
            return Status.FAILURE
