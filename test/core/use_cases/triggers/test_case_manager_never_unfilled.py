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
"""The CASE_MANAGER role is never unfilled (CM-24-006).

Both creation paths register a holder at birth and delegation hands it on, so a
roster with no ``CVDRole.CASE_MANAGER`` is corrupt, not a topology.  The
delegated-context helper still carries CM-24-003's "no manager, send directly"
fallback; this strict ``xfail`` pins its retirement (Task opened from Concern
#3918, ADR-0113 as rewritten 2026-09-30).
"""

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.use_cases.triggers._helpers import _prepare_delegated_context
from vultron.errors import VultronError

OWNER = "https://example.org/actors/owner"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "CM-24-006: _prepare_delegated_context falls back to the requesting "
        "actor when the roster names no CASE_MANAGER (CM-24-003). Tracked by "
        "the Task the #3918 planning PR opened; ADR-0113."
    ),
)
@pytest.mark.spec("CM-24-006")
def test_delegated_context_fails_when_no_case_manager_holds_the_role() -> None:
    """A roster with no CASE_MANAGER is a fault, not a fallback."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=OWNER)
    case = VulnerabilityCase(name="Corrupt roster", attributed_to=OWNER)
    dl.create(case)

    with pytest.raises(VultronError):
        _prepare_delegated_context(dl, case.id_, OWNER)
