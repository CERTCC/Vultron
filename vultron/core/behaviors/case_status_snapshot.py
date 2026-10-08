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

"""Post-mutation CaseStatus snapshot, shared across behavior domains.

:class:`EmitCaseStatusUpdateNode` commits a ``CaseStatus`` snapshot after an
EM or PXA lifecycle node mutates the case (RSH-04-002, RSH-04-003).  The
embargo trigger trees and the status trees both compose it, so it lives in this
purpose-built shared module rather than in either domain's ``nodes`` package
(BTND-04-001).  It cannot live in ``status.nodes``: that package re-exports the
lifecycle nodes that compose the embargo trigger trees, so an embargo tree
importing from it would close an import cycle (CS-05-003).

:func:`promote_pxa` is the SM-09-001 persistence-boundary promotion this node
and :class:`~vultron.core.behaviors.status.nodes.case_status.AppendCaseStatusToCaseNode`
both apply.
"""

import logging
from datetime import UTC, datetime
from typing import Any, cast

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import EmDimension, PxaDimension
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.states.cs import CS_pxa

logger = logging.getLogger(__name__)


def promote_pxa(pxa: CS_pxa) -> CS_pxa:
    """SM-09-001: promote ephemeral pX states at the persistence boundary."""
    if pxa is CS_pxa.pXa:
        return CS_pxa.PXa
    if pxa is CS_pxa.pXA:
        return CS_pxa.PXA
    return pxa


class EmitCaseStatusUpdateNode(DataLayerActionWithPorts, StateWriteCapable):
    """Snapshot the post-mutation CaseStatus, commit a CaseLedgerEntry, and fan out.

    After an EM or PXA lifecycle node mutates the case state, this node:

    1. Reads the VulnerabilityCase from the DataLayer (post-mutation).
    2. Creates a new CaseStatus snapshotting the current ``em`` + ``pxa`` state.
    3. Persists the CaseStatus and appends it to ``case.case_statuses``.
    4. Commits a CaseLedgerEntry via ``create_commit_log_entry_tree``.
    5. FanOutLogEntryNode (inside the commit tree) announces to participants
       when a ``sync_port`` is available on the blackboard.

    MUST NOT route through the inbox seam (RSH-04-004).
    Per RSH-04-002 (EM mutations) and RSH-04-003 (PXA mutations).
    """

    def __init__(self, case_id: str | None, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self._committed_status_id: str | None = None

    def update(self) -> Status:
        if not self.case_id:
            self.feedback_message = (
                "case_id is absent — cannot snapshot CaseStatus"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        # Within-tick idempotency: if this node already committed a CaseStatus
        # for this case during the current BT execution, skip the duplicate write.
        if self._committed_status_id is not None:
            existing_ids = {_as_id(s) for s in case.case_statuses}
            if self._committed_status_id in existing_ids:
                self.logger.info(
                    "%s: already committed '%s' for case '%s' — skipping"
                    " duplicate write (idempotent)",
                    self.name,
                    self._committed_status_id,
                    self.case_id,
                )
                return Status.SUCCESS

        try:
            current = case.current_status
        except (ValueError, IndexError):
            self.feedback_message = (
                f"Case '{self.case_id}' has no materialized CaseStatus"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        # AC-1: pX → PX forced promotion at persistence boundary (SM-09-001)
        pxa_state = promote_pxa(current.pxa.state)
        new_status = CaseStatus(
            context=self.case_id,
            attributed_to=self.actor_id,
            em=EmDimension(state=case.em_state),
            pxa=PxaDimension(state=pxa_state),
        )

        # ``new_status`` is a core-branch ``CaseStatus`` this node just built, so
        # its AS2 form — the ``emState`` / ``pxaState`` snapshot shape
        # CM-18-006's invariant harness and every replica read — comes from the
        # port (ARCH-20-001, CLP-07-009).
        status_dict: dict[str, Any] = self._require_wire_render_port().render(
            new_status
        )
        payload: dict[str, Any] = {
            "type": "Add",
            "actor": self.actor_id,
            "context": self.case_id,
            "published": datetime.now(tz=UTC).isoformat(),
            "object": status_dict,
        }

        commit_tree = create_commit_log_entry_tree(
            case_id=self.case_id,
            object_id=new_status.id_,
            event_type="add_case_status_to_case",
            payload_snapshot=payload,
        )
        result = BTBridge(
            datalayer=cast(CaseOutboxPersistence, self.datalayer)
        ).execute_with_setup(tree=commit_tree, actor_id=self.actor_id)
        if result.status != Status.SUCCESS:
            self.feedback_message = (
                f"Ledger commit failed for CaseStatus '{new_status.id_}'"
                f" in case '{self.case_id}': {result.feedback_message}"
            )
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        # Persist only after the ledger commit succeeds to avoid phantom state.
        self.datalayer.save(new_status)
        case.add_case_status(new_status)
        self.datalayer.save(case)

        # Record committed ID for within-tick idempotency guard.
        self._committed_status_id = new_status.id_

        self.logger.info(
            "%s: committed CaseStatus '%s' for case '%s'",
            self.name,
            new_status.id_,
            self.case_id,
        )
        return Status.SUCCESS
