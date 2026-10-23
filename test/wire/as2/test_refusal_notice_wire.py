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

"""The refusal notice on the wire: its factory, its pattern and its routing.

The CASE_MANAGER's refusal notice is a ``Reject`` whose object is the refused
activity, inline (CLP-05-001, ADR-0141).  Its pattern is the most general
``Reject`` pattern: it takes any inline activity but an ``Invite`` or an
``Offer``, whose ``Reject`` is the decline of that request, and it must not
change what any existing example dispatches to.
"""

import json
from typing import Any

import pytest

import vultron.semantic_registry as registry
from test.architecture._vocab_example_corpus import (
    activity_examples,
    wire_body,
)
from test.support.case_owner import CASE_OWNER_ID
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.events.fault import RefusalNoticeReceivedEvent
from vultron.errors import VultronActivityConstructionError
from vultron.semantic_registry import extract_event, find_matching_semantics
from vultron.wire.as2.enums import as_TransitiveActivityType as TAtype
from vultron.wire.as2.extractor._instances import RefusalNoticePattern
from vultron.wire.as2.factories import (
    refusal_notice_activity,
    reject_close_case_activity,
    rm_close_case_activity,
)
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Reject,
)
from vultron.wire.as2.vocab.examples import vocab_examples
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

CASE_MANAGER = "https://example.org/actors/case-manager"
VENDOR = "https://example.org/actors/vendor"


def _refused() -> dict[str, Any]:
    return wire_body(vocab_examples.add_fix_readiness_to_participant())


def _notice(refused: dict[str, Any] | None = None, **kwargs: Any) -> as_Reject:
    return refusal_notice_activity(
        refused if refused is not None else _refused(),
        "a precondition did not hold",
        actor=CASE_MANAGER,
        to=[VENDOR],
        **kwargs,
    )


def _received(activity: as_Reject) -> Any:
    return parse_activity(json.loads(json.dumps(wire_body(activity))))


def _event(activity: as_Reject) -> RefusalNoticeReceivedEvent:
    event = extract_event(_received(activity))
    assert isinstance(event, RefusalNoticeReceivedEvent)
    return event


@pytest.mark.spec("CLP-05-001")
def test_the_notice_carries_the_refused_activity_inline():
    refused = _refused()

    notice = wire_body(_notice(refused, context="https://example.org/cases/1"))

    assert notice["type"] == "Reject"
    assert notice["object"]["id"] == refused["id"]
    assert notice["object"]["type"] == refused["type"]
    assert notice["inReplyTo"] == refused["id"]
    assert notice["summary"] == "a precondition did not hold"
    assert notice["to"] == [VENDOR]
    assert notice["context"] == "https://example.org/cases/1"


def test_a_refused_body_that_is_not_an_activity_is_a_construction_error():
    with pytest.raises(VultronActivityConstructionError):
        refusal_notice_activity({"type": "Nonsense"}, "reason")


def test_a_blank_reason_is_a_construction_error():
    with pytest.raises(VultronActivityConstructionError):
        refusal_notice_activity(_refused(), "")


@pytest.mark.spec("CLP-05-001")
def test_the_notice_dispatches_as_a_refusal_notice():
    received = _received(_notice())

    assert find_matching_semantics(received) is MessageSemantics.REFUSAL_NOTICE


@pytest.mark.spec("CLP-05-001")
@pytest.mark.parametrize("verb", [TAtype.INVITE, TAtype.OFFER])
def test_a_reject_of_an_invite_or_an_offer_is_not_the_notice(verb: TAtype):
    """Those read as the decline of the request (CLP-05-001)."""
    received = _received(_notice())
    inner = received.object_.model_copy(update={"type_": str(verb)})

    assert not RefusalNoticePattern.match(
        received.model_copy(update={"object_": inner})
    )


@pytest.mark.parametrize(
    "obj",
    [
        "https://example.org/activities/1",
        as_VulnerabilityCase(attributed_to=CASE_OWNER_ID, name="Case"),
    ],
    ids=["bare-uri", "non-activity"],
)
def test_a_reject_of_anything_but_an_inline_activity_is_not_the_notice(obj):
    assert not RefusalNoticePattern.match(
        as_Reject(actor=CASE_MANAGER, object_=obj)
    )


@pytest.mark.spec("CLP-05-001")
def test_a_decline_of_a_leave_routes_to_the_refusal_notice():
    """CM-23-011's ``Reject(Leave(VulnerabilityCase))`` no longer lands on
    ``UnknownUseCase``; the event finds the case the Leave acted on."""
    case = as_VulnerabilityCase(
        attributed_to=CASE_OWNER_ID, name="Closing case"
    )
    leave = rm_close_case_activity(case=case, actor=VENDOR)
    decline = reject_close_case_activity(
        leave=leave, actor=CASE_MANAGER, to=[VENDOR]
    )

    event = _event(decline)

    assert event.semantic_type is MessageSemantics.REFUSAL_NOTICE
    assert event.refused_activity_id == leave.id_
    assert event.case_id == case.id_


def test_the_case_falls_back_to_the_refused_activitys_context():
    refused = {**_refused(), "context": "https://example.org/cases/7"}

    event = _event(_notice(refused))

    assert event.case_id == "https://example.org/cases/7"


def test_a_notice_naming_no_case_has_no_case():
    refused = {k: v for k, v in _refused().items() if k != "context"}

    event = _event(_notice(refused))

    assert event.case_id is None


_EXAMPLES = activity_examples()


def test_examples_were_collected():
    assert len(_EXAMPLES) > 50


@pytest.mark.spec("CLP-05-001")
@pytest.mark.parametrize("name", sorted(_EXAMPLES))
def test_no_existing_example_changes_its_semantics(
    name: str, monkeypatch: pytest.MonkeyPatch
):
    """The notice's pattern only takes what no other pattern matched.

    Each example dispatches to the same semantics with the refusal-notice
    entry removed from the registry, except the notice's own example.
    """
    activity = _EXAMPLES[name]
    with_entry = find_matching_semantics(activity)
    monkeypatch.setattr(
        registry,
        "SEMANTIC_REGISTRY",
        [
            e
            for e in registry.SEMANTIC_REGISTRY
            if e.semantics is not MessageSemantics.REFUSAL_NOTICE
        ],
    )
    without_entry = find_matching_semantics(activity)

    if name == "refusal_notice":
        assert with_entry is MessageSemantics.REFUSAL_NOTICE
        assert without_entry is not MessageSemantics.REFUSAL_NOTICE
    else:
        assert with_entry is without_entry
