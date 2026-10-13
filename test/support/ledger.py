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

"""Read what a store's canonical case ledger holds, for test assertions."""

from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.ports.datalayer import DataLayer


def committed_event_types(dl: DataLayer, case_id: str) -> list[str]:
    """``event_type`` of every ledger entry committed for *case_id*."""
    return [
        str(entry.event_type)
        for entry in dl.list_objects("CaseLedgerEntry")
        if isinstance(entry, CaseLedgerEntry) and entry.case_id == case_id
    ]


def ledger_entries(dl: DataLayer, case_id: str) -> list[CaseLedgerEntry]:
    """Every ledger entry committed for *case_id*, in chain order."""
    entries = [
        entry
        for entry in dl.list_objects("CaseLedgerEntry")
        if isinstance(entry, CaseLedgerEntry) and entry.case_id == case_id
    ]
    return sorted(entries, key=lambda entry: entry.log_index)


def creation_entry_sequence(
    dl: DataLayer, case: VulnerabilityCase
) -> list[tuple[str, str]]:
    """The ``(event_type, object id)`` entries creating *case* commits.

    One rule for every creation path, read off the resulting case file: the
    genesis ``create_case``, each linked report, each participant's statuses
    in roster order, then each case status (CLP-07-013).  Two paths that
    produce the same case therefore commit the same sequence.
    """
    sequence = [("create_case", case.id_)]
    sequence += [
        ("add_report_to_case", str(_as_id(report)))
        for report in case.vulnerability_reports
    ]
    for participant_ref in case.case_participants:
        participant = dl.read(str(_as_id(participant_ref)))
        assert isinstance(participant, CaseParticipant), participant_ref
        sequence += [
            ("add_participant_status_to_participant", status.id_)
            for status in participant.participant_statuses
        ]
    sequence += [
        ("add_case_status_to_case", str(_as_id(status)))
        for status in case.case_statuses
    ]
    return sequence
