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

"""The read-only view of a received activity is read-only all the way down."""

from types import MappingProxyType
from typing import Any, cast

import pytest
from pydantic import BaseModel, ValidationError

from vultron.core.models.activity import VultronActivity
from vultron.core.models.note import VultronNote
from vultron.core.models.received_activity_view import (
    ReceivedActivityView,
    read_only,
)
from vultron.errors import VultronReadOnlyViewError

_ACTOR = "https://example.org/actors/sender"


class _Holder(BaseModel):
    """A model with a field typed as the activity a view wraps."""

    activity: VultronActivity


def _view() -> ReceivedActivityView:
    return ReceivedActivityView(
        VultronActivity(
            id_="https://example.org/activities/a-1",
            type_="Create",
            actor=_ACTOR,
            to=["https://example.org/actors/receiver"],
            object_=VultronNote(
                id_="https://example.org/notes/n-1", content="as received"
            ),
            instrument={"keys": ["a", "b"], "flags": {"x"}},
        )
    )


@pytest.mark.spec("DL-06-001")
def test_the_view_reads_like_the_activity_it_wraps():
    view = _view()

    assert view.type_ == "Create"
    assert getattr(view.object_, "content", None) == "as received"
    assert isinstance(view.object_, ReceivedActivityView)


@pytest.mark.spec("DL-06-001")
@pytest.mark.spec("DL-06-004")
def test_the_view_hands_out_no_model_and_passes_for_none():
    """No attribute of the view reaches the wrapped model, and the view is
    no model a Pydantic field or a reply would take (ADR-0149)."""
    view = _view()

    for leak in ("_model", "_wrapped", "model_dump", "model_copy"):
        with pytest.raises(AttributeError):
            getattr(view, leak)
        with pytest.raises(AttributeError):
            getattr(view.object_, leak)
    assert not isinstance(view, BaseModel)
    with pytest.raises(ValidationError):
        _Holder(activity=cast(Any, view))


@pytest.mark.spec("DL-06-001")
def test_assigning_to_the_view_or_to_a_nested_object_raises():
    view = _view()

    with pytest.raises(VultronReadOnlyViewError):
        view.actor = "https://example.org/actors/someone-else"
    with pytest.raises(VultronReadOnlyViewError):
        view.object_.content = "changed"
    with pytest.raises(VultronReadOnlyViewError):
        del view.object_


@pytest.mark.spec("DL-06-001")
def test_collections_are_read_only_copies():
    view = _view()

    assert view.to == ("https://example.org/actors/receiver",)
    instrument = view.instrument
    assert isinstance(instrument, MappingProxyType)
    assert instrument["keys"] == ("a", "b")
    assert instrument["flags"] == frozenset({"x"})
    with pytest.raises(TypeError):
        instrument["keys"] = ()  # type: ignore[index]


def test_read_only_leaves_an_immutable_value_as_it_is():
    assert read_only("text") == "text"
    assert read_only(3) == 3
    assert read_only(None) is None


def test_views_compare_by_the_model_they_wrap():
    activity = VultronActivity(type_="Create", actor=_ACTOR)

    assert ReceivedActivityView(activity) == ReceivedActivityView(activity)
    assert ReceivedActivityView(activity) != "not a view"
    assert "ReceivedActivityView(" in repr(ReceivedActivityView(activity))
