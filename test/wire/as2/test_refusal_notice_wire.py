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

The CASE_MANAGER's refusal notice is a ``Refuse`` whose object is the refused
activity, inline (CLP-05-001, ADR-0141), sent as ``"type": ["Refuse",
"Reject"]`` (ADR-0196).  Its pattern is the one ``Refuse`` pattern: it takes
a ``Refuse`` of any inline activity, an ``Invite`` or an ``Offer`` included,
and no ``Reject``, so a participant's decline of a request stays a decline.
It must not change what any existing example dispatches to.
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
from test.support.objects import authored_at, make
from test.support.signing import resigned
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.events.fault import RefusalNoticeReceivedEvent
from vultron.errors import VultronActivityConstructionError
from vultron.semantic_registry import extract_event, find_matching_semantics
from vultron.wire.as2.enums import as_TransitiveActivityType as TAtype
from vultron.wire.as2.extractor._instances import RefusalNoticePattern
from vultron.wire.as2.factories import (
    refusal_notice_activity,
    rm_close_case_activity,
)
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Reject,
)
from vultron.wire.as2.vocab.examples import vocab_examples
from vultron.wire.as2.vocab.extension_activities import as_Refuse
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

CASE_MANAGER = "https://example.org/actors/case-manager"
VENDOR = "https://example.org/actors/vendor"


def _refused() -> dict[str, Any]:
    return wire_body(vocab_examples.add_fix_readiness_to_participant())


def _notice(refused: dict[str, Any] | None = None, **kwargs: Any) -> as_Refuse:
    return refusal_notice_activity(
        refused if refused is not None else _refused(),
        "a precondition did not hold",
        actor=CASE_MANAGER,
        to=[VENDOR],
        **kwargs,
        at=authored_at(),
    )


def _received(activity: as_Activity) -> Any:
    return parse_activity(json.loads(json.dumps(wire_body(activity))))


def _event(activity: as_Activity) -> RefusalNoticeReceivedEvent:
    event = extract_event(_received(activity))
    assert isinstance(event, RefusalNoticeReceivedEvent)
    return event


@pytest.mark.spec("CLP-05-001")
def test_the_notice_carries_the_refused_activity_inline():
    refused = _refused()

    notice = wire_body(_notice(refused, context="https://example.org/cases/1"))

    assert notice["type"] == ["Refuse", "Reject"]
    assert notice["object"]["id"] == refused["id"]
    assert notice["object"]["type"] == refused["type"]
    assert notice["inReplyTo"] == refused["id"]
    assert notice["summary"] == "a precondition did not hold"
    assert notice["to"] == [VENDOR]
    assert notice["context"] == "https://example.org/cases/1"


def test_a_refused_body_that_is_not_an_activity_is_a_construction_error():
    with pytest.raises(VultronActivityConstructionError):
        refusal_notice_activity(
            {"type": "Nonsense"}, "reason", at=authored_at()
        )


def test_a_blank_reason_is_a_construction_error():
    with pytest.raises(VultronActivityConstructionError):
        refusal_notice_activity(_refused(), "", at=authored_at())


@pytest.mark.spec("CLP-05-001")
def test_the_notice_dispatches_as_a_refusal_notice():
    received = _received(_notice())

    assert find_matching_semantics(received) is MessageSemantics.REFUSAL_NOTICE


@pytest.mark.spec("CLP-05-001")
def test_the_notice_reads_back_as_a_refuse():
    """A plain AS2 reader sees a ``Reject``; Vultron reads a ``Refuse``."""
    received = _received(_notice())

    assert type(received) is as_Refuse
    assert received.type_ == TAtype.REFUSE


#: A participant's decline of each request kind, and the request it declines.
_DECLINES = {
    "invite": (
        vocab_examples.reject_embargo,
        MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE,
    ),
    "offer": (
        vocab_examples.reject_case_ownership_transfer,
        MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER,
    ),
}


@pytest.mark.spec("CLP-05-001")
@pytest.mark.spec("CLP-02-016")
@pytest.mark.parametrize("name", sorted(_DECLINES))
def test_a_refuse_of_a_request_is_the_notice_and_its_reject_the_decline(
    name: str,
):
    """Who decides, not the shape, tells a refusal from a decline (ADR-0196).

    The CASE_MANAGER's ``Refuse`` of an ``Invite`` or an ``Offer`` reaches the
    refusal-notice use case; a participant's ``Reject`` of the same request
    still reaches its decline semantics.
    """
    build_decline, decline_semantics = _DECLINES[name]
    decline = build_decline()
    assert isinstance(decline.object_, as_Activity)
    request = wire_body(decline.object_)

    refused = _received(_notice(request))
    declined = _received(decline)

    assert str(refused.object_.type_) == request["type"]
    assert find_matching_semantics(refused) is MessageSemantics.REFUSAL_NOTICE
    assert find_matching_semantics(declined) is decline_semantics
    assert not RefusalNoticePattern.match(declined)


@pytest.mark.spec("CLP-05-001")
def test_a_case_managers_reject_of_an_activity_is_not_the_notice():
    """A plain ``Reject`` of a non-request activity no longer reads as one.

    ADR-0196 keeps no fallback: every sender of a refusal notice is this
    implementation, and it sends a ``Refuse``.
    """
    notice = _received(_notice())
    reject = make(
        as_Reject,
        actor=CASE_MANAGER,
        to=[VENDOR],
        object_=notice.object_,
        in_reply_to=notice.in_reply_to,
        summary=notice.summary,
    )

    received = _received(reject)

    assert type(received) is as_Reject
    assert not RefusalNoticePattern.match(received)
    assert find_matching_semantics(received) is MessageSemantics.UNKNOWN


@pytest.mark.parametrize(
    "obj",
    [
        "https://example.org/activities/1",
        make(as_VulnerabilityCase, attributed_to=CASE_OWNER_ID, name="Case"),
    ],
    ids=["bare-uri", "non-activity"],
)
def test_a_reject_of_anything_but_an_inline_activity_is_not_the_notice(obj):
    assert not RefusalNoticePattern.match(
        make(as_Reject, actor=CASE_MANAGER, object_=obj)
    )


@pytest.mark.spec("CLP-05-001")
def test_a_refuse_of_a_leave_finds_the_case_the_leave_acted_on():
    """The event of a ``Refuse(Leave(VulnerabilityCase))`` names the case."""
    case = make(
        as_VulnerabilityCase, attributed_to=CASE_OWNER_ID, name="Closing case"
    )
    leave = rm_close_case_activity(case=case, actor=VENDOR, at=authored_at())

    event = _event(_notice(wire_body(leave)))

    assert event.semantic_type is MessageSemantics.REFUSAL_NOTICE
    assert event.refused_activity_id == leave.id_
    assert event.case_id == case.id_


def test_the_case_falls_back_to_the_refused_activitys_context():
    refused = resigned(_refused(), context="https://example.org/cases/7")

    event = _event(_notice(refused))

    assert event.case_id == "https://example.org/cases/7"


def test_a_notice_naming_no_case_has_no_case():
    refused = resigned(_refused(), alter=lambda b: b.pop("context", None))

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
