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

from vultron.core.predicates.addressing import (
    distinct_recipients,
    is_addressed_to,
    normalise_actor_id,
    participant_id_for_actor,
    same_actor_id,
)

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
@pytest.mark.spec("CLP-10-021")
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
@pytest.mark.spec("CLP-10-021")
def test_is_addressed_to(recipients: list[str], expected: bool) -> None:
    assert is_addressed_to(VENDOR, recipients) is expected


@pytest.mark.parametrize("spelling", [VENDOR, VENDOR + "/"])
def test_normalise_actor_id_drops_trailing_slash(spelling: str) -> None:
    assert normalise_actor_id(spelling) == VENDOR


@pytest.mark.parametrize(
    ("recipients", "expected"),
    [
        ([VENDOR], [VENDOR]),
        ([VENDOR, VENDOR + "/"], [VENDOR]),
        ([None, "", VENDOR], [VENDOR]),
        (
            [VENDOR, "https://example.org/actors/finder"],
            [VENDOR, "https://example.org/actors/finder"],
        ),
        ([], []),
    ],
    ids=[
        "one",
        "two-spellings-one-actor",
        "drops-empty",
        "two-actors",
        "empty",
    ],
)
@pytest.mark.spec("EP-09-010")
def test_distinct_recipients(
    recipients: list[str | None], expected: list[str]
) -> None:
    assert distinct_recipients(recipients) == expected


@pytest.mark.parametrize(
    ("index", "expected"),
    [
        ({VENDOR: "p-1"}, "p-1"),
        ({VENDOR + "/": "p-1"}, "p-1"),
        ({"https://example.org/actors/finder": "p-2"}, None),
        ({"vendor": "p-3"}, None),
        ({}, None),
    ],
    ids=["exact", "trailing-slash-key", "another-actor", "slug", "empty"],
)
@pytest.mark.spec("CLP-10-021")
def test_participant_id_for_actor(
    index: dict[str, str], expected: str | None
) -> None:
    """The index key is matched with ``same_actor_id`` (#4772)."""
    assert participant_id_for_actor(index, VENDOR) == expected
