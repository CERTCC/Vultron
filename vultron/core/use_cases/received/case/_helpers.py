"""Use cases for vulnerability case activities."""

import logging

from vultron.core.behaviors.case.update_support import (
    find_excluded_actor_ids,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.carried_embargo import store_carried_embargo
from vultron.errors import VultronNotFoundError, VultronValidationError

logger = logging.getLogger(__name__)


def _find_report_case_link(
    creator_id: str, dl: CasePersistence
) -> VultronReportCaseLink | None:
    """Return a pending ReportCaseLink expecting a bootstrap from *creator_id*.

    Scans all ``ReportCaseLink`` records and returns the first that has
    ``case_creator_id == creator_id`` and ``case_id is None``
    (i.e. awaiting bootstrap).  Using the sender identity rather than the
    case's vulnerability_reports list makes the lookup independent of whether
    the case snapshot embeds the report.
    """
    for obj in dl.list_objects("ReportCaseLink"):
        if isinstance(obj, VultronReportCaseLink) and (
            obj.case_creator_id == creator_id and obj.case_id is None
        ):
            return obj
    return None


def _check_participant_embargo_acceptance(
    case: VulnerabilityCase, dl: CasePersistence
) -> set[str]:
    """Check which participants have not accepted the active embargo.

    Returns a set of actor IDs whose case updates should be withheld per
    CM-10-004 (participants that have not accepted the active embargo).
    """
    return find_excluded_actor_ids(case, dl)


def _hold_carried_embargo(
    case_obj: VulnerabilityCase, dl: CasePersistence, case_id: str
) -> HandlerResult | None:
    """Hold the ``EmbargoEvent`` a received case names, before it is saved.

    Delegates to :func:`~vultron.core.services.carried_embargo.store_carried_embargo`
    so there is one implementation with the announce seed and the inbox
    pre-store.  The sender carries the embargo rather than referencing it
    because a receiver cannot dereference a URI it does not hold
    (AKM-03-001) — see ``_case_for_wire``; storing it is what makes this
    actor's own ``case.active_embargo`` resolve.

    Call it *before* saving the case.  Returns ``None`` when the named
    embargo (if any) is now held, or a ``REFUSED`` result when the case names
    one this store cannot read — the caller returns it and saves nothing
    (EMB-18-003).
    """
    try:
        store_carried_embargo(case_obj, dl)
    except (VultronNotFoundError, VultronValidationError) as exc:
        reason = (
            f"case '{case_id}' names an active embargo this store cannot"
            f" read (EMB-18-003): {exc}"
        )
        logger.warning("Refusing received case: %s", reason)
        return HandlerResult.refused(reason)
    return None
