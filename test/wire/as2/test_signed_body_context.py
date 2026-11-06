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
"""A signed body parses: its ``@context`` is a list, its ``proof`` set aside.

Signing appends the data-integrity context to a body's own ``@context``
(FEP-8b32), so every signed body's context is a list, and the parser must
accept one on the envelope and on every nested object.  Nothing reads the
``proof`` at the parse edge yet: verification runs before the parser
(SIG-03-003, #5386), so the parser sets the key aside and reports it like any
foreign key (MV-11-003), and the received evidence keeps it (SIG-04-001).
"""

import logging
from typing import Any

import pytest
from pydantic import ValidationError

from test.support.received import delivered_body
from test.support.signing import signed_body
from vultron.wire.as2.factories import add_note_to_case_activity
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.signing import DATA_INTEGRITY_CONTEXT
from vultron.wire.as2.vocab.base.base import (
    ACTIVITY_STREAMS_NS,
    VULTRON_CONTEXT_URI,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Add
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

ACTOR = "https://example.org/actors/finder"
CASE_ID = "https://example.org/cases/signed-context"
SIGNED_CONTEXT = [
    ACTIVITY_STREAMS_NS,
    VULTRON_CONTEXT_URI,
    DATA_INTEGRITY_CONTEXT,
]


def _signed_add_note() -> dict[str, Any]:
    note = as_Note(
        id_="https://example.org/notes/signed-context",
        content="signed",
        context=CASE_ID,
    )
    activity = add_note_to_case_activity(
        note, target=CASE_ID, actor=ACTOR, to=["https://example.org/a/cm"]
    )
    body = delivered_body(activity)
    body["object"]["@context"] = [VULTRON_CONTEXT_URI, ACTIVITY_STREAMS_NS]
    return signed_body(body)


@pytest.mark.spec("VM-10-001")
@pytest.mark.spec("SIG-01-002")
def test_a_signed_body_parses_with_its_list_context():
    body = _signed_add_note()
    assert body["@context"] == SIGNED_CONTEXT

    parsed = parse_activity(body)

    assert parsed.context_ == SIGNED_CONTEXT
    assert isinstance(parsed, as_Add)
    assert isinstance(parsed.object_, as_Note)
    assert parsed.object_.context_ == [
        VULTRON_CONTEXT_URI,
        ACTIVITY_STREAMS_NS,
    ]
    dumped = parsed.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert dumped["@context"] == SIGNED_CONTEXT


@pytest.mark.spec("MV-11-003")
@pytest.mark.spec("MV-11-010")
@pytest.mark.spec("SIG-04-001")
def test_the_proof_is_set_aside_and_kept_in_the_evidence(
    caplog: pytest.LogCaptureFixture,
):
    body = _signed_add_note()

    with caplog.at_level(logging.INFO):
        parsed = parse_activity(body)

    assert "proof" not in parsed.model_dump(by_alias=True)
    assert parsed.received_evidence is not None
    assert parsed.received_evidence["proof"] == body["proof"]
    reports = [
        r
        for r in caplog.records
        if r.levelno == logging.INFO and "'proof'" in r.getMessage()
    ]
    assert len(reports) == 1


@pytest.mark.spec("VM-10-001")
def test_a_single_context_still_parses_as_one_string():
    body = _signed_add_note()
    body["@context"] = ACTIVITY_STREAMS_NS
    del body["proof"]

    assert parse_activity(body).context_ == ACTIVITY_STREAMS_NS


@pytest.mark.spec("CS-08-002")
@pytest.mark.parametrize(
    "context",
    [[], [""], ["   "], [VULTRON_CONTEXT_URI, ""], ""],
    ids=[
        "empty-list",
        "blank-entry",
        "whitespace-entry",
        "one-blank-entry",
        "blank-string",
    ],
)
def test_a_wire_object_refuses_an_empty_or_blank_context(context: Any):
    _assert_context_refused(context)


@pytest.mark.parametrize(
    "context",
    [{"@vocab": "x"}, [VULTRON_CONTEXT_URI, {"@vocab": "x"}]],
    ids=["term-map", "term-map-entry"],
)
def test_a_wire_object_refuses_an_inline_context_object(context: Any):
    """``@context`` is IRIs only; nothing Vultron reads defines terms inline."""
    _assert_context_refused(context)


def _assert_context_refused(context: Any) -> None:
    with pytest.raises(ValidationError) as raised:
        as_Activity.model_validate({"@context": context, "actor": ACTOR})

    assert {error["loc"][0] for error in raised.value.errors()} == {"@context"}
