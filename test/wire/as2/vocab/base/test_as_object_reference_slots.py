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
"""The AS2 reference properties on the two object roots refuse a blank IRI.

Spec: CS-08-001, CS-08-002

``as_Object`` and ``CoreObject`` declared sixteen AS2 properties (``to``,
``cc``, ``context``, ``inReplyTo``, ``attributedTo``, ``url``, ...) as
``Any | None``, so a blank reference validated inbound and reached the core
(#3894).  Each now takes its AS2 range: an embedded object, a Link (wire only)
or a ``NonEmptyString`` IRI, one or many.  These tests pin the probes the issue
named, the shapes AS2 allows, and the core mirror's handling of a wire object it
cannot name.
"""

from typing import Any

import pytest
from pydantic import BaseModel, ValidationError
from pydantic.alias_generators import to_camel

import vultron.wire.as2.vocab.activities  # trigger dynamic discovery
import vultron.wire.as2.vocab.objects  # noqa: F401
from test.support.blank_strings import BLANKS
from test.support.objects import make
from vultron.core.models.actor import CoreActor
from vultron.core.models.base import CoreObject
from vultron.core.models.case import VulnerabilityCase
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.links import as_Link
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

#: The slots #3894 listed as ``Any | None`` on the wire base.
WIRE_SLOTS: tuple[str, ...] = (
    "replies",
    "url",
    "generator",
    "context",
    "tag",
    "in_reply_to",
    "icon",
    "image",
    "attachment",
    "location",
    "to",
    "cc",
    "bto",
    "bcc",
    "audience",
    "attributed_to",
)

#: ``replies`` is functional (AS2 4): one collection, never a list.
SINGLE_VALUED = frozenset({"replies"})

#: The core mirror declares the same slots; ``url`` and ``attributed_to`` were
#: already ``NonEmptyString`` there, and are probed with the rest.
CORE_SLOTS = WIRE_SLOTS


def _blank_probes(slots: tuple[str, ...]) -> list[tuple[str, Any]]:
    """``(wire key, value)`` for a bare blank and, where allowed, ``[blank]``."""
    probes: list[tuple[str, Any]] = []
    for slot in slots:
        for blank in BLANKS:
            probes.append((to_camel(slot), blank))
            if slot not in SINGLE_VALUED:
                probes.append((to_camel(slot), [blank]))
    return probes


@pytest.mark.spec("CS-08-001")
@pytest.mark.parametrize("key,value", _blank_probes(WIRE_SLOTS))
def test_wire_object_refuses_a_blank_reference(key: str, value: Any) -> None:
    """A blank IRI is refused in every AS2 reference slot, bare or listed."""
    with pytest.raises(ValidationError):
        as_Object.model_validate({key: value})


@pytest.mark.spec("CS-08-001")
@pytest.mark.parametrize("key,value", _blank_probes(CORE_SLOTS))
def test_core_object_refuses_a_blank_reference(key: str, value: Any) -> None:
    """The core mirror refuses the same blanks when the object is built."""
    with pytest.raises(ValidationError):
        CoreObject.model_validate({key: value})


@pytest.mark.spec("CS-08-001")
@pytest.mark.parametrize(
    "key,value",
    [
        ("to", [""]),
        ("cc", " "),
        ("attributedTo", ""),
        ("inReplyTo", ""),
        ("context", "   "),
    ],
)
def test_parse_edge_refuses_a_blank_addressing_reference(
    key: str, value: Any
) -> None:
    """The fields the inbox reads refuse a blank at the parse edge (#3855)."""
    body = {
        "type": "Offer",
        "id": "https://example.org/activities/1",
        "actor": "https://example.org/actors/alice",
        "published": "2026-03-04T05:06:07+00:00",
        "object": "https://example.org/objects/1",
        key: value,
    }
    with pytest.raises(VultronParseValidationError):
        parse_activity(body)


def test_wire_object_keeps_every_shape_as2_allows() -> None:
    """An IRI, a list of IRIs, an object, a Link and a core object all validate."""
    note = make(as_Note, id_="https://example.org/notes/1", content="hi")
    link = as_Link(href="https://example.org/x")
    case = make(
        VulnerabilityCase,
        id_="https://example.org/cases/1",
        name="a case",
        attributed_to="https://example.org/actors/alice",
    )
    obj = make(
        as_Object,
        to="https://example.org/actors/bob",
        cc=["https://example.org/actors/a", "https://example.org/actors/b"],
        in_reply_to=note,
        tag=[link],
        context=case,
        url=[link, "https://example.org/page"],
        replies="https://example.org/replies",
    )
    assert obj.to == "https://example.org/actors/bob"
    assert obj.cc == [
        "https://example.org/actors/a",
        "https://example.org/actors/b",
    ]
    assert obj.in_reply_to is note
    assert obj.tag == [link]
    assert obj.context is case
    assert obj.url == [link, "https://example.org/page"]


@pytest.mark.parametrize("value", [42, True, 1.5])
def test_wire_object_refuses_a_value_as2_does_not_allow(value: object) -> None:
    """A number or boolean is neither an object, a Link nor an IRI."""
    with pytest.raises(ValidationError):
        as_Object.model_validate({"to": value})


def test_url_refuses_an_embedded_object() -> None:
    """``url``'s range is an IRI or a Link (AS2 4), never an object."""
    with pytest.raises(ValidationError):
        as_Object.model_validate({"url": make(as_Note, content="hi")})


@pytest.mark.spec("VM-10-005")
def test_core_object_holds_a_wire_object_it_cannot_name() -> None:
    """A wire Link in a core slot is kept as built and dumped by its own class.

    Core cannot import the wire ``Link`` (ARCH-01-001), but the parse edge puts
    wire objects in core objects' slots, so the core union admits an object
    another layer built and serializes it as that object.
    """
    link = as_Link(href="https://example.org/x")
    obj = make(CoreObject, tag=[link])

    assert obj.tag == [link]
    dumped = obj.model_dump(by_alias=True, exclude_none=True)
    assert dumped["tag"][0]["href"] == "https://example.org/x"
    assert dumped["tag"][0]["type"] == "Link"
    # Nested, so it carries no ``@context`` of its own (VM-10-005).
    assert "@context" not in dumped["tag"][0]


def test_core_object_reads_a_raw_mapping_as_a_core_object() -> None:
    """A raw mapping in a core slot validates as a ``CoreObject``, or not at all.

    Only an already-built model takes the open branch; a mapping that is not a
    ``CoreObject`` is refused by its ``extra="forbid"`` (ARCH-12-003) rather
    than carried unexamined.
    """
    obj = CoreObject.model_validate(
        {"context": {"id": "https://example.org/cases/1", "type": "Note"}}
    )
    assert isinstance(obj.context, CoreObject)
    assert obj.context.id_ == "https://example.org/cases/1"

    with pytest.raises(ValidationError):
        CoreObject.model_validate({"context": {"href": "https://example.org"}})


@pytest.mark.spec("CS-08-001")
@pytest.mark.parametrize(
    "root", [as_Actor, CoreActor], ids=lambda c: c.__name__
)
@pytest.mark.parametrize(
    "endpoints",
    ["", "   ", {"sharedInbox": ""}, {"": "https://example.org/i"}],
)
def test_actor_endpoints_refuse_a_blank(
    root: type[BaseModel], endpoints: object
) -> None:
    """``endpoints`` is an IRI or an object of IRIs; a blank names nothing."""
    with pytest.raises(ValidationError):
        root.model_validate(
            {"id": "https://example.org/actors/a", "endpoints": endpoints}
        )


def _offer(**extra: Any) -> dict[str, Any]:
    """A received Offer body, with *extra* keys set on it."""
    return {
        "type": "Offer",
        "id": "https://example.org/activities/1",
        "actor": "https://example.org/actors/alice",
        "published": "2026-03-04T05:06:07+00:00",
        "object": "https://example.org/objects/1",
        **extra,
    }


def _id_less_probes() -> list[tuple[str, Any]]:
    """``(wire key, value)``: an id-less Object, bare and listed, in each slot.

    ``url`` admits no Object (AS2 4), so it has no such probe.
    """
    probes: list[tuple[str, Any]] = []
    for slot in WIRE_SLOTS:
        if slot == "url":
            continue
        key = to_camel(slot)
        probes.append((key, {"type": "Note", "content": "no id"}))
        if slot not in SINGLE_VALUED:
            probes.append((key, [{"type": "Person"}]))
            probes.append((key, [{}]))
    return probes


@pytest.mark.spec("OID-01-013")
@pytest.mark.parametrize("key,value", _id_less_probes())
def test_parse_edge_refuses_an_id_less_object_in_a_reference_slot(
    key: str, value: Any
) -> None:
    """An embedded Object with no id is refused, never given a minted one."""
    with pytest.raises(VultronParseValidationError):
        parse_activity(_offer(**{key: value}))


@pytest.mark.spec("OID-01-013")
def test_parse_edge_refuses_an_id_less_object_as_the_activity_object() -> None:
    """The rule holds outside the reference slots, at any depth."""
    with pytest.raises(VultronParseValidationError):
        parse_activity(_offer(object={"type": "Note", "content": "no id"}))


@pytest.mark.spec("OID-01-013")
def test_parse_edge_refuses_an_id_less_object_in_a_core_slot() -> None:
    """A core class's slot refuses the id-less Object the wire slot refuses."""
    report = {
        "type": "VulnerabilityReport",
        "id": "https://example.org/reports/1",
        "name": "r",
        "content": "c",
        "attributedTo": "https://example.org/actors/alice",
        "published": "2026-03-04T05:06:07+00:00",
        "context": {"type": "Note", "content": "no id"},
    }
    body = _offer(type="Create", object=report)
    with pytest.raises(VultronParseValidationError):
        parse_activity(body)


@pytest.mark.spec("OID-01-014")
def test_parse_edge_keeps_a_received_object_id() -> None:
    """An embedded Object that carries its id keeps exactly that id."""
    note_id = "https://example.org/notes/1"
    activity = parse_activity(
        _offer(tag=[{"type": "Note", "id": note_id, "content": "x"}])
    )
    assert isinstance(activity.tag, list)
    assert getattr(activity.tag[0], "id_", None) == note_id


@pytest.mark.spec("OID-01-013")
@pytest.mark.spec("OID-01-014")
@pytest.mark.parametrize("link_type", ["Link", "Mention"])
def test_parse_edge_keeps_an_id_less_link_with_its_href(
    link_type: str,
) -> None:
    """A Link is not an Object: it needs no id, keeps its href, gets no id."""
    href = "https://example.org/actors/bob"
    activity = parse_activity(_offer(tag=[{"type": link_type, "href": href}]))
    assert isinstance(activity.tag, list)
    (link,) = activity.tag
    assert isinstance(link, as_Link)
    assert link.type_ == link_type
    assert link.href == href
    assert link.id_ is None


@pytest.mark.spec("OID-01-013")
def test_parse_edge_keeps_a_mention_in_a_core_slot() -> None:
    """A core class's ``tag`` holds a received Mention as the Link it is."""
    href = "https://example.org/actors/bob"
    report = {
        "type": "VulnerabilityReport",
        "id": "https://example.org/reports/1",
        "name": "r",
        "content": "c",
        "attributedTo": "https://example.org/actors/alice",
        "published": "2026-03-04T05:06:07+00:00",
        "tag": [{"type": "Mention", "href": href}],
    }
    activity = parse_activity(_offer(type="Create", object=report))
    tag = getattr(getattr(activity, "object_", None), "tag", None)
    assert isinstance(tag, list)
    assert isinstance(tag[0], as_Link)
    assert tag[0].href == href


def test_parse_edge_refuses_a_link_that_names_no_href() -> None:
    """A Link without an ``href`` names no resource (CS-08-001)."""
    with pytest.raises(VultronParseValidationError):
        parse_activity(_offer(tag=[{"type": "Link"}]))


def test_an_unmodelled_link_extension_type_is_refused() -> None:
    """``Hashtag`` is no AS2 type: its parent slot decides, and none admits it.

    MV-04-004 leaves an inline object whose ``type`` the vocabulary lacks for its
    field to validate.  No branch of a reference slot admits a ``Hashtag``: it is
    no ``Link`` by ``type``, and as an Object it carries no id (OID-01-013).
    """
    with pytest.raises(VultronParseValidationError):
        parse_activity(
            _offer(tag=[{"type": "Hashtag", "href": "https://ex.org/t/x"}])
        )


def test_an_object_this_process_builds_still_takes_a_minted_id() -> None:
    """Minting stays the default for an object built here, Link included."""
    assert make(as_Note, content="x").id_
    assert as_Link(href="https://example.org/x").id_


def _recipient_readers() -> list[Any]:
    from vultron.adapters.driven.sender_sequence_stamp import (
        _recipient_ids as stamp_recipient_ids,
    )
    from vultron.core.behaviors.sync.nodes.sender_sequence import (
        _recipient_ids as node_recipient_ids,
    )
    from vultron.demo.helpers.verification.records import recipient_ids
    from vultron.wire.as2.extractor._builders.fields import _get_id_list

    return [
        _get_id_list,
        stamp_recipient_ids,
        node_recipient_ids,
        recipient_ids,
    ]


@pytest.mark.parametrize("reader", _recipient_readers())
def test_recipient_readers_read_every_recipient_of_a_tuple(
    reader: Any,
) -> None:
    """A ``Sequence`` slot keeps a tuple as given; every recipient is read."""
    recipients = ("https://example.org/a", "https://example.org/b")
    obj = make(as_Object, to=recipients)
    assert isinstance(obj.to, tuple)
    assert reader(obj.to) == list(recipients)
