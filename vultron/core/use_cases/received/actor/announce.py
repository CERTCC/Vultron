"""Use cases for case actor/participant invitation and suggestion activities."""

import logging

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.announce_case_received_tree import (
    create_announce_vulnerability_case_received_tree,
)
from vultron.core.models.events.actor import (
    AnnounceVulnerabilityCaseReceivedEvent,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.use_cases._helpers import _as_id, _find_case_actor_id

logger = logging.getLogger(__name__)


def _link_report_case_links(dl: CasePersistence, case) -> None:
    """Attach any matching ``ReportCaseLink`` records to the announced case."""
    for report_ref in case.vulnerability_reports:
        report_id = _as_id(report_ref)
        if report_id is None:
            continue

        link = dl.read(VultronReportCaseLink.build_id(report_id))
        if not isinstance(link, VultronReportCaseLink):
            continue
        if link.case_id == case.id_:
            continue

        dl.save(link.model_copy(update={"case_id": case.id_}))
        logger.info(
            "AnnounceVulnerabilityCase: linked report '%s' to case '%s'",
            report_id,
            case.id_,
        )


class AnnounceVulnerabilityCaseReceivedUseCase:
    """Seed the local DataLayer with a full VulnerabilityCase from the case owner.

    Per MV-10-003, the invitee creates the case if it does not already exist.
    Per MV-10-004, if the case already exists locally, the announcement is
    accepted without overwriting the existing record (idempotent).
    """

    def __init__(
        self,
        dl: CasePersistence,
        request: AnnounceVulnerabilityCaseReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request = request

    def execute(self) -> None:
        request = self._request
        activity = request.activity
        if activity is None:
            logger.warning(
                "AnnounceVulnerabilityCase: no activity on event '%s' — skipping",
                request.activity_id,
            )
            return

        # The case object is the object_ field of the announce activity.
        case_obj = getattr(activity, "object_", None)
        if case_obj is None:
            logger.warning(
                "AnnounceVulnerabilityCase: no case object in activity '%s'"
                " — skipping",
                request.activity_id,
            )
            return

        if (
            not isinstance(case_obj, VulnerabilityCase)
            and getattr(case_obj, "type_", None) != "VulnerabilityCase"
        ):
            logger.warning(
                "AnnounceVulnerabilityCase: object in activity '%s' is not a"
                " VulnerabilityCase (%s) — skipping",
                request.activity_id,
                type(case_obj).__name__,
            )
            return

        case_id = _as_id(case_obj)
        if case_id is None:
            logger.warning(
                "AnnounceVulnerabilityCase: case object has no id in"
                " activity '%s' — skipping",
                request.activity_id,
            )
            return

        case_actor_id = _find_case_actor_id(self._dl, case_id)
        if case_actor_id is not None and case_actor_id != request.actor_id:
            logger.warning(
                "AnnounceVulnerabilityCase: actor '%s' is not the CaseActor"
                " for case '%s' — update rejected (PCR-03-001)",
                request.actor_id,
                case_id,
            )
            return

        tree = create_announce_vulnerability_case_received_tree(
            case_id=case_id,
            case_obj=case_obj,
            request=request,
        )
        bridge = BTBridge(datalayer=self._dl)
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=request.actor_id,
            activity=request,
        )
        if result.status != Status.SUCCESS:
            logger.warning(
                "AnnounceVulnerabilityCaseReceivedBT did not succeed"
                " for case '%s': %s",
                case_id,
                BTBridge.get_failure_reason(tree),
            )
