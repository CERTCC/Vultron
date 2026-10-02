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

"""Tests for ``VultronReportCaseLink`` field names and their retired keys.

#4020 renamed ``trusted_case_creator_id`` to ``case_creator_id`` and
``trusted_case_actor_id`` to ``case_manager_id`` so CodeQL's sensitive-name
heuristic stops reading actor ids as secrets.  Stored data carries no
backwards compatibility, so a link still holding an old key is refused with a
reason naming the store reset; it is never aliased onto the new name.
"""

import re

import pytest
from pydantic import ValidationError

from vultron.core.models.report_case_link import VultronReportCaseLink

REPORT_ID = "https://example.org/reports/r-1"
CREATOR_ID = "https://example.org/actors/vendor"
MANAGER_ID = "https://example.org/actors/vendor/case-actor"

# Name fragments CodeQL's ``SensitiveDataHeuristics`` (and its neighbours)
# treat as secrets or credentials.  An actor-id field whose name matches one
# gets every log line that prints its value flagged by
# ``py/clear-text-logging-sensitive-data``.
_SENSITIVE_NAME = re.compile(
    r"(?<!un)trusted|secret|token|passw|credential|key", re.IGNORECASE
)


def test_field_names_avoid_sensitive_name_heuristic() -> None:
    flagged = [
        name
        for name in VultronReportCaseLink.model_fields
        if _SENSITIVE_NAME.search(name)
    ]
    assert flagged == []


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("trusted_case_creator_id", "case_creator_id"),
        ("trusted_case_actor_id", "case_manager_id"),
    ],
)
def test_a_retired_key_is_refused_naming_the_reset(old: str, new: str) -> None:
    with pytest.raises(ValidationError, match="must be reset") as excinfo:
        VultronReportCaseLink.model_validate(
            {"report_id": REPORT_ID, old: CREATOR_ID}
        )
    assert repr(old) in str(excinfo.value)
    assert repr(new) in str(excinfo.value)


def test_a_retired_key_is_refused_beside_its_replacement() -> None:
    with pytest.raises(ValidationError, match="must be reset"):
        VultronReportCaseLink.model_validate(
            {
                "report_id": REPORT_ID,
                "case_manager_id": MANAGER_ID,
                "trusted_case_actor_id": "https://example.org/actors/stale",
            }
        )


def test_dump_round_trips_under_the_new_keys() -> None:
    link = VultronReportCaseLink(
        report_id=REPORT_ID,
        case_creator_id=CREATOR_ID,
        case_manager_id=MANAGER_ID,
    )
    assert VultronReportCaseLink.model_validate(link.model_dump()) == link


def test_constructor_accepts_new_field_names() -> None:
    link = VultronReportCaseLink(
        report_id=REPORT_ID,
        case_creator_id=CREATOR_ID,
        case_manager_id=MANAGER_ID,
    )
    assert link.case_creator_id == CREATOR_ID
    assert link.case_manager_id == MANAGER_ID
