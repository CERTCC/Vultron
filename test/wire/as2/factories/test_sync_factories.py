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
"""
Unit tests for vultron.wire.as2.factories.sync.

Spec coverage:
- AF-01-002: Factory functions return plain AS2 base types.
- AF-01-003: Explicit, domain-typed parameters for protocol-significant fields.
- AF-04-001: Factory functions wrap ValidationError in
  VultronActivityConstructionError.
- AF-04-002: All factory functions re-exported from factories/__init__.py.
"""

import pytest

from vultron.wire.as2.factories import (
    VultronActivityConstructionError,
    announce_log_entry_activity,
    reject_log_entry_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Announce,
    as_Reject,
)
from vultron.wire.as2.vocab.objects.case_log_entry import CaseLogEntry

_ACTOR_URI = "https://example.org/actors/alice"
_LAST_HASH = "abc123def456"


@pytest.fixture
def sample_log_entry() -> CaseLogEntry:
    return CaseLogEntry(
        case_id="https://example.org/cases/case-001",
        log_object_id="https://example.org/activities/act-001",
        event_type="ReportCreated",
    )


# ---------------------------------------------------------------------------
# announce_log_entry_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_announce_log_entry_returns_announce(sample_log_entry):
    result = announce_log_entry_activity(
        entry=sample_log_entry, actor=_ACTOR_URI
    )
    assert isinstance(result, as_Announce)


def test_announce_log_entry_object_is_entry(sample_log_entry):
    result = announce_log_entry_activity(
        entry=sample_log_entry, actor=_ACTOR_URI
    )
    assert result.object_ == sample_log_entry


def test_announce_log_entry_kwargs_forwarded(sample_log_entry):
    result = announce_log_entry_activity(
        entry=sample_log_entry, actor=_ACTOR_URI
    )
    assert result.actor == _ACTOR_URI


@pytest.mark.spec("AF-04-001")
def test_announce_log_entry_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        announce_log_entry_activity(
            entry="not-a-log-entry"  # type: ignore[arg-type]
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# reject_log_entry_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_reject_log_entry_returns_reject(sample_log_entry):
    result = reject_log_entry_activity(
        entry=sample_log_entry, actor=_ACTOR_URI
    )
    assert isinstance(result, as_Reject)


def test_reject_log_entry_object_is_entry(sample_log_entry):
    result = reject_log_entry_activity(
        entry=sample_log_entry, actor=_ACTOR_URI
    )
    assert result.object_ == sample_log_entry


def test_reject_log_entry_context_is_set(sample_log_entry):
    """context carries the last accepted hash string (SYNC-03-001)."""
    result = reject_log_entry_activity(
        entry=sample_log_entry, context=_LAST_HASH, actor=_ACTOR_URI
    )
    assert result.context == _LAST_HASH


@pytest.mark.spec("AF-04-001")
def test_reject_log_entry_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        reject_log_entry_activity(
            entry="not-a-log-entry"  # type: ignore[arg-type]
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# __init__.py re-exports (AF-04-002)
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-04-002")
def test_all_sync_factories_importable_from_package():
    from vultron.wire.as2.factories import (  # noqa: F401
        announce_log_entry_activity,
        reject_log_entry_activity,
    )
