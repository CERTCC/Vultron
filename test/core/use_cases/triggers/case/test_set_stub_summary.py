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

"""Tests for SvcSetStubSummaryUseCase (demo-only trigger).

Covers:
- Happy path: stub_summary is persisted to the actor's DataLayer case copy.
- Blank summary is refused at request-model construction (NonEmptyString).
- Missing actor raises VultronNotFoundError.
- Missing case raises VultronNotFoundError.
- No outbox activity is queued (_requires_trigger_activity = False).
"""

import pytest
from pydantic import ValidationError

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.core.use_cases.triggers.case import (
    SetStubSummaryTriggerRequest,
    SvcSetStubSummaryUseCase,
)
from vultron.errors import VultronNotFoundError
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)


def _make_actor(name: str) -> as_Service:
    return as_Service(
        name=name, url=f"https://example.org/{name.lower().replace(' ', '-')}"
    )


def _make_actor_dl(name: str) -> tuple[as_Service, SqliteDataLayer]:
    actor = _make_actor(name)
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor.id_)
    dl.clear_all()
    dl.create(actor)
    return actor, dl


class TestSetStubSummaryRequest:
    """Request-model validation tests (Pydantic layer, no use-case needed)."""

    def test_valid_request_accepted(self):
        req = SetStubSummaryTriggerRequest(
            actor_id="urn:test:actor",
            case_id="urn:test:case",
            stub_summary="A meaningful description",
        )
        assert req.stub_summary == "A meaningful description"

    def test_blank_summary_refused(self):
        """Empty string violates NonEmptyString — refused at construction."""
        with pytest.raises(ValidationError):
            SetStubSummaryTriggerRequest(
                actor_id="urn:test:actor",
                case_id="urn:test:case",
                stub_summary="",
            )

    def test_whitespace_only_summary_refused(self):
        """Whitespace-only string violates NonEmptyString — refused at construction."""
        with pytest.raises(ValidationError):
            SetStubSummaryTriggerRequest(
                actor_id="urn:test:actor",
                case_id="urn:test:case",
                stub_summary="   ",
            )


class TestSvcSetStubSummaryUseCase:
    """Use-case execution tests (DataLayer + BT path)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.actor, self.dl = _make_actor_dl("Reporter")
        self.case = as_VulnerabilityCase(name="Test Case")
        self.dl.create(self.case)
        yield
        self.dl.clear_all()
        reset_datalayer(self.actor.id_)

    def test_execute_persists_stub_summary_to_datalayer(self):
        """execute() writes stub_summary to the actor's DataLayer case copy."""
        request = SetStubSummaryTriggerRequest(
            actor_id=self.actor.id_,
            case_id=self.case.id_,
            stub_summary="This is the summary",
        )
        SvcSetStubSummaryUseCase(self.dl, request).execute()

        updated = self.dl.read_case(self.case.id_)
        assert updated is not None
        assert updated.stub_summary == "This is the summary"

    def test_execute_queues_no_outbox_activity(self):
        """No protocol activity is emitted (_requires_trigger_activity=False)."""
        before = set(self.dl.outbox_list())
        request = SetStubSummaryTriggerRequest(
            actor_id=self.actor.id_,
            case_id=self.case.id_,
            stub_summary="Some summary",
        )
        SvcSetStubSummaryUseCase(self.dl, request).execute()

        after = set(self.dl.outbox_list())
        assert after == before, (
            "set-stub-summary must not queue any outbox activity"
        )

    def test_unknown_actor_raises_not_found(self):
        """VultronNotFoundError when the actor is absent from the DataLayer."""
        request = SetStubSummaryTriggerRequest(
            actor_id="urn:uuid:no-such-actor",
            case_id=self.case.id_,
            stub_summary="Some summary",
        )
        with pytest.raises(VultronNotFoundError):
            SvcSetStubSummaryUseCase(self.dl, request).execute()

    def test_unknown_case_raises_not_found(self):
        """VultronNotFoundError when the case is absent from the DataLayer."""
        request = SetStubSummaryTriggerRequest(
            actor_id=self.actor.id_,
            case_id="urn:uuid:no-such-case",
            stub_summary="Some summary",
        )
        with pytest.raises(VultronNotFoundError):
            SvcSetStubSummaryUseCase(self.dl, request).execute()

    def test_execute_overwrites_existing_stub_summary(self):
        """A second call overwrites the previous stub_summary value."""
        for summary in ("first summary", "second summary"):
            request = SetStubSummaryTriggerRequest(
                actor_id=self.actor.id_,
                case_id=self.case.id_,
                stub_summary=summary,
            )
            SvcSetStubSummaryUseCase(self.dl, request).execute()

        updated = self.dl.read_case(self.case.id_)
        assert updated is not None
        assert updated.stub_summary == "second summary"
