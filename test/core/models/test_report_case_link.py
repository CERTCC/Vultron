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

"""Tests for ``VultronReportCaseLink`` field names and their legacy aliases.

#4020 renamed ``trusted_case_creator_id`` to ``case_creator_id`` and
``trusted_case_actor_id`` to ``case_manager_id`` so CodeQL's sensitive-name
heuristic stops reading actor ids as secrets.  A link persisted before the
rename MUST still load, so its CBT-01-006 trust anchors survive the upgrade.
"""

import re

import pytest

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
    "creator_key, manager_key",
    [
        ("trusted_case_creator_id", "trusted_case_actor_id"),
        ("case_creator_id", "case_manager_id"),
    ],
)
def test_link_loads_under_old_and_new_keys(
    creator_key: str, manager_key: str
) -> None:
    link = VultronReportCaseLink.model_validate(
        {
            "report_id": REPORT_ID,
            creator_key: CREATOR_ID,
            manager_key: MANAGER_ID,
        }
    )
    assert link.case_creator_id == CREATOR_ID
    assert link.case_manager_id == MANAGER_ID


def test_dump_writes_only_new_keys_and_round_trips() -> None:
    legacy = VultronReportCaseLink.model_validate(
        {
            "report_id": REPORT_ID,
            "trusted_case_creator_id": CREATOR_ID,
            "trusted_case_actor_id": MANAGER_ID,
        }
    )
    dumped = legacy.model_dump(by_alias=True)
    assert "trusted_case_creator_id" not in dumped
    assert "trusted_case_actor_id" not in dumped
    assert dumped["case_creator_id"] == CREATOR_ID
    assert dumped["case_manager_id"] == MANAGER_ID
    assert VultronReportCaseLink.model_validate(dumped) == legacy


def test_new_key_wins_when_both_spellings_present() -> None:
    link = VultronReportCaseLink.model_validate(
        {
            "report_id": REPORT_ID,
            "case_manager_id": MANAGER_ID,
            "trusted_case_actor_id": "https://example.org/actors/stale",
        }
    )
    assert link.case_manager_id == MANAGER_ID
    assert "trusted_case_actor_id" not in link.model_dump(by_alias=True)


def test_constructor_accepts_new_field_names() -> None:
    link = VultronReportCaseLink(
        report_id=REPORT_ID,
        case_creator_id=CREATOR_ID,
        case_manager_id=MANAGER_ID,
    )
    assert link.case_creator_id == CREATOR_ID
    assert link.case_manager_id == MANAGER_ID
