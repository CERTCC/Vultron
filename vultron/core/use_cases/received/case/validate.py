"""Use cases for vulnerability case activities."""

import logging

from py_trees.common import Status

from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.states.rm import RM
from vultron.core.use_cases._helpers import update_participant_rm_state

logger = logging.getLogger(__name__)


class InvalidateCaseUseCase:
    """Transition the actor's RM state to INVALID within the given case.

    Called by ``InvalidateReportReceivedUseCase`` after dereferencing
    report_id to case_id (CM-12-005).
    """

    def __init__(
        self, dl: CasePersistence, case_id: str, actor_id: str
    ) -> None:
        self._dl = dl
        self._case_id = case_id
        self._actor_id = actor_id

    def execute(self) -> None:
        success = update_participant_rm_state(
            self._case_id, self._actor_id, RM.INVALID, self._dl
        )
        if success:
            logger.info(
                "RM → INVALID for actor '%s' in case '%s'",
                self._actor_id,
                self._case_id,
            )
        else:
            logger.warning(
                "Failed to set RM.INVALID for actor '%s' in case '%s'",
                self._actor_id,
                self._case_id,
            )


class CloseCaseUseCase:
    """Transition the actor's RM state to CLOSED within the given case.

    Called by ``CloseReportReceivedUseCase`` after dereferencing
    report_id to case_id (CM-12-005).
    """

    def __init__(
        self, dl: CasePersistence, case_id: str, actor_id: str
    ) -> None:
        self._dl = dl
        self._case_id = case_id
        self._actor_id = actor_id

    def execute(self) -> None:
        success = update_participant_rm_state(
            self._case_id, self._actor_id, RM.CLOSED, self._dl
        )
        if success:
            logger.info(
                "RM → CLOSED for actor '%s' in case '%s'",
                self._actor_id,
                self._case_id,
            )
        else:
            logger.warning(
                "Failed to set RM.CLOSED for actor '%s' in case '%s'",
                self._actor_id,
                self._case_id,
            )


class ValidateCaseUseCase:
    """Run the validate-report behavior tree for the given case.

    Called by ``ValidateReportReceivedUseCase`` after dereferencing
    report_id to case_id (CM-12-005).

    Advances RM to VALID only.  The engage/defer decision (RM → ACCEPTED
    or RM → DEFERRED) is a distinct, explicit protocol step driven by a
    separate ``engage-case`` or ``defer-case`` trigger.
    """

    def __init__(
        self,
        dl: CasePersistence,
        actor_id: str,
        report_id: str,
        offer_id: str,
    ) -> None:
        self._dl = dl
        self._actor_id = actor_id
        self._report_id = report_id
        self._offer_id = offer_id

    def execute(self) -> None:
        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.report.validate_tree import (
            create_validate_report_tree,
        )

        logger.info(
            "Actor '%s' validates VulnerabilityReport '%s' via BT",
            self._actor_id,
            self._report_id,
        )

        bridge = BTBridge(datalayer=self._dl)
        tree = create_validate_report_tree(
            report_id=self._report_id,
            offer_id=self._offer_id,
        )
        result = bridge.execute_with_setup(tree, actor_id=self._actor_id)

        if result.status == Status.SUCCESS:
            logger.info(
                "✓ BT validation succeeded for report: %s", self._report_id
            )
        elif result.status == Status.FAILURE:
            logger.error(
                "✗ BT validation failed for report: %s — %s",
                self._report_id,
                result.feedback_message,
            )
            for err in result.errors or []:
                logger.error("  - %s", err)
        else:
            logger.warning(
                "⚠ BT validation incomplete for report: %s (status=%s)",
                self._report_id,
                result.status,
            )
