"""Optional string fields on a wire object refuse a blank value when it is built.

"If present, then non-empty" (CS-08-001) holds for every optional field whose
type has a string branch: the branch is the shared ``NonEmptyString``
(CS-08-002), so ``name=""``, ``summary=""``, ``content=""`` or
``mediaType=""`` is refused when the object is built, and an inbound blank is
refused at the parse edge. Nothing strips a blank on the way out, so a
serialized wire object can hold no empty-string field (VM-07-005). Before
#5739 ``as_Object(name="").to_json()`` emitted ``"name":""``.

Blank *references* in ``Any``-typed fields (``to``, ``context``, ...) are a
separate surface, tracked by #3894; they have no string branch to check here.

Spec: `specs/vocabulary-model.yaml` VM-07-005; `specs/code-style.yaml`
CS-08-001, CS-08-002.
"""

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

import json
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from test.architecture._vocab_example_corpus import activity_examples
from test.support.blank_strings import (
    BLANKS,
    declared_type,
    owner_of,
    rejects_blank,
    string_leaves,
)
from test.support.objects import make
from test.support.wire_vocab import import_all_wire_vocab
from vultron.core.models.base import CoreObject
from vultron.primitives import NonEmptyString
from vultron.subclasses import all_subclasses
from vultron.wire.as2.errors import VultronParseError
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.base.links import as_Link
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Create,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Person
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.base.objects.object_types import (
    as_Note,
    as_Place,
    as_Relationship,
    as_Tombstone,
)

#: Lower bound on how many fields the structural check visits, so a broken
#: import or a too-narrow filter cannot make it pass vacuously.
_MIN_STRING_FIELDS = 10

#: Each field the issue names, and the less common ones that shared its
#: ``str | None`` type, on the class that declares it.
_DECLARED_TEXT_FIELDS: list[tuple[type[BaseModel], str]] = [
    (as_Object, "name"),
    (as_Object, "summary"),
    (as_Object, "content"),
    (as_Object, "media_type"),
    (as_Object, "preview"),
    (as_Note, "content"),
    (as_Link, "rel"),
    (as_Link, "hreflang"),
    (as_Person, "preferred_username"),
    (as_Tombstone, "former_type"),
    (as_Relationship, "relationship"),
    (as_Place, "units"),
]


def wire_classes() -> dict[str, type[BaseModel]]:
    """Every ``as_Base`` subclass the wire package defines, by qualified name."""
    import_all_wire_vocab()
    classes: list[type[as_Base]] = [as_Base, *all_subclasses(as_Base)]
    found: dict[str, type[BaseModel]] = {
        cls.__qualname__: cls
        for cls in classes
        if cls.__module__.startswith("vultron.wire")
    }
    return dict(sorted(found.items()))


def wire_string_fields(cls: type[BaseModel]) -> dict[str, Any]:
    """``{field name: declared type}`` for the string fields *cls* declares.

    ``type_`` is left out: a class's ``Literal`` or enum decides it. A field a
    core class declares is the core ratchet's to judge
    (``test_core_reference_fields_reject_blank``), so ``owner_of`` keeps it out.
    """
    return {
        name: declared_type(field)
        for name, field in cls.model_fields.items()
        if name != "type_"
        and owner_of(cls, name) is cls
        and string_leaves(declared_type(field))
    }


def blank_admitting_wire_string_fields(cls: type[BaseModel]) -> list[str]:
    """Names of the string fields of *cls* that accept a blank."""
    return [
        name
        for name, annotation in wire_string_fields(cls).items()
        if not rejects_blank(annotation)
    ]


@pytest.mark.spec("CS-08-001")
@pytest.mark.spec("CS-08-002")
@pytest.mark.spec("VM-07-005")
def test_every_wire_string_field_refuses_a_blank() -> None:
    """No wire class declares a string field that admits ``""`` or ``"   "``.

    A field with a non-``None`` default counts too: a caller can still pass a
    blank, and the blank would be serialized.
    """
    offenders: list[str] = []
    examined = 0
    for qualname, cls in wire_classes().items():
        examined += len(wire_string_fields(cls))
        offenders += [
            f"{qualname}.{name}"
            for name in blank_admitting_wire_string_fields(cls)
        ]
    assert examined >= _MIN_STRING_FIELDS, examined
    assert not offenders, (
        "these wire string fields accept a blank (CS-08-001). Declare the "
        "string as NonEmptyString:\n" + "\n".join(f"  {o}" for o in offenders)
    )


def test_the_check_flags_a_bare_str_field() -> None:
    """A deliberately bad model proves the check can fail.

    A plain ``BaseModel``: it is never walked by :func:`wire_classes`, so it
    cannot leak into other tests.
    """

    class _Bad(BaseModel):
        name: str | None = None
        good: NonEmptyString | None = None

    assert blank_admitting_wire_string_fields(_Bad) == ["name"]


@pytest.mark.spec("CS-08-001")
@pytest.mark.spec("VM-07-005")
@pytest.mark.parametrize("blank", BLANKS)
@pytest.mark.parametrize(
    ("cls", "field"),
    _DECLARED_TEXT_FIELDS,
    ids=[f"{c.__name__}.{f}" for c, f in _DECLARED_TEXT_FIELDS],
)
def test_building_a_wire_object_with_a_blank_text_field_raises(
    cls: type[BaseModel], field: str, blank: str
) -> None:
    with pytest.raises(ValidationError):
        cls(**{field: blank})


@pytest.mark.spec("CS-08-001")
@pytest.mark.spec("VM-07-005")
@pytest.mark.parametrize("cls", [as_Note, CoreObject])
def test_an_object_built_without_content_carries_none(
    cls: type[BaseModel],
) -> None:
    """Absence is ``None``, never a blank default that would be emitted."""
    dumped = cls().model_dump(by_alias=True)
    assert dumped["content"] is None
    assert "content" not in cls().model_dump(by_alias=True, exclude_none=True)


def _inbound_create(**note_fields: str) -> dict[str, Any]:
    return {
        "type": "Create",
        "id": "https://example.org/activities/1",
        "actor": "https://example.org/actors/alice",
        "published": "2026-01-01T00:00:00+00:00",
        "object": {
            "type": "Note",
            "id": "https://example.org/notes/1",
            "content": "A note.",
            **note_fields,
        },
    }


@pytest.mark.spec("CS-08-001")
@pytest.mark.spec("VM-07-005")
@pytest.mark.parametrize("blank", BLANKS)
@pytest.mark.parametrize("key", ["name", "summary", "content", "mediaType"])
def test_an_inbound_activity_with_a_blank_text_field_is_refused(
    key: str, blank: str
) -> None:
    body = _inbound_create()
    body[key] = blank
    with pytest.raises(VultronParseError):
        parse_activity(body)


@pytest.mark.spec("CS-08-001")
@pytest.mark.spec("VM-07-005")
@pytest.mark.parametrize("blank", BLANKS)
@pytest.mark.parametrize("key", ["name", "summary", "content", "mediaType"])
def test_an_inbound_object_with_a_blank_text_field_is_refused(
    key: str, blank: str
) -> None:
    with pytest.raises(VultronParseError):
        parse_activity(_inbound_create(**{key: blank}))


def _empty_string_paths(value: Any, path: str = "$") -> list[str]:
    if isinstance(value, str):
        return [path] if not value.strip() else []
    if isinstance(value, dict):
        return [
            p
            for key, item in value.items()
            for p in _empty_string_paths(item, f"{path}.{key}")
        ]
    if isinstance(value, list):
        return [
            p
            for index, item in enumerate(value)
            for p in _empty_string_paths(item, f"{path}[{index}]")
        ]
    return []


_EXAMPLES = activity_examples()


@pytest.mark.spec("VM-07-005")
@pytest.mark.parametrize("name", sorted(_EXAMPLES))
def test_no_serialized_example_activity_holds_an_empty_string(
    name: str,
) -> None:
    emitted = json.loads(_EXAMPLES[name].to_json())
    assert _empty_string_paths(emitted) == []


@pytest.mark.spec("VM-07-005")
def test_a_built_activity_serializes_without_an_empty_string_field() -> None:
    activity = make(
        as_Create,
        actor="https://example.org/actors/alice",
        object_=make(as_Note, content="A note.", name="Title"),
    )
    assert _empty_string_paths(json.loads(activity.to_json())) == []
