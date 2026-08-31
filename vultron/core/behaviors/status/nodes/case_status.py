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

"""Case status workflow nodes for AddCaseStatusToCase.

Contains the idempotency guard and append node implementing the
AddCaseStatusToCase BT sequence (issue #758).

Per-dimension adjudication nodes (RSH-05, ADR-0061, ISSUE-2256) live in
:mod:`cs_dimension_filter` to keep this module under the 500-line limit.
"""

import logging
from datetime import datetime, timezone
from typing import Any, cast

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.idempotency import SilentIdempotencyGuardMixin
from vultron.core.behaviors.status.nodes.cs_dimension_filter import (
    BB_CASE_STATUS_DIM_FILTER,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import EmDimension, PxaDimension
from vultron.core.states.cs import CS_pxa
from vultron.core.models.protocols import PersistableModel
from vultron.core.ports.case_persistence import CaseOutboxPersistence

logger = logging.getLogger(__name__)

# Stable sentinel used as feedback_message when a CaseStatus duplicate is
# detected.  The use case imports this constant to distinguish idempotent
# no-ops (log at INFO) from real failures (log at WARNING).
CASE_STATUS_ALREADY_PRESENT = "case_status_already_present"


class CheckCaseStatusIdempotencyNode(
    SilentIdempotencyGuardMixin, DataLayerConditionWithPorts
):
    """AC-1: Verify the CaseStatus has not already been added to the case.

    Returns FAILURE with ``feedback_message == CASE_STATUS_ALREADY_PRESENT``
    when *status_id* is already in ``case.case_statuses`` — a benign no-op
    with no ledger write (CLP-13-001, CLP-13-002).

    Returns FAILURE with a distinct message when the case itself is not found.

    Returns SUCCESS when the status is not yet present and the Sequence should
    continue.

    Per issue #758 AC-1.
    """

    def __init__(
        self,
        case_id: str,
        status_id: str,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.status_id = status_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case = self.datalayer.read(self.case_id)
        if not isinstance(case, VulnerabilityCase):
            self.feedback_message = f"Case '{self.case_id}' not found"
            self.logger.warning(
                "CheckCaseStatusIdempotency: %s", self.feedback_message
            )
            return Status.FAILURE

        existing_ids = [_as_id(s) for s in case.case_statuses]
        if self.status_id in existing_ids:
            self.feedback_message = CASE_STATUS_ALREADY_PRESENT
            return self._idempotent_failure(
                self.logger,
                "CheckCaseStatusIdempotency: status '%s' already in case '%s'"
                " — skipping (idempotent, CLP-13-001)",
                self.status_id,
                self.case_id,
            )

        return Status.SUCCESS


class AppendCaseStatusToCaseNode(DataLayerActionWithPorts):
    """Append the resolved CaseStatus to ``case.case_statuses`` and persist.

    When ``BB_CASE_STATUS_DIM_FILTER`` carries a filtered status for this
    tick (written by :class:`FinalizeCsFilterNode`), that filtered object is
    appended and saved to the DataLayer so the canonical record reflects the
    accepted portion, not the raw assertion (RSH-05, ISSUE-2256).

    Falls back to resolving from the DataLayer/fallback when no filter is
    present (original behavior for unfiltered statuses).

    Returns SUCCESS on successful append.
    Returns FAILURE if the case or status cannot be resolved.

    Per issue #758 AC-1.
    """

    def __init__(
        self,
        case_id: str,
        status_id: str,
        status_obj_fallback: PersistableModel | None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.status_id = status_id
        self.status_obj_fallback = status_obj_fallback

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        return {
            **super().input_ports(),
            BB_CASE_STATUS_DIM_FILTER: PortInformation(
                data_type=object, required=False
            ),
        }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            BB_CASE_STATUS_DIM_FILTER: f"/{BB_CASE_STATUS_DIM_FILTER}",
        }

    def _resolve_filtered(self) -> CaseStatus | None:
        """Return the filter-adjusted CaseStatus if one exists for this tick."""
        payload = self._try_get_input(BB_CASE_STATUS_DIM_FILTER)
        if not isinstance(payload, dict):
            return None
        if payload.get("status_id") != self.status_id:
            return None
        obj = payload.get("filtered_status")
        return obj if isinstance(obj, CaseStatus) else None

    def _resolve_status(self) -> "PersistableModel | None":
        assert self.datalayer is not None
        status_obj = self.datalayer.read(self.status_id)
        if hasattr(status_obj, "id_"):
            return status_obj
        status_obj = self.status_obj_fallback
        if status_obj is not None:
            self.datalayer.save(status_obj)
            status_obj = self.datalayer.read(self.status_id) or status_obj
        return status_obj if hasattr(status_obj, "id_") else None

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case = self.datalayer.read(self.case_id)
        if not isinstance(case, VulnerabilityCase):
            self.feedback_message = f"Case '{self.case_id}' not found"
            self.logger.warning(
                "AppendCaseStatusToCase: %s", self.feedback_message
            )
            return Status.FAILURE

        # Use the per-dimension-filtered status when available; otherwise fall
        # back to the raw asserted object (no filtering was needed or applied).
        from_filter = False
        status_obj: CaseStatus | PersistableModel | None = (
            self._resolve_filtered()
        )
        if status_obj is not None:
            from_filter = True
        else:
            status_obj = self._resolve_status()

        if status_obj is None:
            self.feedback_message = f"Status '{self.status_id}' not found"
            self.logger.warning(
                "AppendCaseStatusToCase: %s", self.feedback_message
            )
            return Status.FAILURE

        if not isinstance(status_obj, CaseStatus):
            self.feedback_message = (
                f"Status '{self.status_id}' is not a CaseStatus"
            )
            self.logger.warning(
                "AppendCaseStatusToCase: %s", self.feedback_message
            )
            return Status.FAILURE

        # AC-1: pX → PX forced promotion at persistence boundary (SM-09-001)
        if status_obj.pxa is not None:
            pxa_state = status_obj.pxa.state
            if pxa_state is CS_pxa.pXa:
                status_obj = status_obj.model_copy(
                    update={"pxa": PxaDimension(state=CS_pxa.PXa)}
                )
                from_filter = True
            elif pxa_state is CS_pxa.pXA:
                status_obj = status_obj.model_copy(
                    update={"pxa": PxaDimension(state=CS_pxa.PXA)}
                )
                from_filter = True

        if from_filter:
            self.datalayer.save(status_obj)

        case.add_case_status(status_obj)
        self.datalayer.save(case)
        self.logger.info(
            "AppendCaseStatusToCase: added status '%s' to case '%s'",
            self.status_id,
            self.case_id,
        )
        return Status.SUCCESS


class EmitCaseStatusUpdateNode(DataLayerActionWithPorts):
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

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self._committed_status_id: str | None = None

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        case = self.datalayer.read(self.case_id)
        if not isinstance(case, VulnerabilityCase):
            self.feedback_message = f"Case '{self.case_id}' not found"
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

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
        pxa_state = current.pxa.state
        if pxa_state is CS_pxa.pXa:
            pxa_state = CS_pxa.PXa
        elif pxa_state is CS_pxa.pXA:
            pxa_state = CS_pxa.PXA
        new_status = CaseStatus(
            context=self.case_id,
            attributed_to=self.actor_id,
            em=EmDimension(state=current.em.state),
            pxa=PxaDimension(state=pxa_state),
        )

        status_dict: dict[str, Any] = new_status.model_dump(
            mode="json",
            by_alias=True,
            serialize_as_any=True,
            exclude_none=True,
        )
        payload: dict[str, Any] = {
            "type": "Add",
            "actor": self.actor_id,
            "context": self.case_id,
            "published": datetime.now(tz=timezone.utc).isoformat(),
            "object": status_dict,
        }

        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.sync.commit_tree import (
            create_commit_log_entry_tree,
        )

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
