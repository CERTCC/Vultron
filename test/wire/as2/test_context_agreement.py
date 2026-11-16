#!/usr/bin/env python

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

"""An activity whose parts name different cases is refused at parse (HP-08-015).

The parts are the activity and each object down its ``object`` chain.  Two
``context`` values naming different cases are refused, whatever the activity
type, with every ``context`` and its case in the reason.  One ``context``,
matching ones, and an object named by reference keep their verdict.
"""

from typing import Any

import pytest

from vultron.wire.as2.context_agreement import object_chain
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.parser import parse_activity

_CASE_A = "https://example.org/cases/a"
_CASE_B = "https://example.org/cases/b"
_PUBLISHED = "2026-01-01T00:00:00+00:00"
_ACTIVITY_ID = "https://example.org/activities/outer"


def _note(context: object = None, n: int = 1) -> dict[str, Any]:
    note: dict[str, Any] = {
        "type": "Note",
        "id": f"https://example.org/notes/{n}",
        "content": "A note about the vul.",
        "published": _PUBLISHED,
    }
    if context is not None:
        note["context"] = context
    return note


def _activity(
    type_: str,
    object_: object,
    context: object = None,
    id_: str = _ACTIVITY_ID,
    **slots: Any,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": type_,
        "id": id_,
        "actor": "https://example.org/actors/vendor",
        "object": object_,
        "published": _PUBLISHED,
        **slots,
    }
    if context is not None:
        body["context"] = context
    return body


def _inner(object_: object, context: object = None) -> dict[str, Any]:
    return _activity(
        "Offer",
        object_,
        context,
        id_="https://example.org/activities/inner",
        to=["https://example.org/actors/case-manager"],
    )


def _link(href: str) -> dict[str, Any]:
    return {"type": "Link", "href": href}


_REFUSED = {
    # The issue's two nesting shapes: a plain object, and a nested activity.
    "plain-object": (
        _activity("Add", _note(_CASE_B), _CASE_A, target=_CASE_A),
        [("context", _CASE_A), ("object.context", _CASE_B)],
    ),
    "nested-activity": (
        _activity("Accept", _inner(_note(), _CASE_B), _CASE_A),
        [("context", _CASE_A), ("object.context", _CASE_B)],
    ),
    # The inner activity names no case, so its object is compared with the
    # outer activity's.
    "two-levels-down": (
        _activity("Accept", _inner(_note(_CASE_B)), _CASE_A),
        [("context", _CASE_A), ("object.object.context", _CASE_B)],
    ),
    # Two parts below an activity that names no case still disagree.
    "inner-activity-and-its-object": (
        _activity("Accept", _inner(_note(_CASE_B), _CASE_A)),
        [("object.context", _CASE_A), ("object.object.context", _CASE_B)],
    ),
    "link-context": (
        _activity("Add", _note(_CASE_B), _link(_CASE_A), target=_CASE_A),
        [("context", _CASE_A), ("object.context", _CASE_B)],
    ),
    # AS2 lets a context hold several values; the parts compare as sets.
    "list-context-differs": (
        _activity("Add", _note(_CASE_A), [_CASE_A, _CASE_B]),
        [("context", (_CASE_A, _CASE_B)), ("object.context", _CASE_A)],
    ),
}


@pytest.mark.spec("HP-08-015")
@pytest.mark.parametrize(
    "body, named", list(_REFUSED.values()), ids=list(_REFUSED)
)
def test_parts_naming_different_cases_are_refused_naming_each(
    body: dict[str, Any], named: list[tuple[str, str | tuple[str, ...]]]
) -> None:
    with pytest.raises(VultronParseValidationError) as exc:
        parse_activity(body)

    reason = str(exc.value)
    assert reason.startswith(f"activity {_ACTIVITY_ID!r}: ")
    for position, cases in named:
        listed = ", ".join(
            f"case {case!r}"
            for case in ((cases,) if isinstance(cases, str) else cases)
        )
        assert f"{position} names {listed}" in reason
    assert reason.endswith("(HP-08-015)")


_KEPT = {
    "activity-context-only": _activity("Add", _note(), _CASE_A),
    "object-context-only": _activity("Add", _note(_CASE_A)),
    "matching": _activity("Add", _note(_CASE_A), _CASE_A, target=_CASE_A),
    "matching-through-a-link": _activity(
        "Add", _note(_CASE_A), _link(_CASE_A)
    ),
    "matching-nested": _activity(
        "Accept", _inner(_note(_CASE_A), _CASE_A), _CASE_A
    ),
    "no-context": _activity("Add", _note()),
    "matching-list-context": _activity("Add", _note(_CASE_A), [_CASE_A]),
    # One context naming two cases has no other part to disagree with.
    "one-list-context": _activity("Add", _note(), [_CASE_A, _CASE_B]),
    # A reference carries no context, so it names no case to compare.
    "object-by-uri": _activity("Add", "https://example.org/notes/1", _CASE_B),
    "object-by-link": _activity(
        "Add", _link("https://example.org/notes/1"), _CASE_B
    ),
    "object-by-typed-reference": _activity(
        "Add", {"type": "Note", "id": "https://example.org/notes/1"}, _CASE_B
    ),
    "inner-activity-by-typed-reference": _activity(
        "Accept", {"type": "Offer", "id": "https://example.org/a/1"}, _CASE_B
    ),
}


@pytest.mark.spec("HP-08-015")
@pytest.mark.parametrize("body", list(_KEPT.values()), ids=list(_KEPT))
def test_parts_that_do_not_disagree_parse(body: dict[str, Any]) -> None:
    assert parse_activity(body).id_ == _ACTIVITY_ID


def test_object_chain_follows_nested_activities_and_stops_at_objects() -> None:
    activity = parse_activity(
        _activity("Accept", _inner(_note(_CASE_A), _CASE_A), _CASE_A)
    )

    assert [path for path, _ in object_chain(activity)] == [
        "",
        "object",
        "object.object",
    ]
