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
"""A pattern never sees who sent the activity (SE-03-004, ADR-0152).

A semantic type says what an activity is; whether its sender may send it is
decided after routing, by the handler's sender-entitlement check.
"""

import pytest

from vultron.semantic_registry import SEMANTIC_REGISTRY
from vultron.wire.as2.extractor import ActivityPattern
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.examples import vocab_examples

#: The words a field that reads the sender would carry in its name.
_SENDER_WORDS = ("actor", "sender", "attributed", "role", "author")

#: The fields the base pattern matches on, or that describe it.  A new field
#: is a new thing patterns discriminate on, so it is reviewed here.
_BASE_FIELDS = {
    "description",
    "activity_",
    "strict",
    "accepts_bare_object",
    "to_",
    "object_",
    "target_",
    "context_",
}


def _pattern_classes() -> list[type[ActivityPattern]]:
    found: list[type[ActivityPattern]] = []
    pending: list[type[ActivityPattern]] = [ActivityPattern]
    while pending:
        cls = pending.pop()
        found.append(cls)
        pending.extend(cls.__subclasses__())
    return found


@pytest.mark.spec("SE-03-004")
def test_the_base_pattern_matches_only_the_activitys_shape():
    assert set(ActivityPattern.model_fields) == _BASE_FIELDS


@pytest.mark.spec("SE-03-004")
@pytest.mark.parametrize(
    "pattern_class", _pattern_classes(), ids=lambda c: c.__name__
)
def test_no_pattern_class_has_a_field_for_the_sender(
    pattern_class: type[ActivityPattern],
):
    sender_fields = [
        name
        for name in pattern_class.model_fields
        if any(word in name.lower() for word in _SENDER_WORDS)
    ]
    assert sender_fields == [], (
        f"{pattern_class.__name__} declares {sender_fields}: a pattern never"
        " discriminates on the sender's identity or role (SE-03-004)"
    )


#: Senders an example is re-sent from: an unrelated actor, and the
#: CASE_MANAGER's own actor, whose acts share the participant's type.
_OTHER_SENDERS = (
    "https://example.org/actors/someone-else",
    "https://example.org/actors/case-actor",
)

_EXAMPLES = sorted({o.example for e in SEMANTIC_REGISTRY for o in e.occasions})


@pytest.mark.spec("SE-03-004")
@pytest.mark.parametrize("example", _EXAMPLES)
def test_changing_only_the_sender_changes_no_match(example: str):
    """Every pattern gives the same answer whoever sent the activity.

    A field-name check cannot see a ``match()`` that reads ``actor`` or
    ``attributedTo``; this re-sends each occasion example from other
    senders and compares every registered pattern's verdict.
    """
    activity = getattr(vocab_examples, example)()
    assert isinstance(activity, as_Activity)
    patterns = [e.pattern for e in SEMANTIC_REGISTRY if e.pattern is not None]
    original = [p.match(activity) for p in patterns]
    assert any(original), f"{example}() matches no pattern"
    for sender in _OTHER_SENDERS:
        resent = activity.model_copy(
            update={"actor": sender, "attributed_to": sender}
        )
        assert [p.match(resent) for p in patterns] == original, (
            f"{example}() re-sent by {sender} matches differently"
        )
