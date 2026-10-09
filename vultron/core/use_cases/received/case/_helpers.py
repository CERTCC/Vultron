"""Use cases for vulnerability case activities."""

import logging

from vultron.core.behaviors.case.update_support import (
    find_excluded_actor_ids,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.ports.case_persistence import CasePersistence

logger = logging.getLogger(__name__)


def _check_participant_embargo_acceptance(
    case: VulnerabilityCase, dl: CasePersistence
) -> set[str]:
    """Check which participants have not accepted the active embargo.

    Returns a set of actor IDs whose case updates should be withheld per
    CM-10-004 (participants that have not accepted the active embargo).
    """
    return find_excluded_actor_ids(case, dl)
