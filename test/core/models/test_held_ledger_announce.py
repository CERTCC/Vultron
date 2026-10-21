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
"""Tests for the ``HeldLedgerAnnounce`` index row (SYNC-14-001)."""

import pytest
from pydantic import ValidationError

from vultron.core.models.held_ledger_announce import HeldLedgerAnnounce

_CASE = "https://example.org/cases/case 1"
_FIELDS = {
    "case_id": _CASE,
    "prev_log_hash": "a" * 64,
    "log_index": 3,
    "entry_hash": "b" * 64,
    "entry_id": "https://example.org/entries/3",
    "activity_id": "https://example.org/activities/announce-3",
}


@pytest.mark.spec("SYNC-14-001")
def test_id_is_derived_from_the_case_and_predecessor():
    held = HeldLedgerAnnounce.model_validate(_FIELDS)

    assert held.id_ == HeldLedgerAnnounce.build_id(_CASE, "a" * 64)
    assert held.id_ == (
        "held-ledger-announce/https%3A%2F%2Fexample.org%2Fcases%2Fcase%201/"
        + "a" * 64
    )


def test_two_predecessors_in_one_case_get_two_ids():
    assert HeldLedgerAnnounce.build_id(_CASE, "a" * 64) != (
        HeldLedgerAnnounce.build_id(_CASE, "c" * 64)
    )


def test_an_explicit_id_is_replaced_by_the_derived_one():
    held = HeldLedgerAnnounce.model_validate(
        {**_FIELDS, "id": "urn:uuid:sender-chosen"}
    )

    assert held.id_ == HeldLedgerAnnounce.build_id(_CASE, "a" * 64)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("log_index", -1),
        ("prev_log_hash", ""),
        ("entry_hash", ""),
        ("activity_id", "not a uri"),
        ("case_id", ""),
    ],
)
def test_invalid_fields_are_refused(field, value):
    with pytest.raises(ValidationError):
        HeldLedgerAnnounce.model_validate({**_FIELDS, field: value})


def test_unknown_keys_are_refused():
    with pytest.raises(ValidationError):
        HeldLedgerAnnounce.model_validate({**_FIELDS, "entry": {"id": "x"}})
