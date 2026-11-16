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

"""The ``REFUSED (IDs)`` group: found, stripped, and added (SL-03-004)."""

import pytest

from vultron.core.models.refusal_wording import (
    carries_refusal_group,
    with_refusal_group,
    without_refusal_group,
)


@pytest.mark.spec("SL-03-004")
@pytest.mark.parametrize(
    ("reason", "facts"),
    [
        (
            "Sender 'a' is not the Case Owner — REFUSED (HP-01-006)",
            "Sender 'a' is not the Case Owner",
        ),
        ("p is gone — removal REFUSED (CM-31-003)", "p is gone"),
        ("no case — REFUSED (HP-01-006, DEMOMA-07-003 step 1)", "no case"),
        ("a — REFUSED (X-01-001); b — REFUSED (Y-01-001)", "a; b"),
        ("REFUSED (HP-01-006)", ""),
        ("already closed (CM-23-018)", "already closed (CM-23-018)"),
    ],
)
def test_without_refusal_group_keeps_the_facts(
    reason: str, facts: str
) -> None:
    assert without_refusal_group(reason) == facts
    assert not carries_refusal_group(without_refusal_group(reason))


@pytest.mark.spec("SL-03-002")
def test_a_reason_with_its_own_group_is_logged_unchanged() -> None:
    reason = "x — REFUSED (HP-01-006)"
    assert with_refusal_group(reason) == reason


@pytest.mark.spec("SL-03-002", "HP-01-003")
def test_a_reason_without_a_group_gains_hp_01_003() -> None:
    assert with_refusal_group("ProbeBT: no") == (
        "ProbeBT: no — REFUSED (HP-01-003)"
    )
