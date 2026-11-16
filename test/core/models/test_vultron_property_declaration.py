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
"""The Vultron property marker carries a definition and a value kind (VM-10-008).

``vultron_property`` builds the marker a field passes as its
``json_schema_extra``; ``declared_vultron_property`` reads it back.  These
tests pin what each accepts and refuses.
"""

import pytest
from pydantic.fields import FieldInfo

from vultron.core.models.base.context import (
    VULTRON_PROPERTY_KEY,
    PropertyValueKind,
    VultronPropertyDeclaration,
    declared_vultron_property,
    vultron_property,
)

Kind = PropertyValueKind


@pytest.mark.spec("VM-10-008")
def test_the_marker_round_trips_through_a_field() -> None:
    extra = vultron_property("The ids of things", Kind.SET, items=Kind.IRI)
    assert extra == {
        VULTRON_PROPERTY_KEY: {
            "definition": "The ids of things",
            "kind": "set",
            "items": "iri",
        }
    }
    declaration = declared_vultron_property(FieldInfo(json_schema_extra=extra))
    assert declaration == VultronPropertyDeclaration(
        definition="The ids of things", kind=Kind.SET, items=Kind.IRI
    )


@pytest.mark.spec("VM-10-008")
def test_a_scalar_marker_stores_no_items() -> None:
    extra = vultron_property("A count", Kind.PLAIN)
    assert extra == {
        VULTRON_PROPERTY_KEY: {"definition": "A count", "kind": "plain"}
    }


@pytest.mark.parametrize(
    "extra",
    [None, {}, {"format": "date-time"}],
    ids=["no-extra", "empty", "other-keys"],
)
def test_an_unmarked_field_declares_no_property(extra: object) -> None:
    info = FieldInfo(json_schema_extra=extra)  # type: ignore[arg-type]
    assert declared_vultron_property(info) is None


@pytest.mark.spec("VM-10-008")
@pytest.mark.parametrize(
    "marker",
    [
        True,
        {},
        {"kind": "plain"},
        {"definition": "A count"},
        {"definition": "A count", "kind": "plain", "range": "int"},
        {"definition": 1, "kind": "plain"},
    ],
    ids=[
        "bare-flag",
        "empty",
        "no-definition",
        "no-kind",
        "unknown-key",
        "non-string",
    ],
)
def test_a_marker_without_a_definition_and_kind_is_refused(
    marker: object,
) -> None:
    """The former bare ``True`` flag, or any other shape, cannot pass."""
    info = FieldInfo(json_schema_extra={VULTRON_PROPERTY_KEY: marker})  # type: ignore[dict-item]
    with pytest.raises(TypeError):
        declared_vultron_property(info)


def test_a_marker_with_an_unknown_kind_is_refused() -> None:
    info = FieldInfo(
        json_schema_extra={
            VULTRON_PROPERTY_KEY: {"definition": "A count", "kind": "number"}
        }
    )
    with pytest.raises(ValueError, match="number"):
        declared_vultron_property(info)


@pytest.mark.spec("VM-10-008")
@pytest.mark.parametrize(
    "definition",
    ["", "   ", " leading space", "two\nlines"],
    ids=["empty", "blank", "padded", "multi-line"],
)
def test_a_definition_is_one_non_blank_line(definition: str) -> None:
    with pytest.raises(ValueError, match="definition"):
        vultron_property(definition, Kind.PLAIN)


@pytest.mark.parametrize(
    "kind", [Kind.PLAIN, Kind.IRI, Kind.JSON], ids=lambda k: k.value
)
def test_a_scalar_kind_declares_no_items(kind: PropertyValueKind) -> None:
    with pytest.raises(ValueError, match="scalar"):
        vultron_property("A value", kind, items=Kind.IRI)


@pytest.mark.parametrize(
    "items",
    [Kind.JSON, Kind.LIST, Kind.SET, Kind.INDEX],
    ids=lambda k: k.value,
)
def test_a_container_holds_only_plain_or_iri_items(
    items: PropertyValueKind,
) -> None:
    with pytest.raises(ValueError, match="items"):
        vultron_property("Some values", Kind.LIST, items=items)
