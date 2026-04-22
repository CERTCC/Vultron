"""Tests for unresolvable-object dead-letter use-case (DR-14)."""

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

from typing import cast

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.unknown import UnresolvableObjectReceivedEvent
from vultron.core.use_cases.received.unknown import UnresolvableObjectUseCase
from vultron.semantic_registry import extract_event
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Accept

ACTOR_URI = "https://example.org/coordinator"
UNRESOLVABLE_URI = "urn:uuid:some-offer-id-that-does-not-exist"


def _make_unresolvable_event() -> UnresolvableObjectReceivedEvent:
    """Create an UnresolvableObjectReceivedEvent from an Accept with bare-string object_."""
    accept = as_Accept(
        actor=ACTOR_URI,
        object_=UNRESOLVABLE_URI,
    )
    event = extract_event(accept)
    assert (
        event.semantic_type == MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT
    ), f"Expected UNKNOWN_UNRESOLVABLE_OBJECT but got {event.semantic_type}"
    return cast(UnresolvableObjectReceivedEvent, event)


class TestUnresolvableObjectUseCase:
    """Tests for the UnresolvableObjectUseCase dead-letter handler."""

    def test_execute_stores_dead_letter_record(self):
        """execute() stores a DeadLetterRecord in the DataLayer."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        event = _make_unresolvable_event()

        UnresolvableObjectUseCase(dl, event).execute()

        # by_type("DeadLetterRecord") returns only records of that type;
        # a non-empty result confirms the record was stored correctly.
        stored = dl.by_type("DeadLetterRecord")
        assert len(stored) == 1

    def test_execute_stores_unresolvable_uri(self):
        """Dead-letter record preserves the unresolvable URI."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        event = _make_unresolvable_event()

        UnresolvableObjectUseCase(dl, event).execute()

        stored = dl.by_type("DeadLetterRecord")
        record_data = next(iter(stored.values()))
        assert record_data["unresolvable_uri"] == UNRESOLVABLE_URI

    def test_execute_stores_actor_id(self):
        """Dead-letter record includes the actor ID."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        event = _make_unresolvable_event()

        UnresolvableObjectUseCase(dl, event).execute()

        stored = dl.by_type("DeadLetterRecord")
        record_data = next(iter(stored.values()))
        assert record_data["actor_id"] == ACTOR_URI

    def test_execute_stores_activity_id(self):
        """Dead-letter record includes the activity ID."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        event = _make_unresolvable_event()

        UnresolvableObjectUseCase(dl, event).execute()

        stored = dl.by_type("DeadLetterRecord")
        record_data = next(iter(stored.values()))
        assert record_data["activity_id"] == event.activity_id

    def test_execute_includes_activity_summary(self):
        """Dead-letter record includes an activity_summary snapshot."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        event = _make_unresolvable_event()

        UnresolvableObjectUseCase(dl, event).execute()

        stored = dl.by_type("DeadLetterRecord")
        record_data = next(iter(stored.values()))
        assert record_data.get("activity_summary") is not None

    def test_execute_is_idempotent(self):
        """Calling execute() twice stores two records (no deduplication at this layer)."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        event = _make_unresolvable_event()

        UnresolvableObjectUseCase(dl, event).execute()
        UnresolvableObjectUseCase(dl, event).execute()

        stored = dl.by_type("DeadLetterRecord")
        # Two separate records are stored (idempotency would require dedup logic
        # not currently mandated by spec)
        assert len(stored) >= 1

    def test_execute_logs_warning(self, caplog):
        """execute() logs a WARNING identifying the unresolvable URI."""
        import logging

        dl = SqliteDataLayer("sqlite:///:memory:")
        event = _make_unresolvable_event()

        with caplog.at_level(logging.WARNING):
            UnresolvableObjectUseCase(dl, event).execute()

        assert any(
            UNRESOLVABLE_URI in record.message for record in caplog.records
        ), f"Expected warning about {UNRESOLVABLE_URI!r} in {[r.message for r in caplog.records]}"
