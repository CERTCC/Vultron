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
"""What one entry's payload snapshot records (CEH-04).

An ``Invite`` records no change: the full-case Invite carries a copy of the
case and the stub Invite the case's preview (ADR-0205), so nothing under
one is read as the case's state.
"""

import pytest

from vultron.measure.history.snapshot import snapshot_records

_CASE = "https://example.org/cases/snap"
_STATUS = {
    "id": "https://example.org/statuses/s1",
    "type": "CaseStatus",
    "context": _CASE,
    "emState": "ACTIVE",
}
_PARTICIPANT = {
    "id": "https://example.org/participants/p1",
    "type": "CaseParticipant",
    "attributedTo": "https://example.org/actors/vendor",
    "caseRoles": ["VENDOR"],
}
_WHOLE_CASE = {
    "id": _CASE,
    "type": "VulnerabilityCase",
    "caseParticipants": [_PARTICIPANT],
    "caseStatuses": [_STATUS],
}
_PREVIEWED_CASE = {
    "id": _CASE,
    "type": "VulnerabilityCase",
    "preview": {
        "id": "urn:uuid:preview",
        "type": "VulnerabilityCaseStub",
        "summary": "A case to join",
        "caseStatus": _STATUS,
    },
}


def _invite(case: dict) -> dict:
    return {
        "type": "Invite",
        "object": case,
        "target": "https://example.org/actors/invitee",
    }


@pytest.mark.spec("CEH-04-013")
@pytest.mark.parametrize(
    "snapshot",
    [
        pytest.param(_invite(_WHOLE_CASE), id="full-case-invite"),
        pytest.param(_invite(_PREVIEWED_CASE), id="stub-invite"),
        pytest.param(
            {"type": "Accept", "object": _invite(_WHOLE_CASE)},
            id="accept-of-full-case-invite",
        ),
        pytest.param(
            {"type": "Accept", "object": _invite(_PREVIEWED_CASE)},
            id="accept-of-stub-invite",
        ),
    ],
)
def test_nothing_under_an_invite_is_read_as_state(snapshot: dict) -> None:
    """An Invite's case copy or preview records no participant or status."""
    records = snapshot_records(snapshot)

    assert records.participants == []
    assert records.case_statuses == []
    assert records.register_entries == []


@pytest.mark.spec("CEH-04-013")
def test_the_same_case_outside_an_invite_is_read() -> None:
    """The case the Invite carries is read when an entry carries it itself."""
    records = snapshot_records({"type": "Announce", "object": _WHOLE_CASE})

    assert [p.actor for p in records.participants] == [
        "https://example.org/actors/vendor"
    ]
    assert records.case_statuses == [_STATUS]
