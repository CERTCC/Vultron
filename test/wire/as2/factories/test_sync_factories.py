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

from vultron.core.models.ledger_position import LedgerPosition
from vultron.wire.as2.factories import (
    VultronActivityConstructionError,
    announce_log_entry_activity,
    read_ledger_entry_activity,
    read_ledger_position_activity,
    reject_log_entry_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Announce,
    as_Read,
    as_Reject,
)
from vultron.wire.as2.vocab.objects.case_ledger_entry import as_CaseLedgerEntry

_ACTOR_URI = "https://example.org/actors/alice"
_LAST_HASH = "abc123def456"


@pytest.fixture
def sample_log_entry() -> as_CaseLedgerEntry:
    return as_CaseLedgerEntry(
        case_id="https://example.org/cases/case-001",
        log_object_id="https://example.org/activities/act-001",
        semantic_type="ReportCreated",
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


@pytest.mark.spec("SYNC-02-004")
def test_announce_log_entry_object_is_entry(sample_log_entry):
    result = announce_log_entry_activity(
        entry=sample_log_entry, actor=_ACTOR_URI
    )
    assert result.object_ == sample_log_entry


@pytest.mark.spec("SYNC-02-002")
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


@pytest.mark.spec("SYNC-03-001")
def test_reject_log_entry_object_is_entry(sample_log_entry):
    result = reject_log_entry_activity(
        entry=sample_log_entry, actor=_ACTOR_URI
    )
    assert result.object_ == sample_log_entry


@pytest.mark.spec("SYNC-03-002")
@pytest.mark.spec("SYNC-18-001")
def test_reject_log_entry_states_the_tail_as_its_position(sample_log_entry):
    """The last accepted entry is the Reject's ``ledgerPosition``; ``context``
    names the case (SYNC-18-001)."""
    tail = LedgerPosition(log_index=0, entry_hash=_LAST_HASH)
    result = reject_log_entry_activity(
        entry=sample_log_entry, ledger_position=tail, actor=_ACTOR_URI
    )
    assert result.ledger_position == tail
    assert result.context == sample_log_entry.case_id


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


# ---------------------------------------------------------------------------
# Read(CaseLedgerEntry) by position (SYNC-17-001, SYNC-17-008)
# ---------------------------------------------------------------------------

_CASE_URI = "https://example.org/cases/case-001"
_POSITION = LedgerPosition(log_index=4, entry_hash="ab" * 32)


@pytest.mark.spec("SYNC-17-001", "SYNC-17-008")
def test_read_ledger_position_names_the_entry_at_the_position():
    """The Read names the entry by its ledger coordinates and states them."""
    read = read_ledger_position_activity(
        _CASE_URI, _POSITION, actor=_ACTOR_URI
    )

    assert isinstance(read, as_Read)
    assert read.object_ == f"{_CASE_URI}/log/4"
    assert read.context == _CASE_URI
    assert read.ledger_position == _POSITION


@pytest.mark.spec("SYNC-17-001")
def test_read_ledger_position_refuses_the_empty_ledger():
    """The empty ledger's position names no entry, so there is no Read."""
    empty = LedgerPosition(log_index=-1, entry_hash="cd" * 32)

    with pytest.raises(VultronActivityConstructionError, match="no entry"):
        read_ledger_position_activity(_CASE_URI, empty, actor=_ACTOR_URI)


@pytest.mark.spec("SYNC-17-001")
def test_read_ledger_entry_is_the_read_of_its_position():
    """Naming an entry and naming its position build the same statement."""
    sample_log_entry = as_CaseLedgerEntry(
        case_id=_CASE_URI,
        log_index=4,
        log_object_id="https://example.org/activities/act-004",
        semantic_type="ReportCreated",
        prev_log_hash="ef" * 32,
        entry_hash="ab" * 32,
    )
    by_entry = read_ledger_entry_activity(sample_log_entry, actor=_ACTOR_URI)
    by_position = read_ledger_position_activity(
        sample_log_entry.case_id,
        LedgerPosition(
            log_index=sample_log_entry.log_index,
            entry_hash=sample_log_entry.entry_hash,
        ),
        actor=_ACTOR_URI,
    )

    assert by_entry.object_ == sample_log_entry.id_ == by_position.object_
    assert by_entry.ledger_position == by_position.ledger_position


@pytest.mark.spec("AF-04-001")
def test_read_ledger_entry_without_a_hash_raises(sample_log_entry):
    """An entry whose position cannot be stated is a construction error."""
    with pytest.raises(VultronActivityConstructionError):
        read_ledger_entry_activity(sample_log_entry, actor=_ACTOR_URI)
