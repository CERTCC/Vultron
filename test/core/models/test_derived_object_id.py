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
"""Tests for the one derivation of stable object ids — ID-04-004."""

import uuid

import pytest

from vultron.core.behaviors.case.nodes.embargo import creation_time_embargo_id
from vultron.core.behaviors.case.nodes.proposal_announcement import (
    create_case_activity_id,
)
from vultron.core.models.activity_ids import (
    derived_activity_id,
    derived_object_id,
)


def _hand_built(name: str) -> str:
    return f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, name)}"


@pytest.mark.spec("ID-04-004")
def test_a_single_part_derives_the_uuid5_of_that_part():
    assert derived_object_id("https://example.org/a") == _hand_built(
        "https://example.org/a"
    )


@pytest.mark.spec("ID-04-004")
def test_parts_are_joined_by_a_separator_no_iri_contains():
    assert derived_object_id("a", "b") == _hand_built("a\x1fb")
    assert derived_object_id("a", "b") != derived_object_id("ab")


def test_derived_activity_id_is_the_shared_derivation():
    assert derived_activity_id("kind", "x") == derived_object_id("kind", "x")


def test_callers_keep_their_ids():
    case_id = "https://example.org/cases/1"
    assert creation_time_embargo_id(case_id) == _hand_built(
        f"{case_id}#creation-time-embargo"
    )
    assert create_case_activity_id(case_id) == _hand_built(
        f"{case_id}#create-case"
    )
