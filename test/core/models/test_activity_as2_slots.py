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
"""The AS2 slots of the core activity take AS2 shapes and refuse blanks (#6305).

Spec: CS-08-001, ARCH-10-001, ARCH-12-004, ARCH-21-002

``VultronActivity`` declared ``object``, ``target``, ``instrument``,
``result``, ``proposedEmbargo``, ``anyOf``, ``oneOf`` and ``closed`` as
``Any``, so a blank IRI reached core in any of them.  Each now takes the
shape its wire declaration does, and the activity reads its own dump back
with every embedded object as the class that wrote it.
"""

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from test.support.objects import make
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models._helpers import format_timestamp
from vultron.core.models.activity import VultronActivity
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.note import VultronNote
from vultron.core.models.type_lookup import core_class_for_type
from vultron.wire.as2.vocab.base.links import as_Link
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_TransitiveActivity,
)

_ACTOR = "https://example.org/actors/sender"
_IRI = "https://example.org/objects/o-1"
_BLANKS = ["", "   "]

#: The slots that hold one object or one IRI.
_SINGLE_SLOTS = ["object_", "target", "instrument", "result"]
#: The ``Question`` option slots, which hold one or many.
_OPTION_SLOTS = ["any_of", "one_of"]


def _note(n: int = 1) -> VultronNote:
    return make(
        VultronNote, id_=f"https://example.org/notes/n-{n}", content="text"
    )


def _activity(**fields: Any) -> VultronActivity:
    return make(VultronActivity, type_="Create", actor=_ACTOR, **fields)


@pytest.mark.spec("CS-08-001")
@pytest.mark.spec("ARCH-10-001")
@pytest.mark.parametrize("blank", _BLANKS, ids=repr)
@pytest.mark.parametrize("slot", [*_SINGLE_SLOTS, *_OPTION_SLOTS, "closed"])
def test_a_blank_iri_is_refused_in_every_slot(slot: str, blank: str) -> None:
    with pytest.raises(ValidationError):
        _activity(**{slot: blank})


@pytest.mark.spec("CS-08-001")
@pytest.mark.parametrize("blank", _BLANKS, ids=repr)
@pytest.mark.parametrize("slot", _OPTION_SLOTS)
def test_a_blank_option_in_a_list_is_refused(slot: str, blank: str) -> None:
    with pytest.raises(ValidationError):
        _activity(**{slot: [_IRI, blank]})


@pytest.mark.spec("ARCH-10-001")
@pytest.mark.parametrize("slot", [*_SINGLE_SLOTS, *_OPTION_SLOTS, "closed"])
def test_a_slot_refuses_a_value_no_as2_shape_admits(slot: str) -> None:
    """A bare mapping core models no class for, or a number, is refused."""
    with pytest.raises(ValidationError):
        _activity(**{slot: {"keys": ["a"]}})


@pytest.mark.parametrize("slot", [*_SINGLE_SLOTS, *_OPTION_SLOTS])
def test_a_slot_takes_a_core_object_a_built_wire_object_or_an_iri(
    slot: str,
) -> None:
    """The three AS2 shapes the wire declaration admits are kept as given."""
    link = as_Link(href="https://example.org/links/l-1")
    for value in (_note(), link, _IRI):
        assert getattr(_activity(**{slot: value}), slot) == value


@pytest.mark.spec("ARCH-10-001")
def test_a_dump_of_an_object_core_does_not_model_is_refused() -> None:
    """A Link's mapping names no core class, so core cannot build it.

    Such an object reaches core already built by the wire layer (ADR-0032),
    and a stored row builds it in the adapter before core reads the row.
    """
    link_dump = as_Link(href="https://example.org/links/l-1").model_dump(
        mode="json", by_alias=True
    )

    with pytest.raises(ValidationError):
        _activity(instrument=link_dump)


def test_the_options_take_a_list_of_objects_and_iris() -> None:
    options = [_note(1), _IRI, _note(2)]

    assert _activity(any_of=options).any_of == options
    assert _activity(one_of=options).one_of == options


@pytest.mark.spec("ARCH-10-001")
def test_a_proposed_embargo_is_an_embargo_event_only() -> None:
    """The proposal states terms, so an IRI or another object is refused."""
    event = make(
        EmbargoEvent,
        end_time=datetime(2027, 1, 1, tzinfo=UTC),
        start_time=None,
        context="https://example.org/reports/r-1",
    )

    assert _activity(proposed_embargo=event).proposed_embargo == event
    for value in (_IRI, _note(), "", "   "):
        with pytest.raises(ValidationError):
            _activity(proposed_embargo=value)


@pytest.mark.parametrize(
    "value",
    [True, False, _IRI],
    ids=["true", "false", "iri"],
)
def test_closed_reads_back_its_flag_or_iri(value: object) -> None:
    dumped = _activity(closed=value).model_dump(mode="json", by_alias=True)

    assert VultronActivity.model_validate(dumped).closed == value


def test_closed_reads_back_a_time_as_a_time_in_the_fixed_form() -> None:
    """A stored time is a string, which must not read back as an IRI."""
    closed = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    dumped = _activity(closed=closed).model_dump(mode="json", by_alias=True)

    assert dumped["closed"] == format_timestamp(closed)
    assert VultronActivity.model_validate(dumped).closed == closed


def test_a_naive_closed_time_is_read_as_utc() -> None:
    closed = _activity(
        closed=datetime.fromisoformat("2026-01-02T03:04:05")
    ).closed

    assert closed == datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


@pytest.mark.spec("ARCH-10-001")
@pytest.mark.parametrize("mode", ["json", "python"])
@pytest.mark.parametrize("by_alias", [True, False], ids=["alias", "name"])
def test_an_activity_reads_its_own_dump_back(
    mode: str, by_alias: bool
) -> None:
    """Every embedded object reads back as the class that wrote it.

    The slot's ``CoreObject`` branch forbids a subclass's fields, so before
    the embedded mappings were typed the activity refused its own dump.  A
    nested activity reads back as a ``VultronActivity`` and its own embedded
    note as a ``VultronNote``.
    """
    inner = make(
        VultronActivity,
        id_="https://example.org/activities/offer-1",
        type_="Offer",
        actor="https://example.org/actors/other",
        object_=_note(1),
    )
    activity = _activity(
        id_="https://example.org/activities/accept-1",
        object_=inner,
        target=_note(2),
        result=_IRI,
        any_of=[_note(3), _IRI],
        one_of=_note(4),
        closed=datetime(2026, 1, 2, tzinfo=UTC),
    )

    restored = VultronActivity.model_validate(
        activity.model_dump(mode=mode, by_alias=by_alias)
    )

    assert restored == activity
    assert isinstance(restored.object_, VultronActivity)
    assert isinstance(restored.object_.object_, VultronNote)
    assert isinstance(restored.target, VultronNote)
    assert isinstance(restored.one_of, VultronNote)


@pytest.mark.spec("ARCH-10-001")
def test_a_stored_activity_reads_back_with_its_slots() -> None:
    """A stored activity's object, target and result survive the DataLayer.

    A stored activity row reads back through the wire activity class
    (#1506), with its embedded object collapsed to the id of the object's
    own row, which reads back as the core class.
    """
    dl = SqliteDataLayer(
        "sqlite:///:memory:", actor_id="https://example.org/actors/store"
    )
    try:
        note = _note()
        dl.save(note)
        activity = _activity(
            id_="https://example.org/activities/create-1",
            object_=note,
            target="https://example.org/cases/c-1",
            result=_IRI,
        )
        dl.save(activity)

        restored = dl.read(activity.id_)

        assert isinstance(restored, as_TransitiveActivity)
        assert restored.object_ == note
        assert restored.target == activity.target
        assert restored.result == activity.result
    finally:
        dl.clear_all()
        dl.close()


def test_the_type_lookup_leaves_core_activities_out() -> None:
    """Core activity classes share ``type`` values, so none is named by one."""
    assert core_class_for_type("Note") is VultronNote
    with pytest.raises(KeyError):
        core_class_for_type("Create")
