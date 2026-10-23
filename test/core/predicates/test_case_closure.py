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

"""The one "case is fully closed" condition (CM-23-013, ADR-0152)."""

from dataclasses import dataclass, field

import pytest

from vultron.core.predicates.case_closure import (
    closure_boundary_indices,
    entry_closes_case_manager,
    ledger_records_full_closure,
)

_MANAGER = "https://example.org/actors/case-actor"
_OWNER = "https://example.org/actors/vendor"
_STATUS = "add_participant_status_to_participant"


def _status(actor: str, subject: str, rm: str) -> dict[str, object]:
    """A participant status entry's snapshot, as the ledger carries it."""
    return {
        "type": "Add",
        "actor": actor,
        "object": {
            "type": "ParticipantStatus",
            "attributedTo": subject,
            "rmState": rm,
        },
    }


@dataclass
class _Entry:
    semantic_type: str
    payload_snapshot: dict[str, object] = field(default_factory=dict)


_MANAGER_CLOSED = _Entry(_STATUS, _status(_MANAGER, _MANAGER, "CLOSED"))


@pytest.mark.spec("CM-23-013")
def test_the_managers_own_closed_status_closes_the_case() -> None:
    entries = [_Entry("close_case"), _MANAGER_CLOSED]
    assert ledger_records_full_closure(entries, _MANAGER)


@pytest.mark.spec("CM-23-013")
def test_order_does_not_matter() -> None:
    entries = [_MANAGER_CLOSED, _Entry("add_note_to_case")]
    assert ledger_records_full_closure(entries, _MANAGER)


@pytest.mark.spec("CM-23-013")
def test_an_id_spelled_with_a_trailing_slash_still_matches() -> None:
    entry = _Entry(_STATUS, _status(f"{_MANAGER}/", _MANAGER, "CLOSED"))
    assert ledger_records_full_closure([entry], _MANAGER)


@pytest.mark.spec("CM-23-013")
@pytest.mark.parametrize(
    "entry",
    [
        # The Case Owner's closure, which the CASE_MANAGER writes for it.
        _Entry(_STATUS, _status(_MANAGER, _OWNER, "CLOSED")),
        # The CASE_MANAGER's own earlier rungs.
        _Entry(_STATUS, _status(_MANAGER, _MANAGER, "ACCEPTED")),
        # A status about the CASE_MANAGER that it did not send.
        _Entry(_STATUS, _status(_OWNER, _MANAGER, "CLOSED")),
        # The right status under another semantic type.
        _Entry("close_case", _status(_MANAGER, _MANAGER, "CLOSED")),
        # A snapshot with no status object.
        _Entry(_STATUS, {"type": "Add", "actor": _MANAGER}),
    ],
)
def test_no_other_entry_closes_the_case(entry: _Entry) -> None:
    assert not ledger_records_full_closure([entry], _MANAGER)
    assert not entry_closes_case_manager(
        entry.semantic_type, entry.payload_snapshot, _MANAGER
    )


@pytest.mark.spec("CM-23-013")
def test_an_empty_ledger_is_open() -> None:
    assert not ledger_records_full_closure([], _MANAGER)


@pytest.mark.spec("CM-23-013")
def test_boundary_indices_read_an_exported_ledger() -> None:
    rows: list[dict[str, object]] = [
        {"log_index": 4, "semantic_type": "close_case"},
        {
            "log_index": 6,
            "semantic_type": _STATUS,
            "payload_snapshot": _MANAGER_CLOSED.payload_snapshot,
        },
        {
            "log_index": 5,
            "semantic_type": _STATUS,
            "payload_snapshot": _status(_MANAGER, _OWNER, "CLOSED"),
        },
        # A row with no log index is not a ledger position.
        {
            "semantic_type": _STATUS,
            "payload_snapshot": _MANAGER_CLOSED.payload_snapshot,
        },
    ]
    assert closure_boundary_indices(rows, _MANAGER) == [6]
