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

"""The report's target column names every case and participant (DRPT-03-009).

The target cell, and the summary that embeds it, label each reference through
the shared resolver the case-history dump uses, so no committed recording
renders a ``urn:uuid`` id or a bare UUID there.
"""

import re

import pytest

from vultron.demo.recordings.layout import RECORDINGS_DIR, recording_path
from vultron.demo.report import CaseTimelineEvent, build_timeline
from vultron.measure.ledger import read_ledger_file

#: A ``urn:uuid`` id, or a UUID's leading groups with ``-`` or a space between
#: them (the URI heuristic title-cases a UUID into space-separated groups).
_OPAQUE = re.compile(r"urn:uuid|[0-9a-f]{8}[- ][0-9a-f]{4}", re.IGNORECASE)

_SCENARIOS = sorted(
    path.name
    for path in RECORDINGS_DIR.iterdir()
    if recording_path(path.name).is_file()
)

_CASE = "urn:uuid:7699e8c6-b723-4ec7-98ae-00c35f558ecf"
_PARTICIPANT = "urn:uuid:46f4bf85-d0e7-4d24-90dd-000000000001"
_VENDOR = "http://vendor:7999/api/v2/actors/vendor"


def _timeline(scenario: str) -> list[CaseTimelineEvent]:
    ledger = read_ledger_file(recording_path(scenario))
    return build_timeline({"case-actor": ledger.entries})


def test_every_scenario_has_a_recording():
    assert _SCENARIOS


@pytest.mark.spec("DRPT-03-009")
@pytest.mark.parametrize("scenario", _SCENARIOS)
def test_no_target_cell_shows_an_opaque_id(scenario):
    opaque = [
        (event.log_index, event.target_label)
        for event in _timeline(scenario)
        if event.target_label and _OPAQUE.search(event.target_label)
    ]
    assert opaque == []


@pytest.mark.spec("DRPT-03-009")
@pytest.mark.parametrize("scenario", _SCENARIOS)
def test_no_summary_shows_an_opaque_id(scenario):
    opaque = [
        (event.log_index, event.summary)
        for event in _timeline(scenario)
        if _OPAQUE.search(event.summary)
    ]
    assert opaque == []


def _entry(payload: dict, log_index: int = 1) -> dict:
    return {
        "caseId": _CASE,
        "logIndex": log_index,
        "semanticType": "add_participant_status_to_participant",
        "entryHash": f"{log_index:064x}",
        "payloadSnapshot": payload,
    }


def _seat() -> dict:
    """A case snapshot that seats the vendor through its participant."""
    return _entry(
        {
            "type": "Create",
            "actor": _VENDOR,
            "object": {
                "id": _CASE,
                "type": "VulnerabilityCase",
                "caseParticipants": [
                    {
                        "id": _PARTICIPANT,
                        "type": "CaseParticipant",
                        "attributedTo": _VENDOR,
                    }
                ],
            },
        },
        log_index=0,
    )


@pytest.mark.spec("DRPT-03-001")
def test_a_case_destination_reads_case():
    note = _entry(
        {
            "type": "Add",
            "actor": _VENDOR,
            "object": {"id": "urn:uuid:n1", "type": "Note"},
            "target": _CASE,
        }
    )
    events = build_timeline({"case-actor": [note]})
    assert events[0].target_label == "note → case"


@pytest.mark.spec("DRPT-03-001")
def test_a_participant_destination_reads_the_actor_it_stands_for():
    named = _entry(
        {
            "type": "Create",
            "actor": {"id": _VENDOR, "type": "Organization", "name": "Vendor"},
            "object": {"id": "urn:uuid:r1", "type": "VulnerabilityReport"},
        },
        log_index=2,
    )
    status = _entry(
        {
            "type": "Add",
            "actor": _VENDOR,
            "object": {"id": "urn:uuid:s1", "type": "ParticipantStatus"},
            "target": _PARTICIPANT,
        }
    )
    events = build_timeline({"case-actor": [_seat(), status, named]})
    by_index = {event.log_index: event for event in events}
    assert by_index[1].target_label == "participant status → Vendor"
