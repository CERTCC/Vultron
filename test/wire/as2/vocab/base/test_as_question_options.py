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

"""``as_Question`` carries collections of options (AS2 §4.1, ADR-0100, #3469).

AS2 defines ``anyOf`` and ``oneOf`` as non-functional properties: a Question
offers a *set* of options.  The class declared them as a single value, which
serialised a list last-writer-wins and refused it on re-validation — the
defect that made the retired ``ChoosePreferredEmbargo`` poll unparseable.
``as_Question`` itself stays for the CBT-03-004 bootstrap-replay Question,
so its option fields are corrected rather than removed.
"""

import json

import pytest
from pydantic import ValidationError

from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.links import as_Link
from vultron.wire.as2.vocab.base.objects.activities.intransitive import (
    as_Question,
)
from vultron.wire.as2.vocab.base.objects.base import as_Object

_ACTOR = "https://example.org/actors/coordinator"


def _options(n: int) -> list[as_Object]:
    return [
        as_Object(id_=f"https://example.org/options/{i}", name=f"option {i}")
        for i in range(n)
    ]


@pytest.mark.parametrize("field", ["oneOf", "anyOf"])
def test_question_with_several_options_round_trips(field: str) -> None:
    """Several options survive serialisation and re-validation intact."""
    question = as_Question.model_validate(
        {"actor": _ACTOR, field: _options(3)}
    )

    body = json.loads(question.model_dump_json(by_alias=True))
    assert isinstance(body[field], list)
    assert [o["id"] for o in body[field]] == [
        f"https://example.org/options/{i}" for i in range(3)
    ]

    parsed = parse_activity(body)
    assert isinstance(parsed, as_Question)
    options = getattr(parsed, field)
    assert isinstance(options, list)
    assert [o.id_ for o in options] == [o.id_ for o in _options(3)]


def test_question_with_a_single_option_is_still_accepted() -> None:
    """AS2 lets a non-functional property carry one value; that still parses."""
    (option,) = _options(1)
    question = as_Question(actor=_ACTOR, oneOf=option)
    body = json.loads(question.model_dump_json(by_alias=True))
    parsed = parse_activity(body)
    assert isinstance(parsed, as_Question)
    assert isinstance(parsed.oneOf, type(option))
    assert parsed.oneOf.id_ == option.id_


def test_question_options_accept_uri_references() -> None:
    """Options may be bare URIs, as any AS2 object reference may."""
    uris: list[as_Object | as_Link | str] = [
        f"https://example.org/options/{i}" for i in range(2)
    ]
    question = as_Question(actor=_ACTOR, anyOf=uris)
    body = json.loads(question.model_dump_json(by_alias=True))
    assert body["anyOf"] == uris
    parsed = parse_activity(body)
    assert isinstance(parsed, as_Question)
    assert parsed.anyOf == uris


@pytest.mark.spec("CS-08-001")
@pytest.mark.parametrize("field", ["oneOf", "anyOf"])
@pytest.mark.parametrize("blank", ["", "   "])
def test_question_refuses_a_blank_option_reference(
    field: str, blank: str
) -> None:
    """A URI reference that is present must be non-empty, alone or in a list."""
    with pytest.raises(ValidationError):
        as_Question.model_validate({"actor": _ACTOR, field: blank})
    with pytest.raises(ValidationError):
        as_Question.model_validate(
            {"actor": _ACTOR, field: ["https://example.org/options/0", blank]}
        )


def test_question_refuses_both_any_of_and_one_of() -> None:
    """AS2 §4.1: ``anyOf`` and ``oneOf`` are mutually exclusive."""
    with pytest.raises(ValidationError, match="mutually exclusive"):
        as_Question.model_validate(
            {"actor": _ACTOR, "anyOf": _options(2), "oneOf": _options(1)}
        )

    body = {
        "type": "Question",
        "actor": _ACTOR,
        "anyOf": ["https://example.org/options/0"],
        "oneOf": ["https://example.org/options/1"],
    }
    with pytest.raises(ValidationError, match="mutually exclusive"):
        as_Question.model_validate(body)
