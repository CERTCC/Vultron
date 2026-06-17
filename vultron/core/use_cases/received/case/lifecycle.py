"""Use cases for vulnerability case activities."""

import logging
from typing import TYPE_CHECKING

from vultron.core.models.events.case import (
    AddReportToCaseReceivedEvent,
    CloseCaseReceivedEvent,
)
from vultron.core.models.protocols import is_case_model
from vultron.core.ports.case_persistence import (
    CaseOutboxPersistence,
    CasePersistence,
)
from vultron.core.use_cases._helpers import _as_id, _find_case_actor_id

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort

logger = logging.getLogger(__name__)


class AddReportToCaseReceivedUseCase:
    def __init__(
        self, dl: CasePersistence, request: AddReportToCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: AddReportToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        report_id = request.report_id
        case_id = request.case_id
        if report_id is None or case_id is None:
            logger.warning("add_report_to_case: missing report_id or case_id")
            return
        case = self._dl.read(case_id)

        if not is_case_model(case):
            logger.warning("add_report_to_case: case '%s' not found", case_id)
            return

        existing_report_ids = [_as_id(r) for r in case.vulnerability_reports]
        if report_id in existing_report_ids:
            logger.info(
                "Report '%s' already in case '%s' — skipping (idempotent)",
                report_id,
                case_id,
            )
            return

        case.vulnerability_reports.append(report_id)
        self._dl.save(case)
        logger.info("Added report '%s' to case '%s'", report_id, case_id)


class CloseCaseReceivedUseCase:
    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: CloseCaseReceivedEvent,
        sync_port: "SyncActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: CloseCaseReceivedEvent = request
        self._sync_port = sync_port

    def execute(self) -> None:
        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.case.nodes import (
            create_guarded_commit_case_ledger_entry_tree,
        )

        request = self._request
        case_id = request.case_id
        actor_id = request.actor_id

        if case_id is None:
            logger.warning("close_case: missing case_id")
            return

        logger.info("Actor '%s' is closing case '%s'", actor_id, case_id)

        # Pre-flight guard (ADR-0021, CLP-10-002, CLP-10-003)
        case_actor_id = _find_case_actor_id(self._dl, case_id)
        if case_actor_id is None:
            logger.warning(
                "CloseCaseReceivedUseCase: cannot resolve CaseActor for case"
                " '%s' — skipping commit",
                case_id,
            )
            return

        receiving_actor_id = request.receiving_actor_id
        if receiving_actor_id is None:
            logger.debug(
                "CloseCaseReceivedUseCase: missing receiving_actor_id"
                " — skipping commit"
            )
            return

        if receiving_actor_id != case_actor_id:
            logger.debug(
                "CloseCaseReceivedUseCase: receiving actor '%s' is not the"
                " CaseActor for case '%s' — skipping commit (CLP-10-003)",
                receiving_actor_id,
                case_id,
            )
            return

        BTBridge(datalayer=self._dl).execute_with_setup(
            tree=create_guarded_commit_case_ledger_entry_tree(case_id=case_id),
            actor_id=receiving_actor_id,
            activity=request,
            sync_port=self._sync_port,
        )
