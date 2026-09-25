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
"""The received evidence is the body as it arrived, sealed at parse (VM-08-002).

``parse_activity`` serializes the body before anything expands or validates it
and seals that text onto the parsed activity.  These tests pin the three ways the
evidence could stop being what arrived: taken too late (after the parser's own
expansion rewrote the body), reachable through the parsed object graph, or
reachable through the caller's ``dict`` (ISSUE-3584).
"""

import copy
import math
from typing import Any

import pytest

from vultron.core.models.base import CoreObject
from vultron.wire.as2 import parser
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.parser import parse_activity

ACTOR = "https://example.org/actors/finder"
REPORT_ID = "https://example.org/reports/r1"


def _offer_report() -> dict[str, Any]:
    return {
        "@context": "https://www.w3.org/ns/activitystreams",
        "type": "Offer",
        "id": "https://example.org/activities/offer-1",
        "actor": ACTOR,
        "published": "2026-01-02T03:04:05+00:00",
        "object": {
            "type": "VulnerabilityReport",
            "id": REPORT_ID,
            "name": "r",
            "content": "the sender's words",
            "attributedTo": ACTOR,
        },
        "to": ["https://example.org/actors/vendor"],
    }


@pytest.mark.spec("VM-08-002")
def test_evidence_is_taken_before_the_parser_expands_the_body(
    monkeypatch: pytest.MonkeyPatch,
):
    """Expansion that rewrites the body in place cannot reach the evidence.

    ``_expand_inline_object`` is the parser's first step after the evidence is
    taken; a version of it that mutates its input stands in for any later
    rewrite, and the evidence must still be the body as it arrived.
    """
    body = _offer_report()
    received = copy.deepcopy(body)
    expand = parser._expand_inline_object

    def rewriting_expand(data: dict[str, Any]) -> dict[str, Any]:
        data["object"]["content"] = "rewritten by expansion"
        return expand(data)

    monkeypatch.setattr(parser, "_expand_inline_object", rewriting_expand)

    activity = parse_activity(body)

    assert getattr(activity, "object_").content == "rewritten by expansion"
    assert activity.received_evidence == received


@pytest.mark.spec("VM-08-002")
def test_mutating_the_parsed_nested_object_leaves_the_evidence():
    """The nested core object is mutable by design; the evidence is not."""
    body = _offer_report()
    activity = parse_activity(body)
    report = getattr(activity, "object_")
    assert isinstance(report, CoreObject)

    report.content = "edited after parse"

    assert activity.received_evidence == body


@pytest.mark.spec("VM-08-002")
def test_mutating_the_callers_body_after_parse_leaves_the_evidence():
    """The evidence is a copy, not a view of the ``dict`` the caller passed."""
    body = _offer_report()
    received = copy.deepcopy(body)
    activity = parse_activity(body)

    body["object"]["content"] = "edited by the caller"
    body["actor"] = "https://example.org/actors/impostor"

    assert activity.received_evidence == received


@pytest.mark.spec("VM-08-002")
def test_each_read_of_the_evidence_is_a_fresh_copy():
    """What one reader does to its copy is invisible to the next reader."""
    activity = parse_activity(_offer_report())

    first = activity.received_evidence
    assert first is not None
    first["object"]["content"] = "edited by a reader"

    assert activity.received_evidence == _offer_report()


@pytest.mark.spec("VM-08-002")
def test_evidence_is_sealed_once():
    """Resealing the same text is a no-op; different text is refused."""
    activity = parse_activity(_offer_report())
    sealed = activity.received_evidence_json
    assert sealed is not None

    activity.seal_received_evidence(sealed)
    with pytest.raises(ValueError, match="sealed once"):
        activity.seal_received_evidence('{"type": "Offer"}')

    assert activity.received_evidence_json == sealed


@pytest.mark.spec("VM-08-002")
@pytest.mark.parametrize("value", [math.nan, math.inf, object()])
def test_body_that_is_not_json_is_refused(value: object):
    """A body holding a non-JSON value did not arrive as JSON; refuse it."""
    body = _offer_report()
    body["summary"] = value

    with pytest.raises(VultronParseValidationError, match="not JSON"):
        parse_activity(body)


@pytest.mark.spec("VM-08-002")
def test_an_activity_built_in_process_carries_no_evidence():
    """Only a received activity has received evidence."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Offer,
    )

    activity = as_Offer(actor=ACTOR, object_=REPORT_ID)

    assert activity.received_evidence is None
    assert activity.received_evidence_json is None
