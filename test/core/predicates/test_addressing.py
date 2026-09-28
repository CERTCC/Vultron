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
"""Unit tests for ``vultron.core.predicates.addressing`` (#2667)."""

import pytest

from vultron.core.predicates.addressing import is_addressed_to, same_actor_id

VENDOR = "https://example.org/actors/vendor"


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (VENDOR, VENDOR, True),
        (VENDOR, VENDOR + "/", True),
        (VENDOR + "/", VENDOR, True),
        (VENDOR, "vendor", False),
        (VENDOR, "https://other.example/actors/vendor", False),
    ],
    ids=[
        "exact",
        "trailing-slash",
        "trailing-slash-left",
        "slug",
        "other-host",
    ],
)
def test_same_actor_id(a: str, b: str, expected: bool) -> None:
    assert same_actor_id(a, b) is expected


@pytest.mark.parametrize(
    ("recipients", "expected"),
    [
        ([VENDOR], True),
        (["https://example.org/actors/finder", VENDOR + "/"], True),
        (["vendor"], False),
        ([], False),
    ],
    ids=["exact", "trailing-slash-among-others", "slug", "empty"],
)
def test_is_addressed_to(recipients: list[str], expected: bool) -> None:
    assert is_addressed_to(VENDOR, recipients) is expected
