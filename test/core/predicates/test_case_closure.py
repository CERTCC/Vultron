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

"""The one "case is fully closed" condition (CM-23-013)."""

from dataclasses import dataclass

import pytest

from vultron.core.predicates.case_closure import (
    CASE_FULLY_CLOSED_EVENT_TYPE,
    ledger_records_full_closure,
)


@dataclass
class _Entry:
    event_type: str


@pytest.mark.spec("CM-23-013")
def test_a_ledger_with_case_fully_closed_is_closed() -> None:
    entries = [_Entry("close_case"), _Entry(CASE_FULLY_CLOSED_EVENT_TYPE)]
    assert ledger_records_full_closure(entries)


@pytest.mark.spec("CM-23-013")
def test_order_does_not_matter() -> None:
    entries = [_Entry(CASE_FULLY_CLOSED_EVENT_TYPE), _Entry("add_note")]
    assert ledger_records_full_closure(entries)


@pytest.mark.spec("CM-23-013")
@pytest.mark.parametrize(
    "types", [[], ["close_case"], ["close_case", "add_participant_status"]]
)
def test_a_ledger_without_it_is_open(types: list[str]) -> None:
    assert not ledger_records_full_closure(_Entry(t) for t in types)
