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
"""An embargo goes on the wire as an ``EmbargoEvent``, a subtype of ``Event``.

ADR-0201: a sender writes ``"type": ["EmbargoEvent", "Event"]`` (VM-03-005);
a receiver reads that list, in either order, or ``"EmbargoEvent"`` alone, as
the embargo type (VM-03-006); and a plain ``Event`` matches no embargo
pattern, so it is never read as an embargo.
"""

import json
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError

import vultron.wire.as2.vocab.examples.embargo as examples
from test.support.objects import make
from vultron.core.models.case_preview import EmbargoEventPreview
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events import MessageSemantics
from vultron.core.models.registry import CORE_VOCABULARY
from vultron.metadata.wire_context.sync import vultron_subtype_statements
from vultron.semantic_registry import (
    SEMANTIC_REGISTRY,
    find_matching_semantics,
)
from vultron.wire.as2.extractor._pattern import ActivityPattern
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.typed_reference import is_of_kind
from vultron.wire.as2.vocab.base.enums import VocabNamespace
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.base.objects.object_types import (
    as_Document,
    as_Event,
    as_Page,
)
from vultron.wire.as2.vocab.base.registry import (
    WIRE_TYPE_MAP,
    core_supertype_term,
    is_as2_subtype,
    resolve_wire_type,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

TYPE_LIST = ["EmbargoEvent", "Event"]

#: Each embargo example and the semantics it is read as.  Together they
#: reach every pattern whose object is an embargo.
EMBARGO_EXAMPLES: dict[Callable[[], Any], MessageSemantics] = {
    examples.propose_embargo: MessageSemantics.INVITE_TO_EMBARGO_ON_CASE,
    examples.accept_embargo: MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE,
    examples.reject_embargo: MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE,
    examples.undo_embargo_invite: (
        MessageSemantics.UNDO_INVITE_TO_EMBARGO_ON_CASE
    ),
    examples.create_embargo_event: MessageSemantics.CREATE_EMBARGO_EVENT,
    examples.activate_embargo: MessageSemantics.ACTIVATE_EMBARGO_ON_CASE,
    examples.reject_embargo_proposal: (
        MessageSemantics.REJECT_EMBARGO_PROPOSAL_ON_CASE
    ),
    examples.withdraw_from_embargo: (
        MessageSemantics.WITHDRAW_FROM_EMBARGO_ON_CASE
    ),
    examples.announce_embargo: MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE,
    examples.remove_embargo: MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE,
}


def _wire(obj: Any) -> dict[str, Any]:
    """The JSON a sender writes for *obj*."""
    wire: dict[str, Any] = json.loads(
        obj.model_dump_json(by_alias=True, exclude_none=True)
    )
    return wire


def _retyped(value: Any, type_value: object) -> tuple[Any, int]:
    """*value* with each embargo's ``type`` replaced by *type_value*.

    An embargo is a dict whose ``type`` is the list a sender writes for one.
    Returns the copy and how many embargoes it replaced.
    """
    if isinstance(value, list):
        items = [_retyped(item, type_value) for item in value]
        return [item for item, _ in items], sum(n for _, n in items)
    if not isinstance(value, dict):
        return value, 0
    count = 0
    out: dict[str, Any] = {}
    for key, item in value.items():
        out[key], found = _retyped(item, type_value)
        count += found
    if value.get("type") == TYPE_LIST:
        out["type"] = type_value
        count += 1
    return out, count


def _embargo_patterns() -> list[ActivityPattern]:
    """Every registered pattern whose ``object`` chain ends in an embargo."""
    patterns = []
    for entry in SEMANTIC_REGISTRY:
        pattern = entry.pattern
        obj: object = pattern.object_ if pattern is not None else None
        while isinstance(obj, ActivityPattern):
            obj = obj.object_
        if pattern is not None and obj == "EmbargoEvent":
            patterns.append(pattern)
    return patterns


@pytest.mark.spec("VM-03-005")
def test_an_embargo_is_written_with_the_event_type_list() -> None:
    """The AS2 dump writes the list; the object keeps its one type."""
    embargo = examples.embargo_event()

    assert _wire(embargo)["type"] == TYPE_LIST
    assert embargo.type_ == "EmbargoEvent"


@pytest.mark.spec("VM-03-005")
def test_an_embargo_nested_in_an_activity_is_written_with_the_list() -> None:
    assert _wire(examples.propose_embargo())["object"]["type"] == TYPE_LIST


@pytest.mark.spec("VM-03-005")
def test_the_persistence_dump_keeps_one_type_string() -> None:
    """A stored row reads back as it was written: one string, no list."""
    embargo = examples.embargo_event()

    stored = embargo.model_dump(mode="json")

    assert stored["type_"] == "EmbargoEvent"
    assert EmbargoEvent.model_validate(stored) == embargo


@pytest.mark.spec("VM-03-005")
def test_an_embargo_preview_is_written_with_the_list() -> None:
    """A preview writes its full class's ``type``, so it writes the list."""
    preview = EmbargoEventPreview.model_validate(
        {"type": "EmbargoEvent", "id": "urn:uuid:embargo-1"}
    )

    dumped = preview.model_dump(by_alias=True, exclude_none=True)

    assert dumped["type"] == TYPE_LIST


@pytest.mark.spec("VM-03-006")
@pytest.mark.parametrize(
    "type_value",
    [TYPE_LIST, list(reversed(TYPE_LIST)), "EmbargoEvent"],
    ids=["embargo-first", "event-first", "embargo-alone"],
)
def test_the_resolver_reads_each_spelling_as_the_embargo(
    type_value: object,
) -> None:
    assert resolve_wire_type(type_value) is EmbargoEvent


@pytest.mark.spec("VM-03-006")
def test_the_embargo_reads_its_own_dump_back() -> None:
    embargo = make(
        as_EmbargoEvent,
        context="urn:uuid:case-1",
        end_time="2027-01-01T00:00:00Z",
    )

    assert EmbargoEvent.model_validate(_wire(embargo)) == embargo


def test_the_embargo_is_an_as2_subtype_of_event() -> None:
    """Declared, not inherited: core never extends a wire class."""
    assert not issubclass(EmbargoEvent, as_Event)
    assert is_as2_subtype(EmbargoEvent, as_Event)
    assert not is_as2_subtype(as_Event, EmbargoEvent)


@pytest.mark.spec("VM-10-007")
def test_the_context_declares_the_embargo_a_subclass_of_event() -> None:
    assert vultron_subtype_statements()["EmbargoEvent"] == "Event"


@pytest.mark.parametrize(
    "cls",
    [cls for cls in CORE_VOCABULARY.values() if core_supertype_term(cls)],
    ids=lambda cls: cls.__name__,
)
def test_each_core_supertype_term_names_an_as2_type(cls: type) -> None:
    """A core class may declare only an AS2 core type it refines (ADR-0201).

    The term must name an ActivityStreams class the wire registry holds, and
    that class must not be the declaring class's own type.
    """
    term = core_supertype_term(cls)
    assert term is not None
    supertype = WIRE_TYPE_MAP[term]
    assert getattr(supertype, "_vocab_ns", None) is VocabNamespace.AS
    assert supertype is not cls


def test_the_examples_reach_every_embargo_pattern() -> None:
    """The examples below cover every pattern whose object is an embargo."""
    covered = set(EMBARGO_EXAMPLES.values())
    patterns = _embargo_patterns()
    assert patterns, "no pattern names an embargo object"
    for pattern in patterns:
        assert any(
            pattern.match(parse_activity(_wire(build())))
            for build in EMBARGO_EXAMPLES
        ), pattern
    assert len(covered) == len(EMBARGO_EXAMPLES)


@pytest.mark.spec("VM-03-006")
@pytest.mark.parametrize(
    "type_value",
    [TYPE_LIST, list(reversed(TYPE_LIST)), "EmbargoEvent"],
    ids=["embargo-first", "event-first", "embargo-alone"],
)
@pytest.mark.parametrize(
    "build", list(EMBARGO_EXAMPLES), ids=lambda build: build.__name__
)
def test_every_embargo_pattern_matches_each_spelling(
    build: Callable[[], Any], type_value: object
) -> None:
    body, replaced = _retyped(_wire(build()), type_value)
    assert replaced, "the example carries no embargo"

    assert (
        find_matching_semantics(parse_activity(body))
        == EMBARGO_EXAMPLES[build]
    )


@pytest.mark.parametrize(
    "build", list(EMBARGO_EXAMPLES), ids=lambda build: build.__name__
)
def test_a_plain_event_is_not_read_as_an_embargo(
    build: Callable[[], Any],
) -> None:
    """A receiver refuses a plain ``Event`` where an embargo is expected.

    Only an ``EmbargoEvent`` matches the embargo patterns (ADR-0201), so the
    activity is not read as the embargo message it would otherwise be.
    """
    body, replaced = _retyped(_wire(build()), "Event")
    assert replaced, "the example carries no embargo"

    assert (
        find_matching_semantics(parse_activity(body))
        == MessageSemantics.UNKNOWN
    )


def test_an_invite_of_a_plain_event_is_no_embargo_proposal() -> None:
    """``Invite(Event)`` with a plain ``Event`` is not an embargo proposal."""
    body, _ = _retyped(_wire(examples.propose_embargo()), "Event")
    activity = parse_activity(body)

    assert type(getattr(activity, "object_", None)) is as_Event
    assert find_matching_semantics(activity) not in {
        MessageSemantics.INVITE_TO_EMBARGO_ON_CASE,
        MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT,
    }


@pytest.mark.spec("VM-03-006")
@pytest.mark.spec("MV-10-011")
@pytest.mark.parametrize(
    ("type_value", "expected"),
    [
        (TYPE_LIST, MessageSemantics.ACTIVATE_EMBARGO_ON_CASE),
        (list(reversed(TYPE_LIST)), MessageSemantics.ACTIVATE_EMBARGO_ON_CASE),
        ("EmbargoEvent", MessageSemantics.ACTIVATE_EMBARGO_ON_CASE),
        ("Event", MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT),
    ],
    ids=["embargo-first", "event-first", "embargo-alone", "plain-event"],
)
def test_a_typed_reference_routes_by_the_embargo_type(
    type_value: object, expected: MessageSemantics
) -> None:
    """A reference typed as an embargo routes as one; one typed only as a
    plain ``Event`` names an object the receiver must read first."""
    body = _wire(examples.activate_embargo())
    body["object"] = {"id": body["object"]["id"], "type": type_value}

    assert find_matching_semantics(parse_activity(body)) == expected


@pytest.mark.spec("VM-03-006")
@pytest.mark.parametrize(
    "type_value",
    [["EmbargoEvent", "Note"], ["EmbargoEvent", "Foo"]],
    ids=["another-known-type", "an-unknown-term"],
)
def test_the_embargo_refuses_a_list_it_does_not_write(
    type_value: list[str],
) -> None:
    """Core reads back only the list it writes: it cannot ask the wire
    vocabulary whether another term is unrelated (VM-03-007), so the parse
    edge, not the class, decides such a list."""
    data = _wire(examples.embargo_event())
    data["type"] = type_value

    with pytest.raises(ValidationError):
        EmbargoEvent.model_validate(data)


@pytest.mark.parametrize(
    ("cls", "kind"),
    [
        (EmbargoEvent, as_Event),
        (EmbargoEvent, as_Object),
        (as_Page, as_Document),
    ],
    ids=["embargo-is-an-event", "embargo-is-an-object", "page-is-a-document"],
)
def test_is_of_kind_follows_the_as2_subtype_relation(
    cls: type, kind: type
) -> None:
    """A pattern and rehydration ask one rule: an AS2 subtype is a kind of
    its supertype even without subclassing its class (MV-10-011)."""
    assert is_of_kind(cls, kind)
    assert not is_of_kind(kind, cls)
