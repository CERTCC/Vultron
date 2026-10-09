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

import json
import logging
from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.emit_capable import EmitCapable
from vultron.core.behaviors.helpers import (
    DataLayerAction,
    _EmitSingleActivityBase,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.behaviors.sync.nodes.role_grant_effect import (
    grant_role_to_target,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)


class AutoAcceptCaseParticipantRoleNode(DataLayerAction, EmitCapable):
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

    def _call_factory(self) -> tuple[str, str]:
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
        # The Accept is now persisted.  Outbox enqueue MUST NOT return FAILURE
        # here — the AcceptOrReject Selector would fall through to
        # EmitRejectCaseParticipantRoleNode, producing contradictory protocol
        # state (Accept stored, Reject sent).  Let the exception propagate
        # instead.
        cast(CaseOutboxPersistence, self.datalayer).outbox_append(  # type: ignore[union-attr]
            accept_id
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
        self, accept_id: str, payload_snapshot: str
    ) -> bool:
        assert self.datalayer is not None
        assert self.actor_id is not None
        # Exact blob as snapshot (VM-08-003): the factory sets ``context`` to
        # the case URI from the offer it embeds, so nothing is patched here.
        snapshot_dict: dict = json.loads(payload_snapshot)
        commit_tree = create_commit_log_entry_tree(
            case_id=self.case_id,
            object_id=accept_id,
            event_type="accept_case_participant_role",
            payload_snapshot=snapshot_dict,
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
        except Exception as exc:  # noqa: BLE001  # ruff-baseline #3768
            self.logger.error(  # noqa: TRY400  # ruff-baseline #3353
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


class EmitRejectCaseParticipantRoleNode(_EmitSingleActivityBase):
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
        super().__init__(name=name)
        self.offer_id = offer_id
        self.case_id = case_id
        self.role = role
        self.target_actor_id = target_actor_id
        self.vendor_id = vendor_id

    def _call_factory(self) -> tuple[str, str]:
        if not self.case_id or not self.target_actor_id:
            raise ValueError(
                f"missing case_id or target_actor_id for offer '{self.offer_id}'"
                " — cannot emit Reject"
            )
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

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        self.logger.info(
            "%s: emitted Reject '%s' to vendor '%s' for offer '%s'",
            self.name,
            activity_id,
            self.vendor_id,
            self.offer_id,
        )
