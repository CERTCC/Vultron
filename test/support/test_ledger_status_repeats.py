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

"""Tests for the shared status-entry check's two scopes.

The universal CI invariant passes :data:`CASE_STATUS_TYPES`, because a
same-state ``ParticipantStatus`` is valid protocol behaviour (BTND-10-001);
the exchange-demo checks pass :data:`STATUS_SEMANTIC_TYPES`, because no
exchange demo confirms a state it already holds (#5125).
"""

from test.support.ledger_status_repeats import (
    CASE_STATUS_TYPES,
    STATUS_SEMANTIC_TYPES,
    StatusEntry,
    status_entry_faults,
)

_PARTICIPANT = "https://example.org/cases/c/participants/vendor"


def _participant_status(index: int, vf: str) -> StatusEntry:
    return (
        index,
        "add_participant_status_to_participant",
        {
            "target": {"id": _PARTICIPANT},
            "object": {
                "id": f"urn:uuid:ps-{index}",
                "name": f"ACCEPTED {vf}",
                "rmState": "ACCEPTED",
                "vfState": vf,
            },
        },
    )


_CONFIRMATION = [
    _participant_status(0, "Vf"),
    _participant_status(1, "Vf"),
    _participant_status(2, "VF"),
]


def test_case_status_scope_allows_a_participant_confirmation():
    assert (
        status_entry_faults(_CONFIRMATION, repeat_types=CASE_STATUS_TYPES)
        == []
    )


def test_demo_scope_flags_a_participant_confirmation():
    faults = status_entry_faults(
        iter(_CONFIRMATION), repeat_types=STATUS_SEMANTIC_TYPES
    )
    assert len(faults) == 1
    assert "entry 1" in faults[0]
    assert "repeats entry 0" in faults[0]
    assert _PARTICIPANT in faults[0]
