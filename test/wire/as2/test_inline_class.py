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

"""Which class reads an inline object, inside a preview and out (ADR-0217).

The unknown-key partition and the parser both ask :func:`inline_class`, so
these rows hold its answers; the end-to-end reading of a preview is held by
``test_redaction_marker.py``.
"""

import pytest

from vultron.core.models.case_preview import CasePreview
from vultron.core.models.dimensions import EmDimension
from vultron.core.models.embargo_termination import EmbargoTermination
from vultron.core.models.preview_object import is_loose_form_of, loose_form
from vultron.core.models.vulnerability_item import (
    VulnerabilityItem,
    VulnerabilityItemId,
)
from vultron.wire.as2.inline_class import (
    _shown_form,
    inline_class,
    is_preview_form,
    reads_inside_preview,
)

ITEM = {"type": "VulnerabilityItem", "ids": []}
PERSON = {"type": "Person", "id": "https://example.org/actors/bob"}


def test_outside_a_preview_the_type_names_the_full_class() -> None:
    assert inline_class(ITEM) is VulnerabilityItem


@pytest.mark.spec("MV-12-006")
def test_inside_a_preview_a_field_s_loose_form_reads_the_object() -> None:
    slots = (loose_form(VulnerabilityItem),)

    assert inline_class(ITEM, slots=slots, in_preview=True) is slots[0]


@pytest.mark.spec("MV-12-006")
def test_inside_a_preview_a_free_form_field_reads_its_type_s_loose_form() -> (
    None
):
    shown = inline_class(ITEM, in_preview=True)

    assert shown is loose_form(VulnerabilityItem)


def test_an_actor_inside_a_preview_is_read_whole() -> None:
    """An actor is named by its own profile (AKM-05-017), never cut."""
    whole = inline_class(PERSON)

    assert whole is not None and not is_preview_form(whole)
    assert inline_class(PERSON, in_preview=True) is whole


def test_a_dict_without_a_type_takes_its_field_s_one_loose_form() -> None:
    entry = loose_form(EmbargoTermination)

    assert inline_class({}, slots=(entry,), in_preview=True) is entry


def test_a_dict_without_a_type_and_two_loose_forms_is_left_to_its_field() -> (
    None
):
    """Two loose forms leave no one class to read it, so its field
    validates it, as outside a preview."""
    slots = (loose_form(EmbargoTermination), loose_form(VulnerabilityItemId))

    assert inline_class({}, slots=slots, in_preview=True) is None


def test_a_class_with_its_own_wire_shape_is_shown_whole() -> None:
    """A dimension is written as its bare state, so it has no loose form."""
    assert _shown_form(EmDimension) is EmDimension


def test_a_preview_reads_its_own_fields_inside_a_preview() -> None:
    assert is_preview_form(CasePreview)
    assert reads_inside_preview((CasePreview,), in_preview=False)
    assert not reads_inside_preview((VulnerabilityItem,), in_preview=False)
    assert is_loose_form_of(
        loose_form(VulnerabilityItem).model_validate({}), VulnerabilityItem
    )
