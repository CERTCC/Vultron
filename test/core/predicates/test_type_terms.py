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
"""Core readers ask whether a received ``type`` names a type (ADR-0196)."""

import pytest

from vultron.core.predicates.type_terms import (
    body_type_terms,
    first_named,
    names_type,
    type_terms,
)
from vultron.core.services.case_copy import _names_its_case, _snapshot_objects

pytestmark = pytest.mark.spec("VM-03-006")


@pytest.mark.parametrize(
    "value, terms",
    [
        ("Join", ("Join",)),
        (["Foo", "Join"], ("Foo", "Join")),
        (["Foo", 7, None, " ", "Join"], ("Foo", "Join")),
        ([], ()),
        (None, ()),
        ({"type": "Join"}, ()),
        ("", ()),
    ],
)
def test_type_terms_reads_a_string_or_the_strings_of_a_list(value, terms):
    assert type_terms(value) == terms


def test_body_type_terms_reads_either_key():
    assert body_type_terms({"type": ["Foo", "Join"]}) == ("Foo", "Join")
    assert body_type_terms({"type_": "Join"}) == ("Join",)


def test_membership_and_first_named():
    assert names_type(["Foo", "Join"], {"Join"})
    assert not names_type(["Foo"], {"Join"})
    assert first_named(["Foo", "Note", "Join"], {"Join", "Note"}) == "Note"
    assert first_named("Foo", {"Join"}) is None


def test_a_case_named_by_a_type_list_is_not_descended_into():
    """An act that only names its case is read through a type list too; the
    list is unhashable, so a set-membership test on it once raised."""
    case = {"type": ["Foo", "VulnerabilityCase"], "id": "https://e.org/c/1"}
    act = {"type": ["Foo", "Join"], "id": "https://e.org/a/1", "object": case}

    assert _names_its_case(act, "object", case)
    assert list(_snapshot_objects(act)) == [act]
