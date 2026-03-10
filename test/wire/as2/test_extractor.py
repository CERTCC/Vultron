"""Tests for vultron.wire.as2.extractor."""

import pytest

from vultron.core.models.events import MessageSemantics
from vultron.wire.as2.extractor import (
    SEMANTICS_ACTIVITY_PATTERNS,
    ActivityPattern,
    find_matching_semantics,
)


def test_find_matching_semantics_returns_unknown_for_unmatched_activity():
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    from vultron.wire.as2.vocab.base.objects.actors import as_Actor

    # Create + Actor has no matching pattern (conservative string matching
    # means only explicit typed objects trigger pattern skips)
    actor = as_Actor(name="test-actor")
    activity = as_Create(
        actor="https://example.org/alice",
        object=actor,
    )
    result = find_matching_semantics(activity)
    assert result == MessageSemantics.UNKNOWN


def test_find_matching_semantics_returns_correct_semantics_for_create_report():
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        VulnerabilityReport,
    )

    report = VulnerabilityReport(name="VR-001", content="test report")
    activity = as_Create(
        actor="https://example.org/finder",
        object=report,
    )
    result = find_matching_semantics(activity)
    assert result == MessageSemantics.CREATE_REPORT


def test_all_message_semantics_except_unknown_have_patterns():
    missing = [
        m
        for m in MessageSemantics
        if m != MessageSemantics.UNKNOWN
        and m not in SEMANTICS_ACTIVITY_PATTERNS
    ]
    assert not missing, f"Missing patterns for: {missing}"


def test_activity_pattern_match_returns_false_for_wrong_activity_type():
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    from vultron.wire.as2.enums import (
        as_TransitiveActivityType as TAtype,
        as_ObjectType as AOtype,
    )

    pattern = ActivityPattern(activity_=TAtype.ADD, object_=AOtype.NOTE)
    activity = as_Create(
        actor="https://example.org/alice",
        object="https://example.org/notes/1",
    )
    assert not pattern.match(activity)
