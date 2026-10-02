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

"""A ``ReportCaseLink`` row stored before #4020's field rename still loads.

The row is inserted as a verbatim ``Record`` (no model serialization), so
this exercises the read path a database written before the rename takes.
"""

from vultron.adapters.driven.db_record import Record
from vultron.core.models.report_case_link import VultronReportCaseLink

REPORT_ID = "https://example.org/reports/r-legacy"
CASE_ID = "https://example.org/cases/c-legacy"
CREATOR_ID = "https://example.org/actors/vendor"
MANAGER_ID = "https://example.org/actors/vendor/case-actor"


def _legacy_row() -> Record:
    link_id = VultronReportCaseLink.build_id(REPORT_ID)
    return Record(
        id_=link_id,
        type_="ReportCaseLink",
        data_={
            "id": link_id,
            "type": "ReportCaseLink",
            "name": None,
            "report_id": REPORT_ID,
            "case_id": CASE_ID,
            "trusted_case_creator_id": CREATOR_ID,
            "trusted_case_actor_id": MANAGER_ID,
            "proposal_rejected": False,
            "rejection_reason": None,
            "rm_state": "RECEIVED",
        },
    )


def test_pre_rename_row_reads_back_with_trust_anchors(dl) -> None:
    dl.create(_legacy_row())

    link = dl.read(VultronReportCaseLink.build_id(REPORT_ID))

    assert isinstance(link, VultronReportCaseLink)
    assert link.case_id == CASE_ID
    assert link.case_creator_id == CREATOR_ID
    assert link.case_manager_id == MANAGER_ID


def test_resaving_pre_rename_row_migrates_its_keys(dl) -> None:
    dl.create(_legacy_row())
    link = dl.read(VultronReportCaseLink.build_id(REPORT_ID))
    assert isinstance(link, VultronReportCaseLink)

    dl.save(link)

    row = dl.get("ReportCaseLink", link.id_)
    assert isinstance(row, dict)
    stored = row["data_"]
    assert "trusted_case_creator_id" not in stored
    assert "trusted_case_actor_id" not in stored
    assert stored["case_creator_id"] == CREATOR_ID
    assert stored["case_manager_id"] == MANAGER_ID
